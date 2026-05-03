#!/usr/bin/env python3
"""
strip_savitri_running_headers.py — drop the PDF page-running header that the
chapters splitter pulled into Savitri canto bodies.

Each affected canto carries lines like

    CANTO IV:<i> The Secret Knowledge</i>          (on disk, italics intact)
    CANTO IV:  The Secret Knowledge                (in chapters.db, italics
                                                    stripped during indexing)

at every PDF page boundary — roughly 10–15 occurrences per affected canto,
across 18 cantos. The line is a duplicate of the canto title that already
sits at the top of the section, so it adds nothing for the reader and just
clutters search results that hit the title text.

Strips those lines from BOTH:
  * the on-disk section .txt files under OUT_CHAPTERS_DIR
  * the chapters.content column in chapters.db (FTS5 reindexes on UPDATE)

Leaves the opening "Canto Four / The Secret Knowledge" title block at the
top of each section alone, and leaves the trailing "END OF CANTO X" line
alone (out of scope for this script — those are section delimiters, not the
canto name the user wanted hidden).

Idempotent: re-running on a cleaned tree/DB makes no further changes. Re-run
after every chapters.db / out_chapters rebuild — sync_from_splitter.sh
invokes this automatically; deploy_to_ec2.sh runs the DB pass on prod.

Usage:
    python3 backend/scripts/helpers/strip_savitri_running_headers.py \
        [--db PATH] [--out-chapters PATH] [--dry-run]
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path

# CHANGED: scope is Savitri only. 02CollectedPoems and 05Translations also
# contain lines starting with "CANTO" but those are legitimate poem titles
# (e.g. translations of Italian cantos), not page-running headers — so we
# restrict by collection + book_folder rather than running across the table.
COLLECTION = "sriaurobindo"
BOOK_FOLDER = "33-34Savitri"

# CHANGED: matches the running-header line in either form. Anchored at start
# of line, requires "CANTO" + roman-numeral run + ":" so it can never match a
# verse line that happens to start with the word "Canto" (the opening title
# block is "Canto Four", title-case with no colon — safely excluded).
_HEADER_RE = re.compile(r'^\s*CANTO\s+[IVXLCDM]+\s*:.*$')


def strip_lines(text: str) -> tuple[str, int]:
    """Drop running-header lines. Returns (new_text, lines_removed)."""
    if not text:
        return text, 0
    # CHANGED: keepends=True so we preserve the file's original line endings
    # exactly — the splitter emits LF-terminated lines and round-tripping
    # through write_text would otherwise normalise based on the platform.
    kept = [line for line in text.splitlines(keepends=True)
            if not _HEADER_RE.match(line)]
    new_text = ''.join(kept)
    removed = len(text.splitlines()) - len(new_text.splitlines())
    return new_text, removed


def strip_disk(out_chapters: Path, dry_run: bool) -> tuple[int, int]:
    """Walk Savitri section files. Returns (files_changed, lines_removed)."""
    book_dir = out_chapters / COLLECTION / BOOK_FOLDER
    if not book_dir.is_dir():
        print(f"WARN: Savitri folder not found at {book_dir}; skipping disk pass",
              file=sys.stderr)
        return 0, 0

    files_changed = 0
    lines_removed = 0
    for txt in sorted(book_dir.glob("section_*.txt")):
        original = txt.read_text(encoding='utf-8')
        new_text, removed = strip_lines(original)
        if removed:
            files_changed += 1
            lines_removed += removed
            if not dry_run:
                txt.write_text(new_text, encoding='utf-8')
    return files_changed, lines_removed


def strip_db(db_path: Path, dry_run: bool) -> tuple[int, int]:
    """Update chapters.content in place. Returns (rows_changed, lines_removed)."""
    if not db_path.exists():
        print(f"WARN: chapters.db not found at {db_path}; skipping DB pass",
              file=sys.stderr)
        return 0, 0

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT rowid, content FROM chapters WHERE book_folder = ?",
            (BOOK_FOLDER,),
        ).fetchall()
    except sqlite3.OperationalError as e:
        print(f"ERROR: query failed (DB schema mismatch?): {e}", file=sys.stderr)
        conn.close()
        return -1, -1

    rows_changed = 0
    lines_removed = 0
    updates: list[tuple[str, int]] = []
    for rowid, content in rows:
        new_content, removed = strip_lines(content or '')
        if removed:
            rows_changed += 1
            lines_removed += removed
            updates.append((new_content, rowid))

    if updates and not dry_run:
        # FTS5 reindexes the row's tokens on UPDATE, so search hits for the
        # canto title will stop matching the running-header occurrences after
        # this commit lands.
        conn.executemany(
            "UPDATE chapters SET content = ? WHERE rowid = ?",
            updates,
        )
        conn.commit()
    conn.close()
    return rows_changed, lines_removed


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
        "--out-chapters",
        default=str(repo_root / "backend" / "data" / "out_chapters"),
        help="Path to OUT_CHAPTERS_DIR (default: backend/data/out_chapters)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing.",
    )
    # CHANGED: --db-only / --disk-only let deploy_to_ec2.sh run just the DB
    # pass on prod (where out_chapters is rsynced from local, already cleaned).
    parser.add_argument("--db-only", action="store_true",
                        help="Skip the disk pass (DB only).")
    parser.add_argument("--disk-only", action="store_true",
                        help="Skip the DB pass (disk only).")
    args = parser.parse_args()

    if args.db_only and args.disk_only:
        print("ERROR: --db-only and --disk-only are mutually exclusive",
              file=sys.stderr)
        return 2

    prefix = "[dry-run] " if args.dry_run else ""

    if not args.db_only:
        files, lines = strip_disk(Path(args.out_chapters), args.dry_run)
        print(f"{prefix}disk: stripped {lines} lines from {files} files "
              f"under {args.out_chapters}/{COLLECTION}/{BOOK_FOLDER}")
    if not args.disk_only:
        rows, lines = strip_db(Path(args.db), args.dry_run)
        if rows < 0:
            return 1
        print(f"{prefix}db:   stripped {lines} lines from {rows} rows "
              f"in {args.db}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
