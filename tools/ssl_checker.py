import ssl
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse

def check_ssl(url_or_host: str) -> dict:
    """
    Kiểm tra chứng chỉ SSL/TLS và phiên bản dựa trên RFC 5280 và RFC 8446.
    """
    if "://" in url_or_host:
        parsed = urlparse(url_or_host)
        hostname = parsed.hostname
        port = parsed.port or 443
    else:
        hostname = url_or_host
        port = 443

    result = {
        "hostname": hostname,
        "is_valid": False,
        "not_before": None,
        "not_after": None,
        "days_remaining": 0,
        "issuer": None,
        "subject_alternative_names": [],
        "hostname_matched": False,
        "tls_version": None,
        "error": None
    }

    context = ssl.create_default_context()

    try:
        with socket.create_connection((hostname, port), timeout=5.0) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                result["tls_version"] = ssock.version()

                # Trích xuất thời gian hiệu lực
                not_before_str = cert.get('notBefore')
                not_after_str = cert.get('notAfter')
                
                if not_before_str and not_after_str:
                    not_before = datetime.strptime(not_before_str, '%b %d %H:%M:%S %Y %Z').replace(tzinfo=timezone.utc)
                    not_after = datetime.strptime(not_after_str, '%b %d %H:%M:%S %Y %Z').replace(tzinfo=timezone.utc)
                    
                    result["not_before"] = not_before.isoformat()
                    result["not_after"] = not_after.isoformat()
                    
                    now = datetime.now(timezone.utc)
                    result["days_remaining"] = (not_after - now).days
                    result["is_valid"] = now <= not_after

                # Nhà phát hành chứng chỉ
                issuer_dict = dict(x[0] for x in cert.get('issuer', []))
                result["issuer"] = issuer_dict.get('commonName') or issuer_dict.get('organizationName')

                # Subject Alternative Names (SAN)
                sans = cert.get('subjectAltName', ())
                result["subject_alternative_names"] = [val for sub_type, val in sans if sub_type == 'DNS']

                # Hostname validation
                try:
                    ssl.match_hostname(cert, hostname)
                    result["hostname_matched"] = True
                except ssl.CertificateError:
                    result["hostname_matched"] = False
                    result["is_valid"] = False

    except Exception as e:
        result["error"] = str(e)
        result["is_valid"] = False

    return result