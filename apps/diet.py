from flask import Blueprint, jsonify, request
from core import ai, db
import config
import datetime
import json
import os

diet_bp = Blueprint("diet", __name__)

# -------------------- 数据初始化 --------------------

def init_diet_db():
    conn = db.get_diet_conn()
    c = conn.cursor()

    # 用户表
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            height REAL,
            gender TEXT,
            age INTEGER,
            target_weight REAL,
            current_weight REAL
        )
        """
    )

    # 日志表：存食物记录与体重记录
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            type TEXT,          -- 'food' / 'weight'
            category TEXT,
            value REAL,         -- 食物: kcal; 体重: kg
            note TEXT
        )
        """
    )

    # 健康报告表
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS health_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            report_type TEXT,
            analysis TEXT,
            summary TEXT
        )
        """
    )

    conn.commit()
    conn.close()

    # 至少一个默认用户
    with db.get_diet_conn() as conn2:
        cur = conn2.execute("SELECT COUNT(*) AS n FROM users")
        if cur.fetchone()["n"] == 0:
            conn2.execute(
                "INSERT INTO users (name,height,gender,age,target_weight,current_weight) "
                "VALUES (?,?,?,?,?,?)",
                ("默认用户", 170, "female", 25, 60, 60),
            )
            conn2.commit()


# JSON 食物库
FOOD_DB = []
if os.path.exists(config.FOOD_JSON):
    try:
        with open(config.FOOD_JSON, "r", encoding="utf-8") as f:
            FOOD_DB = json.load(f)
    except Exception:
        FOOD_DB = []

init_diet_db()

# -------------------- 小工具 --------------------

def _today():
    return datetime.date.today().isoformat()


def _get_user_profile(user_id: int):
    with db.get_diet_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(row) if row else None


def _calc_bmr(profile: dict):
    if not profile:
        return 1800
    w = profile.get("current_weight") or profile.get("target_weight") or 60
    h = profile.get("height") or 170
    age = profile.get("age") or 25
    gender = profile.get("gender") or "female"
    base = 10 * w + 6.25 * h - 5 * age
    base += 5 if gender == "male" else -161
    return int(base)

# -------------------- 用户相关 --------------------

@diet_bp.route("/api/get_users")
def get_users():
    with db.get_diet_conn() as conn:
        arr = [dict(r) for r in conn.execute("SELECT id,name FROM users").fetchall()]
    return jsonify(arr)


@diet_bp.route("/api/create_user", methods=["POST"])
def create_user():
    data = request.get_json(force=True)
    name = (data.get("name") or "新用户").strip()
    with db.get_diet_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (name,height,gender,age,target_weight,current_weight) "
            "VALUES (?,?,?,?,?,?)",
            (name, 170, "female", 25, 60, 60),
        )
        uid = cur.lastrowid
        conn.commit()
    return jsonify({"status": "success", "id": uid})


@diet_bp.route("/api/delete_user", methods=["POST"])
def delete_user():
    data = request.get_json(force=True)
    uid = data.get("id")
    with db.get_diet_conn() as conn:
        conn.execute("DELETE FROM logs WHERE user_id=?", (uid,))
        conn.execute("DELETE FROM users WHERE id=?", (uid,))
        conn.commit()
    return jsonify({"status": "success"})


@diet_bp.route("/api/save_profile", methods=["POST"])
def save_profile():
    data = request.get_json(force=True)
    uid = data.get("user_id")
    with db.get_diet_conn() as conn:
        conn.execute(
            """
            UPDATE users
               SET height=?,
                   gender=?,
                   age=?,
                   target_weight=?,
                   current_weight=?
             WHERE id=?
            """,
            (
                data.get("height"),
                data.get("gender"),
                data.get("age"),
                data.get("target_weight"),
                data.get("current_weight_input"),
                uid,
            ),
        )
        conn.commit()
    return jsonify({"status": "success"})

# -------------------- 食物搜索 & AI 估算 --------------------

@diet_bp.route("/api/search_food")
def search_food():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify([])
    res = []
    for item in FOOD_DB:
        name = item.get("name", "")
        if q in name:
            res.append({
                "name": name,
                "cal": item.get("cal") or item.get("kcal") or 0,
                "emoji": item.get("emoji") or "🍽",
            })
        if len(res) >= 20:
            break
    return jsonify(res)


@diet_bp.route("/api/ai_estimate_food", methods=["POST"])
def ai_estimate_food():
    data = request.get_json(force=True)
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "empty"}), 400

    prompt = f"""
你叫小ka，是一个 14 岁的雌小鬼风格减脂饮食助手，说话活泼一点。
用户这样描述自己吃了什么：{text}

