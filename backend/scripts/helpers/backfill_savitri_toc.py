#!/usr/bin/env python3
"""
backfill_savitri_toc.py — set chapters.parent_toc_title for Savitri cantos.

Savitri's structure is Part → Book → Canto. The chapters splitter emits short
divider sections for each "Part X" and "Book X" heading (e.g. content
'BOOK ONE The Book of Beginnings'), then the actual cantos. We use the
existing parent_toc_title column — already rendered as "from <breadcrumb>"
in TextResultCard.jsx and ChapterPage.jsx for journal sub-sections — to
surface the parent Book name on each canto's page header and search-result
card.

Idempotent: re-running on an already-backfilled DB produces identical
parent_toc_title values. Re-run after every chapters.db rebuild until the
upstream splitter is taught to emit this column itself.

Usage:
    python3 backend/scripts/helpers/backfill_savitri_toc.py [--db PATH]

Default DB path: backend/db/chapters.db relative to repo root.
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path

# Identifies the Savitri book folder. Hard-coded because this script is
# specifically for Savitri's Part → Book → Canto structure; other books
# use parent_toc_title for different breadcrumbs (e.g. journal dates) and
# would be corrupted by this logic.
BOOK_FOLDER = "33-34Savitri"

# Matches the divider content emitted by the splitter, e.g.:
#   "BOOK ONE The Book of Beginnings"
#   "BOOK TWELVE Epilogue"
# Group 1 = ordinal (ONE, TWELVE), Group 2 = subtitle.
_BOOK_DIVIDER_RE = re.compile(r'^\s*BOOK\s+(\S+)\s+(.+?)\s*$', re.DOTALL)


def format_book_breadcrumb(divider_content: str) -> str:
    """Convert raw divider content to display form.

    "BOOK ONE The Book of Beginnings" → "Book One — The Book of Beginnings"
    Returns empty string if the content doesn't match the expected shape.
    """
    m = _BOOK_DIVIDER_RE.match(divider_content)
    if not m:
        return ""
    ordinal, subtitle = m.group(1), m.group(2)
    return f"Book {ordinal.title()} — {subtitle.strip()}"


def is_canto_section(section_filename: str) -> bool:
    """Match section_filenames that represent actual cantos.

    Examples that match: section_05_Canto_One__The_Symbol_Dawn.txt
    Examples that don't:
      - section_01_Savitri_a_Legend_and_a_Symbol.txt   (preface)
      - section_03_Part_One_-_Books_I___III.txt         (part divider)
      - section_04_Book_One_-_The_Book_of_Beginnings.txt (book divider)
      - section_66_Epilogue__The_Return_to_Earth.txt   (epilogue, not a canto)
      - section_67_Note_on_the_Text.txt                 (appendix)
    """
    return "_Canto_" in section_filename or section_filename.find("_Canto_") != -1


def backfill(db_path: Path) -> int:
    """Apply backfill in-place. Returns number of rows updated."""
    if not db_path.exists():
        print(f"ERROR: chapters.db not found at {db_path}", file=sys.stderr)
        return -1

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            """
            SELECT rowid, section_filename, content, parent_toc_title
            FROM chapters
            WHERE book_folder = ?
            ORDER BY CAST(chapter AS INTEGER)
            """,
            (BOOK_FOLDER,),
        ).fetchall()
    except sqlite3.OperationalError as e:
        print(f"ERROR: query failed (DB schema mismatch?): {e}", file=sys.stderr)
        conn.close()
        return -1

    if not rows:
        print(f"WARN: no rows found for book_folder={BOOK_FOLDER!r}; nothing to do")
        conn.close()
        return 0

    current_book_breadcrumb = ""
    updates: list[tuple[str, int]] = []
    skipped_dividers = 0
    skipped_no_breadcrumb = 0

    for rowid, section_filename, content, existing in rows:
        first_line = (content or "").strip().split("\n", 1)[0]

        # Track the current Book divider as we walk forward through sections.
        # The breadcrumb is "Book X — Subtitle" and applies to every canto
        # until the next BOOK divider replaces it.
        if first_line.startswith("BOOK "):
            current_book_breadcrumb = format_book_breadcrumb(first_line)
            skipped_dividers += 1
            continue

        # Part dividers are skipped without changing the current book (they
        # mark Part boundaries between Book groups, not new books).
        if first_line.startswith("PART "):
            skipped_dividers += 1
            continue

        # Only stamp cantos. Non-canto pages (preface, Author's Note,
        # Epilogue narrative, Note on the Text) are left alone — assigning
        # a Book breadcrumb to them would be misleading (e.g. Note on the
        # Text comes after Book Twelve but isn't part of it).
        if not is_canto_section(section_filename):
            continue

        if not current_book_breadcrumb:
            # Canto encountered before any BOOK divider — shouldn't happen in
            # a well-formed Savitri table of contents, but skip safely.
            skipped_no_breadcrumb += 1
            continue

        # Idempotency: only stage an UPDATE if the value would change. Lets
        # us re-run the script without churning timestamps or row metadata.
        if (existing or "") != current_book_breadcrumb:
            updates.append((current_book_breadcrumb, rowid))

    if updates:
        conn.executemany(
            "UPDATE chapters SET parent_toc_title = ? WHERE rowid = ?",
            updates,
        )
        conn.commit()

    conn.close()

    print(f"backfill_savitri_toc: scanned {len(rows)} rows, "
          f"skipped {skipped_dividers} dividers, "
          f"updated {len(updates)} cantos"
          + (f", skipped {skipped_no_breadcrumb} cantos before first BOOK"
             if skipped_no_breadcrumb else ""))
    return len(updates)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    repo_root = Path(__file__).resolve().parents[3]
    parser.add_argument(
        "--db",
        default=str(repo_root / "backend" / "db" / "chapters.db"),
        help="Path to chapters.db (default: backend/db/chapters.db)",
    )
    args = parser.parse_args()
    rc = backfill(Path(args.db))
    return 0 if rc >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
