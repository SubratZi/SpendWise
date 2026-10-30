#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
.venv/bin/pip install -q -r requirements.txt
systemctl restart SpendWise
sleep 1
systemctl --no-pager status SpendWise | head -n 5 || true