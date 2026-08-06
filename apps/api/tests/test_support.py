from fastapi.testclient import TestClient

from app.main import app


def test_support_chat_requires_authentication() -> None:
    response = TestClient(app).post(
        "/api/v1/support/chat",
        json={"message": "How do I start a conversation?", "history": []},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_logout_clears_both_auth_cookies() -> None:
    response = TestClient(app).post("/api/v1/auth/logout")
    set_cookie_headers = response.headers.get_list("set-cookie")

    assert response.status_code == 204
    assert any("access_token=" in header and "Path=/" in header for header in set_cookie_headers)
    assert any(
        "refresh_token=" in header and "Path=/api/v1/auth" in header
        for header in set_cookie_headers
    )
