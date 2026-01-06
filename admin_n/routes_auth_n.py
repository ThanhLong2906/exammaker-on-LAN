# exam_system/server/app.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, make_response
from extensions_n import mysql

from werkzeug.security import check_password_hash

auth_bp= Blueprint("auth_bp", __name__)

@auth_bp.route('/login/admin', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('dashboard_bp.admin_dashboard'))

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
            if user['status'] == "locked":
                flash("Tài khoản đã bị khóa!", "danger")
                return redirect(url_for("admin_login"))

            if check_password_hash(user["password_hash"], password):
                session.clear()
                session['admin_logged_in'] = True
                session['admin_id'] = user['id'] # id
                session['admin_username'] = user['username'] # username
                session['admin_role'] = user['role'] # role
                session['admin_unit_id'] = user["unit_id"] # unit_id
                next_url = request.args.get('next') or url_for('dashboard_bp.admin_dashboard')
                return redirect(next_url)
            else:
                error = "Sai mật khẩu."

    return render_template('admin/login.html', error=error)


@auth_bp.route('/logout/admin')
def admin_logout():
    session.clear()
    response = make_response(redirect(url_for('auth_bp.admin_login')))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@auth_bp.route("/login", methods=["GET", "POST"])
def candidate_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT * FROM candidates WHERE username=%s",
            (username,)
        )
        candidate = cur.fetchone()

        if not candidate or not check_password_hash(candidate["password_hash"], password):
            flash("Tên đăng nhập hoặc mật khẩu không đúng", "danger")
            return redirect(url_for("auth_bp.candidate_login"))

        # update session version
        cur.execute("""
                UPDATE candidates
                SET session_version = session_version + 1
                WHERE id = %s
            """, (candidate["id"],))
        mysql.connection.commit()

        cur.execute("SELECT session_version FROM candidates WHERE id=%s", (candidate["id"],))
        version = cur.fetchone()['session_version'] 

        # Lưu session
        session.clear()
        session["candidate_logged_in"] = True
        session["candidate_id"] = candidate["id"]
        session["candidate_name"] = candidate["name"]
        session['candidate_session_version'] = version

        return redirect(url_for("candidates_bp.dashboard"))

    return render_template("candidate/login.html")