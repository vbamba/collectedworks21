#!/usr/bin/env python3
"""
query_stats.py — print top search queries from query_log.db.

The Flask app (backend/app/routes.py) appends one row to query_log.db per
search request — see _log_query() called from /api/search and
/api/text_search. This script reads that file and prints leaderboards
without needing the app running.

Usage:
    python3 backend/scripts/helpers/query_stats.py [--days N] [--top N] [--db PATH]

Examples:
    # last 7 days, top 20 of each report (defaults)
    python3 backend/scripts/helpers/query_stats.py

    # last 24 hours, top 50
    python3 backend/scripts/helpers/query_stats.py --days 1 --top 50

    # against prod log via SSH:
    #   scp ec2-user@<host>:/home/ec2-user/collectedworks21/backend/db/query_log.db /tmp/
    #   python3 backend/scripts/helpers/query_stats.py --db /tmp/query_log.db
"""

import argparse
import sqlite3
import sys
import time
from pathlib import Path


def fmt_query(q: str, max_len: int = 70) -> str:
    """Truncate a query for display, replacing newlines."""
    q = (q or '').replace('\n', ' ').strip()
    if len(q) > max_len:
        q = q[:max_len - 1] + '…'
    return q


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    repo_root = Path(__file__).resolve().parents[3]
    parser.add_argument(
        "--db",
        default=str(repo_root / "backend" / "db" / "query_log.db"),
        help="Path to query_log.db (default: backend/db/query_log.db)",
    )
    parser.add_argument(
        "--days", type=int, default=7,
        help="Look-back window in days (default: 7)",
    )
    parser.add_argument(
        "--top", type=int, default=20,
        help="Top N rows per report (default: 20)",
    )
    args = parser.parse_args()

    db = Path(args.db)
    if not db.exists():
        print(f"ERROR: query log not found at {db}", file=sys.stderr)
        print("       (Created on first search request — has the app run yet?)",
              file=sys.stderr)
        return 1

    cutoff = int(time.time()) - args.days * 86400
    conn = sqlite3.connect(str(db))
    try:
        # ── Header
        # CHANGED: also show all-time running total + first-seen date so the
        # window count has context (e.g. "300 this week / 12,450 since
        # 2026-04-10"). One extra cheap query against the unindexed table.
        total = conn.execute(
            "SELECT COUNT(*) FROM query_log WHERE ts >= ?", (cutoff,)
        ).fetchone()[0]
        all_time, first_ts = conn.execute(
            "SELECT COUNT(*), MIN(ts) FROM query_log"
        ).fetchone()
        if first_ts:
            from datetime import datetime, timezone
            first_str = datetime.fromtimestamp(first_ts, tz=timezone.utc) \
                .astimezone().strftime("%Y-%m-%d")
            print(f"=== All-time: {all_time:,} queries (since {first_str}) ===")
        print(f"=== Last {args.days} day(s) — {total:,} queries ===\n")
        if total == 0:
            return 0

        # ── By endpoint (text vs semantic)
        print("By endpoint:")
        for endpoint, n in conn.execute("""
            SELECT endpoint, COUNT(*)
              FROM query_log WHERE ts >= ?
             GROUP BY endpoint ORDER BY 2 DESC
        """, (cutoff,)):
            print(f"  {endpoint:18s} {n:>6,}")

        # ── By mode (per-endpoint mode breakdown)
        print("\nBy mode:")
        for endpoint, mode, n in conn.execute("""
            SELECT endpoint, COALESCE(mode, ''), COUNT(*)
              FROM query_log WHERE ts >= ?
             GROUP BY endpoint, mode ORDER BY endpoint, 3 DESC
        """, (cutoff,)):
            print(f"  {endpoint:18s} {mode:12s} {n:>6,}")

        # ── Top queries (any endpoint)
        print(f"\nTop {args.top} queries (all endpoints):")
        rows = conn.execute("""
            SELECT query, COUNT(*) AS n, ROUND(AVG(result_count), 1) AS avg_r
              FROM query_log WHERE ts >= ?
             GROUP BY query ORDER BY n DESC LIMIT ?
        """, (cutoff, args.top)).fetchall()
        for q, n, avg_r in rows:
            print(f"  {n:>4}  avg_results={avg_r:>5}  {fmt_query(q)!r}")

        # ── Zero-result queries — what to look at next, content-wise
        print(f"\nTop {args.top} zero-result queries:")
        rows = conn.execute("""
            SELECT query, COUNT(*) AS n
              FROM query_log
             WHERE ts >= ? AND result_count = 0
             GROUP BY query ORDER BY n DESC LIMIT ?
        """, (cutoff, args.top)).fetchall()
        if not rows:
            print("  (none — every query returned at least one result)")
        for q, n in rows:
            print(f"  {n:>4}  {fmt_query(q)!r}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
