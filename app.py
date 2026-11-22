import os
import sqlite3
import secrets
import csv
import io
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, abort
from werkzeug.security import check_password_hash, generate_password_hash

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(APP_DIR, "players.db"))
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ChangeThisAdminPassword")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                jersey_no TEXT NOT NULL,
                jersey_size TEXT NOT NULL,
                shorts_size TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(24)
    return session["_csrf"]

@app.context_processor
def inject_csrf():
    return {"csrf_token": csrf_token}

@app.before_request
def protect_posts():
    if request.method == "POST":
        submitted = request.form.get("csrf_token", "")
        expected = session.get("_csrf", "")
        if not expected or not secrets.compare_digest(submitted, expected):
            abort(400, "Invalid form token. Refresh the page and try again.")

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapped

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        jersey_no = request.form.get("jersey_no", "").strip()
        jersey_size = request.form.get("jersey_size", "").strip()
        shorts_size = request.form.get("shorts_size", "").strip()
        if not all([name, jersey_no, jersey_size, shorts_size]):
            flash("Please fill in every field.", "error")
        elif len(name) > 80 or len(jersey_no) > 10:
            flash("Please check the name and jersey number.", "error")
        else:
            with db() as conn:
                conn.execute(
                    "INSERT INTO players (name, jersey_no, jersey_size, shorts_size) VALUES (?, ?, ?, ?)",
                    (name, jersey_no, jersey_size, shorts_size)
                )
            flash("Your HFC jersey details have been submitted!", "success")
            return redirect(url_for("home"))
    return render_template("index.html")

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        # Password is supplied through the hosting environment; never stored in the database.
        if secrets.compare_digest(password, ADMIN_PASSWORD):
            session.clear()
            session["admin_logged_in"] = True
            session["_csrf"] = secrets.token_urlsafe(24)
            return redirect(url_for("dashboard"))
        flash("Incorrect admin password.", "error")
    return render_template("login.html")

@app.route("/dashboard")
@admin_required
def dashboard():
    search = request.args.get("q", "").strip()
    with db() as conn:
        if search:
            rows = conn.execute(
                "SELECT * FROM players WHERE name LIKE ? OR jersey_no LIKE ? ORDER BY id DESC",
                (f"%{search}%", f"%{search}%")
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM players ORDER BY id DESC").fetchall()
    return render_template("dashboard.html", players=rows, search=search)

@app.route("/admin/edit/<int:player_id>", methods=["GET", "POST"])
@admin_required
def edit_player(player_id):
    with db() as conn:
        player = conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
        if player is None:
            abort(404)
        if request.method == "POST":
            values = (
                request.form.get("name", "").strip(),
                request.form.get("jersey_no", "").strip(),
                request.form.get("jersey_size", "").strip(),
                request.form.get("shorts_size", "").strip()
            )
            if not all(values):
                flash("Please fill in every field.", "error")
            else:
                conn.execute(
                    "UPDATE players SET name=?, jersey_no=?, jersey_size=?, shorts_size=? WHERE id=?",
                    (*values, player_id)
                )
                flash("Player details updated.", "success")
                return redirect(url_for("dashboard"))
    return render_template("edit.html", player=player)

@app.route("/admin/delete/<int:player_id>", methods=["POST"])
@admin_required
def delete_player(player_id):
    with db() as conn:
        conn.execute("DELETE FROM players WHERE id = ?", (player_id,))
    flash("Player registration deleted.", "success")
    return redirect(url_for("dashboard"))

@app.route("/admin/export")
@admin_required
def export_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Jersey No", "Jersey Size", "Shorts Size", "Submitted"])
    with db() as conn:
        rows = conn.execute(
            "SELECT name, jersey_no, jersey_size, shorts_size, created_at FROM players ORDER BY id"
        ).fetchall()
    for row in rows:
        writer.writerow(list(row))
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=hfc_jersey_players.csv"}
    )

@app.route("/logout", methods=["POST"])
@admin_required
def logout():
    session.clear()
    return redirect(url_for("admin_login"))

init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
