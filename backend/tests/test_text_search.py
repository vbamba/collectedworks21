# tests/test_text_search.py
# Run with: pytest -q

import os, sys, sqlite3, tempfile, shutil, pathlib
import unicodedata
import pytest

# Make "scripts" importable (adjust if your tests directory differs)
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.text_search import search_phrase, search_all_words, search_any_words

SCHEMA = """
-- Minimal FTS5 table that matches your queries (snippet(), MATCH on 'content')
CREATE VIRTUAL TABLE chapters USING fts5(
  chapter,
  pdf_file,
  collection_folder,
  book_folder,
  section_filename,
  book_title,
  author,
  group_name,
  priority,
  start_page,
  end_page,
  content,
  non_content UNINDEXED,           -- allow WHERE non_content = 0
  tokenize='unicode61'
);
"""

def mk_db(rows):
    """Create a temp DB with given rows (list of dicts)."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.executescript(SCHEMA)
    for r in rows:
        conn.execute(
            """INSERT INTO chapters
               (chapter,pdf_file,collection_folder,book_folder,section_filename,
                book_title,author,group_name,priority,start_page,end_page,content,non_content)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                r.get("chapter","1"),
                r.get("pdf_file","x.pdf"),
                r.get("collection_folder","CWSA"),
                r.get("book_folder","Book"),
                r.get("section_filename","sec.txt"),
                r.get("book_title","Title"),
                r.get("author","Sri Aurobindo"),
                r.get("group_name","CWSA"),
                r.get("priority",0),
                r.get("start_page",1),
                r.get("end_page",2),
                r.get("content",""),
                r.get("non_content",0),
            )
        )
    conn.commit()
    conn.close()
    return tmp.name

@pytest.fixture(autouse=True)
def env_isolated(monkeypatch):
    # Ensure each test points the search code to its own DB
    yield
    # nothing to clean here; each test sets CHAPTERS_DB directly

def test_exact_phrase_with_ligature(monkeypatch):
    content = (
        "Brahma, Vishnu, Shiva, Krishna, these are the eternal Four, "
        "the quadruple In\uFB01nite."  # 'fi' ligature
    )
    db = mk_db([{"content": content}])
    monkeypatch.setenv("CHAPTERS_DB", db)

    phrase = "Brahma, Vishnu, Shiva, Krishna, these are the eternal Four, the quadruple Infinite"
    res = search_phrase(phrase, limit=10, filters={})
    assert len(res) >= 1
    assert res[0]["result_type"] == "exact"

def test_all_words_punctuation_tokens(monkeypatch):
    content = "… the eternal Four, the quadruple In\uFB01nite …"
    db = mk_db([{"content": content}])
    monkeypatch.setenv("CHAPTERS_DB", db)

    words = ["eternal", "Four,", "quadruple", "Infinite"]
    res = search_all_words(words, limit=10, filters={})
    # our verification normalizes/retokens, so it should pass
    assert len(res) >= 1
    assert all("eternal" in res[0]["snippet"].lower() for _ in [0])  # sanity

def test_any_words(monkeypatch):
    content = "… Four and Infinite are mentioned …"
    db = mk_db([{"content": content}])
    monkeypatch.setenv("CHAPTERS_DB", db)

    res = search_any_words(["Four,", "Infinite"], limit=10, filters={})
    assert len(res) >= 1

def test_exact_phrase_escapes_embedded_quotes(monkeypatch):
    content = "hello world"
    db = mk_db([{"content": content}])
    monkeypatch.setenv("CHAPTERS_DB", db)

    res = search_phrase('hello" world', limit=10, filters={})
    assert len(res) >= 1
    assert res[0]["result_type"] == "exact"
