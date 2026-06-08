# app/routes.py
# CHANGELOG:
# - REMOVED ProxyFix import and appcontext_pushed signal that re-wrapped the app.
# - Left everything else intact. We already normalize scheme/host safely in __init__.py.

import sqlite3
import logging
from flask import Blueprint, request, abort, jsonify, render_template, send_from_directory, url_for, redirect
import json
from pathlib import Path, PurePosixPath
# CHANGED: urlencode for the /chapter?... fallback target in chapter_content_page.
from urllib.parse import urlencode
import os
from dotenv import load_dotenv
from markupsafe import escape
import re
import textwrap
import time  # CHANGED: query_log row timestamps
from typing import List, Dict, Tuple
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
# CHANGED: query_log.db lives next to chapters.db but is a separate SQLite
# file so analytics writes never touch the FTS5 index. Auto-created on
# first request; lives under backend/db/ which is .gitignored.
QUERY_LOG_PATH = BASE_DIR / os.getenv('QUERY_LOG_DB', 'db/query_log.db')
BUILD_VERSION = os.getenv('BUILD_VERSION', 'dev')  # cache-busting for template assets
PDF_DIRECTORY = BASE_DIR / os.getenv('PDF_DIRECTORY', 'pdf')


# ──────────────────────────────────────────────────────────────────────
# Query logging — lightweight per-request append for /query_stats CLI
# ──────────────────────────────────────────────────────────────────────
# CHANGED: search endpoints append one row per request to query_log.db so
# backend/scripts/helpers/query_stats.py can produce top-queries and
# zero-result reports without scraping nginx logs. Best-effort: any error
# during logging is warned and swallowed so analytics never breaks search.

def _ensure_query_log_schema() -> None:
    """Create the query_log table + indexes if missing. Idempotent."""
    conn = sqlite3.connect(str(QUERY_LOG_PATH))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS query_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ts           INTEGER NOT NULL,
                endpoint     TEXT    NOT NULL,
                query        TEXT    NOT NULL,
                result_count INTEGER NOT NULL,
                mode         TEXT,
                filters      TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS query_log_ts_idx ON query_log(ts)")
        conn.execute("CREATE INDEX IF NOT EXISTS query_log_query_idx ON query_log(query)")
        conn.commit()
    finally:
        conn.close()


def _log_query(endpoint: str, query: str, result_count: int,
               mode: str = '', filters: dict = None) -> None:
    """Append one row to query_log. Swallows all errors."""
    try:
        conn = sqlite3.connect(str(QUERY_LOG_PATH))
        try:
            conn.execute(
                "INSERT INTO query_log (ts, endpoint, query, result_count, mode, filters)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (int(time.time()), endpoint, query, result_count, mode,
                 json.dumps(filters) if filters else ''),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        # CHANGED: never let logging failure break search. Warn so we know
        # if the file is unwritable, but the request still returns 200.
        app_logger.warning("query_log write failed: %s", exc)


try:
    _ensure_query_log_schema()
except Exception as exc:
    app_logger.warning("Could not init query_log schema: %s", exc)


