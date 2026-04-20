from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.sql import func

from app.database import Base


class TextHighlight(Base):
    __tablename__ = "text_highlights"

    id = Column(Integer, primary_key=True, index=True)

    paper_id = Column(
        Integer,
        ForeignKey("papers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    paragraph_id = Column(
        Integer,
        ForeignKey("paragraphs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # "paragraph" | "overview"
    scope = Column(String, nullable=False)

    # paragraph: text / summary / key_points / intro_text / item
    # overview: abstract_summary / overall_summary / overall_key_points / section_summary / highlight_summary
    field_name = Column(String, nullable=False)

    # 如果是 key_points[i] / items[i] / overall_key_points[i] / section_summaries[i]
    item_index = Column(Integer, nullable=True)

    # en | zh
    language = Column(String, nullable=False, default="en")

    start_offset = Column(Integer, nullable=False)
    end_offset = Column(Integer, nullable=False)

    # yellow | green | pink
    color = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class PdfHighlight(Base):
    __tablename__ = "pdf_highlights"

    id = Column(Integer, primary_key=True, index=True)

    paper_id = Column(
        Integer,
        ForeignKey("papers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 先保留可空，之後若想讓刪段落時一起刪 PDF highlight，可用這個欄位
    paragraph_id = Column(
        Integer,
        ForeignKey("paragraphs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    page_number = Column(Integer, nullable=False)

    # JSON string: [[x0,y0,x1,y1], ...]
    rects_json = Column(Text, nullable=False)

    color = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )