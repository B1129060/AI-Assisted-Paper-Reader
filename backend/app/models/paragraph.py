from sqlalchemy import Column, Integer, String, Text, ForeignKey
from app.database import Base


class Paragraph(Base):
    __tablename__ = "paragraphs"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True)

    paragraph_index = Column(Integer, nullable=False)

    # 原有相容欄位
    content = Column(Text, nullable=False)

    # 顯示結構
    type = Column(String, nullable=True)         # heading / paragraph / bullet_list
    section_title = Column(Text, nullable=True)  # 這段屬於哪個主 section
    text = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    key_points = Column(Text, nullable=True)     # JSON string
    level = Column(String, nullable=True)        # section / subsection
    intro_text = Column(Text, nullable=True)
    items = Column(Text, nullable=True)          # JSON string

    # 中文欄位
    text_zh = Column(Text, nullable=True)
    summary_zh = Column(Text, nullable=True)
    key_points_zh = Column(Text, nullable=True)  # JSON string
    items_zh = Column(Text, nullable=True)       # JSON string

    # ⭐ PDF 定位欄位（新加）
    page_number = Column(Integer, nullable=True)
    pdf_rects = Column(Text, nullable=True)      # JSON string
    pdf_locations = Column(Text, nullable=True)