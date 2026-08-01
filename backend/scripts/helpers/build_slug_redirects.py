#!/usr/bin/env python3
"""
build_slug_redirects.py — recover /read/ URLs that a chapters.db rebuild killed.

Why this exists: a chapter's slug carries a positional `-2`…`-9` dedup suffix,
assigned by section order within a book. When the splitter changes chapter
boundaries, sections shift, so the slug that pointed at a given passage before
the rebuild can point at a different passage afterwards — or disappear. Measured
2026-08-01: 404 previously-indexable /read/ URLs vanished between the
2026-06-25 build and the current one. Those URLs are live in Google's index and
in other people's links, and they currently return a hard 404.

Concretely: `agenda-vol-10/january-29-1969-2` used to hold the full 4,343-char
talk while the unsuffixed `january-29-1969` held a 476-char orphan fragment. The
rebuild merged the fragment back in, so the full talk now lives at the unsuffixed
slug and the `-2` URL is gone. Google had already indexed the `-2` URL, which is
why Search Console reports "Duplicate, Google chose different canonical than
user" on real chapter pages.

What it does: diffs one or more OLD chapters.db snapshots against the current
one. For every old URL that no longer resolves, it fingerprints the old chapter
text and looks for the current chapter holding that same text. Confident matches
are written to a JSON map that routes.py serves as a 301.

Matching is by content, not by title or slug, because slugs are exactly what
became unreliable. The fingerprint is the first 160 alphanumeric characters of
the chapter's text, lowercased. Matching runs in two passes:

  1. exact — the old chapter's fingerprint is also the opening of a current
     chapter. This is the renamed-or-reshuffled case.
  2. containment — the old chapter's opening appears *inside* a current chapter,
     anywhere. This is the merged-fragment case: a stub that the boundary fix
     folded back into the day's full entry. Restricted to the same book, so a
     passage quoted in two volumes can't pull a redirect across books.

Two guards keep both passes honest:
  - chapters shorter than MIN_CHARS are skipped — short stubs collide trivially
  - a fingerprint matching more than one current chapter is skipped as ambiguous

Old rows with an empty collection_folder are skipped: their URL would have been
`/read//book/slug`, which the Flask route can't match (empty path segment), so
those URLs were never reachable and need no redirect.

The output file accumulates across runs — an old snapshot processed today stays
mapped after tomorrow's rebuild, as long as its target still exists. Entries
whose target has since disappeared are dropped, and any entry whose source slug
has come back to life is dropped too (a live page must never redirect).

Run this after every re-split / chapters.db rebuild, like the other post-rebuild
chores (normalize_ligatures.py, strip_oversized_sections.sql).

Usage:
    # after a rebuild, diff against the snapshot you kept from before it
    python3 backend/scripts/helpers/build_slug_redirects.py \
        --old backend/db/chapters.db.prerebuild-20260625

    # several snapshots at once (older generations of indexed URLs)
    python3 backend/scripts/helpers/build_slug_redirects.py \
        --old backend/db/chapters.db.prerebuild-20260625 \
        --old backend/db/chapters.db.prerebuild-20260711

    --dry-run       report what would change, write nothing
    --replace       start a fresh map instead of merging into the existing one
    --db PATH       current chapters.db      (default backend/db/chapters.db)
    --out PATH      redirect map destination (default backend/data/slug_redirects.json)
"""

import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB = BACKEND_DIR / 'db' / 'chapters.db'
# Lives under backend/app/ on purpose: backend/data/, backend/db/ and
# backend/indexes/ are all .gitignored AND excluded from the deploy rsync
# (see deploy_to_ec2.sh), so a map written there would never reach prod. This
# file is small (~10KB) hand-checkable data that should travel with the code.
DEFAULT_OUT = BACKEND_DIR / 'app' / 'data' / 'slug_redirects.json'

# Below this many characters of text a chapter is a fragment, not a page: its
# fingerprint is short enough to collide with unrelated stubs. 449 pages in the
# current build are under 200 chars, and they are precisely the fragmentation
# artifacts we don't want to map.
MIN_CHARS = 200

# Fingerprint width. 160 alphanumeric characters is roughly two sentences —
# long enough to be unique across a 68M-character corpus, short enough to
# survive the punctuation and italic-markup churn between builds.
FINGERPRINT_CHARS = 160

_TAG_RX = re.compile(r'<[^>]+>')
_WS_RX = re.compile(r'\s+')
_NON_ALNUM_RX = re.compile(r'[^a-z0-9 ]')

INDEXABLE_SQL = """
    SELECT collection_folder, book_slug, slug, content
      FROM chapters
     WHERE non_content = 0
       AND slug IS NOT NULL AND slug != ''
       AND book_slug IS NOT NULL AND book_slug != ''
"""

# Everything the /read/ route can resolve, front matter included. The route
# doesn't filter on non_content — a TOC page is served, just not indexed — so a
# slug present here must never be redirected, even though it's absent from
# INDEXABLE_SQL.
SERVED_SQL = """
    SELECT collection_folder, book_slug, slug
      FROM chapters
     WHERE slug IS NOT NULL AND slug != ''
       AND book_slug IS NOT NULL AND book_slug != ''
"""


def plain_text(content: str) -> str:
    """Chapter text with italic markup and line wrapping removed."""
    return _WS_RX.sub(' ', _TAG_RX.sub('', content or '')).strip()


