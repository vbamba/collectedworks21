#!/usr/bin/env python3
"""
convert_savitri_sources.py — savitri-wiki build step. Two transforms on
each .html file, both pure source→build (never modifies the source tree):

  1. Expand <code>raw/<book>/<section>.txt</code> shorthand into linked
     chapter URLs on ask.collectedworksofsriaurobindo.com. Authors use
     the raw-path form while drafting (lightweight, matches splitter
     filenames); deploy renders them as clickable links.

  2. Inject per-page SEO metadata into <head>: <meta name="description">,
     <link rel="canonical">, Open Graph tags, Twitter card, and JSON-LD
     Article schema. Description is derived from the lede paragraph after
     <h1>; canonical from the filename.

Always writes to a separate build dir (default: savitri-wiki-build/).
Run before deploying via scripts/deploy_savitri.sh — that script already
invokes it. See docs/DEPLOY.md §8.7.

Source citations look up section title + slug from the splitter's
metadata.json files (authoritative — same source the chapter URLs were
generated from).

Usage:
    python3 scripts/convert_savitri_sources.py
    python3 scripts/convert_savitri_sources.py --out /tmp/preview   # for local preview
"""

import argparse
import html as htmllib
import json
import re
import shutil
import sys
from pathlib import Path

# CHANGED (2026-06-06): hardcoded book-folder → (display name, book_slug).
# Extend here if other Sri Aurobindo books ever become wiki sources.
# Display names are the human-readable book titles used in the link text;
# book_slugs match what the splitter writes into chapters.db.book_slug.
BOOKS = {
    '33-34Savitri':       ('Savitri',            'savitri'),
    'Letters-on-Savitri': ('Letters on Savitri', 'letters-on-savitri'),
}

BASE_URL = 'https://ask.collectedworksofsriaurobindo.com/read/sriaurobindo'

# CHANGED (2026-06-06): site identity for SEO injection. Used to build
# canonical URLs and og:site_name / JSON-LD publisher fields.
SITE_BASE = 'https://savitri.thesunlitpath.in'
SITE_NAME = 'SavitriStudy'
DESC_MAX_CHARS = 160  # Google typically truncates meta descriptions ~155-160
# Fallback when a page has no lede paragraph to derive a description from.
SITE_DESC = ("A reader's companion to Sri Aurobindo's Savitri — original "
             "analysis of the epic by character, concept, and canto.")

# CHANGED (2026-06-07): SEO-extraction patterns. TITLE/H1 are DOTALL because
# the index <h1> spans lines via <br/>. LEDE_RX finds the first <p> after the
# first <h1> (the article's opening paragraph, used for the description).
TITLE_RX = re.compile(r'<title>(.*?)</title>', re.DOTALL | re.IGNORECASE)
H1_RX    = re.compile(r'<h1[^>]*>(.*?)</h1>', re.DOTALL | re.IGNORECASE)
LEDE_RX  = re.compile(r'<h1[^>]*>.*?</h1>\s*<p[^>]*>(.*?)</p>',
                      re.DOTALL | re.IGNORECASE)
TAG_RX   = re.compile(r'<[^>]+>')

# Match each <li>...</li> block so we can resolve range patterns like
#   <code>raw/Book/sec_X.txt</code> through <code>sec_Y.txt</code>
# where the second <code> omits the `raw/Book/` prefix (the author uses
# the first ref to establish a "context book" for the rest of the line).
LI_BLOCK_RX  = re.compile(r'<li>(.*?)</li>', re.DOTALL)
RAW_REF_RX   = re.compile(r'<code>raw/([^/]+)/(section_\d+_[^<]+\.txt)</code>')
BARE_REF_RX  = re.compile(r'<code>(section_\d+_[^<]+\.txt)</code>')


def build_lookup(out_chapters_root: Path) -> dict:
    """{(book_folder, section_filename): (section_title, slug)} from metadata.json."""
    lookup = {}
    for book_folder in BOOKS:
        meta_path = out_chapters_root / book_folder / 'metadata.json'
        if not meta_path.exists():
            print(f'WARN: {meta_path} not found, skipping {book_folder}',
                  file=sys.stderr)
            continue
        for entry in json.load(open(meta_path)):
            lookup[(book_folder, entry['filename'])] = (
                entry['section_title'], entry['slug'])
    return lookup


