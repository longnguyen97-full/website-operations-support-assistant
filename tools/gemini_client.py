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

def test_gemini_connection(api_key: str, model: str = "gemini-1.5-flash") -> Dict[str, Any]:
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
                    {"text": "Xin chào, phản hồi ngắn gọn 'OK'."}
                ]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 15,
            "temperature": 0.1
        }
    }

    start_time = time.perf_counter()
    try:
        with httpx.Client(timeout=12.0) as client:
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
                    if parts:
                        reply_text = parts[0].get("text", "").strip()

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

def generate_gemini_analysis(
    prompt: str,
    api_key: str,
    model: str = "gemini-1.5-flash",
    system_instruction: Optional[str] = None,
    timeout: float = 20.0
) -> Optional[str]:
    """
    Gửi câu lệnh phân tích tới Gemini API và trích xuất câu trả lời văn bản.
    Trả về None nếu có lỗi xảy ra để hệ thống tự động Fallback về Rule-Based KB.
    """
    clean_key = (api_key or "").strip()
    if not clean_key:
        return None

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
            "temperature": 0.3,
            "maxOutputTokens": 1024
        }
    }

    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [
                {"text": system_instruction}
            ]
        }

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "").strip()
            else:
                print(f"[!] Gemini API Error ({resp.status_code}): {resp.text[:200]}")
                return None
    except Exception as e:
        print(f"[!] Exception calling Gemini API: {e}")
        return None

    return None
