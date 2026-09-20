#!/usr/bin/env python3
"""
restore_compound_hyphens.py — put back the hyphens the splitter ate.

Why this exists: `merge_lines()` in the splitter de-hyphenates a word that
wrapped across a line by deleting the trailing '-' and pulling the next
fragment up. That is right for a soft hyphen ('un-' + 'happy' -> 'unhappy')
but wrong when the hyphen belongs to the word:

    PDF   '...rather than non-'     ->   stored as  'nonCommunists'
          'Communists should...'         should be  'non-Communists'

Beyond looking wrong, it makes those occurrences unfindable: FTS5 indexes
'nonCommunists' as a single token, so no query reaches it. For a compound
whose only instance in the corpus is a glued one, the query returns nothing
at all (59 such compounds when this was written).

How it decides. The source PDF is the authority: a line ending in '-' whose
continuation fragment is Capitalised-then-lowercase means the hyphen is real.
An ALL-CAPS fragment means an all-caps word merely wrapped mid-word
('PONDI-' + 'CHERRY', 'THE COM-' + 'PLETE WORKS') and the hyphen must still
go. Genuine all-caps compounds exist but cannot be told apart by shape, so
the few known ones are listed in ALLCAPS_KEEP below.

A candidate is only rewritten when BOTH hold: the PDF shows the hyphen, and
the glued spelling actually appears in that book's shipped text. That pairing
is what keeps it from touching legitimate CamelCase.

Scope is per book — a replacement found in one book is never applied to
another, so a coincidental glued spelling elsewhere is left alone.

Idempotent: after a run the glued form is gone, so a re-run matches nothing.
Safe to re-run after any rebuild; it re-derives everything from the PDFs.

Usage:
    python3 backend/scripts/helpers/restore_compound_hyphens.py              # dry run, full report
    python3 backend/scripts/helpers/restore_compound_hyphens.py --write      # apply to .txt + chapters.db
    python3 backend/scripts/helpers/restore_compound_hyphens.py --book 06-07BandeMataram
    python3 backend/scripts/helpers/restore_compound_hyphens.py --write --db-only
"""

import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT_BASE = ROOT / "backend" / "data" / "out_chapters"
PDF_BASE = ROOT / "backend" / "pdf"
DB_PATH = ROOT / "backend" / "db" / "chapters.db"

# All-caps compounds where the hyphen IS real. Shape alone cannot distinguish
# these from an all-caps word that wrapped mid-word, so they are named here.
# Verified against the source PDFs 2026-09-19:
#   SELF-IMPOSED japa            (Agenda Vol3)
#   IT-IS-NO-LONGER-TRUE         (Agenda Vol7)
#   I-AM-NOT-THIS                (Agenda Vol4)
ALLCAPS_KEEP = {"SELFIMPOSED": "SELF-IMPOSED", "ITIS": "IT-IS", "NOTTHIS": "NOT-THIS"}

_LINE_END_HYPHEN = re.compile(r"([A-Za-z]{1,25})-$")
_CAP_FRAGMENT = re.compile(r"^([A-Z][A-Za-z]{0,25})")
# Capitalised-then-lowercase: the real-compound signature.
_REAL_COMPOUND = re.compile(r"^[A-Z][a-z]")


def book_pdf_map():
    """book_folder -> (pdf path, section dir), taken from each book's metadata.json."""
    out = {}
    for meta in OUT_BASE.rglob("metadata.json"):
        try:
            rows = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(rows, list) and rows and rows[0].get("pdf_file"):
            out[meta.parent.name] = (PDF_BASE / rows[0]["pdf_file"], meta.parent)
    return out


