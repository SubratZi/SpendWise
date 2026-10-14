from datetime import datetime
from decimal import Decimal, InvalidOperation
from categories import CATEGORY_NAMES

def parse_amount_cents(text):
    try:
        value = Decimal(text.strip())
    except (InvalidOperation, AttributeError):
        raise ValueError("Amount must be a number, like 12.5")
    if value <=0:
        raise ValueError("Amount must be greater")
    return int(value * 100)

def parse_date_iso(text):
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except (ValueError, TypeError):
        raise ValueError("Date must look like 1999-01-20")

def format_money(cents):
    return f"{cents / 100:,.2f}"

def parse_category(text):
    value = (text or "").strip().lower() or "other"
    if value not in CATEGORY_NAMES:
        raise ValueError("Pick a category from the list")
    return value