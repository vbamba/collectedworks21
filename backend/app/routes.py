# app/routes.py
# CHANGELOG:
# - REMOVED ProxyFix import and appcontext_pushed signal that re-wrapped the app.
# - Left everything else intact. We already normalize scheme/host safely in __init__.py.

import sqlite3
import logging
from flask import Blueprint, request, abort, jsonify, render_template, send_from_directory, url_for, redirect
import json
from pathlib import Path, PurePosixPath
import os
from dotenv import load_dotenv
from markupsafe import escape
import re
import textwrap
from typing import List, Dict
import unicodedata  # NFKC normalization for reflow & highlight
from werkzeug.exceptions import NotFound

from scripts.search import search
from scripts.utils import apply_filters
import nltk

# text search helpers
from scripts.text_search import search_phrase, search_all_words, search_any_words, STOPWORDS

# NLTK data path (unchanged)
nltk.data.path.append('/Users/vbamba/nltk_data')

# ───────────────────────────────
#  App configuration
# ───────────────────────────────
main = Blueprint('main', __name__)

# env + paths
load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent
app_logger = logging.getLogger('main')
app_logger.info(f"Base Dir='{BASE_DIR}'")

faiss_index_path   = BASE_DIR / os.getenv('FAISS_INDEX_PATH')
metadata_path      = BASE_DIR / os.getenv('METADATA_PATH')
book_mapping_path  = BASE_DIR / os.getenv('BOOK_MAPPING_PATH')
OUT_BASE           = BASE_DIR / os.getenv('OUT_CHAPTERS_DIR', 'data/out_chapters')
BACKEND_CHAPTER_URL = os.getenv('BACKEND_CHAPTER_URL', '')
DB_PATH = BASE_DIR / os.getenv('CHAPTERS_DB', 'db/chapters.db')
BUILD_VERSION = os.getenv('BUILD_VERSION', 'dev')  # cache-busting for template assets
PDF_DIRECTORY = BASE_DIR / os.getenv('PDF_DIRECTORY', 'pdf')

def _get_int_env(name: str, default: int, minimum: int) -> int:
    raw_value = os.getenv(name)
    try:
        value = int(raw_value) if raw_value is not None else default
    except ValueError:
        app_logger.warning("Invalid integer for %s=%r; using %s", name, raw_value, default)
        value = default
    return max(minimum, value)

MAX_QUERY_LENGTH = _get_int_env('API_MAX_QUERY_LENGTH', 500, 1)
SEARCH_MAX_TOP_K = _get_int_env('SEARCH_MAX_TOP_K', 100, 1)
TEXT_SEARCH_MAX_LIMIT = _get_int_env('TEXT_SEARCH_MAX_LIMIT', 200, 1)
DEFAULT_SEARCH_TOP_K = min(100, SEARCH_MAX_TOP_K)
DEFAULT_TEXT_SEARCH_LIMIT = min(10, TEXT_SEARCH_MAX_LIMIT)
ALLOWED_SEARCH_TYPES = {'all', 'exact', 'all_words', 'semantic'}
ALLOWED_TEXT_SEARCH_MODES = {'all', 'exact', 'all_words'}

# ──────────────────────────────────────────────────────────────────────
# Reflow configuration (env-driven)
# ──────────────────────────────────────────────────────────────────────
REFLOW_MODE = os.getenv('REFLOW_MODE', 'auto').lower()
_allow_raw  = os.getenv('REFLOW_ALLOW_RE', '')
# CHANGED (2026-04-20): was r'(?i)\bSavitri\b'. Word boundaries do not exist
# between a digit and a letter, so the old default silently failed to match
# book folder '33-34Savitri' — reflow then joined verse lines into prose
# paragraphs. Plain (?i)Savitri catches all Savitri folders.
_deny_raw   = os.getenv('REFLOW_DENY_RE', r'(?i)Savitri')

def _compile_list(patterns_raw: str):
    pats = []
    for part in (patterns_raw or '').split(','):
        part = part.strip()
        if not part:
            continue
        try:
            if not part.startswith('(?i)'):
                part = '(?i)' + part
            pats.append(re.compile(part))
        except re.error as e:
            app_logger.warning("Invalid regex in REFLOW_*_RE: %r (%s)", part, e)
    return pats

REFLOW_ALLOW_PATTERNS = _compile_list(_allow_raw)
REFLOW_DENY_PATTERNS  = _compile_list(_deny_raw)

app_logger.info("Reflow mode=%s allow=%s deny=%s", REFLOW_MODE, _allow_raw or '-', _deny_raw or '-')
app_logger.info(f"Faiss Index Path='{faiss_index_path}'")

for pth, name in [(faiss_index_path, "FAISS index"),
                  (metadata_path, "metadata"),
                  (book_mapping_path, "book mapping")]:
    if not pth.exists():
        app_logger.error(f"{name} file not found at '{pth}'")
        raise FileNotFoundError(f"{name} file not found at '{pth}'")

def _validate_query_arg(arg_name: str = 'query'):
    query = request.args.get(arg_name, '').strip()
    if not query:
        return None, 'query parameter is required'
    if len(query) > MAX_QUERY_LENGTH:
        return None, f'query must be at most {MAX_QUERY_LENGTH} characters'
    return query, None

def _parse_bounded_int_arg(arg_name: str, default: int, minimum: int, maximum: int):
    raw_value = request.args.get(arg_name)
    if raw_value in (None, ''):
        return default, None
    try:
        value = int(raw_value)
    except ValueError:
        return None, f'{arg_name} must be an integer between {minimum} and {maximum}'
    if value < minimum or value > maximum:
        return None, f'{arg_name} must be between {minimum} and {maximum}'
    return value, None

def _normalize_pdf_request_path(filename: str):
    candidate = PurePosixPath(filename)
    if not filename or candidate.is_absolute() or candidate.suffix.lower() != '.pdf':
        return None
    parts = candidate.parts
    if not parts or any(part in {'', '.', '..'} for part in parts):
        return None
    return candidate.as_posix()

@main.route('/api/pdfs/<path:filename>', methods=['GET'])
def serve_pdf(filename):
    safe_filename = _normalize_pdf_request_path(filename)
    if safe_filename is None:
        app_logger.warning("Rejected PDF request for invalid path %r", filename)
        return jsonify({'error': 'File not found.'}), 404

    app_logger.info("Serving PDF %r from %s", safe_filename, PDF_DIRECTORY)
    try:
        return send_from_directory(PDF_DIRECTORY, safe_filename, as_attachment=False)
    except (FileNotFoundError, NotFound):
        app_logger.error("PDF not found: %r", safe_filename)
        return jsonify({'error': 'File not found.'}), 404