# CHANGED: browser-viewable stats endpoint backing query_log.db. Mirrors the
# CLI in backend/scripts/helpers/query_stats.py so we don't need SSH+sqlite
# to spot-check traffic. Gated by ADMIN_TOKEN env var because the log
# contains user queries (not public).
@main.route('/api/admin/query_stats', methods=['GET'])
def query_stats_api():
    expected = os.getenv('ADMIN_TOKEN', '').strip()
    if not expected:
        # Why: refuse to serve if no token is configured — fail closed, not
        # open. Operator must set ADMIN_TOKEN in the gunicorn unit / .env.
        abort(503, description='ADMIN_TOKEN not configured on server')
    supplied = (request.args.get('token')
                or request.headers.get('X-Admin-Token', '')).strip()
    if supplied != expected:
        abort(403)

    try:
        days = max(1, min(365, int(request.args.get('days', 7))))
    except ValueError:
        days = 7
    try:
        top = max(1, min(100, int(request.args.get('top', 20))))
    except ValueError:
        top = 20
    fmt = request.args.get('format', 'html').lower()

    cutoff = int(time.time()) - days * 86400
    conn = sqlite3.connect(str(QUERY_LOG_PATH))
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM query_log WHERE ts >= ?", (cutoff,)
        ).fetchone()[0]
        all_time, first_ts = conn.execute(
            "SELECT COUNT(*), MIN(ts) FROM query_log"
        ).fetchone()
        by_endpoint = conn.execute(
            "SELECT endpoint, COUNT(*) FROM query_log WHERE ts >= ?"
            " GROUP BY endpoint ORDER BY 2 DESC", (cutoff,)
        ).fetchall()
        by_mode = conn.execute(
            "SELECT endpoint, COALESCE(mode,''), COUNT(*) FROM query_log"
            " WHERE ts >= ? GROUP BY endpoint, mode ORDER BY endpoint, 3 DESC",
            (cutoff,)
        ).fetchall()
        top_queries = conn.execute(
            "SELECT query, COUNT(*) AS n, ROUND(AVG(result_count),1)"
            "  FROM query_log WHERE ts >= ? GROUP BY query"
            "  ORDER BY n DESC LIMIT ?", (cutoff, top)
        ).fetchall()
        zero_queries = conn.execute(
            "SELECT query, COUNT(*) AS n FROM query_log"
            "  WHERE ts >= ? AND result_count = 0 GROUP BY query"
            "  ORDER BY n DESC LIMIT ?", (cutoff, top)
        ).fetchall()
        recent = conn.execute(
            "SELECT ts, endpoint, query, result_count, COALESCE(mode,'')"
            "  FROM query_log ORDER BY id DESC LIMIT 50"
        ).fetchall()
    finally:
        conn.close()

    if fmt == 'json':
        return jsonify({
            'all_time': all_time, 'first_ts': first_ts,
            'window_days': days, 'window_count': total,
            'by_endpoint': by_endpoint, 'by_mode': by_mode,
            'top_queries': top_queries, 'zero_queries': zero_queries,
            'recent': recent,
        })

    # Minimal HTML — no template needed.
    from datetime import datetime, timezone

    def _fmt_ts(ts):
        return datetime.fromtimestamp(ts, tz=timezone.utc) \
            .astimezone().strftime('%Y-%m-%d %H:%M')

    first_str = _fmt_ts(first_ts).split(' ')[0] if first_ts else '—'

    def _row(cells):
        return '<tr>' + ''.join(f'<td>{escape(str(c))}</td>' for c in cells) + '</tr>'

    parts = [
        '<!doctype html><meta charset="utf-8"><title>query stats</title>',
        '<style>body{font-family:system-ui,sans-serif;max-width:900px;'
        'margin:2em auto;padding:0 1em;color:#222}'
        'h1{font-size:1.3em}h2{font-size:1.05em;margin-top:1.8em;'
        'border-bottom:1px solid #ddd;padding-bottom:.3em}'
        'table{border-collapse:collapse;width:100%;font-size:.92em}'
        'td,th{padding:.3em .6em;border-bottom:1px solid #eee;text-align:left;'
        'vertical-align:top}td:first-child{white-space:nowrap}'
        '.num{text-align:right;font-variant-numeric:tabular-nums}'
        'form{margin:1em 0;font-size:.9em}.kpi{font-size:1.6em;font-weight:600}'
        '.muted{color:#666;font-size:.9em}</style>',
        f'<h1>Search query stats</h1>',
        f'<div class="kpi">{all_time:,} <span class="muted">all-time queries '
        f'(since {first_str})</span></div>',
        f'<div class="kpi">{total:,} <span class="muted">in last {days} day(s)'
        f'</span></div>',
        '<form method="get">'
        f'<input type="hidden" name="token" value="{escape(supplied)}">'
        f'days <input name="days" value="{days}" size="4"> '
        f'top <input name="top" value="{top}" size="4"> '
        '<button>refresh</button> '
        f'<a href="?token={escape(supplied)}&days={days}&top={top}&format=json">json</a>'
        '</form>',
        '<h2>By endpoint</h2><table>',
        ''.join(_row([e, f'{n:,}']) for e, n in by_endpoint),
        '</table>',
        '<h2>By mode</h2><table>',
        ''.join(_row([e, m or '—', f'{n:,}']) for e, m, n in by_mode),
        '</table>',
        f'<h2>Top {top} queries</h2><table>',
        ''.join(_row([n, f'avg={avg}', q]) for q, n, avg in top_queries),
        '</table>',
        f'<h2>Top {top} zero-result queries</h2><table>',
        (''.join(_row([n, q]) for q, n in zero_queries)
         or '<tr><td class="muted">none</td></tr>'),
        '</table>',
        '<h2>Recent 50</h2><table>',
        ''.join(_row([_fmt_ts(ts), endpoint, mode, rc, q])
                for ts, endpoint, q, rc, mode in recent),
        '</table>',
    ]
    return ''.join(parts)


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
# CHANGED (2026-05-17): bare (?i)Savitri also matched 'Letters-on-Savitri',
# which IS prose (with embedded verse quotes) and must be reflowed; without
# reflow the file was text-wrapped at width=100 and ChapterPage joined those
# wrapped chunks with <br/>, producing double line breaks and splitting our
# verse-recovery <br/> markers (see scripts/helpers/recover_letters_verse_breaks.py).
# Match only the actual Savitri verse folder by name.
_deny_raw   = os.getenv('REFLOW_DENY_RE', r'(?i)33-34Savitri')

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

    # CHANGED: log query for /query_stats CLI. Endpoint label is
    # 'semantic_search' to distinguish from the FTS path on /api/text_search.
    _log_query('semantic_search', query, len(results),
               mode=search_type, filters=filters)
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

        # CHANGED: log query for /query_stats CLI. Logged here (after the
        # response shape is known) so result_count reflects what the user
        # actually saw, not the pre-dedupe candidate buckets.
        _log_query('text_search', q, len(enriched),
                   mode=mode, filters=filters)
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

