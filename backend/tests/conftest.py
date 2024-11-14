# backend/tests/conftest.py
import sys
from pathlib import Path
import pytest
from app import create_app

# Add the 'backend' directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client