def scan_book(pdf_path, section_dir):
    """Return {glued: hyphenated} confirmed for this book."""
    import fitz  # imported lazily so --help works without PyMuPDF

    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        print(f"    ! cannot open {pdf_path.name}: {exc}", file=sys.stderr)
        return {}

    pairs = {}
    try:
        for page in doc:
            lines = page.get_text().split("\n")
            for a, b in zip(lines, lines[1:]):
                ma = _LINE_END_HYPHEN.search(a.rstrip())
                if not ma:
                    continue
                mb = _CAP_FRAGMENT.match(b.lstrip())
                if not mb:
                    continue
                stem, frag = ma.group(1), mb.group(1)
                glued = stem + frag
                if _REAL_COMPOUND.match(frag):
                    pairs[glued] = f"{stem}-{frag}"
                elif glued in ALLCAPS_KEEP:
                    pairs[glued] = ALLCAPS_KEEP[glued]
    finally:
        doc.close()

    if not pairs:
        return {}

    # Confirm against what actually shipped: only rewrite a glued spelling that
    # is really present in this book's text.
    blob = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for p in section_dir.glob("section_*.txt")
    )
    return {
        g: h for g, h in pairs.items()
        if re.search(r"\b" + re.escape(g) + r"\b", blob)
    }


def apply_to_text(s, repl):
    n = 0
    for glued, fixed in repl.items():
        s, k = re.subn(r"\b" + re.escape(glued) + r"\b", fixed, s)
        n += k
    return s, n


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="apply changes (default: dry run)")
    ap.add_argument("--book", help="limit to one book_folder")
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--db-only", action="store_true", help="skip out_chapters/*.txt")
    ap.add_argument("--txt-only", action="store_true", help="skip chapters.db")
    args = ap.parse_args()

    books = book_pdf_map()
    if args.book:
        books = {k: v for k, v in books.items() if k == args.book}
        if not books:
            sys.exit(f"no such book_folder: {args.book}")

    print(f"scanning {len(books)} books for eaten compound hyphens…\n")
    per_book = {}
    for name in sorted(books):
        pdf, secdir = books[name]
        if not pdf.exists():
            print(f"  ? {name}: pdf missing ({pdf})")
            continue
        repl = scan_book(pdf, secdir)
        if repl:
            per_book[name] = repl

    if not per_book:
        print("nothing to do — no eaten hyphens found.")
        return

    total_words = sum(len(v) for v in per_book.values())
    print(f"{total_words} distinct words across {len(per_book)} books\n")
    for name in sorted(per_book):
        items = sorted(per_book[name].items())
        print(f"  {name}  ({len(items)})")
        for g, h in items[:6]:
            print(f"      {g}  ->  {h}")
        if len(items) > 6:
            print(f"      … and {len(items) - 6} more")

    # ---- out_chapters/*.txt ----
    txt_files = txt_hits = 0
    if not args.db_only:
        print("\n.txt files:")
        for name, repl in per_book.items():
            secdir = books[name][1]
            for p in secdir.glob("section_*.txt"):
                s = p.read_text(encoding="utf-8", errors="replace")
                new, n = apply_to_text(s, repl)
                if n:
                    txt_files += 1
                    txt_hits += n
                    if args.write:
                        p.write_text(new, encoding="utf-8")
        print(f"  {txt_hits} replacements in {txt_files} files"
              f"{'' if args.write else '  (dry run)'}")

    # ---- chapters.db ----
    db_rows = db_hits = 0
    if not args.txt_only:
        print("\nchapters.db:")
        conn = sqlite3.connect(args.db)
        try:
            for name, repl in per_book.items():
                like = " OR ".join("content LIKE ?" for _ in repl)
                params = [f"%{g}%" for g in repl]
                rows = conn.execute(
                    f"SELECT rowid, content FROM chapters WHERE book_folder = ? AND ({like})",
                    [name] + params,
                ).fetchall()
                for rowid, content in rows:
                    new, n = apply_to_text(content, repl)
                    if n:
                        db_rows += 1
                        db_hits += n
                        if args.write:
                            conn.execute("UPDATE chapters SET content = ? WHERE rowid = ?",
                                         (new, rowid))
            if args.write:
                conn.commit()
        finally:
            conn.close()
        print(f"  {db_hits} replacements in {db_rows} rows"
              f"{'' if args.write else '  (dry run)'}")

    if not args.write:
        print("\nDRY RUN — nothing written. Re-run with --write to apply.")


if __name__ == "__main__":
    main()
