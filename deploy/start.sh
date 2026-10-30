cd "$(dirname "$0")/.." || exit 1
exec .venv/bin/gunicorn --bind "127.0.0.1:${PORT:?Set PORT in .env}" --workers 1 --threads 4 --access-logfile - app:app