import os
import shutil

# ================= 配置区域 =================
# 🔴 为了方便，您可以直接在这里填入 Key，脚本会自动写入 config.py
# 如果不填，运行完脚本后记得去 config.py 里改
YOUR_API_KEY = "AIzaSyBxmZZk2tVX7mHNtaeRsLRgMtWs2ZOKrg0" 
# ===========================================

BASE_DIR = os.getcwd()
BACKUP_DIR = os.path.join(BASE_DIR, "_OLD_BACKUP")

# 定义所有正确的文件内容
FILES = {
    "config.py": f'''import os
GOOGLE_API_KEY = "{YOUR_API_KEY}"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)
DB_DIET = os.path.join(DATA_DIR, 'diet_data.db')
DB_COOK = os.path.join(DATA_DIR, 'cook_data.db')
COOK_ROOT = os.path.join(DATA_DIR, 'HowToCook', 'dishes')
FOOD_JSON = os.path.join(DATA_DIR, 'food_database.json')
''',

    "run.py": '''from flask import Flask, render_template
from apps.diet import diet_bp
from apps.cook import cook_bp
import config

app = Flask(__name__)
app.register_blueprint(diet_bp)
app.register_blueprint(cook_bp)

@app.route('/')
def home(): return render_template('hub.html', title="AI Personal Hub")
@app.route('/diet')
def diet_page(): return render_template('diet.html', title="FitLife AI")
@app.route('/cook')
def cook_page(): return render_template('cook.html', title="AI 厨房")

if __name__ == '__main__':
    print("🚀 服务已启动: http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
''',

    "core/__init__.py": "",
    
    "core/db.py": '''import sqlite3
import config
def get_diet_conn():
    conn = sqlite3.connect(config.DB_DIET)
    conn.row_factory = sqlite3.Row
    return conn
def get_cook_conn():
    conn = sqlite3.connect(config.DB_COOK)
    conn.row_factory = sqlite3.Row
    return conn
''',

    "core/ai.py": '''import requests
import json
import config
import base64
import re

# 🔴 网络强力配置
PROXY_URL = 'http://127.0.0.1:7897'
PROXIES = { "http": PROXY_URL, "https": PROXY_URL }
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

def _call_gemini_api(payload):
    headers = { 'Content-Type': 'application/json', 'X-goog-api-key': config.GOOGLE_API_KEY }
    try:
        response = requests.post(API_URL, json=payload, headers=headers, proxies=PROXIES, timeout=40)
        if response.status_code != 200:
            print(f"❌ AI Error: {response.status_code}")
            return None
        return response.json()
    except Exception as e:
        print(f"❌ Connect Error: {e}")
        return None

def parse_json(text):
    try:
        clean_text = re.sub(r'```json\s*|\s*```', '', text).strip()
        data = json.loads(clean_text)
        if isinstance(data, list) and len(data) > 0: return data[0]
        if isinstance(data, dict): return data
    except: pass
    return None

def generate_json(prompt):
    payload = { "contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"response_mime_type": "application/json"} }
    res = _call_gemini_api(payload)
    if res:
        try: return parse_json(res['candidates'][0]['content']['parts'][0]['text'])
        except: pass
    return None

def chat_with_text(prompt):
    payload = { "contents": [{"parts": [{"text": prompt}]}] }
    res = _call_gemini_api(payload)
    if res:
        try: return res['candidates'][0]['content']['parts'][0]['text']
        except: pass
    return "AI 响应解析失败"

def analyze_image(image_bytes, prompt):
    b64_data = base64.b64encode(image_bytes).decode('utf-8')
    payload = { "contents": [{ "parts": [ {"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": b64_data}} ] }], "generationConfig": {"response_mime_type": "application/json"} }
    res = _call_gemini_api(payload)
    if res:
        try: return parse_json(res['candidates'][0]['content']['parts'][0]['text'])
        except: pass
    return None
''',

    "apps/__init__.py": "",

    "apps/diet.py": '''from flask import Blueprint, jsonify, request
from core import ai, db
import config
import datetime
import json
import os

diet_bp = Blueprint('diet', __name__)

def init_db():
    with db.get_diet_conn() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, height REAL, gender TEXT, age INTEGER, target_weight REAL, current_weight REAL)')
        conn.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, date TEXT, type TEXT, category TEXT, value REAL, note TEXT)')
        conn.execute('CREATE TABLE IF NOT EXISTS health_reports (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, date TEXT, report_type TEXT, analysis TEXT, summary TEXT)')
        if conn.execute("SELECT count(*) FROM users").fetchone()[0] == 0:
            conn.execute("INSERT INTO users (name, height, gender, age, target_weight, current_weight) VALUES (?, 175, 'male', 25, 65, 70)", ('默认用户',))
        conn.commit()
init_db()

FOOD_DB = []
if os.path.exists(config.FOOD_JSON):
    with open(config.FOOD_JSON, 'r', encoding='utf-8') as f: FOOD_DB = json.load(f)

@diet_bp.route('/api/search_food')
def search_food():
    q = request.args.get('q', '')
    res = []
    for i in FOOD_DB:
        if q in i['name']:
            x = i.copy()
            x['emoji'] = '🍱'
            res.append(x)
            if len(res)>20: break
    return jsonify(res)

@diet_bp.route('/api/diet/analyze_food_photo', methods=['POST'])
def analyze_food_photo():
    if 'photo' not in request.files: return jsonify({"error": "No image"}), 400
    prompt = "识别图中食物。返回JSON列表: [{'name':'菜名','cal':总热量整数,'note':'估算量'}]"
    return jsonify(ai.analyze_image(request.files['photo'].read(), prompt) or [])

@diet_bp.route('/api/diet/analyze_body_photo', methods=['POST'])
def analyze_body_photo():
    uid = request.form.get('user_id', 1)
    prompt = "分析健康图片(体检单/体重秤/InBody)。返回JSON: {'data':{'体重':75.5, '尿酸':400}, 'advice':'建议'}"
    res = ai.analyze_image(request.files['photo'].read(), prompt)
    if res and res.get('data', {}).get('体重'):
        with db.get_diet_conn() as conn:
            w = float(res['data']['体重'])
            conn.execute("UPDATE users SET current_weight=? WHERE id=?", (w, uid))
            conn.execute("INSERT INTO logs (user_id, date, type, value, note) VALUES (?,?,?,?,?)", (uid, datetime.date.today().isoformat(), 'weight', w, 'AI识别'))
            conn.commit()
    return jsonify(res or {})

# CRUD 接口
@diet_bp.route('/api/get_users')
def get_users():
    with db.get_diet_conn() as conn: return jsonify([dict(r) for r in conn.execute("SELECT id,name FROM users").fetchall()])

@diet_bp.route('/api/get_dashboard')
def get_dashboard():
    uid, date = request.args.get('user_id'), request.args.get('date', datetime.date.today().isoformat())
    with db.get_diet_conn() as conn:
        u = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if not u: return jsonify({}), 404
        prof = dict(u)
        food = conn.execute("SELECT SUM(value) FROM logs WHERE user_id=? AND date=? AND type='food'", (uid, date)).fetchone()[0] or 0
        logs = [dict(r) for r in conn.execute("SELECT * FROM logs WHERE user_id=? AND date=? ORDER BY id DESC", (uid, date)).fetchall()]
        return jsonify({"profile": prof, "data": {"food_today": food, "current_weight": prof['current_weight'], "history": logs}})

@diet_bp.route('/api/add', methods=['POST'])
def add():
    d=request.json
    with db.get_diet_conn() as conn:
        conn.execute("INSERT INTO logs (user_id, date, type, category, value, note) VALUES (?,?,?,?,?,?)", (d.get('user_id'), d.get('date'), d['type'], d.get('category'), d['value'], d['note']))
        if d['type']=='weight': conn.execute("UPDATE users SET current_weight=? WHERE id=?", (d['value'], d.get('user_id')))
        conn.commit()
    return jsonify({"status":"ok"})

@diet_bp.route('/api/delete_log', methods=['POST'])
def del_log():
    with db.get_diet_conn() as conn: conn.execute("DELETE FROM logs WHERE id=?", (request.json.get('id'),)); conn.commit()
    return jsonify({"status":"ok"})

@diet_bp.route('/api/get_chart_data')
def chart():
    uid = request.args.get('user_id')
    dates = [(datetime.date.today()-datetime.timedelta(days=i)).isoformat() for i in range(6,-1,-1)]
    vals = []
    with db.get_diet_conn() as conn:
        for d in dates: vals.append(conn.execute("SELECT SUM(value) FROM logs WHERE user_id=? AND date=? AND type='food'", (uid, d)).fetchone()[0] or 0)
    return jsonify({"dates":dates, "values":vals})
    
@diet_bp.route('/api/create_user', methods=['POST'])
def create_user():
    try:
        with db.get_diet_conn() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO users (name, height, gender, age, target_weight, current_weight) VALUES (?, 170, 'male', 25, 60, 60)", (request.json.get('name'),))
            conn.commit()
            return jsonify({"status":"success", "id":c.lastrowid})
    except: return jsonify({"status":"error"})

@diet_bp.route('/api/delete_user', methods=['POST'])
def delete_user():
    with db.get_diet_conn() as conn:
        conn.execute("DELETE FROM logs WHERE user_id=?", (request.json.get('id'),))
        conn.execute("DELETE FROM users WHERE id=?", (request.json.get('id'),))
        conn.commit()
    return jsonify({"status":"success"})
    
@diet_bp.route('/api/save_profile', methods=['POST'])
def save_profile():
    d = request.json
    with db.get_diet_conn() as conn:
        conn.execute("UPDATE users SET height=?, gender=?, age=?, target_weight=?, current_weight=? WHERE id=?",
            (d['height'], d['gender'], d['age'], d['target_weight'], d['current_weight_input'], d.get('user_id')))
        conn.commit()
    return jsonify({"status":"success"})
''',

    "apps/cook.py": '''from flask import Blueprint, jsonify, request, send_from_directory
from core import ai, db
import config
import os
import json
import markdown

cook_bp = Blueprint('cook', __name__)

def generate_and_save(name):
    print(f"Generating: {name}")
    prompt = f"生成菜谱《{name}》。返回JSON: {{'markdown_content':'...','meta':{{'main_ingredients':[''], 'tags':[''], 'difficulty':3, 'calories':500}}}}"
    data = ai.generate_json(prompt)
    if not data: return False
    
    save_dir = os.path.join(config.COOK_ROOT, 'AI_Generated')
    if not os.path.exists(save_dir): os.makedirs(save_dir)
    with open(os.path.join(save_dir, f"{name}.md"), 'w', encoding='utf-8') as f: f.write(data.get('markdown_content',''))
    
    with db.get_cook_conn() as conn:
        conn.execute("INSERT INTO recipes (name, category, path, structured_ingredients, tags, difficulty, calories_est) VALUES (?,?,?,?,?,?,?,?)",
            (name, 'AI生成', os.path.join('AI_Generated', f"{name}.md"), json.dumps(data['meta']['main_ingredients'], ensure_ascii=False), json.dumps(data['meta']['tags'], ensure_ascii=False), 3, data['meta']['calories']))
        conn.commit()
    return True

@cook_bp.route('/api/cook/search')
def search():
    q = request.args.get('q', '').strip()
    if not q: return jsonify([])
    with db.get_cook_conn() as conn:
        rows = conn.execute("SELECT * FROM recipes WHERE name LIKE ? OR tags LIKE ? LIMIT 20", (f'%{q}%', f'%{q}%')).fetchall()
    res = [dict(r) for r in rows]
    if not res and 1<len(q)<10:
        if generate_and_save(q):
            with db.get_cook_conn() as conn:
                res.append(dict(conn.execute("SELECT * FROM recipes WHERE name=?", (q,)).fetchone()))
    return jsonify(res)

@cook_bp.route('/api/cook/pantry')
def pantry():
    ings = set(request.args.get('ingredients','').replace('，',',').split(','))
    with db.get_cook_conn() as conn: recipes = conn.execute("SELECT * FROM recipes").fetchall()
    res = []
    for r in recipes:
        try: needed = json.loads(r['structured_ingredients'])
        except: continue
        if not needed: continue
        hits = sum(1 for n in needed if any(i in n or n in i for i in ings if i.strip()))
        missing = [n for n in needed if not any(i in n or n in i for i in ings if i.strip())]
        if hits > 0 and len(missing) <= 3:
            res.append({"name": r['name'], "category": r['category'], "score": int(hits/len(needed)*100), "missing": missing, "tags": json.loads(r['tags'])})
    res.sort(key=lambda x: x['score'], reverse=True)
    return jsonify(res[:20])

@cook_bp.route('/api/cook/detail')
def detail():
    name = request.args.get('name')
    with db.get_cook_conn() as conn: row = conn.execute("SELECT * FROM recipes WHERE name=?", (name,)).fetchone()
    if not row: return jsonify({"error": "404"})
    path = os.path.join(config.COOK_ROOT, row['path'])
    content = open(path, 'r', encoding='utf-8').read() if os.path.exists(path) else "# Missing"
    return jsonify({"name": row['name'], "category": row['category'], "html": markdown.markdown(content), "calories": row['calories_est'], "tags": json.loads(row['tags'])})

@cook_bp.route('/api/cook/ask_chef', methods=['POST'])
def ask(): return jsonify({"answer": ai.chat_with_text(f"User asks about {request.json.get('recipe')}: {request.json.get('question')}")})

@cook_bp.route('/api/cook/token', methods=['POST'])
def token(): return jsonify({"token": f"#HTC:{request.json['name']}:{request.json['cal']}#"})

@cook_bp.route('/data/HowToCook/dishes/<path:filename>')
def img(filename): return send_from_directory(config.COOK_ROOT, filename)
''',

    "templates/base.html": '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ title }} - Pixel Life</title>
<link href="https://fonts.googleapis.com/css2?family=ZCOOL+KuaiLe&display=swap" rel="stylesheet">
<script src="https://cdn.bootcdn.net/ajax/libs/vue/3.2.47/vue.global.min.js"></script>
<script src="https://cdn.bootcdn.net/ajax/libs/axios/1.3.4/axios.min.js"></script>
<script src="https://cdn.bootcdn.net/ajax/libs/echarts/5.4.1/echarts.min.js"></script>
<script src="https://cdn.tailwindcss.com"></script>
<style>
:root { --pixel-bg: #fdf6e3; --pixel-border: #433422; }
body { background: var(--pixel-bg); font-family: "ZCOOL KuaiLe"; color: var(--pixel-border); }
[v-cloak] { display: none; }
.pixel-box { background: white; border: 4px solid var(--pixel-border); box-shadow: 6px 6px 0px #c2b280; }
.pixel-btn { background: #ffcc00; border: 2px solid var(--pixel-border); box-shadow: 4px 4px 0px var(--pixel-border); transition: 0.1s; text-align: center; font-weight: bold; }
.pixel-btn:active { transform: translate(2px, 2px); box-shadow: 2px 2px 0px var(--pixel-border); }
.pixel-btn.green { background: #8cd612; color: white; }
.pixel-btn.blue { background: #00ccff; color: white; }
.sidebar { background: #2d2d2d; border-right: 4px solid var(--pixel-border); transition: transform 0.3s; }
input { border: 2px solid var(--pixel-border); background: #fff; }
</style>
</head>
<body class="flex h-screen overflow-hidden">
<div id="sidebar" class="sidebar fixed inset-y-0 left-0 w-64 text-white z-50 md:relative transform -translate-x-full md:translate-x-0 flex flex-col">
<div class="p-6 text-2xl border-b-4 border-gray-600 bg-gray-800"><span>👾 My Hub</span></div>
<nav class="flex-1 p-4 space-y-4">
<a href="/" class="block p-3 border-2 border-dashed border-transparent hover:border-white rounded">🏠 首页</a>
<a href="/diet" class="block p-3 border-2 border-dashed border-transparent hover:border-green-400 rounded text-green-300">❤️ FitLife 减脂</a>
<a href="/cook" class="block p-3 border-2 border-dashed border-transparent hover:border-yellow-400 rounded text-yellow-300">🍳 像素厨房</a>
</nav>
</div>
<div class="flex-1 flex flex-col h-screen relative">
<div class="md:hidden bg-yellow-400 p-4 border-b-4 border-black flex justify-between"><button onclick="document.getElementById('sidebar').classList.toggle('-translate-x-full')">☰</button><span class="font-bold">{{ title }}</span></div>
<main class="flex-1 overflow-y-auto p-4 md:p-8 bg-[url('https://www.transparenttextures.com/patterns/pixel-weave.png')]">{% block content %}{% endblock %}</main>
</div>
</body></html>''',

    "templates/hub.html": '''{% extends "base.html" %}
{% block content %}
<div class="max-w-4xl mx-auto p-6">
<div class="pixel-box p-8 mb-6"><h1 class="text-3xl font-bold">欢迎回来!</h1><p>这是您的个人数据中心。</p></div>
<div class="grid grid-cols-1 md:grid-cols-2 gap-6">
<a href="/diet" class="pixel-box p-6 hover:bg-green-50 block"><div class="text-4xl mb-4">🥑</div><h2 class="text-2xl font-bold">FitLife 减脂</h2></a>
<a href="/cook" class="pixel-box p-6 hover:bg-yellow-50 block"><div class="text-4xl mb-4">🍳</div><h2 class="text-2xl font-bold">AI 厨房</h2></a>
</div></div>
{% endblock %}''',

    "templates/diet.html": '''{% extends "base.html" %}
{% block content %}
{% raw %}
<div id="app" v-cloak class="max-w-2xl mx-auto space-y-6 pb-24">
<div class="pixel-box p-4 flex justify-between items-center bg-green-50">
<div @click="showUserModal=true" class="cursor-pointer flex gap-3"><div class="w-12 h-12 bg-green-500 border-2 border-black flex items-center justify-center text-white text-xl">{{ profile.name[0] }}</div><div><h1 class="text-xl">{{ profile.name }}</h1><p class="text-xs">切换用户</p></div></div>
<input type="date" v-model="currentDate" @change="onDateChange" class="pixel-btn bg-white px-2 py-1 text-sm">
</div>
<div class="pixel-box p-0 overflow-hidden bg-[#2c3e50] text-white"><div class="p-6"><div class="flex justify-between items-end mb-4"><div><p class="text-green-300 text-xs">ENERGY LEFT</p><h2 class="text-5xl font-bold">{{ remainingCal }}</h2></div><div class="text-right"><span class="bg-yellow-500 text-black px-2 border-2 border-black text-xs">{{ bmiStatus }}</span></div></div><div class="w-full h-6 border-2 border-white bg-gray-700 relative"><div class="h-full bg-green-500 transition-all" :style="{width: progressWidth + '%'}"></div></div><div class="flex justify-between text-xs mt-1"><span>{{ dashboard.food_today }}</span><span>MAX: {{ bmr }}</span></div></div><div class="bg-white p-4 border-t-4 border-black text-black grid grid-cols-2 gap-4"><label class="pixel-btn blue py-3 flex justify-center gap-2 cursor-pointer">📸 识别食物<input type="file" accept="image/*" class="hidden" @change="uploadPhoto"></label><label class="pixel-btn green py-3 flex justify-center gap-2 cursor-pointer">🩺 身体分析<input type="file" accept="image/*" class="hidden" @change="uploadBodyReport"></label></div></div>
<div class="pixel-box p-4"><h3 class="font-bold mb-2 text-sm text-gray-500">QUICK LOG</h3><div class="flex gap-2 mb-3 relative"><div class="flex-1 relative"><span class="absolute left-3 top-2.5">🔍</span><input v-model="searchQuery" @input="doSearch" placeholder="搜食物 / 粘贴口令..." class="w-full pl-9 p-2 border-2 border-black text-sm outline-none"><div v-if="searchResults.length" class="absolute top-full left-0 right-0 bg-white border-2 border-black z-50 max-h-40 overflow-y-auto"><div v-for="i in searchResults" @click="selectFood(i)" class="p-2 hover:bg-green-100 flex justify-between cursor-pointer"><span>{{ i.emoji }} {{ i.name }}</span><span>{{ i.cal }}</span></div></div></div><button v-if="searchQuery.includes('#HTC')" @click="parseToken" class="pixel-btn bg-black text-white px-4 text-xs">导入</button></div><div class="grid grid-cols-2 gap-3"><button @click="openModal('food')" class="pixel-btn bg-yellow-400 py-2 text-sm">📝 手动</button><button @click="openModal('weight')" class="pixel-btn bg-blue-200 py-2 text-sm">⚖️ 体重</button></div></div>
<div class="space-y-2"><div v-for="i in dashboard.history" class="pixel-box p-3 flex justify-between"><div class="flex gap-3"><span class="text-2xl">{{ i.type=='food'?'🍔':'⚖️' }}</span><div><div class="font-bold">{{ i.note }}</div><div class="text-xs text-gray-400">{{ i.date }} {{ i.cat }}</div></div></div><div class="flex gap-3"><span class="font-bold text-xl">{{ i.val }}</span><button @click="deleteLog(i.id)" class="text-red-500 font-bold px-2">x</button></div></div></div>
<div v-if="modal.show" class="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-6"><div class="pixel-box w-full max-w-sm p-6 bg-white relative"><button @click="modal.show=false" class="absolute top-2 right-2">✕</button><h3 class="text-xl font-bold mb-4 border-b-4 border-black pb-2">{{ modal.note||'新记录' }}</h3><div v-if="modal.isSmart" class="bg-yellow-100 border-2 border-black p-3 mb-4 text-sm">🤖 建议: {{ modal.inputVal }}</div><div v-if="modal.type=='food'" class="flex gap-2 mb-4"><button v-for="cat in ['早餐','午餐','晚餐','加餐']" @click="modal.category=cat" class="flex-1 py-1 text-xs border-2 border-black" :class="modal.category==cat?'bg-green-500 text-white':'bg-white'">{{ cat }}</button></div><input type="number" v-model="modal.inputVal" class="w-full text-4xl font-bold text-center p-3 mb-4 border-2 border-black"><div class="grid grid-cols-2 gap-4"><button @click="modal.show=false" class="pixel-btn bg-gray-200 py-3">取消</button><button @click="submitLog" class="pixel-btn green py-3">保存</button></div></div></div>
<div v-if="showUserModal" class="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-6"><div class="pixel-box w-full max-w-sm p-5 bg-white"><h3 class="text-lg font-bold mb-3 border-b-2 border-black">切换用户</h3><div class="max-h-60 overflow-y-auto space-y-2 mb-4"><div v-for="u in userList" @click="switchUser(u.id)" class="p-2 border-2 border-gray-200 cursor-pointer flex justify-between hover:bg-yellow-50"><span class="font-bold">{{ u.name }}</span><button @click.stop="deleteUser(u)" class="text-red-500 font-bold px-2">🗑️</button></div></div><div class="border-t-2 border-black pt-3"><div v-if="!isAddingUser"><button @click="isAddingUser=true" class="w-full pixel-btn bg-black text-white py-2 text-sm">+ 新用户</button></div><div v-else class="flex gap-2"><input v-model="newUserName" placeholder="名字" class="flex-1 p-2 border-2 border-black"><button @click="addNewUser" class="pixel-btn green px-3 text-xs">OK</button></div></div><button @click="showUserModal=false" class="mt-3 w-full text-xs">关闭</button></div></div>
</div>{% endraw %}<script src="/static/js/diet.js"></script>{% endblock %}''',

    "templates/cook.html": '''{% extends "base.html" %}
{% block content %}
{% raw %}
<div id="app" v-cloak class="h-full flex flex-col md:flex-row gap-6">
<div class="w-full md:w-96 flex flex-col gap-4"><div class="pixel-box p-2 flex gap-2"><button @click="view='search'" class="flex-1 pixel-btn py-2 text-sm" :class="{'bg-yellow-200':view!='search'}">📖 图鉴</button><button @click="view='pantry'" class="flex-1 pixel-btn py-2 text-sm" :class="{'bg-yellow-200':view!='pantry'}">🔨 合成台</button></div>
<div v-if="view=='search'" class="pixel-box flex-1 flex flex-col p-4 min-h-[400px]"><input v-model="searchQ" @input="doSearch" placeholder="输入关键字..." class="w-full p-2 mb-4 text-sm border-2 border-black"><div class="flex-1 overflow-y-auto space-y-2"><div v-for="d in searchList" @click="loadDish(d.name)" class="border-2 border-dashed border-gray-300 p-2 cursor-pointer hover:bg-yellow-50"><div>{{ d.name }}</div><div class="text-xs text-gray-400 mt-1"><span v-for="t in parseTags(d.tags)" class="mr-1">#{{t}}</span></div></div></div></div>
<div v-else class="pixel-box flex-1 flex flex-col p-4 items-center bg-gray-200 min-h-[400px]"><p class="text-xs mb-2 font-bold text-gray-500">放入食材:</p><div class="grid grid-cols-3 gap-1 bg-gray-400 p-1 border-4 border-gray-500 mb-4"><div v-for="i in 9" class="w-12 h-12 bg-gray-300 border-t-2 border-l-2 border-gray-500"></div></div><input v-model="myIngs" @keyup.enter="doPantry" placeholder="食材(逗号隔开)" class="w-full p-2 mb-2 border-2 border-black text-center"><button @click="doPantry" class="pixel-btn green w-full py-3 text-lg">CRAFT!</button><div class="w-full mt-4 flex-1 overflow-y-auto space-y-2"><div v-for="d in pantryList" @click="loadDish(d.name)" class="bg-white border-2 border-black p-2 cursor-pointer flex justify-between hover:bg-green-50"><span>{{ d.name }}</span><span class="text-green-600 font-bold">{{ d.score }}%</span></div></div></div></div>
<div class="flex-1 pixel-box p-6 bg-[#fffaf0] relative flex flex-col"><div v-if="curDish.name" class="flex-1 overflow-y-auto"><div class="border-b-4 border-dashed border-gray-300 pb-4 mb-4 flex justify-between items-start"><div><h1 class="text-4xl mb-2 text-[#5a3e1b]">{{ curDish.name }}</h1><div class="flex gap-2"><span class="bg-red-500 text-white px-2 text-xs border-2 border-black">HP +{{ curDish.calories }}</span></div></div><button @click="genToken" class="pixel-btn text-xs px-2">口令</button></div><div class="prose prose-stone max-w-none font-sans" v-html="curDish.html"></div></div><div v-else class="h-full flex flex-col items-center justify-center opacity-30"><div class="text-8xl">📖</div></div>
<div v-if="curDish.name" class="absolute bottom-4 right-4"><div v-if="showChat" class="pixel-box w-72 h-80 mb-2 flex flex-col text-sm"><div class="bg-blue-500 text-white p-2 font-bold flex justify-between"><span>Chef Bot</span><span @click="showChat=false">x</span></div><div class="flex-1 p-2 overflow-y-auto bg-white"><div v-for="m in chatLog" class="mb-2 p-2 border-2 border-black" :class="m.role=='ai'?'bg-gray-100':'bg-blue-100 text-right'">{{ m.msg }}</div></div><input v-model="chatInput" @keyup.enter="sendChat" class="p-2 border-t-2 border-black" placeholder="Ask..."></div><button @click="showChat=!showChat" class="pixel-btn blue w-12 h-12 rounded-full text-xl">?</button></div></div>
</div>{% endraw %}<script src="/static/js/cook.js"></script>{% endblock %}''',

    "static/js/diet.js": '''const { createApp, reactive, toRefs, computed, onMounted } = Vue;
const app = createApp({
    setup() {
        const getTodayStr = () => new Date().toISOString().split('T')[0];
        const getMealCategory = () => { const h = new Date().getHours(); return h<10?'早餐':h<14?'午餐':h<17?'加餐':h<21?'晚餐':'加餐'; };
        const state = reactive({ currentUserId: parseInt(localStorage.getItem('fitlife_uid')||1), currentDate: getTodayStr(), userList: [], dashboard: {food_today:0,current_weight:0,history:[]}, profile: {name:'',height:170,gender:'male',age:25,target:60}, searchQuery: '', searchResults: [], modal: {show:false,type:'food',inputVal:'',note:'',isSmart:false,unitCal:0,emoji:'',category:'早餐'}, showProfileModal:false, profileForm:{}, showUserModal:false, isAddingUser:false, newUserName:'', tokenInput:'', chartInstance:null });
        
        const handleUpload = async (file, endpoint) => {
            if(!file) return;
            state.modal = {show:true, note:'🤖 AI Analyzing...', inputVal:0, emoji:'⏳'};
            const fd = new FormData(); fd.append('photo', file); fd.append('user_id', state.currentUserId);
            try {
                const res = await axios.post(endpoint, fd, {headers:{'Content-Type':'multipart/form-data'}});
                const r = res.data;
                if(Array.isArray(r) && r.length>0) { state.modal = {show:true, type:'food', note:r[0].name, inputVal:r[0].cal, isSmart:true, unitCal:0, emoji:'🍱', category:getMealCategory()}; }
                else if(r.data) { alert(`✅ 分析成功!\n体重: ${r.data['体重']}\n建议: ${r.advice}`); state.modal.show=false; loadData(); }
                else { alert("AI 未能识别"); state.modal.show=false; }
            } catch(e) { alert("Error"); state.modal.show=false; }
        };
        const uploadPhoto = (e) => handleUpload(e.target.files[0], '/api/diet/analyze_food_photo');
        const uploadBodyReport = (e) => handleUpload(e.target.files[0], '/api/diet/analyze_body_photo');
        const parseToken = () => { const m = (state.tokenInput||state.searchQuery).match(/^#HTC:(.+):(\d+(?:\.\d+)?)#$/); if(m){ state.modal={show:true,type:'food',isSmart:true,note:m[1],inputVal:parseFloat(m[2]),unitCal:0,emoji:'🍳',category:getMealCategory()}; state.tokenInput=''; state.searchQuery=''; } else alert("无效口令"); };
        
        const loadUsers = async () => { state.userList = (await axios.get('/api/get_users')).data; };
        const loadData = async () => { try { const res = await axios.get(`/api/get_dashboard?user_id=${state.currentUserId}&date=${state.currentDate}`); state.dashboard=res.data.data; state.profile=res.data.profile; if(!state.dashboard.current_weight) state.showProfileModal=true; loadChart(); } catch(e){ if(e.response&&e.response.status==404){ await loadUsers(); if(state.userList.length>0) switchUser(state.userList[0].id); else { state.showUserModal=true; state.isAddingUser=true; } } } };
        const loadChart = async () => { const {dates,values}=(await axios.get(`/api/get_chart_data?user_id=${state.currentUserId}`)).data; if(!state.chartInstance) state.chartInstance=echarts.init(document.getElementById('mainChart')); state.chartInstance.setOption({tooltip:{trigger:'axis'}, grid:{top:10,bottom:20,left:30,right:10}, xAxis:{type:'category',data:dates.map(d=>d.slice(5))}, yAxis:{type:'value',splitLine:{lineStyle:{type:'dashed'}}}, series:[{data:values,type:'line',smooth:true,itemStyle:{color:'#10b981'}}]}); };
        const switchUser = (id) => { state.currentUserId=id; localStorage.setItem('fitlife_uid',id); state.showUserModal=false; loadData(); };
        const addNewUser = async () => { if(!state.newUserName) return; await axios.post('/api/create_user', {name:state.newUserName}); await loadUsers(); state.isAddingUser=false; };
        const deleteUser = async (u) => { if(confirm('Del?')) { await axios.post('/api/delete_user', {id:u.id}); await loadUsers(); if(u.id==state.currentUserId) location.reload(); } };
        const submitLog = async () => { await axios.post('/api/add', { user_id:state.currentUserId, date:state.currentDate, type:state.modal.type, category:state.modal.category, value:parseFloat(state.modal.inputVal), note:state.modal.note }); state.modal.show=false; loadData(); };
        const deleteLog = async (id) => { if(confirm('Del?')) { await axios.post('/api/delete_log', {id}); loadData(); } };
        const saveProfile = async () => { await axios.post('/api/save_profile', {...state.profileForm, user_id:state.currentUserId}); await axios.post('/api/add', {user_id:state.currentUserId, date:state.currentDate, type:'weight', value:state.profileForm.current_weight_input, note:'Init'}); state.showProfileModal=false; loadData(); };
        const doSearch = async () => { if(!state.searchQuery) {state.searchResults=[]; return;} const res = await axios.get(`/api/search_food?q=${state.searchQuery}`); state.searchResults=res.data; };
        const selectFood = (i) => { state.modal={show:true,type:'food',isSmart:true,unitCal:i.cal,note:i.name,inputVal:'',emoji:i.emoji,category:getMealCategory()}; state.searchResults=[]; state.searchQuery=''; };
        const openModal = (t) => { state.modal={show:true,type:t,isSmart:false,inputVal:'',note:'',unitCal:0,category:getMealCategory()}; };
        
        onMounted(async () => { await loadUsers(); await loadData(); const q=sessionStorage.getItem('quick_log_food'); if(q){ state.modal={show:true,type:'food',note:q,inputVal:'',isSmart:false,category:getMealCategory()}; sessionStorage.removeItem('quick_log_food'); } });
        return { ...toRefs(state), uploadPhoto, uploadBodyReport, parseToken, submitLog, deleteLog, saveProfile, switchUser, addNewUser, deleteUser, onDateChange, doSearch, selectFood, openModal };
    }
}); app.mount('#app');''',

    "static/js/cook.js": '''const { createApp, reactive, toRefs } = Vue;
const app = createApp({
    setup() {
        const state = reactive({ view:'search', searchQ:'', searchList:[], myIngs:'', pantryList:[], curDish:{}, showChat:false, chatInput:'', chatLog:[{role:'ai',msg:'我是AI帮厨，请问！'}] });
        const doSearch = async () => { if(!state.searchQ) return; state.searchList = (await axios.get(`/api/cook/search?q=${state.searchQ}`)).data; };
        const doPantry = async () => { if(!state.myIngs) return; state.pantryList = (await axios.get(`/api/cook/pantry?ingredients=${state.myIngs}`)).data; };
        const loadDish = async (name) => {
            const res = await axios.get(`/api/cook/detail?name=${name}`);
            let html = res.data.html.replace(/src="\.\//g, `src="/data/HowToCook/dishes/${res.data.category}/`);
            state.curDish = res.data; state.curDish.html = html;
            if(window.innerWidth<768) state.view='detail';
        };
        const genToken = async () => { const res = await axios.post('/api/cook/token', {name:state.curDish.name, cal:state.curDish.calories}); prompt("Copy Token:", res.data.token); };
        const sendChat = async () => {
            if(!state.chatInput) return; const q=state.chatInput; state.chatLog.push({role:'user',msg:q}); state.chatInput='';
            try { const res = await axios.post('/api/cook/ask_chef', {recipe:state.curDish.name, question:q}); state.chatLog.push({role:'ai',msg:res.data.answer}); } 
            catch(e) { state.chatLog.push({role:'ai',msg:'Network Error'}); }
        };
        const parseTags = (s) => { try { return JSON.parse(s); } catch { return []; } };
        return { ...toRefs(state), doSearch, doPantry, loadDish, genToken, sendChat, parseTags };
    }
}); app.mount('#app');'''
}

# 执行写入
print("🚀 开始自动修复所有文件...")

for path, content in FILES.items():
    full_path = os.path.join(BASE_DIR, path)
    
    # 确保目录存在
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    # 写入文件 (强制覆盖)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ 已修复: {path}")

print("\n✨ 全部修复完成！")
print("👉 请立即重启 python run.py")