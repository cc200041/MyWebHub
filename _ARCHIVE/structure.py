import os
import shutil

def create_structure():
    base_dir = os.getcwd() # 获取当前目录
    print(f"📂 正在重构目录: {base_dir}")

    # 1. 需要创建的文件夹列表
    dirs = [
        "core",
        "apps",
        os.path.join("static", "js") # 确保这个路径存在
    ]

    for d in dirs:
        path = os.path.join(base_dir, d)
        if not os.path.exists(path):
            os.makedirs(path)
            print(f"   ✅ 创建文件夹: {d}")

    # 2. 移动和重命名文件
    # 将 static/js/main.js -> static/js/diet.js
    old_js = os.path.join(base_dir, "static", "js", "main.js")
    new_js = os.path.join(base_dir, "static", "js", "diet.js")
    
    if os.path.exists(old_js):
        if not os.path.exists(new_js):
            shutil.move(old_js, new_js)
            print(f"   ✅ 移动并重命名: main.js -> diet.js")
        else:
            print(f"   ℹ️ diet.js 已存在，跳过移动")

    # 3. 备份旧 app.py
    app_py = os.path.join(base_dir, "app.py")
    backup_py = os.path.join(base_dir, "app_old_backup.py")
    
    if os.path.exists(app_py):
        shutil.copy(app_py, backup_py)
        print(f"   ✅ 备份旧代码: app.py -> app_old_backup.py")

    # 4. 创建所有需要的空文件 (占位符)
    new_files = [
        "run.py",
        "config.py",
        "ai_clean_db.py",
        os.path.join("core", "ai.py"),
        os.path.join("core", "db.py"),
        os.path.join("core", "__init__.py"),
        os.path.join("apps", "diet.py"),
        os.path.join("apps", "cook.py"),
        os.path.join("apps", "__init__.py"),
        os.path.join("static", "js", "cook.js")
    ]

    for f in new_files:
        path = os.path.join(base_dir, f)
        if not os.path.exists(path):
            with open(path, 'w', encoding='utf-8') as file:
                file.write("# 占位文件，请填入代码\n")
            print(f"   ✅ 创建新文件: {f}")
        else:
            print(f"   ℹ️ 文件已存在: {f}")

    print("\n🎉 重构完成！现在的结构非常清晰了。")
    print("👉 下一步：请按照之前的指示，把代码分别填入这些新文件里。")

if __name__ == "__main__":
    create_structure()