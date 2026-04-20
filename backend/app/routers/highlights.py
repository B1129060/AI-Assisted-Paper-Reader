import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.highlight import TextHighlight, PdfHighlight
from app.schemas.highlight import (
    TextHighlightCreateRequest,
    TextHighlightResponse,
    PdfHighlightCreateRequest,
    PdfHighlightResponse,
    PaperHighlightsResponse,
)

router = APIRouter(tags=["Highlights"])


@router.get("/papers/{paper_id}/highlights", response_model=PaperHighlightsResponse)
def get_paper_highlights(
    paper_id: int,
    language: str = Query("en", pattern="^(en|zh)$"),
    db: Session = Depends(get_db),
):
    text_rows = (
        db.query(TextHighlight)
        .filter(
            TextHighlight.paper_id == paper_id,
            TextHighlight.language == language,
        )
        .all()
    )

    pdf_rows = (
        db.query(PdfHighlight)
        .filter(PdfHighlight.paper_id == paper_id)
        .all()
    )

    text_highlights = [
        {
            "id": row.id,
            "paper_id": row.paper_id,
            "paragraph_id": row.paragraph_id,
            "scope": row.scope,
            "field_name": row.field_name,
            "item_index": row.item_index,
            "language": row.language,
            "start_offset": row.start_offset,
            "end_offset": row.end_offset,
            "color": row.color,
        }
        for row in text_rows
    ]

    pdf_highlights = []
    for row in pdf_rows:
        try:
            rects = json.loads(row.rects_json) if row.rects_json else []
        except Exception:
            rects = []

        pdf_highlights.append({
            "id": row.id,
            "paper_id": row.paper_id,
            "paragraph_id": row.paragraph_id,
            "page_number": row.page_number,
            "rects": rects,
            "color": row.color,
        })

    return {
        "text_highlights": text_highlights,
        "pdf_highlights": pdf_highlights,
    }


@router.post("/highlights/text", response_model=TextHighlightResponse)
def create_text_highlight(
    payload: TextHighlightCreateRequest,
    db: Session = Depends(get_db),
):
    if payload.start_offset < 0 or payload.end_offset <= payload.start_offset:
        raise HTTPException(status_code=400, detail="Invalid text highlight range.")

    row = TextHighlight(
        paper_id=payload.paper_id,
        paragraph_id=payload.paragraph_id,
        scope=payload.scope,
        field_name=payload.field_name,
        item_index=payload.item_index,
        language=payload.language,
        start_offset=payload.start_offset,
        end_offset=payload.end_offset,
        color=payload.color,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "id": row.id,
        "paper_id": row.paper_id,
        "paragraph_id": row.paragraph_id,
        "scope": row.scope,
        "field_name": row.field_name,
        "item_index": row.item_index,
        "language": row.language,
        "start_offset": row.start_offset,
        "end_offset": row.end_offset,
        "color": row.color,
    }


@router.delete("/highlights/text/{highlight_id}")
def delete_text_highlight(
    highlight_id: int,
    db: Session = Depends(get_db),
):
    row = db.query(TextHighlight).filter(TextHighlight.id == highlight_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Text highlight not found.")

    db.delete(row)
    db.commit()
    return {"status": "deleted", "highlight_id": highlight_id}


@router.post("/highlights/pdf", response_model=PdfHighlightResponse)
def create_pdf_highlight(
    payload: PdfHighlightCreateRequest,
    db: Session = Depends(get_db),
):
    if not payload.rects:
        raise HTTPException(status_code=400, detail="rects cannot be empty.")

    row = PdfHighlight(
        paper_id=payload.paper_id,
        paragraph_id=payload.paragraph_id,
        page_number=payload.page_number,
        rects_json=json.dumps(payload.rects, ensure_ascii=False),
        color=payload.color,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "id": row.id,
        "paper_id": row.paper_id,
        "paragraph_id": row.paragraph_id,
        "page_number": row.page_number,
        "rects": payload.rects,
        "color": row.color,
    }


@router.delete("/highlights/pdf/{highlight_id}")
def delete_pdf_highlight(
    highlight_id: int,
    db: Session = Depends(get_db),
):
    row = db.query(PdfHighlight).filter(PdfHighlight.id == highlight_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="PDF highlight not found.")

    db.delete(row)
    db.commit()
    return {"status": "deleted", "highlight_id": highlight_id}