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
