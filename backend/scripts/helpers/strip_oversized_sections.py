#!/usr/bin/env python3
"""
strip_oversized_sections.py — drop catch-all "Page_N" sections that bundle a
whole book into one row, but only when that book is genuinely split elsewhere.

Supersedes strip_oversized_sections.sql, which hard-coded three
(book_folder, section_filename) pairs. Every rebuild that produces a new bundle
needed a new pair added by hand, and two were missed: Hymns to the Mystic Fire
carries a 924KB "page-13" alongside its 26 real chapters, indexable and
duplicating the book's own content.

Why not just delete anything oversized: Sunil - The Mother's Musician has a
563KB row that looks identical by that test, but it is the ONLY copy of that
book's text — its siblings are a title page, a picture page and a 4KB
introduction, because that PDF's outline is a list of source filenames rather
than a table of contents. Deleting it would remove the book from the site. The
size of a row says nothing on its own; what matters is whether its content
already lives in properly-split chapters.

So a row is deleted only when all three hold:

  1. it is over MIN_BUNDLE_BYTES — a real chapter this size is rare, and the
     ones that exist (Record of Yoga runs to ~216K characters) stay well under
  2. its book has at least MIN_SIBLINGS other rows carrying real text, i.e. the
     splitter did section this book properly
  3. sampled passages from the row are found verbatim in those siblings — direct
     evidence the text is duplicated, not unique to the bundle

Idempotent: a second run finds nothing, since the rows are gone.

Usage — dry-run first; it explains each verdict and changes nothing:
    python3 backend/scripts/helpers/strip_oversized_sections.py
    python3 backend/scripts/helpers/strip_oversized_sections.py --write
    python3 backend/scripts/helpers/strip_oversized_sections.py --db /path/to/chapters.db
"""

import argparse
import re
import shutil
import sqlite3
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB = BACKEND_DIR / 'db' / 'chapters.db'

# A row bigger than this is a bundle suspect. Chosen well above the largest
# genuine chapters in the corpus (Record of Yoga entries, ~216K characters) so
# real content is never even considered.
MIN_BUNDLE_BYTES = 400_000

# The book must look properly sectioned before we treat one row as redundant.
MIN_SIBLINGS = 5
MIN_SIBLING_BYTES = 50_000

# Duplication evidence: passages sampled from the middle of the suspect row.
SAMPLE_COUNT = 5
SAMPLE_CHARS = 120
MIN_SAMPLES_FOUND = 4      # of SAMPLE_COUNT

_TAG_RX = re.compile(r'<[^>]+>')
_WS_RX = re.compile(r'\s+')
_NON_ALNUM_RX = re.compile(r'[^a-z0-9]')


def searchable(content):
    """Text reduced to letters and digits, so markup and spacing can't block a match."""
    return _NON_ALNUM_RX.sub('', _WS_RX.sub(' ', _TAG_RX.sub('', content or '')).lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=str(DEFAULT_DB))
    ap.add_argument('--write', action='store_true', help='apply (default: dry-run)')
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        sys.exit(f'not found: {db_path}')
    conn = sqlite3.connect(str(db_path))

    suspects = conn.execute(
        """
        SELECT rowid, book_folder, section_filename, slug,
               length(cast(content as blob)), content
          FROM chapters
         WHERE length(cast(content as blob)) > ?
         ORDER BY length(cast(content as blob)) DESC
        """,
        (MIN_BUNDLE_BYTES,),
    ).fetchall()

    print(f'{len(suspects)} row(s) over {MIN_BUNDLE_BYTES:,} bytes\n')
    doomed = []

    for rowid, book_folder, section_filename, slug, size, content in suspects:
        print(f'{book_folder} / {section_filename}  ({size:,} bytes, slug={slug!r})')

        siblings = conn.execute(
            """
            SELECT content FROM chapters
             WHERE book_folder = ? AND rowid != ?
               AND length(cast(content as blob)) > 2000
            """,
            (book_folder, rowid),
        ).fetchall()
        sibling_bytes = sum(len((c or '').encode('utf-8')) for (c,) in siblings)

        if len(siblings) < MIN_SIBLINGS or sibling_bytes < MIN_SIBLING_BYTES:
            print(f'   KEEP — book is not properly split ({len(siblings)} substantial '
                  f'siblings, {sibling_bytes:,} bytes). This row may be the only copy '
                  f'of the text; it needs an outline reconstruction, not a delete.\n')
            continue

        haystack = ''.join(searchable(c) for (c,) in siblings)
        body = searchable(content)
        if len(body) < SAMPLE_CHARS * (SAMPLE_COUNT + 2):
            print('   KEEP — too little text to sample reliably.\n')
            continue

        step = len(body) // (SAMPLE_COUNT + 1)
        found = sum(1 for i in range(1, SAMPLE_COUNT + 1)
                    if body[i * step:i * step + SAMPLE_CHARS] in haystack)
        if found < MIN_SAMPLES_FOUND:
            print(f'   KEEP — only {found}/{SAMPLE_COUNT} sampled passages found in '
                  f'sibling chapters; this text looks unique to this row.\n')
            continue

        print(f'   DELETE — {found}/{SAMPLE_COUNT} sampled passages already present in '
              f'{len(siblings)} sibling chapters ({sibling_bytes:,} bytes).\n')
        doomed.append((rowid, book_folder, section_filename))

    if not doomed:
        print('nothing to strip.')
        return

    print(f'{len(doomed)} row(s) to delete:')
    for _rowid, bf, sf in doomed:
        print(f'   {bf} / {sf}')

    if not args.write:
        print('\n--dry-run: nothing written')
        return

    backup = Path(f'{db_path}.bak-{time.strftime("%Y%m%d-%H%M%S")}-pre-strip')
    shutil.copy2(db_path, backup)
    print(f'\nbacked up -> {backup}')
    with conn:
        conn.executemany('DELETE FROM chapters WHERE rowid = ?',
                         [(rowid,) for rowid, _bf, _sf in doomed])
    print(f'deleted {len(doomed)} row(s); '
          f'{conn.execute("SELECT count(*) FROM chapters").fetchone()[0]} rows remain')


if __name__ == '__main__':
    main()
