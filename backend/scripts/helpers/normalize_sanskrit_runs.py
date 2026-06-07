#!/usr/bin/env python3
"""
normalize_sanskrit_runs.py — conservative cleanup of split italic spans
in chapter .txt files extracted from PDFs.

Why this exists: fitz frequently splits a single italic Sanskrit phrase
into multiple <i>...</i> spans separated by blank lines when the phrase
wraps across a line or page boundary, and sometimes leaves an empty
<i></i> behind when a span's content was lost in extraction. The text
is readable but renders as broken italics in the viewer.

What it does (both idempotent):
  1. Delete empty <i></i> spans (and the line they sit on).
  2. Merge two adjacent <i>X</i> ... <i>Y</i> spans separated only by a
     blank line, but ONLY when X ends mid-word (letter or hyphen). If
     X ends with sentence punctuation we treat the two as legitimately
     separate italic emphases (e.g. poem stanzas) and leave them alone.

What it does NOT do: re-attach orphan combining diacritics (ṁ ṣ ḥ etc.)
to their containing words. That artifact lands them on their own line
between or after italic spans, and recovering the correct insertion
point requires PDF text-run coordinates (fitz `get_text("dict")`). That
fix belongs in split_pdf.py, not here — tracked as the B1 follow-up.

Usage:
    python3 backend/scripts/helpers/normalize_sanskrit_runs.py
    python3 backend/scripts/helpers/normalize_sanskrit_runs.py --dry-run
    python3 backend/scripts/helpers/normalize_sanskrit_runs.py --txt-root /custom/path
"""

import argparse
import re
import sys
from pathlib import Path

# CHANGED (2026-06-06): merge only short spans where BOTH contain at least
# one IAST diacritic (ā ī ū ṁ ṣ etc.). Built as a frozenset of explicit
# single-codepoint chars — DO NOT use set('…') over a literal containing
# combining-mark sequences like R̥, which Python decomposes character-by-
# character and silently leaks the base Latin letter into the set.
IAST_DIACRITICS = frozenset([
    'ṁ','ḥ','ḍ','ṅ','ṇ','ṛ','ḷ','ḻ','ś','ṣ','ṭ','ñ','ṃ',
    'ā','ī','ū','ē','ō','Ā','Ī','Ū','Ē','Ō',
    'Ḥ','Ṣ','Ḍ','Ṅ','Ṇ','Ṛ','Ḷ','Ḻ','Ś','Ṭ','Ñ','Ṃ',
])

# Why 60: real Sanskrit/transliteration phrases in this corpus are short
# (typically < 40 chars: "Śarīraṁ khalu dharmasādhanam", "sūkṣma śarīra").
# Long italic continuations (>60 chars on either side) are usually English
# prose that wrapped across a page break — and the page break may have
# inserted a running header BETWEEN the spans, producing garbage merges
# like "...such a New Correspondences of the Mother — II thing.". Leave
# those for B1 (splitter-level fix that can see the running header).
MAX_SPAN_LEN = 60

def _has_iast(s: str) -> bool:
    return any(c in IAST_DIACRITICS for c in s)

def _should_merge(left_content: str, right_content: str) -> bool:
    left_s = left_content.rstrip()
    right_s = right_content.lstrip()
    if not left_s or not right_s:
        return False
    if not (_has_iast(left_s) and _has_iast(right_s)):
        return False
    if len(left_s) > MAX_SPAN_LEN or len(right_s) > MAX_SPAN_LEN:
        return False
    if left_s == right_s:  # adjacent duplicate running headers
        return False
    last = left_s[-1]
    return last.isalpha() or last in '-–—'


# CHANGED (2026-06-06): match ONLY truly empty <i></i> (zero chars between
# the tags). NOT <i> </i> — that's a single-space italic, used heavily in
# metric scansion notation in TheFuturePoetry and LettersOnPoetryAndArt,
# where the space character is meaningful text content. Deleting those
# would silently corrupt 768 such spans.
EMPTY_ITALIC = re.compile(r'<i></i>\s*\n?')

