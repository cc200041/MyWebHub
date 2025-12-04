import re
import json
import requests
import pandas as pd
import os

# 尝试导入简繁转换库
try:
    import opencc
    converter = opencc.OpenCC('t2s')
    HAS_OPENCC = True
except ImportError:
    HAS_OPENCC = False
    print("⚠️ 未安装 opencc，将保留繁体中文。")

TFND_PAGE = "https://consumer.fda.gov.tw/Food/TFND.aspx?nodeID=178"
BASE = "https://consumer.fda.gov.tw"

def download_bytes(url):
    print(f"正在下载: {url}...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(url, headers=headers, timeout=60)
    r.raise_for_status()
    return r.content

def find_download_links(html):
    links = set(re.findall(r"/uc/GetFile\.ashx\?id=\d+&type=ServerFile", html))
    return [BASE + x for x in links]

def build_food_db(file_path):
    print("正在寻找表头并清洗数据...")
    
    # --- 关键修复：自动寻找表头所在的行 ---
    # 先不带表头读取前10行
    temp_df = pd.read_excel(file_path, header=None, nrows=10)
    header_row_index = 0
    
    # 遍历前10行，寻找包含 "名称" 字样的行作为表头
    for i, row in temp_df.iterrows():
        row_str = row.astype(str).str.cat(sep=' ')
        if "樣品名稱" in row_str or "食品名稱" in row_str or "Name" in row_str:
            header_row_index = i
            print(f"✅ 在第 {i+1} 行找到了表头！")
            break
            
    # 使用正确的表头行重新读取所有数据
    df = pd.read_excel(file_path, header=header_row_index)
    # ------------------------------------

    cols = df.columns.astype(str)
    
    def pick_col(keywords):
        for k in keywords:
            for c in cols:
                if k in c: return c
        return None

    name_col = pick_col(["樣品名稱", "食品名稱", "品名", "Name"])
    val_col  = pick_col(["每100克含量", "每100g含量", "熱量", "Energy", "kcal"])

    # 暴力查找热量列
    if not val_col:
        for c in cols:
            if "kcal" in c.lower() or "大卡" in c:
                val_col = c
                break
    
    if not (name_col and val_col):
        print(f"❌ 无法识别列名。现有列名: {list(cols)}")
        return []

    out = []
    for index, row in df.iterrows():
        try:
            raw_name = str(row[name_col]).strip()
            raw_val = row[val_col]
            
            if pd.isna(raw_val) or raw_val == '-': continue
            
            val_str = str(raw_val)
            val_clean = re.findall(r"(\d+\.?\d*)", val_str)
            if not val_clean: continue
            
            cal = int(round(float(val_clean[0])))
            
            if HAS_OPENCC:
                final_name = converter.convert(raw_name)
            else:
                final_name = raw_name

            out.append({"name": final_name, "cal": cal})
        except:
            continue
            
    return out

def main():
    try:
        print("正在连接官方数据库...")
        html = requests.get(TFND_PAGE, timeout=30).text
        links = find_download_links(html)
        
        target_url = links[0] if links else "https://consumer.fda.gov.tw/uc/GetFile.ashx?id=4862259227103213368&type=ServerFile"

        content = download_bytes(target_url)
        with open("temp.xls", "wb") as f:
            f.write(content)

        # 传入文件路径而不是 dataframe
        foods = build_food_db("temp.xls")
        
        if foods:
            with open("food_database.json", "w", encoding="utf-8") as f:
                json.dump(foods, f, ensure_ascii=False, indent=2)
            print(f"\n✅ 成功！已生成 {len(foods)} 条【简体中文】官方数据！")
            print("请重启 app.py 生效。")
        else:
            print("❌ 数据提取失败")

        if os.path.exists("temp.xls"): os.remove("temp.xls")

    except Exception as e:
        print(f"❌ 发生错误: {e}")

if __name__ == "__main__":
    main()