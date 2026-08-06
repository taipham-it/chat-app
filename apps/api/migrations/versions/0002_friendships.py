"""add friendships"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_friendships"
down_revision: str | None = "0001_chat_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)
    op.create_table(
        "friendships",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("user_low_id", uuid_type, nullable=False),
        sa.Column("user_high_id", uuid_type, nullable=False),
        sa.Column("requested_by_id", uuid_type, nullable=False),
        sa.Column("status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("user_low_id <> user_high_id", name="ck_friendship_distinct_users"),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_high_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_low_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_low_id", "user_high_id", name="uq_friendship_user_pair"),
    )
    op.create_index("ix_friendships_user_high_id", "friendships", ["user_high_id"])
    op.create_index("ix_friendships_user_low_id", "friendships", ["user_low_id"])


def downgrade() -> None:
    op.drop_table("friendships")

