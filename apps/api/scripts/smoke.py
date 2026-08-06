"""Run a real API smoke test against the configured development database."""

import asyncio
import uuid

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal, engine
from app.main import app
from app.models.conversation import Conversation
from app.models.user import User


async def main() -> None:
    suffix = uuid.uuid4().hex[:10]
    emails = [f"smoke-a-{suffix}@example.com", f"smoke-b-{suffix}@example.com"]
    user_ids: list[uuid.UUID] = []
    conversation_id: uuid.UUID | None = None
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            users = []
            for index, email in enumerate(emails):
                response = await client.post(
                    "/api/v1/auth/register",
                    json={
                        "email": email,
                        "username": f"smoke_{index}_{suffix}",
                        "password": "StrongPass123",
                    },
                )
                response.raise_for_status()
                users.append(response.json())
                user_ids.append(uuid.UUID(response.json()["id"]))

            login = await client.post(
                "/api/v1/auth/login",
                json={"email": f"smoke_0_{suffix}", "password": "StrongPass123"},
            )
            login.raise_for_status()
            assert login.json() == {"authenticated": True}
            set_cookie_headers = login.headers.get_list("set-cookie")
            assert len(set_cookie_headers) == 2
            assert all("HttpOnly" in header and "SameSite=lax" in header for header in set_cookie_headers)
            assert client.cookies.get("access_token")
            assert client.cookies.get("refresh_token")
            refreshed = await client.post(
                "/api/v1/auth/refresh",
                json={},
            )
            refreshed.raise_for_status()
            headers: dict[str, str] = {}
            current_user = await client.get("/api/v1/users/me")
            current_user.raise_for_status()
            direct = await client.post(
                "/api/v1/conversations/direct",
                headers=headers,
                json={"target_user_id": users[1]["id"]},
            )
            direct.raise_for_status()
            conversation_id = uuid.UUID(direct.json()["id"])
            sent = await client.post(
                f"/api/v1/conversations/{conversation_id}/messages",
                headers=headers,
                json={"client_message_id": str(uuid.uuid4()), "content": "Smoke test hello"},
            )
            sent.raise_for_status()
            history = await client.get(
                f"/api/v1/conversations/{conversation_id}/messages", headers=headers
            )
            history.raise_for_status()
            assert history.json()[-1]["content"] == "Smoke test hello"
            sender_conversations = await client.get("/api/v1/conversations")
            sender_conversations.raise_for_status()
            assert sender_conversations.json()[0]["last_message"]["content"] == "Smoke test hello"
            assert sender_conversations.json()[0]["unread_count"] == 0

            recipient_login = await client.post(
                "/api/v1/auth/login",
                json={"email": f"smoke_1_{suffix}", "password": "StrongPass123"},
            )
            recipient_login.raise_for_status()
            recipient_conversations = await client.get("/api/v1/conversations")
            recipient_conversations.raise_for_status()
            assert recipient_conversations.json()[0]["unread_count"] == 1
            marked_read = await client.post(
                f"/api/v1/conversations/{conversation_id}/read"
            )
            assert marked_read.status_code == 204
            recipient_conversations = await client.get("/api/v1/conversations")
            assert recipient_conversations.json()[0]["unread_count"] == 0
            logout = await client.post("/api/v1/auth/logout")
            assert logout.status_code == 204
            assert not client.cookies.get("access_token")
            assert not client.cookies.get("refresh_token")
            anonymous = await client.get("/api/v1/users/me")
            assert anonymous.status_code == 401
            print("API smoke test: HttpOnly auth, refresh, messaging and logout passed")
    finally:
        async with AsyncSessionLocal() as session:
            if conversation_id:
                await session.execute(delete(Conversation).where(Conversation.id == conversation_id))
            if user_ids:
                await session.execute(delete(User).where(User.id.in_(user_ids)))
            await session.commit()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
