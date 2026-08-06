# Messenger-Style Chat App — Guided Build Workbook

> A practical project guide for building a production-ready chat application with **Next.js, TypeScript, Tailwind CSS, FastAPI, PostgreSQL, Redis, WebSocket, and Docker**.
>
> This workbook intentionally leaves selected backend sections incomplete so you can implement them yourself. Each exercise includes:
>
> - Goal
> - Required behavior
> - File path
> - Suggested commands
> - Hints
> - Verification checklist

---

# 1. Project Goal

Build a Messenger-style web application where users can:

- Register and log in
- Search for users
- Start direct conversations
- Send and receive messages in real time
- Load previous messages
- See typing indicators
- See online/offline presence
- See sent, delivered, and read states
- Upload images and files
- Use the application on desktop and mobile

The first release should prioritize:

1. Correct message storage
2. Real-time delivery
3. Authorization
4. Reconnection
5. Duplicate prevention
6. Reliable database design

Do not add video calling, stories, or end-to-end encryption until the messaging core is stable.

---

# 2. Recommended Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | Next.js + TypeScript | Web user interface |
| Styling | Tailwind CSS | Responsive UI |
| Client state | Zustand | WebSocket and local UI state |
| Server state | TanStack Query | API caching and synchronization |
| Backend | FastAPI | REST API and WebSocket server |
| ORM | SQLAlchemy 2.0 | PostgreSQL database access |
| Validation | Pydantic v2 | Request and response validation |
| Migration | Alembic | Database schema migrations |
| Database | PostgreSQL | Durable application data |
| Cache | Redis | Presence, typing, pub/sub, rate limiting |
| File storage | Supabase Storage / MinIO / S3 | Images and files |
| Authentication | JWT access + refresh tokens | User sessions |
| Deployment | Docker Compose | Local and initial production deployment |

---

# 3. System Architecture

```text
┌─────────────────────────────────┐
│ Next.js Frontend                │
│                                 │
│ - Authentication UI             │
│ - Conversation list             │
│ - Message view                  │
│ - WebSocket client              │
│ - Zustand                       │
│ - TanStack Query                │
└───────────────┬─────────────────┘
                │
         HTTPS / WebSocket
                │
┌───────────────▼─────────────────┐
│ FastAPI Backend                 │
│                                 │
│ - REST API                      │
│ - WebSocket gateway             │
│ - Authentication               │
│ - Authorization                │
│ - Message service               │
│ - Upload service                │
└───────────┬───────────┬─────────┘
            │           │
┌───────────▼──────┐  ┌─▼──────────────┐
│ PostgreSQL       │  │ Redis          │
│                  │  │                │
│ Users            │  │ Presence       │
│ Conversations    │  │ Typing state   │
│ Messages         │  │ Pub/Sub        │
│ Read receipts    │  │ Rate limiting  │
└───────────┬──────┘  └────────────────┘
            │
┌───────────▼──────────┐
│ Object Storage       │
│                      │
│ Images               │
│ Documents            │
│ Voice files          │
└──────────────────────┘
```

---

# 4. Core Data Flow

## 4.1 Send message flow

```text
User types message
    ↓
Frontend creates client_message_id
    ↓
Frontend renders optimistic message
    ↓
Frontend sends WebSocket event
    ↓
Backend authenticates connection
    ↓
Backend checks conversation membership
    ↓
Backend stores message in PostgreSQL
    ↓
Backend publishes event through Redis
    ↓
Connected recipients receive message
    ↓
Receiver sends delivered acknowledgement
    ↓
Receiver opens conversation
    ↓
Receiver sends read acknowledgement
```

## 4.2 Reconnection flow

```text
WebSocket disconnected
    ↓
Frontend enters reconnecting state
    ↓
Reconnect with exponential backoff
    ↓
Frontend sends last received cursor
    ↓
Backend returns missed events/messages
    ↓
Frontend reconciles optimistic messages
```

---

# 5. Project Folder Structure

```text
messenger-app/
├── apps/
│   ├── web/
│   │   ├── src/
│   │   │   ├── app/
│   │   │   ├── components/
│   │   │   ├── features/
│   │   │   │   ├── auth/
│   │   │   │   ├── conversations/
│   │   │   │   ├── messages/
│   │   │   │   ├── presence/
│   │   │   │   └── uploads/
│   │   │   ├── hooks/
│   │   │   ├── lib/
│   │   │   ├── stores/
│   │   │   └── types/
│   │   └── package.json
│   │
│   └── api/
│       ├── app/
│       │   ├── api/
│       │   │   ├── dependencies/
│       │   │   └── routes/
│       │   ├── core/
│       │   ├── db/
│       │   ├── models/
│       │   ├── repositories/
│       │   ├── schemas/
│       │   ├── services/
│       │   ├── websocket/
│       │   ├── workers/
│       │   └── main.py
│       ├── migrations/
│       ├── tests/
│       ├── pyproject.toml
│       └── alembic.ini
│
├── infrastructure/
│   ├── nginx/
│   └── monitoring/
├── docker-compose.yml
├── .env.example
├── Makefile
└── README.md
```

---

# 6. Phase 1 — Create the Project

## 6.1 Create root folders

```bash
mkdir messenger-app
cd messenger-app

mkdir apps
mkdir infrastructure
```

On Windows PowerShell:

```powershell
mkdir messenger-app
cd messenger-app

mkdir apps
mkdir infrastructure
```

---

## 6.2 Create Next.js frontend

```bash
cd apps

npx create-next-app@latest web \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src-dir \
  --import-alias "@/*"
```

Install frontend libraries:

