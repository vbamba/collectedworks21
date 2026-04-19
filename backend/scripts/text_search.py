# scripts/text_search.py
# ======================================================================
#  text_search.py  (Python 3.9 compatible + SQL logging + page‐range)
# ======================================================================
import os
import sqlite3
import logging
import re
import unicodedata            # [NEW] for Unicode normalization (de-ligature)
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict

from .ranking import (
    build_result_dict,
    sort_results,
    diversify_collections,  # kept for API parity
    is_toc_snippet,
)
from .utils import apply_filters

logger = logging.getLogger(__name__)
# Guard against duplicate handlers if module re-imports
if not logger.handlers:  # [CHANGED]
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
logger.propagate = False     # [CHANGED] avoid double logging via root
logger.setLevel(logging.DEBUG)

DB_PATH = os.getenv("CHAPTERS_DB", "db/chapters.db")
CHAPTER_SNIPPET_SIZE = int(os.getenv("CHAPTER_SNIPPET_SIZE", "200"))
TEXT_SEARCH_DEBUG = os.getenv("TEXT_SEARCH_DEBUG", "0") == "1"

# ----------------------------------------------------------------------
# Stop‐word list (minimal hard‐coded set so we don’t depend on NLTK)
# ----------------------------------------------------------------------
STOPWORDS: Set[str] = {
    "a", "an", "the", "this", "that", "these", "those", "there", "here",
    "and", "but", "or", "nor", "for", "yet", "so",
    "of", "in", "on", "at", "by", "to", "from", "with", "as", "into", "about",
    "is", "was", "are", "were", "be", "been", "being",
}

def _connect():
    return sqlite3.connect(DB_PATH)

def _log_sql(tag: str, sql: str, params: List):
    compact = " ".join(line.strip() for line in sql.splitlines())
    logger.debug("SQL (%s) %s  params=%s", tag, compact, params)

def _escape_fts5_phrase(text: str) -> str:
    # FTS5 phrase syntax uses double quotes; double embedded quotes so user input
    # cannot terminate the phrase or trigger a parser error.
    return (text or "").replace('"', '""')

# ----------------------------------------------------------------------
# NEW: Unicode-compat normalization + safe tokenization
# ----------------------------------------------------------------------
def _normalize_compat(text: str) -> str:
    """
    Normalize text to NFKC so compatibility characters (e.g., ﬁ/ﬂ ligatures)
    are converted to their ASCII forms. Also collapse weird spaces.
    """
    if not text:
        return ""
    norm = unicodedata.normalize("NFKC", text)
    # Normalize whitespace runs to a single space for phrase checks
    norm = re.sub(r"\s+", " ", norm)
    return norm

_token_re = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?")  # allows apostrophes within words

def _tokenize_query(q: str) -> List[str]:
    """
    Tokenize a query into FTS-friendly word tokens: strips punctuation like commas.
    Applies NFKC first (so 'Inﬁnite' → 'Infinite'), then lowercases for matching.
    """
    norm = _normalize_compat(q).lower()
    tokens = _token_re.findall(norm)
    # Remove stopwords but keep at least something
    toks = [t for t in tokens if t not in STOPWORDS]
    return toks or tokens or []

# ----------------------------------------------------------------------
# Helpers for diversification by book
# ----------------------------------------------------------------------
def diversify_by_book(results: List[Dict], top_k: int) -> List[Dict]:
    buckets: Dict[str, List[Dict]] = defaultdict(list)
    for r in results:
        buckets[r.get("book_title", "Unknown")].append(r)

    lists = list(buckets.values())
    diversified: List[Dict] = []
    i = 0
    while len(diversified) < top_k and any(i < len(bl) for bl in lists):
        for bl in lists:
            if i < len(bl):
                diversified.append(bl[i])
                if len(diversified) >= top_k:
                    break
        i += 1
    return diversified

def _count_occurrences(snippet: str, query_words: List[str]) -> int:
    text = _normalize_compat(snippet).lower()   # [CHANGED] normalize for consistency
    total = 0
    for w in query_words:
        ww = _normalize_compat(w).lower()
        total += len(re.findall(rf'\b{re.escape(ww)}\b', text))
    return total

def _count_unique_terms(snippet: str, query_words: List[str]) -> int:
    text = _normalize_compat(snippet).lower()   # [CHANGED]
    uniq = 0
    for w in set(_normalize_compat(qw).lower() for qw in query_words):
        if re.search(rf'\b{re.escape(w)}\b', text):
            uniq += 1
    return uniq

