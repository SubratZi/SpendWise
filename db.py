from categories import CATEGORY_NAMES
import os
import sqlite3

DB_PATH = os.environ.get("EXPENSE_DB", "expenses.db")

def connect(path = DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn

def init_db(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses(
        id              INTEGER  PRIMARY KEY AUTOINCREMENT,
        date            TEXT     NOT NULL,          --ISO format: YYYY-MM-DD
        amount_cents    INTEGER  NOT NULL,          --money as integer cents, never floats
        category        TEXT     NOT NULL DEFAULT 'uncategorized',
        note            TEXT     NOT NULL DEFAULT ''
        )
        """
    )

    marks = ",".join("?" * len(CATEGORY_NAMES))
    conn.execute(
        f"UPDATE expenses SET category ='other' WHERE category NOT IN ({marks})",
        CATEGORY_NAMES,
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)")
    
    conn.commit()

def add_expense(conn, date, amount_cents, category, note = ""):
    cur = conn.execute(
        "INSERT INTO expenses (date, amount_cents, category, note) VALUES (?, ?, ?, ?)",
        (date, amount_cents, category, note),
    )

    conn.commit()
    return cur.lastrowid

def get_expense(conn, expense_id):
    return conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()

def list_expenses(conn, category = None, q=None, start=None, end=None, limit=None):
    where, params = [], []
    if category:
        where.append("category = ?"); params.append(category)
    if q:
        esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append("(note LIKE ? ESCAPE '\\' OR category LIKE ? ESCAPE '\\')")
        params +=[f"%{esc}%", f"%{esc}%"]
    if start:
        where.append("date >= ?"); params.append(start)
    if end:
        where.append("date <= ?"); params.append(end)
    query = "SELECT * FROM expenses"
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY date DESC, id DESC"
    if limit:
        query += " LIMIT ?"; params.append(limit)
    return conn.execute(query, params).fetchall()


def delete_expense(conn, expense_id):
    cur = conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    return cur.rowcount > 0

def update_expense(conn, expense_id, **fields):
    allowed = {"date", "amount_cents", "category", "note"}
    fields = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not fields:
        return False
    assignments = ", ".join(f"{col} = ?" for col in fields)
    cur = conn.execute(
        f"UPDATE expenses SET {assignments} WHERE id = ?",
        (*fields.values(), expense_id),
    )
    conn.commit()
    return cur.rowcount > 0

def month_summary(conn, start, end):
    total, count = conn.execute(
        "SELECT COALESCE(SUM(amount_cents), 0), COUNT(*) FROM expenses "
        "WHERE date >= ? AND date < ?", (start, end)
    ).fetchone()
    top = conn.execute(
        "SELECT category, SUM(amount_cents) AS s FROM expenses "
        "WHERE date >= ? AND date < ? GROUP BY category ORDER BY s DESC LIMIT 1",
        (start, end),
    ).fetchone()
    return {
        "total": total, "count": count,
        "top_category" : top["category"] if top else None,
        "top_cents": top["s"] if top else 0,
    }
