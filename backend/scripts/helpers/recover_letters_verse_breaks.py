#!/usr/bin/env python3
# CHANGED: New helper. PDF extraction collapsed Savitri verse quotes embedded
# inside Letters-on-Savitri (and similar) <i>...</i> blocks into a single line.
# This script restores verse line breaks by matching the italicised quotes
# against canonical Savitri text (line-start fingerprints) and inserting
# inline <br/> markers in the source .txt. Re-runnable (idempotent).
#
# Why <br/>: source files are consumed by app/routes._render_chapter_template
# which reflows prose by joining lines with spaces. Real \n breaks inside an
# italic block would be silently re-joined; <br/> survives reflow + DOMPurify
# and renders as a visible line break on the chapter page.
#
# Usage:  python3 backend/scripts/helpers/recover_letters_verse_breaks.py [--dry-run]

import argparse
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT_BASE = ROOT / "backend" / "data" / "out_chapters" / "sriaurobindo"
SAVITRI_DIR = OUT_BASE / "33-34Savitri"
# CHANGED: target books that quote Savitri verse. Letters-on-Savitri is the
# primary case; extend this list if other books show the same problem.
TARGET_DIRS = [
    OUT_BASE / "Letters-on-Savitri",
]

# CHANGED: how many leading words of a Savitri line we treat as a "fingerprint"
# for detecting that line's start inside an italicised prose-stream. 4 keeps
# false-positives rare while still catching short lines.
FINGERPRINT_N = 4

# CHANGED: only consider italic blocks that plausibly contain >1 verse line.
MIN_ITALIC_WORDS = 12

# CHANGED (2026-05-17): per-line word-diff tolerance when validating that a
# candidate Savitri line matches the italic stream at position i. Allows the
# verse-quote in the letters to differ from canonical Savitri by a single
# token (covers OCR errors like "metfs" for "men's" and Sri Aurobindo's own
# in-letter rewordings like "As ocean" for canonical "An ocean").
MAX_LINE_DIFF = 1

LIGATURE_MAP = str.maketrans({
    "ﬁ": "fi",
    "ﬂ": "fl",
    "’": "'",
    "‘": "'",
    "“": '"',
    "”": '"',
})

# CHANGED: punctuation becomes whitespace (NOT removed) so that hyphenated
# words like "self-poised" / "earth-stuff" / "temple-door" tokenize the same
# way in Savitri ("self-poised") and in Letters where the same word might
# appear unhyphenated ("temple door"). Both yield normalized tokens
# ["self","poised"] / ["temple","door"] etc. Apostrophes are dropped entirely
# (not spaced) so "earth's" -> "earths" rather than "earth s".
_punct_rx = re.compile(r"[^\w\s']")
_apos_rx = re.compile(r"'")


_stray_apos_s_rx = re.compile(r"[A-Za-z]'$")


def _split_with_indices(text: str):
    """
    Tokenize `text` and return (orig_tokens, norm_tokens, orig_idx_per_norm).
    A single original token can yield 2+ normalized tokens (e.g. "self-poised"
    -> ["self","poised"]); `orig_idx_per_norm[k]` maps norm token k back to the
    index of the original token it came from, so insertion points stay aligned.

    CHANGED (2026-05-17): merge a stray-spaced possessive ("Truth'" + "s" ->
    "Truth's"). The PDF extraction for Letters-on-Savitri sporadically split
    "X's" into two tokens around the apostrophe; canonical Savitri keeps them
    joined, so without merging here the line-diff check sees a phantom extra
    token and rejects an otherwise-perfect verse line. As a side effect this
    also cleans up the rendered text (no more "earth' s wideness").
    """
    raw = re.findall(r"\S+", text)
    orig_tokens: list = []
    k = 0
    while k < len(raw):
        t = raw[k]
        nxt = raw[k + 1] if k + 1 < len(raw) else ""
        if (_stray_apos_s_rx.search(t)
                and nxt[:1].lower() == "s"
                and len(nxt) <= 2):  # "s" or "s." or "s,"
            orig_tokens.append(t + nxt)
            k += 2
        else:
            orig_tokens.append(t)
            k += 1

    norm_tokens: list = []
    orig_idx: list = []
    for i, tok in enumerate(orig_tokens):
        n = unicodedata.normalize("NFKC", tok).translate(LIGATURE_MAP)
        n = _apos_rx.sub("", n)            # earth's -> earths
        n = _punct_rx.sub(" ", n)          # self-poised -> self poised
        for sub in n.split():
            sub = sub.lower()
            if sub:
                norm_tokens.append(sub)
                orig_idx.append(i)
    return orig_tokens, norm_tokens, orig_idx