```bash
cd web

npm install axios zustand @tanstack/react-query
npm install socket.io-client
npm install lucide-react date-fns
npm install clsx tailwind-merge
```

> You may use the native WebSocket API instead of Socket.IO. This workbook uses native FastAPI WebSocket concepts, so `socket.io-client` is optional.

Run frontend:

```bash
npm run dev
```

Expected URL:

```text
http://localhost:3000
```

---

## 6.3 Create FastAPI backend

From the project root:

```bash
cd apps
mkdir api
cd api
```

Create Python virtual environment:

```bash
python -m venv .venv
```

Activate on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Activate on Windows CMD:

```cmd
.venv\Scripts\activate.bat
```

Activate on Linux/macOS:

```bash
source .venv/bin/activate
```

Install `uv`:

```bash
pip install uv
```

Initialize project:

```bash
uv init
```

Install backend dependencies:

```bash
uv add fastapi
uv add "uvicorn[standard]"
uv add sqlalchemy
uv add asyncpg
uv add alembic
uv add pydantic-settings
uv add python-dotenv
uv add "python-jose[cryptography]"
uv add "passlib[bcrypt]"
uv add python-multipart
uv add redis
uv add httpx
uv add email-validator
```

Install development dependencies:

```bash
uv add --dev pytest
uv add --dev pytest-asyncio
uv add --dev ruff
uv add --dev mypy
uv add --dev coverage
```

---

# 7. Backend Foundation

Create folders:

```bash
mkdir app
mkdir app/api
mkdir app/api/routes
mkdir app/api/dependencies
mkdir app/core
mkdir app/db
mkdir app/models
mkdir app/repositories
mkdir app/schemas
mkdir app/services
mkdir app/websocket
mkdir app/workers
mkdir tests
```

Create Python package files:

```bash
touch app/__init__.py
touch app/api/__init__.py
touch app/api/routes/__init__.py
touch app/api/dependencies/__init__.py
touch app/core/__init__.py
touch app/db/__init__.py
touch app/models/__init__.py
touch app/repositories/__init__.py
touch app/schemas/__init__.py
touch app/services/__init__.py
touch app/websocket/__init__.py
touch app/workers/__init__.py
```

Windows PowerShell alternative:

```powershell
New-Item app/__init__.py -ItemType File
New-Item app/api/__init__.py -ItemType File
New-Item app/api/routes/__init__.py -ItemType File
New-Item app/api/dependencies/__init__.py -ItemType File
New-Item app/core/__init__.py -ItemType File
New-Item app/db/__init__.py -ItemType File
New-Item app/models/__init__.py -ItemType File
New-Item app/repositories/__init__.py -ItemType File
New-Item app/schemas/__init__.py -ItemType File
New-Item app/services/__init__.py -ItemType File
New-Item app/websocket/__init__.py -ItemType File
New-Item app/workers/__init__.py -ItemType File
```

---

# 8. Environment Variables

Create:

```text
apps/api/.env
```

```env
APP_NAME=Messenger App API
APP_ENV=development
DEBUG=true

API_V1_PREFIX=/api/v1

POSTGRES_USER=messenger
POSTGRES_PASSWORD=messenger_password
POSTGRES_DB=messenger_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

DATABASE_URL=postgresql+asyncpg://messenger:messenger_password@localhost:5432/messenger_db

REDIS_URL=redis://localhost:6379/0

JWT_SECRET_KEY=CHANGE_THIS_TO_A_LONG_RANDOM_SECRET
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

CORS_ORIGINS=http://localhost:3000

MAX_UPLOAD_SIZE_MB=10
```

Create:

```text
apps/api/.env.example
```

Use the same variable names but remove real secrets.

Generate a random secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

---

# 9. Exercise 1 — Application Settings

## File

```text
apps/api/app/core/config.py
```

## Goal

Create a Pydantic settings class that reads values from `.env`.

## Required fields

- `APP_NAME`
- `APP_ENV`
- `DEBUG`
- `API_V1_PREFIX`
- `DATABASE_URL`
- `REDIS_URL`
- `JWT_SECRET_KEY`
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS`
- `CORS_ORIGINS`
- `MAX_UPLOAD_SIZE_MB`

## Blank backend section

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # TODO: Add all required settings fields.

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    # TODO: Return a cached Settings instance.
    pass
```

## Suggested commands

Run Python shell:

```bash
uv run python
```

Test settings:

```python
from app.core.config import get_settings

settings = get_settings()
print(settings.APP_NAME)
print(settings.DATABASE_URL)
```

## Hints

- Strings can use `str`
- Debug should use `bool`
- Expiry and upload limits should use `int`
- `CORS_ORIGINS` can initially be a comma-separated string

## Verification checklist

- [ ] `.env` values load correctly
- [ ] Missing required variables produce an error
- [ ] `get_settings()` returns the same cached object
- [ ] Secrets are not hardcoded

---

# 10. Exercise 2 — Database Session

## File

```text
apps/api/app/db/session.py
```

## Goal

Create an asynchronous SQLAlchemy engine and session factory.

## Blank backend section

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

# TODO: Create async engine.
engine = None

# TODO: Create async session factory.
AsyncSessionLocal = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    # TODO:
    # 1. Open a database session.
    # 2. Yield the session.
    # 3. Roll back when an exception occurs.
    # 4. Close the session.
    pass
