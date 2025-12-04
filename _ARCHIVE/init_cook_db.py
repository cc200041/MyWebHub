import sqlite3
import os
import re

# --- 配置 ---
COOK_ROOT = os.path.join('data', 'HowToCook', 'dishes')
DB_PATH = 'cook_data.db'  # 这是做饭App专用的数据库，和减肥App分开

def init_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH) # 为了保证数据最新，每次重建
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. 菜谱索引表
    c.execute('''CREATE TABLE recipes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        category TEXT,
        path TEXT,
        ingredients TEXT  -- 存成字符串，如 "土豆,牛肉,葱"
    )''')
    
    # 2. 搜索历史表 (用于大数据推荐)
    c.execute('''CREATE TABLE search_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword TEXT,
        search_time DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # 3. 收藏表 (从减肥库迁移过来，或者新建)
    c.execute('''CREATE TABLE favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipe_name TEXT
    )''')
    
    conn.commit()
    return conn

def parse_ingredients(content):
    """
    尝试从 Markdown 内容中提取食材。
    HowToCook 的格式不统一，这里用启发式规则提取。
    """
    ingredients = []
    # 策略1：寻找“## 必备原料”或类似标题下的列表
    lines = content.split('\n')
    capture = False
    for line in lines:
        line = line.strip()
        if line.startswith('##') and ('原料' in line or '食材' in line or '材料' in line):
            capture = True
            continue
        if line.startswith('##') and capture: # 遇到下一个标题，停止
            break
        
        if capture:
            # 提取列表项，如 "- 土豆：2个" -> "土豆"
            # 过滤掉 "主料" "辅料" 这种词
            if line.startswith('-') or line.startswith('*'):
                raw = line[1:].strip()
                # 去掉冒号后面的量词 (土豆：2个 -> 土豆)
                item = re.split(r'[:：,，\d]', raw)[0].strip()
                if item and len(item) < 10 and item not in ['主料', '辅料', '可选']:
                    ingredients.append(item)
    
    return ",".join(list(set(ingredients))) # 去重并转字符串

def scan_and_import(conn):
    c = conn.cursor()
    count = 0
    print("🚀 开始扫描菜谱...")
    
    for category in os.listdir(COOK_ROOT):
        cat_path = os.path.join(COOK_ROOT, category)
        if os.path.isdir(cat_path) and not category.startswith('.'):
            for file in os.listdir(cat_path):
                if file.endswith('.md') and not file.startswith('README'):
                    name = file.replace('.md', '')
                    path = os.path.join(category, file)
                    
                    # 读取内容提取食材
                    with open(os.path.join(cat_path, file), 'r', encoding='utf-8') as f:
                        content = f.read()
                        ingredients = parse_ingredients(content)
                    
                    c.execute("INSERT INTO recipes (name, category, path, ingredients) VALUES (?, ?, ?, ?)",
                              (name, category, path, ingredients))
                    count += 1
                    print(f"   - 收录: {name} (食材: {ingredients})")
    
    conn.commit()
    print(f"✅ 扫描完成！共收录 {count} 道菜谱到 {DB_PATH}")

if __name__ == "__main__":
    conn = init_db()
    scan_and_import(conn)
    conn.close()