# ----------------------------------------------------------------------
# Row->dict converter (includes rowid for verification/debug)
# ----------------------------------------------------------------------
def _row_to_result(
    row,
    idx: int,
    category_priority: int,
    distance: float,
    result_type: str
) -> Dict:
    (
        rowid,
        chapter,
        pdf_file,
        collection_folder,
        book_folder,
        section_filename,
        book_title,
        author,
        group,
        priority_str,
        start_page,
        end_page,
        slug,           # NEW (b.3): per-section slug (may be '' for legacy rows)
        book_slug,      # NEW (b.3): per-book slug
        parent_toc_title, # NEW (b.5): journal-sub-section breadcrumb; '' when not a sub-section
        snippet,
    ) = row
    try:
        priority = int(priority_str)
    except (ValueError, TypeError):
        priority = 0

    meta = {
        "chapter": chapter,
        "pdf_file": pdf_file,
        "collection_folder": collection_folder,
        "book_folder": book_folder,
        "section_filename": section_filename,
        "book_title": book_title,
        "author": author,
        "group": group,
        "priority": priority,
        "start_page": start_page,
        "end_page": end_page,
        "slug": slug or "",           # NEW (b.3)
        "book_slug": book_slug or "", # NEW (b.3)
        "parent_toc_title": parent_toc_title or "",  # NEW (b.5)
        "pdf_url": "",
        "rowid": rowid,
    }

    enriched = build_result_dict(meta, snippet, idx, category_priority, distance)
    enriched.update({
        "collection_folder": collection_folder,
        "book_folder": book_folder,
        "section_filename": section_filename,
        "result_type": result_type,
        "start_page": start_page,
        "end_page": end_page,
        "slug": slug or "",            # NEW (b.3)
        "book_slug": book_slug or "",  # NEW (b.3)
        "parent_toc_title": parent_toc_title or "",  # NEW (b.5): exposed so TextResultCard can render a breadcrumb
        "rowid": rowid,
    })
    return enriched

# ----------------------------------------------------------------------
# EXACT‐PHRASE SEARCH  (with Unicode-aware Python fallback)
# ----------------------------------------------------------------------
def _sql_exact_phrase_candidates(phrase: str, limit: int, filters: Optional[Dict[str, str]]) -> List[tuple]:
    """
    Run the direct FTS phrase query (quoted). Returns raw rows (tuples).
    """
    filters = filters or {}
    where_clauses = ["non_content = 0", "content MATCH ?"]
    # Keep the original phrase quoted for FTS (may return 0 due to ligatures)
    params = [f'"{_escape_fts5_phrase(phrase)}"']

    grp = filters.get("group")
    if grp:
        if grp == "CWM":
            where_clauses.append("group_name IN (?,?)")
            params.extend(["CWM", "Agenda"])
        else:
            where_clauses.append("group_name = ?")
            params.append(grp)

    if filters.get("book_title"):
        where_clauses.append("book_title = ?")
        params.append(filters["book_title"])

    where_sql = " AND ".join(where_clauses)
    sql = f"""
      SELECT
        rowid,
        chapter,
        pdf_file,
        collection_folder,
        book_folder,
        section_filename,
        book_title,
        author,
        group_name AS "group",
        priority,
        start_page,
        end_page,
        slug,            -- NEW (b.3): populated from split_pdf.py → chapters.db
        book_slug,       -- NEW (b.3): per-book slug for slug-based URLs
        parent_toc_title,-- CHANGED (b.5): row_to_result unpacks 16 cols; exact-phrase SELECT had been missed, causing ValueError on all/any callers once b.5 landed
        snippet(chapters, -1, '<b>', '</b>', '…', {CHAPTER_SNIPPET_SIZE}) AS snippet
      FROM chapters
      WHERE {where_sql}
      LIMIT ?;
    """
    params.append(limit * 5)
    _log_sql("exact", sql, params)
    with _connect() as conn:
        return conn.execute(sql, params).fetchall()

def _python_verify_exact(rowids: List[int], phrase: str) -> Set[int]:
    """
    Normalize both content and phrase (NFKC + lower + collapse whitespace)
    and check if phrase is a substring of content. Returns matching rowids.
    """
    ok: Set[int] = set()
    norm_phrase = _normalize_compat(phrase).lower()
    if not norm_phrase:
        return ok
    placeholders = ",".join(["?"] * len(rowids)) if rowids else ""
    if not placeholders:
        return ok
    with _connect() as conn:
        for rowid, content in conn.execute(
            f"SELECT rowid, content FROM chapters WHERE rowid IN ({placeholders})", rowids
        ):
            norm_content = _normalize_compat(content).lower()
            if norm_phrase in norm_content:
                ok.add(rowid)
    return ok

