import os

os.environ.update(
    JWT_SECRET="test-secret-that-is-at-least-32-characters",
    ADMIN_PASSWORD="test-password-strong",
    DATABASE_URL="sqlite:///./test.db",
    ADMIN_EMAIL="admin@example.com",
    OPENAI_API_KEY="",
    TWILIO_AUTH_TOKEN="",
    OUTBOUND_ENABLED="false",
)
import pytest
from fastapi.testclient import TestClient
from app.database.session import Base, engine
from app.main import app, buckets, tickets


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    buckets.clear()
    tickets.clear()
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(engine)


@pytest.fixture
def auth(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "test-password-strong"},
    )
    return {"Authorization": "Bearer " + r.json()["access_token"]}
