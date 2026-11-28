"""add blocked_authors (do-not-contact list)

Revision ID: b7e3a91c5d24
Revises: 9c1d2e7f4a10
Create Date: 2026-11-28 09:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e3a91c5d24"
down_revision: str | Sequence[str] | None = "9c1d2e7f4a10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "blocked_authors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "platform",
            sa.Enum("bluesky", "mastodon", "sample", name="platform", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("author_handle", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blocked_authors")),
        sa.UniqueConstraint(
            "platform", "author_handle", name=op.f("uq_blocked_authors_platform_author_handle")
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("blocked_authors")
