"""
Gemini LLM Client Module for Website Operations Support Assistant.
Thực thi các lệnh gọi REST API tới Google Gemini (Generative Language API)
phục vụ cho Incident Analysis Agent (suy luận nguyên nhân gốc RCA & Runbook).
Sử dụng httpx tiêu chuẩn, không phụ thuộc thư viện nặng, hỗ trợ timeout và kiểm thử kết nối.
"""

import time
from typing import Dict, Any, Optional
import httpx

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

def test_gemini_connection(api_key: str, model: str = "gemini-flash-latest") -> Dict[str, Any]:
    """
    Kiểm tra tính hợp lệ của Gemini API Key và khả năng kết nối tới máy chủ Google AI.
    
    Returns:
        Dict[str, Any]: {
            "success": bool,
            "message": str,
            "latency_ms": float,
            "model": str
        }
    """
    clean_key = (api_key or "").strip()
    if not clean_key:
        return {
            "success": False,
            "message": "Gemini API Key đang để trống. Vui lòng nhập API Key.",
            "latency_ms": 0.0,
            "model": model
        }

    url = f"{GEMINI_API_BASE}/{model}:generateContent?key={clean_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": "Xin chào, hãy phản hồi ngắn gọn đúng 2 từ: OK Ready"}
                ]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 250,
            "temperature": 0.1
        }
    }

    start_time = time.perf_counter()
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            latency_ms = round((time.perf_counter() - start_time) * 1000, 1)

            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                reply_text = ""
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    reply_text = "".join([p.get("text", "") for p in parts if "text" in p]).strip()

                return {
                    "success": True,
                    "message": f"Kết nối Gemini API thành công! Mô hình: {model} | Độ trễ: {latency_ms}ms | Phản hồi: '{reply_text}'",
                    "latency_ms": latency_ms,
                    "model": model
                }
            else:
                try:
                    err_info = resp.json().get("error", {})
                    err_detail = err_info.get("message", resp.text)
                except Exception:
                    err_detail = resp.text

                return {
                    "success": False,
                    "message": f"Google Gemini API từ chối ({resp.status_code}): {err_detail}",
                    "latency_ms": latency_ms,
                    "model": model
                }

    except httpx.TimeoutException:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
        return {
            "success": False,
            "message": f"Kết nối Gemini API bị quá thời gian chờ (Timeout sau {latency_ms}ms). Vui lòng kiểm tra lại mạng Internet.",
            "latency_ms": latency_ms,
            "model": model
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
        return {
            "success": False,
            "message": f"Lỗi không xác định khi kết nối Gemini API: {str(e)}",
            "latency_ms": latency_ms,
            "model": model
        }

def generate_gemini_analysis_with_telemetry(
    prompt: str,
    api_key: str,
    model: str = "gemini-flash-latest",
    system_instruction: Optional[str] = None,
    timeout: float = 20.0
) -> Dict[str, Any]:
    """
    Gửi câu lệnh phân tích tới Gemini API và thu thập đầy đủ chỉ số LLMOps Telemetry:
    - text: Câu trả lời từ LLM (hoặc None nếu lỗi).
    - is_success: Trạng thái gọi thành công hay không.
    - latency_ms: Thời gian phản hồi API (ms).
    - prompt_tokens: Số token đầu vào.
    - completion_tokens: Số token sinh ra.
    - total_tokens: Tổng token tiêu thụ.
    - model: Tên mô hình Gemini được sử dụng.
    - status: 'SUCCESS' | 'RATE_LIMITED' | 'TIMEOUT' | 'API_ERROR' | 'NETWORK_ERROR' | 'MISSING_KEY'.
    - error_message: Chi tiết lỗi nếu có.
    """
    clean_key = (api_key or "").strip()
    if not clean_key:
        return {
            "text": None,
            "is_success": False,
            "latency_ms": 0.0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "model": model,
            "status": "MISSING_KEY",
            "error_message": "Gemini API key chưa được cấu hình."
        }

    url = f"{GEMINI_API_BASE}/{model}:generateContent?key={clean_key}"
    payload: Dict[str, Any] = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1024
        }
    }

    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [
                {"text": system_instruction}
            ]
        }

    start_time = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            latency_ms = round((time.perf_counter() - start_time) * 1000, 1)

            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                extracted_text = None
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    extracted_text = "".join([p.get("text", "") for p in parts if "text" in p]).strip()

                usage = data.get("usageMetadata", {})
                p_tokens = usage.get("promptTokenCount", 0)
                c_tokens = usage.get("candidatesTokenCount", 0)
                t_tokens = usage.get("totalTokenCount", p_tokens + c_tokens)

                return {
                    "text": extracted_text,
                    "is_success": bool(extracted_text),
                    "latency_ms": latency_ms,
                    "prompt_tokens": p_tokens,
                    "completion_tokens": c_tokens,
                    "total_tokens": t_tokens,
                    "model": model,
                    "status": "SUCCESS" if extracted_text else "EMPTY_RESPONSE",
                    "error_message": None if extracted_text else "Mô hình trả về nội dung rỗng."
                }
            elif resp.status_code == 429:
                try:
                    err_detail = resp.json().get("error", {}).get("message", resp.text)
                except Exception:
                    err_detail = resp.text
                print(f"[!] Gemini API Rate Limit (429): {err_detail[:150]}")
                return {
                    "text": None,
                    "is_success": False,
                    "latency_ms": latency_ms,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "model": model,
                    "status": "RATE_LIMITED",
                    "error_message": f"Vượt ngưỡng hạn ngạch (HTTP 429 Rate Limit): {err_detail[:150]}"
                }
            else:
                try:
                    err_detail = resp.json().get("error", {}).get("message", resp.text)
                except Exception:
                    err_detail = resp.text
                print(f"[!] Gemini API Error ({resp.status_code}): {err_detail[:150]}")
                return {
                    "text": None,
                    "is_success": False,
                    "latency_ms": latency_ms,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "model": model,
                    "status": "API_ERROR",
                    "error_message": f"Lỗi API HTTP {resp.status_code}: {err_detail[:150]}"
                }

    except httpx.TimeoutException:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
        print(f"[!] Gemini API Timeout after {latency_ms}ms")
        return {
            "text": None,
            "is_success": False,
            "latency_ms": latency_ms,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "model": model,
            "status": "TIMEOUT",
            "error_message": f"Hết thời gian chờ (Timeout sau {latency_ms}ms)."
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
        print(f"[!] Exception calling Gemini API: {e}")
        return {
            "text": None,
            "is_success": False,
            "latency_ms": latency_ms,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "model": model,
            "status": "NETWORK_ERROR",
            "error_message": f"Lỗi mạng / ngoại lệ: {str(e)}"
        }

def generate_gemini_analysis(
    prompt: str,
    api_key: str,
    model: str = "gemini-flash-latest",
    system_instruction: Optional[str] = None,
    timeout: float = 20.0
) -> Optional[str]:
    """
    Wrapper tương thích ngược: Gửi câu lệnh phân tích và trích xuất chuỗi văn bản.
    """
    res = generate_gemini_analysis_with_telemetry(
        prompt=prompt,
        api_key=api_key,
        model=model,
        system_instruction=system_instruction,
        timeout=timeout
    )
    return res.get("text")
