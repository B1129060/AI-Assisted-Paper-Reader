# Pydantic request/response schemas for paragraph edit operations.

from pydantic import BaseModel
from typing import List


# Request body for replacing paragraph text.
class ParagraphUpdateRequest(BaseModel):
    text: str


# Request body for replacing a bullet-list element.
class BulletListUpdateRequest(BaseModel):
    intro_text: str | None = None
    items: List[str]


# Request body for inserting a paragraph after an existing element.
class ParagraphInsertRequest(BaseModel):
    text: str


# Common response for paragraph edit operations.
class ParagraphUpdateResponse(BaseModel):
    paragraph_id: int
    paper_id: int
    section_title: str | None
    status: str