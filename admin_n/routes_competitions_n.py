# exam_system/server/app.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash
from flask import send_file, jsonify, send_from_directory
import openpyxl
from io import BytesIO
from extensions_n import mysql
from utils_n.decorators_n import login_required, role_required
import logging

logging.basicConfig(level=logging.DEBUG)
competitions_bp = Blueprint("competitions_bp", __name__)

# =========================== QUẢN LÝ CUỘC THI =============================
# Xem danh sách cuộc thi 
@competitions_bp.route("/admin/competitions")
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
@competitions_bp.route("/admin/competitions/create", methods=["GET", "POST"])
@login_required
def create_competition():
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
        return redirect(url_for("competitions_bp.competitions"))

    return render_template("admin/create_competition.html")

# danh sách thí sinh của một cuộc thi
@competitions_bp.route("/admin/competitions/<int:comp_id>/candidates")
@login_required
def manage_candidates(comp_id):
    cur = mysql.connection.cursor()

    # Check quyền admin
    if session["admin_role"] != "superadmin":
        cur.execute("SELECT created_by FROM competitions WHERE id=%s", (comp_id,))
        owner = cur.fetchone()
        if not owner or owner["created_by"] != session["admin_id"]:
            return "Bạn không có quyền!", 403

    cur.execute("SELECT * FROM candidates WHERE competition_id=%s", (comp_id,))
    candidates = cur.fetchall()
    cur.close()
    return render_template("admin/candidates.html", candidates=candidates, comp_id=comp_id)

# Thêm thí sinh vào cuộc thi
@competitions_bp.route("/admin/competitions/<int:comp_id>/candidates/add", methods=["POST"])
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

# tải file mẫu danh sách thí sinh 
@competitions_bp.route("/admin/download-candidate-template")
@login_required
def download_candidate_template():
    return send_from_directory(
        directory="static/templates_excel",
        path="mau_dang_ky_thi_sinh.xlsx",
        as_attachment=True
    )

# import danh sách thí sinh từ file excel
@competitions_bp.route("/admin/competitions/<int:comp_id>/candidates/import", methods=["POST"])
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
            INSERT INTO candidates (name, `rank`, position, unit, username, password_hash, competition_id, created_by)
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
@competitions_bp.route("/admin/candidates/delete", methods=["POST"])
@login_required
def delete_candidate():
    cid = request.json.get("candidate_id")

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM candidates WHERE id=%s LIMIT 1", (cid,))
    mysql.connection.commit()
    cur.close()

    return {"status": "success"}

# đổi mật khẩu thí sinh
@competitions_bp.route("/admin/candidates/change_password", methods=["POST"])
@login_required
def change_password():
    cid = request.json.get("id")
    new_password= request.json.get("password")
    cur = mysql.connection.cursor()
    new_hash = generate_password_hash(new_password)
    cur.execute('UPDATE candidates SET password_hash=%s, session_version = session_version + 1 WHERE id=%s',
                    (new_hash, cid,))
    mysql.connection.commit()
    cur.close()
    
    return {"status": "success", "message": "Đổi mật khẩu thành công"}

# Danh sách đề thi theo cuộc thi
@competitions_bp.route("/admin/competitions/<int:comp_id>/exams")
@login_required
def competition_exams(comp_id):
    cur = mysql.connection.cursor()

    # kiểm tra quyền
    if session["admin_role"] != "superadmin":
        cur.execute("SELECT created_by FROM competitions WHERE id=%s", (comp_id,))
        owner = cur.fetchone()
        if not owner or owner["created_by"] != session["admin_id"]:
            return "Bạn không có quyền xem cuộc thi này!", 403

    cur.execute("SELECT * FROM exams WHERE competition_id=%s", (comp_id,))
    exams = cur.fetchall()
    cur.close()

    return render_template("admin/list_exams.html", exams=exams, comp_id=comp_id)

# tải file mẫu tạo đề thi 
@competitions_bp.route("/admin/download-exams-template")
@login_required
def download_exams_template():
    return send_from_directory(
        directory="static/templates_excel",
        path="mau_tao_de_thi.xlsx",
        as_attachment=True
    )

