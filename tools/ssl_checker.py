import ssl
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse
from config import TZ_VN, SSL_TIMEOUT_SECONDS

def _extract_rdn(rdn_tuples) -> dict:
    """Bóc tách Relative Distinguished Names (RDN) thành dictionary key-value."""
    res = {}
    if not rdn_tuples:
        return res
    for item in rdn_tuples:
        for key, value in item:
            res[key] = value
    return res

def check_ssl(url_or_host: str, timeout: float = SSL_TIMEOUT_SECONDS) -> dict:
    """
    Kiểm tra chứng chỉ SSL/TLS dựa trên RFC 5280 (X.509 Certificate Profile) và RFC 8446 (TLS 1.3).
    Hỗ trợ phát hiện self-signed, expired, untrusted CA, hostname mismatch và bóc tách SAN/Issuer.
    """
    raw = url_or_host.strip()
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    hostname = parsed.hostname or url_or_host.strip()
    port = parsed.port or 443

    result = {
        "hostname": hostname,
        "is_valid": False,
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
        "error": None,
        "error_type": None
    }

    # Helper xử lý bóc tách thông tin cert dict
    def populate_cert_info(cert: dict, tls_ver: str = None):
        if tls_ver:
            result["tls_version"] = tls_ver

        not_before_str = cert.get('notBefore')
        not_after_str = cert.get('notAfter')
        if not_before_str and not_after_str:
            not_before = datetime.strptime(not_before_str, '%b %d %H:%M:%S %Y %Z').replace(tzinfo=timezone.utc).astimezone(TZ_VN)
            not_after = datetime.strptime(not_after_str, '%b %d %H:%M:%S %Y %Z').replace(tzinfo=timezone.utc).astimezone(TZ_VN)
            result["not_before"] = not_before.isoformat()
            result["not_after"] = not_after.isoformat()
            
            now = datetime.now(TZ_VN)
            result["days_remaining"] = (not_after - now).days
            if now > not_after or now < not_before:
                result["is_expired"] = True

        # Issuer
        issuer_dict = _extract_rdn(cert.get('issuer', ()))
        result["issuer"] = issuer_dict.get('commonName') or issuer_dict.get('organizationName') or str(cert.get('issuer'))

        # Subject & SANs
        subject_dict = _extract_rdn(cert.get('subject', ()))
        result["subject_common_name"] = subject_dict.get('commonName')

        sans = cert.get('subjectAltName', ())
        result["subject_alternative_names"] = [val for sub_type, val in sans if sub_type == 'DNS']

        # So khớp hostname
        all_valid_names = list(result["subject_alternative_names"])
        if result["subject_common_name"] and result["subject_common_name"] not in all_valid_names:
            all_valid_names.append(result["subject_common_name"])

        matched = False
        for name in all_valid_names:
            if name.lower() == hostname.lower():
                matched = True
                break
            if name.startswith("*.") and hostname.lower().endswith(name[2:].lower()):
                matched = True
                break
        result["hostname_matched"] = matched

        # Kiểm tra tự ký (Self-signed) nếu Subject == Issuer
        if subject_dict and issuer_dict and subject_dict == issuer_dict:
            result["is_self_signed"] = True

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

    # 2. Bước 2: Bắt tay mã hóa SSL/TLS (Presentation/Security Layer L6/L7)
    context = ssl.create_default_context()
    result["can_connect"] = True

    try:
        with sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                populate_cert_info(cert, ssock.version())
                
                # Hợp lệ khi không hết hạn và hostname khớp
                if not result["is_expired"] and result["hostname_matched"]:
                    result["is_valid"] = True
                    result["status"] = "VALID"
                else:
                    result["is_valid"] = False
                    result["status"] = "INVALID"

    except ssl.SSLCertVerificationError as e:
        err_msg = str(e)
        result["error"] = err_msg
        result["error_detail"] = err_msg
        result["is_valid"] = False
        result["status"] = "INVALID"
        
        # Phân loại lỗi chứng chỉ theo RFC 5280
        if "self-signed" in err_msg.lower() or "self signed" in err_msg.lower():
            result["is_self_signed"] = True
            result["error_type"] = "SelfSignedCertificate"
            result["error_title"] = "Self-Signed Certificate"
        elif "expired" in err_msg.lower() or "has expired" in err_msg.lower():
            result["is_expired"] = True
            result["error_type"] = "CertificateExpired"
            result["error_title"] = "Certificate Expired"
        elif "hostname mismatch" in err_msg.lower() or "not valid for" in err_msg.lower():
            result["hostname_matched"] = False
            result["error_type"] = "HostnameMismatch"
            result["error_title"] = "Hostname Mismatch"
        elif "unable to get local issuer certificate" in err_msg.lower() or "authority invalid" in err_msg.lower():
            result["is_untrusted_ca"] = True
            result["error_type"] = "UntrustedCAOrBrokenChain"
            result["error_title"] = "Untrusted CA / Incomplete Certificate Chain"
        else:
            result["error_type"] = "SSLCertVerificationError"
            result["error_title"] = "Certificate Verification Failed"

        # Fallback lấy metadata chứng chỉ ở chế độ unverified để phục vụ phân tích
        try:
            unverified_ctx = ssl._create_unverified_context()
            with socket.create_connection((hostname, port), timeout=timeout) as fallback_sock:
                with unverified_ctx.wrap_socket(fallback_sock, server_hostname=hostname) as fallback_ssock:
                    fallback_cert = fallback_ssock.getpeercert()
                    populate_cert_info(fallback_cert, fallback_ssock.version())
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
            result["error_detail"] = f"Server does not support SSL/TLS on this port (likely HTTP): {err_msg}"
        else:
            result["error_title"] = "SSL/TLS Protocol Error"

    except Exception as e:
        err_msg = str(e)
        result["error"] = err_msg
        result["error_detail"] = err_msg
        result["error_type"] = type(e).__name__
        result["is_valid"] = False
        result["status"] = "ERROR"
        result["error_title"] = type(e).__name__

    return result