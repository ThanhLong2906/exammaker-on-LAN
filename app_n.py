# exam_system/server/app.py
from flask import Flask 
from config_n import Config
from extensions_n import mysql

# import blueprint
from admin_n.routes_auth_n import auth_bp
from admin_n.routes_admin_n import admins_bp
from admin_n.routes_competitions_n import competitions_bp
from admin_n.routes_dashboard_n import dashboard_bp
from admin_n.routes_questions_n import questions_bp
from admin_n.routes_subjects_n import subjects_bp
from admin_n.routes_units_n import units_bp
from admin_n.routes_users_n import candidates_bp

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)

    mysql.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admins_bp)
    app.register_blueprint(competitions_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(questions_bp)
    app.register_blueprint(subjects_bp)
    app.register_blueprint(units_bp)
    app.register_blueprint(candidates_bp)
    
    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)