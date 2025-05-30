import datetime, enum
from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    Integer,
    DateTime,
    Float,
    UUID,
    JSON,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import UUID as PGUUID, ARRAY, TIMESTAMP
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


class MailActionType(enum.Enum):
    delete = "delete"
    archive = "archive"
    spam = "spam"


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
    carbon_factor = Column(Float, default=0.00002)
    carbon_saved_grams = Column(Float, default=0)
    processed_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)


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


class UserCredentials(Base):
    __tablename__ = "user_credentials"
    user_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    expiry = Column(DateTime, nullable=False)
    scopes = Column(JSON, nullable=False, server_default="[]")
