"""create major_topic & major_topic_embedding, add category to mail_embeddings

Revision ID: 2e7fbc5d9f0b
Revises: cf3be5d7a091
Create Date: 2025-06-03 16:05:14.481768

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2e7fbc5d9f0b"
down_revision: Union[str, None] = "cf3be5d7a091"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # major_topic 테이블 생성
    op.create_table(
        "major_topic",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
    )

    # major_topic_embedding 테이블 생성
    op.create_table(
        "major_topic_embedding",
        sa.Column(
            "topic_id",
            sa.Integer(),
            sa.ForeignKey("major_topic.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("vector", sa.ARRAY(sa.Float()), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # mail_embeddings 테이블에 category 컬럼 추가
    op.add_column("mail_embeddings", sa.Column("category", sa.Integer(), nullable=True))

    # 외래키 제약 추가: mail_embeddings.category → major_topic.id
    op.create_foreign_key(
        "fk_mail_category",
        "mail_embeddings",
        "major_topic",
        local_cols=["category"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )


def downgrade():
    # mail_embeddings.category 외래키 제약 제거, 컬럼 제거
    op.drop_constraint("fk_mail_category", "mail_embeddings", type_="foreignkey")
    op.drop_column("mail_embeddings", "category")

    # major_topic_embedding 테이블 제거
    op.drop_table("major_topic_embedding")

    # major_topic 테이블 제거
    op.drop_table("major_topic")
