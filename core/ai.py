# 文件: core/ai.py
import requests
import json
import config
import base64
import re

PROXY_URL = 'http://127.0.0.1:7897'
PROXIES = {
    "http": PROXY_URL,
    "https": PROXY_URL
}

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

def _call_gemini_api(payload):
    headers = {
        'Content-Type': 'application/json',
        'X-goog-api-key': config.GOOGLE_API_KEY
    }
    try:
        resp = requests.post(
            API_URL,
            json=payload,
            headers=headers,
            proxies=PROXIES,
            timeout=40
        )
        if resp.status_code != 200:
            print(f"❌ AI API Error: {resp.status_code} - {resp.text[:100]}")
            return None
        return resp.json()
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return None

def parse_json(text: str):
    """清洗 ```json 包裹 + 容错 list/dict"""
    try:
        clean = re.sub(r'```json\s*|\s*```', '', text).strip()
        data = json.loads(clean)
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None

def generate_json(prompt: str):
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    result = _call_gemini_api(payload)
    if not result:
        return None
    try:
        txt = result["candidates"][0]["content"]["parts"][0]["text"]
        return parse_json(txt)
    except Exception:
        return None

def chat_with_text(prompt: str) -> str:
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    result = _call_gemini_api(payload)
    if not result:
        return "网络连接失败，请检查代理设置。"
    try:
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return "AI 解析错误"

def analyze_image(image_bytes: bytes, prompt: str):
    b64_data = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/jpeg", "data": b64_data}}
            ]
        }],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    result = _call_gemini_api(payload)
    if not result:
        return None
    try:
        txt = result["candidates"][0]["content"]["parts"][0]["text"]
        return parse_json(txt)
    except Exception:
        return None
