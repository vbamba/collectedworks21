#!/usr/bin/env python3
"""
build_canonical_overrides.py — point duplicate chapters at one canonical copy.

Some texts appear in more than one volume: "The Divine Body" is printed in both
Essays in Philosophy and Yoga and The Supramental Manifestation; several poems
appear in Collected Poems, Lyrical Poems and The Future Poetry; Purani's Evening
Talks prints the 11 November 1923 talk twice, at pages 178-180 and 334-337. Each
copy self-canonicalises, so Google clusters them, picks a representative itself,
and reports the rest under "Duplicate, Google chose different canonical than
user". This map makes the choice ours instead.

The output is deliberately a reviewable JSON file rather than a rule applied at
request time, because for the 80-odd CWSA-internal pairs the choice of primary is
genuinely a matter of editorial preference — the rule below is defensible but
arbitrary, and any entry can be flipped by hand. Re-running preserves nothing,
so keep hand edits in mind before regenerating (or edit and don't regenerate).

Clustering is by the first 160 alphanumeric characters, which catches copies that
differ by a stray footnote marker. Two guards stop it grouping pages that merely
open alike:

  * length ratio — the shortest must be at least MIN_LENGTH_RATIO of the longest.
    This is what separates duplicates from EXCERPTS, and the distinction matters:
    india-the-mother/november-23-1963 (2,278 chars) is a compilation quoting part
    of agenda-vol-4/november-23-1963 (5,525). An excerpt is a different page with
    its own editorial context, not a duplicate, and rel=canonical would be the
    wrong tool — Google's own guidance reserves it for duplicates. 8 such
    clusters exist and are all skipped.
  * word-overlap similarity — every copy must be at least MIN_SIMILARITY similar
    to the shortest one, measured over word multisets. Exact-match sampling was
    tried first and was useless here: the two printings of the 11 November 1923
    talk are 99.1% identical but differ in ~25 scattered spots ("night" for
    "day", an inserted "for instance"), roughly one per 175 characters, so any
    sampled window straddles a difference. Word overlap tolerates that while
    still scoring an excerpt near 0.5.

Primary selection, in order:
  0. the copy must be indexable. Three poems were first assigned primaries that
     the splitter had flagged non_content — 344-594 character poems mistaken for
     front matter — so their secondaries pointed a canonical at a page serving
     noindex and absent from the sitemap. That tells Google "the real one is over
     there" while that page says "don't index me", and neither copy survives.
  1. group_name preference: an original collected-works volume beats a
     compilation or a disciple's book (CWSA > CWM > Disciples > Compilations)
  2. a slug without a positional `-2`…`-9` suffix. Those suffixes are assigned by
     section order, so they move when chapter boundaries change — pointing every
     other copy at one would hand the canonical URL to the least stable slug in
     the cluster. This decides the 11 November 1923 pair, where the `-2` copy is
     6 characters longer and would otherwise win on rule 3.
  3. the fuller volume, by chapter count. Collected Poems has 340 chapters
     against Lyrical Poems' 47 and The Future Poetry's 58; Essays in Philosophy
     and Yoga has 111 against The Problem of Rebirth's 24. The complete volume is
     the text's home, and a selection quoting from it is the copy. Without this,
     the length tiebreak below decided by which copy happened to carry one extra
     character, which sent 31 poems to Collected Poems and 2 the other way, and
     pointed 16 essays away from Essays in Philosophy and Yoga.
  4. longest text — the most complete copy
  5. (book_slug, slug) alphabetically, purely so the output is stable

Usage:
    python3 backend/scripts/helpers/build_canonical_overrides.py            # dry-run
    python3 backend/scripts/helpers/build_canonical_overrides.py --write
    python3 backend/scripts/helpers/build_canonical_overrides.py --show-clusters
"""

import argparse
import collections
import json
import re
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB = BACKEND_DIR / 'db' / 'chapters.db'
# Lives beside slug_redirects.json, under backend/app/ so it ships with the code
# (backend/data|db|indexes are all excluded from the deploy rsync).
DEFAULT_OUT = BACKEND_DIR / 'app' / 'data' / 'canonical_overrides.json'

MIN_CHARS = 200
FINGERPRINT_CHARS = 160
MIN_LENGTH_RATIO = 0.8
MIN_SIMILARITY = 0.9

# Keep in sync with _is_indexable() / MIN_INDEXABLE_CHARS / FRONT_MATTER_MAX_CHARS
# in backend/app/routes.py. Duplicated rather than imported because importing the
# app pulls in flask, faiss and nltk for what is three comparisons.
MIN_INDEXABLE_CHARS = 200
FRONT_MATTER_MAX_CHARS = 3000


def is_indexable(plain_len, non_content):
    if plain_len < MIN_INDEXABLE_CHARS:
        return False
    return not (non_content and plain_len < FRONT_MATTER_MAX_CHARS)

