import os
import time
import math
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from PIL import Image, ImageChops, ImageDraw

from config import DATA_DIR, DEFAULT_USER_AGENT, TZ_VN

# Các thư mục lưu trữ ảnh chụp và so sánh giao diện
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
VISUAL_BASELINES_DIR = DATA_DIR / "visual_baselines"
VISUAL_DIFFS_DIR = DATA_DIR / "visual_diffs"

DEFAULT_VIEWPORT = {"width": 1280, "height": 800}
DEFAULT_DIFF_THRESHOLD_PERCENT = 3.0  # Chênh lệch > 3.0% diện tích pixel được coi là biến dạng giao diện (Visual Regression)
COLOR_DIFF_TOLERANCE = 15  # Sai số màu chấp nhận được cho từng kênh R, G, B để chống khử răng cưa font (anti-aliasing)

def _sanitize_name(name: str) -> str:
    """Chuyển tên website thành chuỗi an toàn cho tên file."""
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name.strip().lower())

def _ensure_dirs():
    """Tạo các thư mục lưu trữ ảnh nếu chưa tồn tại."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    VISUAL_BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    VISUAL_DIFFS_DIR.mkdir(parents=True, exist_ok=True)

def _mask_dynamic_elements(page, mask_selectors: List[str]):
    """
    Chuẩn hóa và che đi các vùng nội dung động (thời gian, quảng cáo, banner động)
    bằng cách tiêm CSS che khuất để tránh cảnh báo giả (false positive).
    """
    if not mask_selectors:
        return
    
    css_rules = ", ".join(mask_selectors)
    js_code = f"""() => {{
        const elements = document.querySelectorAll('{css_rules}');
        elements.forEach(el => {{
            el.style.visibility = 'hidden';
            el.style.opacity = '0';
        }});
    }}"""
    try:
        page.evaluate(js_code)
    except Exception:
        pass

def _compare_images(
    baseline_path: Path,
    current_path: Path,
    diff_output_path: Path,
    threshold_percent: float = DEFAULT_DIFF_THRESHOLD_PERCENT
) -> Tuple[float, int, int, bool]:
    """
    So sánh pixel giữa 2 ảnh chụp (Baseline vs Current).
    Tạo ảnh diff trực quan với các vùng sai khác được đánh dấu màu đỏ nổi bật.
    
    Trả về: (diff_percentage, diff_pixels_count, total_pixels, is_regression)
    """
    img_base = Image.open(baseline_path).convert("RGBA")
    img_curr = Image.open(current_path).convert("RGBA")

    # Đồng bộ kích thước ảnh nếu có sự chênh lệch nhỏ
    max_w = max(img_base.width, img_curr.width)
    max_h = max(img_base.height, img_curr.height)

    if img_base.size != (max_w, max_h):
        padded_base = Image.new("RGBA", (max_w, max_h), (255, 255, 255, 255))
        padded_base.paste(img_base, (0, 0))
        img_base = padded_base

    if img_curr.size != (max_w, max_h):
        padded_curr = Image.new("RGBA", (max_w, max_h), (255, 255, 255, 255))
        padded_curr.paste(img_curr, (0, 0))
        img_curr = padded_curr

    total_pixels = max_w * max_h
    diff_pixels_count = 0

    base_data = img_base.load()
    curr_data = img_curr.load()

    # Tạo ảnh Diff trực quan (nền làm mờ xám + vùng lỗi tô màu đỏ sáng)
    diff_img = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
    diff_draw = diff_img.load()

    for y in range(max_h):
        for x in range(max_w):
            r1, g1, b1, a1 = base_data[x, y]
            r2, g2, b2, a2 = curr_data[x, y]

            # Tính khoảng cách màu Euclidean giữa 2 pixel
            dr = abs(r1 - r2)
            dg = abs(g1 - g2)
            db = abs(b1 - b2)

            if dr > COLOR_DIFF_TOLERANCE or dg > COLOR_DIFF_TOLERANCE or db > COLOR_DIFF_TOLERANCE:
                diff_pixels_count += 1
                # Đánh dấu pixel khác biệt màu đỏ hồng neon rực rỡ
                diff_draw[x, y] = (255, 0, 80, 255)
            else:
                # Giữ nguyên pixel hiện tại nhưng làm mờ xám nhẹ
                gray = int(0.299 * r2 + 0.587 * g2 + 0.114 * b2)
                diff_draw[x, y] = (gray, gray, gray, 160)

    diff_percentage = round((diff_pixels_count / total_pixels) * 100, 3)
    is_regression = diff_percentage > threshold_percent

    # Lưu ảnh diff nếu có phát hiện sai khác
    diff_img.save(diff_output_path, "PNG")

    return diff_percentage, diff_pixels_count, total_pixels, is_regression

def check_visual_regression(
    url: str,
    website_identifier: str,
    baseline_image_path: Optional[str] = None,
    mask_selectors: Optional[List[str]] = None,
    diff_threshold_percent: float = DEFAULT_DIFF_THRESHOLD_PERCENT,
    full_page: bool = False,
    update_baseline_if_missing: bool = True,
    timeout: float = 20.0
) -> Dict[str, Any]:
    """
    Công cụ Visual Regression Monitoring dựa trên Playwright Visual Comparisons (RULE_BUILD_TOOLS.md mục 6).
    
    Quy trình:
    1. Sử dụng Playwright mở website với Viewport cố định (1280x800).
    2. Che phủ (Mask) các vùng nội dung động (quảng cáo, đồng hồ, banner xoay vòng) để chống false positive.
    3. Chụp ảnh màn hình hiện tại (screenshot).
    4. So sánh với ảnh baseline chuẩn:
       - Nếu chưa có baseline: Tự động khởi tạo baseline mới từ ảnh chụp đầu tiên.
       - Nếu đã có baseline: So sánh chi tiết từng pixel, đo tỷ lệ chênh lệch (%) và tạo ảnh Diff trực quan.
    """
    _ensure_dirs()
    safe_name = _sanitize_name(website_identifier)
    timestamp_str = datetime.now(TZ_VN).strftime("%Y%m%d_%H%M%S")

    current_img_name = f"{safe_name}_{timestamp_str}.png"
    current_img_path = SCREENSHOTS_DIR / current_img_name
    latest_curr_symlink = SCREENSHOTS_DIR / f"{safe_name}_latest.png"

    default_baseline_path = VISUAL_BASELINES_DIR / f"{safe_name}_baseline.png"
    target_baseline_path = Path(baseline_image_path) if baseline_image_path else default_baseline_path

    diff_img_path = VISUAL_DIFFS_DIR / f"{safe_name}_diff_{timestamp_str}.png"

    result = {
        "url": url,
        "website_identifier": website_identifier,
        "is_regression_detected": False,
        "diff_percentage": 0.0,
        "diff_pixels_count": 0,
        "total_pixels": 0,
        "diff_threshold_percent": diff_threshold_percent,
        "is_baseline_created": False,
        "baseline_image_path": str(target_baseline_path) if target_baseline_path.exists() else None,
        "current_image_path": str(current_img_path),
        "diff_image_path": None,
        "masked_selectors": mask_selectors or [],
        "viewport": DEFAULT_VIEWPORT,
        "capture_time_ms": 0.0,
        "status": "HEALTHY",
        "error": None
    }

    try:
        from playwright.sync_api import sync_playwright

        start_t = time.time()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport=DEFAULT_VIEWPORT,
                user_agent=DEFAULT_USER_AGENT,
                device_scale_factor=1
            )
            page = context.new_page()

            try:
                page.goto(url, timeout=int(timeout * 1000), wait_until="load")
            except Exception:
                # Fallback nếu mạng chậm hoặc sự kiện load bị trễ
                page.goto(url, timeout=int(timeout * 1000), wait_until="domcontentloaded")
            
            page.wait_for_timeout(400)  # Chờ layout và web fonts ổn định

            # Che (Mask) các thành phần nội dung động
            if mask_selectors:
                _mask_dynamic_elements(page, mask_selectors)

            # Chụp ảnh màn hình
            page.screenshot(path=str(current_img_path), full_page=full_page)
            # Lưu bản sao latest
            page.screenshot(path=str(latest_curr_symlink), full_page=full_page)

            browser.close()

        result["capture_time_ms"] = round((time.time() - start_t) * 1000, 2)

        # Kiểm tra Baseline
        if not target_baseline_path.exists():
            if update_baseline_if_missing:
                # Khởi tạo ảnh baseline đầu tiên
                import shutil
                shutil.copyfile(str(current_img_path), str(target_baseline_path))
                result["is_baseline_created"] = True
                result["baseline_image_path"] = str(target_baseline_path)
                result["status"] = "BASELINE_INITIALIZED"
                return result
            else:
                result["status"] = "NO_BASELINE"
                result["error"] = f"Chưa có ảnh baseline chuẩn tại '{target_baseline_path}'."
                return result

        # Thực hiện so sánh Pixel với Baseline
        diff_pct, diff_pix, total_pix, is_regr = _compare_images(
            baseline_path=target_baseline_path,
            current_path=current_img_path,
            diff_output_path=diff_img_path,
            threshold_percent=diff_threshold_percent
        )

        result["diff_percentage"] = diff_pct
        result["diff_pixels_count"] = diff_pix
        result["total_pixels"] = total_pix
        result["is_regression_detected"] = is_regr
        result["baseline_image_path"] = str(target_baseline_path)
        result["diff_image_path"] = str(diff_img_path)

        if is_regr:
            result["status"] = "VISUAL_REGRESSION_DETECTED"
        else:
            result["status"] = "HEALTHY"

    except Exception as e:
        result["error"] = str(e)
        result["status"] = "ERROR"

    return result
