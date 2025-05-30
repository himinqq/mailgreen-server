"""add history_id to analysis_tasks

Revision ID: 311ee75c0e9f
Revises: 0b2bfefc3e48
Create Date: 2025-05-30 12:07:06.085581

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "311ee75c0e9f"
down_revision: Union[str, None] = "0b2bfefc3e48"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # analysis_tasks 테이블에 history_id(TEXT) 컬럼 추가
    op.add_column("analysis_tasks", sa.Column("history_id", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("analysis_tasks", "history_id")
