from sqlalchemy import Column, Integer, ForeignKey, Text, String, DateTime
from sqlalchemy.sql import func

from app.database import Base


class PaperOverview(Base):
    __tablename__ = "paper_overviews"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(
        Integer,
        ForeignKey("papers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )

    language = Column(String, nullable=False, default="en")

    # 英文
    abstract_summary = Column(Text, nullable=False, default="")
    overall_summary = Column(Text, nullable=False)
    overall_key_points = Column(Text, nullable=False)      # JSON string
    highlight_element_ids = Column(Text, nullable=False)   # JSON string
    highlight_summaries = Column(Text, nullable=False)     # JSON string
    section_summaries = Column(Text, nullable=False)       # JSON string

    # 中文
    abstract_summary_zh = Column(Text, nullable=True)
    overall_summary_zh = Column(Text, nullable=True)
    overall_key_points_zh = Column(Text, nullable=True)    # JSON string
    highlight_summaries_zh = Column(Text, nullable=True)   # JSON string
    section_summaries_zh = Column(Text, nullable=True)     # JSON string

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )