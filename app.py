import csv
import io
import os
import sqlite3
import smtplib
import ssl
from email.message import EmailMessage
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, session, Response)
from werkzeug.security import check_password_hash, generate_password_hash
from classifier import classify_complaint

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-before-deployment")
DB_PATH = os.path.join(os.path.dirname(__file__), "complaints.db")

# Demo credentials. Set ADMIN_USERNAME and ADMIN_PASSWORD environment variables before use.
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

CATEGORIES = [
    "Academics", "Infrastructure", "IT & Wi-Fi", "Water & Sanitation",
    "Canteen & Food", "Hostel", "Transport", "Administration", "Other"
]
STATUSES = ["Pending", "In Progress", "Resolved"]
PRIORITIES = ["Low", "Medium", "High"]

# Configure these with real department email addresses via environment variables.
DEPARTMENT_EMAILS = {
    "Academics": os.environ.get("ACADEMICS_EMAIL", "").strip(),
    "Infrastructure": os.environ.get("INFRASTRUCTURE_EMAIL", "").strip(),
    "IT & Wi-Fi": os.environ.get("IT_EMAIL", "").strip(),
    "Water & Sanitation": os.environ.get("SANITATION_EMAIL", "").strip(),
    "Canteen & Food": os.environ.get("CANTEEN_EMAIL", "").strip(),
    "Hostel": os.environ.get("HOSTEL_EMAIL", "").strip(),
    "Transport": os.environ.get("TRANSPORT_EMAIL", "").strip(),
    "Administration": os.environ.get("ADMINISTRATION_EMAIL", "").strip(),
    "Other": os.environ.get("OTHER_EMAIL", "").strip(),
}


def send_department_email(complaint_id, student_name, student_email,
                          complaint_text, category, priority, created_at):
    """Send a new complaint to the configured department using SMTP."""
    recipient = DEPARTMENT_EMAILS.get(category, "")
    smtp_host = os.environ.get("SMTP_HOST", "").strip()
    smtp_user = os.environ.get("SMTP_USERNAME", "").strip()
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    from_address = os.environ.get("SMTP_FROM", smtp_user).strip()
    try:
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    except ValueError:
        return "failed: invalid SMTP_PORT", recipient

    if not recipient:
        return "not_configured: department email", ""
    if not smtp_host or not from_address:
        return "not_configured: SMTP settings", recipient

    message = EmailMessage()
    message["Subject"] = f"CampusCare complaint #{complaint_id}: {category} ({priority} priority)"
    message["From"] = from_address
    message["To"] = recipient
    if student_email:
        message["Reply-To"] = student_email
    message.set_content(
        f"A new complaint was submitted through CampusCare.\n\n"
        f"Complaint ID: #{complaint_id}\n"
        f"Category: {category}\n"
        f"Priority: {priority}\n"
        f"Submitted: {created_at}\n"
        f"Student: {student_name}\n"
        f"Student email: {student_email or 'Not provided'}\n\n"
        f"Complaint details:\n{complaint_text}\n\n"
        "Please review this complaint in the CampusCare admin dashboard."
    )
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            if smtp_user:
                server.login(smtp_user, smtp_password)
            server.send_message(message)
        return "sent", recipient
    except Exception as exc:
        app.logger.exception("Department email failed for complaint #%s", complaint_id)
        return f"failed: {type(exc).__name__}", recipient