def load_savitri_lines() -> dict:
    """
    Load canonical Savitri lines and a word→line-indices inverted index over
    each line's first FINGERPRINT_N words. Used to find candidate lines that
    might match a position in an italic block, allowing up to MAX_LINE_DIFF
    substitutions anywhere in the line — not just the first word — so we
    catch cases like canonical "In her he **found** a vastness…" matching the
    letter's "In her he **met** a vastness…" (1 substitution at position 3).
    """
    lines: list = []
    inv: dict = {}
    for path in sorted(SAVITRI_DIR.glob("section_*.txt")):
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("<"):
                continue
            _, norm_tokens, _ = _split_with_indices(line)
            if len(norm_tokens) < FINGERPRINT_N:
                continue
            words = tuple(norm_tokens)
            li = len(lines)
            lines.append(words)
            # Index each line under each unique word that appears in its first
            # FINGERPRINT_N positions. At lookup time we union the candidate
            # sets for italic[i..i+FINGERPRINT_N], so as long as at least one
            # of the first FINGERPRINT_N words survived unmodified in the
            # letter, we'll find the line.
            for w in set(words[:FINGERPRINT_N]):
                inv.setdefault(w, set()).add(li)
    return {"lines": lines, "inv": inv}


# CHANGED: matches one <i>...</i> span. Non-greedy; the source has these on
# single lines, but DOTALL keeps us safe if a future block spans newlines.
_italic_rx = re.compile(r"<i>(.*?)</i>", re.DOTALL)


def insert_breaks(inner: str, savitri_idx: dict) -> str:
    """Insert <br/> markers at detected Savitri-line starts inside an italic block."""
    # Skip blocks that already contain <br/> (idempotent re-run).
    if "<br" in inner.lower():
        return inner

    orig, norm, idx_map = _split_with_indices(inner)
    if len(orig) < MIN_ITALIC_WORDS:
        return inner

    lines = savitri_idx["lines"]
    inv = savitri_idx["inv"]

    # Walk the normalized stream. At each position, build the candidate set
    # of Savitri lines (via inverted index over italic[i..i+FINGERPRINT_N]),
    # then validate each candidate by full-line comparison with ≤MAX_LINE_DIFF
    # substitutions. The best (longest, fewest-diff) match wins. On a hit we
    # advance by the matched line's length so we look for the *next* verse
    # line at the expected boundary — this avoids the false-positive cascade
    # a sliding window produced.
    break_orig_idx: set = set()
    i = 1
    while i <= len(norm) - FINGERPRINT_N:
        # Union of lines that contain *any* of these 4 italic words in their
        # first FINGERPRINT_N positions. As long as at least one survived
        # the rewording, the real line is in this set.
        cands: set = set()
        for w in norm[i : i + FINGERPRINT_N]:
            cands |= inv.get(w, set())

        # CHANGED: score is (-diff, L) — fewest diffs first, then longest.
        # The opposite ordering (longest first) lets a 10-word fuzzy line win
        # over a 5-word exact line, which "absorbs" the next verse line's
        # words and drops its break. Diff=0 must always win over diff=1.
        best = None  # (-diff, L, line_idx)
        avail = len(norm) - i
        for li in cands:
            line = lines[li]
            L = len(line)
            if L > avail:
                continue
            diff = sum(1 for a, b in zip(norm[i : i + L], line) if a != b)
            if diff <= MAX_LINE_DIFF:
                score = (-diff, L)
                if best is None or score > (best[0], best[1]):
                    best = (-diff, L, li)

        if best is not None:
            L = best[1]
            b = idx_map[i]
            if b > 0:
                break_orig_idx.add(b)
            i += L
        else:
            i += 1

    if not break_orig_idx:
        return inner

    out_parts: list = []
    last = 0
    for b in sorted(break_orig_idx):
        out_parts.append(" ".join(orig[last:b]))
        last = b
    out_parts.append(" ".join(orig[last:]))
    return " <br/> ".join(out_parts)


