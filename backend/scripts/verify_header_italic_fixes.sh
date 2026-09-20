#!/usr/bin/env bash
# Verification tests for the running-header + question-italics fixes.
# Run from the collectedworks21 repo root. Read-only; touches nothing.
set -uo pipefail
cd "$(dirname "$0")" 2>/dev/null || true
REPO="$HOME/Projects/collectedworks21"
DB="$REPO/backend/db/chapters.db"
OUT="$REPO/backend/data/out_chapters"
BAK="/tmp/cw_backup_20260723/out_chapters.bak"   # pre-rebuild snapshot
pass(){ echo "  ✅ $1"; }
fail(){ echo "  ❌ $1"; }

echo "══ FIX 1: running headers removed ══"
# 1a. reported page: header gone from the served .txt
f="$OUT/sriaurobindo/01EarlyCulturalWritings/section_113_Dayananda_and_the_Veda.txt"
n=$(grep -c 'Bankim–Tilak–Dayananda' "$f")
[ "$n" = 0 ] && pass "no header leak in Dayananda chapter (.txt)" || fail "still $n leaks"
# 1b. sentence rejoined
grep -q 'different degrees to minimise it' "$f" && pass "split sentence rejoined" || fail "sentence still broken"
# 1c. FTS phrase search now matches across the old gap
r=$(sqlite3 "$DB" "SELECT COUNT(*) FROM chapters WHERE content MATCH '\"degrees to minimise it\"';")
[ "$r" -ge 1 ] && pass "FTS phrase search matches ($r hit)" || fail "phrase not searchable"
# 1d. only legit residual is the Part-divider heading
r=$(sqlite3 "$DB" "SELECT slug FROM chapters WHERE content LIKE '%Bankim–Tilak–Dayananda%';")
[ "$r" = "part-nine-bankim-tilak-dayananda" ] && pass "only residual is the legit Part heading" || fail "unexpected residual: $r"

echo "══ FIX 2: questions consistently italic ══"
sec="$OUT/sriaurobindo/35LettersOnHimselfAndTheAshram/section_22_Remarks_on_Public_Figures_in_India.txt"
miss=0
while IFS= read -r q; do
  line=$(grep -F "$q" "$sec" | head -1)
  case "$line" in "<i>"*) ;; *) echo "     not italic: $q"; miss=$((miss+1));; esac
done <<'Q'
This second fast
Yesterday I thought
The letter to Govindbhai
I heard that Gandhi has written
Yesterday Gandhi asked permission
Q
[ "$miss" = 0 ] && pass "all 5 Gandhi-run questions italic" || fail "$miss questions still plain"

echo "══ SAFETY: content conservation vs pre-rebuild (normalized: tags/whitespace/ligatures/accents ignored) ══"
# The real regression signals: (1) ANY book that GAINED characters = duplication;
# (2) a book whose LOSS looks like prose, not title-case header text. Intended
# header removal shows as loss of title-case chars only, with gained=0.
SPLIT="$HOME/Projects/collectedworks"
if [ -d "$BAK" ] && [ -f "$SPLIT/scripts/check_conservation.py" ]; then
  rep=$(python3 "$SPLIT/scripts/check_conservation.py" "$BAK" "$OUT" --max-delta 999999 2>/dev/null | grep -E '^(OK|FAIL) ')
  # Flag only books that GAINED >50 chars (real duplication). A handful of
  # gained chars is a heading re-render at a section boundary, not a defect.
  dup=$(echo "$rep" | sed -E 's/.*\(\+([0-9]+)\/.*/\1/' | awk '$1>50' | wc -l | tr -d ' ')
  echo "$rep" | awk -F'[+/]' '{g=$2+0; if(g>50) print "     GAINED>50: "$0}'
  [ "$dup" = 0 ] && pass "no book duplicated text (all gains <50 chars = heading re-renders)" || fail "$dup books gained >50 chars — investigate"
  # show the books with the largest loss so you can eyeball that it's header text
  echo "  ── largest losses (expected = removed running-header text) ──"
  echo "$rep" | sed -E 's/.*delta=([0-9]+).*\(\+0\/-([0-9]+)\)/\2 &/' | sort -rn | head -5 | sed 's/^[0-9]* /     /'
else
  echo "  ⚠️  no snapshot or tool; skipping"
fi

echo "══ SANITY: DB shape ══"
echo "  $(sqlite3 "$DB" "SELECT COUNT(*) FROM chapters;") rows / $(sqlite3 "$DB" "SELECT COUNT(DISTINCT book_folder) FROM chapters;") books"