def fingerprint(content: str) -> str:
    """
    Content key used to match an old chapter to its current home. Returns ''
    for anything too short to match safely — callers treat that as "skip".
    """
    text = plain_text(content)
    if len(text) < MIN_CHARS:
        return ''
    return _NON_ALNUM_RX.sub('', text.lower())[:FINGERPRINT_CHARS]


def url_key(collection: str, book_slug: str, slug: str) -> str:
    """The /read/ path minus the /read/ prefix — how the map is keyed."""
    return f"{collection}/{book_slug}/{slug}"


def load_rows(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute(INDEXABLE_SQL).fetchall()
    finally:
        conn.close()


def searchable(content: str) -> str:
    """Full chapter text reduced to the same alphabet as fingerprint(), so a
    fingerprint can be looked for inside it with a plain substring test."""
    return _NON_ALNUM_RX.sub('', plain_text(content).lower())


def index_current(db_path: Path):
    """
    Returns (live_keys, fingerprint -> [key, ...], (collection, book_slug) ->
    [(key, searchable_text), ...]) for the current build.

    live_keys covers every slug the route can serve, so a page that is merely
    unindexable (front matter) is never mistaken for a deleted one. The two
    content indexes cover indexable chapters only — redirect targets should be
    real chapters. Fingerprints with more than one key are ambiguous and
    rejected at lookup; the per-book index backs the containment pass.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        live = {url_key(*row) for row in conn.execute(SERVED_SQL)}
    finally:
        conn.close()

    by_fp = defaultdict(list)
    by_book = defaultdict(list)
    for collection, book_slug, slug, content in load_rows(db_path):
        key = url_key(collection, book_slug, slug)
        fp = fingerprint(content)
        if fp:
            by_fp[fp].append(key)
        by_book[(collection, book_slug)].append((key, searchable(content)))
    return live, by_fp, by_book


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--old', action='append', default=[], required=True,
                    help='pre-rebuild chapters.db snapshot (repeatable)')
    ap.add_argument('--db', default=str(DEFAULT_DB), help='current chapters.db')
    ap.add_argument('--out', default=str(DEFAULT_OUT), help='redirect map JSON')
    ap.add_argument('--dry-run', action='store_true', help='report only, write nothing')
    ap.add_argument('--replace', action='store_true',
                    help='discard the existing map instead of merging into it')
    args = ap.parse_args()

    current_db = Path(args.db)
    out_path = Path(args.out)
    if not current_db.exists():
        sys.exit(f"current db not found: {current_db}")

    live, by_fp, by_book = index_current(current_db)
    print(f"current build: {len(live)} slugs served, "
          f"{len(by_fp)} distinct content fingerprints")

    # Start from the existing map so earlier snapshots stay covered, then drop
    # anything that has gone stale (target deleted, or source slug revived).
    redirects = {}
    if out_path.exists() and not args.replace:
        redirects = json.loads(out_path.read_text(encoding='utf-8'))
        stale_target = [k for k, v in redirects.items() if v not in live]
        revived = [k for k in redirects if k in live]
        for k in stale_target + revived:
            redirects.pop(k, None)
        print(f"existing map: {len(redirects)} entries kept, "
              f"{len(stale_target)} dropped (target gone), {len(revived)} dropped (source is live again)")

    added = 0
    for old_db in args.old:
        old_path = Path(old_db)
        if not old_path.exists():
            sys.exit(f"old db not found: {old_path}")

        vanished = unrouteable = too_short = ambiguous = unmatched = 0
        exact = contained = 0
        for collection, book_slug, slug, content in load_rows(old_path):
            key = url_key(collection, book_slug, slug)
            if key in live:
                continue
            vanished += 1
            if not collection:
                # `/read//book/slug` never matched the route — nothing to redirect.
                unrouteable += 1
                continue
            fp = fingerprint(content)
            if not fp:
                too_short += 1
                continue

            targets = by_fp.get(fp, [])
            if len(targets) > 1:
                ambiguous += 1
                continue
            if targets:
                exact += 1
            else:
                # Pass 2: the old chapter was a fragment folded into a longer
                # current chapter. Look for its opening inside every chapter of
                # the same book.
                targets = [k for k, text in by_book.get((collection, book_slug), [])
                           if fp in text]
                if not targets:
                    unmatched += 1
                    continue
                if len(targets) > 1:
                    ambiguous += 1
                    continue
                contained += 1

            if redirects.get(key) != targets[0]:
                added += 1
            redirects[key] = targets[0]

        print(f"\n{old_path.name}:")
        print(f"  vanished URLs      {vanished}")
        print(f"  → mapped exactly                    {exact}")
        print(f"  → mapped by containment (merged)    {contained}")
        print(f"  unrouteable (no collection_folder)  {unrouteable}")
        print(f"  too short to match safely           {too_short}")
        print(f"  ambiguous fingerprint               {ambiguous}")
        print(f"  no match in current build           {unmatched}")

    print(f"\nmap: {len(redirects)} entries total ({added} new/changed)")
    for key in sorted(redirects)[:5]:
        print(f"  /read/{key}\n      → /read/{redirects[key]}")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(redirects, indent=2, sort_keys=True, ensure_ascii=False) + '\n',
        encoding='utf-8')
    print(f"wrote {out_path}")


if __name__ == '__main__':
    main()
