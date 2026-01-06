# exam_system/server/app.py
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response, jsonify
from flask_mysqldb import MySQL
from MySQLdb.cursors import DictCursor
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
import pandas as pd
from flask import send_file
import openpyxl
from io import BytesIO
from utils import get_units_tree

app = Flask(__name__, template_folder="templates")
app.secret_key = os.urandom(24)

# Cấu hình kết nối MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '1234'
app.config['MYSQL_DB'] = 'exam_system'

mysql = MySQL(app)

@app.after_request
def add_header_no_cache(response):
    # """
    # Ngăn cache cho tất cả các trang admin.
    # Khi người dùng nhấn 'Back' sau khi logout,
    # trình duyệt buộc phải gửi request mới — và bị kiểm tra session.
    # """
    if request.path.startswith('/admin'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash("Vui lòng đăng nhập để tiếp tục.", "warning")
            return redirect(url_for('admin_login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    """Decorator cho phép truy cấp khi session role nằm trong allowed_roles"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_role = session.get('admin_role')
            if not user_role:
                flash("Bạn cần đăng nhập!", "warning")
                return redirect(url_for("admin_login", next=request.url))
            if user_role not in allowed_roles:
                flash("Bạn không có quyền truy cập trang này.", "danger")
                return redirect(url_for('admin_dashboard'))
            return func(*args, **kwargs)
        return wrapper
    return decorator

@app.route('/login/admin', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        cur = mysql.connection.cursor()
        cur.execute("SELECT id, username, password_hash, role, status, unit_id FROM admin_users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        if not user:
            error = "Tên đăng nhập không tồn tại."
        else:
            # user_id, user_name, password_hash = user
            if user[4] == "locked":
                flash("Tài khoản đã bị khóa!", "danger")
                return redirect(url_for("admin_login"))

            if check_password_hash(user[2], password):
                session['admin_logged_in'] = True
                session['admin_id'] = user[0] # id
                session['admin_username'] = user[1] # username
                session['admin_role'] = user[3] # role
                session['admin_unit_id'] = user[5] # unit_id
                next_url = request.args.get('next') or url_for('admin_dashboard')
                return redirect(next_url)
            else:
                error = "Sai mật khẩu."

    return render_template('admin/login.html', error=error)


@app.route('/logout/admin')
def admin_logout():
    session.clear()
    response = make_response(redirect(url_for('admin_login')))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# =========================== ADMIN ====================================
# dashboard
@app.route('/admin')
@login_required
def admin_dashboard():
    return render_template('admin/dashboard.html')

# đổi mật khẩu
@app.route("/admin/change_password_admin", methods=["GET", "POST"])
@login_required
def admin_change_password():
    # if "admin_logged_in" not in session:
    #     return redirect(url_for("admin_login"))

    if request.method == "POST":
        current_password = request.form["current_password"]
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        # Lấy thông tin tài khoản hiện tại
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT password_hash FROM admin_users WHERE id=%s", (session["admin_id"],))
        user = cursor.fetchone()

        # Kiểm tra mật khẩu cũ
        if not check_password_hash(user[0], current_password):
            flash("Mật khẩu cũ không đúng!", "danger")
            return redirect(url_for("admin_change_password"))

        # Kiểm tra mật khẩu trùng
        if new_password != confirm_password:
            flash("Mật khẩu mới không khớp!", "danger")
            return redirect(url_for("admin_change_password"))

        # Cập nhật mật khẩu
        new_hash = generate_password_hash(new_password)
        cursor.execute("UPDATE admin_users SET password_hash=%s WHERE id=%s",
                       (new_hash, session["admin_id"]))
        mysql.connection.commit()

        flash("Đổi mật khẩu thành công!", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin/change_password.html")

# ======================= QUẢN LÝ NGƯỜI DÙNG =================================
# Quản trị người dùng
@app.route("/admin/user_management")
@login_required
@role_required("superadmin")
def user_management():
    units_tree = get_units_tree()
    return render_template("admin/user_management.html", units_tree=units_tree)

#lấy danh sách tài khoản thuộc 1 đơn vị
@app.route("/admin/get_users/<int:unit_id>")
@login_required
def get_users_by_unit(unit_id):
    cursor = mysql.connection.cursor(DictCursor)
    cursor.execute("""
        SELECT id, username, role, status   
        FROM admin_users 
        WHERE unit_id = %s
    """, (unit_id,))
    users = cursor.fetchall()
    cursor.close()
    return jsonify(users)

# tạo tài khoản quản trị
@app.route("/admin/create_user", methods=["GET", "POST"])
@login_required
@role_required("superadmin")
def create_user():
    # if "admin_logged_in" not in session:
    #     return redirect(url_for("admin_login"))
    active_unit = session.get("active_unit")
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        confirm = request.form["confirm"]

        # Kiểm tra trùng mật khẩu
        if password != confirm:
            flash("Mật khẩu xác nhận không khớp!", "danger")
            return redirect(url_for("create_user"))

        cursor = mysql.connection.cursor()

        # Kiểm tra username tồn tại
        cursor.execute("SELECT id FROM admin_users WHERE username=%s", (username,))
        if cursor.fetchone():
            flash("Tên tài khoản đã tồn tại!", "danger")
            return redirect(url_for("create_user"))

        # Lưu user mới
        password_hash = generate_password_hash(password)
        cursor.execute("""
            INSERT INTO admin_users (username, password_hash, unit_id, role, status) 
            VALUES (%s, %s, %s, "admin", "active")
        """, (username, password_hash, active_unit))
        mysql.connection.commit()

        flash("Tạo tài khoản quản trị thành công!", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin/create_user.html")

# đổi mật khẩu user
@app.route("/admin/change_password", methods=["POST"])
@login_required
@role_required("superadmin")
def change_password():
    data = request.get_json()
    user_id = data.get("user_id")
    new_password = data.get("password")

    if not user_id or not new_password:
        return jsonify({"status": "error", "message": "Thiếu dữ liệu!"})

    password_hash = generate_password_hash(new_password)

    cursor = mysql.connection.cursor()
    cursor.execute("""
        UPDATE admin_users 
        SET password_hash = %s
        WHERE id = %s
    """, (password_hash, user_id))

    mysql.connection.commit()
    cursor.close()

    return jsonify({"status": "success"})

# Điều chỉnh tài khoản
@app.route("/admin/toggle_user_status", methods=["POST"])
@login_required
@role_required("superadmin")
def toggle_user_status():
    data = request.get_json()
    user_id = data.get("user_id")
    current_status = data.get("current_status")

    new_status = "locked" if current_status == "active" else "active"

    cursor = mysql.connection.cursor()
    cursor.execute("""
        UPDATE admin_users 
        SET status = %s
        WHERE id = %s
    """, (new_status, user_id))
    mysql.connection.commit()
    cursor.close()

    return jsonify({"status": "success", "new_status": new_status})

# Xóa tài khoản
@app.route("/admin/delete_user", methods=["POST"])
@login_required
@role_required("superadmin")
def delete_user():
    data = request.get_json()
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"status": "error", "message": "Thiếu user_id!"})

    cursor = mysql.connection.cursor()

    # Không cho phép xóa chính mình
    if user_id == session.get("admin_id"):
        return jsonify({"status": "error", "message": "Không thể tự xóa chính mình!"})

    cursor.execute("DELETE FROM admin_users WHERE id = %s", (user_id,))
    mysql.connection.commit()
    cursor.close()

    return jsonify({"status": "success"})

# Tạo đơn vị
@app.route("/admin/create_unit", methods=["POST"])
@login_required
def create_unit():
    data = request.get_json()

    unit_name = data.get("unit_name")
    parent_id = data.get("parent_id")

    if parent_id == "" or parent_id is None:
        parent_id = None

    cur = mysql.connection.cursor()

    cur.execute("""
        INSERT INTO units (unit_name, parent_id)
        VALUES (%s, %s)
    """, (unit_name, parent_id))

    mysql.connection.commit()

    return {"success": True, "message": "Thêm đơn vị thành công!"}

# Xóa đơn vị
@app.route("/admin/delete_unit", methods=["POST"])
def delete_unit():
    data = request.get_json()
    unit_id = data.get("unit_id")

    cursor = mysql.connection.cursor()

    # Kiểm tra đơn vị có tồn tại
    cursor.execute("SELECT unit_id FROM units WHERE unit_id=%s", (unit_id,))
    if not cursor.fetchone():
        return jsonify({"success": False, "message": "Đơn vị không tồn tại!"})

    # Xóa đơn vị
    cursor.execute("DELETE FROM units WHERE unit_id=%s", (unit_id,))
    mysql.connection.commit()

    return jsonify({"success": True, "message": "Đã xóa đơn vị thành công!"})

#lưu đơn vị đang chọn vào session
@app.route("/admin/set_active_unit", methods=["POST"])
@login_required
@role_required("superadmin")
def set_active_unit():
    data = request.get_json()
    if not data or "unit_id" not in data:
        return {"status": "error", "message": "Missing unit_id"}, 400
    session["active_unit"] = data.get("unit_id")
    return {"status": "ok"}

#============================== QUẢN LÝ NGÂN HÀNG CÂU HỎI ==================================
# Ngân hàng câu hỏi (on dashboard)
@app.route('/admin/questions', methods=['GET', 'POST'])
@login_required
def admin_questions():
    cur = mysql.connection.cursor()
    # subject_id = request.args.get("subject_id")
    # print(f"subject_id: {subject_id}")
    subject_filter = request.args.get("subject_filter")
    if request.method == 'POST':
        subject_id = request.form.get("subject_id")
        content = request.form.get('content', '').strip()
        a = request.form.get('a', '').strip()
        b = request.form.get('b', '').strip()
        c = request.form.get('c', '').strip()
        d = request.form.get('d', '').strip()
        correct = request.form.get('correct', '').strip().upper()

        if not content or not a or not b or not c or not d or correct not in ['A', 'B', 'C', 'D']:
            flash('Vui lòng điền đầy đủ thông tin và chọn đáp án đúng (A, B, C, D).', 'error')
        else:
            cur.execute("SELECT COUNT(*) FROM questions WHERE content = %s AND option_a = %s AND option_b = %s AND option_c = %s AND option_d = %s AND correct_option = %s AND created_by = %s",
                        (content,a,b,c,d,correct,session['admin_id']))
            count = cur.fetchone()[0]
            if count > 0:
                flash("⚠ Câu hỏi này đã tồn tại trong ngân hàng!", "error")
                mysql.connection.commit()
                cur.close()
                return redirect(url_for('admin_questions'))
            else:
                cur.execute("INSERT INTO questions (content, option_a, option_b, option_c, option_d, correct_option, created_by, subject_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                            (content, a, b, c, d, correct, session["admin_id"], subject_id))
                mysql.connection.commit()
                flash('Thêm câu hỏi thành công!', 'success')

    if session['admin_role'] == "superadmin":
        cur.execute("SELECT * FROM subjects")
    else:
        cur.execute("SELECT * FROM subjects WHERE created_by = %s", (session['admin_id'],))
    subjects = cur.fetchall()
    # else:
    #     # Admin chỉ xem câu hỏi do họ tạo
    #     cur.execute("SELECT * FROM questions WHERE created_by = %s", (session['admin_id'],))
    # questions = cur.fetchall()


    query = "SELECT * FROM questions WHERE 1=1"
    params = []

    # Superadmin xem tất cả, admin chỉ xem câu hỏi của mình
    if session['admin_role'] != "superadmin":
        query += " AND created_by = %s"
        params.append(session['admin_id'])

    # Lọc theo môn học
    if subject_filter:
        query += " AND subject_id = %s"
        params.append(subject_filter)

    cur.execute(query, params)
    questions = cur.fetchall()
    cur.close()

    # # Phân chia số câu hỏi hiển thi mỗi trang
    # page = int(request.args.get('page', 1)) # lấy số trang hiện tại
    # per_page = 10 #số câu hỏi mỗi trang

    # total_page = (len(questions) + per_page -1) // per_page
    # start = (page - 1)*per_page
    # end=start + per_page
    
    # page_questions = questions[start:end]

    # return render_template('admin/questions.html', questions=page_questions,
    #                                                 page=page,
    #                                                 total_page = total_page)
    return render_template('admin/questions.html', questions=questions,
                                                    subjects=subjects,
                                                    subject_filter=subject_filter )
# tìm kiếm câu hỏi
@app.route('/question_list')
@login_required
def question_list():
    keyword = request.args.get('keyword', '').strip()
    cur = mysql.connection.cursor()

    if keyword:
        sql = """
            SELECT * FROM questions
            WHERE content LIKE %s
            OR option_a LIKE %s
            OR option_b LIKE %s
            OR option_c LIKE %s
            OR option_d LIKE %s
        """
        like = f"%{keyword}%"
        cur.execute(sql, (like, like, like, like, like))
    else:
        cur.execute("SELECT * FROM questions")

    questions = cur.fetchall()
    cur.close()
    return render_template('admin/questions.html', questions=questions, keyword=keyword)

# Tạo môn học
@app.route("/admin/subjects/create", methods=["POST"])
@login_required
def create_subject():
    data = request.get_json()
    name = data.get("subject_name", "").strip()

    if not name:
        return jsonify({"status": "error", "message": "Tên môn học không được để trống!"})

    cur = mysql.connection.cursor()

    # Kiểm tra trùng tên trong phạm vi admin
    if session["admin_role"] == "superadmin":
        cur.execute("SELECT id FROM subjects WHERE subject_name=%s", (name,))
    else:
        cur.execute("SELECT id FROM subjects WHERE subject_name=%s AND created_by=%s",
                    (name, session["admin_id"]))

    if cur.fetchone():
        return jsonify({"status": "error", "message": "Môn học đã tồn tại!"})

    cur.execute("""
        INSERT INTO subjects (subject_name, created_by)
        VALUES (%s, %s)
    """, (name, session["admin_id"]))

    mysql.connection.commit()
    cur.close()

    return jsonify({"status": "success", "message": "Đã tạo môn học mới!"})

# Thêm câu hỏi từ file excel
@app.route("/admin/questions/import", methods=["POST"])
@login_required
def import_questions():
    cur = mysql.connection.cursor()
    subject_id = request.form.get("subject_id")
    if 'excel_file' not in request.files:
        flash("Không tìm thấy file tải lên.")
        return redirect(url_for('admin_questions'))

    file = request.files['excel_file']
    if file.filename == '':
        flash("Chưa chọn file Excel.")
        return redirect(url_for('admin_questions'))

    try:
        # Đọc dữ liệu từ Excel
        df = pd.read_excel(file)

        # Yêu cầu file Excel có cột: question_text, option_a, option_b, option_c, option_d, correct_answer
        expected_columns = ["content", "option_a", "option_b", "option_c", "option_d", "correct_option"]
        if not all(col in df.columns for col in expected_columns):
            flash(f"File Excel phải có các cột: {', '.join(expected_columns)}")
            return redirect(url_for('admin_questions'))

        for _, row in df.iterrows():
            # Kiểm tra câu hỏi trùng lặp trong ngân hàng câu hỏi
            cur.execute("SELECT COUNT(*) FROM questions WHERE content = %s AND option_a = %s AND option_b = %s AND option_c = %s AND option_d = %s AND correct_option = %s AND created_by = %s",
                        (row['content'],row['option_a'],row['option_b'],row['option_c'],row['option_d'],row['correct_option'], session['admin_id']))
            count = cur.fetchone()[0]
            if count <= 0:
                cur.execute("INSERT INTO questions (content, option_a, option_b, option_c, option_d, correct_option, created_by, subject_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", (
                    row['content'],
                    row['option_a'],
                    row['option_b'],
                    row['option_c'],
                    row['option_d'],
                    row['correct_option'],
                    session['admin_id'],
                    subject_id
                ))
        mysql.connection.commit()
        cur.close()
        if count > 0:
            flash(f"Tồn tại {count} câu hỏi đã có sẵn trong ngân hàng câu hỏi.")
        flash("Nhập câu hỏi từ Excel thành công!")
    except Exception as e:
        flash(f"Lỗi khi nhập: {str(e)}")

    return redirect(url_for('admin_questions'))

# Chỉnh sửa câu hỏi
@app.route('/admin/questions/edit/<int:question_id>', methods=['GET', 'POST'])
@login_required
def edit_question(question_id):
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        content = request.form['content']
        a = request.form['a']
        b = request.form['b']
        c = request.form['c']
        d = request.form['d']
        correct = request.form['correct'].upper()

        cur.execute("UPDATE questions SET content=%s, option_a=%s, option_b=%s, option_c=%s, option_d=%s, correct_option=%s WHERE id=%s",
                    (content, a, b, c, d, correct, question_id))
        mysql.connection.commit()
        flash('Cập nhật câu hỏi thành công!', 'success')
        return redirect(url_for('admin_questions'))

    cur.execute("SELECT * FROM questions WHERE id=%s", (question_id,))
    question = cur.fetchone()
    cur.close()
    return render_template('admin/edit_question.html', question=question)

# xóa câu hỏi
@app.route('/admin/questions/delete/<int:question_id>', methods=['POST'])
@login_required
def delete_question(question_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM questions WHERE id=%s", (question_id,))
    mysql.connection.commit()
    cur.close()
    flash('Xóa câu hỏi thành công!', 'success')
    return redirect(url_for('admin_questions'))

# =========================== QUẢN LÝ CUỘC THI =============================
# Xem danh sách cuộc thi 
@app.route("/admin/competitions")
@login_required
# @role_required(["superadmin, admin"])
def competitions():
    cur = mysql.connection.cursor()

    if session["admin_role"] == "superadmin":
        cur.execute("SELECT * FROM competitions")
    else:
        cur.execute("SELECT * FROM competitions WHERE created_by = %s", 
                    (session["admin_id"],))
    comps = cur.fetchall()
    cur.close()

    return render_template("admin/competitions.html", competitions=comps)

# Tạo cuộc thi mới 
@app.route("/admin/competitions/create", methods=["GET", "POST"])
@login_required
def create_competition():
    print(f"session: {session}")
    if session["admin_role"] not in ["admin", "superadmin"]:
        return "Bạn không có quyền!", 403

    if request.method == "POST":
        title = request.form["title"]
        description = request.form.get("description", "")

        created_by = session["admin_id"]
        unit_id = session["admin_unit_id"]

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO competitions (title, description, created_by, unit_id)
            VALUES (%s, %s, %s, %s)
        """, (title, description, created_by, unit_id))
        
        mysql.connection.commit()
        cur.close()

        flash("Tạo cuộc thi thành công!", "success")
        return redirect(url_for("competitions"))

    return render_template("admin/create_competition.html")

# danh sách thí sinh của một cuộc thi
@app.route("/admin/competitions/<int:comp_id>/candidates")
@login_required
def manage_candidates(comp_id):
    cur = mysql.connection.cursor()

    # Check quyền admin
    if session["admin_role"] != "superadmin":
        cur.execute("SELECT created_by FROM competitions WHERE id=%s", (comp_id,))
        owner = cur.fetchone()
        if not owner or owner[0] != session["admin_id"]:
            return "Bạn không có quyền!", 403

    cur.execute("SELECT * FROM candidates WHERE competition_id=%s", (comp_id,))
    candidates = cur.fetchall()
    cur.close()

    return render_template("admin/candidates.html", candidates=candidates, comp_id=comp_id)

# Thêm thí sinh vào cuộc thi
@app.route("/admin/competitions/<int:comp_id>/candidates/add", methods=["POST"])
@login_required
def add_candidate(comp_id):
    data = request.json
    full_name = data["full_name"]
    rank = data["rank"]
    position = data["position"]
    unit = data["unit"]
    username = data["username"]
    password = data["password"]

    pw_hash = generate_password_hash(password)

    cur = mysql.connection.cursor()

    # Check username trùng
    cur.execute("SELECT id FROM candidates WHERE username=%s", (username,))
    if cur.fetchone():
        return {"status": "error", "message": "Tên đăng nhập đã tồn tại!"}

    cur.execute("""
        INSERT INTO candidates (name, `rank`, position, unit, username, password_hash, competition_id, created_by)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (full_name, rank, position, unit, username, pw_hash, comp_id, session["admin_id"]))

    mysql.connection.commit()
    cur.close()

    return {"status": "success", "message": "Thêm thí sinh thành công!"}

# import danh sách thí sinh từ file excel
@app.route("/admin/competitions/<int:comp_id>/candidates/import", methods=["POST"])
@login_required
def import_candidates(comp_id):
    file = request.files.get('excel_file')
    if not file:
        return {"status": "error", "message": "Không có file Excel"}

    import pandas as pd
    df = pd.read_excel(file)

    required = ["full_name", "rank", "position", "unit", "username", "password"]
    if not all(col in df.columns for col in required):
        return {"status": "error", "message": "File thiếu cột"}

    cur = mysql.connection.cursor()

    added = 0
    skipped = 0
    for _, row in df.iterrows():
        cur.execute("SELECT id FROM candidates WHERE username=%s", (row["username"],))
        if cur.fetchone():
            skipped += 1
            continue

        pw_hash = generate_password_hash(str(row["password"]).strip())

        cur.execute("""
            INSERT INTO candidates (full_name, `rank`, position, unit, username, password_hash, competition_id, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            row["full_name"], row["rank"], row["position"], row["unit"],
            row["username"], pw_hash, comp_id, session["admin_id"]
        ))
        added += 1

    mysql.connection.commit()
    cur.close()

    return {
        "status": "success",
        "added": added,
        "skipped": skipped,
        "message": f"Thêm {added} thí sinh, bỏ qua {skipped} tài khoản trùng."
    }

# xóa thí sinh khỏi cuộc thi
@app.route("/admin/candidates/delete", methods=["POST"])
@login_required
def delete_candidate():
    cid = request.json.get("candidate_id")

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM candidates WHERE id=%s LIMIT 1", (cid,))
    mysql.connection.commit()
    cur.close()

    return {"status": "success"}

# Danh sách đề thi theo cuộc thi
@app.route("/admin/competitions/<int:comp_id>/exams")
@login_required
def competition_exams(comp_id):
    cur = mysql.connection.cursor()

    # kiểm tra quyền
    if session["admin_role"] != "superadmin":
        cur.execute("SELECT created_by FROM competitions WHERE id=%s", (comp_id,))
        owner = cur.fetchone()
        if not owner or owner[0] != session["admin_id"]:
            return "Bạn không có quyền xem cuộc thi này!", 403

    cur.execute("SELECT * FROM exams WHERE competition_id=%s", (comp_id,))
    exams = cur.fetchall()
    cur.close()

    return render_template("admin/list_exams.html", exams=exams, comp_id=comp_id)

# Tạo đề thi mới
@app.route('/admin/competitions/<int:comp_id>/exams/add', methods=['GET', 'POST'])
@login_required
def admin_exams(comp_id):
    cur = mysql.connection.cursor()
    # competition_id = request.args.get("competition_id") 
    if request.method == 'POST':
        title = request.form['title']
        duration_minutes = request.form['duration_minutes']

        file = request.files.get("excel_file")
        num_questions = request.form.get("num_questions", type=int)  # số câu hỏi mỗi đề
        num_exams = request.form.get("num_exams", type=int) or 1      # số lượng đề cần tạo, mặc định 1

        # Nếu không có file Excel thì xử lý như cũ (checkbox chọn câu hỏi)
        if not file:
            cur.execute("INSERT INTO exams (title, duration_minutes, competition_id) VALUES (%s, %s, %s)", (title, duration_minutes, comp_id))
            exam_id = cur.lastrowid

            question_ids = request.form.getlist('question_ids')
            scores = request.form.getlist('scores')
            for qid, score in zip(question_ids, scores):
                cur.execute("INSERT INTO exam_questions (exam_id, question_id, score) VALUES (%s, %s, %s)",
                            (exam_id, qid, score,))
            mysql.connection.commit()
            flash("✅ Đã tạo đề thi mới từ câu hỏi có sẵn", "success")
            return redirect(url_for('competition_exams', comp_id=comp_id))

        # Nếu có file Excel tải lên
        import pandas as pd
        df = pd.read_excel(file)

        expected_cols = ["content", "option_a", "option_b", "option_c", "option_d", "correct_option", "score"]
        if not all(col in df.columns for col in expected_cols):
            flash(f"⚠ File Excel phải có các cột: {', '.join(expected_cols)}", "error")
            return redirect(url_for('admin_exams'))

        for i in range(num_exams):  # tạo nhiều đề
            exam_title = f"{title} - Đề {i+1}" if num_exams > 1 else title
            cur.execute("INSERT INTO exams (title, duration_minutes, competition_id) VALUES (%s, %s, %s)", (exam_title, duration_minutes,comp_id))
            exam_id = cur.lastrowid

            # Random số lượng câu hỏi cho đề
            if num_questions and num_questions > 0 and num_questions < len(df):
                df_sample = df.sample(n=num_questions)  # random khác nhau mỗi lần
            else:
                df_sample = df.copy()
            inserted_ids = []
            for _, row in df_sample.iterrows():
                cur.execute("""
                    SELECT id FROM questions 
                    WHERE content=%s AND option_a=%s AND option_b=%s AND option_c=%s AND option_d=%s AND correct_option=%s
                """, (row['content'], row['option_a'], row['option_b'], row['option_c'], row['option_d'], row['correct_option']))
                result = cur.fetchone()
                if result:
                    q_id = result[0]
                else:
                    cur.execute("""
                        INSERT INTO questions (content, option_a, option_b, option_c, option_d, correct_option)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        row["content"], row["option_a"], row["option_b"],
                        row["option_c"], row["option_d"], row["correct_option"]
                    ))
                    q_id = cur.lastrowid
                inserted_ids.append((q_id, row["score"]))

            # Gắn câu hỏi vào đề thi
            for q_id, score in inserted_ids:
                cur.execute("INSERT INTO exam_questions (exam_id, question_id, score) VALUES (%s, %s, %s)",
                            (exam_id, q_id, score))

        mysql.connection.commit()
        flash(f"✅ Đã tạo {num_exams} đề thi mới từ file Excel!", "success")

    cur.execute("SELECT * FROM questions")
    questions = cur.fetchall()
    cur.execute("SELECT * FROM exams")
    exams = cur.fetchall()
    cur.close()
    return render_template('admin/exams.html', questions=questions, exams=exams)

#Thêm câu hỏi vào đề thi
@app.route('/admin/competitions/<int:comp_id>/exams/<int:exam_id>/add_questions', methods=['GET', 'POST'])
@login_required
def add_questions_to_exam(comp_id, exam_id):
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        question_ids = request.form.getlist('question_ids')
        scores = request.form.getlist('scores')
        for qid, score in zip(question_ids, scores):
            cur.execute("INSERT IGNORE INTO exam_questions (exam_id, question_id, score) VALUES (%s, %s, %s)", (exam_id, qid, score))
        mysql.connection.commit()
        flash('Đã thêm câu hỏi vào đề thi.', 'success')
        return redirect(url_for('add_questions_to_exam', exam_id=exam_id, comp_id=comp_id))

    cur.execute("SELECT * FROM questions WHERE id NOT IN (SELECT question_id FROM exam_questions WHERE exam_id = %s)", (exam_id,))
    available_questions = cur.fetchall()
    cur.execute("SELECT * FROM exams WHERE id = %s", (exam_id,))
    exam = cur.fetchone()
    cur.execute("SELECT q.id, q.content, eq.score FROM questions q JOIN exam_questions eq ON q.id = eq.question_id WHERE eq.exam_id = %s", (exam_id,))
    assigned_questions = cur.fetchall()
    cur.close()
    return render_template('admin/add_questions_to_exam.html', exam=exam, questions=available_questions, assigned_questions=assigned_questions, comp_id=comp_id)

# Xóa câu hỏi khỏi đề thi (câu hỏi vẫn lưu trong ngân hàng)
@app.route('/admin/exams/<int:exam_id>/remove_question/<int:question_id>')
@login_required
def remove_question_from_exam(exam_id, question_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM exam_questions WHERE exam_id = %s AND question_id = %s", (exam_id, question_id))
    mysql.connection.commit()
    cur.close()
    flash('Đã xóa câu hỏi khỏi đề thi.', 'success')
    return redirect(url_for('add_questions_to_exam', exam_id=exam_id))

# Xem chi tiết đề thi
@app.route('/admin/exams/<int:exam_id>')
@login_required
def view_exam_detail(exam_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT title FROM exams WHERE id = %s", (exam_id,))
    exam = cur.fetchone()
    cur.execute("SELECT q.id, q.content, eq.score FROM questions q JOIN exam_questions eq ON q.id = eq.question_id WHERE eq.exam_id = %s", (exam_id,))
    questions = cur.fetchall()
    cur.close()
    return render_template('admin/view_exam.html', exam_id=exam_id, title=exam[0], questions=questions)

#Chỉnh sửa thông tin đề thi
@app.route('/admin/competitions/<int:comp_id>/exams/<int:exam_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_exam(comp_id, exam_id):
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        title = request.form['title']
        duration = request.form['duration']
        cur.execute("UPDATE exams SET title = %s, duration_minutes = %s WHERE id = %s", (title, duration, exam_id))
        mysql.connection.commit()
       # Cập nhật điểm từng câu hỏi trong đề thi nếu có dữ liệu
        for key in request.form:
            if key.startswith("score_"):
                qid = key.replace("score_", "")
                score = request.form[key]
                cur.execute("UPDATE exam_questions SET score = %s WHERE exam_id = %s AND question_id = %s",
                            (score, exam_id, qid))
        mysql.connection.commit()
        cur.close()
        flash('Cập nhật đề thi thành công!', 'success')
        return redirect(url_for('competition_exams'))
    cur.execute("SELECT * FROM exams WHERE id = %s", (exam_id,))
    exam = cur.fetchone()
    cur.execute("SELECT q.id, q.content, eq.score FROM questions q JOIN exam_questions eq ON q.id = eq.question_id WHERE eq.exam_id = %s", (exam_id,))
    exam_questions = cur.fetchall()
    cur.close()
    return render_template('admin/edit_exam.html', exam=exam, comp_id=comp_id)

# Xem kết quả
@app.route('/admin/competitions/<int:comp_id>/exam/<int:exam_id>/view_result')
@login_required
def view_result(comp_id, exam_id):
    results = []
    cur = mysql.connection.cursor()
    cur.execute('SELECT title FROM exams WHERE id = %s', (exam_id,))
    exam_title = cur.fetchone()[0]
    cur.execute('SELECT c.name, c.rank, c.unit, s.submitted_at, s.score FROM submissions s JOIN candidates c ON s.candidate_id = c.id WHERE exam_id = %s', (exam_id,))
    results_raw = cur.fetchall()
    for r in results_raw:
        results.append({
            "name":r[0],
            "rank":r[1],
            "unit": r[2],
            "exam_title": exam_title,
            "submitted_at": r[3],
            "score": r[4]
        })
    mysql.connection.commit()
    cur.close()
    return render_template('list_results.html', results=results, comp_id=comp_id)

#Cập nhật thời gian cho đề thi
@app.route('/admin/exams/<int:exam_id>/update_time', methods=['POST'])
@login_required
def update_time(exam_id):
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        duration_minutes = request.form['duration_minutes']
        cur.execute('UPDATE exams SET duration_minutes = %s WHERE id = %s',(duration_minutes, exam_id,))
        flash('Cập nhập thời gian thành công!!!')
    cur.close()
    return redirect(url_for('add_questions_to_exam', exam_id=exam_id))

@app.route('/admin/exams/<int:exam_id>/update_assigned_questions', methods=['POST'])
@login_required
def update_assigned_questions(exam_id):
    cur = mysql.connection.cursor()
    # Lấy danh sách câu hỏi của đề thi
    cur.execute("SELECT question_id FROM exam_questions WHERE exam_id = %s", (exam_id,))
    question_ids = cur.fetchall()

    for q in question_ids:
        qid = q['question_id']
        new_score = request.form.get(f'score_{qid}')
        if new_score is not None:
            cur.execute("""
                UPDATE exam_questions SET score = %s
                WHERE exam_id = %s AND question_id = %s
            """, (new_score, exam_id, qid))
    mysql.connection.commit()
    cur.close()    
    return redirect(url_for('add_questions_to_exam', exam_id=exam_id))

# Xóa đề thi
@app.route('/admin/exams/<int:exam_id>/delete', methods=['POST'])
@login_required
def delete_exam(exam_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM exam_questions WHERE exam_id = %s", (exam_id,))
    cur.execute("DELETE FROM exams WHERE id = %s", (exam_id,))
    mysql.connection.commit()
    cur.close()
    flash('Đã xóa đề thi!', 'success')
    return redirect(url_for('competition_exams'))

#Xem kết quả thi
@app.route('/admin/competitions/<int:comp_id>/results')
@login_required
def admin_results(comp_id):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT c.name, c.rank, c.unit, e.title, s.id, s.submitted_at, s.score
        FROM submissions s
        JOIN candidates c ON s.candidate_id = c.id
        JOIN exams e ON s.exam_id = e.id
        WHERE s.competition_id = %s
        ORDER BY s.submitted_at DESC
    """, (comp_id,))
    results = [
        {
            'name': row[0], 'rank': row[1], 'unit': row[2], 'id': row[4],
            'exam_title': row[3], 'submitted_at': row[5], 'score': row[6]
        } for row in cur.fetchall()
    ]
    cur.close()
    return render_template('admin/results.html', results=results)

# Xóa kết quả thi
@app.route('/admin/results/delete/<int:submission_id>', methods=['POST'])
@login_required
def delete_result(submission_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM submissions WHERE id = %s", (submission_id,))
    mysql.connection.commit()
    cur.close()
    flash('Đã xóa kết quả thi!', 'success')
    return redirect(url_for('admin_results'))

# Xóa tất cả kết quả thi
@app.route('/admin/results/delete_all', methods=['POST'])
@login_required
def delete_all_results():
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM submissions")  # Xóa toàn bộ kết quả
    mysql.connection.commit()
    cur.close()
    flash('Đã xóa toàn bộ lịch sử thi!', 'success')
    return redirect(url_for('admin_results'))

# @app.route("/exam_list/<int:candidate_id>")
# @login_required
# def exam_list(candidate_id):
#     cur = mysql.connection.cursor()
#     # Lấy tên thí sinh
#     cur.execute("SELECT full_name FROM candidates WHERE id = %s", (candidate_id,))
#     candidate = cur.fetchone()

#     # Lấy danh sách đề thi
#     cur.execute("SELECT id, title FROM exams")
#     exams = cur.fetchall()
#     cur.close()

#     return render_template(
#         "exam_list.html",
#         candidate_name=candidate[0] if candidate else "",
#         candidate_id=candidate_id,
#         exams=exams
#     )

# Xóa tất cả câu hỏi trong ngân hàng
@app.route('/admin/questions/delete_all', methods=['POST'])
@login_required
def delete_all_questions():
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM questions")  # Xóa toàn bộ câu hỏi
    mysql.connection.commit()
    cur.close()
    flash('Đã xóa toàn bộ câu hỏi!', 'success')
    return redirect(url_for('admin_questions'))

# xem chi tiết kết quả thi
@app.route('/submission_detail/<int:submission_id>')
@login_required
def submission_detail(submission_id):
    cursor = mysql.connection.cursor()
    
    # Lấy thông tin chung
    cursor.execute("""
        SELECT s.id, s.submitted_at, s.score,
               c.name, c.rank, c.unit,
               e.title AS exam_title
        FROM submissions s
        JOIN candidates c ON s.candidate_id = c.id
        JOIN exams e ON s.exam_id = e.id
        WHERE s.id = %s
    """, (submission_id,))
    submission = cursor.fetchone()
    # Lấy chi tiết trả lời
    cursor.execute("""
        SELECT q.content, q.option_a, q.option_b, q.option_c, q.option_d,
               q.correct_option,
               sa.selected_option, sa.is_correct, sa.score_earned
        FROM submission_answers sa
        JOIN questions q ON sa.question_id = q.id
        WHERE sa.submission_id = %s
    """, (submission_id,))
    answers_ori = cursor.fetchall()
    # Chuyển biến None thành "Không chọn"
    answers = ()
    for a in answers_ori:
        a_list = list(a)
        if a_list[6] == None:
            a_list[6] = "Không chọn"
        a_tuple = tuple(a_list)
        answers = answers + (a_tuple,)

    cursor.close()
    return render_template("admin/submission_detail.html",
                           submission=submission,
                           answers=answers)

# Xuất kết quả thi ra file excel
@app.route('/submission_detail/<int:submission_id>/export_excel')
@login_required
def export_submission_excel(submission_id):
    cursor = mysql.connection.cursor()

    # Lấy thông tin chung
    cursor.execute("""
        SELECT s.id, s.submitted_at, s.score,
               c.name, c.rank, c.unit,
               e.title AS exam_title
        FROM submissions s
        JOIN candidates c ON s.candidate_id = c.id
        JOIN exams e ON s.exam_id = e.id
        WHERE s.id = %s
    """, (submission_id,))
    submission = cursor.fetchone()

    # Lấy chi tiết trả lời
    cursor.execute("""
        SELECT q.content, q.option_a, q.option_b, q.option_c, q.option_d,
               q.correct_option,
               sa.selected_option, sa.is_correct, sa.score_earned
        FROM submission_answers sa
        JOIN questions q ON sa.question_id = q.id
        WHERE sa.submission_id = %s
    """, (submission_id,))
    answers = cursor.fetchall()
    cursor.close()

    # Tạo file Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Kết quả bài thi"

    # Thông tin chung
    ws.append(["Thí sinh:", submission[3]])
    ws.append(["Đề thi:", submission[6]])
    ws.append(["Thời gian nộp:", str(submission[1])])
    ws.append(["Điểm tổng:", submission[2]])
    ws.append([])

    # Tiêu đề bảng
    ws.append(["TT","Câu hỏi", "Đáp án A", "Đáp án B", "Đáp án C", "Đáp án D", "Đáp án đúng", "Đã chọn", "Điểm"])

    # Nội dung câu hỏi
    for index, a in enumerate(answers):
        ws.append([
            index, 
            a[0],  # Câu hỏi
            a[1],  # A
            a[2],  # B
            a[3],  # C
            a[4],  # D
            a[5],  # Đáp án đúng
            a[6] if a[7] else "Không chọn",  # Đã chọn
            a[8]   # Điểm
        ])

    # Xuất ra file
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=f"ket_qua_bai_thi_{submission_id}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# Xóa tất cả đề thi
@app.route('/admin/exams/delete_all', methods=['POST'])
@login_required
def delete_all_exams():
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM exams")   # Xóa tất cả đề thi
    mysql.connection.commit()
    cur.close()
    flash("Đã xóa tất cả đề thi thành công!", "success")
    return redirect(url_for('competition_exams'))

# ---------- USER ----------
@app.route('/')
def index():
    return render_template('register_candidate.html')
# đăng kí thi
@app.route('/register_candidate', methods=['GET', 'POST'])
def register_candidate(candidate_id=None):
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        candidate_name = request.form['name']
        rank = request.form['rank']
        position = request.form['position']
        unit = request.form['unit']
        cur.execute('INSERT INTO candidates (name, `rank`, position, unit) VALUES (%s, %s, %s, %s)', (candidate_name, rank, position, unit))
        candidate_id = cur.lastrowid
        mysql.connection.commit()
    if request.method == 'GET':
        candidate_id = request.args.get("candidate_id", None)
    cur.execute("SELECT id, title FROM exams")
    exams = cur.fetchall()
    cur.close()
    return render_template('select_exam.html', exams=exams, candidate_id = candidate_id)


# chọn đề thi
@app.route('/do_exam/<int:exam_id>/candidate/<int:candidate_id>', methods=['POST'])
def do_exam(exam_id, candidate_id):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT id FROM submissions
        WHERE exam_id = %s AND candidate_id = %s
        LIMIT 1""",(exam_id, candidate_id))
    existing = cur.fetchone()
    if existing:
        flash("Bạn đã làm đề thi này rồi, mỗi thí sinh chỉ được làm một lần.")
        return redirect(url_for("register_candidate", candidate_id=candidate_id))
    cur.execute('SELECT duration_minutes FROM exams WHERE id = %s', (exam_id,))
    duration = cur.fetchone()[0]
    cur.execute('SELECT * FROM questions q JOIN exam_questions eq ON q.id = eq.question_id WHERE eq.exam_id = %s', (exam_id, ))
    questions = cur.fetchall()
    cur.close()
    if request.method == 'POST':
        candidate_id = request.form['candidate_id']
    return render_template('exam.html', duration = duration, questions = questions, candidate_id = candidate_id, exam_id = exam_id)

# Nộp bài
@app.route('/submit', methods=['POST'])
def submit_exam():
    candidate_id = request.form['candidate_id']
    exam_id = request.form['exam_id']
    answers = request.form.to_dict()

    correct_t = 0
    total = 0

    cur = mysql.connection.cursor()
    cur.execute("SELECT SUM(score) FROM exam_questions WHERE exam_id = %s", (exam_id,))
    total = round(cur.fetchone()[0],2)
    cur.execute("SELECT name FROM candidates WHERE id = %s",(candidate_id,))
    candidate_name = cur.fetchone()[0]
    cur.execute("SELECT q.id, q.correct_option, eq.score FROM questions q JOIN exam_questions eq ON q.id = eq.question_id WHERE eq.exam_id = %s", (exam_id,))
    correct_answers = cur.fetchall()
    for item in correct_answers:
        qid = item[0]
        correct_option = item[1]
        score = item[2]
        if answers.get(f'q{qid}') == correct_option:
            correct_t += score

    cur.execute("INSERT INTO submissions (candidate_id, exam_id, submitted_at, score) VALUES (%s, %s, %s, %s)",
                (candidate_id, exam_id, datetime.now(), correct_t))
    submission_id = cur.lastrowid
    question_details = []
    cur.execute("SELECT q.id, q.content, q.option_a, q.option_b, q.option_c, q.option_d, q.correct_option, eq.score FROM questions q JOIN exam_questions eq ON q.id = eq.question_id WHERE eq.exam_id = %s", (exam_id,))
    questions = cur.fetchall()
    total_score = 0
    for q in questions:
        qid = str(q[0])
        selected = request.form.get(f'q{qid}')  # Ví dụ: name="question_3"
        correct = q[6]
        is_correct = (selected == correct)
        score_earned = q[7] if is_correct else 0
        total_score += score_earned

        #Lưu câu trả lời vào submission_answers
        cur.execute("INSERT INTO submission_answers (submission_id, question_id, selected_option, is_correct, score_earned) VALUES (%s, %s, %s, %s, %s)", (submission_id, qid, selected, is_correct, score_earned))

        # Chuẩn bị dữ liệu hiển thị
        question_details.append({
            'content': q[1],
            'option_a': q[2],
            'option_b': q[3],
            'option_c': q[4],
            'option_d': q[5],
            'correct_option': correct,
            'selected_option': selected,
            'is_correct': is_correct,
            'score': q[7]
        })
    mysql.connection.commit()
    cur.close()

    return render_template('result.html', score=round(correct_t,2), total= total, candidate_name = candidate_name, candidate_id=candidate_id, questions=question_details)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)