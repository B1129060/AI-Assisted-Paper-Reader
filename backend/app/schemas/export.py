# Pydantic request schema for export/download options.

from pydantic import BaseModel
from typing import Literal


# Request options controlling which export files and highlights are included.
class ExportOptions(BaseModel):
    include_pdf: bool = True
    include_overview: bool = True
    include_paragraphs: bool = True

    language_mode: Literal["en", "zh", "both"] = "both"

    include_pdf_highlights: bool = True
    include_text_highlights: bool = True