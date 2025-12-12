from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
from flask_mysqldb import MySQL
import os 

app = Flask(__name__, template_folder="templates")
app.secret_key = os.urandom(24)

# Cấu hình kết nối MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '1234'
app.config['MYSQL_DB'] = 'exam_system'

mysql = MySQL(app)

def get_units_tree():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT unit_id, unit_name, parent_id FROM units ORDER BY unit_name")
    rows = cursor.fetchall()
    tree = []
    lookup = {}
    units_dict = []
    for idx, row in enumerate(rows):
        units_dict.append({})
        units_dict[idx]["unit_id"] = row[0]
        units_dict[idx]["unit_name"] = row[1]
        units_dict[idx]["parent_id"] = row[2]
        units_dict[idx]["children"] = []
        # row["children"] = []
        lookup[row[0]] = units_dict[idx]

    for unit_dict in units_dict:
        if unit_dict["parent_id"] is None:
            tree.append(unit_dict)
        else:
            lookup[unit_dict["parent_id"]]["children"].append(unit_dict)
    return tree
