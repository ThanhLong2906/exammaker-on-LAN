# exam_system/server/app.py
from flask import Blueprint, request, session, jsonify
from extensions_n import mysql
from utils_n.decorators_n import login_required
import logging
logging.basicConfig(level="DEBUG")
subjects_bp = Blueprint("subjects_bp", __name__)
# Tạo môn học
@subjects_bp.route("/admin/subjects/create", methods=["POST"])
@login_required
def create_subject():
    data = request.get_json()
    logging.INFO(f"data: {data}")    
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

# Xóa môn học
@subjects_bp.route("/admin/subjects/delete", methods=["POST"])
@login_required
def delete_subject():
    data = request.get_json()
    subject_id = data.get("subject_id")

    cur = mysql.connection.cursor()

    try:
        if subject_id:
            # ❌ Xóa môn → câu hỏi tự xóa nhờ CASCADE
            cur.execute("DELETE FROM subjects WHERE id = %s", (subject_id,))
            msg = "Đã xóa môn học và toàn bộ câu hỏi thuộc môn!"
        else:
            # ❌ Xóa tất cả môn → xóa tất cả câu hỏi
            cur.execute("DELETE FROM subjects")
            msg = "Đã xóa toàn bộ môn học và toàn bộ câu hỏi!"

        mysql.connection.commit()
        return jsonify(success=True, message=msg)

    except Exception as e:
        mysql.connection.rollback()
        return jsonify(success=False, message=str(e))

    finally:
        cur.close()