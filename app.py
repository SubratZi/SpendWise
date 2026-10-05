from datetime import date
from flask import Flask, flash, redirect, render_template, request, url_for
from typing import Optional

import db
from utils import format_money, parse_amount_cents, parse_date_iso

app = Flask(__name__)
app.secret_key = "Amlh87*&!:AS;dwjAJSD(2lP)"
app.jinja_env.filters["money"] = format_money

def read_form() -> tuple[Optional[dict], Optional[str]]:
    try:
        fields: dict[str, object] = {
            "date": parse_date_iso(request.form.get("date", "")),
            "amount_cents": parse_amount_cents(request.form.get("amount", "")),
            "category": request.form.get("category", "").strip().lower() or "uncategorized",
            "note": request.form.get("note", "").strip(),
        }
        return fields, None
    except ValueError as err:
        return None,str(err)

@app.route("/")
def index():
    conn = db.connect()
    category = request.args.get("category") or None
    expenses = db.list_expenses(conn, category = category)
    total = sum(e["amount_cents"] for e in expenses)
    categories = [r[0] for r in conn.execute("SELECT DISTINCT category FROM expenses ORDER BY 1")]
    return render_template(
        "index.html", expenses = expenses, total = total,
        categories = categories,
        selected = category,
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
    return render_template("edit.html", e= expense)

@app.route("/delete/<int:expense_id>", methods = ["POST"])
def delete(expense_id):
    db.delete_expense(db.connect(), expense_id)
    flash("Expense Deleted.")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug = True)