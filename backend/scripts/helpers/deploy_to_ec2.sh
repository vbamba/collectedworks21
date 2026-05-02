#!/usr/bin/env bash
#
# deploy_to_ec2.sh — one-shot deploy of the working tree to ask.cw EC2.
#
# Mirrors docs/DEPLOY.md §0.5 → §1 → (§3 SQL apply) → §4 smoke. Frontend deploy
# (§2) is intentionally not automated here — only run a frontend rebuild +
# rsync when frontend/build/ actually changed, and that's a manual call.
#
# Usage:
#   export EC2=ec2-user@44.245.34.75
#   export PEM=/Users/vbamba/Projects/aws-ssh-keys/ewcc.pem
#   backend/scripts/helpers/deploy_to_ec2.sh <TAG>
#
# Example:
#   backend/scripts/helpers/deploy_to_ec2.sh release-$(date +%Y-%m-%d)
#
# Flags (env vars):
#   SKIP_SNAPSHOT=1   skip §0.5 prod tarball (NOT recommended; rollback breaks)
#   SKIP_SQL=1        skip the strip_oversized_sections.sql apply on prod DB
#   SKIP_SMOKE=1      skip the §4 smoke tests at the end
#
# Exit codes: 0 success, non-zero on first failed step. `set -euo pipefail`
# means any single command failure aborts the whole deploy.

set -euo pipefail

# ── Args & env ────────────────────────────────────────────────────────────────
TAG="${1:-}"
if [[ -z "$TAG" ]]; then
  echo "ERROR: TAG arg required. e.g. $0 release-$(date +%Y-%m-%d)" >&2
  exit 64
fi
: "${EC2:?ERROR: \$EC2 must be set, e.g. ec2-user@44.245.34.75}"
: "${PEM:?ERROR: \$PEM must be set, path to your ewcc.pem}"
[[ -r "$PEM" ]] || { echo "ERROR: PEM not readable: $PEM" >&2; exit 66; }

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"

# Sanity: refuse to deploy from anywhere but the collectedworks21 repo root.
[[ -f backend/wsgi.py && -f docs/DEPLOY.md ]] || {
  echo "ERROR: not at collectedworks21 repo root (cwd=$REPO_ROOT)" >&2
  exit 65
}

REMOTE_APP=/home/ec2-user/collectedworks21
REMOTE_DB="$REMOTE_APP/backend/db/chapters.db"
REMOTE_SQL="$REMOTE_APP/backend/scripts/helpers/strip_oversized_sections.sql"
SSH=(ssh -i "$PEM" "$EC2")

step() { printf '\n=== [%s] %s ===\n' "$(date +%H:%M:%S)" "$*"; }

# ── 0. Connection check ───────────────────────────────────────────────────────
step "0/5 ssh sanity check ($EC2)"
"${SSH[@]}" 'hostname && uptime'

# ── 1. Snapshot prod (DEPLOY.md §0.5) ────────────────────────────────────────
if [[ "${SKIP_SNAPSHOT:-0}" == "1" ]]; then
  step "1/5 snapshot SKIPPED (SKIP_SNAPSHOT=1) — rollback will not be possible"
else
  step "1/5 snapshot prod (tag=$TAG)"
  "${SSH[@]}" "
    set -e
    mkdir -p /home/ec2-user/backups
    APP_OUT=/home/ec2-user/backups/collectedworks21-pre-$TAG.tar.gz
    echo '[backup] flask app -> '\$APP_OUT
    tar --exclude='collectedworks21/backups' \
        -czf \$APP_OUT -C /home/ec2-user collectedworks21
    WEB_OUT=/home/ec2-user/backups/nginx-html-pre-$TAG.tar.gz
    echo '[backup] nginx html -> '\$WEB_OUT
    sudo tar -czf \$WEB_OUT -C /usr/share/nginx html
    sudo chown ec2-user:ec2-user \$WEB_OUT
    ls -lh \$APP_OUT \$WEB_OUT
  "
fi

# ── 2. Rsync code + restart Flask (DEPLOY.md §1) ─────────────────────────────
step "2/5 rsync working tree -> $EC2:$REMOTE_APP"
# Excludes split into two groups so future readers see what's policy vs what's
# scratch:
#   - "core" excludes mirror docs/DEPLOY.md §1 (build artifacts, large data,
#     local-only infra like venv/ and .claude/)
#   - "scratch" excludes are unreferenced files that shouldn't reach prod:
#     orphan scripts (text_search2.py, "utils copy.py"), unused AI scaffolding,
#     local-only HTML mockups, debug/ping artifacts, .txt backup leftovers next
#     to .jsx files. Add to this list when new noise accumulates.
rsync -av --delete -e "ssh -i $PEM" \
      --exclude '.git/' --exclude '.claude/' --exclude '.restore/' \
      --exclude 'node_modules/' --exclude 'frontend/build/' \
      --exclude 'backend/db/' --exclude 'backend/data/' \
      --exclude 'backend/indexes/' --exclude 'backend/pdf/' \
      --exclude 'backend/venv/' \
      --exclude '__pycache__/' --exclude '*.pyc' \
      --exclude 'backend/backup/' --exclude 'frontend/src/backup/' \
      --exclude '.DS_Store' --exclude '*.zip' \
      --exclude 'backups/' \
      --exclude 'backend/venv.broken-*' \
      --exclude 'backend/scripts/text_search2.py' \
      --exclude 'backend/scripts/utils copy.py' \
      --exclude 'backend/scripts/ai/' \
      --exclude 'backend/config/' \
      --exclude 'frontend/public/searchform.html' \
      --exclude 'frontend/src/components/*.txt' \
      --exclude 'frontend/src/pages/*.txt' \
      --exclude 'ping.txt' \
      ./ "$EC2":"$REMOTE_APP/"