请粗略估算总热量，给出一个 JSON，格式如下（只输出 JSON）：
{{
  "name": "一句话概括这顿饭",
  "est_cal": 600
}}
热量单位是 kcal，只要整数，不要加单位。
"""
    answer = ai.chat_with_text(prompt)
    try:
        js = json.loads(answer)
    except Exception:
        import re
        m = re.search(r"(\\d+)", answer or "")
        est = int(m.group(1)) if m else 500
        js = {"name": text[:20], "est_cal": est}
    return jsonify(js)


@diet_bp.route("/api/diet/analyze_food_photo", methods=["POST"])
def analyze_food_photo():
    file = request.files.get("photo")
    if not file:
        return jsonify({"error": "no file"}), 400
    img_bytes = file.read()
    prompt = "这张照片里主要吃的食物是什么？请估算总热量（kcal），并给出 JSON：{name: 食物名称, est_cal: 热量整数}。"
    js = ai.analyze_image(img_bytes, prompt) or {}
    name = js.get("name") or "未知食物"
    cal = js.get("est_cal") or 0
    return jsonify({"name": name, "cal": cal})

# -------------------- 仪表盘 & 记录 --------------------

@diet_bp.route("/api/get_dashboard")
def get_dashboard():
    uid = int(request.args.get("user_id", 1))
    date = request.args.get("date") or _today()

    profile = _get_user_profile(uid)
    bmr = _calc_bmr(profile)

    with db.get_diet_conn() as conn:
        cur = conn.execute(
            "SELECT COALESCE(SUM(value),0) AS total "
            "FROM logs WHERE user_id=? AND date=? AND type='food'",
            (uid, date),
        )
        food_today = cur.fetchone()["total"]

        rows = conn.execute(
            """
            SELECT id,date,type,value,note
              FROM logs
             WHERE user_id=? AND date=?
             ORDER BY id DESC
            """,
            (uid, date),
        ).fetchall()

    history = [{
        "id": r["id"],
        "date": r["date"],
        "type": r["type"],
        "value": r["value"],
        "note": r["note"],
    } for r in rows]

    data = {
        "food_today": float(food_today),
        "current_weight": profile.get("current_weight") if profile else None,
        "bmr": bmr,
        "history": history,
    }

    return jsonify({"profile": profile, "data": data})


@diet_bp.route("/api/get_chart_data")
def get_chart_data():
    """近 30 天每日总热量，用于 K 线 + 日历."""
    uid = int(request.args.get("user_id", 1))
    days = 30
    today = datetime.date.today()

    dates, values = [], []
    with db.get_diet_conn() as conn:
        for i in range(days - 1, -1, -1):
            d = today - datetime.timedelta(days=i)
            ds = d.isoformat()
            cur = conn.execute(
                "SELECT COALESCE(SUM(value),0) AS total "
                "FROM logs WHERE user_id=? AND date=? AND type='food'",
                (uid, ds),
            )
            total = cur.fetchone()["total"] or 0
            dates.append(ds)
            values.append(float(total))

    return jsonify({"dates": dates, "values": values})


@diet_bp.route("/api/add", methods=["POST"])
def add_log():
    data = request.get_json(force=True)
    uid = int(data.get("user_id", 1))
    date = data.get("date") or _today()
    tp = data.get("type") or "food"
    value = float(data.get("value") or 0)
    note = data.get("note") or ""
    with db.get_diet_conn() as conn:
        conn.execute(
            "INSERT INTO logs (user_id,date,type,category,value,note) "
            "VALUES (?,?,?,?,?,?)",
            (uid, date, tp, "", value, note),
        )
        if tp == "weight":
            conn.execute(
                "UPDATE users SET current_weight=? WHERE id=?",
                (value, uid),
            )
        conn.commit()
    return jsonify({"status": "success"})


@diet_bp.route("/api/delete_log", methods=["POST"])
def delete_log():
    data = request.get_json(force=True)
    log_id = data.get("id")
    with db.get_diet_conn() as conn:
        conn.execute("DELETE FROM logs WHERE id=?", (log_id,))
        conn.commit()
    return jsonify({"status": "success"})

# -------------------- AI 日报 --------------------

@diet_bp.route("/api/diet/daily_report", methods=["POST"])
def daily_report():
    data = request.get_json(force=True)
    uid = int(data.get("user_id", 1))

    profile = _get_user_profile(uid)
    bmr = _calc_bmr(profile)

    today = datetime.date.today()
    with db.get_diet_conn() as conn:
        lines = []
        for i in range(6, -1, -1):
            d = today - datetime.timedelta(days=i)
            ds = d.isoformat()
            total = conn.execute(
                "SELECT COALESCE(SUM(value),0) AS total "
                "FROM logs WHERE user_id=? AND date=? AND type='food'",
                (uid, ds),
            ).fetchone()["total"]
            lines.append(f"{ds}: {total} kcal")

    prompt = f"""
你是一位健身营养教练。

用户基础信息：{json.dumps(profile, ensure_ascii=False)}
估算基础代谢：{bmr} kcal

下面是最近 7 天每日摄入热量：
{chr(10).join(lines)}

请用 3~5 句话给出：
1. 今日总体评价
2. 本周趋势简要分析
3. 明天可以执行的一条具体建议

只输出中文自然语言，不要列表编号。
"""
    text = ai.chat_with_text(prompt)
    return jsonify({"report": text})
