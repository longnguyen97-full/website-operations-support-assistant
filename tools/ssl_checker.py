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

    # 1. Thử xác thực chuẩn với Root CAs hệ thống
    context = ssl.create_default_context()

    try:
        with socket.create_connection((hostname, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                populate_cert_info(cert, ssock.version())
                
                # Hợp lệ khi không hết hạn và hostname khớp
                if not result["is_expired"] and result["hostname_matched"]:
                    result["is_valid"] = True
                else:
                    result["is_valid"] = False

    except ssl.SSLCertVerificationError as e:
        err_msg = str(e)
        result["error"] = err_msg
        result["is_valid"] = False
        
        # Phân loại lỗi chứng chỉ theo RFC 5280
        if "self-signed" in err_msg.lower() or "self signed" in err_msg.lower():
            result["is_self_signed"] = True
            result["error_type"] = "SelfSignedCertificate"
        elif "expired" in err_msg.lower() or "has expired" in err_msg.lower():
            result["is_expired"] = True
            result["error_type"] = "CertificateExpired"
        elif "hostname mismatch" in err_msg.lower() or "not valid for" in err_msg.lower():
            result["hostname_matched"] = False
            result["error_type"] = "HostnameMismatch"
        elif "unable to get local issuer certificate" in err_msg.lower() or "authority invalid" in err_msg.lower():
            result["is_untrusted_ca"] = True
            result["error_type"] = "UntrustedCAOrBrokenChain"
        else:
            result["error_type"] = "SSLCertVerificationError"

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
        result["error"] = str(e)
        result["error_type"] = "SSLError"
        result["is_valid"] = False

    except Exception as e:
        result["error"] = str(e)
        result["error_type"] = type(e).__name__
        result["is_valid"] = False

    return result