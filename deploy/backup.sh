set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p "$HOME/backups"
out="$HOME/backups/SpendWise-$(date +%F-%H%M).db"
python3 - "$out" <<'PY'
import sqlite3, sys
src = sqlite3.connect("expenses.db")
dst = sqlite3.connect(sys.argv[1])
src.backup(dst)
dst.close(); src.close()
PY
chmod 600 "$out"
ls -t "$HOME"/backups/SpendWise-*.db | tail -n +15 | xargs -r rm --
echo "Backup saved: $out"