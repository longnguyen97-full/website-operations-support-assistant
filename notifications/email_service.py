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
    timestamp: str
) -> str:
    """Tạo nội dung email HTML cảnh báo sự cố chi tiết và trực quan."""
    if overall_status == "CRITICAL":
        header_bg = "#dc2626"
        status_title = "🚨 CẢNH BÁO SỰ CỐ NGHIÊM TRỌNG (CRITICAL)"
        badge_color = "#dc2626"
    elif overall_status == "WARNING":
        header_bg = "#f59e0b"
        status_title = "⚠️ CẢNH BÁO TIỀM ẨN RỦI RO (WARNING)"
        badge_color = "#f59e0b"
    else:
        header_bg = "#10b981"
        status_title = "✅ HỆ THỐNG ĐÃ PHỤC HỒI (RECOVERY)"
        badge_color = "#10b981"

    # Trích xuất tóm tắt các lỗi
    issues = []
    if not http_res.get("is_expected_status"):
        if http_res.get("error"):
            issues.append(f"<b>HTTP Error:</b> {http_res.get('error')}")
        else:
            issues.append(f"<b>HTTP Status Mismatch:</b> Trả về <code>{http_res.get('status_code')}</code> (Kỳ vọng: <code>{http_res.get('expected_status')}</code>)")
            
    if not dns_res.get("resolved"):
        issues.append(f"<b>DNS Resolution Failed:</b> {dns_res.get('error')}")
    elif dns_res.get("changes_detected") and not dns_res.get("is_load_balancing_suspected"):
        issues.append("<b>DNS Drift:</b> Phát hiện thay đổi bản ghi IP ngoài dự kiến so với Baseline.")

    if not ssl_res.get("is_valid"):
        issues.append(f"<b>SSL/TLS Invalid:</b> {ssl_res.get('error') or 'Chứng chỉ không hợp lệ / Hết hạn'}")
    elif ssl_res.get("days_remaining", 0) <= SSL_EXPIRY_WARNING_DAYS:
        issues.append(f"<b>SSL Expiring Soon:</b> Chứng chỉ số chỉ còn lại <b>{ssl_res.get('days_remaining')} ngày</b> hiệu lực (ngưỡng cảnh báo: $\\le$ {SSL_EXPIRY_WARNING_DAYS} ngày).")

    issues_html = "".join([f"<li style='margin-bottom: 6px;'>{issue}</li>" for issue in issues]) if issues else "<li>Không ghi nhận bất thường.</li>"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; }}
            .container {{ background: #ffffff; max-width: 650px; margin: 0 auto; border-radius: 8px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
            .header {{ background: {header_bg}; color: #ffffff; padding: 20px; text-align: center; }}
            .content {{ padding: 25px; color: #1e293b; }}
            .metric-box {{ display: inline-block; width: 30%; background: #f1f5f9; padding: 10px; border-radius: 6px; text-align: center; margin-right: 2%; box-sizing: border-box; }}
            .issues-box {{ background: #fef2f2; border-left: 4px solid {badge_color}; padding: 15px; margin: 20px 0; border-radius: 4px; }}
            .table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 14px; }}
            .table td {{ padding: 8px 12px; border-bottom: 1px solid #f1f5f9; }}
            .footer {{ background: #f8fafc; padding: 15px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="margin: 0;">{status_title}</h2>
                <p style="margin: 5px 0 0 0; opacity: 0.95;">Website: <b>{site_name}</b></p>
            </div>
            <div class="content">
                <p>Hệ thống giám sát phát hiện thay đổi trạng thái hoạt động tại website <b>{site_name}</b> (<code>{site_url}</code>):</p>
                
                <div class="issues-box">
                    <h4 style="margin: 0 0 10px 0; color: #991b1b;">🔍 Chi tiết các điểm cần chú ý:</h4>
                    <ul style="margin: 0; padding-left: 20px;">
                        {issues_html}
                    </ul>
                </div>

                <h4 style="margin-top: 20px; margin-bottom: 10px;">📊 Tóm tắt chỉ số Probes (RFC Standards):</h4>
                <table class="table">
                    <tr><td><strong>Thời điểm quét:</strong></td><td>{timestamp.replace('T', ' ')[:19]} (UTC+7)</td></tr>
                    <tr><td><strong>HTTP Status (RFC 9110):</strong></td><td><code>{http_res.get('status_code')} ({http_res.get('status_category', 'N/A')})</code> - {http_res.get('response_time_ms')} ms</td></tr>
                    <tr><td><strong>DNS Resolution (RFC 1035):</strong></td><td>{'✅ Phân giải thành công' if dns_res.get('resolved') else '❌ Lỗi phân giải'} ({dns_res.get('resolution_time_ms')} ms)</td></tr>
                    <tr><td><strong>SSL/TLS (RFC 5280):</strong></td><td>{'✅ Hợp lệ' if ssl_res.get('is_valid') else '❌ Không hợp lệ'} | Còn lại: <b>{ssl_res.get('days_remaining', 0)} ngày</b> ({ssl_res.get('tls_version') or 'N/A'})</td></tr>
                </table>

                <p style="margin-top: 25px; font-size: 13px; color: #64748b;">Vui lòng truy cập <a href="http://localhost:8501">Dashboard Quản trị</a> để theo dõi chi tiết và đưa ra phương án xử lý kịp thời.</p>
            </div>
            <div class="footer">
                Thông báo tự động từ Agentic AI Website Operations Support Assistant
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
    ssl_res: dict
):
    """Kiểm tra điều kiện cấu hình và gửi email cảnh báo có áp dụng cơ chế Cooldown."""
    settings = get_email_settings()
    if not settings.get("is_enabled"):
        return

    recipients = parse_recipients(settings.get("recipient_emails", ""))
    if not recipients:
        return

    site_id = site["id"]
    site_name = site["name"]
    site_url = site["url"]
    now = datetime.now(TZ_VN)
    cooldown_delta = timedelta(minutes=int(settings.get("cooldown_minutes", DEFAULT_COOLDOWN_MINUTES)))

    # Kiểm tra loại cảnh báo được phép gửi
    if overall_status == "CRITICAL" and not settings.get("notify_on_critical", True):
        return
    if overall_status == "WARNING" and not settings.get("notify_on_warning", True):
        return

    # Lấy thông tin lần alert trước
    site_alert_state = _alert_tracker.get(site_id, {})
    last_alert_time = site_alert_state.get("last_alert_time")
    last_status = site_alert_state.get("last_status")

    # Trường hợp phục hồi (Recovery): chuyển từ CRITICAL/WARNING về HEALTHY
    if overall_status == "HEALTHY":
        if last_status in ["CRITICAL", "WARNING"] and settings.get("notify_on_recovery", True):
            subject = f"✅ [Phục hồi] Website '{site_name}' đã hoạt động bình thường trở lại"
            html = build_incident_alert_html(site_name, site_url, "HEALTHY", http_res, dns_res, ssl_res, now.isoformat())
            send_email(recipients, subject, html, settings=settings)
            _alert_tracker[site_id] = {"last_alert_time": now, "last_status": "HEALTHY"}
        return

    # Trường hợp có sự cố (CRITICAL hoặc WARNING): Kiểm tra Cooldown
    if last_alert_time and (now - last_alert_time) < cooldown_delta and last_status == overall_status:
        # Đang trong thời gian Cooldown và trạng thái không đổi -> Bỏ qua để tránh spam
        return

    # Gửi Alert Email
    emoji = "🚨" if overall_status == "CRITICAL" else "⚠️"
    subject = f"{emoji} [{overall_status}] Cảnh báo sự cố Website '{site_name}'"
    html = build_incident_alert_html(site_name, site_url, overall_status, http_res, dns_res, ssl_res, now.isoformat())
    
    success, msg = send_email(recipients, subject, html, settings=settings)
    if success:
        _alert_tracker[site_id] = {"last_alert_time": now, "last_status": overall_status}

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

        row = f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">
                <b>{site['name']}</b><br>
                <small style="color: #64748b;">{site['url']}</small>
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
            incident_rows.append(f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #fee2e2;">{t_str}</td>
                <td style="padding: 8px; border-bottom: 1px solid #fee2e2;"><b>{inc['website_name']}</b></td>
                <td style="padding: 8px; border-bottom: 1px solid #fee2e2;">{badge}</td>
                <td style="padding: 8px; border-bottom: 1px solid #fee2e2;">HTTP: {inc['http_code'] or 'Lỗi'} | DNS: {'OK' if inc['dns_resolved'] else 'Lỗi'} | SSL: {'OK' if inc['ssl_valid'] else 'Lỗi'}</td>
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
