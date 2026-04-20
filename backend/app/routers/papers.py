import os
from pathlib import Path
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.paper import Paper
from app.models.paragraph import Paragraph
from app.schemas.paper import PaperListItemResponse, PaperDetailResponse
from app.config import settings

router = APIRouter(prefix="/papers", tags=["Papers"])


@router.get("/", response_model=list[PaperListItemResponse])
def list_papers(db: Session = Depends(get_db)):
    papers = db.query(Paper).order_by(Paper.id.desc()).all()

    return [
        {
            "paper_id": p.id,
            "title": p.title,
            "original_filename": p.original_filename,
            "parse_status": p.parse_status,
            "zh_translation_status": p.zh_translation_status,
            "zh_translation_started_at": p.zh_translation_started_at.isoformat() if p.zh_translation_started_at else None,
            "zh_translation_finished_at": p.zh_translation_finished_at.isoformat() if p.zh_translation_finished_at else None,
        }
        for p in papers
    ]


@router.get("/{paper_id}", response_model=PaperDetailResponse)
def get_paper_detail(
    paper_id: int,
    lang: str = Query("en", pattern="^(en|zh)$"),
    db: Session = Depends(get_db),
):
    paper = db.query(Paper).filter(Paper.id == paper_id).first()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found.")

    paragraphs = (
        db.query(Paragraph)
        .filter(Paragraph.paper_id == paper_id)
        .order_by(Paragraph.paragraph_index.asc())
        .all()
    )

    pdf_filename = Path(paper.stored_file_path).name if paper.stored_file_path else ""
    elements = []

    paragraph_has_pdf_locations = hasattr(Paragraph, "pdf_locations")

    for p in paragraphs:
        el_type = p.type or "paragraph"

        if lang == "zh":
            text = p.text_zh or p.text
            summary = p.summary_zh or p.summary
            key_points_raw = p.key_points_zh or p.key_points
            items_raw = p.items_zh or p.items
        else:
            text = p.text
            summary = p.summary
            key_points_raw = p.key_points
            items_raw = p.items

        try:
            key_points = json.loads(key_points_raw) if key_points_raw else None
        except Exception:
            key_points = None

        try:
            items = json.loads(items_raw) if items_raw else None
        except Exception:
            items = None

        try:
            pdf_rects = json.loads(p.pdf_rects) if p.pdf_rects else []
        except Exception:
            pdf_rects = []

        pdf_locations = []
        if paragraph_has_pdf_locations:
            try:
                raw_pdf_locations = getattr(p, "pdf_locations", None)
                pdf_locations = json.loads(raw_pdf_locations) if raw_pdf_locations else []
            except Exception:
                pdf_locations = []

        elements.append({
            "id": p.paragraph_index,
            "paragraph_id": p.id,
            "type": el_type,
            "text": text,
            "summary": summary,
            "key_points": key_points,
            "level": p.level,
            "intro_text": p.intro_text,
            "items": items,
            "page_number": p.page_number,
            "pdf_rects": pdf_rects,
            "pdf_locations": pdf_locations,
        })

    return {
        "paper_id": paper.id,
        "title": paper.title or paper.original_filename,
        "original_filename": paper.original_filename,
        "parse_status": paper.parse_status,
        "zh_translation_status": paper.zh_translation_status,
        "zh_translation_started_at": paper.zh_translation_started_at.isoformat() if paper.zh_translation_started_at else None,
        "zh_translation_finished_at": paper.zh_translation_finished_at.isoformat() if paper.zh_translation_finished_at else None,
        "pdf_url": f"/uploads/{pdf_filename}" if pdf_filename else "",
        "elements": elements,
    }


@router.delete("/{paper_id}")
def delete_paper(paper_id: int, db: Session = Depends(get_db)):
    paper = db.query(Paper).filter(Paper.id == paper_id).first()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found.")

    stored_file_path = paper.stored_file_path
    stored_file_name = Path(stored_file_path).stem

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    debug_dir = os.path.join(base_dir, "debug")

    if stored_file_path and os.path.exists(stored_file_path):
        try:
            os.remove(stored_file_path)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete uploaded PDF: {str(e)}"
            )

    debug_prefix = f"{stored_file_name}_{settings.PDF_EXTRACTOR}_{settings.CHUNK_MAX_CHARS}"

    if os.path.isdir(debug_dir):
        for filename in os.listdir(debug_dir):
            if filename.startswith(debug_prefix):
                file_path = os.path.join(debug_dir, filename)
                if os.path.isfile(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        raise HTTPException(
                            status_code=500,
                            detail=f"Failed to delete debug file {filename}: {str(e)}"
                        )

    try:
        db.delete(paper)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete paper record: {str(e)}"
        )

    return {
        "message": "Paper deleted successfully.",
        "paper_id": paper_id,
        "deleted_pdf": True,
        "deleted_debug_prefix": debug_prefix,
    }


@router.delete("/{paper_id}/db-only")
def delete_paper_db_only(paper_id: int, db: Session = Depends(get_db)):
    paper = db.query(Paper).filter(Paper.id == paper_id).first()

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found.")

    try:
        db.delete(paper)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete paper record from database: {str(e)}"
        )

    return {
        "message": "Paper record deleted from database only.",
        "paper_id": paper_id,
        "deleted_pdf": False,
        "deleted_debug_files": False,
    }