# CHANGED: detect standalone "Month Day, Year" lines (e.g. "October 5, 1963")
# so chapter blocks that contain a date header inline — typical of Mother's
# Agenda where the splitter cuts at page boundaries and folds multiple dates
# into one section — can be rendered with the date promoted to a bold heading
# on its own line, instead of being collapsed into the following paragraph by
# prose reflow. Anchored to ^...$ so dates appearing mid-sentence inside prose
# are never matched.
_inline_date_rx = re.compile(
    r'^\s*(?:January|February|March|April|May|June|July|August|September|October|November|December)'
    r'\s+\d{1,2}(?:st|nd|rd|th)?,\s+\d{4}\s*$',
    re.IGNORECASE,
)

def _split_block_on_dates(lines: List[str]) -> List[Tuple[str, List[str]]]:
    """
    Split a single raw block's lines on standalone date headings. Returns a
    list of ('lines'|'date_heading', sub_lines) tuples. Date headings preserve
    only the date text (one entry per sub-list). Empty leading/trailing chunks
    are dropped so callers don't have to filter.
    """
    out: List[Tuple[str, List[str]]] = []
    buf: List[str] = []
    for ln in lines:
        if _inline_date_rx.match(ln):
            if any(x.strip() for x in buf):
                out.append(('lines', buf))
            buf = []
            out.append(('date_heading', [ln.strip()]))
        else:
            buf.append(ln)
    if any(x.strip() for x in buf):
        out.append(('lines', buf))
    return out

# CHANGED (2026-05-25): detect subsection headings — short title-case lines like
# "The Teaching of the Gita" / "Apparent Contradictions in the Gita" that the
# source .txt files emit on their own line with only a single newline before
# the following paragraph. Without this, raw_blocks (split on blank lines)
# keeps heading+paragraph in one block, and reflow then joins them mid-sentence
# because the heading has no terminal punctuation. Same shape as
# _split_block_on_dates so the renderer treats them as siblings.
_subheading_tag_rx = re.compile(r'</?[a-z][^>]*>')

