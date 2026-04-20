from pydantic import BaseModel
from typing import List


class HighlightSummary(BaseModel):
    element_id: int
    title: str
    summary: str


class SectionSummary(BaseModel):
    section_title: str
    summary: str


class PaperOverviewResponse(BaseModel):
    paper_id: int
    language: str
    abstract_summary: str
    overall_summary: str
    overall_key_points: List[str]
    highlight_element_ids: List[int]
    highlight_summaries: List[HighlightSummary]
    section_summaries: List[SectionSummary]