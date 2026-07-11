from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
import json
import os
from datetime import datetime
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
                        
# 导入游戏数据模块
from game_data import (
    create_game_session, get_game_session, end_game_session,
    get_next_icons, get_random_start_icon, get_icon_by_id,
    load_icon_data, save_icon_data, active_games
)

app = Flask(__name__)
app.secret_key = "icon-story-game-secret-key-2024"

USER_FILE = "users.json"

# 配置文件上传和静态文件
UPLOAD_FOLDER = 'static/images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 添加图片服务路由
@app.route('/static/images/<path:filename>')
def serve_image(filename):
    """服务图片文件"""
    return send_from_directory('static/images', filename)

# ==================== 用户数据管理 ====================
def load_users():
    """从JSON文件加载用户数据"""
    if not os.path.exists(USER_FILE):
        with open(USER_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4)
        return {}
    
    with open(USER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    """保存用户数据到JSON文件"""
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)

def update_user_stats(username: str, chain_length: int):
    """更新用户游戏统计"""
    users = load_users()
    if username in users:
        stats = users[username].get("game_stats", {"total_games": 0, "longest_chain": 0})
        stats["total_games"] += 1
        if chain_length > stats.get("longest_chain", 0):
            stats["longest_chain"] = chain_length
        users[username]["game_stats"] = stats
        save_users(users)