def process_file(path: Path, savitri_fps: set, dry_run: bool) -> tuple:
    """Returns (n_blocks_touched, n_breaks_inserted)."""
    text = path.read_text(encoding="utf-8")
    n_blocks = 0
    n_breaks = 0

    def _sub(m: re.Match) -> str:
        nonlocal n_blocks, n_breaks
        inner = m.group(1)
        new_inner = insert_breaks(inner, savitri_fps)
        if new_inner != inner:
            n_blocks += 1
            n_breaks += new_inner.count("<br/>")
            return f"<i>{new_inner}</i>"
        return m.group(0)

    new_text = _italic_rx.sub(_sub, text)

    if new_text != text and not dry_run:
        # CHANGED: write a .bak once per run so the user can revert manually.
        bak = path.with_suffix(path.suffix + ".bak")
        if not bak.exists():
            bak.write_text(text, encoding="utf-8")
        path.write_text(new_text, encoding="utf-8")

    return n_blocks, n_breaks


# CHANGED (2026-05-17): default path to chapters.db so --db can be passed
# bare. Mirrors the convention used by other backend/scripts/helpers/*.py.
DEFAULT_DB = ROOT / "backend" / "db" / "chapters.db"


def sync_db(db_path: Path) -> tuple:
    """
    Push the on-disk .txt contents into the FTS5 `chapters.content` column so
    snippet() returns the verse-broken text. The FTS index already keys rows
    by (collection_folder, book_folder, section_filename); we look up each
    target file and UPDATE its content. Without this step, search-result
    snippets keep showing the pre-recovery prose (no <br/>, "Truth' s" still
    split) because chapters.db was indexed before this script first ran.

    Returns (rows_updated, rows_missing).
    """
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    updated = missing = 0
    for tdir in TARGET_DIRS:
        if not tdir.exists():
            continue
        book_folder = tdir.name
        # Collection folder is the parent of the book folder under OUT_BASE.
        coll_folder = tdir.parent.name
        for path in sorted(tdir.glob("section_*.txt")):
            new_content = path.read_text(encoding="utf-8")
            section = path.name
            row = cur.execute(
                "SELECT rowid, content FROM chapters "
                "WHERE collection_folder=? AND book_folder=? AND section_filename=?",
                (coll_folder, book_folder, section),
            ).fetchone()
            if row is None:
                missing += 1
                continue
            rowid, old_content = row
            if old_content == new_content:
                continue
            cur.execute(
                "UPDATE chapters SET content=? WHERE rowid=?",
                (new_content, rowid),
            )
            updated += 1
    conn.commit()
    conn.close()
    return updated, missing


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Report changes without writing files")
    # CHANGED (2026-05-17): --db syncs the FTS5 content column from the
    # recovered .txt files so /api/text_search snippets render verse breaks.
    ap.add_argument("--db", nargs="?", const=str(DEFAULT_DB), default=None,
                    help=f"Also update chapters.db FTS5 content from disk "
                         f"(default path: {DEFAULT_DB})")
    args = ap.parse_args()

    if not SAVITRI_DIR.exists():
        print(f"ERROR: Savitri dir not found: {SAVITRI_DIR}", file=sys.stderr)
        return 1

    savitri_idx = load_savitri_lines()
    print(f"Loaded {len(savitri_idx['lines'])} Savitri lines, "
          f"{len(savitri_idx['inv'])} distinct head-words in inverted index")

    total_files = total_blocks = total_breaks = 0
    for tdir in TARGET_DIRS:
        if not tdir.exists():
            print(f"  skip (missing): {tdir}")
            continue
        for path in sorted(tdir.glob("section_*.txt")):
            blocks, breaks = process_file(path, savitri_idx, args.dry_run)
            if blocks:
                total_files += 1
                total_blocks += blocks
                total_breaks += breaks
                print(f"  {path.name}: {blocks} italic blocks, "
                      f"{breaks} <br/> inserted")

    verb = "would touch" if args.dry_run else "touched"
    print(f"\nDone. {verb} {total_files} files, {total_blocks} italic blocks, "
          f"inserted {total_breaks} <br/> markers.")

    if args.db and not args.dry_run:
        db_path = Path(args.db)
        if not db_path.exists():
            print(f"ERROR: chapters.db not found: {db_path}", file=sys.stderr)
            return 2
        print(f"\nSyncing FTS5 content from disk -> {db_path}")
        upd, miss = sync_db(db_path)
        print(f"  updated {upd} rows, {miss} not found in DB")
    elif args.db and args.dry_run:
        print(f"(dry-run: would also sync FTS5 content -> {args.db})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
