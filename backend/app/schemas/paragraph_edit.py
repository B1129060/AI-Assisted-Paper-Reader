from pydantic import BaseModel
from typing import List


class ParagraphUpdateRequest(BaseModel):
    text: str


class BulletListUpdateRequest(BaseModel):
    intro_text: str | None = None
    items: List[str]


class ParagraphInsertRequest(BaseModel):
    text: str


class ParagraphUpdateResponse(BaseModel):
    paragraph_id: int
    paper_id: int
    section_title: str | None
    status: str