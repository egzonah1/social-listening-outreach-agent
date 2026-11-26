"""add posts_drafted to search runs

Revision ID: 9c1d2e7f4a10
Revises: 4843768b3e39
Create Date: 2026-11-26 19:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c1d2e7f4a10"
down_revision: str | Sequence[str] | None = "4843768b3e39"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "search_runs", sa.Column("posts_drafted", sa.Integer(), server_default="0", nullable=False)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("search_runs", "posts_drafted")