```

## Suggested research commands

Inspect SQLAlchemy installation:

```bash
uv run python -c "import sqlalchemy; print(sqlalchemy.__version__)"
```

Open SQLAlchemy async documentation from package help:

```bash
uv run python -c "from sqlalchemy.ext.asyncio import create_async_engine; help(create_async_engine)"
```

Run type checker:

```bash
uv run mypy app/db/session.py
```

## Hints

Use:

```python
create_async_engine(...)
async_sessionmaker(...)
```

Recommended engine options:

```python
pool_pre_ping=True
echo=settings.DEBUG
```

## Verification checklist

- [ ] Backend connects to PostgreSQL
- [ ] Sessions close after requests
- [ ] Failed transactions roll back
- [ ] Engine uses the asyncpg driver

---

# 11. Docker Compose Infrastructure

Create:

```text
docker-compose.yml
```

```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: messenger-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: messenger
      POSTGRES_PASSWORD: messenger_password
      POSTGRES_DB: messenger_db
    ports:
      - "5432:5432"
    volumes:
      - messenger_postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U messenger -d messenger_db"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    container_name: messenger-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - messenger_redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  messenger_postgres_data:
  messenger_redis_data:
```

Start services:

```bash
docker compose up -d
```

Check status:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs -f postgres
docker compose logs -f redis
```

Test PostgreSQL:

```bash
docker exec -it messenger-postgres psql -U messenger -d messenger_db
```

Test Redis:

```bash
docker exec -it messenger-redis redis-cli ping
```

Expected result:

```text
PONG
```

---

# 12. Database Models

## 12.1 Base model

Create:

```text
apps/api/app/db/base.py
```

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

---

# 13. Exercise 3 — User Model

## File

```text
apps/api/app/models/user.py
```

## Required columns

| Column | Type | Rules |
|---|---|---|
| id | UUID | Primary key |
| email | String | Unique, indexed, required |
| username | String | Unique, indexed, required |
| password_hash | Text | Required |
| is_active | Boolean | Default true |
| created_at | DateTime timezone | Server default now |
| updated_at | DateTime timezone | Server default now |

## Blank backend section

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    # TODO: Implement all required columns.
    pass
```

## Suggested commands

Create an interactive Python shell:

```bash
uv run python
```

Test import:

```python
from app.models.user import User
print(User.__tablename__)
```

Run linter:

```bash
uv run ruff check app/models/user.py
```

## Hints

Example mapped field:

```python
id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    primary_key=True,
    default=uuid.uuid4,
)
```

## Verification checklist

- [ ] UUID generated automatically
- [ ] Email is unique
- [ ] Username is unique
- [ ] Password hash is never nullable
- [ ] Timestamps use timezone-aware values

---

# 14. Exercise 4 — Conversation Models

## Files

```text
apps/api/app/models/conversation.py
apps/api/app/models/conversation_member.py
```

## Conversation requirements

- UUID primary key
- Type: `direct` or `group`
- Optional title
- Optional avatar URL
- Creator user ID
- Optional `direct_key`
- Created timestamp
- Updated timestamp

## Conversation member requirements

- Composite primary key:
  - conversation ID
  - user ID
- Role:
  - member
  - admin
  - owner
- Joined timestamp
- Last-read message ID
- Muted status

## Blank conversation model

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    # TODO: Define columns.

    # TODO: Define members relationship.
    pass
```

## Blank member model

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ConversationMember(Base):
    __tablename__ = "conversation_members"

    # TODO: Define composite primary key.
    # TODO: Define role, joined_at, last_read_message_id, is_muted.
    # TODO: Define relationships.
    pass
```

## Business rule

For direct conversations, generate:

```text
direct:{smaller_user_uuid}:{larger_user_uuid}
```

Add a unique constraint for `direct_key`.

## Verification checklist

- [ ] Duplicate direct conversations are prevented
- [ ] Conversation deletion removes membership rows
- [ ] User deletion is handled intentionally
- [ ] Group title can be null only when appropriate
- [ ] Membership role is validated

---

# 15. Exercise 5 — Message Model

## File

```text
apps/api/app/models/message.py
```

## Required columns

- `id`
- `conversation_id`
- `sender_id`
- `client_message_id`
- `reply_to_message_id`
- `type`
- `content`
- `status`
- `created_at`
- `edited_at`
- `deleted_at`

## Important constraint

```text
UNIQUE(sender_id, client_message_id)
```

This prevents duplicates when the client retries sending the same message.

## Blank backend section

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Message(Base):
    __tablename__ = "messages"

    __table_args__ = (
        # TODO: Add unique constraint for sender_id + client_message_id.
    )

    # TODO: Implement message columns.
    # TODO: Implement relationships.
    pass
```

## Required indexes

Create indexes for:

```text
messages(conversation_id, created_at DESC)
messages(sender_id, created_at DESC)
```

## Verification checklist

- [ ] Duplicate retry does not create duplicate row
- [ ] Message belongs to a valid conversation
- [ ] Sender belongs to a valid user
- [ ] Reply target can be null
- [ ] Soft deletion is possible
- [ ] Message timestamps are timezone-aware

---

# 16. Alembic Migrations

Initialize Alembic:

```bash
cd apps/api
uv run alembic init migrations
```

Update:

```text
apps/api/alembic.ini
```

Do not hardcode production credentials.

Update:

```text
apps/api/migrations/env.py
```

Import:

```python
from app.db.base import Base
from app.models.user import User
from app.models.conversation import Conversation
from app.models.conversation_member import ConversationMember
from app.models.message import Message

target_metadata = Base.metadata
```

Generate migration:

```bash
uv run alembic revision --autogenerate -m "create chat core tables"
```

Inspect migration before applying it.

Apply migration:

```bash
uv run alembic upgrade head
```

Show current migration:

```bash
uv run alembic current
```

Show history:

```bash
uv run alembic history
```

