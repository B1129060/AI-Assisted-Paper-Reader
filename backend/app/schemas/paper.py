# Pydantic schemas for paper list, detail, upload, processing, and overview payloads.

from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import List, Optional

from app.schemas.paragraph import ParagraphResult, ElementResponse


# Full ORM-backed paper response payload.
class PaperResponse(BaseModel):
    id: int
    title: str | None
    original_filename: str
    stored_file_path: str
    parse_status: str
    parse_error: str | None = None
    parse_started_at: str | None = None
    parse_finished_at: str | None = None
    overview_status: str
    overview_error: str | None = None
    overview_started_at: str | None = None
    overview_finished_at: str | None = None
    zh_translation_status: str
    zh_translation_error: str | None = None
    export_status: str
    export_error: str | None = None
    export_started_at: str | None = None
    export_finished_at: str | None = None
    last_error_message: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Compact paper row used by the home page list.
class PaperListItemResponse(BaseModel):
    paper_id: int
    title: str | None
    original_filename: str
    parse_status: str
    parse_error: str | None = None
    parse_started_at: str | None = None
    parse_finished_at: str | None = None
    overview_status: str
    overview_error: str | None = None
    overview_started_at: str | None = None
    overview_finished_at: str | None = None
    zh_translation_status: str
    zh_translation_error: str | None = None
    zh_translation_started_at: str | None = None
    zh_translation_finished_at: str | None = None
    export_status: str
    export_error: str | None = None
    export_started_at: str | None = None
    export_finished_at: str | None = None
    last_error_message: str | None = None


# Reader-page paper detail payload with structured elements.
class PaperDetailResponse(BaseModel):
    paper_id: int
    title: str | None
    original_filename: str
    parse_status: str
    parse_error: str | None = None
    parse_started_at: str | None = None
    parse_finished_at: str | None = None
    overview_status: str
    overview_error: str | None = None
    overview_started_at: str | None = None
    overview_finished_at: str | None = None
    zh_translation_status: str
    zh_translation_error: str | None = None
    zh_translation_started_at: str | None = None
    zh_translation_finished_at: str | None = None
    export_status: str
    export_error: str | None = None
    export_started_at: str | None = None
    export_finished_at: str | None = None
    last_error_message: str | None = None
    pdf_url: str
    elements: List[ElementResponse]


# Legacy processing response shape kept for compatibility.
class PaperProcessResponse(BaseModel):
    paper_id: int
    original_filename: str
    stored_file_path: str
    parse_status: str
    parse_error: str | None = None
    parse_started_at: str | None = None
    parse_finished_at: str | None = None
    overview_status: str
    overview_error: str | None = None
    paragraphs: list[ParagraphResult]


# Upload response shape returned after queueing parse work.
class UploadResponse(BaseModel):
    paper_id: int
    title: str | None
    original_filename: str
    parse_status: str
    parse_error: str | None = None
    parse_started_at: str | None = None
    parse_finished_at: str | None = None
    overview_status: str
    overview_error: str | None = None
    overview_started_at: str | None = None
    overview_finished_at: str | None = None
    zh_translation_status: str | None = None
    zh_translation_error: str | None = None
    export_status: str | None = None
    export_error: str | None = None
    export_started_at: str | None = None
    export_finished_at: str | None = None
    last_error_message: str | None = None
    pdf_url: str
    elements: List[ElementResponse]


# Paper schema highlight summary item.
class HighlightSummaryResponse(BaseModel):
    element_id: int
    title: str
    summary: str


# Paper schema section summary item.
class SectionSummaryResponse(BaseModel):
    section_key: Optional[str] = None
    section_title: str
    summary: str


# Paper overview response returned by overview endpoints.
class PaperOverviewResponse(BaseModel):
    paper_id: int
    language: str
    abstract_summary: str
    overall_summary: str
    overall_key_points: List[str]
    highlight_element_ids: List[int]
    highlight_summaries: List[HighlightSummaryResponse]
    section_summaries: List[SectionSummaryResponse]
