# run.py
from flask import Flask, render_template
import config

from apps.diet import diet_bp
from apps.cook import cook_bp

app = Flask(__name__)
app.register_blueprint(diet_bp)
app.register_blueprint(cook_bp)


@app.route("/")
def home():
    return render_template("hub.html", title="AI Personal Hub")


@app.route("/diet")
def diet_page():
    return render_template("diet.html", title="FitLife AI")


@app.route("/cook")
def cook_page():
    return render_template("cook.html", title="AI 厨房")


@app.route("/brain")
def brain_page():
    # 这里把思源地址丢给模板
    return render_template(
        "brain.html",
        title="小ka 知识仓库",
        siyuan_url=config.SIYUAN_URL,
    )


if __name__ == "__main__":
    print("🚀 服务器启动中... (AI 模式: 开启)")
    app.run(debug=True, host="0.0.0.0", port=5000)
