# API routes for listing, reading, exporting, renaming, serving, and deleting papers.

import logging
import os
import shutil
from pathlib import Path
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.paper import Paper
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.status_service import (
    refresh_stale_processing_status,
    refresh_stale_papers,
    repair_missing_active_task_for_paper,
    utc_now,
)
from app.models.paragraph import Paragraph
from app.schemas.paper import PaperListItemResponse, PaperDetailResponse
from app.config import settings

from fastapi.responses import Response, FileResponse
from app.models.paper_overview import PaperOverview
from app.models.highlight import TextHighlight, PdfHighlight
from app.schemas.export import ExportOptions
from app.services.export_service import (
    create_annotated_pdf,
    create_overview_pdf,
    create_paragraphs_pdf,
    package_files_as_zip,
    parse_json_field,
    safe_filename,
)

router = APIRouter(prefix="/papers", tags=["Papers"])
logger = logging.getLogger(__name__)

# Request body for updating a paper title.
class PaperTitleUpdateRequest(BaseModel):
    title: str


# Return a paper only when it belongs to the current user.
def get_owned_paper_or_404(db: Session, paper_id: int, current_user: User) -> Paper:
    paper = (
        db.query(Paper)
        .filter(Paper.id == paper_id, Paper.user_id == current_user.id)
        .first()
    )

    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found.")

    return paper


# Resolve the upload root from settings.
def _get_upload_root() -> Path:
    return settings.upload_dir_path


# Return the structured upload directory for a paper.
def _get_structured_paper_dir(paper: Paper) -> Path:
    return _get_upload_root() / f"user_{paper.user_id}" / f"paper_{paper.id}"




# Check whether parse, overview, or translation is still active.
def _is_core_processing(paper: Paper) -> bool:
    return (
        paper.parse_status in ["queued", "processing"]
        or paper.overview_status in ["queued", "processing"]
        or paper.zh_translation_status in ["queued", "processing"]
    )


# Refresh stale state and reject deletion while core processing is active.
def _ensure_paper_can_be_deleted(db: Session, paper: Paper) -> None:
    # If the paper was stuck in processing from a previous interrupted request,
    # finalize it as failed first. A stale failed paper may be deleted; an
    # actively processing paper should not be deleted by a normal delete action.
    repaired = repair_missing_active_task_for_paper(db, paper)
    stale_changed = refresh_stale_processing_status(paper, db)
    if repaired or stale_changed:
        db.commit()
        db.refresh(paper)

    if _is_core_processing(paper):
        logger.warning("Delete rejected because paper is processing paper_id=%s user_id=%s", paper.id, paper.user_id)
        raise HTTPException(
            status_code=409,
            detail="這篇論文仍在處理中，請等處理完成後再刪除。",
        )

# Delete the structured paper directory or legacy uploaded PDF path.
def _delete_uploaded_pdf_or_paper_dir(paper: Paper) -> bool:
    structured_dir = _get_structured_paper_dir(paper)
    deleted_anything = False

    if structured_dir.exists() and structured_dir.is_dir():
        shutil.rmtree(structured_dir)
        deleted_anything = True

        user_dir = structured_dir.parent
        try:
            user_dir.rmdir()
        except OSError:
            pass

        return deleted_anything

    if paper.stored_file_path and os.path.exists(paper.stored_file_path):
        os.remove(paper.stored_file_path)
        deleted_anything = True

    return deleted_anything


# Persist successful immediate export status.
def _mark_export_completed(db: Session, paper: Paper) -> None:
    logger.info("Export completed paper_id=%s user_id=%s", paper.id, paper.user_id)
    paper.export_status = "completed"
    paper.export_error = None
    paper.export_finished_at = utc_now()
    db.commit()
    db.refresh(paper)


