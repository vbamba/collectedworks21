# backend/tests/test_routes.py
def test_filters(client):
    response = client.get('/filters')
    assert response.status_code == 200
    data = response.get_json()
    assert 'authors' in data
    assert 'groups' in data
    assert 'book_titles' in data

def test_search(client):
    response = client.get('/search', query_string={'query': 'test'})
    assert response.status_code == 200
    data = response.get_json()
    assert 'results' in data
