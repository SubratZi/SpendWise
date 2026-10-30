set -euo pipefail
cd "$(dirname "$0")/.."

[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

if [ -f .env ]; then
    echo ".env already exists - keeping it."
else
    PORT=$(nest get_port | grep -Eo '[0-9]{4,5}' | head -1 || true)
    if [ -z "$PORT" ]; then
        echo "Couldn't read a port from 'nest get_port'."
        echo "Run it yourself, then copy .env.example to .env and set PORT."
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
chmod 700 .

mkdir -p "$HOME/.config/systemd/user"
cp deploy/spendwise.service "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now spendwise
systemctl --user restart spendwise

PORT=$(grep -E '^PORT=' .env | cut -d= -f2)
echo
echo "Service started. One step left - give it a web address:"
echo "  nest caddy add spendwise.$USER.hackclub.app --proxy localhost:$PORT"
echo "  systemctl --user reload caddy"
echo "Then open https://spendwise.$USER.hackclub.app"