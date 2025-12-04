import os

GOOGLE_API_KEY = "你的 key ..."

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DB_DIET = os.path.join(DATA_DIR, 'diet_data.db')
DB_COOK = os.path.join(DATA_DIR, 'cook_data.db')
COOK_ROOT = os.path.join(DATA_DIR, 'HowToCook', 'dishes')
FOOD_JSON = os.path.join(DATA_DIR, 'food_database.json')

# ✅ 思源笔记服务地址（本机）
SIYUAN_URL = os.environ.get("SIYUAN_URL", "http://127.0.0.1:6806")
