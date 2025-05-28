from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from mailgreen.app.config import Config
from mailgreen.app.models import Base

engine = create_engine(
    Config.DATABASE_URL,
    echo=False,
    future=True,
    poolclass=NullPool,  # Celery + FastAPI 병행 시 커넥션 풀 deadlock 예방용
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