def _link_for(book_folder: str, section_filename: str,
              lookup: dict, unknowns: list) -> str | None:
    """Build the <a> element for a (book, section) pair. None if unmappable."""
    key = (book_folder, section_filename)
    if book_folder not in BOOKS or key not in lookup:
        unknowns.append(key)
        return None
    display, book_slug = BOOKS[book_folder]
    section_title, slug = lookup[key]
    url = f'{BASE_URL}/{book_slug}/{slug}'
    return (
        f'<a href="{url}" target="_blank" rel="noopener">'
        f'{display} — {section_title}</a>'
    )


def _process_li(li_content: str, lookup: dict, unknowns: list) -> tuple[str, int]:
    """Two-pass: first resolve raw/Book/ refs, then resolve any remaining bare
    <code>section_*.txt</code> refs using the first raw/'s book as context.
    Returns (new_content, num_links_made)."""
    raw_matches = list(RAW_REF_RX.finditer(li_content))
    if not raw_matches:
        return li_content, 0
    context_book = raw_matches[0].group(1)
    n = 0

    def replace_raw(m: re.Match) -> str:
        nonlocal n
        link = _link_for(m.group(1), m.group(2), lookup, unknowns)
        if link is None:
            return m.group(0)
        n += 1
        return link

    new_content = RAW_REF_RX.sub(replace_raw, li_content)

    # Bare-ref pass uses the context book inferred from the first raw/ ref —
    # only fires inside a li that already had a raw/ ref, so we never make up
    # links from thin air. Pattern only matches surviving <code>section_*</code>
    # blocks because the raw/ pass above rewrote those into <a>.
    def replace_bare(m: re.Match) -> str:
        nonlocal n
        link = _link_for(context_book, m.group(1), lookup, unknowns)
        if link is None:
            return m.group(0)
        n += 1
        return link

    return BARE_REF_RX.sub(replace_bare, new_content), n


def convert(text: str, lookup: dict, unknowns: list) -> tuple[str, int]:
    total = 0
    def replace_li(m: re.Match) -> str:
        nonlocal total
        new_content, n = _process_li(m.group(1), lookup, unknowns)
        total += n
        return f'<li>{new_content}</li>'
    new_text = LI_BLOCK_RX.sub(replace_li, text)
    return new_text, total


# CHANGED (2026-06-07): SEO injection. Pure build-time transform — derives
# per-page <meta name="description">, <link rel="canonical">, Open Graph,
# Twitter card, and JSON-LD Article schema from each page's own <title>,
# <h1>, and lede paragraph. Source files are never touched.

def _strip_tags(s: str) -> str:
    """Inner-HTML → plain text: drop tags, unescape entities, collapse space."""
    return re.sub(r'\s+', ' ', htmllib.unescape(TAG_RX.sub('', s))).strip()


def _truncate(s: str, n: int) -> str:
    """Trim to <= n chars on a word boundary, with an ellipsis."""
    if len(s) <= n:
        return s
    return s[:n].rsplit(' ', 1)[0].rstrip(' ,;:—-') + '…'


def _canonical_url(filename: str) -> str:
    # index.html is served at the site root (matches sitemap.xml's <loc>).
    if filename == 'index.html':
        return SITE_BASE + '/'
    return f'{SITE_BASE}/{filename}'


