from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

from app.database import Base


class Paper(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True)
    original_filename = Column(String, nullable=False)
    stored_file_path = Column(String, nullable=False)
    parse_status = Column(String, nullable=False, default="uploaded")

    zh_translation_status = Column(String, nullable=False, default="not_started")
    zh_translation_started_at = Column(DateTime(timezone=True), nullable=True)
    zh_translation_finished_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())