@main.route('/api/filters', methods=['GET'])
def get_filters():
    app_logger.info("Fetching filters")
    try:
        with open(book_mapping_path, 'r', encoding='utf-8') as f:
            book_mapping = json.load(f)
    except Exception as e:
        app_logger.error(f"Error loading book mapping: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

    group_order = ["CWSA", "CWM", "Disciples"]
    groups = sorted(
        {info['group'] for info in book_mapping.values()},
        key=lambda g: group_order.index(g) if g in group_order else len(group_order)
    )
    book_titles_by_group = {
        grp: sorted([info['book_title']
                     for info in book_mapping.values()
                     if info['group'] == grp])
        for grp in groups
    }
    all_books_sorted = [t for grp in groups for t in book_titles_by_group[grp]]

    app_logger.info("Filters fetched successfully")
    return jsonify({
        "authors": sorted({info['author'] for info in book_mapping.values()}),
        "groups": groups,
        "book_titles": all_books_sorted,
        "book_titles_by_group": book_titles_by_group
    })

@main.route('/api/search', methods=['GET'])
def search_api():
    query, error = _validate_query_arg()
    if error:
        return jsonify({"error": error}), 400

    top_k, error = _parse_bounded_int_arg('top_k', DEFAULT_SEARCH_TOP_K, 1, SEARCH_MAX_TOP_K)
    if error:
        return jsonify({"error": error}), 400

    search_type = request.args.get('search_type', 'all').lower()
    if search_type not in ALLOWED_SEARCH_TYPES:
        allowed = ', '.join(sorted(ALLOWED_SEARCH_TYPES))
        return jsonify({"error": f"search_type must be one of: {allowed}"}), 400

    filters = {
        'author': request.args.get('author', ''),
        'group': request.args.get('group', ''),
        'book_title': request.args.get('book_title', '')
    }
    filters = {k: v for k, v in filters.items() if v}

    app_logger.info(
        "Received search request: query=%r filters=%s top_k=%s search_type=%s",
        query,
        filters,
        top_k,
        search_type,
    )

    try:
        results = search(
            query=query,
            index_path=str(faiss_index_path),
            metadata_path=str(metadata_path),
            top_k=top_k,
            filters=filters,
            search_type=search_type
        )
    except Exception as e:
        app_logger.error(f"Error during semantic search: {e}", exc_info=True)
        return jsonify({"error": "Internal Server Error"}), 500

    group_counts = {}
    for r in results:
        grp = r.get('group', 'Unknown')
        group_counts[grp] = group_counts.get(grp, 0) + 1

    return jsonify({"results": results, "group_counts": group_counts}), 200

@main.route('/api/text_search', methods=['GET'])
def text_search_api():
    q, error = _validate_query_arg()
    if error:
        return jsonify({'error': error}), 400

    mode = request.args.get('mode', 'all').lower()
    if mode not in ALLOWED_TEXT_SEARCH_MODES:
        allowed = ', '.join(sorted(ALLOWED_TEXT_SEARCH_MODES))
        return jsonify({'error': f'mode must be one of: {allowed}'}), 400

    limit, error = _parse_bounded_int_arg('limit', DEFAULT_TEXT_SEARCH_LIMIT, 1, TEXT_SEARCH_MAX_LIMIT)
    if error:
        return jsonify({'error': error}), 400

    filters = {
        'author': request.args.get('author', ''),
        'group': request.args.get('group', ''),
        'book_title': request.args.get('book_title', ''),
    }
    filters = {k: v for k, v in filters.items() if v}

    try:
        exact = search_phrase(q, limit, filters)
        if mode == 'exact' or len(exact) >= limit:
            buckets = [exact]
        else:
            raw_words = q.split()
            words_wo_sw = [w for w in raw_words if w.lower() not in STOPWORDS] or raw_words
            allw = search_all_words(words_wo_sw, limit, filters)
            merged_tmp = exact + allw
            if len(merged_tmp) >= limit or mode == 'all_words':
                buckets = [exact, allw]
            else:
                anyw = search_any_words(words_wo_sw, limit, filters)
                buckets = [exact, allw, anyw]

        seen = set()
        merged: List[Dict] = []
        for bucket in buckets:
            for r in bucket:
                key = f"{r.get('file_path', r.get('pdf_file'))}|{r['section_filename']}"
                if key not in seen:
                    merged.append(r)
                    seen.add(key)
                    if len(merged) >= limit:
                        break
            if len(merged) >= limit:
                break

        enriched = []
        for r in merged:
            pdf_fname = r.get('file_path', r.get('pdf_file'))
            if r.get('group') == 'Disciples' and r.get('author', '') != 'Various':
                combined_path = f"{r['collection_folder']}/{r['author']}/{pdf_fname}"
            else:
                combined_path = f"{r['collection_folder']}/{pdf_fname}"
            r['pdf_url'] = url_for('main.serve_pdf', filename=combined_path)

            r['chapter_url'] = BACKEND_CHAPTER_URL + url_for(
                'main.chapter_content_page',
                collection_folder=r['collection_folder'],
                book_folder=r['book_folder'],
                section_filename=r['section_filename'],
                query=q,
                result_type=r.get('result_type', 'all'),
            )
            # NEW (b.4): slug-based URL when both slugs are populated. Legacy
            # rows or books with empty slugs keep chapter_url only; the frontend
            # falls back cleanly.
            if r.get('slug') and r.get('book_slug'):
                r['chapter_slug_url'] = BACKEND_CHAPTER_URL + url_for(
                    'main.chapter_by_slug_page',
                    collection=r['collection_folder'],
                    book_slug=r['book_slug'],
                    slug=r['slug'],
                    query=q,
                    result_type=r.get('result_type', 'all'),
                )
            enriched.append(r)

        group_counts = {}
        for r in enriched:
            grp = r.get('group', 'Unknown') or 'Unknown'
            group_counts[grp] = group_counts.get(grp, 0) + 1

        return jsonify({
            'query': q,
            'mode': mode,
            'results': enriched,
            'group_counts': group_counts,
        }), 200

    except Exception as exc:
        app_logger.exception("Error during text search: %s", exc)
        return jsonify({'error': 'Internal Server Error'}), 500


# ──────────────────────────────────────────────────────────────────────
# Generic prose reflow utilities (+ poetry detection)
# ──────────────────────────────────────────────────────────────────────

_end_punct_rx = re.compile(r'[.!?…"”)\]]\s*$')
_soft_hyphen_split_rx = re.compile(r'([A-Za-z])-\s*$')

def _matches_any(patterns: List[re.Pattern], text: str) -> bool:
    t = text or ""
    for pat in patterns:
        if pat.search(t):
            return True
    return False

def _looks_like_poetry(lines: List[str]) -> bool:
    """
    Heuristic poetry detector to avoid reflowing verse:
      - many short lines (<= 55 chars)
      - frequent stanza breaks (blank lines)
    """
    sample = [ln.rstrip() for ln in lines[:200]]
    if not sample:
        return False
    nonblank = [ln for ln in sample if ln.strip()]
    if not nonblank:
        return False

    short = [ln for ln in nonblank if len(ln) <= 55]
    short_ratio = len(short) / max(1, len(nonblank))
    blanks = sum(1 for ln in sample if not ln.strip())
    stanza_density = blanks / max(1, len(sample))
    return (short_ratio >= 0.60) and (stanza_density >= 0.10)

def _should_reflow(collection_folder: str, book_folder: str, raw_text: str) -> bool:
    """
    Decide if we should apply prose reflow based on:
      - REFLOW_MODE
      - allow/deny regexes (match against collection or book folder)
      - automatic poetry detection (never reflow poems)
    """
    coll = collection_folder or ""
    book = book_folder or ""
    combined = f"{coll} / {book}"

    if _matches_any(REFLOW_DENY_PATTERNS, combined):
        app_logger.debug("Reflow: DENY matched for %s", combined)
        return False

    if _looks_like_poetry(raw_text.splitlines()):
        app_logger.debug("Reflow: looks like poetry, skip for %s", combined)
        return False

    mode = REFLOW_MODE
    if mode == 'allowlist':
        allow = _matches_any(REFLOW_ALLOW_PATTERNS, combined)
        app_logger.debug("Reflow mode=allowlist allow=%s for %s", allow, combined)
        return allow
    elif mode == 'all':
        app_logger.debug("Reflow mode=all (poetry already filtered), allow for %s", combined)
        return True
    else:
        if REFLOW_ALLOW_PATTERNS:
            allow = _matches_any(REFLOW_ALLOW_PATTERNS, combined)
            app_logger.debug("Reflow mode=auto (allowlist present) allow=%s for %s", allow, combined)
            return allow
        lines = [ln.rstrip() for ln in raw_text.splitlines()[:300] if ln.strip()]
        if not lines:
            return False
        avg_len = sum(len(ln) for ln in lines) / len(lines)
        no_punct = sum(1 for ln in lines if not _end_punct_rx.search(ln))
        no_punct_ratio = no_punct / len(lines)
        allow = (avg_len <= 100) and (no_punct_ratio >= 0.45)
        app_logger.debug("Reflow mode=auto avg_len=%.1f no_punct_ratio=%.2f allow=%s for %s",
                         avg_len, no_punct_ratio, allow, combined)
        return allow

def _reflow_lines_for_prose(lines: List[str], width: int) -> List[str]:
    """
    Merge hard-wrapped lines from OCR/PDF into flowing paragraphs.
    - preserve blank-line paragraph breaks
    - join lines that end mid-sentence
    - remove hyphenation at line wraps: 'word-' + 'next' -> 'wordnext'
    - NFKC normalize every line (preserves italics tags like <i>..</i>)
    Returns a list of wrapped lines for the template JSON structure.
    """
    norm_lines = [unicodedata.normalize('NFKC', ln.rstrip()) for ln in lines]

    paragraphs: List[str] = []
    buf = ""

    for ln in norm_lines + [""]:
        if not ln.strip():
            if buf.strip():
                paragraphs.append(buf.strip())
                buf = ""
            continue

        if not buf:
            buf = ln.strip()
            continue

        m = _soft_hyphen_split_rx.search(buf)
        if m:
            buf = _soft_hyphen_split_rx.sub(r'\1', buf) + ln.lstrip()
        else:
            if _end_punct_rx.search(buf):
                paragraphs.append(buf.strip())
                buf = ln.strip()
            else:
                buf = (buf.rstrip() + " " + ln.lstrip()).replace("  ", " ")

    out_lines: List[str] = []
    for p in paragraphs:
        words = p.split(" ")
        cur = []
        cur_len = 0
        for w in words:
            wlen = len(w)
            if cur_len == 0:
                cur = [w]; cur_len = wlen
            elif cur_len + 1 + wlen <= width:
                cur.append(w); cur_len += 1 + wlen
            else:
                out_lines.append(" ".join(cur))
                cur = [w]; cur_len = wlen
        if cur:
            out_lines.append(" ".join(cur))
        out_lines.append("")

    if out_lines and out_lines[-1] == "":
        out_lines.pop()

    return out_lines

# ──────────────────────────────────────────────────────────────────────
# Server-rendered chapter (HTML) with reflow + FORCE flag
# ──────────────────────────────────────────────────────────────────────

# NEW (b.4): shared chapter.html render helper
# ─────────────────────────────────────────────────────────────────────────────
# Both the legacy `/api/chapter_content?...` route and the new slug-based
# `/read/<collection>/<book_slug>/<slug>` route render the same chapter.html
# template. Any change to block-building, reflow, or nav-computation goes here
# once — not in two places.
def _render_chapter_template(collection: str, book: str, section: str):
    base = OUT_BASE / collection
    candidate = next((p for p in base.rglob(section) if p.parent.name == book), None)
    if not candidate or not candidate.exists():
        abort(404, "Section not found")

    raw = candidate.read_text(encoding='utf-8')

    # force_reflow override (unchanged behavior)
    force_flag = request.args.get('force_reflow', '').strip()
    if force_flag == '1':
        do_reflow = True
        app_logger.debug("Reflow OVERRIDE: force_reflow=1 → ON for %s / %s / %s",
                         collection, book, section)
    elif force_flag == '0':
        do_reflow = False
        app_logger.debug("Reflow OVERRIDE: force_reflow=0 → OFF for %s / %s / %s",
                         collection, book, section)
    else:
        do_reflow = _should_reflow(collection, book, raw)
        app_logger.debug("Reflow DECISION: do_reflow=%s for %s / %s / %s (mode=%s)",
                         do_reflow, collection, book, section, REFLOW_MODE)

    # Build blocks
    blocks = []
    raw_blocks = re.split(r'\n\s*\n+', raw)

    for blk in raw_blocks:
        if not blk.strip():
            continue

        lines = blk.splitlines()

        if do_reflow:
            reflowed = _reflow_lines_for_prose(lines, width=90)
            if not reflowed:
                continue
            if all(line.strip() == '*' for line in reflowed if line.strip()):
                blocks.append({'type': 'hr'})
            else:
                para: List[str] = []
                for line in reflowed + [""]:
                    if not line.strip():
                        if para:
                            blocks.append({'type': 'lines', 'lines': para})
                            para = []
                    else:
                        para.append(line)
        else:
            if all(line.strip() == '*' for line in lines):
                blocks.append({'type': 'hr'})
            else:
                wrapped = []
                for line in lines:
                    nline = unicodedata.normalize('NFKC', line)  # normalize for highlight robustness
                    wrapped.extend(textwrap.wrap(nline, width=120) or [''])
                blocks.append({'type': 'lines', 'lines': wrapped})

    # Heading from first non-hr block
    chap_heading = ""
    for b in blocks:
        if b['type'] == 'lines' and b['lines']:
            chap_heading = " ".join(b['lines'][:2])
            break

    # DB lookups for nav + title
    # CHANGED (b.4 nav fix): also select slug + book_slug so the template can
    # build canonical /read/<coll>/<book_slug>/<slug> prev/next links. The old
    # template emitted relative `?collection_folder=...` URLs which broke on
    # the /read/<...> path (querystring replacement on a path-param URL).
    # CHANGED (b.5): also select parent_toc_title so the chapter header can
    # render a "from <parent>" breadcrumb on Pass-3 journal sub-sections.
    conn = sqlite3.connect(str(DB_PATH))
    # CHANGED: also pull non_content so prev/next nav can skip TOC / Publisher's
    # Note sections (non_content=1). Without this, [Previous Chapter] from the
    # first real chapter would land on the front-matter TOC, which has no
    # clickable entries — a dead end for the reader.
    cursor = conn.execute(
        """
        SELECT section_filename, slug, book_slug, book_title, parent_toc_title, non_content
        FROM chapters
        WHERE collection_folder = ? AND book_folder = ?
        ORDER BY CAST(chapter AS INTEGER)
        """,
        (collection, book)
    )
    rows = cursor.fetchall()
    conn.close()

    sections      = [r[0] for r in rows]
    section_slugs = [r[1] or '' for r in rows]
    book_slug     = next((r[2] for r in rows if r[2]), '')  # first non-empty
    fallback_title = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', re.sub(r'^\d+', '', book)).title()
    book_title = rows[0][3] if rows and rows[0][3] else fallback_title

    # CHANGED: helper to walk past non_content sections when computing prev/next.
    # We keep the full `sections` list (so direct URLs to a TOC page still
    # render — bookmarks shouldn't break) but only return a content-only target
    # for navigation. Step direction = -1 for prev, +1 for next.
    def _step_to_content(start_idx: int, step: int):
        i = start_idx + step
        while 0 <= i < len(rows) and rows[i][5]:  # rows[i][5] = non_content
            i += step
        return i if 0 <= i < len(rows) else None

    try:
        idx = sections.index(section)
    except ValueError:
        prev_section = next_section = None
        prev_slug    = next_slug    = ''
        # NEW (b.5): unknown section → no breadcrumb
        parent_toc_title = ''
    else:
        prev_idx = _step_to_content(idx, -1)  # CHANGED: skip non_content
        next_idx = _step_to_content(idx, +1)  # CHANGED: skip non_content
        prev_section = sections[prev_idx] if prev_idx is not None else None
        next_section = sections[next_idx] if next_idx is not None else None
        prev_slug    = section_slugs[prev_idx] if prev_idx is not None else ''
        next_slug    = section_slugs[next_idx] if next_idx is not None else ''
        # NEW (b.5): breadcrumb for the *current* section; empty for TOC-level
        # entries and legacy rows predating Pass 3.
        parent_toc_title = rows[idx][4] or ''

    query       = request.args.get('query', '').strip()
    result_type = request.args.get('result_type', '').strip()

    return render_template(
        'chapter.html',
        title=book_title,
        chap_heading=chap_heading,
        blocks=blocks,
        collection_folder=collection,
        book_folder=book,
        prev_section=prev_section,
        next_section=next_section,
        # NEW (b.4 nav fix): slug-aware nav. Template prefers these when set.
        book_slug=book_slug,
        prev_slug=prev_slug,
        next_slug=next_slug,
        # NEW (b.5): non-empty only for Pass-3 journal sub-sections
        parent_toc_title=parent_toc_title,
        query=query,
        result_type=result_type,
        build_version=BUILD_VERSION,  # ensure static links get cache-busted
    )


@main.route('/api/chapter_content', methods=['GET'])
def chapter_content_page():
    """
    Legacy server-rendered chapter page (HTML). Kept for backward compatibility
    with existing search-result links and bookmarks. Delegates to the shared
    helper so behavior is identical to /read/<...>.
    """
    collection = request.args.get('collection_folder','').strip()
    book       = request.args.get('book_folder','').strip()
    section    = request.args.get('section_filename','').strip()

    if not (collection and book and section):
        abort(400, "collection_folder, book_folder and section_filename are required")

    return _render_chapter_template(collection, book, section)


# NEW (b.4): slug-based chapter URL. Renders chapter.html directly at the slug
# path (no redirect) so the browser URL bar stays on /read/<coll>/<book>/<slug>,
# which is the whole point of slugs — stable, shareable URLs.
@main.route('/read/<collection>/<book_slug>/<slug>', methods=['GET'])
def chapter_by_slug_page(collection, book_slug, slug):
    collection = (collection or '').strip()
    book_slug  = (book_slug or '').strip()
    slug       = (slug or '').strip()
    if not (collection and book_slug and slug):
        abort(400, "collection, book_slug and slug are required")

    conn = sqlite3.connect(str(DB_PATH))
    try:
        row = conn.execute(
            """
            SELECT book_folder, section_filename
              FROM chapters
             WHERE collection_folder = ?
               AND book_slug = ?
               AND slug = ?
             LIMIT 1
            """,
            (collection, book_slug, slug),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        abort(404, "Chapter not found for that slug")

    book_folder, section_filename = row
    return _render_chapter_template(collection, book_folder, section_filename)

# ──────────────────────────────────────────────────────────────────────
# SPA JSON chapter with reflow + FORCE flag
# ──────────────────────────────────────────────────────────────────────

@main.route('/api/chapter', methods=['GET'])
def get_chapter():
    """
    JSON chapter for SPA. Uses the same prose reflow policy (config + poetry detection).
    NEW: `force_reflow` query flag to override decision (1=ON, 0=OFF).
    """
    collection = request.args.get('collection_folder','').strip()
    book       = request.args.get('book_folder','').strip()
    section    = request.args.get('section_filename','').strip()
    if not (collection and book and section):
        return jsonify({"error":"collection_folder, book_folder and section_filename required"}),400

    base = OUT_BASE / collection
    candidate = next((p for p in base.rglob(section) if p.parent.name == book), None)
    if not candidate or not candidate.exists():
        return jsonify({"error":"section not found"}),404

    raw = candidate.read_text(encoding='utf-8')

    # [NEW] query override
    force_flag = request.args.get('force_reflow', '').strip()
    if force_flag == '1':
        do_reflow = True
        app_logger.debug("Reflow OVERRIDE: force_reflow=1 → ON (SPA) for %s / %s / %s",
                         collection, book, section)
    elif force_flag == '0':
        do_reflow = False
        app_logger.debug("Reflow OVERRIDE: force_reflow=0 → OFF (SPA) for %s / %s / %s",
                         collection, book, section)
    else:
        do_reflow = _should_reflow(collection, book, raw)
        app_logger.debug("Reflow DECISION (SPA): do_reflow=%s for %s / %s / %s (mode=%s)",
                         do_reflow, collection, book, section, REFLOW_MODE)

    blocks = []
    raw_blocks = re.split(r'\n\s*\n+', raw)

    for blk in raw_blocks:
        if not blk.strip():
            continue

        lines = blk.splitlines()
        if do_reflow:
            reflowed = _reflow_lines_for_prose(lines, width=90)
            if not reflowed:
                continue
            if all(line.strip() == '*' for line in reflowed if line.strip()):
                blocks.append({'type':'hr'})
            else:
                para: List[str] = []
                for line in reflowed + [""]:
                    if not line.strip():
                        if para:
                            blocks.append({'type':'lines','lines':para})
                            para=[]
                    else:
                        para.append(line)
        else:
            if all(line.strip() == '*' for line in lines):
                blocks.append({'type':'hr'})
            else:
                wrapped = []
                for line in lines:
                    nline = unicodedata.normalize('NFKC', line)
                    wrapped.extend(textwrap.wrap(nline, width=100) or [''])
                blocks.append({'type':'lines','lines':wrapped})

    # nav + title
    # CHANGED (b.5): pull parent_toc_title alongside section_filename so we can
    # surface the journal-sub-section breadcrumb in the SPA chapter header.
    # CHANGED: also pull non_content so prev/next/first/last skip TOC and
    # Publisher's Note sections (non_content=1). They have no clickable entries
    # so landing on them via nav is a dead-end for the reader.
    conn = sqlite3.connect(str(DB_PATH))
    # CHANGED: also pull slug + book_slug so /api/chapter can return slug-based
    # nav targets. With the SPA migration, chapter URLs are /read/<coll>/<book>/<slug>
    # and the prev/next links must build new /read/... URLs — which requires
    # knowing each neighbor's slug, not just its section_filename.
    cur = conn.execute(
        "SELECT section_filename, parent_toc_title, non_content, slug, book_slug FROM chapters "
        "WHERE collection_folder=? AND book_folder=? "
        "ORDER BY CAST(chapter AS INTEGER)",
        (collection, book)
    )
    section_rows = cur.fetchall()
    sections = [r[0] for r in section_rows]
    section_parents = [r[1] or '' for r in section_rows]
    section_non_content = [bool(r[2]) for r in section_rows]  # CHANGED: TOC flag per section
    section_slugs = [r[3] or '' for r in section_rows]        # CHANGED: per-section slug for /read URL building
    book_slug = next((r[4] for r in section_rows if r[4]), '')  # CHANGED: same for every row, take first non-empty
    cur = conn.execute(
        "SELECT book_title FROM chapters "
        "WHERE collection_folder=? AND book_folder=? LIMIT 1",
        (collection, book)
    )
    row = cur.fetchone()
    conn.close()

    fallback_title = re.sub(
        r'(?<=[a-z])(?=[A-Z])', ' ',
        re.sub(r'^\d+', '', book)
    ).title()
    book_title = row[0] if row and row[0] else fallback_title

    # CHANGED: indices of content-only sections, used for nav so Prev/Next/
    # First/Last never point to a TOC or Publisher's Note. The full `sections`
    # list is preserved for `sections.index(section)` so direct URLs to a TOC
    # page (bookmarks) still render — we only hide them from navigation.
    content_idxs = [i for i, nc in enumerate(section_non_content) if not nc]

    # CHANGED (2026-04-19): also compute first/last section_filename so the SPA
    # can render jump-to-start and jump-to-end links alongside prev/next. These
    # are None when the book has 0 sections, or equal to prev/next when the
    # current chapter is already at the boundary (client decides whether to
    # hide or just visually disable).
    # CHANGED: first/last now point at the first/last content sections, not the
    # raw section list — otherwise [« First] in book 28 lands on the Publisher's
    # Note (section_01), the very dead-end we're trying to hide.
    first_section = sections[content_idxs[0]] if content_idxs else None
    last_section = sections[content_idxs[-1]] if content_idxs else None
    # CHANGED: parallel slug accessors so the SPA can build /read/<coll>/<book>/<slug>
    # nav links without a second roundtrip. Empty string when slug is missing
    # (legacy rows that predate the slug column).
    first_slug = section_slugs[content_idxs[0]] if content_idxs else ''
    last_slug = section_slugs[content_idxs[-1]] if content_idxs else ''
    try:
        idx = sections.index(section)
        # CHANGED: walk past non_content neighbors so prev/next skip TOC pages.
        prev_idx = next((i for i in reversed(content_idxs) if i < idx), None)
        next_idx = next((i for i in content_idxs if i > idx), None)
        prev_section = sections[prev_idx] if prev_idx is not None else None
        next_section = sections[next_idx] if next_idx is not None else None
        # CHANGED: matching slugs for prev/next (empty when neighbor is None).
        prev_slug = section_slugs[prev_idx] if prev_idx is not None else ''
        next_slug = section_slugs[next_idx] if next_idx is not None else ''
        # NEW (b.5): current section's breadcrumb (empty for TOC-level entries)
        parent_toc_title = section_parents[idx]
    except ValueError:
        prev_section = next_section = None
        prev_slug = next_slug = ''
        parent_toc_title = ''

    return jsonify({
        'blocks'      : blocks,
        'book_title'  : book_title,
        'prev_section': prev_section,
        'next_section': next_section,
        # CHANGED (2026-04-19): boundary links so readers can jump to the start
        # or end of the book without clicking prev/next N times.
        'first_section': first_section,
        'last_section': last_section,
        # CHANGED: slug-form versions of nav targets. Empty string for boundaries
        # or for legacy rows without slugs; the SPA falls back to /chapter?... in
        # that case so old data still works.
        'prev_slug': prev_slug,
        'next_slug': next_slug,
        'first_slug': first_slug,
        'last_slug': last_slug,
        'book_slug': book_slug,
        # NEW (b.5): Pass-3 sub-section breadcrumb; ChapterPage.jsx renders
        # "from <parent_toc_title>" under the book title when non-empty.
        'parent_toc_title': parent_toc_title,
        # CHANGED (2026-04-20): expose reflow decision so the SPA can preserve
        # verse line breaks (Savitri etc.) instead of joining lines with spaces.
        # When reflowed=False the frontend must keep per-line breaks (<br/>);
        # when True it can join with spaces so the browser word-wraps prose.
        'reflowed': do_reflow,
    }), 200

# ──────────────────────────────────────────────────────────────────────
# NEW (b.3): slug-based chapter lookup
# ──────────────────────────────────────────────────────────────────────
# Resolves (collection_folder, book_slug, slug) → (book_folder, section_filename)
# via chapters.db, then 307-redirects to the canonical /api/chapter endpoint so
# all reflow / nav / title logic stays in one place. Returns 404 if the slug
# pair doesn't match any indexed section. The slug columns are populated by
# build_chapter_index.py from metadata.json; rebuild chapters.db after running
# backfill_slugs.py (or a fresh split_pdf.py) for this lookup to resolve.
@main.route('/api/chapter_by_slug', methods=['GET'])
def chapter_by_slug():
    collection = request.args.get('collection_folder', '').strip()
    book_slug  = request.args.get('book_slug', '').strip()
    slug       = request.args.get('slug', '').strip()
    if not (collection and book_slug and slug):
        return jsonify({'error': 'collection_folder, book_slug and slug are required'}), 400

    conn = sqlite3.connect(str(DB_PATH))
    try:
        row = conn.execute(
            """
            SELECT book_folder, section_filename
              FROM chapters
             WHERE collection_folder = ?
               AND book_slug = ?
               AND slug = ?
             LIMIT 1
            """,
            (collection, book_slug, slug),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return jsonify({'error': 'slug not found'}), 404

    book_folder, section_filename = row
    # Forward extra args (force_reflow, etc.) so the redirect is transparent.
    forwarded = {
        'collection_folder': collection,
        'book_folder':       book_folder,
        'section_filename':  section_filename,
    }
    for passthrough in ('force_reflow',):
        val = request.args.get(passthrough)
        if val is not None:
            forwarded[passthrough] = val

    target = url_for('main.get_chapter', **forwarded)
    return redirect(target, code=307)


@main.route('/api/chapter_meta', methods=['GET'])
def chapter_meta():
    collection = request.args.get('collection_folder', '').strip()
    book       = request.args.get('book_folder', '').strip()
    section    = request.args.get('section_filename', '').strip()
    if not (collection and book and section):
        abort(400, "collection_folder, book_folder and section_filename are required")

    conn = sqlite3.connect(str(DB_PATH))
    # CHANGED (b.5): include parent_toc_title so chapter_meta can surface the
    # journal-sub-section breadcrumb to any caller.
    cursor = conn.execute(
        """
        SELECT section_filename, parent_toc_title FROM chapters
         WHERE collection_folder=? AND book_folder=?
         ORDER BY CAST(chapter AS INTEGER)
        """,
        (collection, book)
    )
    meta_rows = cursor.fetchall()
    sections = [r[0] for r in meta_rows]
    section_parents = [r[1] or '' for r in meta_rows]

    cursor = conn.execute(
        """
        SELECT book_title FROM chapters
         WHERE collection_folder=? AND book_folder=?
         LIMIT 1
        """,
        (collection, book)
    )
    row = cursor.fetchone()
    fallback = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ',
               re.sub(r'^\d+', '', book)).title()
    book_title = row[0] if row and row[0] else fallback
    conn.close()

    try:
        idx = sections.index(section)
    except ValueError:
        prev_section = next_section = None
        parent_toc_title = ''
    else:
        prev_section = sections[idx-1] if idx > 0 else None
        next_section = sections[idx+1] if idx < len(sections)- 1 else None
        parent_toc_title = section_parents[idx]  # NEW (b.5)

    return jsonify({
        'prev_section': prev_section,
        'next_section': next_section,
        'book_title': book_title,
        'parent_toc_title': parent_toc_title,  # NEW (b.5)
    })
