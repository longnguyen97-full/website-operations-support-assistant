"""
Technology Stack Fingerprinting & Web Server Detection Tool.
Chịu trách nhiệm nhận diện vân tay công nghệ của website mục tiêu theo chuẩn SRE Reconnaissance:
- Web Server: Nginx, Apache, LiteSpeed, Caddy, Microsoft-IIS, OpenResty, Cloudflare Server.
- CDN / Reverse Proxy: Cloudflare, AWS CloudFront, Fastly, Akamai, Varnish, Sucuri.
- Ngôn ngữ & Runtime: PHP, Node.js, Python, ASP.NET, Java, Ruby.
- CMS & Framework: WordPress, Next.js, Laravel, Drupal, Shopify, React, Vue, jQuery, Bootstrap, Tailwind CSS.
- Security Hardening: Phát hiện việc để lộ phiên bản nhạy cảm qua HTTP Headers.
- SRE Actionable Commands: Đề xuất các lệnh điều tra cứu hộ đặc thù theo stack phát hiện được.
"""

import re
from typing import Dict, Any, Optional, List
import httpx
from config import DEFAULT_USER_AGENT, HTTP_TIMEOUT_SECONDS

def detect_technology_stack(
    url: str,
    http_res: Optional[Dict[str, Any]] = None,
    dom_res: Optional[Dict[str, Any]] = None,
    html_content: Optional[str] = None,
    timeout: float = 6.0
) -> Dict[str, Any]:
    """
    Phân tích và nhận diện hệ sinh thái công nghệ (Technology Stack) của website mục tiêu:
    Kết hợp 2 tầng:
    1. Passive Header & Cookie Fingerprinting (HTTP Headers, Set-Cookie).
    2. Semantic HTML & DOM Pattern Inspection (Meta tags, Asset paths, Scripts, Framework attributes).
    """
    headers: Dict[str, str] = {}
    cookies: List[str] = []

    # 1. Trích xuất headers và cookies từ kết quả http_res nếu đã có
    if http_res:
        raw_headers = http_res.get("headers") or {}
        headers = {str(k).lower(): str(v) for k, v in raw_headers.items() if v is not None}
        cookies = [str(c).lower() for c in (http_res.get("cookies") or [])]

    # 2. Nếu chưa có HTML content nhưng cần phân tích sâu DOM, tải nhanh 1 sample HTML nhẹ
    if not html_content and (not http_res or http_res.get("is_success")):
        try:
            with httpx.Client(timeout=timeout, verify=False, follow_redirects=True) as client:
                r = client.get(url, headers={"User-Agent": DEFAULT_USER_AGENT})
                html_content = r.text[:150000]  # Giới hạn 150KB đầu tiên để đạt tốc độ cao
                # Bổ sung headers và cookies nếu trước đó chưa có
                for k, v in r.headers.items():
                    k_low = k.lower()
                    if k_low not in headers:
                        headers[k_low] = str(v)
                for c in r.cookies.keys():
                    c_low = c.lower()
                    if c_low not in cookies:
                        cookies.append(c_low)
        except Exception:
            html_content = html_content or ""

    html_str = html_content or ""

    detected_components: List[Dict[str, Any]] = []
    security_warnings: List[str] = []
    sre_commands: List[str] = []

    web_server = None
    web_server_ver = None
    cdn_proxies: List[str] = []
    languages: List[str] = []
    lang_ver = None
    frameworks_cms: List[str] = []
    cms_ver = None

    # =========================================================================
    # TẦNG 1: NHẬN DIỆN WEB SERVER
    # =========================================================================
    server_hdr = headers.get("server", "").strip()

    if server_hdr:
        s_low = server_hdr.lower()
        if "cloudflare" in s_low:
            web_server = "Cloudflare Edge Server"
            if "Cloudflare" not in cdn_proxies:
                cdn_proxies.append("Cloudflare")
            detected_components.append({
                "category": "Web Server / CDN",
                "name": "Cloudflare Server",
                "version": None,
                "confidence": "HIGH",
                "source": f"Header 'Server: {server_hdr}'"
            })
        elif "nginx" in s_low or "openresty" in s_low:
            web_server = "OpenResty" if "openresty" in s_low else "Nginx"
            m = re.search(r"nginx/([\d\.]+)", server_hdr, re.IGNORECASE) or re.search(r"openresty/([\d\.]+)", server_hdr, re.IGNORECASE)
            if m:
                web_server_ver = m.group(1)
                security_warnings.append(f"Server để lộ phiên bản Nginx ({web_server_ver}) qua header. Khuyến nghị cấu hình 'server_tokens off;' trong nginx.conf.")
            detected_components.append({
                "category": "Web Server",
                "name": web_server,
                "version": web_server_ver,
                "confidence": "HIGH",
                "source": f"Header 'Server: {server_hdr}'"
            })
            sre_commands.extend([
                "nginx -t  # Kiểm tra tính toàn vẹn cú pháp cấu hình Nginx",
                "systemctl status nginx  # Kiểm tra trạng thái tiến trình Nginx master/worker",
                "tail -n 50 /var/log/nginx/error.log  # Xem log lỗi gần nhất"
            ])
        elif "apache" in s_low:
            web_server = "Apache HTTP Server"
            m = re.search(r"apache/([\d\.]+)", server_hdr, re.IGNORECASE)
            if m:
                web_server_ver = m.group(1)
                security_warnings.append(f"Server để lộ phiên bản Apache ({web_server_ver}). Khuyến nghị cấu hình 'ServerTokens Prod' và 'ServerSignature Off'.")
            detected_components.append({
                "category": "Web Server",
                "name": "Apache",
                "version": web_server_ver,
                "confidence": "HIGH",
                "source": f"Header 'Server: {server_hdr}'"
            })
            sre_commands.extend([
                "apache2ctl configtest  # (Hoặc httpd -t) Kiểm tra file cấu hình và .htaccess",
                "systemctl status apache2  # (Hoặc systemctl status httpd)",
                "tail -n 50 /var/log/apache2/error.log"
            ])
        elif "litespeed" in s_low or "lite speed" in s_low:
            web_server = "LiteSpeed Web Server"
            detected_components.append({
                "category": "Web Server",
                "name": "LiteSpeed",
                "version": None,
                "confidence": "HIGH",
                "source": f"Header 'Server: {server_hdr}'"
            })
            sre_commands.append("systemctl status lsws  # Kiểm tra tiến trình LiteSpeed")
        elif "microsoft-iis" in s_low or "iis" in s_low:
            web_server = "Microsoft IIS"
            m = re.search(r"iis/([\d\.]+)", server_hdr, re.IGNORECASE)
            if m:
                web_server_ver = m.group(1)
            detected_components.append({
                "category": "Web Server",
                "name": "Microsoft-IIS",
                "version": web_server_ver,
                "confidence": "HIGH",
                "source": f"Header 'Server: {server_hdr}'"
            })
            sre_commands.append("iisreset /status  # Kiểm tra dịch vụ Windows IIS W3SVC")
        elif "caddy" in s_low:
            web_server = "Caddy"
            detected_components.append({
                "category": "Web Server",
                "name": "Caddy",
                "version": None,
                "confidence": "HIGH",
                "source": f"Header 'Server: {server_hdr}'"
            })
            sre_commands.append("systemctl status caddy  # Kiểm tra dịch vụ Caddy Web Server")
        elif "gunicorn" in s_low or "uvicorn" in s_low:
            web_server = "Gunicorn / Uvicorn (Python)"
            detected_components.append({
                "category": "Web Server",
                "name": web_server,
                "version": None,
                "confidence": "HIGH",
                "source": f"Header 'Server: {server_hdr}'"
            })
        else:
            web_server = server_hdr

    # Kiểm tra thêm header x-litespeed-cache
    if "x-litespeed-cache" in headers and "LiteSpeed" not in (web_server or ""):
        web_server = "LiteSpeed"
        detected_components.append({
            "category": "Web Server",
            "name": "LiteSpeed",
            "version": None,
            "confidence": "HIGH",
            "source": "Header 'X-LiteSpeed-Cache'"
        })

    # =========================================================================
    # TẦNG 2: NHẬN DIỆN CDN / REVERSE PROXY
    # =========================================================================
    if "cf-ray" in headers or "cf-cache-status" in headers or "cloudflare" in server_hdr.lower():
        if "Cloudflare" not in cdn_proxies:
            cdn_proxies.append("Cloudflare")
            detected_components.append({
                "category": "CDN / Reverse Proxy",
                "name": "Cloudflare CDN & WAF",
                "version": None,
                "confidence": "HIGH",
                "source": f"Header 'CF-Ray: {headers.get('cf-ray', 'Active')}'"
            })
            sre_commands.append("Kiểm tra Cloudflare Dashboard -> SSL/TLS Encryption Mode (Full/Strict) & Development Mode")

    if "x-amz-cf-id" in headers or "x-amz-cf-pop" in headers or "cloudfront" in headers.get("via", "").lower():
        if "AWS CloudFront" not in cdn_proxies:
            cdn_proxies.append("AWS CloudFront")
            detected_components.append({
                "category": "CDN / Reverse Proxy",
                "name": "AWS CloudFront",
                "version": None,
                "confidence": "HIGH",
                "source": "Header 'X-Amz-Cf-Id'"
            })

    if "x-fastly-request-id" in headers or "fastly" in headers.get("via", "").lower():
        if "Fastly" not in cdn_proxies:
            cdn_proxies.append("Fastly")
            detected_components.append({
                "category": "CDN / Reverse Proxy",
                "name": "Fastly CDN",
                "version": None,
                "confidence": "HIGH",
                "source": "Header 'X-Fastly-Request-Id'"
            })

    if "x-varnish" in headers or "varnish" in headers.get("via", "").lower():
        if "Varnish" not in cdn_proxies:
            cdn_proxies.append("Varnish Cache")
            detected_components.append({
                "category": "Reverse Proxy / Cache",
                "name": "Varnish Cache",
                "version": None,
                "confidence": "HIGH",
                "source": "Header 'X-Varnish' hoặc 'Via'"
            })
            sre_commands.append("varnishlog -d | varnishstat  # Kiểm tra hit rate của Varnish")

    if "x-sucuri-id" in headers or "sucuri" in server_hdr.lower():
        if "Sucuri" not in cdn_proxies:
            cdn_proxies.append("Sucuri WAF")
            detected_components.append({
                "category": "WAF / Proxy",
                "name": "Sucuri CloudProxy WAF",
                "version": None,
                "confidence": "HIGH",
                "source": "Header 'X-Sucuri-ID'"
            })

    # =========================================================================
    # TẦNG 3: NHẬN DIỆN NGÔN NGỮ & RUNTIME
    # =========================================================================
    powered_by = headers.get("x-powered-by", "").strip()
    if powered_by:
        p_low = powered_by.lower()
        if "php" in p_low:
            languages.append("PHP")
            m = re.search(r"php/([\d\.]+)", powered_by, re.IGNORECASE)
            if m:
                lang_ver = m.group(1)
                security_warnings.append(f"Header để lộ phiên bản PHP ({lang_ver}). Khuyến nghị thiết lập 'expose_php = Off' trong php.ini.")
            detected_components.append({
                "category": "Programming Language",
                "name": "PHP",
                "version": lang_ver,
                "confidence": "HIGH",
                "source": f"Header 'X-Powered-By: {powered_by}'"
            })
            sre_commands.extend([
                "systemctl status php*-fpm  # Kiểm tra trạng thái PHP FastCGI Process Manager",
                "tail -n 50 /var/log/php*-fpm.log  # Xem log lỗi crash/exhausted workers của PHP"
            ])
        elif "express" in p_low:
            languages.append("Node.js")
            frameworks_cms.append("Express.js")
            detected_components.append({
                "category": "Framework / Runtime",
                "name": "Node.js (Express)",
                "version": None,
                "confidence": "HIGH",
                "source": f"Header 'X-Powered-By: {powered_by}'"
            })
            sre_commands.append("pm2 status || pm2 logs --lines 50  # Kiểm tra tiến trình Node.js")
        elif "asp.net" in p_low:
            languages.append(".NET (C#)")
            frameworks_cms.append("ASP.NET")
            asp_ver = headers.get("x-aspnet-version")
            detected_components.append({
                "category": "Framework / Runtime",
                "name": "ASP.NET",
                "version": asp_ver,
                "confidence": "HIGH",
                "source": f"Header 'X-Powered-By: {powered_by}'"
            })
        elif "next.js" in p_low:
            languages.append("Node.js")
            frameworks_cms.append("Next.js")
            detected_components.append({
                "category": "Framework",
                "name": "Next.js",
                "version": None,
                "confidence": "HIGH",
                "source": f"Header 'X-Powered-By: {powered_by}'"
            })

    # Nhận diện qua Cookies
    for c in cookies:
        if "phpsessid" in c and "PHP" not in languages:
            languages.append("PHP")
            detected_components.append({
                "category": "Programming Language",
                "name": "PHP",
                "version": None,
                "confidence": "HIGH",
                "source": "Cookie 'PHPSESSID'"
            })
        elif ("laravel_session" in c or "xsrf-token" in c) and "Laravel" not in frameworks_cms:
            if "PHP" not in languages:
                languages.append("PHP")
            frameworks_cms.append("Laravel")
            detected_components.append({
                "category": "Framework",
                "name": "Laravel",
                "version": None,
                "confidence": "HIGH",
                "source": "Cookie 'laravel_session'"
            })
            sre_commands.append("php artisan optimize:clear  # Dọn cache config/route của Laravel")
        elif "connect.sid" in c and "Node.js" not in languages:
            languages.append("Node.js")
            detected_components.append({
                "category": "Runtime",
                "name": "Node.js (Express Session)",
                "version": None,
                "confidence": "HIGH",
                "source": "Cookie 'connect.sid'"
            })
        elif ("csrftoken" in c or "sessionid" in c) and "Python (Django)" not in languages:
            # Gợi ý Django
            if any(kw in html_str for kw in ["csrfmiddlewaretoken", "django"]):
                languages.append("Python (Django)")
                frameworks_cms.append("Django")
                detected_components.append({
                    "category": "Framework",
                    "name": "Django",
                    "version": None,
                    "confidence": "HIGH",
                    "source": "Cookie 'csrftoken' & Form Input"
                })

    # =========================================================================
    # TẦNG 4: NHẬN DIỆN CMS & FRONTEND FRAMEWORKS (HTML / DOM ANALYSIS)
    # =========================================================================
    x_gen = headers.get("x-generator", "")
    meta_gen_match = re.search(r'<meta[^>]*name=["\']generator["\'][^>]*content=["\']([^"\']+)["\']', html_str, re.IGNORECASE)
    generator_val = meta_gen_match.group(1).strip() if meta_gen_match else x_gen

    # 1. Nhận diện WordPress
    is_wordpress = False
    if "wordpress" in generator_val.lower():
        is_wordpress = True
        m_wp = re.search(r"wordpress\s*([\d\.]+)", generator_val, re.IGNORECASE)
        if m_wp:
            cms_ver = m_wp.group(1)
    elif "/wp-content/" in html_str or "/wp-includes/" in html_str or "wp-json" in html_str:
        is_wordpress = True
    elif any("wordpress_" in c or "wp-settings-" in c for c in cookies):
        is_wordpress = True

    if is_wordpress and "WordPress" not in frameworks_cms:
        frameworks_cms.append("WordPress")
        if "PHP" not in languages:
            languages.append("PHP")
        detected_components.append({
            "category": "CMS",
            "name": "WordPress",
            "version": cms_ver,
            "confidence": "CONFIRMED",
            "source": f"Meta Generator: '{generator_val}'" if cms_ver else "Asset Paths (/wp-content/)"
        })
        sre_commands.extend([
            "wp core check-update  # (WP-CLI) Kiểm tra phiên bản lõi WordPress",
            "wp plugin list --status=active  # Xem danh sách plugin đang kích hoạt",
            "Kiểm tra wp-config.php -> WP_MEMORY_LIMIT, DB_HOST, WP_DEBUG"
        ])

    # 2. Nhận diện Next.js
    if "/_next/static/" in html_str or 'id="__NEXT_DATA__"' in html_str:
        if "Next.js" not in frameworks_cms:
            frameworks_cms.append("Next.js")
            if "Node.js" not in languages:
                languages.append("Node.js")
            detected_components.append({
                "category": "Framework",
                "name": "Next.js",
                "version": None,
                "confidence": "CONFIRMED",
                "source": "HTML Marker '/_next/static/' hoặc '__NEXT_DATA__'"
            })
            sre_commands.append("pm2 reload nextjs-app || docker restart next-frontend")

    # 3. Nhận diện React
    if "data-reactroot" in html_str or "react.production.min.js" in html_str or "_react" in html_str:
        if "React" not in frameworks_cms:
            frameworks_cms.append("React")
            detected_components.append({
                "category": "Frontend UI Library",
                "name": "React",
                "version": None,
                "confidence": "HIGH",
                "source": "HTML attribute 'data-reactroot' hoặc React bundle"
            })

    # 4. Nhận diện Vue.js
    if "data-v-" in html_str or "vue.min.js" in html_str:
        if "Vue.js" not in frameworks_cms:
            frameworks_cms.append("Vue.js")
            detected_components.append({
                "category": "Frontend UI Library",
                "name": "Vue.js",
                "version": None,
                "confidence": "HIGH",
                "source": "Attribute 'data-v-' (Scoped CSS) hoặc Vue runtime"
            })

    # 5. Nhận diện Drupal
    if "drupal" in generator_val.lower() or "/sites/default/files" in html_str or "x-drupal-cache" in headers:
        if "Drupal" not in frameworks_cms:
            frameworks_cms.append("Drupal")
            if "PHP" not in languages:
                languages.append("PHP")
            detected_components.append({
                "category": "CMS",
                "name": "Drupal",
                "version": None,
                "confidence": "HIGH",
                "source": "Drupal Signatures"
            })
            sre_commands.append("drush cr  # Xóa cache Drupal")

    # 6. Nhận diện Shopify
    if "shopify" in generator_val.lower() or "cdn.shopify.com" in html_str:
        if "Shopify" not in frameworks_cms:
            frameworks_cms.append("Shopify")
            detected_components.append({
                "category": "E-Commerce Platform",
                "name": "Shopify (SaaS)",
                "version": None,
                "confidence": "CONFIRMED",
                "source": "Shopify CDN Assets"
            })

    # 7. Nhận diện CSS Frameworks (Tailwind CSS, Bootstrap)
    if any(cls in html_str for cls in ["flex items-center", "text-sm font-medium", "grid grid-cols-"]):
        if "Tailwind CSS" not in frameworks_cms:
            frameworks_cms.append("Tailwind CSS")
            detected_components.append({
                "category": "CSS Framework",
                "name": "Tailwind CSS",
                "version": None,
                "confidence": "MEDIUM",
                "source": "Utility-first CSS Classes"
            })

    if "bootstrap.min.css" in html_str or "bootstrap.css" in html_str:
        if "Bootstrap" not in frameworks_cms:
            frameworks_cms.append("Bootstrap")
            detected_components.append({
                "category": "CSS Framework",
                "name": "Bootstrap",
                "version": None,
                "confidence": "HIGH",
                "source": "Bootstrap CSS Link"
            })

    # 8. Nhận diện jQuery
    if "jquery.min.js" in html_str or "jquery-" in html_str:
        if "jQuery" not in frameworks_cms:
            frameworks_cms.append("jQuery")
            detected_components.append({
                "category": "JavaScript Library",
                "name": "jQuery",
                "version": None,
                "confidence": "HIGH",
                "source": "jQuery Script Tag"
            })

    # Fallback cho Web Server nếu chưa xác định được nhưng có gợi ý
    if not web_server:
        if "Cloudflare" in cdn_proxies:
            web_server = "Cloudflare Proxy (Origin Server Hidden)"
        else:
            web_server = "Ẩn danh (Custom Gateway / Header Strip)"

    # Tạo tóm tắt ngắn cho UI Badge (One-line Summary)
    summary_parts = []
    if web_server and "Ẩn danh" not in web_server:
        summary_parts.append(f"{web_server}" + (f" {web_server_ver}" if web_server_ver else ""))
    if cdn_proxies:
        summary_parts.append(f"CDN: {', '.join(cdn_proxies[:2])}")
    if frameworks_cms:
        # Ưu tiên hiển thị CMS chính
        main_cms = [f for f in frameworks_cms if f in ["WordPress", "Next.js", "Laravel", "Drupal", "Shopify"]]
        if main_cms:
            summary_parts.append(f"CMS/App: {main_cms[0]}" + (f" {cms_ver}" if cms_ver else ""))
    if languages:
        summary_parts.append(f"Lang: {languages[0]}" + (f" {lang_ver}" if lang_ver else ""))

    one_line_summary = " | ".join(summary_parts) if summary_parts else "Chưa nhận diện được công nghệ đặc thù"

    return {
        "is_detected": len(detected_components) > 0,
        "one_line_summary": one_line_summary,
        "web_server": web_server,
        "web_server_version": web_server_ver,
        "cdn_proxies": cdn_proxies,
        "programming_languages": languages,
        "language_version": lang_ver,
        "frameworks_cms": frameworks_cms,
        "cms_version": cms_ver,
        "detected_components": detected_components,
        "security_warnings": security_warnings,
        "recommended_sre_commands": sre_commands,
        "raw_evidence": {
            "server_header": server_hdr or None,
            "powered_by": powered_by or None,
            "generator": generator_val or None,
            "cookies": cookies[:5]
        }
    }
