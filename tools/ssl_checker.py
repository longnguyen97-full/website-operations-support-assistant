import ssl
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional

from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
from config import TZ_VN, SSL_TIMEOUT_SECONDS

def check_ssl(url_or_host: str, timeout: float = SSL_TIMEOUT_SECONDS) -> Dict[str, Any]:
    """
    Kiểm tra chứng chỉ SSL/TLS dựa trên RFC 5280 (X.509 Certificate Profile) và RFC 8446 (TLS 1.3).
    Hỗ trợ phát hiện self-signed, expired, untrusted CA, hostname mismatch và bóc tách SAN/Issuer
    bằng thư viện cryptography chuẩn xác.
    """
    raw = url_or_host.strip()
    is_http_only = raw.startswith("http://") and not raw.startswith("https://")
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    hostname = parsed.hostname or url_or_host.strip()
    port = parsed.port or 443

    result: Dict[str, Any] = {
        "hostname": hostname,
        "is_http_only": is_http_only,
        "is_valid": False,
        "status": "UNKNOWN",
        "not_before": None,
        "not_after": None,
        "days_remaining": 0,
        "issuer": None,
        "subject_common_name": None,
        "subject_alternative_names": [],
        "hostname_matched": False,
        "tls_version": None,
        "is_self_signed": False,
        "is_expired": False,
        "is_untrusted_ca": False,
        "can_connect": False,
        "error": None,
        "error_title": None,
        "error_detail": None,
        "error_type": None
    }

    # 1. Bước 1: Thiết lập kết nối TCP Socket (Transport Layer L4)
    try:
        sock = socket.create_connection((hostname, port), timeout=timeout)
    except Exception as e:
        err_msg = str(e)
        result["can_connect"] = False
        result["is_valid"] = False
        result["status"] = "UNREACHABLE"
        result["error"] = err_msg
        result["error_detail"] = err_msg
        result["error_type"] = type(e).__name__

        if "10061" in err_msg or "actively refused" in err_msg.lower() or "connection refused" in err_msg.lower():
            result["error_title"] = "Connection Refused (TCP Layer)"
        elif "11001" in err_msg or "getaddrinfo" in err_msg.lower() or "gaierror" in type(e).__name__.lower():
            result["error_title"] = "Host Not Found (DNS Failure)"
        elif "timeout" in err_msg.lower() or isinstance(e, TimeoutError):
            result["error_title"] = f"SSL Connection Timeout (>{timeout}s)"
        else:
            result["error_title"] = f"TCP Connection Failed ({type(e).__name__})"
        return result

    result["can_connect"] = True

    # 2. Bước 2: Bắt tay mã hóa TLS & Trích xuất chứng chỉ X.509
    der_cert = None
    tls_version = None
    is_ca_verified = True

    # Thử bắt tay TLS có kiểm tra CA chuẩn
    try:
        default_ctx = ssl.create_default_context()
        with sock:
            with default_ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                der_cert = ssock.getpeercert(binary_form=True)
                tls_version = ssock.version()
    except ssl.SSLCertVerificationError as e:
        is_ca_verified = False
        err_str = str(e)
        result["error_detail"] = err_str
        # Fallback lấy chứng chỉ DER bằng unverified context để phân tích sâu metadata
        try:
            unverified_ctx = ssl._create_unverified_context()
            with socket.create_connection((hostname, port), timeout=timeout) as fb_sock:
                with unverified_ctx.wrap_socket(fb_sock, server_hostname=hostname) as fb_ssock:
                    der_cert = fb_ssock.getpeercert(binary_form=True)
                    tls_version = fb_ssock.version()
        except Exception:
            pass
    except ssl.SSLError as e:
        err_msg = str(e)
        result["error"] = err_msg
        result["error_detail"] = err_msg
        result["error_type"] = "SSLError"
        result["is_valid"] = False
        result["status"] = "HANDSHAKE_ERROR"
        if "WRONG_VERSION_NUMBER" in err_msg:
            result["error_title"] = "SSL Protocol / Port Mismatch (Non-HTTPS port)"
            result["error_detail"] = f"Server does not support SSL/TLS on this port (likely plain HTTP): {err_msg}"
        else:
            result["error_title"] = "SSL/TLS Protocol Error"
        return result
    except Exception as e:
        result["error"] = str(e)
        result["error_detail"] = str(e)
        result["error_title"] = "SSL Connection Error"
        result["error_type"] = type(e).__name__
        result["is_valid"] = False
        result["status"] = "ERROR"
        return result

    if not der_cert:
        result["error"] = "Không thể lấy chứng chỉ SSL từ máy chủ."
        result["error_title"] = "Certificate Missing"
        result["error_type"] = "CertificateMissing"
        result["is_valid"] = False
        result["status"] = "INVALID"
        return result

    # 3. Bước 3: Phân tích cú pháp X.509 qua cryptography
    try:
        cert = x509.load_der_x509_certificate(der_cert)
        result["tls_version"] = tls_version

        # Trích xuất Thời hạn hiệu lực
        try:
            not_before_utc = cert.not_valid_before_utc
            not_after_utc = cert.not_valid_after_utc
        except AttributeError:
            # Tương thích phiên bản cryptography cũ hơn
            not_before_utc = cert.not_valid_before.replace(tzinfo=timezone.utc)
            not_after_utc = cert.not_valid_after.replace(tzinfo=timezone.utc)

        not_before_vn = not_before_utc.astimezone(TZ_VN)
        not_after_vn = not_after_utc.astimezone(TZ_VN)
        result["not_before"] = not_before_vn.isoformat()
        result["not_after"] = not_after_vn.isoformat()

        now_utc = datetime.now(timezone.utc)
        days_remaining = (not_after_utc - now_utc).days
        result["days_remaining"] = days_remaining

        if now_utc > not_after_utc or now_utc < not_before_utc:
            result["is_expired"] = True

        # Trích xuất Subject CN & Org
        subject_cns = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        result["subject_common_name"] = subject_cns[0].value if subject_cns else None

        # Trích xuất Issuer
        issuer_cns = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
        issuer_orgs = cert.issuer.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)
        result["issuer"] = (
            issuer_cns[0].value if issuer_cns
            else (issuer_orgs[0].value if issuer_orgs else str(cert.issuer))
        )

        # Kiểm tra Tự ký (Self-signed: Subject == Issuer)
        if cert.subject == cert.issuer:
            result["is_self_signed"] = True

        # Trích xuất Subject Alternative Names (SANs)
        sans_list = []
        try:
            san_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
            sans_list = san_ext.value.get_values_for_type(x509.DNSName)
        except Exception:
            pass
        result["subject_alternative_names"] = sans_list

        # So khớp Hostname (RFC 6125)
        all_valid_names = list(sans_list)
        if result["subject_common_name"] and result["subject_common_name"] not in all_valid_names:
            all_valid_names.append(result["subject_common_name"])

        matched = False
        for name in all_valid_names:
            if name.lower() == hostname.lower():
                matched = True
                break
            if name.startswith("*.") and hostname.lower().endswith(name[2:].lower()):
                # Ví dụ *.test khớp site-001.test
                matched = True
                break
        result["hostname_matched"] = matched

        # 4. Bước 4: Đánh giá & Phân loại sự cố SSL
        is_synthetic_lab = hostname.endswith(".test") or hostname.endswith(".local") or hostname == "localhost"

        if result["is_expired"]:
            result["is_valid"] = False
            result["status"] = "INVALID"
            result["error_type"] = "CertificateExpired"
            result["error_title"] = "Certificate Expired"
            result["error"] = f"Chứng chỉ SSL đã hết hạn vào {not_after_vn.strftime('%d/%m/%Y %H:%M:%S')}."
            result["error_detail"] = result["error"]

        elif not result["hostname_matched"]:
            result["is_valid"] = False
            result["status"] = "INVALID"
            result["error_type"] = "HostnameMismatch"
            result["error_title"] = "Hostname Mismatch"
            san_str = ", ".join(all_valid_names) if all_valid_names else "None"
            result["error"] = f"Tên miền '{hostname}' không khớp với chứng chỉ máy chủ (SAN/CN: {san_str})."
            result["error_detail"] = result["error"]

        elif result["is_self_signed"] and not is_synthetic_lab:
            result["is_valid"] = False
            result["status"] = "INVALID"
            result["error_type"] = "SelfSignedCertificate"
            result["error_title"] = "Self-Signed Certificate"
            result["error"] = "Chứng chỉ SSL là tự ký và không thuộc tổ chức CA được tin cậy."
            result["error_detail"] = result["error"]

        elif not is_ca_verified and not is_synthetic_lab:
            result["is_valid"] = False
            result["status"] = "INVALID"
            result["is_untrusted_ca"] = True
            result["error_type"] = "UntrustedCAOrBrokenChain"
            result["error_title"] = "Untrusted CA / Incomplete Certificate Chain"
            result["error"] = "Tổ chức cấp phát chứng chỉ không được tin cậy hoặc chuỗi CA bị gián đoạn."
            result["error_detail"] = result["error"]

        else:
            # Chứng chỉ hoàn toàn hợp lệ
            result["is_valid"] = True
            result["status"] = "VALID"
            result["error"] = None
            result["error_title"] = None
            result["error_detail"] = None
            result["error_type"] = None

    except Exception as e:
        result["error"] = f"Lỗi phân tích cú pháp chứng chỉ: {e}"
        result["error_title"] = "Certificate Parse Error"
        result["error_type"] = type(e).__name__
        result["is_valid"] = False
        result["status"] = "ERROR"

    return result