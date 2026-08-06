import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError, ValidationError
from app.db.session import get_db_session
from app.models.friendship import Friendship
from app.models.user import User
from app.repositories.friendship_repository import FriendshipRepository
from app.repositories.user_repository import UserRepository
from app.schemas.friendship import FriendshipResponse
from app.websocket.manager import connection_manager, event_envelope

router = APIRouter(prefix="/friends", tags=["Friends"])


def response_for(friendship: Friendship, other_user: User, current_user_id: uuid.UUID) -> FriendshipResponse:
    return FriendshipResponse(
        id=friendship.id,
        status=friendship.status,
        user=other_user,
        requested_by_me=friendship.requested_by_id == current_user_id,
        created_at=friendship.created_at,
    )


@router.get("", response_model=list[FriendshipResponse])
async def list_friends(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[FriendshipResponse]:
    rows = await FriendshipRepository(session).list_for_user(current_user.id, status="accepted")
    return [response_for(friendship, user, current_user.id) for friendship, user in rows]


@router.get("/requests", response_model=list[FriendshipResponse])
async def list_requests(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[FriendshipResponse]:
    rows = await FriendshipRepository(session).list_for_user(current_user.id, status="pending")
    return [
        response_for(friendship, user, current_user.id)
        for friendship, user in rows
        if friendship.requested_by_id != current_user.id
    ]


@router.post("/requests/{user_id}", response_model=FriendshipResponse, status_code=status.HTTP_201_CREATED)
async def send_request(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> FriendshipResponse:
    if user_id == current_user.id:
        raise ValidationError("You cannot add yourself as a friend.")
    target = await UserRepository(session).get_by_id(user_id)
    if not target or not target.is_active:
        raise NotFoundError("User not found.", code="USER_NOT_FOUND")
    repository = FriendshipRepository(session)
    existing = await repository.get_between(current_user.id, user_id)
    if existing:
        if existing.status == "pending" and existing.requested_by_id == user_id:
            existing.status = "accepted"
            await session.commit()
            await connection_manager.send_to_user(
                user_id=user_id,
                payload=event_envelope(
                    "friend.accepted",
                    {
                        "friendship_id": str(existing.id),
                        "user_id": str(current_user.id),
                        "username": current_user.username,
                    },
                ),
            )
            return response_for(existing, target, current_user.id)
        raise ConflictError("A friend request or friendship already exists.", code="FRIENDSHIP_EXISTS")
    friendship = await repository.create(current_user.id, user_id)
    await session.commit()
    await connection_manager.send_to_user(
        user_id=user_id,
        payload=event_envelope(
            "friend.requested",
            {"friendship_id": str(friendship.id), "user_id": str(current_user.id), "username": current_user.username},
        ),
    )
    return response_for(friendship, target, current_user.id)


@router.post("/requests/{friendship_id}/accept", response_model=FriendshipResponse)
async def accept_request(
    friendship_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> FriendshipResponse:
    repository = FriendshipRepository(session)
    friendship = await repository.get_by_id(friendship_id)
    if not friendship or friendship.status != "pending":
        raise NotFoundError("Friend request not found.", code="FRIEND_REQUEST_NOT_FOUND")
    if current_user.id not in (friendship.user_low_id, friendship.user_high_id):
        raise AuthorizationError()
    if friendship.requested_by_id == current_user.id:
        raise AuthorizationError("Only the recipient can accept this friend request.")
    requester = await UserRepository(session).get_by_id(friendship.requested_by_id)
    if not requester or not requester.is_active:
        raise NotFoundError("User not found.", code="USER_NOT_FOUND")
    friendship.status = "accepted"
    await session.commit()
    await connection_manager.send_to_user(
        user_id=requester.id,
        payload=event_envelope(
            "friend.accepted",
            {"friendship_id": str(friendship.id), "user_id": str(current_user.id), "username": current_user.username},
        ),
    )
    return response_for(friendship, requester, current_user.id)


@router.delete("/{friendship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_friendship(
    friendship_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    friendship = await FriendshipRepository(session).get_by_id(friendship_id)
    if not friendship:
        raise NotFoundError("Friendship not found.", code="FRIENDSHIP_NOT_FOUND")
    if current_user.id not in (friendship.user_low_id, friendship.user_high_id):
        raise AuthorizationError()
    await session.delete(friendship)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
