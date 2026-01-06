# exam_system/server/app.py
from functools import wraps
from flask import Blueprint, request, session, jsonify
from utils_n.decorators_n import login_required, role_required
from extensions_n import mysql

units_bp = Blueprint("units_bp", __name__)

# Tạo đơn vị
@units_bp.route("/admin/create_unit", methods=["POST"])
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
@units_bp.route("/admin/delete_unit", methods=["POST"])
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
@units_bp.route("/admin/set_active_unit", methods=["POST"])
@login_required
@role_required("superadmin")
def set_active_unit():
    data = request.get_json()
    if not data or "unit_id" not in data:
        return {"status": "error", "message": "Missing unit_id"}, 400
    session["active_unit"] = data.get("unit_id")
    return {"status": "ok"}