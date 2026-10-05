import argparse
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import db

def parse_amount(text):
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"invalid amount: {text!r}")
    if value <=0:
        raise argparse.ArgumentTypeError("amount must be greater than 0")
    return int(value *100)

def parse_date(text):
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"date must be YYYY-MM-DD, got {text!r}")

def format_money(cents):
    return f"{cents/ 100:,.2f}"

def print_table(rows):
    if not rows:
        print("No expenses found.")
        return
    print(f"{'ID':>4} {'Date':<10} {'Amount':>10} {'Category':<14} Note")
    print("-" * 60)
    for r in rows:
        print(f"{r['id']:>4} {r['date']:<10} {format_money(r['amount_cents']):>10}"
        f"{r['category']: <14} {r['note']}"
        )
    total = sum(r["amount_cents"] for r in rows)
    print("-"* 60)
    print(f"{'Total':>17} {format_money(total):>10}")

def cmd_add(conn, args):
    new_id = db.add_expense(conn, args.date, args.amount, args.category, args.note)
    print(f"Added expense {new_id}: {format_money(args.amount)} ({args.category}) on {args.date}")

def cmd_list(conn, args):
    print_table(db.list_expenses(conn, category = args.category, limit = args.limit))

def cmd_delete(conn, args):
    if db.delete_expense(conn, args.id):
        print(f"Deleted expense #{args.id}")
    else:
        sys.exit(f"No expense with id {args.id}")

def cmd_edit(conn, args):
    if db.get_expense(conn, args.id) is None:
        sys.exit(f"No expense with id {args.id}")
    changed = db.update_expense(
        conn, args.id,
        date = args.id,
        amount_cents = args.amount,
        category = args.category,
        note = args.note,
    )
    print(f"Updated expense #{args.id}" if changed else "Nothing to update (pass at least one option)")

def build_parser():
    parser = argparse.ArgumentParser(description = "Personal expense tracker")
    sub = parser.add_subparsers(dest = "command", required = True)
    p = sub.add_parser("add", help = "add a new expense")
    p.add_argument("amount", type = parse_amount, help = "e.g. 12.5")
    p.add_argument("-c", "--category", default="uncategorized")
    p.add_argument("-n", "--note", default="")
    p.add_argument("-d", "--date", type=parse_date, default=date.today().isoformat(), help="YYYY-MM-DD (default: today)")
    p.set_defaults(func = cmd_add)

    p = sub.add_parser("list", help = "list expenses, newest first")
    p.add_argument("-c", "--category")
    p.add_argument("--limit", type=int)
    p.set_defaults(func = cmd_list)

    p = sub.add_parser("delete", help = "delete an expense by id")
    p.add_argument("id", type = int)
    p.set_defaults(func = cmd_delete)

    p = sub.add_parser("edit", help = "edit an existing expense")
    p.add_argument("id", type = int)
    p.add_argument("--amount", type=parse_amount)
    p.add_argument("-c", "--category")
    p.add_argument("-n", "--note")
    p.add_argument("-d", "--date", type = parse_date)
    p.set_defaults(func = cmd_edit)

    return parser

def main():
    args = build_parser().parse_args()
    conn = db.connect()
    args.func(conn, args)

if __name__ == "__main__":
    main()