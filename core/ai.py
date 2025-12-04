# 文件: core/ai.py
# 说明: 使用阿里云通义千问（DashScope）作为小ka的大脑

import requests
import json
import base64
import re
import config

# DashScope 文本生成接口
QWEN_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

# 优先用通义千问的 Key
API_KEY = config.QWEN_API_KEY


def _call_qwen(messages, temperature=0.7, max_tokens=1024):
    """
    调用通义千问文本接口。
    messages: [{"role": "system"|"user"|"assistant", "content": "xxx"}, ...]
    成功时返回模型回复的字符串，失败时返回 None。
    """
    if not API_KEY:
        print("[Qwen] no API key, please set QWEN_API_KEY in environment")
        return None

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "qwen-plus",  # 额度允许的话可以换成 qwen-max / qwen-turbo
        "input": {
            "messages": messages
        },
        "parameters": {
            "result_format": "message",  # 输出为 message 结构，统一取 content
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
    }

    try:
        resp = requests.post(QWEN_API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # 官方返回结构: output.choices[0].message.content
        return (
            data.get("output", {})
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
        )
    except Exception as e:
        print("[Qwen] request failed:", repr(e))
        return None


# --------- JSON 解析小工具 ---------

def _try_parse_json(text: str):
    """尽量从模型输出里抠出 JSON（容错处理）"""
    if not text:
        return None

    # 1. 如果有 ```json ... ``` 包裹，先取出来
    block = re.search(r"```json(.*?)```", text, re.S | re.I)
    if block:
        text = block.group(1)

    # 2. 再尝试截取第一个 { 或 [
    m = re.search(r"([\{\[][\s\S]*[\}\]])", text)
    if m:
        text = m.group(1)

    try:
        return json.loads(text)
    except Exception:
        return None


# ========= 对外给后端用的三个函数 =========

def chat_with_text(prompt: str) -> str:
    """
    普通聊天 / 解释说明。
    用于：小卡大厨聊天、小卡营养师分析等。
    """
    messages = [
        {
            "role": "system",
            "content": "你是一个说话可爱、但是讲解很认真、会控制热量的小厨娘“小ka”，用中文回答，语气口语化简洁。"
        },
        {"role": "user", "content": prompt},
    ]

    result = _call_qwen(messages, temperature=0.6, max_tokens=800)
    if not result:
        return "小ka 这边连不上通义千问服务器了，稍后再试试叭～"

    return result


def generate_json(prompt: str):
    """
    让模型输出结构化 JSON（用于：解析食材、生成菜谱结构、热量分析等）。
    返回 Python dict / list，失败时返回 None。
    """
    messages = [
        {
            "role": "system",
            "content": (
                "你是一个只会输出 JSON 的助手，必须返回合法 JSON 字符串，"
                "不要包含任何多余的解释文字。"
                "如果无法按要求给出结构化内容，就返回："
                '{"reason": "简要说明原因"}'
            ),
        },
        {"role": "user", "content": prompt},
    ]

    result = _call_qwen(messages, temperature=0.2, max_tokens=1200)
    js = _try_parse_json(result)
    if js is None:
        print("[Qwen] JSON parse failed, raw text:", result)
    return js


def analyze_image(img_bytes: bytes, prompt: str):
    """
    预留的图像+文本接口。
    目前 DashScope 多模态接口和这个不同，这里先返回 None，
    前端本身有兜底文案，不会崩。
    以后你要做“拍照识别食物”，我们再专门接多模态 API。
    """
    return None
