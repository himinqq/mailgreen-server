import datetime, enum
from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    Integer,
    DateTime,
    UUID,
    Index,
    Float,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID, ARRAY, TIMESTAMP, JSONB
from pgvector.sqlalchemy import Vector
from uuid import uuid4

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    google_sub = Column(String(128), unique=True, nullable=False)
    email = Column(String(320), nullable=False)
    name = Column(String(100))
    picture_url = Column(Text)
    created_at = Column(TIMESTAMP, default=datetime.datetime.utcnow)


class UserCredentials(Base):
    __tablename__ = "user_credentials"
    user_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    expiry = Column(DateTime, nullable=False)


class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False)
    task_type = Column(String(50))
    status = Column(String(20))
    progress_pct = Column(Integer)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True), nullable=True)
    error_msg = Column(Text, nullable=True)
    history_id = Column(Text, nullable=True)


class MajorTopic(Base):
    __tablename__ = "major_topic"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)
    description = Column(Text, nullable=True)

    mails = relationship("MailEmbedding", back_populates="topic")
    embedding = relationship(
        "MajorTopicEmbedding", back_populates="topic", uselist=False
    )


class MailEmbedding(Base):
    __tablename__ = "mail_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), nullable=False)
    gmail_msg_id = Column(String(32), unique=True, nullable=False)
    thread_id = Column(String(32))
    sender = Column(String(320))
    subject = Column(Text)
    snippet = Column(Text)
    labels = Column(ARRAY(Text))
    size_bytes = Column(Integer)
    is_read = Column(Boolean)
    is_starred = Column(Boolean)
    received_at = Column(DateTime(timezone=True))
    vector = Column(Vector(384))
    keywords = Column(ARRAY(Text))
    processed_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

    # Soft-Delete
    is_deleted = Column(Boolean, nullable=False, server_default="false")
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    category = Column(
        Integer,
        ForeignKey("major_topic.id", ondelete="SET NULL"),
        nullable=True,
    )

    topic = relationship("MajorTopic", back_populates="mails")

    # is_deleted 컬럼 인덱스 > 삭제되지 않은 레코드 빠르게 조회
    __table_args__ = (Index("ix_mail_embeddings_is_deleted", "is_deleted"),)


class MajorTopicEmbedding(Base):
    __tablename__ = "major_topic_embedding"

    topic_id = Column(
        Integer,
        ForeignKey("major_topic.id", ondelete="CASCADE"),
        primary_key=True,
    )
    vector = Column(ARRAY(Float), nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default="NOW()"
    )

    topic = relationship("MajorTopic", back_populates="embedding")


MajorTopic.embedding = relationship(
    "MajorTopicEmbedding", back_populates="topic", uselist=False
)


class UserProtectedSender(Base):
    __tablename__ = "user_protected_sender"

    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    sender_email = Column(String(320), primary_key=True)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    sender = Column(String(320), nullable=False)
    unsubscribe_link = Column(Text, nullable=False)  # 기존 unsubscribe_method
    is_active = Column(Boolean, default=True)
