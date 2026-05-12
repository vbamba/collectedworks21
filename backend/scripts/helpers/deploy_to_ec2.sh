#!/usr/bin/env bash
#
# deploy_to_ec2.sh — one-shot deploy of the working tree to ask.cw EC2.
#
# Mirrors docs/DEPLOY.md §0.5 → §1 → §3 fixups → §2 frontend (opt-in) → §4
# smoke. Frontend rebuild + nginx push is gated behind --frontend because most
# deploys are backend-only and a full React build adds ~30s.
#
# Usage:
#   export EC2=ec2-user@44.245.34.75
#   export PEM=/Users/vbamba/Projects/aws-ssh-keys/ewcc.pem
#   backend/scripts/helpers/deploy_to_ec2.sh <TAG> [--frontend]
#
# Examples:
#   # backend-only (most common)
#   backend/scripts/helpers/deploy_to_ec2.sh release-$(date +%Y-%m-%d)
#
#   # backend + frontend rebuild + nginx push
#   backend/scripts/helpers/deploy_to_ec2.sh release-$(date +%Y-%m-%d) --frontend
#
# Flags (positional):
#   --frontend     also: npm run build, rsync build/ to nginx html, reload nginx
#
# Flags (env vars):
#   SKIP_SNAPSHOT=1   skip §0.5 prod tarball (NOT recommended; rollback breaks)
#   SKIP_SQL=1        skip the chapters.db fixups on prod DB
#   SKIP_SMOKE=1      skip the §4 smoke tests at the end
#   BUILD_VERSION=X   override the cache-buster baked into the React build
#                     (used only with --frontend; default: today's date YYYYMMDD)
#
# Exit codes: 0 success, non-zero on first failed step. `set -euo pipefail`
# means any single command failure aborts the whole deploy.

set -euo pipefail

# ── Args & env ────────────────────────────────────────────────────────────────
# CHANGED: separate flag args from positional TAG so --frontend can appear in
# any position. Anything that isn't a recognized flag is treated as positional.
DO_FRONTEND=0
POSITIONAL=()
for arg in "$@"; do
  case "$arg" in
    --frontend|-f) DO_FRONTEND=1 ;;
    *) POSITIONAL+=("$arg") ;;
  esac
done
set -- "${POSITIONAL[@]:-}"

TAG="${1:-}"
if [[ -z "$TAG" ]]; then
  echo "ERROR: TAG arg required. e.g. $0 release-$(date +%Y-%m-%d) [--frontend]" >&2
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
# CHANGED: Savitri parent_toc_title backfill ships alongside the SQL strip;
# both are idempotent post-rebuild fixups for the chapters splitter.
REMOTE_BACKFILL_SAVITRI="$REMOTE_APP/backend/scripts/helpers/backfill_savitri_toc.py"
# CHANGED: Savitri running-header stripper — drops "CANTO IV: ..." page-header
# duplicates that the splitter pulls into canto bodies. Runs in full mode
# (disk + DB) on prod because deploy_to_ec2.sh doesn't rsync out_chapters
# (DEPLOY.md §3 is a manual step), so prod's section .txt files would
# otherwise still render the headers when /api/chapter reads them off disk.
# Idempotent — no-op on second run.
REMOTE_STRIP_SAVITRI_HDRS="$REMOTE_APP/backend/scripts/helpers/strip_savitri_running_headers.py"
REMOTE_OUT_CHAPTERS="$REMOTE_APP/backend/data/out_chapters"
SSH=(ssh -i "$PEM" "$EC2")

step() { printf '\n=== [%s] %s ===\n' "$(date +%H:%M:%S)" "$*"; }

# ── 0. Connection check ───────────────────────────────────────────────────────
step "0/6 ssh sanity check ($EC2)"
"${SSH[@]}" 'hostname && uptime'

# ── 1. Snapshot prod (DEPLOY.md §0.5) ────────────────────────────────────────
if [[ "${SKIP_SNAPSHOT:-0}" == "1" ]]; then
  step "1/6 snapshot SKIPPED (SKIP_SNAPSHOT=1) — rollback will not be possible"
else
  step "1/6 snapshot prod (tag=$TAG)"
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

    # CHANGED: prune to the 3 most recent backups of each kind so /home/ec2-user
    # doesn't grow unbounded. ls -t sorts newest-first; tail -n +4 yields the
    # 4th-and-older entries to delete. Runs after the new snapshot is written
    # so the freshly-created tarball is always counted among the kept three.
    echo '[backup] pruning older backups (keeping 3 most recent of each kind)'
    for prefix in collectedworks21-pre nginx-html-pre; do
      ls -t /home/ec2-user/backups/\${prefix}-*.tar.gz 2>/dev/null \
        | tail -n +4 \
        | xargs -r rm -v
    done
  "
fi

# ── 2. Rsync code + restart Flask (DEPLOY.md §1) ─────────────────────────────
step "2/6 rsync working tree -> $EC2:$REMOTE_APP"
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

step "2/6 restart gunicorn (collectedworks.service)"
"${SSH[@]}" 'sudo systemctl restart collectedworks && sleep 1 && sudo systemctl is-active collectedworks'

