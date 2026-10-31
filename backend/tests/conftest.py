import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

TEST_DB = Path(__file__).resolve().parent / "test_campus_memory.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["APP_ENV"] = "test"
os.environ["SEED_DEMO_DATA"] = "true"

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import engine


@pytest.fixture(scope="session")
def client():
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        engine.dispose()

        if TEST_DB.exists():
            TEST_DB.unlink()


@pytest.fixture
def tokens(client):
    def login(username):
        result = client.post(
            "/api/auth/login",
            json={
                "username": username,
                "password": "demo123!"
            }
        )
        assert result.status_code == 200, result.text
        return {
            "Authorization": f"Bearer {result.json()['access_token']}"
        }

    return login