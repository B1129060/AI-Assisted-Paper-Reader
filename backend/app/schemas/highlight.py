from pydantic import BaseModel, Field
from typing import List, Optional


class TextHighlightCreateRequest(BaseModel):
    paper_id: int
    paragraph_id: Optional[int] = None
    scope: str
    field_name: str
    item_index: Optional[int] = None
    language: str = Field(..., pattern="^(en|zh)$")
    start_offset: int
    end_offset: int
    color: str


class TextHighlightResponse(BaseModel):
    id: int
    paper_id: int
    paragraph_id: Optional[int]
    scope: str
    field_name: str
    item_index: Optional[int]
    language: str
    start_offset: int
    end_offset: int
    color: str


class PdfHighlightCreateRequest(BaseModel):
    paper_id: int
    paragraph_id: Optional[int] = None
    page_number: int
    rects: List[List[float]]
    color: str


class PdfHighlightResponse(BaseModel):
    id: int
    paper_id: int
    paragraph_id: Optional[int]
    page_number: int
    rects: List[List[float]]
    color: str


class PaperHighlightsResponse(BaseModel):
    text_highlights: List[TextHighlightResponse]
    pdf_highlights: List[PdfHighlightResponse]