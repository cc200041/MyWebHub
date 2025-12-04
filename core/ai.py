# 文件：core/ai.py
# 说明：去掉本地 127.0.0.1 代理，在 Render 等云环境可以正常访问 Gemini

import requests
import json
import base64
import config
import re

# Google Gemini API 地址
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# 不再强制走本地代理，云服务器上没有 127.0.0.1:7897
PROXIES = None  # 本地如果一定想走代理，可以改成 {"http": "...", "https": "..."}

def _call_gemini_api(payload: dict):
    """底层请求 Gemini 的封装，出错时返回 None，并在日志中打印错误。"""
    try:
        resp = requests.post(
            API_URL,
            params={"key": config.GOOGLE_API_KEY},
            json=payload,
            timeout=30,
            proxies=PROXIES,
        )
        resp.raise_for_status()
        data = resp.json()
        # 如果 Gemini 返回的是错误结构，也打印出来
        if isinstance(data, dict) and data.get("error"):
            print("[Gemini] API error:", data)
            return None
        return data
    except Exception as e:
        print("[Gemini] request failed:", repr(e))
        return None


def chat_with_text(prompt: str) -> str:
    """普通对话：输入一段文字，返回一段文字。"""
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    result = _call_gemini_api(payload)
    if not result:
        return "小ka 这边连不上 AI 服务了，稍后再试试吧～"

    try:
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print("[Gemini] parse text error:", repr(e), "resp=", result)
        return "AI 返回的内容我解析失败了，先用右边搜索框顶一顶～"


def _try_parse_json(text: str):
    """尽量从模型输出里抠出 JSON。"""
    try:
        return json.loads(text)
    except Exception:
        pass

    try:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
    except Exception:
        pass
    return None


def generate_json(prompt: str):
    """
    让模型直接返回 JSON（用于做饭/减脂这些功能）。
    返回 Python dict / list，失败则返回 None。
    """
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
    except Exception as e:
        print("[Gemini] no text in JSON response:", repr(e), "resp=", result)
        return None

    js = _try_parse_json(txt)
    if js is None:
        print("[Gemini] JSON parse failed, raw text:", txt)
    return js


def analyze_image(image_bytes: bytes, prompt: str):
    """
    图像 + 文本的 JSON 分析（给减脂 app 用的多模态）。
    返回 dict / list，失败返回 None。
    """
    b64_data = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/jpeg", "data": b64_data}},
            ]
        }],
        "generationConfig": {
            "response_mime_type": "application/json",
        },
    }
    result = _call_gemini_api(payload)
    if not result:
        return None

    try:
        txt = result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print("[Gemini] image response no text:", repr(e), "resp=", result)
        return None

    js = _try_parse_json(txt)
    if js is None:
        print("[Gemini] image JSON parse failed, raw text:", txt)
    return js