Rollback one migration:

```bash
uv run alembic downgrade -1
```

---

# 17. Exercise 6 — Password Hashing

## File

```text
apps/api/app/core/security.py
```

## Goal

Implement:

- Password hashing
- Password verification
- Access token generation
- Refresh token generation
- JWT decoding

## Blank backend section

```python
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

password_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    # TODO: Hash password.
    pass


def verify_password(plain_password: str, password_hash: str) -> bool:
    # TODO: Verify password.
    pass


def create_access_token(subject: str) -> str:
    # TODO:
    # 1. Create expiration time.
    # 2. Create JWT payload.
    # 3. Encode JWT.
    pass


def create_refresh_token(subject: str) -> str:
    # TODO: Create refresh token with a longer expiration.
    pass


def decode_token(token: str) -> dict[str, Any]:
    # TODO:
    # Decode token.
    # Raise a controlled authentication exception when invalid.
    pass
```

## Suggested commands

Inspect jose:

```bash
uv run python -c "from jose import jwt; help(jwt.encode)"
```

Inspect Passlib:

```bash
uv run python -c "from passlib.context import CryptContext; help(CryptContext)"
```

Run tests:

```bash
uv run pytest tests/test_security.py -v
```

## Security requirements

- Do not store plain passwords
- Do not log passwords
- Access token should be short-lived
- Refresh token should have a different token type
- Check the `type` claim during decoding

## Suggested token payload

```json
{
  "sub": "user-uuid",
  "type": "access",
  "iat": 1784690000,
  "exp": 1784690900
}
```

---

# 18. Exercise 7 — User Repository

## File

```text
apps/api/app/repositories/user_repository.py
```

## Goal

Implement database operations separately from route handlers.

## Blank backend section

```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        # TODO: Query user by ID.
        pass

    async def get_by_email(self, email: str) -> User | None:
        # TODO: Query user by normalized email.
        pass

    async def get_by_username(self, username: str) -> User | None:
        # TODO: Query user by normalized username.
        pass

    async def create(
        self,
        *,
        email: str,
        username: str,
        password_hash: str,
    ) -> User:
        # TODO:
        # 1. Create User object.
        # 2. Add to session.
        # 3. Flush.
        # 4. Refresh.
        # 5. Return user.
        pass
```

## Suggested commands

Run repository tests:

```bash
uv run pytest tests/repositories/test_user_repository.py -v
```

Check SQL generated during development:

```env
DEBUG=true
```

## Verification checklist

- [ ] Email lookup is case-normalized
- [ ] Username lookup is case-normalized
- [ ] Duplicate email raises a controlled error
- [ ] Duplicate username raises a controlled error
- [ ] Repository does not contain HTTP-specific logic

---

# 19. Exercise 8 — Authentication Service

## File

```text
apps/api/app/services/auth_service.py
```

## Goal

Implement business logic for registration and login.

## Blank backend section

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def register(
        self,
        *,
        email: str,
        username: str,
        password: str,
    ):
        # TODO:
        # 1. Normalize email and username.
        # 2. Check duplicates.
        # 3. Validate password strength.
        # 4. Hash password.
        # 5. Create user.
        # 6. Commit transaction.
        # 7. Return user.
        pass

    async def login(self, *, email: str, password: str) -> dict[str, str]:
        # TODO:
        # 1. Find user.
        # 2. Verify active status.
        # 3. Verify password.
        # 4. Create access token.
        # 5. Create refresh token.
        # 6. Return token response.
        pass
```

## Business rules

Password should initially require:

- Minimum 8 characters
- At least one lowercase letter
- At least one uppercase letter
- At least one number

## Verification checklist

- [ ] Duplicate users rejected
- [ ] Wrong password rejected
- [ ] Inactive user rejected
- [ ] Password is hashed before database insert
- [ ] Login returns access and refresh tokens
- [ ] Service does not return password hash

---

# 20. Pydantic Schemas

Create:

```text
apps/api/app/schemas/auth.py
```

```python
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
```

Create:

```text
apps/api/app/schemas/user.py
```

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    username: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

---

# 21. Exercise 9 — Authentication Routes

## File

```text
apps/api/app/api/routes/auth.py
```

## Blank backend section

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
):
    # TODO: Call AuthService.register.
    pass


@router.post(
    "/login",
    response_model=TokenResponse,
)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
):
    # TODO: Call AuthService.login.
    pass
```

## Suggested commands

Run API:

```bash
uv run uvicorn app.main:app --reload
```

Open documentation:

```text
http://localhost:8000/docs
```

Test registration with curl:

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "tai@example.com",
    "username": "tai",
    "password": "StrongPass123"
  }'
```

Windows PowerShell:

```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:8000/api/v1/auth/register" `
  -ContentType "application/json" `
  -Body '{
    "email": "tai@example.com",
    "username": "tai",
    "password": "StrongPass123"
  }'
```

---

# 22. Exercise 10 — Current User Dependency

## File

```text
apps/api/app/api/dependencies/auth.py
```

## Goal

Read a bearer token, decode it, load the user, and reject invalid authentication.

## Blank backend section

```python
import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db_session
from app.models.user import User
from app.repositories.user_repository import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    # TODO:
    # 1. Ensure credentials exist.
    # 2. Decode token.
    # 3. Ensure token type is access.
    # 4. Parse user UUID.
    # 5. Load user.
    # 6. Ensure user is active.
    # 7. Return user.
    pass
```

## Verification checklist

- [ ] Missing token returns 401
- [ ] Invalid token returns 401
- [ ] Refresh token cannot access protected endpoints
- [ ] Deleted user cannot access protected endpoints
- [ ] Inactive user cannot access protected endpoints

