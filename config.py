import os

# =============== API Key ===============
# 不再把 Key 写死在代码里，而是从环境变量读取：
# - 本地：可以在系统里配置 GOOGLE_API_KEY，或者在运行前 export / set
# - Render：在 Dashboard → Environment 里添加同名变量即可
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

# =============== 路径配置 ===============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# 减肥 & 做饭两个 SQLite 数据库
DB_DIET = os.path.join(DATA_DIR, "diet_data.db")
DB_COOK = os.path.join(DATA_DIR, "cook_data.db")

# HowToCook 图片根目录（现在就算没有也不会影响程序跑）
COOK_ROOT = os.path.join(DATA_DIR, "HowToCook", "dishes")

# 食物热量 JSON 数据库
FOOD_JSON = os.path.join(DATA_DIR, "food_database.json")