def _exact_fallback_candidates(phrase: str, limit: int, filters: Optional[Dict[str, str]]) -> List[tuple]:
    """
    Fallback: build candidates using ALL-words on punctuation-free tokens.
    We do NOT include every token if FTS would likely miss (e.g., ligature-affected),
    because we rely on Python verification to enforce exactness.
    """
    filters = filters or {}
    tokens = _tokenize_query(phrase)          # punctuation-free, NFKC’d
    if not tokens:
        return []

    # Use up to first 6 tokens to keep SQL performant, require AND
    # (they are already stopword-filtered)
    words_for_sql = tokens[:6]
    query = " AND ".join(f'"{w}"' for w in words_for_sql)

    where_clauses = ["non_content = 0", "content MATCH ?"]
    params = [query]

    grp = filters.get("group")
    if grp:
        if grp in ("CWM", "Agenda"):
            where_clauses.append("group_name IN (?,?)")
            params.extend(["CWM", "Agenda"])
        else:
            where_clauses.append("group_name = ?")
            params.append(grp)

    if filters.get("book_title"):
        where_clauses.append("book_title = ?")
        params.append(filters["book_title"])

    where_sql = " AND ".join(where_clauses)
    sql = f"""
      SELECT
        rowid,
        chapter,
        pdf_file,
        collection_folder,
        book_folder,
        section_filename,
        book_title,
        author,
        group_name AS "group",
        priority,
        start_page,
        end_page,
        slug,            -- NEW (b.3)
        book_slug,       -- NEW (b.3)
        parent_toc_title,-- NEW (b.5): Pass-3 journal sub-section breadcrumb (empty for TOC-level entries)
        snippet(chapters, -1, '<b>', '</b>', '…', {CHAPTER_SNIPPET_SIZE}) AS snippet
      FROM chapters
      WHERE {where_sql}
      LIMIT ?;
    """
    params.append(limit * 10)  # a bit wider, Python will filter
    _log_sql("exact-fallback", sql, params)
    with _connect() as conn:
        return conn.execute(sql, params).fetchall()

def search_phrase(
    phrase: str,
    limit: int = 10,
    filters: Optional[Dict[str, str]] = None
) -> List[Dict]:
    filters = filters or {}
    logger.info("search_phrase() phrase=%r limit=%s filters=%s", phrase, limit, filters)

    # 1) Try strict FTS phrase
    rows = _sql_exact_phrase_candidates(phrase, limit, filters)
    logger.debug("Fetched %d rows (exact)", len(rows))

    # 2) If nothing, do Unicode-aware Python fallback
    if not rows:
        fallback_rows = _exact_fallback_candidates(phrase, limit, filters)
        rowids = [r[0] for r in fallback_rows]
        verified = _python_verify_exact(rowids, phrase)
        rows = [r for r in fallback_rows if r[0] in verified]
        if TEXT_SEARCH_DEBUG:
            logger.debug("exact-fallback: candidates=%d verified=%d", len(fallback_rows), len(rows))

    results = [
        _row_to_result(r, idx, category_priority=1, distance=0.0, result_type="exact")
        for idx, r in enumerate(rows)
    ]

    # Count stats for better tie-breaking in sort
    phrase_words = _tokenize_query(phrase)  # use the same tokenizer for counts
    for r in results:
        r["term_count"] = _count_occurrences(r["snippet"], phrase_words)
        r["term_unique_count"] = _count_unique_terms(r["snippet"], phrase_words)

    filtered = apply_filters(results, filters)
    filtered = [r for r in filtered if not is_toc_snippet(r["snippet"])]

    sorted_res = sort_results(filtered)
    diversified = diversify_by_book(sorted_res, top_k=limit)

    if TEXT_SEARCH_DEBUG:
        logger.debug("search_phrase(): returning %d (after sort/diversify)", len(diversified))
        logger.debug("search_phrase(): top3 %s", [
            {"grp": r.get("group"), "uniq": r.get("term_unique_count"), "cnt": r.get("term_count")}
            for r in diversified[:3]
        ])
    return diversified

