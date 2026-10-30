import csv
import hmac
import io
import os
import secrets
from datetime import date, timedelta
from typing import Optional

from flask import (Flask, Response, flash, g, redirect, render_template,
                   request, session, url_for)

import auth
import db
from categories import CATEGORY_COLORS, CATEGORY_NAMES
from utils import (format_money, month_bounds, parse_amount_cents,
                   parse_category, parse_date_iso)

app = Flask(__name__)
app.secret_key = auth.load_secret_key()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("HTTPS_ONLY") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(days=14),
)

_hops = int(os.environ.get("TRUSTED_PROXY_HOPS", "0"))
if _hops:
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for= _hops, x_proto= _hops, x_host=_hops)

app.jinja_env.filters["money"] = format_money
app.jinja_env.filters["cat_color"] = lambda c: CATEGORY_COLORS.get(c, "#6B7268")

login_limiter = auth.Limiter(max_hits=5, window_seconds=300) 
signup_limiter = auth.Limiter(max_hits=10, window_seconds=3600)



def get_conn():
    if "conn" not in g:
        g.conn = db.connect()
    return g.conn


@app.teardown_appcontext
def close_conn(exc):
    conn = g.pop("conn", None)
    if conn is not None:
        conn.close()


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token

PUBLIC_ENDPOINTS = {"login", "signup"}


def _safe_next(target):
    """Only allow same-site relative paths (blocks open redirects)."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return url_for("index")


@app.before_request
def guard():
    g.user = None
    if request.endpoint == "static":
        return None

    if request.method == "POST":
        sent = request.form.get("csrf_token", "").encode()
        expected = session.get("csrf", "").encode()
        if not expected or not hmac.compare_digest(sent, expected):
            flash("Your session expired. Please try again.", "error")
            return redirect(url_for("login"))

    user_id = session.get("user_id")
    if user_id:
        g.user = db.get_user(get_conn(), user_id)
        if g.user is None:
            session.clear()

    if g.user is None and request.endpoint not in PUBLIC_ENDPOINTS and request.endpoint is not None:
        if request.method == "GET":
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        return redirect(url_for("login"))
    return None


@app.after_request
def no_store(resp):
    if getattr(g, "user", None):
        resp.headers["Cache-Control"] = "no-store"
    return resp


def start_session(user_id):
    session.clear()
    session.permanent = True
    session["user_id"] = user_id


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("index"))
    nxt = request.values.get("next", "")
    username = ""
    if request.method == "POST":
        ip = request.remote_addr or "?"
        username = request.form.get("username", "").strip()
        wait = login_limiter.locked_for(ip)
        if wait:
            flash(f"Too many attempts. Try again in {wait // 60 + 1} min.", "error")
        else:
            user = db.get_user_by_name(get_conn(), username)
            if auth.check_password(user["password_hash"] if user else None,
                                   request.form.get("password", "")):
                login_limiter.reset(ip)
                start_session(user["id"])
                return redirect(_safe_next(nxt))
            login_limiter.record(ip)
            flash("Incorrect username or password.", "error")
    return render_template("login.html", next=nxt, username=username,
                           signup_open=auth.signup_enabled())


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if g.user:
        return redirect(url_for("index"))
    if not auth.signup_enabled():
        flash("Sign-ups are currently closed.", "error")
        return redirect(url_for("login"))
    username = ""
    if request.method == "POST":
        ip = request.remote_addr or "?"
        username = request.form.get("username", "").strip()
        wait = signup_limiter.locked_for(ip)
        if wait:
            flash(f"Too many attempts. Try again in {wait // 60 + 1} min.", "error")
        else:
            signup_limiter.record(ip)
            password = request.form.get("password", "")
            if "confirm" not in request.form:
                error = "This page is out of date. Refresh it (Ctrl+Shift+R) and try again."
            else:
                error = auth.validate_signup(username, password, request.form["confirm"])
            if not error:
                try:
                    user_id = db.create_user(get_conn(), username, auth.hash_password(password))
                except db.UsernameTaken:
                    error = "That username is already taken."
            if error:
                flash(error, "error")
            else:
                start_session(user_id)
                flash(f"Welcome to SpendWise, {username}!", "success")
                return redirect(url_for("index"))
    return render_template("signup.html", username=username)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You've been signed out.", "success")
    return redirect(url_for("login"))


def read_form() -> tuple[Optional[dict], Optional[str]]:
    try:
        fields: dict[str, object] = {
            "date": parse_date_iso(request.form.get("date", "")),
            "amount_cents": parse_amount_cents(request.form.get("amount", "")),
            "category": parse_category(request.form.get("category", "")),
            "note": request.form.get("note", "").strip(),
        }
        return fields, None
    except ValueError as err:
        return None, str(err)


def read_filters():
    def clean_date(key):
        try:
            return parse_date_iso(request.args.get(key, ""))
        except ValueError:
            return None
    return {
        "category": request.args.get("category") or None,
        "q": request.args.get("q", "").strip() or None,
        "start": clean_date("start"),
        "end": clean_date("end"),
    }


def csv_safe(text):
    """Stop spreadsheet apps from running a note that starts like a formula."""
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@app.route("/export.csv")
def export_csv():
    rows = db.list_expenses(get_conn(), g.user["id"], **read_filters())
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date", "category", "note", "amount"])
    for r in rows:
        w.writerow([r["date"], r["category"], csv_safe(r["note"]), f"{r['amount_cents'] / 100:.2f}"])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=expenses.csv"})


@app.route("/")
def index():
    conn, uid = get_conn(), g.user["id"]
    filters = read_filters()
    expenses = db.list_expenses(conn, uid, **filters)
    total = sum(e["amount_cents"] for e in expenses)
    today = date.today()
    start, end = month_bounds(today)
    summary = db.month_summary(conn, uid, start, end)
    summary["daily_avg"] = summary["total"] // today.day
    return render_template(
        "index.html", expenses=expenses, total=total,
        categories=CATEGORY_NAMES, f=filters, summary=summary,
        today=today.isoformat(),
    )


@app.route("/add", methods=["POST"])
def add():
    fields, error = read_form()
    if error:
        flash(error, "error")
    else:
        assert fields is not None
        db.add_expense(get_conn(), g.user["id"], **fields)
        flash("Expense added.", "success")
    return redirect(url_for("index"))


@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
def edit(expense_id):
    conn, uid = get_conn(), g.user["id"]
    expense = db.get_expense(conn, uid, expense_id)
    if expense is None:
        flash("That expense doesn't exist.", "error")
        return redirect(url_for("index"))
    if request.method == "POST":
        fields, error = read_form()
        if error:
            flash(error, "error")
        else:
            assert fields is not None
            db.update_expense(conn, uid, expense_id, **fields)
            flash("Expense updated.", "success")
            return redirect(url_for("index"))
    return render_template("edit.html", e=expense, categories=CATEGORY_NAMES)


@app.route("/delete/<int:expense_id>", methods=["POST"])
def delete(expense_id):
    if db.delete_expense(get_conn(), g.user["id"], expense_id):
        flash("Expense deleted.", "success")
    else:
        flash("That expense doesn't exist.", "error")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1")