def inject_seo(text: str, filename: str) -> tuple[str, bool]:
    """Insert SEO <head> tags before </head>. Returns (new_text, injected?).
    Idempotent: skips a page that already carries a description meta."""
    if 'name="description"' in text or '</head>' not in text:
        return text, False

    title_m = TITLE_RX.search(text)
    title = _strip_tags(title_m.group(1)) if title_m else SITE_NAME
    h1_m = H1_RX.search(text)
    headline = _strip_tags(h1_m.group(1)) if h1_m else title
    lede_m = LEDE_RX.search(text)
    description = _truncate(_strip_tags(lede_m.group(1)), DESC_MAX_CHARS) \
        if lede_m else SITE_DESC

    canonical = _canonical_url(filename)
    title_attr = htmllib.escape(title, quote=True)
    desc_attr = htmllib.escape(description, quote=True)

    ld = {
        '@context': 'https://schema.org',
        '@type': 'Article',
        'headline': headline,
        'description': description,
        'inLanguage': 'en',
        'mainEntityOfPage': {'@type': 'WebPage', '@id': canonical},
        'author': {'@type': 'Organization', 'name': SITE_NAME, 'url': SITE_BASE},
        'publisher': {'@type': 'Organization', 'name': SITE_NAME, 'url': SITE_BASE},
    }
    ld_json = json.dumps(ld, ensure_ascii=False, indent=2)

    block = (
        f'<meta name="description" content="{desc_attr}">\n'
        f'<link rel="canonical" href="{canonical}">\n'
        f'<meta property="og:type" content="article">\n'
        f'<meta property="og:title" content="{title_attr}">\n'
        f'<meta property="og:description" content="{desc_attr}">\n'
        f'<meta property="og:url" content="{canonical}">\n'
        f'<meta property="og:site_name" content="{SITE_NAME}">\n'
        f'<meta property="og:locale" content="en_US">\n'
        f'<meta name="twitter:card" content="summary">\n'
        f'<meta name="twitter:title" content="{title_attr}">\n'
        f'<meta name="twitter:description" content="{desc_attr}">\n'
        f'<script type="application/ld+json">\n{ld_json}\n</script>\n'
    )
    return text.replace('</head>', block + '</head>', 1), True


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    repo_root = Path(__file__).resolve().parents[1]
    parser.add_argument('--src',
        default=str(repo_root / 'savitri-wiki'),
        help='Wiki source dir (default: savitri-wiki/)')
    parser.add_argument('--out',
        default=str(repo_root / 'savitri-wiki-build'),
        help='Build output dir (default: savitri-wiki-build/, gitignored)')
    parser.add_argument('--out-chapters',
        default=str(repo_root / 'backend' / 'data' / 'out_chapters' / 'sriaurobindo'),
        help='Splitter metadata.json root (default: backend/data/out_chapters/sriaurobindo)')
    args = parser.parse_args()

    src = Path(args.src)
    out = Path(args.out)
    if not src.is_dir():
        print(f'ERROR: source dir not found: {src}', file=sys.stderr)
        return 1

    # Mirror everything to the build dir, then rewrite the .html files in place.
    # Using rmtree+copytree (vs rsync) keeps the script dependency-free.
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(src, out)

    lookup = build_lookup(Path(args.out_chapters))
    if not lookup:
        print('ERROR: no sections loaded from metadata.json — wrong --out-chapters?',
              file=sys.stderr)
        return 1

    unknowns: list = []
    files_changed = 0
    total_subs = 0
    seo_count = 0  # CHANGED (2026-06-07): count pages that got SEO metadata
    html_files = list(out.rglob('*.html'))
    for path in sorted(html_files):
        text = path.read_text(encoding='utf-8')
        new_text, n = convert(text, lookup, unknowns)
        # CHANGED (2026-06-07): inject SEO head tags in the same build pass.
        new_text, seo_added = inject_seo(new_text, path.name)
        if n or seo_added:
            path.write_text(new_text, encoding='utf-8')
            files_changed += 1
            total_subs += n
            if seo_added:
                seo_count += 1

    print(f'scanned {len(html_files)} html files in {src}')
    print(f'built  {out}')
    print(f'rewrote {files_changed} files with {total_subs} source-link substitutions')
    print(f'injected SEO metadata into {seo_count} pages')
    if unknowns:
        unique = sorted(set(unknowns))
        print(f'\nWARN: {len(unique)} unknown section refs (left as <code>):',
              file=sys.stderr)
        for u in unique[:10]:
            print(f'  {u[0]} / {u[1]}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
