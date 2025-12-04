import os

# ========== API Key ==========

# 通义千问的 Key，推荐只用这个
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")

# ========== 数据与文件路径 ==========

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# 减脂 & 做饭两个数据库
DB_DIET = os.path.join(DATA_DIR, "diet_data.db")
DB_COOK = os.path.join(DATA_DIR, "cook_data.db")

# HowToCook 菜谱根目录
COOK_ROOT = os.path.join(DATA_DIR, "HowToCook", "dishes")

# 食物热量 JSON
FOOD_JSON = os.path.join(DATA_DIR, "food_database.json")
