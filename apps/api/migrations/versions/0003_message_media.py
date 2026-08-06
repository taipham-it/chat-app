"""add message media metadata"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_message_media"
down_revision: str | None = "0002_friendships"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("media_object_key", sa.String(512), nullable=True))
    op.add_column("messages", sa.Column("media_filename", sa.String(255), nullable=True))
    op.add_column("messages", sa.Column("media_content_type", sa.String(127), nullable=True))
    op.add_column("messages", sa.Column("media_size", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "media_size")
    op.drop_column("messages", "media_content_type")
    op.drop_column("messages", "media_filename")
    op.drop_column("messages", "media_object_key")
