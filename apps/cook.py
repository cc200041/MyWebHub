from flask import Blueprint, jsonify, request, send_from_directory
from core import ai, db
import config
import os
import json
import markdown

cook_bp = Blueprint('cook', __name__)


def _ensure_dir(path: str):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def generate_and_save(name: str):
    """
    针对“新菜名”调用 AI 生成一份菜谱，并立即：
    - 写入 data/HowToCook/dishes/AI_Generated/{name}.md
    - 写入 cook_data.db 的 recipes 表
    返回一个 dict，可直接给前端用。
    """
    prompt = f"""
    你是一个中文菜谱助手，请为《{name}》生成一个详细菜谱。

    请严格返回一个 JSON 对象，结构如下（不要写多余文字）：
    {{
      "markdown_content": "# {name}\\n...(完整 Markdown 菜谱)...",
      "meta": {{
        "main_ingredients": ["食材1", "食材2"],
        "tags": ["家常菜", "低脂"],
        "difficulty": 3,
        "calories": 500
      }}
    }}
    其中：
    - markdown_content 必须是完整可用的 Markdown 菜谱
    - main_ingredients 只放 3~8 个核心食材（短语）
    - tags 放 1~5 个标签，如“家常菜/川菜/低脂/快手菜”
    - difficulty 为 1~5 的整数
    - calories 为每份估算热量，整数，单位 kcal
    """
    data = ai.generate_json(prompt)
    if not data:
        return None

    markdown_content = (data.get("markdown_content") or "").strip()
    meta = data.get("meta") or {}
    main_ings = meta.get("main_ingredients") or []
    tags = meta.get("tags") or []
    try:
        difficulty = int(meta.get("difficulty") or 3)
    except Exception:
        difficulty = 3
    try:
        calories = int(meta.get("calories") or 0)
    except Exception:
        calories = 0

    if not markdown_content:
        markdown_content = f"# {name}\n\n暂时没有详细菜谱，稍后再来看看吧。"

    save_dir = os.path.join(config.COOK_ROOT, "AI_Generated")
    _ensure_dir(save_dir)
    rel_path = os.path.join("AI_Generated", f"{name}.md")
    full_path = os.path.join(config.COOK_ROOT, rel_path)

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    with db.get_cook_conn() as conn:
        c = conn.cursor()
        # 清理旧记录，避免重复
        c.execute("DELETE FROM recipes WHERE name=?", (name,))
        c.execute(
            """
            INSERT INTO recipes
            (name, category, path, raw_ingredients, structured_ingredients, tags, difficulty, calories_est)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                name,
                "AI生成",
                rel_path,
                "",
                json.dumps(main_ings, ensure_ascii=False),
                json.dumps(tags, ensure_ascii=False),
                difficulty,
                calories,
            ),
        )
        conn.commit()

    # 返回一个“看起来像 dict(row)”的结构给前端
    return {
        "name": name,
        "category": "AI生成",
        "path": rel_path,
        "raw_ingredients": "",
        "structured_ingredients": json.dumps(main_ings, ensure_ascii=False),
        "tags": json.dumps(tags, ensure_ascii=False),
        "difficulty": difficulty,
        "calories_est": calories,
    }


@cook_bp.route("/api/cook/search")
def search():
    """图鉴搜索：支持关键词模糊匹配；没搜到时自动生成新菜并入库。"""
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify([])

    with db.get_cook_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM recipes WHERE name LIKE ? OR tags LIKE ? LIMIT 20",
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
        res = [dict(r) for r in rows]

    # 如果库里没有，就让 AI 现编一份，偷偷写入数据库 & 菜谱文件
    if not res and 1 < len(q) < 20:
        gen = generate_and_save(q)
        if gen:
            res.append(gen)

    return jsonify(res)


@cook_bp.route("/api/cook/pantry")
def pantry():
    """合成台：根据“我有什么食材”在本地 recipes 表里算匹配度。"""
    ings_str = request.args.get("ingredients", "")
    ings = {i.strip() for i in ings_str.replace("，", ",").split(",") if i.strip()}
    if not ings:
        return jsonify([])

    with db.get_cook_conn() as conn:
        recipes = conn.execute("SELECT * FROM recipes").fetchall()

    res = []
    for r in recipes:
        try:
            needed = json.loads(r["structured_ingredients"] or "[]")
        except Exception:
            continue
        if not needed:
            continue

        hits = sum(1 for n in needed if any(i in n or n in i for i in ings))
        missing = [n for n in needed if not any(i in n or n in i for i in ings)]

        if hits > 0 and len(missing) <= 3:
            res.append(
                {
                    "name": r["name"],
                    "category": r["category"],
                    "score": int(hits / len(needed) * 100),
                    "missing": missing,
                    "tags": json.loads(r["tags"] or "[]"),
                }
            )

    res.sort(key=lambda x: x["score"], reverse=True)
    return jsonify(res[:20])


@cook_bp.route("/api/cook/detail")
def detail():
    """菜谱详情：文件丢了就让 AI 现写一份 Markdown，而不是显示 Missing。"""
    name = (request.args.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400

    with db.get_cook_conn() as conn:
        row = conn.execute("SELECT * FROM recipes WHERE name=?", (name,)).fetchone()

    if not row:
        return jsonify({"error": "404"}), 404

    rel_path = row["path"]
    full_path = os.path.join(config.COOK_ROOT, rel_path)

    if os.path.exists(full_path):
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        # 本地文件缺失：找 AI 补一份
        md = ai.chat_with_text(
            f"菜谱文件丢失了，请为《{row['name']}》写一份详细菜谱，使用 Markdown 标题和步骤列表。"
        )
        content = md or f"# {row['name']}\n\n暂时找不到原始菜谱。"

    html = markdown.markdown(content)

    return jsonify(
        {
            "name": row["name"],
            "category": row["category"],
            "html": html,
            "calories": row["calories_est"],
            "tags": json.loads(row["tags"] or "[]"),
        }
    )


@cook_bp.route("/api/cook/ask_chef", methods=["POST"])
def ask():
    data = request.get_json(force=True)
    recipe = data.get("recipe", "")
    question = data.get("question", "")
    answer = ai.chat_with_text(f"菜谱《{recipe}》，用户提问：{question}")
    return jsonify({"answer": answer})


@cook_bp.route("/api/cook/token", methods=["POST"])
def token():
    data = request.get_json(force=True)
    return jsonify({"token": f"#HTC:{data['name']}:{data['cal']}#"})


@cook_bp.route("/api/cook/chef_chat", methods=["POST"])
def chef_chat():
    """
    左侧“厨师”聊天：
    - 读取用户自然语言描述的食材 / 需求
    - 用 AI 生成推荐菜名列表
    - 对于本地不存在的菜，后台自动 generate_and_save 一份写入数据库
    """
    data = request.get_json(force=True)
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"reply": "先告诉我你家里有什么食材吧～", "recipes": []})

    prompt = f"""
    你是一个根据用户现有食材推荐菜谱的中文 厨师助手。
    用户说：\"{message}\"。

    请先判断用户大概有哪些食材、是否有饮食限制（例如：想减脂、不要辣、不要油炸等）。

    严格输出 JSON（不要写多余文字），格式：
    {{
      "reply": "用口语化中文，2~3 句，对用户说今天可以怎么吃。",
      "recipes": [
        {{
          "name": "对应的菜名",
          "missing": ["缺少的关键食材1", "缺少的关键食材2"],
          "score": 0 到 100 的整数，表示推荐程度
        }}
      ]
    }}
    如果暂时想不到菜，就把 recipes 设为 []，reply 里诚实说明。
    """

    ai_result = ai.generate_json(prompt)
    if not ai_result:
        return jsonify(
            {
                "reply": "我这会儿有点卡壳，你可以先用右边搜索框手动搜菜名。",
                "recipes": [],
            }
        )

    recipes = ai_result.get("recipes") or []
    if isinstance(recipes, dict):
        recipes = [recipes]

    normalized = []
    with db.get_cook_conn() as conn:
        c = conn.cursor()
        for r in recipes:
            name = (r.get("name") or "").strip()
            if not name:
                continue

            row = c.execute(
                "SELECT * FROM recipes WHERE name LIKE ? LIMIT 1", (f"%{name}%",)
            ).fetchone()

            # 不在库里的菜：后台偷偷生成一份写入数据库
            if not row:
                gen = generate_and_save(name)
                if gen:
                    row = c.execute(
                        "SELECT * FROM recipes WHERE name=?", (name,)
                    ).fetchone()

            if row:
                normalized.append(
                    {
                        "name": row["name"],
                        "score": int(r.get("score", 80)),
                        "missing": r.get("missing") or [],
                        "exists": True,
                        "category": row["category"],
                    }
                )
            else:
                normalized.append(
                    {
                        "name": name,
                        "score": int(r.get("score", 60)),
                        "missing": r.get("missing") or [],
                        "exists": False,
                    }
                )

    return jsonify(
        {"reply": ai_result.get("reply", "试着换个说法再问我一次吧～"), "recipes": normalized}
    )


@cook_bp.route("/data/HowToCook/dishes/<path:filename>")
def img(filename):
    return send_from_directory(config.COOK_ROOT, filename)
