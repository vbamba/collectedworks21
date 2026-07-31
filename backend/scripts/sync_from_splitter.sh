#!/usr/bin/env bash
# sync_from_splitter.sh — refresh text-search data from the splitter repo.
#
# NEW (2026-04-19): after Pass 3 regenerated out_chapters on the splitter side
# with journal sub-sections, the serving repo was stuck on a Jul-2025 snapshot.
# This script is the canonical way to pull splitter artifacts here so we don't
# have to remember a one-off rsync invocation.
#
# What it syncs:
#   <SPLITTER_DIR>/out_chapters/  ->  backend/data/out_chapters/
#   <SPLITTER_DIR>/db/chapters.db ->  backend/db/chapters.db
#
# What it does NOT sync:
#   - indexes/faiss_index.bin / metadata.json (semantic-search branch; not
#     touched by Pass 3 and has a separate rebuild cadence)
#   - pdfs/ (source PDFs live in the splitter repo; serving doesn't mirror them)
#
# Usage:
#   backend/scripts/sync_from_splitter.sh            # copy for real
#   backend/scripts/sync_from_splitter.sh --dry-run  # show what rsync would do
#
# Override splitter location:
#   SPLITTER_DIR=/some/other/path backend/scripts/sync_from_splitter.sh

set -euo pipefail

# CHANGED: resolve paths from this script's location, not $PWD, so the script
# is safe to run from any cwd (cron, CI, etc.).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVING_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

SPLITTER_DIR="${SPLITTER_DIR:-$HOME/Projects/collectedworks}"

SRC_CHAPTERS="$SPLITTER_DIR/out_chapters"
SRC_DB="$SPLITTER_DIR/db/chapters.db"
DST_CHAPTERS="$SERVING_DIR/backend/data/out_chapters"
DST_DB="$SERVING_DIR/backend/db/chapters.db"

DRY_RUN=()
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=(--dry-run)
  echo "[sync] DRY RUN — no files will be written"
fi

# NEW: fail loudly if the splitter repo isn't where we expect, instead of
# silently copying an empty tree and wiping the serving data.
for p in "$SRC_CHAPTERS" "$SRC_DB"; do
  if [[ ! -e "$p" ]]; then
    echo "[sync] ERROR: missing source: $p" >&2
    echo "[sync] set SPLITTER_DIR=... if the splitter repo lives elsewhere." >&2
    exit 1
  fi
done

# NEW: refuse to run if a splitter pipeline process is still holding the DB
# open (rare, but cp-mid-write would produce a corrupt chapters.db).
if command -v lsof >/dev/null 2>&1; then
  if lsof "$SRC_DB" >/dev/null 2>&1; then
    echo "[sync] ERROR: $SRC_DB is open in another process; aborting." >&2
    exit 1
  fi
fi

echo "[sync] splitter : $SPLITTER_DIR"
echo "[sync] serving  : $SERVING_DIR"

mkdir -p "$DST_CHAPTERS" "$(dirname "$DST_DB")"

# CHANGED: rsync with --delete so books removed on the splitter side also
# disappear here. Excludes cover splitter-only debug artifacts that the
# serving backend doesn't need:
#   - raw_section_*.txt : pre-split debug dumps (e.g. 192 raw_* + 265 section_*
#                         in Agenda Vol1; only section_* are indexed)
#   - diagnostic.*      : per-book splitter diagnostics
#   - toc.{json,txt}    : raw TOC extractions (metadata.json already carries
#                         the resolved structure)
echo "[sync] rsync out_chapters..."
# CHANGED (2026-07-30): also exclude *.bak — recover_letters_verse_breaks.py
# writes a .txt.bak beside each file it rewrites, and those were riding along
# into the serving tree (and on to prod). They are never indexed or served.
rsync -a "${DRY_RUN[@]}" --delete \
  --exclude 'raw_section_*.txt' \
  --exclude 'diagnostic.*' \
  --exclude 'toc.json' \
  --exclude 'toc.txt' \
  --exclude '*.bak' \
  "$SRC_CHAPTERS/" "$DST_CHAPTERS/"

# CHANGED: copy DB via a temp file + mv so a concurrent Flask request can
# never observe a half-written chapters.db. SQLite is fine with atomic
# replacement; existing open connections will continue to see the old file
# until they close.
echo "[sync] copying chapters.db..."
if [[ ${#DRY_RUN[@]} -eq 0 ]]; then
  cp "$SRC_DB" "$DST_DB.tmp"
  mv "$DST_DB.tmp" "$DST_DB"
else
  echo "[sync] [dry-run] would cp $SRC_DB -> $DST_DB (via .tmp + mv)"
fi

# NEW: quick smoke check — report row count after a real copy so the operator
# can eyeball whether the sync worked, without remembering the sqlite query.
if [[ ${#DRY_RUN[@]} -eq 0 ]] && command -v sqlite3 >/dev/null 2>&1; then
  rows=$(sqlite3 "$DST_DB" "SELECT COUNT(*) FROM chapters;")
  books=$(sqlite3 "$DST_DB" "SELECT COUNT(DISTINCT book_folder) FROM chapters;")
  echo "[sync] chapters.db now has $rows rows across $books books"
fi

# CHANGED: post-rebuild cleanup — strip Savitri's PDF page-running headers
# ("CANTO IV: The Secret Knowledge" lines) from both the freshly-synced
# out_chapters tree and chapters.db. Idempotent and Savitri-scoped, so it
# costs nothing on books it doesn't touch. Lives here (vs. as a separate
# step the operator has to remember) because every sync_from_splitter.sh
# invocation re-imports the upstream artifacts and would otherwise reintroduce
# the headers — see backend/scripts/helpers/strip_savitri_running_headers.py.
if [[ ${#DRY_RUN[@]} -eq 0 ]]; then
  echo "[sync] stripping Savitri running headers..."
  python3 "$SCRIPT_DIR/helpers/strip_savitri_running_headers.py" \
    --db "$DST_DB" --out-chapters "$DST_CHAPTERS"
else
  echo "[sync] [dry-run] would run strip_savitri_running_headers.py"
fi

echo "[sync] done."