step "2/5 restart gunicorn (collectedworks.service)"
"${SSH[@]}" 'sudo systemctl restart collectedworks && sleep 1 && sudo systemctl is-active collectedworks'

# ── 3. Apply chapters.db cleanup SQL (idempotent) ────────────────────────────
# Safe to run on every deploy — the DELETE is a no-op once the rows are gone.
# Required after any chapters.db rebuild that re-emits the catch-all "Page_X"
# rows (see backend/scripts/helpers/strip_oversized_sections.sql for context).
if [[ "${SKIP_SQL:-0}" == "1" ]]; then
  step "3/5 SQL cleanup SKIPPED (SKIP_SQL=1)"
else
  step "3/5 apply strip_oversized_sections.sql on prod chapters.db"
  # CHANGED: was 'sqlite3 ... < sql_file', but the prod EC2 (Amazon Linux 2)
  # ships without the sqlite3 CLI. Python3 is always present (gunicorn runs
  # on it), and its sqlite3 module reads the same DB file format, so use
  # executescript() instead. Avoids needing yum/dnf install at deploy time.
  "${SSH[@]}" "
    set -e
    BAK=$REMOTE_DB.bak-\$(date +%Y%m%d-%H%M%S)
    echo '[sql] backing up prod DB -> '\$BAK
    cp $REMOTE_DB \$BAK
    echo '[sql] applying $REMOTE_SQL via python3'
    python3 -c \"import sqlite3; c=sqlite3.connect('$REMOTE_DB'); c.executescript(open('$REMOTE_SQL').read()); c.commit(); c.close()\"
    echo '[sql] restarting gunicorn so workers reopen the DB file'
    sudo systemctl restart collectedworks
    sleep 1
    sudo systemctl is-active collectedworks
  "
fi

# ── 4. Smoke tests (DEPLOY.md §4 + TOC-fix specific) ─────────────────────────
if [[ "${SKIP_SMOKE:-0}" == "1" ]]; then
  step "4/5 smoke tests SKIPPED (SKIP_SMOKE=1)"
else
  step "4/5 smoke test prod"
  HOST=https://ask.collectedworksofsriaurobindo.com

  echo '[smoke] /api/text_search returns results and parent_toc_title field exists'
  curl -fsS "$HOST/api/text_search?query=aspiration+surrender+rejection&mode=all&limit=5" \
    | python3 -c 'import sys,json; d=json.load(sys.stdin); \
        rs=d.get("results",[]); \
        assert rs, "no results"; \
        assert any("parent_toc_title" in r for r in rs), "missing parent_toc_title"; \
        print(f"  ok ({len(rs)} results, parent_toc_title present)")'

  echo '[smoke] mega-section is gone from search results'
  curl -fsS "$HOST/api/text_search?query=I+happened+to+be+the+main+target&mode=all&limit=5" \
    | python3 -c 'import sys,json; d=json.load(sys.stdin); \
        bad={"section_74_Page_8.txt","section_76_Page_11.txt","section_49_Page_1.txt"}; \
        sects=[r["section_filename"] for r in d.get("results",[])]; \
        assert not (set(sects) & bad), f"mega-section still present: {sects}"; \
        print(f"  ok (top: {sects[0] if sects else None})")'

  echo '[smoke] chapter nav skips section_01 / TOC pages'
  curl -fsS "$HOST/api/chapter?collection_folder=sriaurobindo&book_folder=28LettersOnYoga-I&section_filename=section_04_Chapter_One_-_The_Divine_and_Its_Aspects.txt" \
    | python3 -c 'import sys,json; d=json.load(sys.stdin); \
        first=d.get("first_section",""); \
        assert not first.startswith("section_01"), f"first_section is TOC: {first}"; \
        print(f"  ok (first_section={first})")'
fi

# ── 5. Local audit tag ────────────────────────────────────────────────────────
step "5/5 local audit tag"
# CHANGED: was "deployed-$(date +%Y-%m-%d)-${TAG#release-}" which double-printed
# the date when TAG already started "release-YYYY-MM-DD". Strip the "release-"
# prefix from TAG (no-op if absent) and use that directly.
TAG_NAME="deployed-${TAG#release-}"
if git rev-parse "$TAG_NAME" >/dev/null 2>&1; then
  echo "[tag] '$TAG_NAME' already exists, leaving it alone"
else
  git tag -a "$TAG_NAME" -m "deployed to ask.cw via rsync (TAG=$TAG)"
  echo "[tag] created '$TAG_NAME' at $(git rev-parse --short HEAD)"
fi

cat <<EOF

✓ Deploy complete (TAG=$TAG, HEAD=$(git rev-parse --short HEAD)).
  Rollback: see docs/DEPLOY.md §5 with the same TAG.
  Frontend (§2) was not touched — run a build + rsync separately if needed.
EOF