# CHANGED (2026-06-06): join orphan-leading-punctuation continuations.
# Pattern: a word char ending a line, followed by a line starting with one
# of ',;:'  — typically PDF extraction breaking a phrase across lines.
# Conservative on the punctuation class — skip '.?!' which usually end
# sentences (joining "Hello.\n? she asked" → "Hello.? she asked" is wrong).
# Also requires the preceding char to be a word char (\w), so cases like
# "end.\n,then" don't produce ".,then".
JOINING_PUNCT_LEAD = re.compile(r'(\w)[^\S\n]*\n[^\S\n]*([,;:])')
SPLIT_ITALIC = re.compile(
    r'<i>([^<]*?)</i>'     # group 1: left italic content
    r'(\s*\n\s*\n\s*)'     # group 2: at least one blank line between
    r'<i>([^<]*?)</i>'     # group 3: right italic content
)


def _merge_callback(m: re.Match) -> str:
    left, _gap, right = m.group(1), m.group(2), m.group(3)
    if not _should_merge(left, right):
        return m.group(0)  # leave untouched
    merged = re.sub(r' +', ' ', left.rstrip() + ' ' + right.lstrip())
    return f'<i>{merged}</i>'


def clean(text: str) -> tuple[str, int, int, int]:
    """Return (new_text, empty_italic_deletions, span_merges, punct_joins)."""
    deletions = len(EMPTY_ITALIC.findall(text))
    text = EMPTY_ITALIC.sub('', text)

    merges = 0
    # Loop the split-italic pass: each pass merges at most one element of
    # any chain (re.subn handles non-overlapping matches in one sweep, but
    # a 3-span chain needs two passes).
    while True:
        before_spans = text.count('<i>')
        new_text, _ = SPLIT_ITALIC.subn(_merge_callback, text)
        if new_text == text:
            break
        after_spans = new_text.count('<i>')
        merges += before_spans - after_spans
        text = new_text

    # CHANGED (2026-06-06): punctuation-hugs pass. Run after italic merges
    # so newly-merged content participates. Loop until stable in case a
    # join enables another (rare but possible with cascading orphans).
    joins = 0
    while True:
        new_text, n = JOINING_PUNCT_LEAD.subn(r'\1\2', text)
        if n == 0:
            break
        joins += n
        text = new_text
    return text, deletions, merges, joins


def run(root: Path, dry_run: bool) -> int:
    if not root.exists():
        print(f"ERROR: {root} not found", file=sys.stderr)
        return 1
    scanned = 0
    files_changed = 0
    total_deletions = 0
    total_merges = 0
    total_joins = 0
    changed_files: list[tuple[str, int, int, int]] = []
    for path in sorted(root.rglob('*.txt')):
        scanned += 1
        text = path.read_text(encoding='utf-8')
        new_text, d, m, j = clean(text)
        if new_text != text:
            files_changed += 1
            total_deletions += d
            total_merges += m
            total_joins += j
            changed_files.append((str(path.relative_to(root)), d, m, j))
            if not dry_run:
                tmp = path.with_suffix(path.suffix + '.tmp')
                tmp.write_text(new_text, encoding='utf-8')
                tmp.replace(path)
    verb = 'would rewrite' if dry_run else 'rewrote'
    print(f'scanned {scanned} files; {verb} {files_changed}.')
    print(f'  empty-italic deletions: {total_deletions}')
    print(f'  split-italic merges:    {total_merges}')
    print(f'  punctuation-hug joins:  {total_joins}')
    if changed_files:
        print('\ntop 25 changed files (by total operations):')
        for f, d, m, j in sorted(changed_files, key=lambda x: -(x[1] + x[2] + x[3]))[:25]:
            print(f'  delete={d:>3}  merge={m:>3}  join={j:>4}  {f}')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    repo_root = Path(__file__).resolve().parents[3]
    parser.add_argument(
        '--txt-root',
        default=str(repo_root / 'backend' / 'data' / 'out_chapters'),
        help='Root of out_chapters tree (default: backend/data/out_chapters)',
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Report what would change; make no writes.')
    args = parser.parse_args()
    return run(Path(args.txt_root), args.dry_run)


if __name__ == '__main__':
    sys.exit(main())
