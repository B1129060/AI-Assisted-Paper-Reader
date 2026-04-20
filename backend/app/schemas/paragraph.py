from pydantic import BaseModel, Field
from typing import Literal, List, Optional


class PdfLocation(BaseModel):
    page: int
    bbox: List[float]


class ParagraphResult(BaseModel):
    global_paragraph_index: int
    chunk_index: int
    paragraph_index_within_chunk: int
    section_title: str

    type: Literal["heading", "paragraph", "bullet_list"]

    # common
    text: Optional[str] = None

    # heading
    level: Optional[str] = None

    # paragraph / list
    summary: Optional[str] = None
    key_points: Optional[List[str]] = None

    # list only
    intro_text: Optional[str] = None
    items: Optional[List[str]] = None

    # PDF 定位資訊
    page_number: Optional[int] = None
    pdf_rects: List[List[float]] = Field(default_factory=list)

    # 新格式：每個 rect 自帶 page
    pdf_locations: List[PdfLocation] = Field(default_factory=list)


class ElementResponse(BaseModel):
    id: int
    paragraph_id: int
    type: Literal["heading", "paragraph", "bullet_list"]

    text: Optional[str] = None
    summary: Optional[str] = None
    key_points: Optional[List[str]] = None

    level: Optional[str] = None
    intro_text: Optional[str] = None
    items: Optional[List[str]] = None

    # PDF 定位資訊
    page_number: Optional[int] = None
    pdf_rects: List[List[float]] = Field(default_factory=list)

    # 新格式：每個 rect 自帶 page
    pdf_locations: List[PdfLocation] = Field(default_factory=list)

    match_confidence: Optional[str] = None