# Persist failed immediate export status with a user-facing message.
def _mark_export_failed(
    db: Session,
    paper_id: int,
    current_user: User,
    message: str,
) -> None:
    db.rollback()

    paper = (
        db.query(Paper)
        .filter(Paper.id == paper_id, Paper.user_id == current_user.id)
        .first()
    )

    if not paper:
        return

    logger.warning("Export failed paper_id=%s user_id=%s error=%s", paper_id, current_user.id, message)
    paper.export_status = "failed"
    paper.export_error = message
    paper.export_finished_at = utc_now()
    paper.last_error_message = message
    db.commit()


@router.get("/", response_model=list[PaperListItemResponse])
# Return the current user's papers after refreshing stale statuses.
def list_papers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    papers = (
        db.query(Paper)
        .filter(Paper.user_id == current_user.id)
        .order_by(Paper.id.desc())
        .all()
    )

    refresh_stale_papers(db, papers)

    return [
        {
            "paper_id": p.id,
            "title": p.title,
            "original_filename": p.original_filename,
            "parse_status": p.parse_status,
            "parse_error": p.parse_error,
            "parse_started_at": p.parse_started_at.isoformat() if p.parse_started_at else None,
            "parse_finished_at": p.parse_finished_at.isoformat() if p.parse_finished_at else None,
            "overview_status": p.overview_status,
            "overview_error": p.overview_error,
            "overview_started_at": p.overview_started_at.isoformat() if p.overview_started_at else None,
            "overview_finished_at": p.overview_finished_at.isoformat() if p.overview_finished_at else None,
            "zh_translation_status": p.zh_translation_status,
            "zh_translation_error": p.zh_translation_error,
            "export_status": p.export_status,
            "export_error": p.export_error,
            "export_started_at": p.export_started_at.isoformat() if p.export_started_at else None,
            "export_finished_at": p.export_finished_at.isoformat() if p.export_finished_at else None,
            "last_error_message": p.last_error_message,
            "zh_translation_started_at": p.zh_translation_started_at.isoformat() if p.zh_translation_started_at else None,
            "zh_translation_finished_at": p.zh_translation_finished_at.isoformat() if p.zh_translation_finished_at else None,
        }
        for p in papers
    ]


