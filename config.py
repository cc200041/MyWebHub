import os

# ========== API Key ==========

# 从环境变量里拿 key，这样本地和 Render 都能共用同一套代码
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
# 优先用 QWEN_API_KEY，如果没设置，就回退到 GOOGLE_API_KEY
QWEN_API_KEY = os.getenv("QWEN_API_KEY", GOOGLE_API_KEY)

# ========== 数据与文件路径 ==========

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

DB_DIET = os.path.join(DATA_DIR, 'diet_data.db')
DB_COOK = os.path.join(DATA_DIR, 'cook_data.db')

# HowToCook 菜谱根目录
COOK_ROOT = os.path.join(DATA_DIR, 'HowToCook', 'dishes')

# 食物热量 JSON
FOOD_JSON = os.path.join(DATA_DIR, 'food_database.json')
