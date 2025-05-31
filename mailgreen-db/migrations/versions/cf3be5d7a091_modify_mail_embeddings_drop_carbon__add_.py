"""modify mail_embeddings: drop carbon_*, add is_deleted & deleted_at

Revision ID: cf3be5d7a091
Revises: 311ee75c0e9f
Create Date: 2025-05-31 17:26:03.700500

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "cf3be5d7a091"
down_revision: Union[str, None] = "311ee75c0e9f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # carbon_factor, carbon_saved_grams 컬럼 제거
    op.drop_column("mail_embeddings", "carbon_factor")
    op.drop_column("mail_embeddings", "carbon_saved_grams")

    # is_deleted, deleted_at 컬럼 추가
    op.add_column(
        "mail_embeddings",
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column(
        "mail_embeddings",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # is_deleted 인덱스 생성
    op.create_index(
        "ix_mail_embeddings_is_deleted",
        "mail_embeddings",
        ["is_deleted"],
    )


def downgrade():
    # 롤백 시, 추가했던 것들을 역순으로 제거/복원
    op.drop_index("ix_mail_embeddings_is_deleted", table_name="mail_embeddings")
    op.drop_column("mail_embeddings", "deleted_at")
    op.drop_column("mail_embeddings", "is_deleted")

    # carbon_factor, carbon_saved_grams 컬럼 다시 추가
    op.add_column(
        "mail_embeddings",
        sa.Column(
            "carbon_saved_grams",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "mail_embeddings",
        sa.Column(
            "carbon_factor",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.00002"),
        ),
    )
