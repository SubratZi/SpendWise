set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-8003}"

[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

if [ -f .env ]; then
    echo ".env already exists - keeping it."
else
    if ! python3 -c "import socket, sys; s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(('0.0.0.0', int(sys.argv[1])))" "$PORT" 2>/dev/null; then
        echo "Port $PORT is already in use. Pick another one, e.g.: PORT=8004 bash deploy/setup.sh"
        exit 1
    fi
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    ( umask 077
      cat > .env <<ENVFILE
PORT=$PORT
SECRET_KEY=$SECRET
HTTPS_ONLY=1
TRUSTED_PROXY_HOPS=1
ENVFILE
    )
    echo "Created .env with port $PORT and a new SECRET_KEY."
fi
chmod 600 .env

cp deploy/SpendWise.service /etc/systemd/system/SpendWise.service
systemctl daemon-reload
systemctl enable --now SpendWise
systemctl restart SpendWise
sleep 2
systemctl --no-pager status SpendWise | head -n 8 || true

PORT=$(grep -E '^PORT=' .env | cut -d= -f2)