# ----------------------------------------------------------------------
# ALL‐WORDS SEARCH  (strict verification with Unicode normalization)
# ----------------------------------------------------------------------
def _verify_all_words_rowids(rowids: List[int], words_clean: List[str]) -> Tuple[Set[int], Dict[int, Dict[str, List[str]]]]:
    """
    Verify in raw 'content' that *all* words exist as whole words.
    Uses NFKC normalization to handle ligatures etc.
    Returns (ok_set, debug_map) where debug_map[rowid] = {"found":[...], "missing":[...]}
    """
    if not rowids:
        return set(), {}
    placeholders = ",".join(["?"] * len(rowids))
    # Normalize the tokens once
    words_norm = [ _normalize_compat(w).lower() for w in words_clean ]
    regexes = [(w, re.compile(rf"\b{re.escape(w)}\b")) for w in words_norm]

    ok: Set[int] = set()
    debug_map: Dict[int, Dict[str, List[str]]] = {}

    with _connect() as conn:
        for rowid, content in conn.execute(
            f"SELECT rowid, content FROM chapters WHERE rowid IN ({placeholders})", rowids
        ):
            text = _normalize_compat(content).lower()
            found, missing = [], []
            for w, rx in regexes:
                (found if rx.search(text) else missing).append(w)
            if not missing:
                ok.add(rowid)
            debug_map[rowid] = {"found": found, "missing": missing}
    return ok, debug_map

def search_all_words(
    words: List[str],
    limit: int = 10,
    filters: Optional[Dict[str, str]] = None
) -> List[Dict]:
    filters = filters or {}

    # [CHANGED] robust tokenization (strip punctuation, NFKC)
    raw_tokens = _tokenize_query(" ".join(words))
    words_clean = raw_tokens  # already stopword-filtered & normalized
    query = " AND ".join(f'"{w}"' for w in words_clean) if words_clean else ""
    logger.info("search_all_words() words=%s limit=%s filters=%s", words_clean, limit, filters)

    rows: List[tuple] = []

    if filters.get("group") or filters.get("book_title"):
        where_clauses = ["non_content = 0"]
        params: List = []
        if words_clean:
            where_clauses.append("content MATCH ?")
            params.append(query)

        grp = filters.get("group")
        if grp:
            if grp in ("CWM", "Agenda"):
                where_clauses.append("group_name IN (?,?)")
                params.extend(["CWM", "Agenda"])
            else:
                where_clauses.append("group_name = ?")
                params.append(grp)

        if filters.get("book_title"):
            where_clauses.append("book_title = ?")
            params.append(filters["book_title"])

        where_sql = " AND ".join(where_clauses)
        sql = f"""
          SELECT
            rowid,
            chapter,
            pdf_file,
            collection_folder,
            book_folder,
            section_filename,
            book_title,
            author,
            group_name AS "group",
            priority,
            start_page,
            end_page,
            slug,            -- NEW (b.3)
            book_slug,       -- NEW (b.3)
            parent_toc_title,-- CHANGED (b.5): added so _row_to_result's 16-tuple unpack succeeds on the ALL-words filter path
            snippet(chapters, -1, '<b>', '</b>', '…', {CHAPTER_SNIPPET_SIZE}) AS snippet
          FROM chapters
          WHERE {where_sql}
          LIMIT ?;
        """
        params.append(limit * 5)
        _log_sql("all", sql, params)
        with _connect() as conn:
            rows = conn.execute(sql, params).fetchall()
    else:
        unions = [
            ("CWSA",),
            ("CWM", "Agenda"),
            ("Disciples",),
        ]
        for grp_tuple in unions:
            where_clauses = ["non_content = 0"]
            params: List = []

            if len(grp_tuple) == 1:
                where_clauses.append("group_name = ?")
                params.append(grp_tuple[0])
            else:
                where_clauses.append("group_name IN (?,?)")
                params.extend(grp_tuple)

            if words_clean:
                where_clauses.append("content MATCH ?")
                params.append(query)

            where_sql = " AND ".join(where_clauses)
            sql = f"""
              SELECT
                rowid,
                chapter,
                pdf_file,
                collection_folder,
                book_folder,
                section_filename,
                book_title,
                author,
                group_name AS "group",
                priority,
                start_page,
                end_page,
                slug,            -- NEW (b.3)
                book_slug,       -- NEW (b.3)
                parent_toc_title,-- CHANGED (b.5): added on the ALL-words union path (CWSA/CWM+Agenda/Disciples) to match _row_to_result's 16-tuple unpack
                snippet(chapters, -1, '<b>', '</b>', '…', {CHAPTER_SNIPPET_SIZE}) AS snippet
              FROM chapters
              WHERE {where_sql}
              LIMIT ?;
            """
            params.append(limit * 5)
            _log_sql("all-union", sql, params)
            with _connect() as conn:
                rows.extend(conn.execute(sql, params).fetchall())

    logger.debug("Fetched %d rows (all-words pre-verify)", len(rows))

    rowids = [r[0] for r in rows]
    valid, dbg = _verify_all_words_rowids(rowids, words_clean)    # Unicode-aware
    if TEXT_SEARCH_DEBUG:
        dropped = [rid for rid in rowids if rid not in valid]
        logger.debug("ALL verify: kept=%d, dropped=%d", len(valid), len(dropped))
        for rid in dropped[:5]:
            logger.debug("ALL verify drop rowid=%s missing=%s found=%s", rid, dbg.get(rid, {}).get("missing"), dbg.get(rid, {}).get("found"))

    rows = [r for r in rows if r[0] in valid]

    results = [
        _row_to_result(r, idx, category_priority=2, distance=0.1, result_type="all")
        for idx, r in enumerate(rows)
    ]

    for r in results:
        r["term_count"] = _count_occurrences(r["snippet"], words_clean)
        r["term_unique_count"] = _count_unique_terms(r["snippet"], words_clean)
        r["debug_verified"] = dbg.get(r.get("rowid"), {"found": [], "missing": []})

    filtered = apply_filters(results, filters)
    filtered = [r for r in filtered if not is_toc_snippet(r["snippet"])]
    sorted_res = sort_results(filtered)
    diversified = diversify_by_book(sorted_res, top_k=limit)

    if TEXT_SEARCH_DEBUG:
        logger.debug("search_all_words(): returning %d", len(diversified))
        logger.debug("search_all_words(): top3 %s", [
            {
                "grp": r.get("group"),
                "uniq": r.get("term_unique_count"),
                "cnt": r.get("term_count"),
                "verify": r.get("debug_verified"),
            }
            for r in diversified[:3]
        ])
    return diversified

