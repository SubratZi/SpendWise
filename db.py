from categories import CATEGORY_NAMES
import os
import sqlite3

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("EXPENSE_DB", os.path.join(_HERE, "expenses.db"))


class UsernameTaken(Exception):
    pass


def connect(path=DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    return conn


def init_db(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users(
        id              INTEGER  PRIMARY KEY AUTOINCREMENT,
        username        TEXT     NOT NULL UNIQUE COLLATE NOCASE,
        password_hash   TEXT     NOT NULL,
        created_at      TEXT     NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses(
        id              INTEGER  PRIMARY KEY AUTOINCREMENT,
        date            TEXT     NOT NULL,          -- ISO format: YYYY-MM-DD
        amount_cents    INTEGER  NOT NULL,          -- money as integer cents, never floats
        category        TEXT     NOT NULL DEFAULT 'other',
        note            TEXT     NOT NULL DEFAULT '',
        user_id         INTEGER  REFERENCES users(id)
        )
        """
    )

    cols = {r["name"] for r in conn.execute("PRAGMA table_info(expenses)")}
    if "user_id" not in cols:
        conn.execute("ALTER TABLE expenses ADD COLUMN user_id INTEGER REFERENCES users(id)")

    marks = ",".join("?" * len(CATEGORY_NAMES))
    conn.execute(
        f"UPDATE expenses SET category = 'other' WHERE category NOT IN ({marks})",
        CATEGORY_NAMES,
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_user_date ON expenses(user_id, date)")
    conn.commit()


def create_user(conn, username, password_hash):
    """Create an account. The very first account inherits any expenses that
    were saved before accounts existed (rows with no owner)."""
    try:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
    except sqlite3.IntegrityError:
        conn.rollback()
        raise UsernameTaken(username)
    user_id = cur.lastrowid
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1:
        conn.execute("UPDATE expenses SET user_id = ? WHERE user_id IS NULL", (user_id,))
    conn.commit()
    return user_id


def get_user(conn, user_id):
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_user_by_name(conn, username):
    return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def set_password_hash(conn, user_id, password_hash):
    cur = conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
    conn.commit()
    return cur.rowcount > 0

def add_expense(conn, user_id, date, amount_cents, category, note=""):
    cur = conn.execute(
        "INSERT INTO expenses (user_id, date, amount_cents, category, note) VALUES (?, ?, ?, ?, ?)",
        (user_id, date, amount_cents, category, note),
    )
    conn.commit()
    return cur.lastrowid


def get_expense(conn, user_id, expense_id):
    return conn.execute(
        "SELECT * FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user_id)
    ).fetchone()


def list_expenses(conn, user_id, category=None, q=None, start=None, end=None, limit=None):
    where, params = ["user_id = ?"], [user_id]
    if category:
        where.append("category = ?"); params.append(category)
    if q:
        esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append("(note LIKE ? ESCAPE '\\' OR category LIKE ? ESCAPE '\\')")
        params += [f"%{esc}%", f"%{esc}%"]
    if start:
        where.append("date >= ?"); params.append(start)
    if end:
        where.append("date <= ?"); params.append(end)
    query = "SELECT * FROM expenses WHERE " + " AND ".join(where)
    query += " ORDER BY date DESC, id DESC"
    if limit:
        query += " LIMIT ?"; params.append(limit)
    return conn.execute(query, params).fetchall()


def delete_expense(conn, user_id, expense_id):
    cur = conn.execute(
        "DELETE FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user_id)
    )
    conn.commit()
    return cur.rowcount > 0


def update_expense(conn, user_id, expense_id, **fields):
    allowed = {"date", "amount_cents", "category", "note"}
    fields = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not fields:
        return False
    assignments = ", ".join(f"{col} = ?" for col in fields)
    cur = conn.execute(
        f"UPDATE expenses SET {assignments} WHERE id = ? AND user_id = ?",
        (*fields.values(), expense_id, user_id),
    )
    conn.commit()
    return cur.rowcount > 0


def month_summary(conn, user_id, start, end):
    total, count = conn.execute(
        "SELECT COALESCE(SUM(amount_cents), 0), COUNT(*) FROM expenses "
        "WHERE user_id = ? AND date >= ? AND date < ?", (user_id, start, end)
    ).fetchone()
    top = conn.execute(
        "SELECT category, SUM(amount_cents) AS s FROM expenses "
        "WHERE user_id = ? AND date >= ? AND date < ? "
        "GROUP BY category ORDER BY s DESC LIMIT 1",
        (user_id, start, end),
    ).fetchone()
    return {
        "total": total, "count": count,
        "top_category": top["category"] if top else None,
        "top_cents": top["s"] if top else 0,
    }