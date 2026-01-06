# exam_system/server/app.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from MySQLdb.cursors import DictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from utils import get_units_tree
from utils_n.decorators_n import login_required, role_required
from extensions_n import mysql

admins_bp = Blueprint("admins_bp", __name__)
# ======================= THÔNG TIN CÁ NHÂN ==================================
# đổi mật khẩu
@admins_bp.route("/admin/change_password_admin", methods=["GET", "POST"])
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
            return redirect(url_for("admins_bp.admin_change_password"))

        # Kiểm tra mật khẩu trùng
        if new_password != confirm_password:
            flash("Mật khẩu mới không khớp!", "danger")
            return redirect(url_for("admins_bp.admin_change_password"))

        # Cập nhật mật khẩu
        new_hash = generate_password_hash(new_password)
        cursor.execute("UPDATE admin_users SET password_hash=%s WHERE id=%s",
                       (new_hash, session["admin_id"]))
        mysql.connection.commit()

        flash("Đổi mật khẩu thành công!", "success")
        return redirect(url_for("dashboard_bp.admin_dashboard"))

    return render_template("admin/change_password.html")
# ======================= QUẢN LÝ NGƯỜI DÙNG =================================
# Quản trị người dùng
@admins_bp.route("/admin/user_management")
@login_required
@role_required("superadmin")
def user_management():
    units_tree = get_units_tree()
    return render_template("admin/user_management.html", units_tree=units_tree)

#lấy danh sách tài khoản thuộc 1 đơn vị
@admins_bp.route("/admin/get_users/<int:unit_id>")
@login_required
@role_required("superadmin")
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
@admins_bp.route("/admin/create_user", methods=["GET", "POST"])
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
        return redirect(url_for("dashboard_bp.admin_dashboard"))

    return render_template("admin/create_user.html")

# đổi mật khẩu user
@admins_bp.route("/admin/change_password", methods=["POST"])
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
@admins_bp.route("/admin/toggle_user_status", methods=["POST"])
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
@admins_bp.route("/admin/delete_user", methods=["POST"])
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

