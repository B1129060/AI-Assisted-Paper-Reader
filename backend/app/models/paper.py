# Database model for uploaded papers and their processing/export status fields.

from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


# Uploaded paper row with processing, translation, export, and ownership metadata.
class Paper(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=True)
    original_filename = Column(String, nullable=False)
    stored_file_path = Column(String, nullable=False)

    # PDF parse / paragraph build status.
    # expected values: uploaded | queued | processing | processed | failed
    parse_status = Column(String, nullable=False, default="uploaded")
    parse_error = Column(Text, nullable=True)
    parse_started_at = Column(DateTime(timezone=True), nullable=True)
    parse_finished_at = Column(DateTime(timezone=True), nullable=True)

    # Overview generation / regeneration status.
    # expected values: not_started | queued | processing | completed | failed
    overview_status = Column(String, nullable=False, default="not_started")
    overview_error = Column(Text, nullable=True)
    overview_started_at = Column(DateTime(timezone=True), nullable=True)
    overview_finished_at = Column(DateTime(timezone=True), nullable=True)

    # Chinese translation status.
    # expected values: not_started | queued | processing | completed | failed
    zh_translation_status = Column(String, nullable=False, default="not_started")
    zh_translation_error = Column(Text, nullable=True)
    zh_translation_started_at = Column(DateTime(timezone=True), nullable=True)
    zh_translation_finished_at = Column(DateTime(timezone=True), nullable=True)

    # Export status is currently updated for immediate exports; later it can be
    # reused by a background export task.
    # expected values: not_started | queued | processing | completed | failed
    export_status = Column(String, nullable=False, default="not_started")
    export_error = Column(Text, nullable=True)
    export_started_at = Column(DateTime(timezone=True), nullable=True)
    export_finished_at = Column(DateTime(timezone=True), nullable=True)

    # Short, user-facing latest failure reason for HomePage / ReaderPage display.
    last_error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="papers")
