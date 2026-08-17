import httpx

def check_http(url: str, method: str = "GET", expected_status: int = 200) -> dict:
    """
    Kiểm tra trạng thái HTTP dựa trên RFC 9110.
    """
    result = {
        "url": url,
        "method": method.upper(),
        "status_code": None,
        "is_expected_status": False,
        "redirect_chain": [],
        "response_time_ms": 0.0,
        "headers": {},
        "error": None
    }
    
    if method.upper() not in ["GET", "HEAD"]:
        result["error"] = "Unsupported HTTP method. Use GET or HEAD."
        return result

    try:
        with httpx.Client(follow_redirects=True, timeout=10.0) as client:
            response = client.request(method.upper(), url)
            
            # Ghi nhận redirect chain
            if response.history:
                result["redirect_chain"] = [
                    {"url": str(resp.url), "status_code": resp.status_code} 
                    for resp in response.history
                ]
            
            result["status_code"] = response.status_code
            result["is_expected_status"] = (response.status_code == expected_status)
            result["response_time_ms"] = round(response.elapsed.total_seconds() * 1000, 2)
            
            # Lọc các header liên quan đến caching, retry và server response
            relevant_headers = ["cache-control", "retry-after", "server", "content-type", "age", "etag"]
            result["headers"] = {k: response.headers.get(k) for k in relevant_headers if k in response.headers}

    except httpx.RequestError as e:
        result["error"] = str(e)
        
    return result