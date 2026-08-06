import uuid
from datetime import UTC, datetime

from app.schemas.message import MessageReactionResponse, MessageResponse, ToggleReactionRequest


def test_reaction_schemas() -> None:
    req = ToggleReactionRequest(emoji="👍")
    assert req.emoji == "👍"

    reaction_id = uuid.uuid4()
    msg_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)

    reaction_resp = MessageReactionResponse(
        id=reaction_id,
        message_id=msg_id,
        user_id=user_id,
        emoji="❤️",
        created_at=now,
    )
    assert reaction_resp.emoji == "❤️"

    msg_resp = MessageResponse(
        id=msg_id,
        conversation_id=uuid.uuid4(),
        sender_id=user_id,
        client_message_id=uuid.uuid4(),
        type="text",
        content="Hello world",
        media_filename=None,
        media_content_type=None,
        media_size=None,
        status="sent",
        created_at=now,
        edited_at=None,
        deleted_at=None,
        reactions=[reaction_resp],
    )
    assert len(msg_resp.reactions) == 1
    assert msg_resp.reactions[0].emoji == "❤️"
