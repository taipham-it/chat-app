import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import get_db_session
from app.models.user import User
from app.repositories.friendship_repository import FriendshipRepository
from app.repositories.user_repository import UserRepository
from app.schemas.friendship import UserSearchResponse
from app.schemas.user import UserResponse, UserUpdateRequest

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    username = payload.username.strip()
    existing = await UserRepository(session).get_by_username(username)
    if existing and existing.id != current_user.id:
        raise ConflictError("That username is already taken.", code="USER_EXISTS")
    current_user.username = username
    current_user.avatar_url = payload.avatar_url
    await session.commit()
    await session.refresh(current_user)
    return current_user


@router.get("/search", response_model=list[UserSearchResponse])
async def search_users(
    q: str = Query(min_length=1, max_length=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[UserSearchResponse]:
    users = await UserRepository(session).search(q, current_user_id=current_user.id)
    friendship_repository = FriendshipRepository(session)
    results: list[UserSearchResponse] = []
    for user in users:
        friendship = await friendship_repository.get_between(current_user.id, user.id)
        relationship_status = "none"
        if friendship:
            relationship_status = (
                "friends"
                if friendship.status == "accepted"
                else "outgoing_pending"
                if friendship.requested_by_id == current_user.id
                else "incoming_pending"
            )
        result = UserSearchResponse.model_validate(user)
        result.friendship_status = relationship_status
        result.friendship_id = friendship.id if friendship else None
        results.append(result)
    return results


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    _current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    user = await UserRepository(session).get_by_id(user_id)
    if not user or not user.is_active:
        raise NotFoundError("User not found.", code="USER_NOT_FOUND")
    return user
