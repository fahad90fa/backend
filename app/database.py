from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from app.config import get_settings
from app.models import Base
import os
import logging

logger = logging.getLogger(__name__)

settings = get_settings()

connect_args = {}
if "sqlite" in settings.DATABASE_URL:
    connect_args = {"check_same_thread": False}
elif "postgresql" in settings.DATABASE_URL or "postgres" in settings.DATABASE_URL:
    connect_args = {"sslmode": "require"} if "vercel" in os.environ.get("VERCEL", "") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info(f"Database initialized successfully with {settings.DATABASE_URL.split('@')[0]}...")
        
        if "sqlite" in settings.DATABASE_URL:
            @event.listens_for(engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        if settings.ENVIRONMENT == "production":
            logger.error(f"DATABASE_URL scheme: {settings.DATABASE_URL.split('://')[0] if '://' in settings.DATABASE_URL else 'unknown'}")
        raise
