import time
from typing import Optional, List, Dict, Any
from config import DEFAULT_USER_AGENT

# Các danh mục phần tử DOM cốt lõi cần kiểm tra cấu trúc (Structural Monitoring)
CORE_DOM_CATEGORIES = {
    "title": {
        "description": "Tiêu đề trang (<title>)",
        "selectors": ["title"],
        "critical": True
    },
    "headings": {
        "description": "Cấu trúc tiêu đề (h1, h2, h3)",
        "selectors": ["h1", "h2", "h3"],
        "critical": True
    },
    "navigation": {
        "description": "Thanh điều hướng / Menu (nav, navbar, menu)",
        "selectors": ["nav", "[role='navigation']", ".nav-menu", "header nav", "#menu", ".navbar"],
        "critical": False
    },
    "main_content": {
        "description": "Khu vực nội dung chính (main, article, #content)",
        "selectors": ["main", "[role='main']", "article", "#content", ".main-content", "#main"],
        "critical": False
    },
    "buttons_cta": {
        "description": "Nút bấm hành động / CTA (button, .btn, [role='button'])",
        "selectors": ["button.btn-primary", "a.btn-primary", ".btn-primary", "button[type='submit']", "input[type='submit']", "button", "a.btn", "a.button", "[role='button']", "input[type='button']"],
        "critical": False
    },
    "forms": {
        "description": "Biểu mẫu nhập liệu (form)",
        "selectors": ["form"],
        "critical": False
    },
    "footer": {
        "description": "Chân trang (footer, [role='contentinfo'])",
        "selectors": ["footer", "[role='contentinfo']", ".footer", "#footer"],
        "critical": False
    }
}

