set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
.venv/bin/pip install -q -r requirements.txt
systemctl --user restart spendwise
sleep 1
systemctl --user --no-pager status spendwise | head -n 5