# ----------------------------------------------------------------------
# ANY‐WORDS SEARCH (tokenization+normalization for counts only; SQL unchanged)
# ----------------------------------------------------------------------
def search_any_words(
    words: List[str],
    limit: int = 10,
    filters: Optional[Dict[str, str]] = None
) -> List[Dict]:
    filters = filters or {}

    # [CHANGED] robust tokenization for scoring; SQL will still use quoted tokens
    tokens = _tokenize_query(" ".join(words))
    words_clean = tokens

    # Build MATCH with OR over tokens (if empty, skip MATCH)
    where_clauses = ["non_content = 0"]
    params: List = []
    if words_clean:
        query = " OR ".join(f'"{w}"' for w in words_clean)
        where_clauses.append("content MATCH ?")
        params.append(query)

    logger.info("search_any_words() words=%s limit=%s filters=%s", words_clean, limit, filters)

    grp = filters.get("group")
    if grp:
        if grp == "CWM":
            where_clauses.append("group_name IN (?,?)")
            params.extend(["CWM", "Agenda"])
        else:
            where_clauses.append("group_name = ?")
            params.append(grp)

    if filters.get("book_title"):
        where_clauses.append("book_title = ?")
        params.append(filters["book_title"])

    where_sql = " AND ".join(where_clauses)
    sql = f"""
      SELECT
        rowid,
        chapter,
        pdf_file,
        collection_folder,
        book_folder,
        section_filename,
        book_title,
        author,
        group_name AS "group",
        priority,
        start_page,
        end_page,
        slug,            -- NEW (b.3)
        book_slug,       -- NEW (b.3)
        parent_toc_title,-- NEW (b.5): Pass-3 journal sub-section breadcrumb (empty for TOC-level entries)
        snippet(chapters, -1, '<b>', '</b>', '…', {CHAPTER_SNIPPET_SIZE}) AS snippet
      FROM chapters
      WHERE {where_sql}
      LIMIT ?;
    """
    params.append(limit * 5)
    _log_sql("any", sql, params)
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    logger.debug("Fetched %d rows (any-words)", len(rows))

    results = [
        _row_to_result(r, idx, category_priority=3, distance=0.2, result_type="any")
        for idx, r in enumerate(rows)
    ]

    for r in results:
        r["term_count"] = _count_occurrences(r["snippet"], words_clean)
        r["term_unique_count"] = _count_unique_terms(r["snippet"], words_clean)

    filtered = apply_filters(results, filters)
    filtered = [r for r in filtered if not is_toc_snippet(r["snippet"])]
    sorted_res = sort_results(filtered)
    diversified = diversify_by_book(sorted_res, top_k=limit)

    if TEXT_SEARCH_DEBUG:
        logger.debug("search_any_words(): returning %d", len(diversified))
        logger.debug("search_any_words(): top3 %s", [
            {"grp": r.get("group"), "uniq": r.get("term_unique_count"), "cnt": r.get("term_count")}
            for r in diversified[:3]
        ])
    return diversified