---

# 23. Conversation Creation Logic

## Direct conversation algorithm

```python
def build_direct_key(user_a_id: str, user_b_id: str) -> str:
    ordered_ids = sorted([user_a_id, user_b_id])
    return f"direct:{ordered_ids[0]}:{ordered_ids[1]}"
```

## Exercise 11 — Conversation Service

## File

```text
apps/api/app/services/conversation_service.py
```

## Required behavior

When user A starts a direct conversation with user B:

1. Reject conversation with self
2. Check that user B exists
3. Generate deterministic direct key
4. Search for existing conversation
5. Return existing conversation when found
6. Otherwise create conversation
7. Add both members
8. Commit atomically

## Blank backend section

```python
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_direct_conversation(
        self,
        *,
        current_user: User,
        target_user_id: uuid.UUID,
    ):
        # TODO: Implement direct conversation business logic.
        pass
```

## Transaction requirement

Conversation and membership rows must be created inside one transaction.

Suggested pattern:

```python
async with self.session.begin():
    ...
```

## Verification checklist

- [ ] Self-conversation rejected
- [ ] Missing target user rejected
- [ ] Existing direct conversation returned
- [ ] Duplicate requests remain safe
- [ ] Both users become members
- [ ] Partial membership is never committed

---

# 24. Exercise 12 — Message Sending Service

## File

```text
apps/api/app/services/message_service.py
```

## Required behavior

1. Validate that sender belongs to conversation
2. Validate message content
3. Check existing `client_message_id`
4. Return existing message for duplicate retries
5. Create message
6. Update conversation timestamp
7. Commit transaction
8. Publish real-time event after successful storage

## Blank backend section

```python
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class MessageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def send_text_message(
        self,
        *,
        current_user: User,
        conversation_id: uuid.UUID,
        client_message_id: uuid.UUID,
        content: str,
    ):
        # TODO:
        # Validate membership.
        # Validate content.
        # Handle duplicate retry.
        # Store message.
        # Update conversation.
        # Commit transaction.
        # Return stored message.
        pass
```

## Required validation

- Empty content rejected
- Content length limited
- Sender must be a member
- Conversation must exist
- Blocked users should be handled later
- `sender_id` must come from `current_user`, not request body

## Verification checklist

- [ ] Unauthorized user cannot send
- [ ] Duplicate client ID returns same message
- [ ] Empty content rejected
- [ ] Message stored before broadcast
- [ ] Sender cannot impersonate another user

---

# 25. Cursor-Based Message Pagination

Recommended API:

```text
GET /api/v1/conversations/{conversation_id}/messages?before=<message-id>&limit=30
```

Alternative timestamp cursor:

```text
GET /api/v1/conversations/{conversation_id}/messages?before_created_at=...
```

## Exercise 13 — Message History Query

## Required behavior

- Check conversation membership
- Default limit: 30
- Maximum limit: 100
- Return newest messages before cursor
- Stable ordering using:
  - `created_at`
  - `id`

## Blank repository method

```python
async def list_messages(
    self,
    *,
    conversation_id: uuid.UUID,
    before_created_at: datetime | None,
    before_id: uuid.UUID | None,
    limit: int,
) -> list[Message]:
    # TODO: Implement stable cursor pagination.
    pass
```

## Important

Do not use offset pagination for very large chat histories.

---

# 26. Redis Client

Create:

```text
apps/api/app/core/redis.py
```

```python
from redis.asyncio import Redis

from app.core.config import get_settings

settings = get_settings()

redis_client = Redis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
)
```

Test connection:

```bash
uv run python -c "import asyncio; from app.core.redis import redis_client; print(asyncio.run(redis_client.ping()))"
```

---

# 27. Exercise 14 — WebSocket Connection Manager

## File

```text
apps/api/app/websocket/manager.py
```

## Goal

Track active WebSocket connections by user.

## Blank backend section

```python
import uuid
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[
            uuid.UUID,
            set[WebSocket],
        ] = defaultdict(set)

    async def connect(
        self,
        *,
        user_id: uuid.UUID,
        websocket: WebSocket,
    ) -> None:
        # TODO:
        # Accept WebSocket.
        # Store connection for user.
        pass

    def disconnect(
        self,
        *,
        user_id: uuid.UUID,
        websocket: WebSocket,
    ) -> None:
        # TODO:
        # Remove connection.
        # Remove empty user key.
        pass

    async def send_to_user(
        self,
        *,
        user_id: uuid.UUID,
        payload: dict,
    ) -> None:
        # TODO:
        # Send JSON to every active device.
        # Remove dead connections safely.
        pass

    async def broadcast_to_users(
        self,
        *,
        user_ids: list[uuid.UUID],
        payload: dict,
    ) -> None:
        # TODO: Send event to each user.
        pass


connection_manager = ConnectionManager()
```

## Important limitation

This in-memory manager works only for one FastAPI process.

For multiple backend instances:

- Publish events through Redis Pub/Sub
- Each backend instance subscribes
- Each instance forwards events to its local WebSocket connections

## Verification checklist

- [ ] Multiple devices supported
- [ ] Dead sockets removed
- [ ] One failed socket does not stop all sends
- [ ] Disconnect cleanup works
- [ ] Connection manager contains no database logic

---

# 28. WebSocket Event Contract

Use a consistent event envelope:

