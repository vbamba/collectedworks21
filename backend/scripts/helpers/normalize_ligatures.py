#!/usr/bin/env python3
"""
normalize_ligatures.py — strip PDF-extraction ligatures (ﬁ, ﬂ, ﬀ, ﬃ, ﬄ)
from the `content` column of chapters.db.

Why this exists: pdf2text leaves U+FB0x ligature codepoints in the
extracted text. FTS5 indexes those as their own tokens, so a query for
"difficulties" (plain f+i) never matches a page that stores
"difﬁculties" (with U+FB01). Visually identical, search-broken.

What it does: runs a SQL UPDATE on the FTS5 `chapters` table replacing
each ligature with its ASCII equivalent. FTS5 reindexes on UPDATE so the
search index picks up the change automatically. Curly quotes / dashes
are intentionally LEFT ALONE — those are display-meaningful and the
search layer already handles them via prepare_text_for_matching().

Idempotent: re-running on already-clean rows is a no-op (replace() over
a string with no matches returns the same string, so FTS5 sees no change).

Usage:
    python3 backend/scripts/helpers/normalize_ligatures.py
    python3 backend/scripts/helpers/normalize_ligatures.py --db /path/to/chapters.db
    python3 backend/scripts/helpers/normalize_ligatures.py --dry-run    # just count
    python3 backend/scripts/helpers/normalize_ligatures.py --txt        # also rewrite out_chapters/*.txt
    python3 backend/scripts/helpers/normalize_ligatures.py --txt-only   # skip the DB, only do .txt files
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Keep in sync with scripts/utils.py:normalize_text() — same mapping, minus
# curly quotes / dashes (those must NOT be flattened at storage time).
LIGATURES = {
    'ﬀ': 'ff',   # ﬀ
    'ﬁ': 'fi',   # ﬁ
    'ﬂ': 'fl',   # ﬂ
    'ﬃ': 'ffi',  # ﬃ
    'ﬄ': 'ffl',  # ﬄ
    'ﬅ': 'st',   # ﬅ (long-s + t)
    'ﬆ': 'st',   # ﬆ
}


def count_affected(conn: sqlite3.Connection) -> int:
    """Count rows whose content column contains any ligature codepoint."""
    where = " OR ".join(f"content LIKE ?" for _ in LIGATURES)
    params = [f"%{lig}%" for lig in LIGATURES]
    cur = conn.execute(f"SELECT COUNT(*) FROM chapters WHERE {where}", params)
    return cur.fetchone()[0]


def fix_string(s: str) -> str:
    for lig, repl in LIGATURES.items():
        if lig in s:
            s = s.replace(lig, repl)
    return s


def normalize_db(db_path: Path, dry_run: bool) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        before = count_affected(conn)
        print(f"[db] rows with ligatures before: {before:,}")
        if before == 0:
            print("[db] nothing to do.")
            return 0
        if dry_run:
            print("[db] dry-run; no changes written.")
            return 0

        # Build a nested REPLACE() so we do it in a single UPDATE.
        expr = "content"
        params = []
        for lig, repl in LIGATURES.items():
            expr = f"REPLACE({expr}, ?, ?)"
            params.extend([lig, repl])

        # Why the WHERE: FTS5 UPDATE reindexes the row even if the value
        # is unchanged. Filtering down to only rows that actually contain
        # a ligature keeps the rebuild work minimal.
        where_clause = " OR ".join("content LIKE ?" for _ in LIGATURES)
        where_params = [f"%{lig}%" for lig in LIGATURES]

        sql = f"UPDATE chapters SET content = {expr} WHERE {where_clause}"
        conn.execute(sql, params + where_params)
        conn.commit()

        after = count_affected(conn)
        print(f"[db] rows with ligatures after:  {after:,}")
        print(f"[db] cleaned {before - after:,} rows.")
        return 0
    finally:
        conn.close()


def normalize_txt_tree(root: Path, dry_run: bool) -> int:
    """Rewrite every *.txt under `root` in place, replacing ligatures."""
    if not root.exists():
        print(f"[txt] ERROR: {root} not found", file=sys.stderr)
        return 1
    changed = 0
    scanned = 0
    for path in root.rglob("*.txt"):
        scanned += 1
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            print(f"[txt] skip (decode): {path} — {exc}", file=sys.stderr)
            continue
        fixed = fix_string(original)
        if fixed != original:
            changed += 1
            if not dry_run:
                # Write atomically via .tmp + rename so a half-written file
                # never goes live if we get interrupted mid-loop.
                tmp = path.with_suffix(path.suffix + ".tmp")
                tmp.write_text(fixed, encoding="utf-8")
                tmp.replace(path)
    verb = "would rewrite" if dry_run else "rewrote"
    print(f"[txt] scanned {scanned:,} files; {verb} {changed:,}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    repo_root = Path(__file__).resolve().parents[3]
    parser.add_argument(
        "--db",
        default=str(repo_root / "backend" / "db" / "chapters.db"),
        help="Path to chapters.db (default: backend/db/chapters.db)",
    )
    parser.add_argument(
        "--txt-root",
        default=str(repo_root / "backend" / "data" / "out_chapters"),
        help="Root of out_chapters tree (default: backend/data/out_chapters)",
    )
    parser.add_argument(
        "--txt", action="store_true",
        help="Also rewrite .txt files under --txt-root in place.",
    )
    parser.add_argument(
        "--txt-only", action="store_true",
        help="Only rewrite .txt files; skip the chapters.db UPDATE.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Just count rows / files that would change; make no writes.",
    )
    args = parser.parse_args()

    rc = 0
    if not args.txt_only:
        db = Path(args.db)
        if not db.exists():
            print(f"ERROR: chapters.db not found at {db}", file=sys.stderr)
            return 1
        rc |= normalize_db(db, args.dry_run)

    if args.txt or args.txt_only:
        rc |= normalize_txt_tree(Path(args.txt_root), args.dry_run)

    return rc


if __name__ == "__main__":
    sys.exit(main())