def _looks_like_subheading(line: str, next_line: str) -> bool:
    s = _subheading_tag_rx.sub('', line).strip()
    nxt = _subheading_tag_rx.sub('', next_line).strip()
    if not s or not nxt:
        return False
    if len(s) > 70:
        return False
    # Headings are noun phrases — no terminal sentence punctuation, and no
    # internal `;` or `:` (those mark prose continuations). Commas are OK
    # ("The Gita, the Divine Mother and the Purushottama").
    if s[-1] in '.?!,:;':
        return False
    if ';' in s or ':' in s:
        return False
    if not s[0].isupper():
        return False
    # Next line must start a new sentence — guards against false positives on
    # wrapped prose lines where the wrap point happens to leave a fragment.
    if not nxt[0].isupper():
        return False
    words = [w for w in re.split(r'\s+', s) if w]
    if len(words) < 2 or len(words) > 12:
        return False
    cap = sum(1 for w in words if w[0].isupper())
    return cap >= max(2, len(words) // 2)

def _split_block_on_subheadings(lines: List[str]) -> List[Tuple[str, List[str]]]:
    """
    Split a block's lines so that a subsection heading at the top of the block
    is emitted as its own ('subheading', [text]) tuple, with the remainder as
    ('lines', [...]). Only checks the first non-blank line per block: real
    subheadings always appear at block boundaries in this corpus, and limiting
    the scan avoids matching prose fragments mid-paragraph.
    """
    # Find first non-blank line
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines) - 1:
        return [('lines', lines)]
    if _looks_like_subheading(lines[i], lines[i + 1]):
        heading = lines[i].strip()
        rest = lines[i + 1:]
        return [('subheading', [heading]), ('lines', rest)]
    return [('lines', lines)]

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
        # CHANGED (2026-05-23): in auto mode, treat REFLOW_ALLOW_RE as a
        # force-include override rather than a whitelist. Previously, once
        # any allow pattern was set, auto degenerated into allowlist-only
        # behavior — books not explicitly listed (e.g. Q&A 1953) fell back
        # to no-reflow even when the heuristic would have green-lit them.
        # Now: allow short-circuits to True; everything else runs through
        # the heuristic.
        if REFLOW_ALLOW_PATTERNS and _matches_any(REFLOW_ALLOW_PATTERNS, combined):
            app_logger.debug("Reflow mode=auto allow override matched for %s", combined)
            return True
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

        # CHANGED (2026-05-23): standalone "*" marks the boundary between
        # letters in the Letters-on-Yoga compilations (and any other letter
        # collection). Without this, reflow joins "*" into the next letter's
        # first paragraph because "*" doesn't end in sentence-final punct —
        # the renderer then misses the asterism case and the visual break
        # collapses. Treat "*" like a paragraph boundary so it survives as
        # its own block downstream.
        if ln.strip() == '*':
            if buf.strip():
                paragraphs.append(buf.strip())
                buf = ""
            paragraphs.append('*')
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

        # CHANGED: pre-split each raw block on standalone date headings so
        # Agenda-style "October 5, 1963" lines get their own date_heading
        # block instead of being merged into the following paragraph by reflow.
        for kind, sub_lines in _split_block_on_dates(blk.splitlines()):
            if kind == 'date_heading':
                blocks.append({'type': 'date_heading', 'text': sub_lines[0]})
                continue

            # CHANGED (2026-05-25): also split out subsection headings (see
            # _split_block_on_subheadings). Runs after date-splitting so an
            # Agenda block that contains both a date and a subheading still
            # routes each to its own block type.
            for kind2, sub_lines2 in _split_block_on_subheadings(sub_lines):
                if kind2 == 'subheading':
                    blocks.append({'type': 'subheading', 'text': sub_lines2[0]})
                    continue

                lines = sub_lines2

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

    # CHANGED (2026-05-23): build per-page meta description + canonical URL
    # so social-link previews and search engines see chapter-specific data
    # instead of the same generic homepage title for every URL. The
    # description is derived from the first prose block; stripping HTML
    # tags and clamping to ~155 chars (Google snippet length).
    meta_description = ''
    _chap_norm = re.sub(r'\s+', ' ', (chap_heading or '')).strip().lower()
    for b in blocks:
        if b.get('type') != 'lines' or not b.get('lines'):
            continue
        raw = ' '.join(b['lines'])
        raw = re.sub(r'<[^>]+>', '', raw)                # drop <i> etc.
        raw = re.sub(r'\s+', ' ', raw).strip()
        # CHANGED: skip the chapter-heading block (block 0 is usually the
        # title verbatim) and any block too short to function as a snippet.
        # Without this filter the description echoed the title, which is
        # redundant for Google's SERP and wastes the meta-description slot.
        if raw.lower() == _chap_norm or len(raw) < 60:
            continue
        meta_description = (raw[:152] + '…') if len(raw) > 155 else raw
        break
    # CHANGED: build canonical URL from the resolved (idx, slug) pair when
    # the section was found in `sections`; on a 404-ish fallback leave empty
    # so the template suppresses the <link rel="canonical"> tag rather than
    # pointing crawlers at a self-referential bad URL.
    try:
        _section_slug = rows[idx][1] if 0 <= idx < len(rows) else ''
    except (NameError, IndexError):
        _section_slug = ''
    canonical_url = (
        f"https://ask.collectedworksofsriaurobindo.com"
        f"/read/{collection}/{book_slug or book}/{_section_slug}"
    ) if _section_slug else ''

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
        # NEW (2026-05-23): per-page SEO metadata for crawlers/social previews
        meta_description=meta_description,
        canonical_url=canonical_url,
    )


