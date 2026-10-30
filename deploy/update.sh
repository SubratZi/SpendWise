set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
.venv/bin/pip install -q -r requirements.txt
systemctl --user restart SpendWise
sleep 1
systemctl --user --no-pager status SpendWise | head -n 5