# ── 3. Apply chapters.db post-rebuild fixups (all idempotent) ────────────────
# Three scripts run together so we only bounce gunicorn once:
#   a) strip_oversized_sections.sql — drop the catch-all "Page_X" rows that the
#      splitter emits (1MB+ each, content already duplicated in proper chapters)
#   b) backfill_savitri_toc.py — set chapters.parent_toc_title = "Book X — ..."
#      for every Savitri canto, so the SPA chapter header and search-result
#      cards show the parent Book breadcrumb. Idempotent post-second-run.
#   c) strip_savitri_running_headers.py — drop the duplicated "CANTO IV:
#      <title>" lines the splitter pulls out of PDF page headers into canto
#      bodies. Runs disk + DB; the disk pass cleans prod's section .txt
#      files in place so /api/chapter doesn't render them when reading off
#      disk (deploy_to_ec2.sh doesn't rsync out_chapters).
# All safe on every deploy; they're no-ops if their target state is already
# correct. Required after any chapters.db rebuild.
if [[ "${SKIP_SQL:-0}" == "1" ]]; then
  step "3/6 chapters.db fixups SKIPPED (SKIP_SQL=1)"
else
  step "3/6 apply chapters.db fixups (strip mega-sections + Savitri TOC backfill)"
  # CHANGED: was 'sqlite3 ... < sql_file', but the prod EC2 (Amazon Linux 2)
  # ships without the sqlite3 CLI. Python3 is always present (gunicorn runs
  # on it), and its sqlite3 module reads the same DB file format, so use
  # executescript() instead. Avoids needing yum/dnf install at deploy time.
  "${SSH[@]}" "
    set -e
    BAK=$REMOTE_DB.bak-\$(date +%Y%m%d-%H%M%S)
    echo '[fixup] backing up prod DB -> '\$BAK
    cp $REMOTE_DB \$BAK
    echo '[fixup] applying $REMOTE_SQL via python3'
    python3 -c \"import sqlite3; c=sqlite3.connect('$REMOTE_DB'); c.executescript(open('$REMOTE_SQL').read()); c.commit(); c.close()\"
    echo '[fixup] running $REMOTE_BACKFILL_SAVITRI'
    python3 $REMOTE_BACKFILL_SAVITRI --db $REMOTE_DB
    echo '[fixup] running $REMOTE_STRIP_SAVITRI_HDRS (disk + DB)'
    python3 $REMOTE_STRIP_SAVITRI_HDRS --db $REMOTE_DB --out-chapters $REMOTE_OUT_CHAPTERS
    echo '[fixup] restarting gunicorn so workers reopen the DB file'
    sudo systemctl restart collectedworks
    sleep 1
    sudo systemctl is-active collectedworks
  "
fi

# ── 4. Frontend build + nginx push (DEPLOY.md §2, opt-in via --frontend) ─────
# CHANGED: previously this was a manual call after the script finished. Folded
# in here so the four-line build/rsync/reload sequence travels with the rest
# of the deploy. Skipped by default because most deploys are backend-only and
# `npm run build` adds ~30s; pass --frontend when the React bundle changed.
if [[ "$DO_FRONTEND" != "1" ]]; then
  step "4/6 frontend build + nginx push SKIPPED (pass --frontend to include)"
else
  step "4/6 frontend build + nginx push"
  # Bake a cache-buster into the bundle so browsers don't serve stale JS/CSS.
  # Default = today's date (YYYYMMDD); override via BUILD_VERSION=... if you
  # need a same-day re-deploy with a suffix (matches DEPLOY.md §0 convention).
  FE_VERSION="${BUILD_VERSION:-$(date +%Y%m%d)}"
  echo "[frontend] building with REACT_APP_BUILD_VERSION=$FE_VERSION"
  pushd frontend > /dev/null
  REACT_APP_BUILD_VERSION="$FE_VERSION" npm run build
  popd > /dev/null

  # Two-stage rsync: user-owned scratch dir first, then sudo copy into the
  # nginx html root (which is root-owned). Keeps the privileged step minimal
  # and matches DEPLOY.md §2 verbatim.
  echo "[frontend] rsync build/ -> $EC2:/tmp/cw-build/"
  rsync -av --delete -e "ssh -i $PEM" frontend/build/ "$EC2":/tmp/cw-build/
  echo "[frontend] sudo rsync into /usr/share/nginx/html/ + reload nginx"
  "${SSH[@]}" '
    set -e
    sudo rsync -av --delete /tmp/cw-build/ /usr/share/nginx/html/
    sudo nginx -t
    sudo systemctl reload nginx
  '
fi

# ── 5. Smoke tests (DEPLOY.md §4 + TOC-fix specific) ─────────────────────────
if [[ "${SKIP_SMOKE:-0}" == "1" ]]; then
  step "5/6 smoke tests SKIPPED (SKIP_SMOKE=1)"
else
  step "5/6 smoke test prod"
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

# ── 6. Local audit tag ────────────────────────────────────────────────────────
step "6/6 local audit tag"
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

# CHANGED: footer reflects whether frontend was actually built so the operator
# knows which surfaces went out.
if [[ "$DO_FRONTEND" == "1" ]]; then
  FE_NOTE="frontend rebuilt + pushed (BUILD_VERSION=${BUILD_VERSION:-$(date +%Y%m%d)})"
else
  FE_NOTE="frontend NOT touched (re-run with --frontend if React bundle changed)"
fi

cat <<EOF

✓ Deploy complete (TAG=$TAG, HEAD=$(git rev-parse --short HEAD)).
  $FE_NOTE.
  Rollback: see docs/DEPLOY.md §5 with the same TAG.
EOF
