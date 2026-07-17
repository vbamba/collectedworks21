# tests/test_text_search.py
# Run with: pytest -q

import os, sys, sqlite3, tempfile, shutil, pathlib
import unicodedata
import pytest

# Make "scripts" importable (adjust if your tests directory differs)
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# CHANGED (2026-07-15): + search_near (new proximity tier)
from scripts.text_search import search_phrase, search_near, search_all_words, search_any_words

# CHANGED (2026-07-15): schema now mirrors production chapters.db — porter
# tokenizer and the slug/book_slug/parent_toc_title columns the SELECTs read.
# The old fixture (unicode61, no slug columns) predated schema b.3/b.5 and
# would error on any query; tests only "passed" because _connect() used to
# bind CHAPTERS_DB at import time and silently hit the real db/chapters.db.
SCHEMA = """
CREATE VIRTUAL TABLE chapters USING fts5(
  chapter,
  content,
  pdf_file,
  collection_folder,
  book_folder,
  section_filename,
  book_title,
  author,
  group_name,
  priority,
  description,
  start_page UNINDEXED,
  end_page   UNINDEXED,
  slug       UNINDEXED,
  book_slug  UNINDEXED,
  parent_toc_title UNINDEXED,
  non_content UNINDEXED,
  tokenize='porter'
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
               (chapter,content,pdf_file,collection_folder,book_folder,section_filename,
                book_title,author,group_name,priority,description,start_page,end_page,
                slug,book_slug,parent_toc_title,non_content)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                r.get("chapter","1"),
                r.get("content",""),
                r.get("pdf_file","x.pdf"),
                r.get("collection_folder","CWSA"),
                r.get("book_folder","Book"),
                r.get("section_filename","sec.txt"),
                r.get("book_title","Title"),
                r.get("author","Sri Aurobindo"),
                r.get("group_name","CWSA"),
                r.get("priority",0),
                r.get("description",""),
                r.get("start_page",1),
                r.get("end_page",2),
                r.get("slug",""),
                r.get("book_slug",""),
                r.get("parent_toc_title",""),
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
        "the quadruple Inﬁnite."  # 'fi' ligature
    )
    db = mk_db([{"content": content}])
    monkeypatch.setenv("CHAPTERS_DB", db)

    phrase = "Brahma, Vishnu, Shiva, Krishna, these are the eternal Four, the quadruple Infinite"
    res = search_phrase(phrase, limit=10, filters={})
    assert len(res) >= 1
    assert res[0]["result_type"] == "exact"

def test_all_words_punctuation_tokens(monkeypatch):
    # CHANGED (2026-07-15): fixture text no longer carries a ligature — the
    # production DB is ligature-normalized (normalize_ligatures.py), and the
    # ALL-words FTS AND requires every token to be findable in the index.
    content = "… the eternal Four, the quadruple Infinite …"
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

# ----------------------------------------------------------------------
# NEW (2026-07-15): proximity (NEAR) tier
# ----------------------------------------------------------------------

# The real passage from Savitri, Canto Two "The Adoration of the Divine
# Mother" — the motivating user query said "our" where the text says "are".
SAVITRI_PASSAGE = (
    "Her light, her bliss he asked for earth and men. "
    "But vain are human power and human love "
    "To break earth's seal of ignorance and death; "
    "His nature's might seemed now an infant's grasp; "
    "Heaven is too high for outstretched hands to seize."
)

def test_near_rescues_misremembered_quote(monkeypatch):
    # "our" instead of "are": exact fails, but drop-one NEAR must find it.
    db = mk_db([
        {"content": SAVITRI_PASSAGE, "book_title": "Savitri",
         "section_filename": "canto_two.txt"},
        {"content": "Unrelated chapter about human effort and divine grace.",
         "section_filename": "other.txt"},
    ])
    monkeypatch.setenv("CHAPTERS_DB", db)

    assert search_phrase("vain our human power", limit=10, filters={}) == []
    res = search_near("vain our human power", limit=10, filters={})
    assert len(res) == 1
    assert res[0]["result_type"] == "near"
    assert res[0]["section_filename"] == "canto_two.txt"

def test_near_handles_plural_via_porter(monkeypatch):
    # "powers" for "power": the porter index makes them equivalent.
    db = mk_db([{"content": SAVITRI_PASSAGE, "book_title": "Savitri"}])
    monkeypatch.setenv("CHAPTERS_DB", db)

    res = search_near("but vain our human powers", limit=10, filters={})
    assert len(res) == 1

def test_near_requires_proximity(monkeypatch):
    # All words present but scattered → no NEAR match.
    scattered = (
        "The vain pursuit filled his days. " + "Filler words here. " * 20 +
        "Human aspiration grew. " + "More filler text follows. " * 20 +
        "A new power descended. " + "Our story continues elsewhere. " * 5
    )
    db = mk_db([{"content": scattered}])
    monkeypatch.setenv("CHAPTERS_DB", db)

    assert search_near("vain our human power", limit=10, filters={}) == []

def test_near_skips_single_word(monkeypatch):
    db = mk_db([{"content": SAVITRI_PASSAGE}])
    monkeypatch.setenv("CHAPTERS_DB", db)
    assert search_near("vain", limit=10, filters={}) == []

def test_exact_phrase_of_true_text_still_exact(monkeypatch):
    db = mk_db([{"content": SAVITRI_PASSAGE, "book_title": "Savitri"}])
    monkeypatch.setenv("CHAPTERS_DB", db)

    res = search_phrase("vain are human power", limit=10, filters={})
    assert len(res) == 1
    assert res[0]["result_type"] == "exact"

# ----------------------------------------------------------------------
# NEW (2026-07-15): British/American spelling variants
# ----------------------------------------------------------------------

def test_exact_phrase_spelling_variant(monkeypatch):
    # American query, British text (the corpus is mostly British).
    db = mk_db([{"content": "He sought to realise the Divine in life."}])
    monkeypatch.setenv("CHAPTERS_DB", db)

    res = search_phrase("realize the Divine", limit=10, filters={})
    assert len(res) == 1
    assert res[0]["result_type"] == "exact"

def test_all_words_spelling_variant(monkeypatch):
    db = mk_db([{"content": "The colour of dawn heralded a new realisation."}])
    monkeypatch.setenv("CHAPTERS_DB", db)

    res = search_all_words(["color", "realization"], limit=10, filters={})
    assert len(res) == 1

def test_all_words_verify_allows_stem_match(monkeypatch):
    # FTS(porter) matches "powers" for query "power"; the Python verify step
    # used to drop such rows with a literal \b..\b check.
    db = mk_db([{"content": "The hidden powers of the soul awaken slowly."}])
    monkeypatch.setenv("CHAPTERS_DB", db)

    res = search_all_words(["power", "soul"], limit=10, filters={})
    assert len(res) == 1
