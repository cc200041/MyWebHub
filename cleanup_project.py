import os
import shutil

# 1. 定义【必须保留】的白名单
# 这些是网站运行的核心，绝对不能动
KEEP_FILES = [
    "run.py",           # 新的启动入口
    "config.py",        # 配置文件
    "ai_clean_db.py",   # 清洗数据库脚本 (留着以后更新数据用)
    "cleanup_project.py" # 本脚本
]

KEEP_DIRS = [
    "core",      # 核心逻辑
    "apps",      # 业务逻辑
    "templates", # 页面
    "static",    # JS/CSS
    "data",      # 数据库和菜谱文件
    "_ARCHIVE"   # 归档目录
]

def main():
    base_dir = os.getcwd()
    archive_dir = os.path.join(base_dir, "_ARCHIVE")
    
    # 创建归档目录
    if not os.path.exists(archive_dir):
        os.makedirs(archive_dir)
        print(f"📦 创建归档目录: {archive_dir}")

    print("🧹 开始清理项目目录...")
    
    # 遍历根目录下的所有文件和文件夹
    for item in os.listdir(base_dir):
        # 跳过归档目录本身
        if item == "_ARCHIVE": continue
        
        src_path = os.path.join(base_dir, item)
        dst_path = os.path.join(archive_dir, item)

        # 判断是否在白名单里
        if item in KEEP_FILES or item in KEEP_DIRS:
            print(f"✅ 保留: {item}")
            continue
        
        # 剩下的都是杂物，移走！
        try:
            shutil.move(src_path, dst_path)
            print(f"👋 移入归档: {item}")
        except Exception as e:
            print(f"⚠️ 移动失败 {item}: {e}")

    print("\n✨ 清理完成！")
    print("现在的目录非常干净，只有核心代码。")
    print("旧文件都在 _ARCHIVE 文件夹里，万一需要可以找回。")

if __name__ == "__main__":
    main()