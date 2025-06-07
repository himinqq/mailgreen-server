"""create_user_protected_sender

Revision ID: c0a447889f9f
Revises: 2e7fbc5d9f0b
Create Date: 2025-06-06 19:16:02.713792

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c0a447889f9f"
down_revision: Union[str, None] = "2e7fbc5d9f0b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "user_protected_sender",
        sa.Column(
            "user_id", sa.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("sender_email", sa.String(length=320), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "sender_email"),
    )


def downgrade():
    op.drop_table("user_protected_sender")
