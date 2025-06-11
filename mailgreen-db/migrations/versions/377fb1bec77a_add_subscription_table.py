"""add subscription table

Revision ID: 377fb1bec77a
Revises: c0a447889f9f
Create Date: 2025-06-08 19:56:32.352625

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "377fb1bec77a"
down_revision: Union[str, None] = "c0a447889f9f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("sender", sa.String(length=320), nullable=False),
        sa.Column("unsubscribe_link", sa.Text(), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
    )
    # (원하면) 인덱스 추가
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])


def downgrade():
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")
