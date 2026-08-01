# backend/tests/test_routes.py
def test_search_rejects_non_integer_top_k(client):
    response = client.get('/api/search', query_string={'query': 'test', 'top_k': 'abc'})
    assert response.status_code == 400
    assert 'top_k' in response.get_json()['error']

def test_search_rejects_negative_top_k(client):
    response = client.get('/api/search', query_string={'query': 'test', 'top_k': '-1'})
    assert response.status_code == 400
    assert 'top_k' in response.get_json()['error']

def test_text_search_rejects_negative_limit(client):
    response = client.get('/api/text_search', query_string={'query': 'test', 'limit': '-1'})
    assert response.status_code == 400
    assert 'limit' in response.get_json()['error']

def test_serve_pdf_rejects_non_pdf_paths(client):
    response = client.get('/api/pdfs/not-a-pdf.txt')
    assert response.status_code == 404
    assert response.get_json()['error'] == 'File not found.'


# NEW (2026-08-01): SEO — retired /read/ URLs and fragment pages.
# The redirect cases read a pair out of the live map rather than hard-coding
# slugs, so regenerating slug_redirects.json after a rebuild can't stale them.
import sqlite3

import pytest

from app import routes


def _redirect_pair():
    if not routes.SLUG_REDIRECTS:
        pytest.skip("no slug redirect map loaded")
    source = sorted(routes.SLUG_REDIRECTS)[0]
    return source, routes.SLUG_REDIRECTS[source]


def test_retired_slug_redirects_permanently(client):
    source, target = _redirect_pair()
    response = client.get(f'/read/{source}')
    assert response.status_code == 301
    assert response.headers['Location'].endswith(f'/read/{target}')


def test_retired_slug_redirect_keeps_query_string(client):
    source, target = _redirect_pair()
    response = client.get(f'/read/{source}', query_string={'query': 'divine'})
    assert response.status_code == 301
    assert response.headers['Location'] == f'/read/{target}?query=divine'


def test_unknown_slug_still_404s(client):
    response = client.get('/read/mother/agenda-vol-10/no-such-chapter-xyz')
    assert response.status_code == 404


def _fragment_chapter():
    """A chapter whose plain text is too short to be worth indexing."""
    conn = sqlite3.connect(str(routes.DB_PATH))
    try:
        rows = conn.execute(
            """
            SELECT collection_folder, book_slug, slug, content
              FROM chapters
             WHERE non_content = 0
               AND slug != '' AND book_slug != ''
               AND length(cast(content as blob)) < 600
            """
        ).fetchall()
    finally:
        conn.close()
    for collection, book_slug, slug, content in rows:
        plain = routes._WS_RX.sub(' ', routes._TAG_RX.sub('', content or '')).strip()
        if len(plain) < routes.MIN_INDEXABLE_CHARS:
            return f'{collection}/{book_slug}/{slug}'
    pytest.skip("no fragment chapters in this build")


def test_fragment_page_is_noindex(client):
    response = client.get(f'/read/{_fragment_chapter()}')
    assert response.status_code == 200
    assert b'<meta name="robots" content="noindex, follow">' in response.data


def test_sitemap_omits_fragment_pages(client):
    response = client.get('/sitemap.xml')
    assert response.status_code == 200
    assert f'/read/{_fragment_chapter()}<'.encode() not in response.data


def _substantial_chapters(limit=5):
    """Chapters far above the fragment threshold — these must stay indexable."""
    conn = sqlite3.connect(str(routes.DB_PATH))
    try:
        return conn.execute(
            """
            SELECT collection_folder, book_slug, slug
              FROM chapters
             WHERE non_content = 0
               AND slug != '' AND book_slug != ''
               AND length(cast(content as blob)) > 20000
             LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()


def test_substantial_chapters_are_indexable(client):
    """
    Regression guard (2026-08-01): the noindex length check once measured a
    single block of the page instead of the whole chapter, because the
    meta-description loop shadowed the variable holding the chapter text. Any
    chapter whose first paragraph was short got noindex — Karmayogin No 1, at
    9,709 characters, shipped that way. test_fragment_page_is_noindex did not
    catch it: a fragment's one block is short too, so it passed either way.
    """
    chapters = _substantial_chapters()
    assert chapters, "no substantial chapters found — check the test DB"
    for collection, book_slug, slug in chapters:
        response = client.get(f'/read/{collection}/{book_slug}/{slug}')
        assert response.status_code == 200
        assert b'name="robots"' not in response.data, \
            f'{book_slug}/{slug} is long but marked noindex'


def _legacy_chapter_params():
    conn = sqlite3.connect(str(routes.DB_PATH))
    try:
        row = conn.execute(
            """
            SELECT collection_folder, book_folder, section_filename, book_slug, slug
              FROM chapters
             WHERE non_content = 0 AND slug != '' AND book_slug != ''
             LIMIT 1
            """
        ).fetchone()
    finally:
        conn.close()
    if not row:
        pytest.skip("no chapters in the DB")
    return row


def test_legacy_chapter_url_redirects_permanently(client):
    collection, book_folder, section_filename, book_slug, slug = _legacy_chapter_params()
    response = client.get('/chapter', query_string={
        'collection_folder': collection,
        'book_folder': book_folder,
        'section_filename': section_filename,
        'query': 'divine',
    })
    assert response.status_code == 301
    assert response.headers['Location'] == f'/read/{collection}/{book_slug}/{slug}?query=divine'


def test_legacy_chapter_url_without_params_404s(client):
    assert client.get('/chapter').status_code == 404


def test_spa_tool_routes_are_noindex(client):
    for tool in routes._NOINDEX_SPA_ROUTES:
        response = client.get(f'/{tool}')
        assert response.status_code == 200, tool
        assert response.headers['X-Robots-Tag'] == 'noindex, follow', tool
        assert b'<meta name="robots" content="noindex, follow">' in response.data, tool


def test_mixed_case_slug_redirects_to_canonical_casing(client):
    collection, _book_folder, _section, book_slug, slug = _legacy_chapter_params()
    response = client.get(f'/read/{collection.capitalize()}/{book_slug}/{slug}')
    assert response.status_code == 301
    assert response.headers['Location'] == f'/read/{collection}/{book_slug}/{slug}'


def test_chapter_titles_are_unique_within_a_book(client):
    """
    Karmayogin's 33 chapters all titled themselves from the journal masthead
    because the title came from the page body. They now come from the TOC title,
    with an ordinal when siblings collide.
    """
    conn = sqlite3.connect(str(routes.DB_PATH))
    try:
        slugs = [r[0] for r in conn.execute(
            "SELECT slug FROM chapters WHERE book_slug = 'karmayogin' "
            "AND non_content = 0 AND slug != '' LIMIT 6"
        )]
    finally:
        conn.close()
    if len(slugs) < 2:
        pytest.skip("karmayogin not in this build")
    titles = []
    for slug in slugs:
        data = client.get(f'/read/sriaurobindo/karmayogin/{slug}').get_data(as_text=True)
        titles.append(data.split('<title>')[1].split('</title>')[0])
    assert len(set(titles)) == len(titles), f'duplicate titles: {titles}'


def test_chapter_title_has_no_markup(client):
    """chap_heading carries <i> tags; they must not reach the <title>."""
    response = client.get('/read/mother/agenda-vol-13/february-7-1973')
    assert response.status_code == 200
    head = response.data.split(b'</title>')[0]
    assert b'&lt;i&gt;' not in head
