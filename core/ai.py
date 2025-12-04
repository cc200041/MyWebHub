# 文件: core/ai.py （改成使用阿里云通义千问 Qwen）
import requests
import json
import config
import base64
import re

# DashScope 文本生成接口
API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

# 这里优先使用 QWEN_API_KEY，如果没有，就回退到 GOOGLE_API_KEY
API_KEY = getattr(config, "QWEN_API_KEY", None) or getattr(config, "GOOGLE_API_KEY", "")


def _call_qwen(messages, temperature=0.7, max_tokens=1024):
    """
    调用千问文本接口。
    messages: [{"role": "system"|"user"|"assistant", "content": "xxx"}, ...]
    返回字符串（模型回复），出错时返回 None
    """
    if not API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "qwen-plus",  # 也可以换成 qwen-max / qwen-turbo，看你账户额度
        "input": {
            "messages": messages
        },
        "parameters": {
            "result_format": "message",  # 返回 message 结构，方便取 content
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
    }

    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            return None
        data = resp.json()
        # 官方返回：output.choices[0].message.content
        return (
            data.get("output", {})
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
        )
    except Exception:
        return None


# -------- 通用 JSON 解析工具 --------

def parse_json(text):
    """
    从模型返回的字符串里，尽量把 JSON 抠出来并转成 dict/list。
    """
    if not text:
        return None

    # 1. 先找 ```json ... ``` 这种包裹
    code_block = re.search(r"```json(.*?)```", text, re.S | re.I)
    if code_block:
        text = code_block.group(1)

    # 2. 再找第一个 { 或 [ 开头 的 JSON 片段
    m = re.search(r"([\{\[][\s\S]*[\}\]])", text)
    if m:
        text = m.group(1)

    try:
        return json.loads(text)
    except Exception:
        return None


# ========= 对外暴露的三个函数 =========

def chat_with_text(prompt: str) -> str:
    """
    普通聊天 / 解释说明，用于：
      - 饮食分析
      - 厨房问答等
    """
    msg = [
        {
            "role": "system",
            "content": "你是一个说话可爱、会认真解释的健康与美食助手“小ka”，回答要简洁、口语化，用中文。"
        },
        {"role": "user", "content": prompt},
    ]
    result = _call_qwen(msg, temperature=0.6, max_tokens=800)
    return result or "小ka这边网络有点问题，稍后再试一下叭～"


def generate_json(prompt: str):
    """
    让模型严格输出 JSON，给做饭 / 记录热量用。
    """
    msg = [
        {
            "role": "system",
            "content": (
                "你是一个只会输出 JSON 的助手，必须返回合法 JSON，不能带任何解释文字。"
                "如果用户问题无法用结构化表示，就用一个字段 reason 来说明原因。"
            ),
        },
        {"role": "user", "content": prompt},
    ]
    result = _call_qwen(msg, temperature=0.2, max_tokens=1200)
    return parse_json(result)


def analyze_image(img_bytes: bytes, prompt: str):
    """
    目前先占位：千问的多模态接口和文本接口不同，这里暂时只返回 None。
    前端那边已经写了 “ai.analyze_image(...) or {}”，所以不会炸，只是提示识别失败。
    以后想接入图片识别，可以再单独换成多模态 API。
    """
    return None