# Tạo đề thi mới
@competitions_bp.route('/admin/competitions/<int:comp_id>/exams/add', methods=['GET', 'POST'])
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
            return redirect(url_for('competitions_bp.competition_exams', comp_id=comp_id))

        # Nếu có file Excel tải lên
        import pandas as pd
        df = pd.read_excel(file)

        expected_cols = ["content", "option_a", "option_b", "option_c", "option_d", "correct_option", "score"]
        if not all(col in df.columns for col in expected_cols):
            flash(f"⚠ File Excel phải có các cột: {', '.join(expected_cols)}", "error")
            return redirect(url_for('competitions_bp.admin_exams'))

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
                    q_id = result["id"]
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
@competitions_bp.route('/admin/competitions/<int:comp_id>/exams/<int:exam_id>/add_questions', methods=['GET', 'POST'])
@login_required
def add_questions_to_exam(comp_id, exam_id):
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        question_ids = request.form.getlist('question_ids')
        # scores = request.form.get('scores')

        for qid in question_ids:
            score = request.form.get(f'score_{qid}')
            cur.execute("INSERT IGNORE INTO exam_questions (exam_id, question_id, score) VALUES (%s, %s, %s)", (exam_id, qid, score))
        mysql.connection.commit()
        flash('Đã thêm câu hỏi vào đề thi.', 'success')
        return redirect(url_for('competitions_bp.add_questions_to_exam', exam_id=exam_id, comp_id=comp_id))

    cur.execute("SELECT * FROM questions WHERE id NOT IN (SELECT question_id FROM exam_questions WHERE exam_id = %s)", (exam_id,))
    available_questions = cur.fetchall()
    cur.execute("SELECT * FROM exams WHERE id = %s", (exam_id,))
    exam = cur.fetchone()
    
    cur.execute("SELECT q.id, q.content, eq.score FROM questions q JOIN exam_questions eq ON q.id = eq.question_id WHERE eq.exam_id = %s", (exam_id,))
    assigned_questions = cur.fetchall()
    cur.close()
    return render_template('admin/add_questions_to_exam.html', exam=exam, questions=available_questions, assigned_questions=assigned_questions, comp_id=comp_id)

