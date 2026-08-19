import time
import dns.resolver
from typing import Optional, Dict, Any
from config import DNS_TIMEOUT_SECONDS

def check_dns(domain: str, baseline: Optional[dict] = None, timeout: float = DNS_TIMEOUT_SECONDS) -> dict:
    """
    Kiểm tra hệ thống tên miền DNS dựa trên RFC 1035.
    Hỗ trợ phân giải A, AAAA, CNAME, MX, TXT, trích xuất TTL và phát hiện Load Balancing.
    """
    clean_domain = domain.strip().rstrip('.')
    result = {
        "domain": clean_domain,
        "resolved": False,
        "resolution_time_ms": 0.0,
        "a": [],
        "aaaa": [],
        "cname": None,
        "mx": [],
        "txt": [],
        "ttl": {},
        "records_status": {},
        "changes_detected": {},
        "is_load_balancing_suspected": False,
        "error": None
    }
    
    resolver = dns.resolver.Resolver()
    resolver.timeout = timeout
    resolver.lifetime = timeout
    start_time = time.time()
    
    # Hàm helper query từng record an toàn
    def query_record(rdtype: str):
        try:
            answers = resolver.resolve(clean_domain, rdtype)
            ttl = answers.rrset.ttl if answers.rrset else None
            return answers, ttl, None
        except dns.resolver.NXDOMAIN:
            return None, None, "NXDOMAIN"
        except dns.resolver.NoAnswer:
            return None, None, "NO_ANSWER"
        except dns.resolver.Timeout:
            return None, None, "TIMEOUT"
        except Exception as e:
            return None, None, str(e)

    # 1. Bản ghi A (IPv4)
    a_answers, a_ttl, a_err = query_record('A')
    if a_answers:
        result["a"] = sorted([str(r) for r in a_answers])
        result["ttl"]["a"] = a_ttl
        result["records_status"]["a"] = "OK"
        result["resolved"] = True
    else:
        result["records_status"]["a"] = a_err

    # 2. Bản ghi AAAA (IPv6)
    aaaa_answers, aaaa_ttl, aaaa_err = query_record('AAAA')
    if aaaa_answers:
        result["aaaa"] = sorted([str(r) for r in aaaa_answers])
        result["ttl"]["aaaa"] = aaaa_ttl
        result["records_status"]["aaaa"] = "OK"
        result["resolved"] = True
    else:
        result["records_status"]["aaaa"] = aaaa_err

    # 3. Bản ghi CNAME
    cname_answers, cname_ttl, cname_err = query_record('CNAME')
    if cname_answers:
        result["cname"] = str(cname_answers[0].target).rstrip('.')
        result["ttl"]["cname"] = cname_ttl
        result["records_status"]["cname"] = "OK"
        result["resolved"] = True
    else:
        result["records_status"]["cname"] = cname_err

    # 4. Bản ghi MX (Mail Exchange)
    mx_answers, mx_ttl, mx_err = query_record('MX')
    if mx_answers:
        result["mx"] = sorted([f"{r.preference} {str(r.exchange).rstrip('.')}" for r in mx_answers])
        result["ttl"]["mx"] = mx_ttl
        result["records_status"]["mx"] = "OK"
        result["resolved"] = True
    else:
        result["records_status"]["mx"] = mx_err

    # 5. Bản ghi TXT
    txt_answers, txt_ttl, txt_err = query_record('TXT')
    if txt_answers:
        result["txt"] = sorted([r.to_text().strip('"') for r in txt_answers])
        result["ttl"]["txt"] = txt_ttl
        result["records_status"]["txt"] = "OK"
        result["resolved"] = True
    else:
        result["records_status"]["txt"] = txt_err

    # Fallback cho localhost / tên miền nội bộ qua OS Resolver (file hosts / loopback)
    # dnspython mặc định query ra ngoài công cộng sẽ bị NXDOMAIN với localhost
    if not result["resolved"] or clean_domain.lower() in ["localhost", "127.0.0.1", "::1"] or clean_domain.lower().endswith(".local") or clean_domain.lower().endswith(".localhost"):
        try:
            import socket
            addr_info = socket.getaddrinfo(clean_domain, None)
            ipv4_list = sorted(list(set([item[4][0] for item in addr_info if item[0] == socket.AF_INET])))
            ipv6_list = sorted(list(set([item[4][0] for item in addr_info if item[0] == socket.AF_INET6])))
            
            if ipv4_list:
                result["a"] = ipv4_list
                result["ttl"]["a"] = "OS Hosts/Cache"
                result["records_status"]["a"] = "OK (OS Resolver)"
                result["resolved"] = True
            if ipv6_list:
                result["aaaa"] = ipv6_list
                result["ttl"]["aaaa"] = "OS Hosts/Cache"
                result["records_status"]["aaaa"] = "OK (OS Resolver)"
                result["resolved"] = True
        except Exception:
            pass

    # Tính tổng thời gian phân giải
    end_time = time.time()
    result["resolution_time_ms"] = round((end_time - start_time) * 1000, 2)

    # Nếu tất cả query đều gặp lỗi NXDOMAIN hoặc TIMEOUT
    if not result["resolved"]:
        all_errs = list(result["records_status"].values())
        if "NXDOMAIN" in all_errs:
            result["error_title"] = "Domain Not Found (NXDOMAIN)"
            result["error_detail"] = f"Domain '{clean_domain}' does not exist in DNS (NXDOMAIN / [Errno 11001] getaddrinfo failed)."
        elif "TIMEOUT" in all_errs:
            result["error_title"] = "DNS Query Timeout"
            result["error_detail"] = f"DNS query timed out after {timeout}s for domain '{clean_domain}'."
        else:
            result["error_title"] = "DNS Resolution Failed"
            result["error_detail"] = f"Failed to resolve DNS records for domain '{clean_domain}'."
        result["error"] = result["error_detail"]
    else:
        result["error"] = None
        result["error_title"] = None
        result["error_detail"] = None

    # 6. So sánh với baseline & Phân biệt Load Balancing vs Thay đổi ngoài dự kiến
    if baseline:
        changes = {}
        for field in ["a", "aaaa", "cname", "mx", "txt"]:
            current_val = result.get(field)
            baseline_val = baseline.get(field)
            if baseline_val is not None and current_val != baseline_val:
                changes[field] = {"baseline": baseline_val, "current": current_val}

        # Cơ chế phát hiện Load Balancing / Multi-IP Round-Robin
        is_lb = False
        if "a" in changes:
            curr_a_set = set(result["a"])
            base_a_set = set(baseline.get("a") or [])
            # Nếu tập IP giống nhau nhưng thứ tự khác, hoặc giao nhau (subset/superset/multi-ip pool)
            if curr_a_set == base_a_set:
                is_lb = True
            elif len(curr_a_set & base_a_set) > 0:
                is_lb = True
            elif len(curr_a_set) > 1:
                # Có nhiều IP trả về từ CDN / Load Balancer
                is_lb = True
                
        if len(result["a"]) > 1 or len(result["aaaa"]) > 1:
            result["is_load_balancing_suspected"] = True
        elif is_lb:
            result["is_load_balancing_suspected"] = True

        result["changes_detected"] = changes

    return result