# exam_system/server/app.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import pandas as pd
from utils_n.decorators_n import login_required, role_required
from extensions_n import mysql
import logging
import ast

logging.basicConfig(level="DEBUG")
questions_bp = Blueprint("questions_bp", __name__)

#============================== QUẢN LÝ NGÂN HÀNG CÂU HỎI ==================================
# Ngân hàng câu hỏi (on dashboard)
@questions_bp.route('/admin/questions', methods=['GET', 'POST'])
@login_required
@role_required("superadmin", "admin")
def admin_questions():
    cur = mysql.connection.cursor()
    subject_filter = request.args.get("subject_filter")
    if request.method == 'POST':
        subject_id = session.get("active_subject_id")
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
            count = cur.fetchone()["COUNT(*)"]
            if count > 0:
                flash("⚠ Câu hỏi này đã tồn tại trong ngân hàng!", "error")
                mysql.connection.commit()
                cur.close()
                return redirect(url_for('questions_bp.admin_questions'))
            else:
                cur.execute("INSERT INTO questions (content, option_a, option_b, option_c, option_d, correct_option, created_by, subject_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                            (content, a, b, c, d, correct, session["admin_id"], subject_id))
                mysql.connection.commit()
                flash('Thêm câu hỏi thành công!', 'success')
                return redirect(url_for('questions_bp.admin_questions'))

    if session['admin_role'] == "superadmin":
        cur.execute("SELECT * FROM subjects")
    else:
        cur.execute("SELECT * FROM subjects WHERE created_by = %s", (session['admin_id'],))
    subjects = cur.fetchall()
    return render_template('admin/questions.html', subjects=subjects)
# tìm kiếm câu hỏi
@questions_bp.route('/question_list')
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
@questions_bp.route("/admin/subjects/create", methods=["POST"])
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
@questions_bp.route("/admin/questions/import", methods=["POST"])
@login_required
def import_questions():
    cur = mysql.connection.cursor()
    subject_id = request.form.get("subject_id")
    if 'excel_file' not in request.files:
        flash("Không tìm thấy file tải lên.")
        return redirect(url_for('questions_bp.admin_questions'))

    file = request.files['excel_file']
    if file.filename == '':
        flash("Chưa chọn file Excel.")
        return redirect(url_for('questions_bp.admin_questions'))
    
    try:
        # Đọc dữ liệu từ Excel
        df = pd.read_excel(file)
        
        # Yêu cầu file Excel có cột: question_text, option_a, option_b, option_c, option_d, correct_answer
        expected_columns = ["content", "option_a", "option_b", "option_c", "option_d", "correct_option"]
        if not all(col in df.columns for col in expected_columns):
            flash(f"File Excel phải có các cột: {', '.join(expected_columns)}")
            return redirect(url_for('questions_bp.admin_questions'))
        for _, row in df.iterrows():
            # Kiểm tra câu hỏi trùng lặp trong ngân hàng câu hỏi
            cur.execute("SELECT COUNT(*) FROM questions WHERE content = %s AND option_a = %s AND option_b = %s AND option_c = %s AND option_d = %s AND correct_option = %s AND created_by = %s",
                        (row['content'],row['option_a'],row['option_b'],row['option_c'],row['option_d'],row['correct_option'], session['admin_id']))
            count = cur.fetchone()["COUNT(*)"]
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

    return redirect(url_for('questions_bp.admin_questions'))

# Chỉnh sửa câu hỏi
@questions_bp.route('/admin/questions/edit/<int:question_id>', methods=['GET', 'POST'])
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
@questions_bp.route('/admin/questions/delete/<int:question_id>', methods=['POST'])
@login_required
def delete_question(question_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM questions WHERE id=%s", (question_id,))
    mysql.connection.commit()
    cur.close()
    flash('Xóa câu hỏi thành công!', 'success')
    return redirect(url_for('admin_questions'))

# Xóa tất cả câu hỏi trong ngân hàng
@questions_bp.route('/admin/questions/delete_all', methods=['POST'])
@login_required
def delete_all_questions():
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM questions")  # Xóa toàn bộ câu hỏi
    mysql.connection.commit()
    cur.close()
    flash('Đã xóa toàn bộ câu hỏi!', 'success')
    return redirect(url_for('admin_questions'))

#Lọc câu hỏi theo môn
@questions_bp.route("/admin/questions/api", methods= ['POST'])
@login_required
def api_questions():
    cur = mysql.connection.cursor()

    subject_filter = request.json.get("subjectFilter")
    subject_filter = ast.literal_eval(subject_filter)
    query = "SELECT * FROM questions WHERE 1=1"
    params = []

    if subject_filter and not isinstance(subject_filter, tuple):
        query += " AND subject_id = %s"
        params.append(subject_filter)
    elif subject_filter:
        ids = []
        for s in subject_filter:
            ids.append(s['id'])
        query += " AND subject_id IN %s"
        params.append(tuple(ids))
    cur.execute(query, params)
    data = cur.fetchall()
    cur.close()
    return jsonify(data)

# nhận subject_id khi chọn
@questions_bp.route("/admin/questions/set_active_subject", methods=["POST"])
@login_required
def set_active_subject():
    data = request.get_json()
    subject_id = data.get("subject_id")

    session["active_subject_id"] = subject_id

    return jsonify({
        "status": "success",
        "subject_id": subject_id
    })