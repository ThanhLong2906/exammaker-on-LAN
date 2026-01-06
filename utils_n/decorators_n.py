# exam_system/server/app.py
from functools import wraps
from flask import request, redirect, url_for, session, flash
from extensions_n import mysql

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash("Vui lòng đăng nhập để tiếp tục.", "warning")
            return redirect(url_for('auth_bp.admin_login', next=request.url))
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
                return redirect(url_for("auth_bp.admin_login", next=request.url))
            if user_role not in allowed_roles:
                flash("Bạn không có quyền truy cập trang này.", "danger")
                return redirect(url_for('dashboard_bp.admin_dashboard'))
            return func(*args, **kwargs)
        return wrapper
    return decorator

def candidate_login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("candidate_logged_in"):
            return redirect(url_for("auth_bp.candidate_login"))
        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT session_version FROM candidates WHERE id=%s",
            (session['candidate_id'],)
        )
        row = cur.fetchone()
        cur.close()

        if not row or row['session_version'] != session.get('candidate_session_version'):
            session.clear()
            flash("⚠ Tài khoản đã đăng nhập ở nơi khác", "warning")
            return redirect(url_for('auth_bp.candidate_login'))
        return f(*args, **kwargs)
    return wrapper