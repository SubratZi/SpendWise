import argparse
import os
import sys
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import db
from categories import CATEGORY_NAMES


def parse_amount(text):
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"invalid amount: {text!r}")
    if not value.is_finite() or value <= 0:
        raise argparse.ArgumentTypeError("amount must be greater than 0")
    return int((value * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def parse_date(text):
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"date must be YYYY-MM-DD, got {text!r}")

def format_money(cents):
    return f"{cents / 100:,.2f}"


def print_table(rows):
    if not rows:
        print("No expenses found.")
        return
    print(f"{'ID':>4} {'Date':<10} {'Amount':>10} {'Category':<14} Note")
    print("-" * 60)
    for r in rows:
        print(f"{r['id']:>4} {r['date']:<10} {format_money(r['amount_cents']):>10} "
              f"{r['category']:<14} {r['note']}")
    total = sum(r["amount_cents"] for r in rows)
    print("-" * 60)
    print(f"{'Total':>17} {format_money(total):>10}")


def cmd_add(conn, uid, args):
    new_id = db.add_expense(conn, uid, args.date.isoformat(), args.amount, args.category, args.note)
    print(f"Added expense {new_id}: {format_money(args.amount)} ({args.category}) on {args.date.isoformat()}")


def cmd_list(conn, uid, args):
    print_table(db.list_expenses(conn, uid, category=args.category, limit=args.limit))


def cmd_delete(conn, uid, args):
    if db.delete_expense(conn, uid, args.id):
        print(f"Deleted expense #{args.id}")
    else:
        sys.exit(f"No expense with id {args.id}")


def cmd_edit(conn, uid, args):
    if db.get_expense(conn, uid, args.id) is None:
        sys.exit(f"No expense with id {args.id}")
    changed = db.update_expense(
        conn, uid, args.id,
        date=args.date.isoformat() if args.date else None,
        amount_cents=args.amount,
        category=args.category,
        note=args.note,
    )
    print(f"Updated expense #{args.id}" if changed else "Nothing to update (pass at least one option)")

def build_parser():
    parser = argparse.ArgumentParser(description="SpendWise: personal expense tracker")
    parser.add_argument("-u", "--user", default=os.environ.get("TRACKER_USER"),
                        help="account username (or set TRACKER_USER)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add", help="add a new expense")
    p.add_argument("amount", type=parse_amount, help="e.g. 12.5")
    p.add_argument("-c", "--category", choices=CATEGORY_NAMES, default="other")
    p.add_argument("-n", "--note", default="")
    p.add_argument("-d", "--date", type=parse_date, default=date.today(), help="YYYY-MM-DD (default: today)")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("list", help="list expenses, newest first")
    p.add_argument("-c", "--category", choices=CATEGORY_NAMES)
    p.add_argument("--limit", type=int)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("delete", help="delete an expense by id")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("edit", help="edit an existing expense")
    p.add_argument("id", type=int)
    p.add_argument("--amount", type=parse_amount)
    p.add_argument("-c", "--category", choices=CATEGORY_NAMES)
    p.add_argument("-n", "--note")
    p.add_argument("-d", "--date", type=parse_date)
    p.set_defaults(func=cmd_edit)
    return parser

def main():
    args = build_parser().parse_args()
    conn = db.connect()
    if not args.user:
        sys.exit("Say whose expenses to use: -u USERNAME (or set TRACKER_USER).")
    user = db.get_user_by_name(conn, args.user)
    if user is None:
        sys.exit(f"No account named {args.user!r}. Sign up in the web app first.")
    args.func(conn, user["id"], args)


if __name__ == "__main__":
    main()