```json
{
  "event_id": "uuid",
  "event_type": "message.created",
  "timestamp": "2026-07-22T04:30:00Z",
  "data": {
    "message_id": "uuid",
    "conversation_id": "uuid",
    "sender_id": "uuid",
    "client_message_id": "uuid",
    "type": "text",
    "content": "Hello",
    "created_at": "2026-07-22T04:30:00Z"
  }
}
```

Client send event:

```json
{
  "event_type": "message.send",
  "data": {
    "conversation_id": "uuid",
    "client_message_id": "uuid",
    "content": "Hello"
  }
}
```

Error event:

```json
{
  "event_type": "error",
  "data": {
    "code": "CONVERSATION_ACCESS_DENIED",
    "message": "You are not a member of this conversation.",
    "client_message_id": "uuid"
  }
}
```

---

# 29. Exercise 15 — WebSocket Route

## File

```text
apps/api/app/api/routes/websocket.py
```

## Blank backend section

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
):
    # TODO:
    # 1. Read access token.
    # 2. Authenticate user.
    # 3. Connect using ConnectionManager.
    # 4. Receive JSON events in loop.
    # 5. Route message.send events.
    # 6. Handle typing events.
    # 7. Handle WebSocketDisconnect.
    # 8. Clean up connection.
    pass
```

## Authentication options

Option A:

```text
ws://localhost:8000/api/v1/ws?token=<access-token>
```

Option B:

Use a secure cookie.

For a learning project, query-token authentication is easier. For production, secure cookies or a short-lived WebSocket ticket are safer.

## Verification checklist

- [ ] Invalid token rejected
- [ ] Valid user connected
- [ ] Disconnect cleanup works
- [ ] Unsupported event returns controlled error
- [ ] JSON parsing errors do not crash server
- [ ] Message sender identity comes from token

---

# 30. Exercise 16 — Typing Indicator

## Redis key

```text
typing:conversation:{conversation_id}:{user_id}
```

## Required behavior

- Typing state expires automatically
- Typing start is rate-limited/debounced
- Typing state is not stored in PostgreSQL
- Only conversation members receive typing events

## Blank service method

```python
async def set_typing(
    *,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    is_typing: bool,
) -> None:
    # TODO:
    # When true:
    #   Set Redis key with short TTL.
    # When false:
    #   Delete Redis key.
    # Publish typing event.
    pass
```

Recommended TTL:

```text
5 seconds
```

---

# 31. Exercise 17 — Online Presence

## Redis design

```text
presence:user:{user_id}:connections
```

Recommended approach:

- Increment when a WebSocket connects
- Decrement when a WebSocket disconnects
- User is online while connection count > 0
- Save `last_seen_at` in PostgreSQL when final connection closes

## Blank methods

```python
async def mark_online(user_id: uuid.UUID) -> None:
    # TODO: Increment active connection count.
    pass


async def mark_offline(user_id: uuid.UUID) -> None:
    # TODO:
    # Decrement count.
    # If count reaches zero:
    #   delete presence key
    #   update last_seen_at
    #   publish presence.changed
    pass
```

## Verification checklist

- [ ] Multiple tabs do not incorrectly mark user offline
- [ ] Multiple devices supported
- [ ] Crashed connections eventually expire
- [ ] Last seen saved only after final disconnect
- [ ] Presence visible only to authorized users

---

# 32. Main FastAPI Application

Create:

```text
apps/api/app/main.py
```

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, websocket
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.CORS_ORIGINS.split(",")
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    auth.router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    websocket.router,
    prefix=settings.API_V1_PREFIX,
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
```

Run:

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Check:

```text
http://localhost:8000/health
http://localhost:8000/docs
```

---

# 33. Backend Error Handling

Create:

```text
apps/api/app/core/exceptions.py
```

Suggested domain exceptions:

```python
class AppError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        status_code: int,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class AuthenticationError(AppError):
    pass


class AuthorizationError(AppError):
    pass


class NotFoundError(AppError):
    pass


class ConflictError(AppError):
    pass


class ValidationError(AppError):
    pass
```

## Exercise 18 — Global Exception Handler

Create:

```text
apps/api/app/core/handlers.py
```

Required response:

```json
{
  "error": {
    "code": "USER_EMAIL_EXISTS",
    "message": "A user with this email already exists."
  }
}
```

Blank section:

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError


def register_exception_handlers(app: FastAPI) -> None:
    # TODO: Register handler for AppError.
    pass
```

---

# 34. Logging

Use structured logs.

Recommended log fields:

```text
timestamp
level
request_id
user_id
conversation_id
message_id
event_type
duration_ms
error_code
```

Never log:

- Passwords
- JWT tokens
- Refresh tokens
- Full private message content
- Secret keys
- Database passwords

Suggested package:

```bash
uv add structlog
```

---

# 35. Backend Testing Structure

```text
apps/api/tests/
├── conftest.py
├── test_health.py
├── test_security.py
├── repositories/
│   ├── test_user_repository.py
│   ├── test_conversation_repository.py
│   └── test_message_repository.py
├── services/
│   ├── test_auth_service.py
│   ├── test_conversation_service.py
│   └── test_message_service.py
└── websocket/
    └── test_websocket.py
```

Run all tests:

```bash
uv run pytest -v
```

Run with coverage:

```bash
uv run coverage run -m pytest
uv run coverage report -m
```

Run one test:

```bash
uv run pytest tests/services/test_message_service.py::test_send_message -v
```

---

# 36. Exercise 19 — Security Tests

Create:

```text
apps/api/tests/test_security.py
```

Required test cases:

```python
def test_hash_password_does_not_return_plain_password():
    # TODO
    pass


def test_verify_password_accepts_correct_password():
    # TODO
    pass


def test_verify_password_rejects_wrong_password():
    # TODO
    pass