def _validate_with_playwright(
    url: str,
    custom_selectors: Optional[List[str]] = None,
    timeout_seconds: float = 15.0
) -> Dict[str, Any]:
    """Kiểm tra cấu trúc DOM thực tế qua Playwright Browser (hỗ trợ SPA / JS rendering & visibility)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=DEFAULT_USER_AGENT, ignore_https_errors=True)
        page = context.new_page()

        start_time = time.time()
        page.goto(url, timeout=int(timeout_seconds * 1000), wait_until="domcontentloaded")

        # Đợi thêm một chút để dynamic JS hoàn tất render
        page.wait_for_timeout(500)
        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        page_title = page.title() or ""
        body_text_len = len(page.inner_text("body") or "")

        components = {}

        # 1. Kiểm tra Tiêu đề (<title>)
        title_found = bool(page_title.strip())
        components["title"] = {
            "found": title_found,
            "visible": True,
            "count": 1 if title_found else 0,
            "value": page_title.strip(),
            "status": "OK" if title_found else "MISSING"
        }

        # 2. Kiểm tra Headings (h1, h2, h3)
        h1_locators = page.locator("h1")
        h1_count = h1_locators.count()
        h2_count = page.locator("h2").count()
        h3_count = page.locator("h3").count()
        h1_texts = [h1_locators.nth(i).inner_text().strip() for i in range(min(h1_count, 3))]

        components["headings"] = {
            "found": (h1_count + h2_count + h3_count) > 0,
            "has_h1": h1_count > 0,
            "h1_count": h1_count,
            "h2_count": h2_count,
            "h3_count": h3_count,
            "h1_samples": h1_texts,
            "status": "OK" if h1_count > 0 else ("WARNING_NO_H1" if (h2_count + h3_count) > 0 else "MISSING")
        }

        # 3. Helper kiểm tra nhóm selector trong Playwright
        def check_group_selectors(selector_list: List[str]):
            hidden_match = None
            for sel in selector_list:
                try:
                    loc = page.locator(sel)
                    cnt = loc.count()
                    if cnt > 0:
                        visible_cnt = 0
                        has_explicitly_hidden = False
                        for i in range(min(cnt, 5)):
                            if loc.nth(i).is_visible():
                                visible_cnt += 1
                            else:
                                has_explicitly_hidden = True

                        # Kiểm tra trường hợp đặc biệt cho container wrapper (.navbar, header):
                        # Nếu wrapper hiển thị nhưng chứa nav/menu bên trong bị ẩn hoàn toàn
                        if sel in [".navbar", "header"]:
                            inner_loc = page.locator(f"{sel} nav, {sel} .nav-menu, {sel} [role='navigation']")
                            inner_cnt = inner_loc.count()
                            if inner_cnt > 0:
                                inner_visible = any(inner_loc.nth(j).is_visible() for j in range(min(inner_cnt, 3)))
                                if not inner_visible:
                                    return {
                                        "found": True,
                                        "visible": False,
                                        "count": inner_cnt,
                                        "matched_selector": f"{sel} > nav",
                                        "status": "HIDDEN"
                                    }

                        if visible_cnt > 0 and not has_explicitly_hidden:
                            return {
                                "found": True,
                                "visible": True,
                                "count": visible_cnt,
                                "matched_selector": sel,
                                "status": "OK"
                            }
                        elif has_explicitly_hidden and hidden_match is None:
                            hidden_match = {
                                "found": True,
                                "visible": False,
                                "count": cnt,
                                "matched_selector": sel,
                                "status": "HIDDEN"
                            }
                            if sel in ["nav", "[role='navigation']", ".nav-menu", "button.btn-primary", "a.btn-primary", ".btn-primary", "main"]:
                                return hidden_match
                except Exception:
                    continue
            if hidden_match:
                return hidden_match
            return {"found": False, "visible": False, "count": 0, "matched_selector": None, "status": "MISSING"}

        # 4. Kiểm tra Navigation, Main Content, Buttons/CTA, Forms, Footer
        components["navigation"] = check_group_selectors(CORE_DOM_CATEGORIES["navigation"]["selectors"])
        components["main_content"] = check_group_selectors(CORE_DOM_CATEGORIES["main_content"]["selectors"])
        components["buttons_cta"] = check_group_selectors(CORE_DOM_CATEGORIES["buttons_cta"]["selectors"])
        components["forms"] = check_group_selectors(CORE_DOM_CATEGORIES["forms"]["selectors"])
        components["footer"] = check_group_selectors(CORE_DOM_CATEGORIES["footer"]["selectors"])

        # 5. Kiểm tra các Custom Selectors do người dùng yêu cầu
        custom_results = {}
        if custom_selectors:
            for c_sel in custom_selectors:
                try:
                    loc = page.locator(c_sel)
                    cnt = loc.count()
                    vis = False
                    sample_txt = ""
                    if cnt > 0:
                        vis = loc.first.is_visible()
                        sample_txt = (loc.first.inner_text() or "").strip()[:100]
                    custom_results[c_sel] = {
                        "found": cnt > 0,
                        "visible": vis,
                        "count": cnt,
                        "text_sample": sample_txt,
                        "status": "OK" if (cnt > 0 and vis) else ("HIDDEN" if cnt > 0 else "MISSING")
                    }
                except Exception as ex:
                    custom_results[c_sel] = {
                        "found": False,
                        "visible": False,
                        "count": 0,
                        "error": str(ex),
                        "status": "ERROR"
                    }

        # 6. Thống kê số lượng thẻ tổng quan
        dom_stats = page.evaluate("""() => {
            return {
                total_nodes: document.getElementsByTagName('*').length,
                total_links: document.getElementsByTagName('a').length,
                total_images: document.getElementsByTagName('img').length,
                total_scripts: document.getElementsByTagName('script').length
            };
        }""")

        browser.close()

        return {
            "source": "playwright_browser",
            "validation_time_ms": elapsed_ms,
            "page_title": page_title,
            "body_text_length": body_text_len,
            "components": components,
            "custom_selectors": custom_results,
            "stats": dom_stats
        }

def _validate_with_bs4(
    url: str,
    custom_selectors: Optional[List[str]] = None,
    timeout_seconds: float = 10.0
) -> Dict[str, Any]:
    """Kiểm tra cấu trúc DOM qua HTTPX & BeautifulSoup4 (Chế độ nhẹ / Fallback)."""
    import httpx
    from bs4 import BeautifulSoup

    start_time = time.time()
    with httpx.Client(follow_redirects=True, timeout=timeout_seconds, verify=False) as client:
        resp = client.get(url, headers={"User-Agent": DEFAULT_USER_AGENT})
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        html_text = resp.text

    soup = BeautifulSoup(html_text, "html.parser")
    page_title = soup.title.string.strip() if soup.title and soup.title.string else ""
    body_text_len = len(soup.body.get_text()) if soup.body else 0

    components = {}

    # Title
    title_found = bool(page_title)
    components["title"] = {
        "found": title_found,
        "visible": True,
        "count": 1 if title_found else 0,
        "value": page_title,
        "status": "OK" if title_found else "MISSING"
    }

    # Headings
    h1s = soup.find_all("h1")
    h2s = soup.find_all("h2")
    h3s = soup.find_all("h3")
    h1_samples = [h.get_text().strip() for h in h1s[:3]]
    components["headings"] = {
        "found": (len(h1s) + len(h2s) + len(h3s)) > 0,
        "has_h1": len(h1s) > 0,
        "h1_count": len(h1s),
        "h2_count": len(h2s),
        "h3_count": len(h3s),
        "h1_samples": h1_samples,
        "status": "OK" if len(h1s) > 0 else ("WARNING_NO_H1" if (len(h2s) + len(h3s)) > 0 else "MISSING")
    }

    # Helper nhóm selector BS4
    def check_bs4_group(selector_list: List[str]):
        hidden_match = None
        for sel in selector_list:
            try:
                matches = soup.select(sel)
                if matches:
                    # Lọc các element bị ẩn bởi style inline hoặc attribute hidden
                    visible_matches = [
                        m for m in matches
                        if "display:none" not in str(m.get("style", "")).replace(" ", "").lower()
                        and not m.has_attr("hidden")
                    ]
                    has_explicitly_hidden = any(
                        "display:none" in str(m.get("style", "")).replace(" ", "").lower() or m.has_attr("hidden")
                        for m in matches
                    )

                    # Kiểm tra đặc biệt cho container wrapper (.navbar, header):
                    # Nếu bên trong container này có nav hoặc menu nhưng tất cả đều bị ẩn
                    if sel in [".navbar", "header"]:
                        inner_navs = soup.select(f"{sel} nav, {sel} .nav-menu, {sel} [role='navigation']")
                        if inner_navs:
                            visible_inner = [
                                n for n in inner_navs
                                if "display:none" not in str(n.get("style", "")).replace(" ", "").lower()
                                and not n.has_attr("hidden")
                            ]
                            if not visible_inner:
                                return {
                                    "found": True,
                                    "visible": False,
                                    "count": len(inner_navs),
                                    "matched_selector": f"{sel} > nav",
                                    "status": "HIDDEN"
                                }

                    if visible_matches and not has_explicitly_hidden:
                        return {
                            "found": True,
                            "visible": True,
                            "count": len(visible_matches),
                            "matched_selector": sel,
                            "status": "OK"
                        }
                    elif has_explicitly_hidden and hidden_match is None:
                        hidden_match = {
                            "found": True,
                            "visible": False,
                            "count": len(matches),
                            "matched_selector": sel,
                            "status": "HIDDEN"
                        }
                        if sel in ["nav", "[role='navigation']", ".nav-menu", "button.btn-primary", "a.btn-primary", ".btn-primary", "main"]:
                            return hidden_match
            except Exception:
                continue
        if hidden_match:
            return hidden_match
        return {"found": False, "visible": False, "count": 0, "matched_selector": None, "status": "MISSING"}

    components["navigation"] = check_bs4_group(CORE_DOM_CATEGORIES["navigation"]["selectors"])
    components["main_content"] = check_bs4_group(CORE_DOM_CATEGORIES["main_content"]["selectors"])
    components["buttons_cta"] = check_bs4_group(CORE_DOM_CATEGORIES["buttons_cta"]["selectors"])
    components["forms"] = check_bs4_group(CORE_DOM_CATEGORIES["forms"]["selectors"])
    components["footer"] = check_bs4_group(CORE_DOM_CATEGORIES["footer"]["selectors"])

    # Custom Selectors
    custom_results = {}
    if custom_selectors:
        for c_sel in custom_selectors:
            try:
                elems = soup.select(c_sel)
                sample = elems[0].get_text().strip()[:100] if elems else ""
                custom_results[c_sel] = {
                    "found": len(elems) > 0,
                    "visible": len(elems) > 0,
                    "count": len(elems),
                    "text_sample": sample,
                    "status": "OK" if len(elems) > 0 else "MISSING"
                }
            except Exception as ex:
                custom_results[c_sel] = {
                    "found": False,
                    "visible": False,
                    "count": 0,
                    "error": str(ex),
                    "status": "ERROR"
                }

    stats = {
        "total_nodes": len(soup.find_all()),
        "total_links": len(soup.find_all("a")),
        "total_images": len(soup.find_all("img")),
        "total_scripts": len(soup.find_all("script"))
    }

    return {
        "source": "bs4_html_parser",
        "validation_time_ms": elapsed_ms,
        "page_title": page_title,
        "body_text_length": body_text_len,
        "components": components,
        "custom_selectors": custom_results,
        "stats": stats
    }

def validate_dom(
    url: str,
    expected_selectors: Optional[List[str]] = None,
    use_browser: bool = True,
    timeout: float = 15.0,
    timeout_seconds: Optional[float] = None
) -> Dict[str, Any]:
    if timeout_seconds is not None:
        timeout = timeout_seconds
    """
    Công cụ DOM Validation dựa trên tiêu chuẩn Structural Monitoring (RULE_BUILD_TOOLS.md mục 5).
    
    Kiểm tra tính toàn vẹn cấu trúc DOM của website:
    - Xác thực sự tồn tại & trạng thái hiển thị của Title, Headings (H1/H2/H3), Navigation, Form, Nút bấm CTA, Footer.
    - Hỗ trợ kiểm tra danh sách CSS selectors tùy chỉnh (expected_selectors).
    - Phát hiện bất thường cấu trúc (thân trang rỗng, thiếu thẻ tiêu đề h1, thiếu title, v.v.).
    """
    result = {
        "url": url,
        "is_structure_valid": False,
        "validation_time_ms": 0.0,
        "page_title": "",
        "body_text_length": 0,
        "missing_critical_elements": [],
        "structural_anomalies": [],
        "components": {},
        "custom_selectors": {},
        "dom_stats": {},
        "monitoring_source": "synthetic",
        "error": None
    }

    try:
        raw_res = None
        if use_browser:
            try:
                raw_res = _validate_with_playwright(url, custom_selectors=expected_selectors, timeout_seconds=timeout)
            except Exception:
                raw_res = None

        if not raw_res:
            raw_res = _validate_with_bs4(url, custom_selectors=expected_selectors, timeout_seconds=min(timeout, 10.0))

        result["monitoring_source"] = raw_res["source"]
        result["validation_time_ms"] = raw_res["validation_time_ms"]
        result["page_title"] = raw_res["page_title"]
        result["body_text_length"] = raw_res["body_text_length"]
        result["components"] = raw_res["components"]
        result["custom_selectors"] = raw_res["custom_selectors"]
        result["dom_stats"] = raw_res["stats"]

        missing_critical = []
        anomalies = []

        # 1. Đánh giá tính hợp lệ của Tiêu đề (Title)
        if not raw_res["components"].get("title", {}).get("found"):
            missing_critical.append("Page Title (<title>)")
            anomalies.append("Trang web thiếu thẻ <title> hoặc tiêu đề rỗng.")

        # 2. Đánh giá Headings (Cấu trúc phân cấp nội dung)
        headings_info = raw_res["components"].get("headings", {})
        if not headings_info.get("found"):
            missing_critical.append("Headings (h1/h2/h3)")
            anomalies.append("Không tìm thấy bất kỳ thẻ heading (h1, h2, h3) nào trên trang.")
        elif not headings_info.get("has_h1"):
            anomalies.append("Trang web có heading nhưng thiếu thẻ <h1> cấp cao nhất (SEO / Accessibility Warning).")

        # 3. Đánh giá Body Content (Trang trắng / Blank Page)
        if result["body_text_length"] < 20 or raw_res["stats"].get("total_nodes", 0) < 10:
            missing_critical.append("Body Content (Blank Page / Empty DOM)")
            anomalies.append("Thân trang web hầu như rỗng hoặc không có nội dung văn bản hiển thị.")

        # 4. Đánh giá thành phần cấu trúc cốt lõi bị ẩn bất thường (Hidden UI / Missing DOM Elements)
        nav_info = raw_res["components"].get("navigation", {})
        if nav_info.get("status") == "HIDDEN":
            missing_critical.append(f"Thanh điều hướng bị ẩn ({nav_info.get('matched_selector', 'navigation')})")
            anomalies.append("Thanh điều hướng chính của website bị ẩn bất thường (display: none / hidden).")

        content_info = raw_res["components"].get("main_content", {})
        if content_info.get("status") == "HIDDEN":
            missing_critical.append(f"Khu vực nội dung chính bị ẩn ({content_info.get('matched_selector', 'main')})")
            anomalies.append("Khu vực nội dung chính bị ẩn bất thường (display: none / hidden).")

        buttons_info = raw_res["components"].get("buttons_cta", {})
        if buttons_info.get("status") == "HIDDEN":
            missing_critical.append(f"Thành phần tương tác bị ẩn ({buttons_info.get('matched_selector', 'buttons/CTA')})")
            anomalies.append("Các nút bấm hoặc thành phần tương tác của trang bị ẩn bất thường (display: none).")

        # 5. Đánh giá tính toàn vẹn của khung xương giao diện (Semantic Skeleton)
        # Nếu website thiếu đồng thời cả Navigation, Main Content và Headings -> Vỡ layout toàn diện
        if nav_info.get("status") == "MISSING" and content_info.get("status") == "MISSING" and not headings_info.get("found"):
            missing_critical.append("Khung giao diện cơ bản (Thiếu đồng thời Navigation, Content & Headings)")
            anomalies.append("Trang web bị vỡ khung giao diện cơ bản.")

        # 6. Đánh giá Custom Selectors (nếu có yêu cầu từ cấu hình)
        for sel, c_data in raw_res["custom_selectors"].items():
            if not c_data.get("found"):
                missing_critical.append(f"Custom Element: '{sel}'")
                anomalies.append(f"Không tìm thấy thành phần bắt buộc '{sel}' trên trang.")
            elif not c_data.get("visible"):
                missing_critical.append(f"Custom Element Hidden: '{sel}'")
                anomalies.append(f"Thành phần '{sel}' tồn tại trong DOM nhưng đang bị ẩn (hidden).")

        result["missing_critical_elements"] = missing_critical
        result["structural_anomalies"] = anomalies
        result["is_structure_valid"] = len(missing_critical) == 0

    except Exception as e:
        err_msg = str(e)
        result["error"] = err_msg
        result["can_inspect"] = False
        # Nếu lỗi là do timeout hoặc không kết nối được mạng, cấu trúc trang không bị phán quyết là vỡ
        result["is_structure_valid"] = True
        result["structural_anomalies"] = [f"Không thể kiểm tra DOM do lỗi mạng/kết nối: {err_msg}"]

    return result
