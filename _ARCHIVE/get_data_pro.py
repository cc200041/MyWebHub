import requests
import pandas as pd
import json
import os
import re
import time

# --- 配置区域 (每次运行前可以在这里改) ---
OFF_START_PAGE = 50      # 从第几页开始抓？(上次抓了前5页，这次可以填6)
OFF_PAGES_COUNT = 100    # 这次要新抓多少页？
SKIP_TFND = True        # 是否跳过台湾官方库？(如果之前抓过了，填 True 可以省时间)

# ------------------------------------
TFND_URL = "https://consumer.fda.gov.tw/uc/GetFile.ashx?id=4862259227103213368&type=ServerFile"
OFF_API = "https://world.openfoodfacts.org/cgi/search.pl"
DB_FILE = "food_database.json"

try:
    import opencc
    converter = opencc.OpenCC('t2s')
    HAS_OPENCC = True
except:
    HAS_OPENCC = False

def clean_name(name):
    if pd.isna(name): return ""
    name = str(name).strip()
    if HAS_OPENCC: name = converter.convert(name)
    return name

# 1. 读取现有数据
def load_existing_data():
    if os.path.exists(DB_FILE):
        print(f"📂 读取现有数据库: {DB_FILE} ...")
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"   - 已加载 {len(data)} 条旧数据。")
                return data
        except:
            print("   - 读取失败或文件为空，将创建新库。")
            return []
    else:
        print("   - 文件不存在，将创建新库。")
        return []

# 2. 抓取 OpenFoodFacts (支持指定页码)
def fetch_openfoodfacts(start_page, pages_count):
    print(f"🌍 开始抓取 OpenFoodFacts (第 {start_page} 页 -> 第 {start_page + pages_count - 1} 页)...")
    foods = []
    
    for p in range(start_page, start_page + pages_count):
        try:
            print(f"   - 正在下载第 {p} 页...")
            params = {
                "action": "process", "tagtype_0": "countries", "tag_contains_0": "contains",
                "tag_0": "china", "sort_by": "popularity", "page_size": 100, "page": p, "json": 1
            }
            headers = {'User-Agent': 'FitLifeApp/1.0'}
            resp = requests.get(OFF_API, params=params, headers=headers, timeout=10)
            data = resp.json()
            
            for product in data.get('products', []):
                name = product.get('product_name_zh', '') or product.get('product_name', '')
                if not name: continue
                
                nutriments = product.get('nutriments', {})
                cal = nutriments.get('energy-kcal_100g')
                if cal is None:
                    kj = nutriments.get('energy-kj_100g')
                    if kj: cal = float(kj) / 4.184
                
                if cal is not None:
                    foods.append({"name": clean_name(name), "cal": int(cal)})
            
            time.sleep(1) # 休息一下防封号
            
        except Exception as e:
            print(f"   ⚠️ 第 {p} 页失败: {e}")
            
    print(f"✅ OpenFoodFacts 新增抓取 {len(foods)} 条。")
    return foods

# 3. 抓取 TFND (同前，略微简化)
def fetch_tfnd():
    print("🥩 正在更新台湾 FDA 基础食材库...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(TFND_URL, headers=headers, timeout=60)
        with open("temp_tfnd.xls", "wb") as f: f.write(resp.content)
        
        # 简单找表头逻辑
        temp_df = pd.read_excel("temp_tfnd.xls", header=None, nrows=10)
        header_row = 0
        for i, row in temp_df.iterrows():
            if "樣品名稱" in str(row.values) or "Name" in str(row.values):
                header_row = i; break
        
        df = pd.read_excel("temp_tfnd.xls", header=header_row)
        cols = df.columns.astype(str)
        name_col = next((c for c in cols if "名稱" in c or "Name" in c), None)
        cal_col = next((c for c in cols if "kcal" in str(c).lower() or "熱量" in str(c)), None)
        
        foods = []
        if name_col and cal_col:
            for _, row in df.iterrows():
                try:
                    name = str(row[name_col]).strip()
                    cal = row[cal_col]
                    if pd.isna(cal) or str(cal) == '-': continue
                    cal_val = float(re.search(r"(\d+\.?\d*)", str(cal)).group(1))
                    foods.append({"name": clean_name(name), "cal": int(round(cal_val))})
                except: continue
        
        if os.path.exists("temp_tfnd.xls"): os.remove("temp_tfnd.xls")
        print(f"✅ TFND 更新完成，共 {len(foods)} 条。")
        return foods
    except Exception as e:
        print(f"⚠️ TFND 更新失败: {e}")
        return []

if __name__ == "__main__":
    # 1. 拿旧数据
    existing_data = load_existing_data()
    
    # 2. 拿新数据
    new_data_off = fetch_openfoodfacts(start_page=OFF_START_PAGE, pages_count=OFF_PAGES_COUNT)
    
    new_data_tfnd = []
    if not SKIP_TFND:
        new_data_tfnd = fetch_tfnd()
    else:
        print("⏭️  跳过 TFND 更新 (使用配置 SKIP_TFND=True)")

    # 3. 合并与去重 (核心逻辑)
    print("🔄 正在合并数据...")
    # 使用字典去重：key是名字，value是整条数据
    # 逻辑：旧数据 < TFND < OpenFoodFacts (后来的覆盖先来的)
    unique_map = {}
    
    # 先放旧数据
    for item in existing_data:
        unique_map[item['name']] = item
        
    # 再放 TFND (如果名字一样，更新热量)
    for item in new_data_tfnd:
        unique_map[item['name']] = item
        
    # 再放 OpenFoodFacts
    for item in new_data_off:
        unique_map[item['name']] = item
        
    final_list = list(unique_map.values())
    
    # 4. 保存
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(final_list, f, ensure_ascii=False, indent=2)
        
    print(f"\n🎉 更新完毕！")
    print(f"📊 更新前: {len(existing_data)} 条")
    print(f"📈 更新后: {len(final_list)} 条 (净增 {len(final_list) - len(existing_data)} 条)")