def test_access_token_contains_access_type():
    # TODO
    pass


def test_refresh_token_contains_refresh_type():
    # TODO
    pass
```

## Verification checklist

- [ ] Password hash changes between runs
- [ ] Correct password verifies
- [ ] Wrong password fails
- [ ] Access token has correct type
- [ ] Refresh token has correct type
- [ ] Expired token is rejected

---

# 37. Exercise 20 — Message Service Tests

Required scenarios:

- Member sends a message successfully
- Non-member cannot send
- Empty content rejected
- Duplicate client message ID returns same message
- Conversation timestamp updates
- Database failure does not broadcast event
- Stored sender ID equals authenticated user ID

Suggested command:

```bash
uv run pytest tests/services/test_message_service.py -v
```

---

# 38. Frontend Pages

Recommended routes:

```text
/login
/register
/chat
/chat/[conversationId]
/settings/profile
```

Recommended layout:

```text
Desktop:
┌────────────────┬─────────────────────────────┐
│ Conversations  │ Active Conversation         │
│                │                             │
│ Search         │ Header                      │
│ Conversation 1 │ Message List                │
│ Conversation 2 │ Composer                    │
└────────────────┴─────────────────────────────┘

Mobile:
Conversation list screen
        ↓
Active conversation screen
```

---

# 39. Frontend API Client

Create:

```text
apps/web/src/lib/api-client.ts
```

```typescript
import axios from "axios";

export const apiClient = axios.create({
  baseURL:
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    "http://localhost:8000/api/v1",
  withCredentials: true,
});
```

Create:

```text
apps/web/.env.local
```

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8000/api/v1/ws
```

---

# 40. Frontend WebSocket Store

Create:

```text
apps/web/src/stores/websocket-store.ts
```

Suggested state:

```typescript
type ConnectionStatus =
  | "disconnected"
  | "connecting"
  | "connected"
  | "reconnecting";

type WebSocketState = {
  socket: WebSocket | null;
  status: ConnectionStatus;
  reconnectAttempts: number;
  connect: (token: string) => void;
  disconnect: () => void;
  sendEvent: (event: unknown) => void;
};
```

Recommended reconnect delays:

```text
1 second
2 seconds
4 seconds
8 seconds
15 seconds maximum
```

Add random jitter so many clients do not reconnect at the same instant.

---

# 41. Optimistic Message Design

Frontend temporary message:

```typescript
type OptimisticMessage = {
  id: string;
  clientMessageId: string;
  conversationId: string;
  content: string;
  status: "pending" | "sent" | "failed";
  createdAt: string;
};
```

Flow:

```text
Create clientMessageId
    ↓
Render pending message
    ↓
Send message.send event
    ↓
Receive message.created
    ↓
Match by clientMessageId
    ↓
Replace optimistic message with stored message
```

Never match messages only by content.

---

# 42. File Upload Flow

Do not send large binary files through WebSocket.

Recommended flow:

```text
Frontend requests signed upload URL
    ↓
Backend validates filename and content type
    ↓
Backend returns signed URL
    ↓
Frontend uploads directly to storage
    ↓
Frontend sends message with storage key
    ↓
Backend validates storage object
    ↓
Backend stores attachment metadata
```

Required validation:

- File size
- MIME type
- Extension
- Image dimensions
- Malware scanning
- Private storage bucket
- Time-limited download URL

---

# 43. API Endpoint Checklist

## Authentication

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
```

## Users

```text
GET   /api/v1/users/me
PATCH /api/v1/users/me
GET   /api/v1/users/search?q=
GET   /api/v1/users/{user_id}
```

## Conversations

```text
POST /api/v1/conversations/direct
POST /api/v1/conversations/group
GET  /api/v1/conversations
GET  /api/v1/conversations/{conversation_id}
POST /api/v1/conversations/{conversation_id}/members
DELETE /api/v1/conversations/{conversation_id}/members/{user_id}
```

## Messages

```text
GET    /api/v1/conversations/{conversation_id}/messages
POST   /api/v1/conversations/{conversation_id}/messages
PATCH  /api/v1/messages/{message_id}
DELETE /api/v1/messages/{message_id}
POST   /api/v1/messages/{message_id}/read
```

## Uploads

```text
POST /api/v1/uploads/presigned-url
POST /api/v1/uploads/complete
```

## WebSocket

```text
GET /api/v1/ws
```

---

# 44. Development Commands Cheat Sheet

## Start infrastructure

```bash
docker compose up -d
```

## Stop infrastructure

```bash
docker compose down
```

## Remove infrastructure data

```bash
docker compose down -v
```

## Run backend

```bash
cd apps/api
uv run uvicorn app.main:app --reload --port 8000
```

## Run frontend

```bash
cd apps/web
npm run dev
```

## Create migration

```bash
cd apps/api
uv run alembic revision --autogenerate -m "migration name"
```

## Apply migrations

```bash
uv run alembic upgrade head
```

## Run backend tests

```bash
uv run pytest -v
```

## Run lint

```bash
uv run ruff check .
```

## Auto-fix lint

```bash
uv run ruff check . --fix
```

## Format Python

```bash
uv run ruff format .
```

## Type check

```bash
uv run mypy app
```

## Frontend lint

```bash
npm run lint
```

## Frontend build test

```bash
npm run build
```

---

# 45. Recommended Makefile

Create:

```text
Makefile
```

```makefile
infra-up:
	docker compose up -d

infra-down:
	docker compose down

api:
	cd apps/api && uv run uvicorn app.main:app --reload --port 8000

web:
	cd apps/web && npm run dev

