#!/usr/bin/env python3
import sqlite3, sys

DB = "../../db/chapters.db"
if len(sys.argv) < 2:
    print("Usage: search_db.py \"your query words...\" [limit]")
    sys.exit(1)

words = sys.argv[1].split()
limit = int(sys.argv[2]) if len(sys.argv)>2 else 20

# Build AND + OR queries for testing
and_q = " AND ".join(f'"{w}"' for w in words)
or_q  = " OR ".join(f'"{w}"' for w in words)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("== Exact Phrase ==")
for row in cur.execute("SELECT book_title, section_filename FROM chapters WHERE content MATCH ? LIMIT ?", (f'"{" ".join(words)}"', limit)):
    print(" ", row["book_title"] + "-" + row["section_filename"])

print("\n== All Words (AND) ==")
for row in cur.execute("SELECT book_title, section_filename FROM chapters WHERE content MATCH ? LIMIT ?", (and_q, limit)):
    print(" ", row["book_title"] + "-" + row["section_filename"])

print("\n== Any Words (OR) ==")
for row in cur.execute("SELECT book_title, section_filename FROM chapters WHERE content MATCH ? LIMIT ?", (or_q, limit)):
    print(" ", row["book_title"] + "-" + row["section_filename"])

conn.close()
