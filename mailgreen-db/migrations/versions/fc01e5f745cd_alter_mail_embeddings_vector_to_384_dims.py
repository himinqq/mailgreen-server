"""alter mail_embeddings.vector to 384 dims

Revision ID: fc01e5f745cd
Revises: c1b624571f02
Create Date: 2025-05-24 03:08:29.566164

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fc01e5f745cd'
down_revision: Union[str, None] = 'c1b624571f02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
