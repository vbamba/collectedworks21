# scripts/ranking.py

import re
import logging
from collections import Counter

logger = logging.getLogger(__name__)

# [CHANGED] simpler, safe debug toggle (defaults off).
_RANKING_DEBUG = False
def _enable_debug(flag: bool):
    """Allow upstream to enable extra ranking debug output."""
    global _RANKING_DEBUG
    _RANKING_DEBUG = bool(flag)

# ── TOC / PUBLISHER’S NOTE DETECTION ───────────────────────────────────────────
_pub_re = re.compile(r"publisher[’'`]s?\s+note", re.I)

def is_toc_snippet(snippet: str) -> bool:
    """
    Heuristic TOC detector:
     1) Contents header
     2) Publisher's Note
     3) Dot leaders
     4) Chapter/Part entries WITH dot leaders (to avoid real headings)
     5) Mostly very short lines
    """
    lines = [ln.strip() for ln in snippet.splitlines() if ln.strip()]
    if not lines:
        return False
    first = lines[0].lower()

    if first in {"contents", "table of contents"}:
        return True
    if _pub_re.match(first) or any(_pub_re.search(ln) for ln in lines[:3]):
        return True
    if any(re.search(r"\.{5,}", ln) for ln in lines):
        return True
    if re.match(r"^(chapter|part)\b", first) and any(re.search(r"\.{5,}", ln) for ln in lines):
        return True
    short = [ln for ln in lines if len(ln.split()) <= 5]
    if len(lines) >= 3 and (len(short) / len(lines)) > 0.7:
        return True
    return False

# Treat Agenda as CWM for priority
PRIMARY_CWM = {"CWM", "Agenda"}
PRIMARY_GROUPS = {"CWSA"} | PRIMARY_CWM

def build_result_dict(meta, snippet, idx, category_priority=1, distance=0.0):
    return {
        'idx': idx,
        'author': meta.get('author', 'Unknown'),
        'book_title': meta.get('book_title', 'Unknown'),
        'chapter_name': meta.get('chapter', 'N/A'),
        'file_path': meta.get('pdf_file', ''),
        'group': meta.get('group', 'Unknown'),
        'page_number': 'N/A',
        'pdf_url': meta.get('pdf_url', ''),
        'priority': meta.get('priority', 0),
        'category_priority': category_priority,
        'snippet': snippet,
        'distance': distance
    }

def sort_results(results):
    """
    Sort precedence:
      1) category_priority (exact → all → any → semantic)
      2) distance (lower first)
      3) group priority (CWSA/CWM/Agenda before Disciples)
      4) term_unique_count
      5) term_count
      6) priority
      7) match_count
    """
    file_counts = Counter((item.get('file_path', ''), item.get('category_priority')) for item in results)
    for res in results:
        key = (res.get('file_path', ''), res.get('category_priority'))
        res['match_count'] = file_counts.get(key, 1)

    def key_fn(x):
        distance = x['distance'] if x.get('distance') is not None else float('inf')
        group_penalty = 0 if x.get('group') in PRIMARY_GROUPS else 1
        term_unique = x.get('term_unique_count', 0)
        term_total  = x.get('term_count', 0)
        return (
            x.get('category_priority', 999),
            distance,
            group_penalty,
            -term_unique,
            -term_total,
            -x.get('priority', 0),
            -x.get('match_count', 1),
        )

    sorted_res = sorted(results, key=key_fn)

    # optional compact preview
    if _RANKING_DEBUG and sorted_res:
        try:
            head = sorted_res[:5]
            logger.debug(
                "sort_results(): top5 → %s",
                [
                    {
                        "type": r.get("result_type"),
                        "grp": r.get("group"),
                        "cat": r.get("category_priority"),
                        "dist": r.get("distance"),
                        "uniq": r.get("term_unique_count"),
                        "cnt": r.get("term_count"),
                        "prio": r.get("priority"),
                        "file": r.get("file_path"),
                    } for r in head
                ],
            )
        except Exception:
            pass

    return sorted_res

def diversify_collections(results, top_k=100, ratio=0.5):
    """
    Interleave CWSA and CWM(+Agenda) up to top_k, then append leftovers.
    """
    cwsa_list   = [r for r in results if r.get('group') == 'CWSA']
    cwm_family  = [r for r in results if r.get('group') in PRIMARY_CWM]
    others      = [r for r in results if r.get('group') not in PRIMARY_GROUPS]

    cwsa_quota = int(top_k * ratio)
    cwm_quota  = top_k - cwsa_quota

    cwsa_partial = cwsa_list[:cwsa_quota]
    cwm_partial  = cwm_family[:cwm_quota]

    blended = []
    i = j = 0
    while i < len(cwsa_partial) or j < len(cwm_partial):
        if i < len(cwsa_partial):
            blended.append(cwsa_partial[i]); i += 1
        if j < len(cwm_partial):
            blended.append(cwm_partial[j]); j += 1

    leftover = cwsa_list[cwsa_quota:] + cwm_family[cwm_quota:] + others
    final = (blended + leftover)[:top_k]

    if _RANKING_DEBUG:
        logger.debug(
            "diversify_collections(): cwsa=%d, cwm+agenda=%d, others=%d → top_k=%d",
            len(cwsa_list), len(cwm_family), len(others), len(final)
        )

    return final
