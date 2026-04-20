from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import List,  Optional

from app.schemas.paragraph import ParagraphResult, ElementResponse


class PaperResponse(BaseModel):
    id: int
    title: str | None
    original_filename: str
    stored_file_path: str
    parse_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaperListItemResponse(BaseModel):
    paper_id: int
    title: str | None
    original_filename: str
    parse_status: str
    zh_translation_status: str
    zh_translation_started_at: str | None = None
    zh_translation_finished_at: str | None = None


class PaperDetailResponse(BaseModel):
    paper_id: int
    title: str | None
    original_filename: str
    parse_status: str
    zh_translation_status: str
    zh_translation_started_at: str | None = None
    zh_translation_finished_at: str | None = None
    pdf_url: str
    elements: List[ElementResponse]


class PaperProcessResponse(BaseModel):
    paper_id: int
    original_filename: str
    stored_file_path: str
    parse_status: str
    paragraphs: list[ParagraphResult]


class UploadResponse(BaseModel):
    paper_id: int
    title: str | None
    original_filename: str
    parse_status: str
    pdf_url: str
    elements: List[ElementResponse]


class HighlightSummaryResponse(BaseModel):
    element_id: int
    title: str
    summary: str


class SectionSummaryResponse(BaseModel):
    section_key: Optional[str] = None
    section_title: str
    summary: str


class PaperOverviewResponse(BaseModel):
    paper_id: int
    language: str
    abstract_summary: str
    overall_summary: str
    overall_key_points: List[str]
    highlight_element_ids: List[int]
    highlight_summaries: List[HighlightSummaryResponse]
    section_summaries: List[SectionSummaryResponse]