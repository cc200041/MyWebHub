import sys
import os  # ✅ 补上了这一行

# 将当前目录加入系统路径，确保能找到 core 模块
sys.path.append(os.getcwd())

try:
    from core.ai import chat_with_text
    print("🔍 正在测试 AI 连接 (使用 core/ai.py 配置)...")
    
    # 发送测试请求
    response = chat_with_text("你好，这是一次连接测试。请回复：连接成功！")
    
    print(f"\n🤖 AI 回复:\n{'-'*20}\n{response}\n{'-'*20}")

    if "失败" in response or "错误" in response:
        print("❌ 测试失败：请检查 core/ai.py 里的 PROXY_URL (端口是否7897) 和 API_KEY")
    else:
        print("✅ 测试成功！AI 模块工作正常。")
        print("👉 现在您可以运行 python run.py，去网页里使用【AI帮厨】和【拍照识别】了！")

except ImportError:
    print("❌ 错误：找不到 core.ai 模块。请确保 test_ai.py 文件在 MyWebHub 根目录下。")
except Exception as e:
    print(f"❌ 发生未知错误: {e}")