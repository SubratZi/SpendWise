from datetime import date
from flask import Flask, flash, redirect, render_template, request, url_for
from typing import Optional
from categories import CATEGORY_NAMES, CATEGORY_COLORS

import db
from utils import format_money, parse_amount_cents, parse_date_iso, parse_category, month_bounds

app = Flask(__name__)
app.secret_key = "Amlh87*&!:AS;dwjAJSD(2lP)"
app.jinja_env.filters["money"] = format_money
app.jinja_env.filters["cat_color"] = lambda c: CATEGORY_COLORS.get(c,"#6B7268")

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
        return None,str(err)

def read_filters():
    def clean_date(key):
        try:
            return parse_date_iso(request.args.get(key, ""))
        except ValueError:
            return None
    return {
        "category" : request.args.get("category") or None,
        "q" : request.args.get("q", "").strip() or None,
        "start" : clean_date("start"),
        "end" : clean_date("end"),
    }

@app.route("/")
def index():
    conn = db.connect()
    filters = read_filters()
    category = request.args.get("category") or None
    expenses = db.list_expenses(conn, category = category)
    total = sum(e["amount_cents"] for e in expenses)
    categories = CATEGORY_NAMES
    today = date.today()
    start, end = month_bounds(today)
    summary = db.month_summary(conn, start, end)
    summary["daily_avg"] = summary["total"] // today.day
    return render_template(
        "index.html", expenses = expenses, total = total,
        categories = categories,
        f= filters,
        selected = category,
        summary = summary,
        today = date.today().isoformat(),
    )

@app.route("/add", methods=["POST"])
def add():
    fields, error = read_form()
    if error:
        flash(error)
    else:
        assert fields is not None
        db.add_expense(db.connect(), **fields)
        flash("Expense added.")
    return redirect(url_for("index"))

@app.route("/edit/<int:expense_id>", methods = ["GET", "POST"])
def edit(expense_id):
    conn = db.connect()
    expense = db.get_expense(conn, expense_id)
    if expense is None:
        flash("That expense doesn't exist")
        return redirect(url_for("index"))
    if request.method == "POST":
        fields, error = read_form()
        if error:
            flash(error)
        else:
            assert fields is not None
            db.update_expense(conn, expense_id, **fields)
            flash("Expense Updated.")
            return redirect(url_for("index"))
    return render_template("edit.html", e= expense, categories= CATEGORY_NAMES)

@app.route("/delete/<int:expense_id>", methods = ["POST"])
def delete(expense_id):
    db.delete_expense(db.connect(), expense_id)
    flash("Expense Deleted.")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug = True)