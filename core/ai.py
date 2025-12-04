# 文件: core/ai.py
import os
import requests
import json
import config
import base64
import re

# =============== 代理设置 ===============
# 本地调试：如果系统里配了 HTTP_PROXY / HTTPS_PROXY，就自动走代理
# Render 云端：默认不配这些环境变量，就不会走代理，直接连外网
PROXY_URL = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
if PROXY_URL:
    PROXIES = {
        "http": PROXY_URL,
        "https": PROXY_URL,
    }
else:
    PROXIES = None

# =============== Gemini 配置 ===============
API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)


def _call_gemini_api(payload: dict):
    """底层请求封装，所有上层功能都走这一层。"""
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": config.GOOGLE_API_KEY,
    }
    try:
        kwargs = {
            "json": payload,
            "headers": headers,
            "timeout": 40,
        }
        if PROXIES:
            kwargs["proxies"] = PROXIES

        resp = requests.post(API_URL, **kwargs)

        if resp.status_code != 200:
            print(f"❌ AI API Error: {resp.status_code} - {resp.text[:200]}")
            return None
        return resp.json()
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return None


def parse_json(text: str):
    """清洗 ```json 包裹 + 容错 list/dict."""
    try:
        # 去掉 ```json ... ``` 包裹
        clean = re.sub(r"```json\s*|\s*```", "", text).strip()
        data = json.loads(clean)

        # 有些模型会返回 [ {...} ]，只取第一个
        if isinstance(data, list) and data:
            return data[0]
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


def generate_json(prompt: str):
    """让模型直接按 JSON 格式回答，返回 Python dict。"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "response_mime_type": "application/json",
        },
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
    """普通文本对话，返回字符串。"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
    }
    result = _call_gemini_api(payload)
    if not result:
        return "网络连接失败，请稍后再试。"
    try:
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return "AI 解析错误"


def analyze_image(image_bytes: bytes, prompt: str):
    """
    图像 + 文本提示联合输入，要求模型输出 JSON，
    返回 Python dict（或 None）。
    """
    b64_data = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": b64_data,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
        },
    }
    result = _call_gemini_api(payload)
    if not result:
        return None
    try:
        txt = result["candidates"][0]["content"]["parts"][0]["text"]
        return parse_json(txt)
    except Exception:
        return None