@main.route('/api/chapter_content', methods=['GET'])
def chapter_content_page():
    """
    DEPRECATED legacy entry point. Redirects to the SPA so chapter rendering
    lives in one place (ChapterPage.jsx). Old bookmarks keep working — they
    get a 302 to the matching /read/<coll>/<book_slug>/<slug> when the section
    has slugs (the common case post-b.3), or to /chapter?... for legacy rows
    that pre-date the slug column.

    Forwards query / result_type / search_type so a search-result link still
    highlights correctly after the redirect.
    """
    # CHANGED: was a direct `_render_chapter_template(...)` call which served
    # the legacy chapter.html template. Switching to a redirect deletes the
    # second chapter renderer from production traffic — chapter.html is now
    # only reachable via the (also-legacy) Flask /read/... route, which is
    # dead in prod (nginx serves /read/... as the SPA index.html).
    collection = request.args.get('collection_folder', '').strip()
    book       = request.args.get('book_folder', '').strip()
    section    = request.args.get('section_filename', '').strip()

    if not (collection and book and section):
        abort(400, "collection_folder, book_folder and section_filename are required")

    # Look up slug + book_slug for this section so we can redirect to a clean
    # /read/.../<slug> URL when available. Single-row lookup keyed on the
    # exact triple the request asked for; if the section is missing we still
    # redirect to /chapter?... rather than 404 — it's the SPA's job to render
    # the "not found" state, and that keeps this route's behavior consistent.
    conn = sqlite3.connect(str(DB_PATH))
    try:
        row = conn.execute(
            "SELECT slug, book_slug FROM chapters "
            "WHERE collection_folder = ? AND book_folder = ? AND section_filename = ? "
            "LIMIT 1",
            (collection, book, section),
        ).fetchone()
    finally:
        conn.close()

    # Forward the highlight-relevant query string verbatim. Build via url_for
    # and request.args so encoding stays consistent with how chapter.html used
    # to embed them.
    forwarded = {}
    for key in ('query', 'result_type', 'search_type'):
        value = request.args.get(key)
        if value:
            forwarded[key] = value

    if row and row[0] and row[1]:
        slug, book_slug = row[0], row[1]
        target = url_for(
            'main.chapter_by_slug_page',
            collection=collection,
            book_slug=book_slug,
            slug=slug,
            **forwarded,
        )
    else:
        # Legacy fallback: section has no slug (older row). Build /chapter?...
        # directly — there's no Flask route for /chapter (it's a pure SPA path
        # served by nginx → index.html in prod, and by the React dev server
        # locally), so url_for can't resolve it.
        params = {
            'collection_folder': collection,
            'book_folder': book,
            'section_filename': section,
            **forwarded,
        }
        target = '/chapter?' + urlencode(params)
    return redirect(target, code=302)


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

        # CHANGED: pre-split each raw block on standalone date headings so
        # Agenda-style "October 5, 1963" lines get their own date_heading
        # block instead of being merged into the following paragraph by reflow.
        for kind, sub_lines in _split_block_on_dates(blk.splitlines()):
            if kind == 'date_heading':
                blocks.append({'type': 'date_heading', 'text': sub_lines[0]})
                continue

            # CHANGED (2026-05-25): split out subsection headings here too so
            # the SPA's /api/chapter response carries 'subheading' blocks.
            # Without this, ChapterPage.jsx receives the heading glued to the
            # next paragraph and renders e.g. "The Teaching of the GitaThis
            # world is as the Gita describes it…".
            for kind2, sub_lines2 in _split_block_on_subheadings(sub_lines):
                if kind2 == 'subheading':
                    blocks.append({'type': 'subheading', 'text': sub_lines2[0]})
                    continue

                lines = sub_lines2
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


