# exam_system/server/app.py
from flask import Blueprint, render_template
from utils_n.decorators_n import login_required, role_required

dashboard_bp = Blueprint("dashboard_bp", __name__)

# dashboard
@dashboard_bp.route('/admin')
@login_required
@role_required("superadmin", "admin")
def admin_dashboard():
    return render_template('admin/dashboard.html')