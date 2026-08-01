#!/usr/bin/env python3
"""
graft_book_rows.py — replace one book's rows in the serving chapters.db with
the rows the splitter just built for it, leaving every other book untouched.

Why this exists: the splitter's build_chapter_index.py drops and rebuilds the
whole DB from its out_chapters/ tree, then syncs it into this repo. That's the
right tool for a corpus-wide rebuild, but the wrong one when a single book has
been re-split — the splitter tree can hold a whole generation of unshipped
changes (e.g. the 2026-07-23 running-header rebuild), and syncing it wholesale
to fix one book means shipping all of that unreviewed.

So: build the splitter's own DB with SKIP_SERVING_SYNC=1, then graft the one
book across with this. Row values come from the canonical builder rather than
being re-derived here, so slug/book_slug/non_content/page ranges stay consistent
with the rest of the corpus.

First used for 14VedicAndPhilologicalStudies (2026-08-01), whose PDF outline was
the typesetter's source-file list rather than a table of contents, so the
splitter had produced two "chapters" holding all 756 pages and the whole book was
unreachable. The same treatment is pending for the 3 AES books the running-header
pass skipped.

Safety: refuses to run if the incoming rows have empty slug/book_slug (the exact
state that made the book unreachable), and snapshots the DB before writing.

Usage — dry-run first, it prints the plan and changes nothing:
    python3 backend/scripts/helpers/graft_book_rows.py --book 14VedicAndPhilologicalStudies
    python3 backend/scripts/helpers/graft_book_rows.py --book 14VedicAndPhilologicalStudies --write

Then ship the data per docs/DEPLOY.md §3 — this only touches the local DB.
"""

import argparse
import shutil
import sqlite3
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
# The splitter repo is a sibling checkout; its DB is the build output we graft from.
DEFAULT_SOURCE = BACKEND_DIR.parent.parent / 'collectedworks' / 'db' / 'chapters.db'
DEFAULT_TARGET = BACKEND_DIR / 'db' / 'chapters.db'


def columns(conn):
    return [r[1] for r in conn.execute('PRAGMA table_info(chapters)')]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--book', required=True, help='book_folder to graft')
    ap.add_argument('--source', default=str(DEFAULT_SOURCE), help="splitter's chapters.db")
    ap.add_argument('--target', default=str(DEFAULT_TARGET), help='serving chapters.db')
    ap.add_argument('--write', action='store_true', help='apply (default: dry-run)')
    args = ap.parse_args()

    for path in (args.source, args.target):
        if not Path(path).exists():
            sys.exit(f'not found: {path}')

    src = sqlite3.connect(f'file:{args.source}?mode=ro', uri=True)
    tgt = sqlite3.connect(args.target)

    src_cols, tgt_cols = columns(src), columns(tgt)
    if src_cols != tgt_cols:
        sys.exit(f'schema mismatch\n  source: {src_cols}\n  target: {tgt_cols}')

    col_list = ', '.join(src_cols)
    new_rows = src.execute(
        f'SELECT {col_list} FROM chapters WHERE book_folder = ?', (args.book,)).fetchall()
    old_rows = tgt.execute(
        f'SELECT {col_list} FROM chapters WHERE book_folder = ?', (args.book,)).fetchall()

    i_slug, i_bslug, i_sec = (src_cols.index(c) for c in ('slug', 'book_slug', 'section_filename'))

    def describe(rows, label):
        print(f'{label}: {len(rows)} rows')
        for r in rows[:4]:
            print(f'    slug={r[i_slug]!r:<46} book_slug={r[i_bslug]!r:<32} {r[i_sec]}')
        if len(rows) > 4:
            print(f'    ... {len(rows) - 4} more')

    describe(old_rows, 'CURRENT in serving DB')
    describe(new_rows, 'INCOMING from splitter DB')

    if not new_rows:
        sys.exit('refusing to run: the source DB has no rows for this book')
    unreachable = [r for r in new_rows if not r[i_slug] or not r[i_bslug]]
    if unreachable:
        sys.exit(f'refusing to run: {len(unreachable)} incoming rows have an empty '
                 'slug/book_slug and would be unreachable via /read/')

    total_before = tgt.execute('SELECT count(*) FROM chapters').fetchone()[0]
    print(f'\nserving DB total rows: {total_before}')
    print(f'plan: delete {len(old_rows)}, insert {len(new_rows)} '
          f'→ {total_before - len(old_rows) + len(new_rows)}')

    if not args.write:
        print('\n--dry-run: nothing written')
        return

    backup = Path(f'{args.target}.bak-{time.strftime("%Y%m%d-%H%M%S")}-pre-graft-{args.book}')
    shutil.copy2(args.target, backup)
    print(f'backed up -> {backup}')

    placeholders = ', '.join('?' * len(src_cols))
    with tgt:
        tgt.execute('DELETE FROM chapters WHERE book_folder = ?', (args.book,))
        tgt.executemany(
            f'INSERT INTO chapters ({col_list}) VALUES ({placeholders})', new_rows)

    total_after = tgt.execute('SELECT count(*) FROM chapters').fetchone()[0]
    grafted = tgt.execute(
        'SELECT count(*) FROM chapters WHERE book_folder = ?', (args.book,)).fetchone()[0]
    print(f'done: total rows {total_before} → {total_after}, book rows now {grafted}')
    print('reminder: copy the new section_*.txt into backend/data/out_chapters/, '
          'then ship both per docs/DEPLOY.md §3')


if __name__ == '__main__':
    main()