# ──────────────────────────────────────────────────────────────────────
# NEW: book listing for the SPA's Books quick-picker
# ──────────────────────────────────────────────────────────────────────
# Returns one row per book with its display fields and the slug of the
# first content chapter, so the SPA can build a /read/<coll>/<book>/<slug>
# URL that opens the book at its opening section. Cached against
# chapters.db's mtime so a sync_from_splitter.sh refresh is picked up
# automatically without restarting gunicorn.
_BOOKS_CACHE: Dict[str, object] = {'mtime': None, 'data': None}


@main.route('/api/books', methods=['GET'])
def list_books():
    """List all books with their first content chapter slug.

    Used by frontend/src/components/BooksMenu.jsx to populate the global
    nav's "Books" picker. One JSON array, sorted by group_name then title.
    Excludes books with no slug-bearing content chapters (legacy rows that
    predate the slug column would otherwise produce un-navigable entries).
    """
    try:
        mtime = DB_PATH.stat().st_mtime
    except OSError:
        return jsonify({'error': 'chapters.db not available'}), 503

    # CHANGED: mtime-keyed cache so a fresh chapters.db (mv'd in by
    # sync_from_splitter.sh / DEPLOY.md §3) invalidates automatically on
    # the next request — no gunicorn restart required just to refresh.
    if _BOOKS_CACHE['data'] is not None and _BOOKS_CACHE['mtime'] == mtime:
        return jsonify(_BOOKS_CACHE['data']), 200

    conn = sqlite3.connect(str(DB_PATH))
    try:
        # CHANGED: per-book pick the lowest CAST(chapter AS INTEGER) row
        # where non_content=0 (skip TOC / Publisher's Note pages so the
        # picker lands on actual reading material) AND slug is populated
        # (legacy rows without slugs can't be deep-linked via /read/...).
        # The CTE finds the qualifying chapter number per book; the outer
        # SELECT joins back to recover the row's display fields + slug.
        # CHANGED: also pull pdf_file so the picker can offer a "PDF" link
        # next to each book that opens the source PDF in a new tab.
        rows = conn.execute("""
            WITH first_content AS (
              SELECT book_folder,
                     MIN(CAST(chapter AS INTEGER)) AS first_chapter
                FROM chapters
               WHERE COALESCE(non_content, 0) = 0
                 AND COALESCE(slug, '') <> ''
                 AND COALESCE(book_slug, '') <> ''
               GROUP BY book_folder
            )
            SELECT c.collection_folder,
                   c.book_folder,
                   c.book_title,
                   c.book_slug,
                   c.author,
                   c.group_name,
                   c.slug       AS first_slug,
                   c.pdf_file
              FROM chapters c
              JOIN first_content fc
                ON fc.book_folder = c.book_folder
               AND CAST(c.chapter AS INTEGER) = fc.first_chapter
             WHERE COALESCE(c.book_slug, '') <> ''
               AND COALESCE(c.slug, '') <> ''
             ORDER BY c.group_name COLLATE NOCASE, c.book_title COLLATE NOCASE
        """).fetchall()
    finally:
        conn.close()

    books = []
    seen = set()  # CHANGED: defend against duplicates if two sections share
                  # the same MIN(chapter) value (theoretical; not seen today).
    for r in rows:
        collection, book_folder, title, book_slug, author, group, first_slug, pdf_file = r
        if not (collection and title and book_slug and first_slug):
            # Skip the malformed Nolini-Kanta-Gupta-Seer-Poets row (empty
            # collection + title) and any row missing identifiers we need
            # to build the chapter URL.
            continue
        key = (collection, book_folder)
        if key in seen:
            continue
        seen.add(key)

        # CHANGED: build pdf_url via the same path convention as the
        # search-result enrichment block (~line 282-288): Disciples books
        # with a named author live at /api/pdfs/disciples/<author>/<file>
        # because each disciple has their own subdir under pdf/disciples/;
        # everything else is /api/pdfs/<collection>/<file>. None of this
        # checks the file actually exists — caller will see a 404 from
        # /api/pdfs/... if it doesn't, which is the same failure mode the
        # search-result PDF link has had since launch.
        pdf_url = ''
        if pdf_file:
            if collection == 'disciples' and author and author != 'Various':
                pdf_path = f"{collection}/{author}/{pdf_file}"
            else:
                pdf_path = f"{collection}/{pdf_file}"
            pdf_url = url_for('main.serve_pdf', filename=pdf_path)

        books.append({
            'collection': collection,
            'book_folder': book_folder,
            'title': title,
            'book_slug': book_slug,
            'author': author or '',
            'group_name': group or '',
            'first_slug': first_slug,
            'pdf_url': pdf_url,
        })

    _BOOKS_CACHE['mtime'] = mtime
    _BOOKS_CACHE['data'] = books
    return jsonify(books), 200


