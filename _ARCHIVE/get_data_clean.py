import json
import re
import time
from deep_translator import GoogleTranslator

# --- 配置 ---
DB_FILE = "food_database.json"
BACKUP_FILE = "food_database_backup.json"

# 初始化工具
try:
    import opencc
    cc = opencc.OpenCC('t2s')
    HAS_OPENCC = True
except:
    HAS_OPENCC = False

translator = GoogleTranslator(source='auto', target='zh-CN')

def is_chinese(text):
    """检查是否包含至少一个汉字"""
    return bool(re.search(r'[\u4e00-\u9fa5]', text))

def clean_name(name):
    """清理名称中的奇怪符号"""
    # 去掉多余的空格
    name = str(name).strip()
    # 简繁转换
    if HAS_OPENCC:
        name = cc.convert(name)
    return name

def process_database():
    if not os.path.exists(DB_FILE):
        print("❌ 找不到 food_database.json")
        return

    print("📂 读取现有数据库...")
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 备份一份，怕万一删多了
    with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ 已备份原数据到 {BACKUP_FILE}")

    cleaned_list = []
    removed_count = 0
    translated_count = 0

    print(f"🔍 开始清洗 {len(data)} 条数据 (这可能需要一点时间)...")

    for item in data:
        original_name = item['name']
        name = clean_name(original_name)
        cal = item['cal']

        # 1. 已经是中文的，保留
        if is_chinese(name):
            item['name'] = name
            cleaned_list.append(item)
            continue

        # 2. 全是英文/外文的，尝试翻译
        try:
            # 只有纯字母才翻译，避免翻译乱码
            print(f"   翻译中: {name} ...", end="")
            trans = translator.translate(name)
            
            # 翻译成功且包含中文
            if trans and is_chinese(trans):
                print(f" -> [{trans}] (保留)")
                item['name'] = trans
                cleaned_list.append(item)
                translated_count += 1
                time.sleep(0.5) # 稍微慢点，防止封IP
            else:
                # 翻译完了还不是中文（比如品牌名 Ambpoeial），或者翻译失败 -> 删除！
                print(f" -> 翻译无效，删除 🗑️")
                removed_count += 1
        except Exception as e:
            print(f" -> 翻译出错，删除 🗑️")
            removed_count += 1

    # 3. 保存清洗后的数据
    print("\n💾 正在保存...")
    # 去重
    unique_data = {v['name']: v for v in cleaned_list}.values()
    
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(unique_data), f, ensure_ascii=False, indent=2)

    print("-" * 30)
    print(f"🎉 清洗完成！")
    print(f"📉 原有数据: {len(data)} 条")
    print(f"🗑️ 删除无效/纯英文数据: {removed_count} 条")
    print(f"🔁 成功翻译: {translated_count} 条")
    print(f"✅ 最终剩余: {len(unique_data)} 条高质量数据")

import os
if __name__ == "__main__":
    process_database()