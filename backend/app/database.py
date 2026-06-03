# SQLAlchemy engine, session factory, declarative base, and request-scoped DB dependency.

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Yield one SQLAlchemy session per dependency call and always close it.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()