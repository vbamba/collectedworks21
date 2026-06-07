#!/usr/bin/env bash
# Deploy the Savitri Study static wiki to EC2.
# See docs/DEPLOY.md § 8 for the full runbook.
set -euo pipefail

EC2="${EC2:-ec2-user@44.245.34.75}"
PEM="${PEM:-/Users/vbamba/Projects/aws-ssh-keys/ewcc.pem}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO_ROOT/savitri-wiki/"

[ -d "$SRC" ] || { echo "ERROR: $SRC not found" >&2; exit 1; }
[ -f "$PEM" ] || { echo "ERROR: PEM key $PEM not found" >&2; exit 1; }

echo "[1/3] rsync $SRC -> $EC2:/home/ec2-user/savitri-wiki/"
rsync -av --delete -e "ssh -i $PEM" "$SRC" "$EC2":/home/ec2-user/savitri-wiki/

echo "[2/3] sync to nginx root + fix perms"
ssh -i "$PEM" "$EC2" '
  set -e
  sudo rsync -a --delete /home/ec2-user/savitri-wiki/ /usr/share/nginx/savitri-wiki/
  sudo chown -R nginx:nginx /usr/share/nginx/savitri-wiki
  sudo find /usr/share/nginx/savitri-wiki -type d -exec chmod 755 {} \;
  sudo find /usr/share/nginx/savitri-wiki -type f -exec chmod 644 {} \;
'

echo "[3/3] smoke test"
curl -fsS -o /dev/null -w "  https://savitri.thesunlitpath.in/  -> %{http_code}\n" \
  https://savitri.thesunlitpath.in/

echo "Done."
