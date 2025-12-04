import sqlite3
import json

conn = sqlite3.connect('data/cook_data.db')
cursor = conn.cursor()

# 随机查 5 道菜，看看它们的食材数据
rows = cursor.execute("SELECT name, structured_ingredients FROM recipes ORDER BY RANDOM() LIMIT 5").fetchall()

print("🔍 数据库抽查：")
for row in rows:
    name, ings = row
    print(f"菜名: {name}")
    print(f"食材数据 (原始): {ings}")
    try:
        print(f"食材列表 (解析): {json.loads(ings)}")
    except:
        print("❌ 解析失败，数据为空或格式错误")
    print("-" * 20)

conn.close()