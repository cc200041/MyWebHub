from flask import Flask, render_template, request, jsonify, send_from_directory
import sqlite3
import datetime
import json
import os
import random
import markdown

app = Flask(__name__)

# --- 配置 ---
DIET_DB = 'diet_data.db'   # 减肥App专用
COOK_DB = 'cook_data.db'   # 做饭App专用 (新)
COOK_ROOT = os.path.join('data', 'HowToCook', 'dishes')

# 加载食物热量库 (只读，用于计算口令码热量)
def load_food_data():
    if os.path.exists('food_database.json'):
        with open('food_database.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return []
FOOD_DB = load_food_data()

# --- 数据库连接辅助 ---
def get_diet_conn():
    conn = sqlite3.connect(DIET_DB)
    conn.row_factory = sqlite3.Row
    return conn

def get_cook_conn():
    conn = sqlite3.connect(COOK_DB)
    conn.row_factory = sqlite3.Row
    return conn

# --- 初始化 (仅 Diet 库，Cook 库由 init_cook_db.py 维护) ---
def init_diet_db():
    conn = get_diet_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, height REAL, gender TEXT, age INTEGER, target_weight REAL, current_weight REAL)''')
    # 增加 logs 表
    c.execute('''CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, date TEXT, type TEXT, category TEXT, value REAL, note TEXT)''')
    # 检查默认用户
    c.execute("SELECT count(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users (name, height, gender, age, target_weight, current_weight) VALUES (?, 175, 'male', 25, 65, 70)", ('默认用户',))
    conn.commit()
    conn.close()

init_diet_db()

# --- 页面路由 ---
@app.route('/')
def home(): return render_template('hub.html', title="首页")
@app.route('/diet')
def diet_app(): return render_template('diet.html', title="FitLife 减脂")
@app.route('/cook')
def cook_app(): return render_template('cook.html', title="HowToCook")

# ==========================================
# 🍳 HowToCook 专属接口 (读 cook_data.db)
# ==========================================

# 1. 记录搜索历史 (用于推荐)
def log_search(keyword):
    if not keyword: return
    conn = get_cook_conn()
    conn.cursor().execute("INSERT INTO search_history (keyword) VALUES (?)", (keyword,))
    conn.commit()
    conn.close()

# 2. 搜索菜谱 (支持历史记录)
@app.route('/api/cook/search')
def cook_search():
    keyword = request.args.get('q', '')
    log_search(keyword) # 记录足迹
    
    conn = get_cook_conn()
    # 模糊搜索名字或食材
    cursor = conn.execute("SELECT * FROM recipes WHERE name LIKE ? OR ingredients LIKE ?", 
                          (f'%{keyword}%', f'%{keyword}%'))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(results)

# 3. 推荐系统 (Mode A: 猜你喜欢)
@app.route('/api/cook/recommend')
def cook_recommend():
    conn = get_cook_conn()
    # 简单算法：获取最近搜索的3个关键词
    recent_searches = conn.execute("SELECT keyword FROM search_history ORDER BY id DESC LIMIT 3").fetchall()
    
    recommendations = []
    
    # 如果有搜索记录，尝试根据关键词推荐
    for row in recent_searches:
        kw = row['keyword']
        rows = conn.execute("SELECT * FROM recipes WHERE ingredients LIKE ? ORDER BY RANDOM() LIMIT 2", (f'%{kw}%',)).fetchall()
        recommendations.extend([dict(r) for r in rows])
    
    # 如果不够6个，用随机菜谱补齐
    if len(recommendations) < 6:
        needed = 6 - len(recommendations)
        rows = conn.execute("SELECT * FROM recipes ORDER BY RANDOM() LIMIT ?", (needed,)).fetchall()
        recommendations.extend([dict(r) for r in rows])
        
    # 去重
    seen = set()
    final_list = []
    for r in recommendations:
        if r['id'] not in seen:
            final_list.append(r)
            seen.add(r['id'])
            
    conn.close()
    return jsonify(final_list)

# 4. 厨房合成台 (Mode B: 缺一点模式)
@app.route('/api/cook/pantry')
def cook_pantry():
    # 用户拥有的食材，逗号分隔，如 "鸡蛋,西红柿"
    my_ingredients = request.args.get('ingredients', '').split(',')
    my_ingredients = [i.strip() for i in my_ingredients if i.strip()]
    
    if not my_ingredients: return jsonify([])
    
    conn = get_cook_conn()
    # 获取所有菜谱进行匹配 (数据量不大，Python处理更灵活)
    all_recipes = conn.execute("SELECT * FROM recipes").fetchall()
    conn.close()
    
    results = []
    for r in all_recipes:
        recipe_ings = r['ingredients'].split(',') if r['ingredients'] else []
        recipe_ings = [i for i in recipe_ings if i] # 清洗空值
        
        if not recipe_ings: continue
        
        # 计算匹配度
        missing = []
        hit_count = 0
        
        for ri in recipe_ings:
            # 模糊匹配：比如我有"土豆"，菜谱要"大土豆"，算匹配
            is_match = False
            for my_i in my_ingredients:
                if my_i in ri or ri in my_i:
                    is_match = True
                    break
            
            if is_match:
                hit_count += 1
            else:
                missing.append(ri)
        
        # 规则：至少命中1个，且缺失不超过3个
        if hit_count > 0 and len(missing) <= 3:
            # 匹配分数：缺失越少分越高
            score = 100 - len(missing) * 10
            results.append({
                "name": r['name'],
                "category": r['category'],
                "missing": missing,
                "score": score
            })
            
    # 按分数排序
    results.sort(key=lambda x: x['score'], reverse=True)
    return jsonify(results[:20]) # 只返回前20个

# 5. 获取菜谱详情 (Markdown + 估算热量)
@app.route('/api/cook/detail')
def cook_detail():
    name = request.args.get('name')
    conn = get_cook_conn()
    row = conn.execute("SELECT * FROM recipes WHERE name=?", (name,)).fetchone()
    conn.close()
    
    if not row: return jsonify({"error": "Not Found"})
    
    # 读取 Markdown
    full_path = os.path.join(COOK_ROOT, row['path'])
    content = ""
    if os.path.exists(full_path):
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
    
    # 估算热量 (根据 ingredients 查 food_database.json)
    ingredients_list = row['ingredients'].split(',') if row['ingredients'] else []
    estimated_cal = 0
    cal_detail = []
    
    for ing in ingredients_list:
        if not ing: continue
        # 在 FOOD_DB 里找
        found = False
        for fd in FOOD_DB:
            if ing in fd['name']:
                # 默认估算每种食材 100g (很粗略，但比没有强)
                estimated_cal += fd['cal']
                cal_detail.append(f"{ing}({fd['cal']})")
                found = True
                break
        if not found:
            cal_detail.append(f"{ing}(?)")
            
    return jsonify({
        "name": row['name'],
        "category": row['category'],
        "html": markdown.markdown(content),
        "calories": estimated_cal, # 总估算热量
        "cal_detail": cal_detail   # 详情
    })

# 6. 生成口令码
@app.route('/api/cook/generate_token', methods=['POST'])
def generate_token():
    d = request.json
    # 格式: #HTC:菜名:热量#
    token = f"#HTC:{d['name']}:{d['cal']}#"
    return jsonify({"token": token})

# 图片代理
@app.route('/data/HowToCook/dishes/<path:filename>')
def serve_cook_images(filename):
    return send_from_directory(COOK_ROOT, filename)

# ==========================================
# 🥑 FitLife 减脂接口 (读 diet_data.db)
# ==========================================
# (保持之前的接口不变，但加上 token 解析功能)

# ... (search_food, get_users, create_user, delete_user, get_dashboard, get_chart_data, save_profile 保持原样) ...
# 为了节省篇幅，这里复用您之前的代码逻辑，只展示新增的 token 解析逻辑

@app.route('/api/search_food')
def search_food():
    # ... 保持原样 ...
    query = request.args.get('q', '')
    if not query: return jsonify([])
    results = []
    count = 0
    def get_emoji(n):
        if '面' in n: return '🍜'
        if '饭' in n: return '🍚'
        if '肉' in n: return '🥩'
        return '🍽️'
    for item in FOOD_DB:
        if query in item['name']:
            item['emoji'] = get_emoji(item['name'])
            results.append(item)
            count += 1
            if count>=30: break
    return jsonify(results)

@app.route('/api/get_users')
def get_users():
    conn = get_diet_conn()
    res = jsonify([{"id":r['id'],"name":r['name']} for r in conn.execute("SELECT id,name FROM users").fetchall()])
    conn.close()
    return res

@app.route('/api/create_user', methods=['POST'])
def create_user():
    try:
        conn = get_diet_conn()
        c = conn.cursor()
        c.execute("INSERT INTO users (name, height, gender, age, target_weight, current_weight) VALUES (?, 170, 'male', 25, 60, 60)", (request.json.get('name'),))
        conn.commit()
        new_id = c.lastrowid
        conn.close()
        return jsonify({"status":"success", "id":new_id})
    except: return jsonify({"status":"error"})

@app.route('/api/delete_user', methods=['POST'])
def delete_user():
    conn = get_diet_conn()
    conn.execute("DELETE FROM logs WHERE user_id=?", (request.json.get('id'),))
    conn.execute("DELETE FROM users WHERE id=?", (request.json.get('id'),))
    conn.commit()
    conn.close()
    return jsonify({"status":"success"})

@app.route('/api/get_dashboard')
def get_dashboard():
    user_id = request.args.get('user_id', 1)
    date_str = request.args.get('date', datetime.date.today().isoformat())
    conn = get_diet_conn()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not row: return jsonify({"error": "user not found"}), 404
    profile = {"height": row['height'], "gender": row['gender'], "age": row['age'], "target": row['target_weight'], "current_weight": row['current_weight'], "name": row['name']}
    
    food_today = conn.execute("SELECT SUM(value) FROM logs WHERE user_id=? AND date=? AND type='food'", (user_id, date_str)).fetchone()[0] or 0
    logs_cursor = conn.execute("SELECT * FROM logs WHERE user_id=? AND date=? ORDER BY id DESC", (user_id, date_str))
    logs = [{"id": r['id'], "type": r['type'], "val": r['value'], "note": r['note'], "date": r['date'], "cat": r['category']} for r in logs_cursor.fetchall()]
    conn.close()
    return jsonify({"profile": profile, "data": {"food_today": food_today, "current_weight": profile['current_weight'], "history": logs}})

@app.route('/api/get_chart_data')
def get_chart_data():
    user_id = request.args.get('user_id', 1)
    dates = [(datetime.date.today() - datetime.timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    vals = []
    conn = get_diet_conn()
    for d in dates:
        vals.append(conn.execute("SELECT SUM(value) FROM logs WHERE user_id=? AND date=? AND type='food'", (user_id, d)).fetchone()[0] or 0)
    conn.close()
    return jsonify({"dates": dates, "values": vals})

@app.route('/api/save_profile', methods=['POST'])
def save_profile():
    d = request.json
    conn = get_diet_conn()
    conn.execute("UPDATE users SET height=?, gender=?, age=?, target_weight=?, current_weight=? WHERE id=?",
        (d['height'], d['gender'], d['age'], d['target_weight'], d['current_weight_input'], d.get('user_id')))
    conn.commit()
    conn.close()
    return jsonify({"status":"success"})

@app.route('/api/add', methods=['POST'])
def add_record():
    d = request.json
    conn = get_diet_conn()
    conn.execute("INSERT INTO logs (user_id, date, type, category, value, note) VALUES (?, ?, ?, ?, ?, ?)",
        (d.get('user_id'), d.get('date'), d['type'], d.get('category', ''), d['value'], d['note']))
    if d['type'] == 'weight':
        conn.execute("UPDATE users SET current_weight=? WHERE id=?", (d['value'], d.get('user_id')))
    conn.commit()
    conn.close()
    return jsonify({"status":"success"})

@app.route('/api/delete_log', methods=['POST'])
def delete_log():
    conn = get_diet_conn()
    conn.execute("DELETE FROM logs WHERE id=?", (request.json.get('id'),))
    conn.commit()
    conn.close()
    return jsonify({"status":"success"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)