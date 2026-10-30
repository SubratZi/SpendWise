import hmac
import os
import re
import secrets
import time
from collections import defaultdict, deque
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SECRET_FILE = os.environ.get("SECRET_KEY_FILE", os.path.join(BASE_DIR, ".secret_key"))

USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,30}$")
MIN_PASSWORD, MAX_PASSWORD = 8, 128

def _read(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip() or None
    except FileNotFoundError:
        return None


def load_secret_key():
    key = os.environ.get("SECRET_KEY") or _read(SECRET_FILE)
    if not key:
        key = secrets.token_hex(32)
        with open(SECRET_FILE, "w", encoding="utf-8") as fh:
            fh.write(key)
        try:
            os.chmod(SECRET_FILE, 0o600)
        except OSError:
            pass
    return key


_DUMMY_HASH = generate_password_hash("not-a-real-password")


def hash_password(password):
    return generate_password_hash(password)


def check_password(stored_hash, password):
    if len(password) > MAX_PASSWORD * 8:
        return False
    if stored_hash is None:
        check_password_hash(_DUMMY_HASH, password)
        return False
    return check_password_hash(stored_hash, password)


def validate_signup(username, password, confirm):
    if not USERNAME_RE.match(username):
        return "Username must be 3–30 characters: letters, numbers, dot, dash or underscore."
    if len(password) < MIN_PASSWORD:
        return f"Password must be at least {MIN_PASSWORD} characters."
    if len(password) > MAX_PASSWORD:
        return f"Password is too long (max {MAX_PASSWORD} characters)."
    if password.lower() == username.lower():
        return "Password can't be the same as your username."
    if password != confirm:
        return "Passwords don't match."
    return None


def signup_enabled():
    return os.environ.get("SIGNUP_ENABLED", "1") != "0"


class Limiter:
    def __init__(self, max_hits, window_seconds):
        self.max_hits, self.window = max_hits, window_seconds
        self._hits = defaultdict(deque)

    def _prune(self, key):
        q, cutoff = self._hits[key], time.time() - self.window
        while q and q[0] < cutoff:
            q.popleft()
        return q

    def locked_for(self, key):
        q = self._prune(key)
        if len(q) >= self.max_hits:
            return max(1, int(q[0] + self.window - time.time()))
        return 0

    def record(self, key):
        self._prune(key).append(time.time())

    def reset(self, key):
        self._hits.pop(key, None)