# Lower sorts first = preferred as the canonical copy.
GROUP_RANK = {'CWSA': 0, 'CWM': 1, 'Agenda': 2, 'Disciples': 3, 'Compilations': 4}

_TAG_RX = re.compile(r'<[^>]+>')
_WS_RX = re.compile(r'\s+')
_NON_ALNUM_RX = re.compile(r'[^a-z0-9]')
# A trailing -2..-9 is the splitter's dedup counter. Single digit on purpose: a
# four-digit year ("january-29-1969") must not look like a positional suffix.
_POSITIONAL_SUFFIX_RX = re.compile(r'-[2-9]$')


def searchable(content):
    return _NON_ALNUM_RX.sub('', _WS_RX.sub(' ', _TAG_RX.sub('', content or '')).lower())


def words(content):
    return collections.Counter(
        _WS_RX.sub(' ', _TAG_RX.sub('', content or '')).lower().split())


def similarity(a, b):
    """
    Overlap of two word multisets: 2*shared / (total_a + total_b). 1.0 for
    identical text, ~0.98 for the same talk printed twice with minor variants,
    and low for an excerpt against its source. Linear, unlike a diff ratio,
    which matters because some of these chapters run to 40,000 characters.
    """
    shared = sum((a & b).values())
    total = sum(a.values()) + sum(b.values())
    return (2 * shared / total) if total else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=str(DEFAULT_DB))
    ap.add_argument('--out', default=str(DEFAULT_OUT))
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--show-clusters', action='store_true',
                    help='print every cluster and its chosen primary')
    args = ap.parse_args()

    if not Path(args.db).exists():
        sys.exit(f'not found: {args.db}')
    conn = sqlite3.connect(f'file:{args.db}?mode=ro', uri=True)

    # Chapters per volume, for the "fuller volume wins" rule.
    book_size = {row[0]: row[1] for row in conn.execute(
        """
        SELECT book_slug, count(*) FROM chapters
         WHERE slug IS NOT NULL AND slug != ''
           AND book_slug IS NOT NULL AND book_slug != ''
         GROUP BY book_slug
        """
    )}

    clusters = collections.defaultdict(list)
    for coll, book_slug, slug, group_name, non_content, content in conn.execute(
        """
        SELECT collection_folder, book_slug, slug, group_name, non_content, content
          FROM chapters
         WHERE slug IS NOT NULL AND slug != ''
           AND book_slug IS NOT NULL AND book_slug != ''
        """
    ):
        text = searchable(content)
        if len(text) >= MIN_CHARS:
            plain_len = len(_WS_RX.sub(' ', _TAG_RX.sub('', content or '')).strip())
            clusters[text[:FINGERPRINT_CHARS]].append(
                (f'{coll}/{book_slug}/{slug}', group_name or '', text, words(content),
                 is_indexable(plain_len, bool(non_content))))

    overrides = {}
    skipped_excerpt = skipped_similarity = skipped_unindexable = 0
    reported = []

    for members in clusters.values():
        if len(members) < 2:
            continue
        lengths = [len(m[2]) for m in members]
        if min(lengths) < MIN_LENGTH_RATIO * max(lengths):
            skipped_excerpt += 1
            continue

        shortest = min(members, key=lambda m: len(m[2]))
        sims = [similarity(shortest[3], m[3]) for m in members if m[0] != shortest[0]]
        if min(sims) < MIN_SIMILARITY:
            skipped_similarity += 1
            continue

        if not any(m[4] for m in members):
            skipped_unindexable += 1
            continue

        primary = sorted(
            members,
            key=lambda m: (0 if m[4] else 1,
                           GROUP_RANK.get(m[1], 9),
                           1 if _POSITIONAL_SUFFIX_RX.search(m[0]) else 0,
                           -book_size.get(m[0].split('/')[1], 0),
                           -len(m[2]),
                           m[0])
        )[0]
        for key, _group, _text, _w, _ix in members:
            if key != primary[0]:
                overrides[key] = primary[0]
        reported.append((primary, members, min(sims)))

    print(f'{len(reported)} duplicate cluster(s), {len(overrides)} secondary page(s)')
    print(f'skipped: {skipped_excerpt} excerpt-like (length ratio), '
          f'{skipped_similarity} below {MIN_SIMILARITY} similarity, '
          f'{skipped_unindexable} with no indexable copy')

    if args.show_clusters:
        for primary, members, sim in sorted(reported, key=lambda r: r[0][0]):
            print(f'\n  primary: {primary[0]}  [{primary[1]}, {len(primary[2])} chars, '
                  f'similarity {sim:.3f}]')
            for key, group, text, _w, _ix in sorted(members):
                if key != primary[0]:
                    print(f'      →  {key}  [{group}, {len(text)} chars]')

    if not args.write:
        print('\n--dry-run: nothing written')
        return

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(overrides, indent=2, sort_keys=True, ensure_ascii=False) + '\n',
        encoding='utf-8')
    print(f'wrote {out_path}')


if __name__ == '__main__':
    main()