# ==================== 注册功能 ====================
@app.route("/register", methods=["GET", "POST"])
def register():
    """用户注册页面"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        
        # 表单验证
        errors = []
        if not username:
            errors.append("用户名不能为空")
        elif len(username) < 3:
            errors.append("用户名至少3个字符")
        
        if not password:
            errors.append("密码不能为空")
        elif len(password) < 4:
            errors.append("密码至少4个字符")
        
        if password != confirm_password:
            errors.append("两次输入的密码不一致")
        
        # 检查用户名是否已存在
        users = load_users()
        if username in users:
            errors.append("用户名已存在，请更换用户名")
        
        if errors:
            return render_template("register.html", errors=errors, username=username)
        
        # 注册成功，保存用户
        users[username] = {
            "password": password,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "game_stats": {
                "total_games": 0,
                "longest_chain": 0
            }
        }
        save_users(users)
        
        return render_template("register.html", 
                               success=True, 
                               message=f"🎉 用户 {username} 注册成功！请前往登录")
    
    return render_template("register.html")

# ==================== 登录功能 ====================
@app.route("/login", methods=["GET", "POST"])
def login():
    """用户登录页面"""
    if "username" in session:
        return redirect(url_for("game_home"))
    
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        errors = []
        if not username:
            errors.append("请输入用户名")
        if not password:
            errors.append("请输入密码")
        
        if not errors:
            users = load_users()
            if username in users and users[username]["password"] == password:
                session["username"] = username
                return redirect(url_for("game_home"))
            else:
                errors.append("用户名或密码错误")
        
        return render_template("login.html", errors=errors, username=username)
    
    return render_template("login.html")

# ==================== 游戏主页面 ====================
@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("game_home"))
    return redirect(url_for("login"))

@app.route("/game_home")
def game_home():
    if "username" not in session:
        return redirect(url_for("login"))
    
    users = load_users()
    user_info = users.get(session["username"], {})
    
    return render_template("game_home.html", 
                          username=session["username"],
                          user_info=user_info)

# ==================== 游戏页面 ====================

# app.py 中的 game 路由需要确保传递 common_meaning

@app.route("/game")
def game():
    """游戏主页面"""
    if "username" not in session:
        return redirect(url_for("login"))
    
    session_id = request.args.get("session_id")
    game_session = get_game_session(session_id)
    
    if not game_session or game_session.username != session["username"]:
        return redirect(url_for("game_home"))
    
    # 获取当前游戏状态
    if game_session.chain and len(game_session.chain) > 0:
        current_icon = game_session.chain[-1]
    else:
        game_session.start_game()
        current_icon = game_session.chain[-1] if game_session.chain else None
    
    # 确保当前图标有完整信息
    if current_icon:
        if not current_icon.get("icon_url"):
            current_icon["icon_url"] = ""
        if not current_icon.get("icon"):
            current_icon["icon"] = "🖼️"
        if not current_icon.get("common_meaning"):
            current_icon["common_meaning"] = get_icon_meaning(current_icon["id"])
        if not current_icon.get("name"):
            current_icon["name"] = current_icon["common_meaning"][:20]
    
    # 获取选项
    used_ids = list(game_session.used_icon_ids) if hasattr(game_session, 'used_icon_ids') else []
    next_options = get_next_icons(current_icon["id"], 4, used_ids) if current_icon else []
    
    # 确保所有选项都有完整信息
    for option in next_options:
        if not option.get("icon_url"):
            option["icon_url"] = ""
        if not option.get("icon"):
            option["icon"] = "🖼️"
        if not option.get("common_meaning"):
            option["common_meaning"] = get_icon_meaning(option["id"])
        if not option.get("name"):
            option["name"] = option["common_meaning"][:20]
    
    # 确保故事链中的图标都有完整信息
    for icon in game_session.chain:
        if not icon.get("icon_url"):
            icon["icon_url"] = ""
        if not icon.get("icon"):
            icon["icon"] = "🖼️"
        if not icon.get("common_meaning"):
            icon["common_meaning"] = get_icon_meaning(icon["id"])
        if not icon.get("name"):
            icon["name"] = icon["common_meaning"][:20]
    
    game_state = {
        "current_icon": current_icon,
        "options": next_options,
        "round": game_session.current_round,
        "total_rounds": game_session.total_rounds,
        "chain": game_session.chain
    }
    
    return render_template("game.html", 
                          game_session_id=session_id,
                          game_state=game_state,
                          username=session["username"])
# ==================== 游戏API ====================
@app.route("/api/game/start", methods=["POST"])
def api_start_game():
    """开始新游戏"""
    if "username" not in session:
        return jsonify({"error": "未登录"}), 401
    
    data = request.get_json()
    total_rounds = data.get("total_rounds", 10)
    
    # 修改这里：允许 10、20、40 回合
    if total_rounds not in [10, 20, 40]:
        total_rounds = 10
    
    session_id = create_game_session(session["username"], total_rounds)
    game_session = get_game_session(session_id)
    game_session.start_game()
    
    return jsonify({
        "session_id": session_id,
        "total_rounds": total_rounds
    })

@app.route("/api/game/choose", methods=["POST"])
def api_game_choose():
    """玩家选择图标"""
    if "username" not in session:
        return jsonify({"error": "未登录"}), 401
    
    data = request.get_json()
    session_id = data.get("session_id")
    icon_id = data.get("icon_id")
    
    game_session = get_game_session(session_id)
    if not game_session or game_session.username != session["username"]:
        return jsonify({"error": "无效的游戏会话"}), 400
    
    result = game_session.make_choice(icon_id)
    
    if result.get("game_complete"):
        # 游戏完成，更新用户统计
        update_user_stats(session["username"], len(result["chain"]))
        end_game_session(session_id)
    
    return jsonify(result)

@app.route("/api/game/replay")
def api_game_replay():
    """获取游戏回放数据"""
    if "username" not in session:
        return jsonify({"error": "未登录"}), 401
    
    session_id = request.args.get("session_id")
    game_session = get_game_session(session_id)
    
    # 也检查已结束的游戏
    if not game_session:
        # 尝试从活跃会话中查找
        return jsonify({"error": "游戏会话不存在"}), 404
    
    if game_session.username != session["username"]:
        return jsonify({"error": "无权访问"}), 403
    
    return jsonify({
        "chain": game_session.chain,
        "summary": game_session.get_game_summary()
    })

@app.route("/api/game/quit", methods=["POST"])
def api_game_quit():
    """退出游戏"""
    if "username" not in session:
        return jsonify({"error": "未登录"}), 401
    
    data = request.get_json()
    session_id = data.get("session_id")
    
    end_game_session(session_id)
    return jsonify({"success": True})

# ==================== 图标管理API（预留第三棒）====================
@app.route("/api/icons")
def api_get_icons():
    """获取所有图标"""
    icons = load_icon_data()
    return jsonify(icons)

@app.route("/api/icons/<icon_id>")
def api_get_icon(icon_id):
    """获取单个图标信息"""
    icon = get_icon_by_id(icon_id)
    if icon:
        return jsonify(icon)
    return jsonify({"error": "图标不存在"}), 404

@app.route("/api/icons/relation/<icon_id>")
def api_get_relations(icon_id):
    """获取图标的关联推荐（第三棒可扩展）"""
    recommendations = get_next_icons(icon_id, 5)
    return jsonify({
        "source": icon_id,
        "recommendations": recommendations
    })

# ==================== 登出功能 ====================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ==================== API接口 ====================
@app.route("/api/check_login")
def check_login():
    if "username" in session:
        return jsonify({"logged_in": True, "username": session["username"]})
    return jsonify({"logged_in": False})

# ==================== 启动应用 ====================
if __name__ == "__main__":
    # 使用更稳定的配置
    print("=" * 50)
    print("🎮 图标地书接龙游戏服务器启动中...")
    print("=" * 50)
    print("本地访问: http://127.0.0.1:5000")
    print("按 Ctrl+C 停止服务器")
    print("=" * 50)
    
    app.run(debug=True, host="127.0.0.1", port=5000,use_reloader=False)  # 只能本机访问
