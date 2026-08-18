import httpx
from typing import Optional
from config import HTTP_TIMEOUT_SECONDS, DEFAULT_USER_AGENT

def get_status_category(status_code: Optional[int]) -> Optional[str]:
    """Phân loại mã trạng thái theo RFC 9110."""
    if not status_code:
        return None
    if 100 <= status_code <= 199:
        return "1xx Informational"
    elif 200 <= status_code <= 299:
        return "2xx Successful"
    elif 300 <= status_code <= 399:
        return "3xx Redirection"
    elif 400 <= status_code <= 499:
        return "4xx Client Error"
    elif 500 <= status_code <= 599:
        return "5xx Server Error"
    return "Unknown"

def check_http(url: str, method: str = "GET", expected_status: int = 200, timeout: float = HTTP_TIMEOUT_SECONDS) -> dict:
    """
    Kiểm tra trạng thái HTTP dựa trên RFC 9110.
    """
    method_upper = method.upper()
    result = {
        "url": url,
        "method": method_upper,
        "status_code": None,
        "status_category": None,
        "is_expected_status": False,
        "expected_status": expected_status,
        "is_success": False,
        "is_client_error": False,
        "is_server_error": False,
        "redirect_chain": [],
        "response_time_ms": 0.0,
        "headers": {},
        "error": None,
        "error_type": None
    }
    
    if method_upper not in ["GET", "HEAD"]:
        result["error"] = "Unsupported HTTP method. Use GET or HEAD (RFC 9110)."
        result["error_type"] = "InvalidMethod"
        return result

    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            response = client.request(method_upper, url)
            
            # Ghi nhận redirect chain
            if response.history:
                result["redirect_chain"] = [
                    {
                        "url": str(resp.url),
                        "status_code": resp.status_code,
                        "status_category": get_status_category(resp.status_code)
                    } 
                    for resp in response.history
                ]
            
            result["status_code"] = response.status_code
            result["status_category"] = get_status_category(response.status_code)
            result["is_expected_status"] = (response.status_code == expected_status)
            result["is_success"] = (200 <= response.status_code <= 299)
            result["is_client_error"] = (400 <= response.status_code <= 499)
            result["is_server_error"] = (500 <= response.status_code <= 599)
            result["response_time_ms"] = round(response.elapsed.total_seconds() * 1000, 2)
            
            # Lọc các header liên quan đến caching, retry và server response theo RFC 9110
            relevant_headers = [
                "cache-control", "retry-after", "server", "content-type", 
                "age", "etag", "expires", "last-modified", "via"
            ]
            result["headers"] = {k: response.headers.get(k) for k in relevant_headers if k in response.headers}

    except httpx.TimeoutException as e:
        result["error"] = f"Request timed out after {timeout}s: {str(e)}"
        result["error_type"] = "Timeout"
    except httpx.ConnectError as e:
        result["error"] = f"Connection failed (DNS or Network): {str(e)}"
        result["error_type"] = "ConnectionError"
    except httpx.RequestError as e:
        result["error"] = str(e)
        result["error_type"] = type(e).__name__
    except Exception as e:
        result["error"] = str(e)
        result["error_type"] = "UnknownError"
        
    return result