# ──────────────────────────────────────────────────────────────────────
# NEW: per-book table of contents for the redesigned Library's volume page.
# ──────────────────────────────────────────────────────────────────────
# Returns the ordered content chapters of one book (collection + book_slug),
# each with its slug so the SPA can deep-link /read/<coll>/<book_slug>/<slug>.
# Chapter display titles are derived client-side from section_filename (same
# logic the search-result cards use), so this stays a thin query. Read-only
# and additive — does not touch any existing endpoint.
@main.route('/api/book_toc', methods=['GET'])
def book_toc():
    collection = request.args.get('collection_folder', '').strip()
    book_slug  = request.args.get('book_slug', '').strip()
    if not (collection and book_slug):
        abort(400, "collection_folder and book_slug are required")

    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute(
            """
            SELECT slug, section_filename, COALESCE(parent_toc_title, ''), start_page,
                   book_title, author, group_name
              FROM chapters
             WHERE collection_folder = ?
               AND book_slug = ?
               AND COALESCE(non_content, 0) = 0
               AND COALESCE(slug, '') <> ''
             ORDER BY CAST(chapter AS INTEGER)
            """,
            (collection, book_slug)
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return jsonify({'error': 'book not found'}), 404

    chapters = [{
        'slug': r[0],
        'section_filename': r[1],
        'parent_toc_title': r[2],
        'start_page': r[3],
    } for r in rows]

    return jsonify({
        'book_title': rows[0][4] or '',
        'author': rows[0][5] or '',
        'group_name': rows[0][6] or '',
        'chapters': chapters,
    }), 200


# ──────────────────────────────────────────────────────────────────────
# NEW: editable home-page "thought of the day" messages.
# ──────────────────────────────────────────────────────────────────────
# Curated list in content/daily_messages.json; edit that file to add or
# change messages (no redeploy — the mtime-keyed cache picks it up on the
# next request). The client date-seeds the selection so every visitor sees
# the same thought on a given day.
_DAILY_PATH = BASE_DIR / 'content' / 'daily_messages.json'
_DAILY_CACHE: Dict[str, object] = {'mtime': None, 'data': None}


@main.route('/api/daily', methods=['GET'])
def daily_messages():
    try:
        mtime = _DAILY_PATH.stat().st_mtime
    except OSError:
        return jsonify({'messages': []}), 200
    if _DAILY_CACHE['data'] is not None and _DAILY_CACHE['mtime'] == mtime:
        return jsonify({'messages': _DAILY_CACHE['data']}), 200
    try:
        with open(_DAILY_PATH, encoding='utf-8') as fh:
            data = json.load(fh)
        if not isinstance(data, list):
            data = []
    except (OSError, ValueError):
        data = []
    _DAILY_CACHE['mtime'] = mtime
    _DAILY_CACHE['data'] = data
    return jsonify({'messages': data}), 200


# ──────────────────────────────────────────────────────────────────────
# SEO: bot-rendered homepage (/)
# ──────────────────────────────────────────────────────────────────────
# CHANGED (2026-05-25): Flask-rendered homepage for crawlers. nginx routes
# / to this when $is_bot matches (see DEPLOY.md §2.5); humans still hit the
# React SPA. Solves the "Referring page: None detected" problem in Search
# Console — without an HTML hub, Googlebot saw the JS-only Books modal
# as a dead-end and could only discover chapter URLs via sitemap.xml.
# Mirrors the data-shape of /api/books (same CTE) but groups by group_name
# for a TOC-style page rather than a flat JSON array.

@main.route('/', methods=['GET'])
def home_page():
    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute("""
            WITH first_content AS (
              SELECT book_folder,
                     MIN(CAST(chapter AS INTEGER)) AS first_chapter
                FROM chapters
               WHERE COALESCE(non_content, 0) = 0
                 AND COALESCE(slug, '') <> ''
                 AND COALESCE(book_slug, '') <> ''
               GROUP BY book_folder
            )
            SELECT c.collection_folder,
                   c.book_title,
                   c.book_slug,
                   c.author,
                   c.group_name,
                   c.slug AS first_slug
              FROM chapters c
              JOIN first_content fc
                ON fc.book_folder = c.book_folder
               AND CAST(c.chapter AS INTEGER) = fc.first_chapter
             WHERE COALESCE(c.book_slug, '') <> ''
               AND COALESCE(c.slug, '') <> ''
             ORDER BY c.group_name COLLATE NOCASE, c.book_title COLLATE NOCASE
        """).fetchall()
    finally:
        conn.close()

    # CHANGED: group by group_name, dedupe by (collection, book_slug) since
    # multiple sections in a book can tie on MIN(chapter) — same defensive
    # check /api/books does at line ~1389.
    groups: List[Tuple[str, List[Dict]]] = []
    current_group = None
    current_books: List[Dict] = []
    seen = set()
    for coll, title, book_slug, author, group, first_slug in rows:
        if not (coll and title and book_slug and first_slug):
            continue
        key = (coll, book_slug)
        if key in seen:
            continue
        seen.add(key)
        if group != current_group:
            if current_group is not None:
                groups.append((current_group, current_books))
            current_group = group
            current_books = []
        current_books.append({
            'collection': coll,
            'title': title,
            'book_slug': book_slug,
            'author': author or '',
            'first_slug': first_slug,
        })
    if current_group is not None:
        groups.append((current_group, current_books))

    return render_template('home.html', groups=groups)


# ──────────────────────────────────────────────────────────────────────
# SEO: /sitemap.xml + /robots.txt
# ──────────────────────────────────────────────────────────────────────
# CHANGED (2026-05-23): expose every readable chapter URL as a sitemap
# so Google + Bing can discover the corpus without crawling the SPA. The
# document is built from chapters.db at request time — small enough
# (~6k URLs) that a per-request query is cheap, and always up to date
# without a rebuild step. robots.txt points crawlers at the sitemap.

# CHANGED: canonical host for sitemap entries. Hard-coded today since the
# alias decision (sunlitpath.in vs collectedworks) is "both work for now".
# Switch this constant when you pick a canonical.
SITEMAP_BASE_URL = "https://ask.collectedworksofsriaurobindo.com"


@main.route('/sitemap.xml', methods=['GET'])
def sitemap_xml():
    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT collection_folder, book_slug, slug
              FROM chapters
             WHERE non_content = 0
               AND slug IS NOT NULL AND slug != ''
               AND book_slug IS NOT NULL AND book_slug != ''
            """
        ).fetchall()
    finally:
        conn.close()

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        # Homepage — search interface
        f'<url><loc>{SITEMAP_BASE_URL}/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>',
    ]
    for coll, book_slug, slug in rows:
        # escape() handles the rare slugs with & or special chars; the data
        # in chapters.db is alnum + hyphens almost universally but be safe.
        loc = f"{SITEMAP_BASE_URL}/read/{escape(coll)}/{escape(book_slug)}/{escape(slug)}"
        parts.append(f'<url><loc>{loc}</loc><changefreq>monthly</changefreq><priority>0.8</priority></url>')
    parts.append('</urlset>')

    return ('\n'.join(parts), 200, {'Content-Type': 'application/xml; charset=utf-8'})


@main.route('/robots.txt', methods=['GET'])
def robots_txt():
    # CHANGED (2026-05-23): explicit robots.txt with sitemap pointer.
    # Previously a static placeholder under /usr/share/nginx/html/robots.txt
    # was served by nginx; we now overrule it with a Flask route so the
    # Sitemap: directive always reflects the live host.
    body = (
        "User-agent: *\n"
        "Disallow:\n"
        f"Sitemap: {SITEMAP_BASE_URL}/sitemap.xml\n"
    )
    return (body, 200, {'Content-Type': 'text/plain; charset=utf-8'})
