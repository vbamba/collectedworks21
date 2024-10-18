# backend/tests/test_routes.py
import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_filters(client):
    response = client.get('/filters')
    assert response.status_code == 200
    data = response.get_json()
    assert 'authors' in data
    assert 'groups' in data
    assert 'book_titles' in data

def test_search(client):
    response = client.get('/search', query_string={'query': 'all can bd done'})
    assert response.status_code == 200
    data = response.get_json()
    assert 'results' in data
