import urllib.parse

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.config import get_settings
from app.main import app


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_localhost_alias_cors_preflight() -> None:
    response = TestClient(app).options(
        "/api/v1/auth/register",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"


def test_websocket_without_session_closes_as_unauthorized() -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with TestClient(app).websocket_connect("/api/v1/ws") as websocket:
            websocket.receive_json()
    assert exc_info.value.code == 4401


def test_google_login_redirect_contains_state_and_openid_scopes() -> None:
    settings = get_settings()
    original_client_id = settings.GOOGLE_CLIENT_ID
    original_client_secret = settings.GOOGLE_CLIENT_SECRET
    settings.GOOGLE_CLIENT_ID = "test-client-id"
    settings.GOOGLE_CLIENT_SECRET = "test-client-secret"
    try:
        response = TestClient(app).get("/api/v1/auth/google/login", follow_redirects=False)
    finally:
        settings.GOOGLE_CLIENT_ID = original_client_id
        settings.GOOGLE_CLIENT_SECRET = original_client_secret

    assert response.status_code == 307
    parsed = urllib.parse.urlparse(response.headers["location"])
    query = urllib.parse.parse_qs(parsed.query)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == "https://accounts.google.com/o/oauth2/v2/auth"
    assert query["response_type"] == ["code"]
    assert query["scope"] == ["openid profile email"]
    assert query["state"][0]
    assert response.cookies.get("google_oauth_state") == query["state"][0]


def test_google_login_normalizes_loopback_host_to_callback_host() -> None:
    settings = get_settings()
    original_client_id = settings.GOOGLE_CLIENT_ID
    original_client_secret = settings.GOOGLE_CLIENT_SECRET
    original_redirect_uri = settings.GOOGLE_REDIRECT_URI
    settings.GOOGLE_CLIENT_ID = "test-client-id"
    settings.GOOGLE_CLIENT_SECRET = "test-client-secret"
    settings.GOOGLE_REDIRECT_URI = "http://localhost:8000/api/v1/auth/google/callback"
    try:
        response = TestClient(app, base_url="http://127.0.0.1:8000").get(
            "/api/v1/auth/google/login", follow_redirects=False
        )
    finally:
        settings.GOOGLE_CLIENT_ID = original_client_id
        settings.GOOGLE_CLIENT_SECRET = original_client_secret
        settings.GOOGLE_REDIRECT_URI = original_redirect_uri

    assert response.status_code == 307
    assert response.headers["location"] == "http://localhost:8000/api/v1/auth/google/login"
    assert "google_oauth_state" not in response.cookies


def test_google_callback_rejects_invalid_state() -> None:
    response = TestClient(app).get(
        "/api/v1/auth/google/callback?code=test&state=wrong",
        cookies={"google_oauth_state": "expected"},
        follow_redirects=False,
    )
    assert response.status_code == 307
    assert response.headers["location"].endswith("/login?error=google_invalid_state")