@router.get("/{paper_id}", response_model=PaperDetailResponse)
# Return reader-page paper data, elements, translations, and PDF locations.
def get_paper_detail(
    paper_id: int,
    lang: str = Query("en", pattern="^(en|zh)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    paper = get_owned_paper_or_404(db, paper_id, current_user)
    repaired = repair_missing_active_task_for_paper(db, paper)
    stale_changed = refresh_stale_processing_status(paper, db)
    if repaired or stale_changed:
        db.commit()
        db.refresh(paper)

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
            intro_text = p.intro_text_zh or p.intro_text
            items_raw = p.items_zh or p.items
        else:
            text = p.text
            summary = p.summary
            key_points_raw = p.key_points
            intro_text = p.intro_text
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
            "intro_text": intro_text,
            "intro_text_zh": p.intro_text_zh,
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
        "parse_error": paper.parse_error,
        "parse_started_at": paper.parse_started_at.isoformat() if paper.parse_started_at else None,
        "parse_finished_at": paper.parse_finished_at.isoformat() if paper.parse_finished_at else None,
        "overview_status": paper.overview_status,
        "overview_error": paper.overview_error,
        "overview_started_at": paper.overview_started_at.isoformat() if paper.overview_started_at else None,
        "overview_finished_at": paper.overview_finished_at.isoformat() if paper.overview_finished_at else None,
        "zh_translation_status": paper.zh_translation_status,
        "zh_translation_error": paper.zh_translation_error,
        "export_status": paper.export_status,
        "export_error": paper.export_error,
        "export_started_at": paper.export_started_at.isoformat() if paper.export_started_at else None,
        "export_finished_at": paper.export_finished_at.isoformat() if paper.export_finished_at else None,
        "last_error_message": paper.last_error_message,
        "zh_translation_started_at": paper.zh_translation_started_at.isoformat() if paper.zh_translation_started_at else None,
        "zh_translation_finished_at": paper.zh_translation_finished_at.isoformat() if paper.zh_translation_finished_at else None,
        "pdf_url": f"/papers/{paper.id}/pdf" if pdf_filename else "",
        "elements": elements,
    }


@router.get("/{paper_id}/pdf")
# Serve the owned PDF inline with a safe display filename.
def get_paper_pdf(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    paper = get_owned_paper_or_404(db, paper_id, current_user)

    if not paper.stored_file_path or not os.path.exists(paper.stored_file_path):
        raise HTTPException(status_code=404, detail="PDF file not found.")

    display_name = paper.title or paper.original_filename or f"paper_{paper.id}.pdf"
    filename = safe_filename(display_name)
    if not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"

    return FileResponse(
        path=paper.stored_file_path,
        media_type="application/pdf",
        filename=filename,
        content_disposition_type="inline",
    )


@router.delete("/{paper_id}")
# Delete the paper row, uploaded files, and matching debug files.
def delete_paper(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    paper = get_owned_paper_or_404(db, paper_id, current_user)
    logger.info("Delete requested paper_id=%s user_id=%s", paper_id, current_user.id)
    _ensure_paper_can_be_deleted(db, paper)

    stored_file_path = paper.stored_file_path
    stored_file_name = Path(stored_file_path).stem

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    debug_dir = os.path.join(base_dir, "debug")

    try:
        deleted_pdf = _delete_uploaded_pdf_or_paper_dir(paper)
        logger.info("Deleted uploaded files paper_id=%s user_id=%s deleted=%s", paper_id, current_user.id, deleted_pdf)
    except Exception as e:
        logger.exception("Failed to delete uploaded files paper_id=%s user_id=%s", paper_id, current_user.id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete uploaded PDF files: {str(e)}"
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
        logger.info("Paper record deleted paper_id=%s user_id=%s", paper_id, current_user.id)
    except Exception as e:
        db.rollback()
        logger.exception("Failed to delete paper record paper_id=%s user_id=%s", paper_id, current_user.id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete paper record: {str(e)}"
        )

    return {
        "message": "Paper deleted successfully.",
        "paper_id": paper_id,
        "deleted_pdf": deleted_pdf,
        "deleted_debug_prefix": debug_prefix,
    }


@router.delete("/{paper_id}/db-only")
# Delete only the database paper row after safety checks.
def delete_paper_db_only(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    paper = get_owned_paper_or_404(db, paper_id, current_user)
    _ensure_paper_can_be_deleted(db, paper)

    try:
        db.delete(paper)
        db.commit()
        logger.info("Paper record deleted paper_id=%s user_id=%s", paper_id, current_user.id)
    except Exception as e:
        db.rollback()
        logger.exception("Failed to delete paper record paper_id=%s user_id=%s", paper_id, current_user.id)
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

@router.post("/{paper_id}/export")
# Build immediate export files and return either a PDF or ZIP response.
def export_paper(
    paper_id: int,
    options: ExportOptions,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    paper = get_owned_paper_or_404(db, paper_id, current_user)
    logger.info("Export requested paper_id=%s user_id=%s options=%s", paper_id, current_user.id, options.model_dump() if hasattr(options, "model_dump") else options.dict())

    if not (options.include_pdf or options.include_overview or options.include_paragraphs):
        # This is a user selection error, not a paper processing failure.
        raise HTTPException(status_code=400, detail="No export option selected.")

    paper.export_status = "processing"
    paper.export_error = None
    paper.export_started_at = utc_now()
    paper.export_finished_at = None
    paper.last_error_message = None
    db.commit()
    db.refresh(paper)

    try:
        display_name = paper.title or paper.original_filename
        safe_name = safe_filename(display_name)

        paragraphs = (
            db.query(Paragraph)
            .filter(Paragraph.paper_id == paper_id)
            .order_by(Paragraph.paragraph_index.asc())
            .all()
        )

        overview_rows = (
            db.query(PaperOverview)
            .filter(PaperOverview.paper_id == paper_id)
            .all()
        )

        overview_en_row = next((o for o in overview_rows if o.language == "en"), None)
        overview_zh_row = next((o for o in overview_rows if o.language == "zh"), None)

        text_highlight_rows = (
            db.query(TextHighlight)
            .filter(TextHighlight.paper_id == paper_id)
            .all()
        )

        pdf_highlight_rows = (
            db.query(PdfHighlight)
            .filter(PdfHighlight.paper_id == paper_id)
            .all()
        )

        paper_dict = {
            "paper_id": paper.id,
            "display_name": display_name,
            "original_filename": paper.original_filename,
            "stored_file_path": paper.stored_file_path,
        }

        def build_overview_dict(row: PaperOverview | None):
            if not row:
                return None
            return {
                "abstract_summary": row.abstract_summary,
                "overall_summary": row.overall_summary,
                "overall_key_points": parse_json_field(row.overall_key_points, []),
                "highlight_summaries": parse_json_field(row.highlight_summaries, []),
                "section_summaries": parse_json_field(row.section_summaries, []),
            }

        overview_en = build_overview_dict(overview_en_row)
        overview_zh = None
        if overview_zh_row:
            overview_zh = {
                "abstract_summary": overview_zh_row.abstract_summary_zh or "",
                "overall_summary": overview_zh_row.overall_summary_zh or "",
                "overall_key_points": parse_json_field(overview_zh_row.overall_key_points_zh, []),
                "highlight_summaries": parse_json_field(overview_zh_row.highlight_summaries_zh, []),
                "section_summaries": parse_json_field(overview_zh_row.section_summaries_zh, []),
            }
        elif overview_en_row:
            overview_zh = {
                "abstract_summary": overview_en_row.abstract_summary_zh or "",
                "overall_summary": overview_en_row.overall_summary_zh or "",
                "overall_key_points": parse_json_field(overview_en_row.overall_key_points_zh, []),
                "highlight_summaries": parse_json_field(overview_en_row.highlight_summaries_zh, []),
                "section_summaries": parse_json_field(overview_en_row.section_summaries_zh, []),
            }

        paragraph_dicts = []
        for p in paragraphs:
            paragraph_dicts.append(
                {
                    "paragraph_id": p.id,
                    "paragraph_index": p.paragraph_index,
                    "type": p.type or "paragraph",
                    "level": p.level,
                    "text": p.text,
                    "text_zh": p.text_zh,
                    "summary": p.summary,
                    "summary_zh": p.summary_zh,
                    "key_points": parse_json_field(p.key_points, []),
                    "key_points_zh": parse_json_field(p.key_points_zh, []),
                    "intro_text": p.intro_text,
                    "intro_text_zh": p.intro_text_zh,
                    "items": parse_json_field(p.items, []),
                    "items_zh": parse_json_field(p.items_zh, []),
                    "page_number": p.page_number,
                    "pdf_rects": parse_json_field(p.pdf_rects, []),
                    "pdf_locations": parse_json_field(p.pdf_locations, []),
                }
            )

        text_highlights = [
            {
                "id": h.id,
                "paper_id": h.paper_id,
                "paragraph_id": h.paragraph_id,
                "scope": h.scope,
                "field_name": h.field_name,
                "item_index": h.item_index,
                "language": h.language,
                "start_offset": h.start_offset,
                "end_offset": h.end_offset,
                "color": h.color,
            }
            for h in text_highlight_rows
        ]

        pdf_highlights = [
            {
                "id": h.id,
                "paper_id": h.paper_id,
                "paragraph_id": h.paragraph_id,
                "page_number": h.page_number,
                "rects": parse_json_field(h.rects_json, []),
                "color": h.color,
            }
            for h in pdf_highlight_rows
        ]

        files: dict[str, bytes] = {}

        if options.include_pdf:
            if not paper.stored_file_path or not os.path.exists(paper.stored_file_path):
                raise HTTPException(status_code=400, detail="Original PDF file not found.")

            if options.include_pdf_highlights:
                files[f"{safe_name}_annotated.pdf"] = create_annotated_pdf(
                    paper.stored_file_path,
                    pdf_highlights,
                )
            else:
                with open(paper.stored_file_path, "rb") as f:
                    files[f"{safe_name}_original.pdf"] = f.read()

        if options.include_overview:
            files[f"{safe_name}_overview.pdf"] = create_overview_pdf(
                paper=paper_dict,
                overview_en=overview_en,
                overview_zh=overview_zh,
                text_highlights=text_highlights,
                language_mode=options.language_mode,
                include_text_highlights=options.include_text_highlights,
            )

        if options.include_paragraphs:
            files[f"{safe_name}_paragraphs.pdf"] = create_paragraphs_pdf(
                paper=paper_dict,
                paragraphs=paragraph_dicts,
                text_highlights=text_highlights,
                language_mode=options.language_mode,
                include_text_highlights=options.include_text_highlights,
            )

        if len(files) == 1:
            filename, content = next(iter(files.items()))
            media_type = "application/pdf" if filename.endswith(".pdf") else "application/octet-stream"
            _mark_export_completed(db, paper)
            return Response(
                content=content,
                media_type=media_type,
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        zip_name = f"{safe_name}_export.zip"
        zip_bytes = package_files_as_zip(files)
        _mark_export_completed(db, paper)
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{zip_name}"'},
        )

    except HTTPException as e:
        message = str(e.detail)
        _mark_export_failed(db, paper_id, current_user, message)
        raise e

    except Exception as e:
        message = f"Export failed: {str(e)}"
        _mark_export_failed(db, paper_id, current_user, message)
        raise HTTPException(status_code=500, detail=message)

@router.delete("/{paper_id}/with-file")
# Delete the paper row and uploaded file directory.
def delete_paper_with_file(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    paper = get_owned_paper_or_404(db, paper_id, current_user)
    _ensure_paper_can_be_deleted(db, paper)

    stored_file_path = paper.stored_file_path

    try:
        deleted_pdf = _delete_uploaded_pdf_or_paper_dir(paper)
        logger.info("Deleted uploaded files paper_id=%s user_id=%s deleted=%s", paper_id, current_user.id, deleted_pdf)
    except Exception as e:
        logger.exception("Failed to delete uploaded files paper_id=%s user_id=%s", paper_id, current_user.id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete uploaded PDF files: {str(e)}"
        )

    try:
        db.delete(paper)
        db.commit()
        logger.info("Paper record deleted paper_id=%s user_id=%s", paper_id, current_user.id)
    except Exception as e:
        db.rollback()
        logger.exception("Failed to delete paper record paper_id=%s user_id=%s", paper_id, current_user.id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete paper record: {str(e)}"
        )

    return {
        "message": "Paper and uploaded PDF deleted successfully.",
        "paper_id": paper_id,
        "deleted_pdf": deleted_pdf,
        "deleted_debug_files": False,
    }

@router.patch("/{paper_id}/title")
# Validate and persist a new display title for a paper.
def update_paper_title(
    paper_id: int,
    payload: PaperTitleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    paper = get_owned_paper_or_404(db, paper_id, current_user)

    new_title = payload.title.strip()

    if not new_title:
        raise HTTPException(status_code=400, detail="Title cannot be empty.")

    if len(new_title) > 255:
        raise HTTPException(status_code=400, detail="Title is too long.")

    paper.title = new_title

    try:
        db.commit()
        db.refresh(paper)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update paper title: {str(e)}"
        )

    return {
        "paper_id": paper.id,
        "title": paper.title,
        "original_filename": paper.original_filename,
        "message": "Paper title updated successfully.",
    }