def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name TEXT NOT NULL,
                student_email TEXT,
                department TEXT,
                complaint_text TEXT NOT NULL,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                created_at TEXT NOT NULL,
                confidence REAL DEFAULT 0,
                updated_at TEXT,
                feedback_rating INTEGER,
                feedback_comment TEXT,
                anonymous INTEGER NOT NULL DEFAULT 0,
                email_status TEXT DEFAULT 'not_attempted',
                email_recipient TEXT
            )
        """)
        # Migrate an older version of the project database without deleting records.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(complaints)")}
        migrations = {
            "confidence": "ALTER TABLE complaints ADD COLUMN confidence REAL DEFAULT 0",
            "updated_at": "ALTER TABLE complaints ADD COLUMN updated_at TEXT",
            "feedback_rating": "ALTER TABLE complaints ADD COLUMN feedback_rating INTEGER",
            "feedback_comment": "ALTER TABLE complaints ADD COLUMN feedback_comment TEXT",
            "anonymous": "ALTER TABLE complaints ADD COLUMN anonymous INTEGER NOT NULL DEFAULT 0",
            "email_status": "ALTER TABLE complaints ADD COLUMN email_status TEXT DEFAULT 'not_attempted'",
            "email_recipient": "ALTER TABLE complaints ADD COLUMN email_recipient TEXT",
        }
        for col, sql in migrations.items():
            if col not in columns:
                conn.execute(sql)
        conn.execute("UPDATE complaints SET updated_at = created_at WHERE updated_at IS NULL")


def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("Please log in to access the admin dashboard.", "error")
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapped


@app.route("/")
def index():
    return render_template("index.html", categories=CATEGORIES)


@app.route("/submit", methods=["POST"])
def submit():
    name = request.form.get("student_name", "").strip()
    email = request.form.get("student_email", "").strip()
    department = request.form.get("department", "").strip()
    complaint = request.form.get("complaint_text", "").strip()
    anonymous = request.form.get("anonymous") == "on"

    if not complaint or len(complaint) < 8:
        flash("Please enter a complaint with at least 8 characters.", "error")
        return redirect(url_for("index"))
    if not anonymous and not name:
        flash("Enter your name or select anonymous submission.", "error")
        return redirect(url_for("index"))

    if anonymous:
        name, email = "Anonymous", ""
    category, priority, confidence = classify_complaint(complaint)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        cur = conn.execute("""
            INSERT INTO complaints
            (student_name, student_email, department, complaint_text, category, priority,
             status, created_at, confidence, updated_at, anonymous)
            VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?, ?, ?, ?)
        """, (name, email, department, complaint, category, priority, now,
              confidence, now, int(anonymous)))
        complaint_id = cur.lastrowid

    email_status, email_recipient = send_department_email(
        complaint_id, name, email, complaint, category, priority, now
    )
    with get_db() as conn:
        conn.execute(
            "UPDATE complaints SET email_status = ?, email_recipient = ? WHERE id = ?",
            (email_status, email_recipient, complaint_id)
        )

    return render_template("submitted.html", complaint_id=complaint_id,
                           category=category, priority=priority,
                           confidence=round(confidence * 100),
                           email_status=email_status,
                           email_recipient=email_recipient)


@app.route("/track", methods=["GET", "POST"])
def track():
    complaint = None
    searched = False
    if request.method == "POST":
        searched = True
        raw_id = request.form.get("complaint_id", "").strip()
        if raw_id.isdigit():
            with get_db() as conn:
                complaint = conn.execute("""
                    SELECT id, category, priority, status, created_at, complaint_text,
                           feedback_rating, feedback_comment
                    FROM complaints WHERE id = ?
                """, (int(raw_id),)).fetchone()
    return render_template("track.html", complaint=complaint, searched=searched)


@app.route("/feedback/<int:complaint_id>", methods=["POST"])
def feedback(complaint_id):
    raw_rating = request.form.get("rating", "")
    comment = request.form.get("comment", "").strip()[:1000]
    if raw_rating not in {"1", "2", "3", "4", "5"}:
        flash("Please select a rating from 1 to 5.", "error")
        return redirect(url_for("track"))
    with get_db() as conn:
        row = conn.execute("SELECT status FROM complaints WHERE id = ?", (complaint_id,)).fetchone()
        if not row:
            flash("Complaint not found.", "error")
        elif row["status"] != "Resolved":
            flash("Feedback is available after a complaint is resolved.", "error")
        else:
            conn.execute("""
                UPDATE complaints SET feedback_rating = ?, feedback_comment = ?
                WHERE id = ?
            """, (int(raw_rating), comment, complaint_id))
            flash("Thanks! Your feedback has been saved.", "success")
    return redirect(url_for("track"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin"))
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        # Environment-based password is compared directly for simple demo setup.
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session.clear()
            session["admin_logged_in"] = True
            session["admin_username"] = username
            flash("Welcome back, administrator.", "success")
            return redirect(request.args.get("next") or url_for("admin"))
        flash("Incorrect username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def admin():
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    priority = request.args.get("priority", "").strip()
    status = request.args.get("status", "").strip()
    date_range = request.args.get("range", "").strip()

    clauses, params = [], []
    if search:
        clauses.append("(CAST(id AS TEXT) LIKE ? OR student_name LIKE ? OR complaint_text LIKE ? OR department LIKE ?)")
        term = f"%{search}%"
        params.extend([term, term, term, term])
    if category in CATEGORIES:
        clauses.append("category = ?")
        params.append(category)
    if priority in PRIORITIES:
        clauses.append("priority = ?")
        params.append(priority)
    if status in STATUSES:
        clauses.append("status = ?")
        params.append(status)
    if date_range in {"today", "week", "month"}:
        now = datetime.now()
        if date_range == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif date_range == "week":
            start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        clauses.append("created_at >= ?")
        params.append(start.strftime("%Y-%m-%d %H:%M:%S"))

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with get_db() as conn:
        complaints = conn.execute(
            "SELECT * FROM complaints" + where + " ORDER BY id DESC", params
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'").fetchone()[0]
        progress = conn.execute("SELECT COUNT(*) FROM complaints WHERE status='In Progress'").fetchone()[0]
        resolved = conn.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'").fetchone()[0]
        high = conn.execute("SELECT COUNT(*) FROM complaints WHERE priority='High'").fetchone()[0]
        avg_rating = conn.execute("SELECT AVG(feedback_rating) FROM complaints WHERE feedback_rating IS NOT NULL").fetchone()[0]
        category_rows = conn.execute(
            "SELECT category, COUNT(*) AS count FROM complaints GROUP BY category ORDER BY count DESC"
        ).fetchall()
        status_rows = conn.execute(
            "SELECT status, COUNT(*) AS count FROM complaints GROUP BY status"
        ).fetchall()
        priority_rows = conn.execute(
            "SELECT priority, COUNT(*) AS count FROM complaints GROUP BY priority"
        ).fetchall()
        avg_resolution = conn.execute("""
            SELECT AVG((julianday(updated_at)-julianday(created_at))*24)
            FROM complaints WHERE status='Resolved' AND updated_at IS NOT NULL
        """).fetchone()[0]

    chart_data = {
        "categories": [r["category"] for r in category_rows],
        "categoryCounts": [r["count"] for r in category_rows],
        "statuses": [r["status"] for r in status_rows],
        "statusCounts": [r["count"] for r in status_rows],
        "priorities": [r["priority"] for r in priority_rows],
        "priorityCounts": [r["count"] for r in priority_rows],
    }
    return render_template(
        "admin.html", complaints=complaints, total=total, pending=pending,
        progress=progress, resolved=resolved, high=high, avg_rating=avg_rating,
        avg_resolution=avg_resolution, chart_data=chart_data,
        categories=CATEGORIES, priorities=PRIORITIES, statuses=STATUSES,
        filters={"q": search, "category": category, "priority": priority,
                 "status": status, "range": date_range}
    )


@app.route("/admin/update/<int:complaint_id>", methods=["POST"])
@admin_required
def update_status(complaint_id):
    status = request.form.get("status", "")
    if status not in STATUSES:
        flash("Invalid status.", "error")
        return redirect(url_for("admin"))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        conn.execute("UPDATE complaints SET status = ?, updated_at = ? WHERE id = ?",
                     (status, now, complaint_id))
    flash(f"Complaint #{complaint_id} updated to {status}.", "success")
    return redirect(url_for("admin", **request.args))


@app.route("/admin/export.csv")
@admin_required
def export_csv():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, student_name, student_email, department, complaint_text, category,
                   priority, status, created_at, updated_at, confidence, feedback_rating,
                   feedback_comment, anonymous
            FROM complaints ORDER BY id DESC
        """).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Student", "Email", "Department", "Complaint", "Category",
                     "Priority", "Status", "Created At", "Updated At",
                     "Model Confidence", "Feedback Rating", "Feedback Comment", "Anonymous"])
    for row in rows:
        writer.writerow(list(row))
    return Response(
        "\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=campuscare_complaints.csv"}
    )


@app.route("/about")
def about():
    return render_template("about.html")


init_db()

if __name__ == "__main__":
    app.run(debug=True)
