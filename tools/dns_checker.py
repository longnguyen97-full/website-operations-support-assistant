import time
import dns.resolver

def check_dns(domain: str, baseline: dict = None) -> dict:
    """
    Kiểm tra hệ thống tên miền DNS dựa trên RFC 1035.
    """
    result = {
        "domain": domain,
        "resolved": False,
        "resolution_time_ms": 0.0,
        "a": [],
        "aaaa": [],
        "cname": None,
        "mx": [],
        "txt": [],
        "changes_detected": {}
    }
    
    resolver = dns.resolver.Resolver()
    start_time = time.time()
    
    try:
        # Bản ghi A (IPv4)
        try:
            answers = resolver.resolve(domain, 'A')
            result["a"] = sorted([str(r) for r in answers])
            result["resolved"] = True
        except Exception:
            pass

        # Bản ghi AAAA (IPv6)
        try:
            answers = resolver.resolve(domain, 'AAAA')
            result["aaaa"] = sorted([str(r) for r in answers])
            result["resolved"] = True
        except Exception:
            pass

        # Bản ghi CNAME
        try:
            answers = resolver.resolve(domain, 'CNAME')
            result["cname"] = str(answers[0].target).rstrip('.')
            result["resolved"] = True
        except Exception:
            pass

        # Bản ghi MX
        try:
            answers = resolver.resolve(domain, 'MX')
            result["mx"] = sorted([f"{r.preference} {str(r.exchange).rstrip('.')}" for r in answers])
            result["resolved"] = True
        except Exception:
            pass

        # Bản ghi TXT
        try:
            answers = resolver.resolve(domain, 'TXT')
            result["txt"] = sorted([r.to_text().strip('"') for r in answers])
            result["resolved"] = True
        except Exception:
            pass

    except Exception as e:
        result["error"] = str(e)
    
    end_time = time.time()
    result["resolution_time_ms"] = round((end_time - start_time) * 1000, 2)

    # So sánh giá trị bản ghi so với baseline
    if baseline:
        changes = {}
        for field in ["a", "aaaa", "cname", "mx", "txt"]:
            current_val = result.get(field)
            baseline_val = baseline.get(field)
            if current_val != baseline_val:
                changes[field] = {"baseline": baseline_val, "current": current_val}
        result["changes_detected"] = changes

    return result