# Xóa câu hỏi khỏi đề thi (câu hỏi vẫn lưu trong ngân hàng)
@competitions_bp.route('/admin/competitions/<int:comp_id>/exams/<int:exam_id>/remove_question/<int:question_id>')
@login_required
def remove_question_from_exam(comp_id, exam_id, question_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM exam_questions WHERE exam_id = %s AND question_id = %s", (exam_id, question_id))
    mysql.connection.commit()
    cur.close()
    flash('Đã xóa câu hỏi khỏi đề thi.', 'success')
    return redirect(url_for('competitions_bp.add_questions_to_exam', comp_id = comp_id, exam_id=exam_id))

# Xem chi tiết đề thi
@competitions_bp.route('/admin/exams/<int:exam_id>')
@login_required
def view_exam_detail(exam_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT title FROM exams WHERE id = %s", (exam_id,))
    exam = cur.fetchone()
    cur.execute("SELECT q.id, q.content, eq.score FROM questions q JOIN exam_questions eq ON q.id = eq.question_id WHERE eq.exam_id = %s", (exam_id,))
    questions = cur.fetchall()
    cur.close()
    return render_template('admin/view_exam.html', exam_id=exam_id, title=exam["title"], questions=questions)

#Chỉnh sửa thông tin đề thi
@competitions_bp.route('/admin/competitions/<int:comp_id>/exams/<int:exam_id>/edit', methods=['GET', 'POST'])
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
        return redirect(url_for('competitions_bp.competition_exams', comp_id=comp_id))
    cur.execute("SELECT * FROM exams WHERE id = %s", (exam_id,))
    exam = cur.fetchone()
    cur.execute("SELECT q.id, q.content, eq.score FROM questions q JOIN exam_questions eq ON q.id = eq.question_id WHERE eq.exam_id = %s", (exam_id,))
    exam_questions = cur.fetchall()
    cur.close()
    return render_template('admin/edit_exam.html', exam=exam, comp_id=comp_id)

# Xem kết quả
@competitions_bp.route('/admin/competitions/<int:comp_id>/exam/<int:exam_id>/view_result')
@login_required
def view_result(comp_id, exam_id):
    results = []
    cur = mysql.connection.cursor()
    cur.execute('SELECT title FROM exams WHERE id = %s', (exam_id,))
    exam_title = cur.fetchone()['title']
    cur.execute('SELECT c.name, c.rank, c.unit, s.submitted_at, s.score FROM submissions s JOIN candidates c ON s.candidate_id = c.id WHERE exam_id = %s', (exam_id,))
    results_raw = cur.fetchall()
    for r in results_raw:
        results.append({
            "name":r['name'],
            "rank":r['rank'],
            "unit": r['unit'],
            "exam_title": exam_title,
            "submitted_at": r['submitted_at'],
            "score": r['score']
        })
    mysql.connection.commit()
    cur.close()
    return render_template('list_results.html', results=results, comp_id=comp_id)

#Cập nhật thời gian cho đề thi
@competitions_bp.route('/admin/competitions/<int:comp_id>/exams/<int:exam_id>/update_time', methods=['POST'])
@login_required
def update_time(comp_id, exam_id):
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        duration_minutes = request.form['duration_minutes']
        cur.execute('UPDATE exams SET duration_minutes = %s WHERE id = %s',(duration_minutes, exam_id,))
        flash('Cập nhập thời gian thành công!!!')
    cur.close()
    return redirect(url_for('competitions_bp.add_questions_to_exam', comp_id=comp_id, exam_id=exam_id))

@competitions_bp.route('/admin/competitions/<int:comp_id>/exams/<int:exam_id>/update_assigned_questions', methods=['POST'])
@login_required
def update_assigned_questions(comp_id, exam_id):
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
    return redirect(url_for('competitions_bp.add_questions_to_exam', comp_id=comp_id, exam_id=exam_id))

# Xóa đề thi
@competitions_bp.route('/admin/competitions/<int:comp_id>/exams/<int:exam_id>/delete', methods=['POST'])
@login_required
def delete_exam(comp_id, exam_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM exam_questions WHERE exam_id = %s", (exam_id,))
    cur.execute("DELETE FROM exams WHERE id = %s", (exam_id,))
    mysql.connection.commit()
    cur.close()
    flash('Đã xóa đề thi!', 'success')
    return redirect(url_for('competitions_bp.competition_exams', comp_id=comp_id))

#Xem kết quả thi
@competitions_bp.route('/admin/competitions/<int:comp_id>/results')
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
            'name': row['name'], 'rank': row['rank'], 'unit': row['unit'], 'id': row['id'],
            'exam_title': row['title'], 'submitted_at': row['submitted_at'], 'score': row['score']
        } for row in cur.fetchall()
    ]
    cur.close()
    return render_template('admin/results.html', comp_id = comp_id, results=results)

# cập nhật kết quả thi
@competitions_bp.route('/admin/competitions/<int:comp_id>/results/json')
@login_required
def admin_results_json(comp_id):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT c.name, c.rank, c.unit, e.title, s.id, s.submitted_at, s.score
        FROM submissions s
        JOIN candidates c ON s.candidate_id = c.id
        JOIN exams e ON s.exam_id = e.id
        WHERE s.competition_id = %s
        ORDER BY s.submitted_at DESC
    """, (comp_id,))

    results = [{
        "id": row["id"],
        "name": row["name"],
        "rank": row["rank"],
        "unit": row["unit"],
        "exam_title": row["title"],
        "submitted_at": row["submitted_at"].strftime("%d/%m/%Y %H:%M:%S"),
        "score": row["score"]
    } for row in cur.fetchall()]

    cur.close()
    return {"results": results}

# Xóa kết quả thi
@competitions_bp.route('/admin/competitions/<int:comp_id>/results/delete/<int:submission_id>', methods=['POST'])
@login_required
def delete_result(comp_id, submission_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM submissions WHERE id = %s", (submission_id,))
    mysql.connection.commit()
    cur.close()
    flash('Đã xóa kết quả thi!', 'success')
    return redirect(url_for('competitions_bp.admin_results', comp_id=comp_id))

# Xóa tất cả kết quả thi
@competitions_bp.route('/admin/competitions/<int:comp_id>/results/delete_all', methods=['POST'])
@login_required
def delete_all_results(comp_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM submissions")  # Xóa toàn bộ kết quả
    mysql.connection.commit()
    cur.close()
    flash('Đã xóa toàn bộ lịch sử thi!', 'success')
    return redirect(url_for('competitions_bp.admin_results', comp_id=comp_id))

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

# xem chi tiết kết quả thi
@competitions_bp.route('/submission_detail/<int:submission_id>')
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
    answers = cursor.fetchall()
    # Chuyển biến None thành "Không chọn"
    # answers = ()
    for answer in answers:
        
        if answer['selected_option'] == None:
            answer['selected_option'] = "Không chọn"
        # answers = answers + (a_tuple,)
    cursor.close()
    return render_template("admin/submission_detail.html",
                           submission=submission,
                           answers=answers)

# Xuất kết quả thi ra file excel
@competitions_bp.route('/submission_detail/<int:submission_id>/export_excel')
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
    ws.append(["Thí sinh:", submission['name']])
    ws.append(["Đề thi:", submission['exam_title']])
    ws.append(["Thời gian nộp:", str(submission['submitted_at'])])
    ws.append(["Điểm tổng:", submission['score']])
    ws.append([])

    # Tiêu đề bảng
    ws.append(["TT","Câu hỏi", "Đáp án A", "Đáp án B", "Đáp án C", "Đáp án D", "Đáp án đúng", "Đã chọn", "Điểm"])

    # Nội dung câu hỏi
    for index, a in enumerate(answers):
        ws.append([
            index, 
            a['content'],  # Câu hỏi
            a['option_a'],  # A
            a['option_b'],  # B
            a['option_c'],  # C
            a['option_d'],  # D
            a['correct_option'],  # Đáp án đúng
            a['selected_option'] if a['is_correct'] else "Không chọn",  # Đã chọn
            a['score_earned']   # Điểm
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
@competitions_bp.route('/admin/exams/delete_all', methods=['POST'])
@login_required
def delete_all_exams():
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM exams")   # Xóa tất cả đề thi
    mysql.connection.commit()
    cur.close()
    flash("Đã xóa tất cả đề thi thành công!", "success")
    return redirect(url_for('competitions_bp.competition_exams'))

#Gán đề thi cho thí sinh
@competitions_bp.route('/admin/competitions/<int:competition_id>/assign-exams')
@login_required
def assign_exam_page(competition_id):
    cur = mysql.connection.cursor()

    # Thí sinh + đề đã gán (nếu có)
    cur.execute("""
        SELECT 
            c.id AS candidate_id,
            c.name,
            c.rank,
            c.position,
            c.unit,
            ea.exam_id,
            e.title AS exam_title
        FROM candidates c
        LEFT JOIN exam_assignments ea
            ON c.id = ea.candidate_id AND ea.competition_id = %s
        LEFT JOIN exams e ON ea.exam_id = e.id
        WHERE c.competition_id = %s
        ORDER BY c.name
    """, (competition_id, competition_id))
    candidates = cur.fetchall()
    # Kiểm tra thí sinh đã làm ;bài
    for candidate in candidates:
        cur.execute("""
            SELECT id
            FROM submissions
            WHERE candidate_id=%s
            AND competition_id=%s
            LIMIT 1
        """, (candidate['candidate_id'], competition_id))

        submitted = cur.fetchone()

        if submitted:
            candidate['submitted'] = True
            
    # Danh sách đề trong cuộc thi
    cur.execute("""
        SELECT id, title
        FROM exams
        WHERE competition_id = %s
    """, (competition_id,))
    exams = cur.fetchall()

    cur.close()

    return render_template(
        "admin/assign_exam_by_candidate.html",
        candidates=candidates,
        exams=exams,
        competition_id=competition_id
    )

# AJAX gán đề thi
@competitions_bp.route('/admin/assign-exam/ajax', methods=['POST'])
@login_required
def assign_exam_ajax():
    data = request.get_json()
    competition_id = data.get("competition_id")
    candidate_id = data.get("candidate_id")
    exam_id = data.get("exam_id")

    cur = mysql.connection.cursor()

    # Nếu chọn "-- Chưa gán đề thi" → xóa gán
    if not exam_id:
        cur.execute("""
            DELETE FROM exam_assignments
            WHERE competition_id=%s AND candidate_id=%s
        """, (competition_id, candidate_id))
        mysql.connection.commit()
        cur.close()
        return jsonify(success=True)

    # Upsert (gán hoặc cập nhật)
    cur.execute("""
        INSERT INTO exam_assignments (competition_id, candidate_id, exam_id)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE exam_id = VALUES(exam_id)
    """, (competition_id, candidate_id, exam_id))

    mysql.connection.commit()
    cur.close()

    return jsonify(success=True)

#Tự động gán đề thi - thí sinh
@competitions_bp.route('/admin/assign-exam/auto', methods=['POST'])
@login_required
def auto_assign_exam():
    data = request.get_json()
    competition_id = data.get("competition_id")
    cur = mysql.connection.cursor()

    # 1. Lấy danh sách thí sinh
    cur.execute("""
        SELECT id FROM candidates
        WHERE competition_id = %s
    """, (competition_id,))
    candidates = cur.fetchall()

    if not candidates:
        return jsonify(success=False, message="Không có thí sinh")

    # Kiểm tra thí sinh đã làm ;bài
    for candidate in candidates:
        cur.execute("""
            SELECT id
            FROM submissions
            WHERE candidate_id=%s
            AND competition_id=%s
            LIMIT 1
        """, (candidate['id'], competition_id))

        submitted = cur.fetchone()

        if submitted:
            candidate['submitted'] = True

    # 2. Lấy danh sách đề
    cur.execute("""
        SELECT id 
        FROM exams e
        WHERE competition_id = %s
    """, (competition_id,))
    exams = cur.fetchall()

    if not exams:
        return jsonify(success=False, message="Cuộc thi chưa có đề thi")

    import random

    exam_ids = [e["id"] for e in exams]
    print(f"candidates: {candidates}")
    # 3. Gán đề random
    i = 0
    for c in candidates:
        if not 'submitted' in c:
            exam_id = random.choice(exam_ids)

            cur.execute("""
                INSERT INTO exam_assignments (competition_id, candidate_id, exam_id)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE exam_id = VALUES(exam_id)
            """, (competition_id, c["id"], exam_id))
            print(i)
            i+=1

    mysql.connection.commit()
    cur.close()

    return jsonify(success=True)


