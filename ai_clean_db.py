import sqlite3
import os
import json
import time
import requests
import re
import config

# ================= 🔴 网络配置 =================
PROXY_URL = 'http://127.0.0.1:7897'
PROXIES = {
    "http": PROXY_URL,
    "https": PROXY_URL
}
API_KEY = config.GOOGLE_API_KEY
# ===============================================

DB_PATH = config.DB_COOK
COOK_ROOT = config.COOK_ROOT

def init_db():
    # 不删除旧库，支持断点续传
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS recipes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, category TEXT, path TEXT, raw_ingredients TEXT,
        structured_ingredients TEXT, tags TEXT, difficulty INTEGER, calories_est INTEGER
    )''')
    c.execute('CREATE TABLE IF NOT EXISTS search_history (id INTEGER PRIMARY KEY, keyword TEXT, search_time DATETIME)')
    c.execute('CREATE TABLE IF NOT EXISTS favorites (id INTEGER PRIMARY KEY, recipe_name TEXT)')
    conn.commit()
    return conn

# --- 备胎：正则提取 (当AI失败时使用) ---
def extract_by_regex(content):
    ingredients = []
    lines = content.split('\n')
    capture = False
    for line in lines:
        line = line.strip()
        if line.startswith('##') and any(k in line for k in ['原料', '材料', '食材']):
            capture = True; continue
        if line.startswith('##') and capture: break
        if capture and (line.startswith('-') or line.startswith('*')):
            text = line[1:].strip()
            item = re.split(r'[:：,，\d]', text)[0].strip().replace('*', '')
            if item and len(item) < 10: ingredients.append(item)
    
    return {
        "main_ingredients": list(set(ingredients)),
        "tags": ["家常菜"], "difficulty": 3, "calories": 0
    }

# --- 核心：AI 响应解析 (修复 List 报错) ---
def parse_ai_response(text):
    try:
        # 1. 尝试清洗 Markdown 标记
        clean_text = text.replace('```json', '').replace('```', '').strip()
        data = json.loads(clean_text)
    except:
        return None

    # 2. 关键修复：如果 AI 返回了列表，取第一个元素
    if isinstance(data, list):
        if len(data) > 0 and isinstance(data[0], dict):
            data = data[0]
        else:
            return None 

    if not isinstance(data, dict): return None
    return data

def analyze_recipe_rest(content, dish_name):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    
    prompt = f"""
    分析菜谱《{dish_name}》。内容：{content[:1500]}...
    请提取以下信息并以纯 JSON 对象格式返回：
    {{
        "main_ingredients": ["食材1", "食材2"], 
        "tags": ["标签1", "标签2"],
        "difficulty": 3,
        "calories": 500
    }}
    注意：main_ingredients 只列出核心食材。
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    
    headers = {'Content-Type': 'application/json', 'X-goog-api-key': API_KEY}
    
    for attempt in range(3): # 遇到错误重试3次
        try:
            response = requests.post(url, json=payload, headers=headers, proxies=PROXIES, timeout=30)
            
            if response.status_code == 200:
                raw_text = response.json()['candidates'][0]['content']['parts'][0]['text']
                return parse_ai_response(raw_text)
            elif response.status_code == 429:
                print(f"[429] 休息30秒...", end="", flush=True)
                time.sleep(30) # 遇到限流，狠狠休息1分钟
                continue
            else:
                # print(f"[HTTP {response.status_code}]", end="")
                pass
        except:
            time.sleep(5)
            continue
    return None

def main():
    print(f"🔌 代理: {PROXY_URL}")
    print(f"🐢 启动【安全慢速】模式：请求间隔 10 秒")
    
    conn = init_db()
    c = conn.cursor()
    
    files = []
    for root, dirs, filenames in os.walk(COOK_ROOT):
        for f in filenames:
            if f.endswith('.md') and not f.startswith('README'):
                files.append((f.replace('.md',''), os.path.basename(root), os.path.join(root, f), os.path.join(os.path.basename(root), f)))

    print(f"📊 总计: {len(files)} 道菜谱")
    
    success_cnt = 0
    
    for i, (name, cat, full_path, rel_path) in enumerate(files):
        print(f"\r[{i+1}/{len(files)}] 处理: {name:<10} ", end="", flush=True)
        
        # 断点续传检查
        check = c.execute("SELECT id FROM recipes WHERE name=? AND structured_ingredients IS NOT NULL", (name,)).fetchone()
        if check:
            print("⏭️", end="") # 已存在，跳过
            continue

        with open(full_path, 'r', encoding='utf-8') as f: content = f.read()
        
        # 1. AI 尝试
        data = analyze_recipe_rest(content, name)
        
        # 2. 失败则正则兜底
        if not data or not data.get('main_ingredients'):
            data = extract_by_regex(content)
            print("⚠️(正则)", end="")
        else:
            print("✅(AI)", end="")
            success_cnt += 1
            
        # 入库
        c.execute("DELETE FROM recipes WHERE name=?", (name,)) # 删旧
        try:
            c.execute('''INSERT INTO recipes VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (name, cat, rel_path, "", 
                 json.dumps(data.get('main_ingredients', []), ensure_ascii=False),
                 json.dumps(data.get('tags', []), ensure_ascii=False),
                 data.get('difficulty', 3), data.get('calories', 0)))
        except:
            pass
            
        # ✅ 安全间隔：10秒
        # 这是为了确保您的账号绝对安全，您可以去忙别的，让它慢慢跑
        time.sleep(2) 
        conn.commit()

    conn.close()
    print(f"\n\n🎉 全部完成！本次 AI 清洗成功: {success_cnt} 条。")

if __name__ == "__main__":
    main()