migrate:
	cd apps/api && uv run alembic upgrade head

migration:
	cd apps/api && uv run alembic revision --autogenerate -m "$(name)"

test:
	cd apps/api && uv run pytest -v

lint:
	cd apps/api && uv run ruff check .

format:
	cd apps/api && uv run ruff format .
```

Examples:

```bash
make infra-up
make migrate
make api
make web
make test
make migration name="add message receipts"
```

Windows users can run the underlying commands directly if `make` is unavailable.

---

# 46. Security Checklist

## Authentication

- [ ] Passwords hashed
- [ ] Access tokens expire quickly
- [ ] Refresh tokens rotated
- [ ] Refresh tokens revocable
- [ ] Login rate limited
- [ ] Password reset does not reveal whether user exists

## Authorization

- [ ] Every conversation request checks membership
- [ ] Every message request checks membership
- [ ] Sender ID comes from authentication
- [ ] Group admin operations check role
- [ ] Blocked users cannot contact each other

## WebSocket

- [ ] Connection authenticated
- [ ] Event payload validated
- [ ] Event size limited
- [ ] Rate limiting applied
- [ ] Unknown event types rejected
- [ ] Private events sent only to authorized users

## Uploads

- [ ] MIME type validated
- [ ] File extension validated
- [ ] Maximum size enforced
- [ ] Bucket is private
- [ ] Signed URLs expire
- [ ] Malware scanning planned

## Infrastructure

- [ ] HTTPS enabled
- [ ] WSS enabled
- [ ] Secrets outside Git
- [ ] Database backup enabled
- [ ] Restore process tested
- [ ] Redis not publicly exposed
- [ ] PostgreSQL not publicly exposed

---

# 47. Performance Checklist

- [ ] Cursor pagination used
- [ ] Message indexes created
- [ ] Conversation membership indexed
- [ ] Presence stored in Redis
- [ ] Typing events debounced
- [ ] Files uploaded directly to storage
- [ ] Message list virtualized
- [ ] Redis Pub/Sub used for multiple API instances
- [ ] Database connection pool configured
- [ ] Slow queries logged
- [ ] Image thumbnails generated
- [ ] Read receipt updates batched

---

# 48. Production Deployment Plan

Initial production architecture:

```text
Cloudflare
    ↓
Nginx
    ↓
┌─────────────────────────────────┐
│ Next.js                         │
│ FastAPI API                     │
│ FastAPI WebSocket worker        │
│ Background worker               │
│ PostgreSQL                      │
│ Redis                           │
│ Object storage                  │
└─────────────────────────────────┘
```

Recommended first deployment options:

### Option A — Simple VPS

- Ubuntu Server
- Docker Compose
- Nginx
- PostgreSQL container or managed PostgreSQL
- Redis container
- Cloudflare DNS and proxy

### Option B — Hybrid managed services

- Frontend: Vercel
- Backend: VPS / Render / Railway / Fly.io
- Database: Supabase PostgreSQL
- Storage: Supabase Storage
- Redis: Upstash or VPS Redis

For WebSocket reliability, a VPS or platform with stable long-lived connections is often simpler than heavily serverless backend hosting.

---

# 49. MVP Build Order

Complete features in this order:

```text
1. FastAPI health endpoint
2. PostgreSQL connection
3. Alembic migration
4. User registration
5. User login
6. Protected current-user endpoint
7. User search
8. Direct conversation creation
9. Conversation list
10. Message REST creation
11. Message history
12. WebSocket authentication
13. Real-time message event
14. Optimistic frontend messages
15. Reconnection
16. Read receipts
17. Typing status
18. Online presence
19. Attachments
20. Group chat
```

Do not start real-time messaging before normal database message creation works through REST.

---

# 50. Final Verification Checklist

## Backend foundation

- [ ] `/health` returns `200`
- [ ] PostgreSQL connection works
- [ ] Redis connection works
- [ ] Alembic upgrade works
- [ ] Configuration loads from `.env`

## Authentication

- [ ] User can register
- [ ] User can log in
- [ ] Password stored as hash
- [ ] Invalid token rejected
- [ ] Refresh token cannot access protected route

## Conversations

- [ ] User can create direct conversation
- [ ] Duplicate direct conversation prevented
- [ ] Non-member cannot read conversation
- [ ] Conversation list sorted by activity

## Messaging

- [ ] Member can send message
- [ ] Non-member cannot send
- [ ] Message survives restart
- [ ] Duplicate retry prevented
- [ ] Message history paginated
- [ ] Message ordering stable

## WebSocket

- [ ] Valid user connects
- [ ] Invalid user rejected
- [ ] Recipient receives message without refreshing
- [ ] Reconnection works
- [ ] Dead sockets removed
- [ ] Multiple devices supported

## Security

- [ ] Sender ID derived from token
- [ ] Membership checked on every action
- [ ] Event size limited
- [ ] Inputs validated
- [ ] Secrets excluded from source control
- [ ] Private messages excluded from logs

## Deployment

- [ ] Docker images build
- [ ] Environment variables documented
- [ ] Migrations run before app startup
- [ ] Health checks configured
- [ ] Backups configured
- [ ] Rollback procedure documented

---

# 51. Recommended Next Exercise

Start with these three files:

```text
apps/api/app/core/config.py
apps/api/app/db/session.py
apps/api/app/models/user.py
```

Then run:

```bash
docker compose up -d
cd apps/api
uv run alembic revision --autogenerate -m "create users table"
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Your first milestone is complete when:

```text
GET /health
```

returns:

```json
{
  "status": "ok"
}
```

and the `users` table exists in PostgreSQL.
