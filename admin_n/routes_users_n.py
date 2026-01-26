# exam_system/server/app.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime
from extensions_n import mysql
from utils_n.decorators_n import candidate_login_required
candidates_bp = Blueprint("candidates_bp", __name__)
# ---------- USER ----------
# @users_bp.route('/')
# def index():
#     return render_template('register_candidate.html')
# # đăng kí thi
# @users_bp.route('/register_candidate', methods=['GET', 'POST'])
# def register_candidate(candidate_id=None):
#     cur = mysql.connection.cursor()
#     if request.method == 'POST':
#         candidate_name = request.form['name']
#         rank = request.form['rank']
#         position = request.form['position']
#         unit = request.form['unit']
#         cur.execute('INSERT INTO candidates (name, `rank`, position, unit) VALUES (%s, %s, %s, %s)', (candidate_name, rank, position, unit))
#         candidate_id = cur.lastrowid
#         mysql.connection.commit()
#     if request.method == 'GET':
#         candidate_id = request.args.get("candidate_id", None)
#     cur.execute("SELECT id, title FROM exams")
#     exams = cur.fetchall()
#     cur.close()
#     return render_template('select_exam.html', exams=exams, candidate_id = candidate_id)

# chọn đề thi
@candidates_bp.route('/candidate/do_exam/<int:comp_id>', methods=['POST'])
def do_exam(comp_id):
    cur = mysql.connection.cursor()
    candidate_id = session["candidate_id"]
    cur.execute("""
        SELECT id FROM submissions
        WHERE competition_id = %s AND candidate_id = %s
        LIMIT 1""",(comp_id, candidate_id))
    existing = cur.fetchone()
    if existing:
        flash("Bạn đã làm đề thi này rồi, mỗi thí sinh chỉ được làm một lần.")
        return redirect(url_for("candidates_bp.dashboard"))
    # cur.execute('SELECT duration_minutes FROM exams WHERE id = %s', (exam_id,))
    cur.execute("SELECT e.duration_minutes, e.id FROM exams e JOIN exam_assignments ea ON e.id = ea.exam_id WHERE ea.candidate_id = %s AND ea.competition_id = %s", (candidate_id, comp_id))
    exam = cur.fetchone()
    duration = exam['duration_minutes']
    exam_id = exam['id']
    cur.execute('SELECT * FROM questions q JOIN exam_questions eq ON q.id = eq.question_id WHERE eq.exam_id = %s', (exam_id, ))
    questions = cur.fetchall()
    cur.close()
    if request.method == 'POST':
        candidate_id = request.form.get('candidate_id')
    return render_template('candidate/exam.html', duration = duration, questions = questions, candidate_id = candidate_id, exam_id = exam_id, comp_id=comp_id)

@candidates_bp.route("/")
@candidate_login_required
def dashboard():
    candidate_id = session["candidate_id"]

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT 
            c.id AS competition_id,
            c.title AS competition_name
        FROM competitions c 
        JOIN exam_assignments ea ON ea.competition_id = c.id
        WHERE ea.candidate_id = %s
    """, (candidate_id,))

    competitions = cur.fetchall()
    cur.close()
    return render_template(
        "candidate/dashboard.html",
        competitions=competitions
    )

# Nộp bài
@candidates_bp.route('/submit/comp_id/<int:comp_id>', methods=['POST'])
def submit_exam(comp_id):
    candidate_id = session['candidate_id']
    exam_id = request.form.get('exam_id')
    answers = request.form.to_dict()

    correct_t = 0
    total = 0

    cur = mysql.connection.cursor()
    cur.execute("SELECT SUM(score) FROM exam_questions WHERE exam_id = %s", (exam_id,))
    total = round(cur.fetchone()['SUM(score)'],2)
    cur.execute("SELECT name FROM candidates WHERE id = %s",(candidate_id,))
    candidate_name = cur.fetchone()['name']
    cur.execute("SELECT q.id, q.correct_option, eq.score FROM questions q JOIN exam_questions eq ON q.id = eq.question_id WHERE eq.exam_id = %s", (exam_id,))
    correct_answers = cur.fetchall()
    for item in correct_answers:
        qid = item['id']
        correct_option = item['correct_option']
        score = item['score']
        if answers.get(f'q{qid}') == correct_option:
            correct_t += score

    cur.execute("INSERT INTO submissions (candidate_id, exam_id, submitted_at, score, competition_id) VALUES (%s, %s, %s, %s, %s)",
                (candidate_id, exam_id, datetime.now(), correct_t, int(comp_id)))
    submission_id = cur.lastrowid
    question_details = []
    cur.execute("SELECT q.id, q.content, q.option_a, q.option_b, q.option_c, q.option_d, q.correct_option, eq.score FROM questions q JOIN exam_questions eq ON q.id = eq.question_id WHERE eq.exam_id = %s", (exam_id,))
    questions = cur.fetchall()
    total_score = 0
    for q in questions:
        qid = str(q['id'])
        selected = request.form.get(f'q{qid}')  # Ví dụ: name="question_3"
        correct = q['correct_option']
        is_correct = (selected == correct)
        score_earned = q['score'] if is_correct else 0
        total_score += score_earned

        #Lưu câu trả lời vào submission_answers
        cur.execute("INSERT INTO submission_answers (submission_id, question_id, selected_option, is_correct, score_earned) VALUES (%s, %s, %s, %s, %s)", (submission_id, qid, selected, is_correct, score_earned))

        # Chuẩn bị dữ liệu hiển thị
        question_details.append({
            'content': q['content'],
            'option_a': q['option_a'],
            'option_b': q['option_b'],
            'option_c': q['option_c'],
            'option_d': q['option_d'],
            'correct_option': correct,
            'selected_option': selected,
            'is_correct': is_correct,
            'score': q['score']
        })
    mysql.connection.commit()
    cur.close()

    return render_template('candidate/result.html', score=round(correct_t,2), total= total, candidate_name = candidate_name, candidate_id=candidate_id, questions=question_details)

# Nhận vi phạm
@candidates_bp.route("/candidate/violation", methods=["POST"])
def candidate_violation():
    data = request.get_json()
    reason = data.get("reason")

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO exam_violations (candidate_id, reason)
        VALUES (%s, %s)
    """, (session["candidate_id"], reason))
    mysql.connection.commit()
    cur.close()

    return jsonify({"status": "ok"})
