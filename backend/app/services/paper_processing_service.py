# Worker-side parse_overview task implementation and database write workflow.

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models.paper import Paper
from app.models.paragraph import Paragraph
from app.models.paper_overview import PaperOverview
from app.services.paper_processor import process_uploaded_paper
from app.services.overview_generator import (
    generate_abstract_summary,
    generate_overview,
    generate_section_summaries,
)

logger = logging.getLogger(__name__)


# Utc now.
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Internal helper for short.
def _short(prefix: str, error: Exception | str) -> str:
    raw = str(error).strip() or "Unknown error"
    return f"{prefix}: {raw[:500]}"


# Internal helper for insert paragraphs from elements.
def _insert_paragraphs_from_elements(db: Session, paper_id: int, elements: list[dict]) -> list[dict]:
    db.query(Paragraph).filter(Paragraph.paper_id == paper_id).delete()
    db.flush()

    returned_elements: list[dict] = []
    paragraph_has_pdf_locations = hasattr(Paragraph, "pdf_locations")

    for idx, el in enumerate(elements):
        el_type = el.get("type", "paragraph")
        text = el.get("text")
        level = el.get("level")
        summary = el.get("summary")
        key_points = el.get("key_points")
        intro_text = el.get("intro_text")
        items = el.get("items")
        section_title = el.get("section_title")

        page_number = el.get("page_number")
        pdf_rects = el.get("pdf_rects") or []
        pdf_locations = el.get("pdf_locations") or []

        if el_type == "heading":
            content = text or ""
        elif el_type == "bullet_list":
            parts: list[str] = []
            if intro_text:
                parts.append(str(intro_text))
            if items:
                parts.extend([str(item) for item in items])
            content = "\n".join(parts)
        else:
            content = text or ""

        paragraph_kwargs = dict(
            paper_id=paper_id,
            paragraph_index=el.get("id", idx),
            content=content,
            type=el_type,
            section_title=section_title,
            text=text,
            level=level,
            summary=summary,
            key_points=json.dumps(key_points, ensure_ascii=False) if key_points is not None else None,
            intro_text=intro_text,
            items=json.dumps(items, ensure_ascii=False) if items is not None else None,
            page_number=page_number,
            pdf_rects=json.dumps(pdf_rects, ensure_ascii=False) if pdf_rects is not None else None,
        )

        if paragraph_has_pdf_locations:
            paragraph_kwargs["pdf_locations"] = (
                json.dumps(pdf_locations, ensure_ascii=False)
                if pdf_locations is not None else None
            )

        paragraph_row = Paragraph(**paragraph_kwargs)
        db.add(paragraph_row)
        db.flush()

        returned_elements.append({
            "id": paragraph_row.paragraph_index,
            "paragraph_id": paragraph_row.id,
            "type": paragraph_row.type,
            "text": paragraph_row.text,
            "summary": paragraph_row.summary,
            "key_points": key_points,
            "level": paragraph_row.level,
            "intro_text": paragraph_row.intro_text,
            "items": items,
            "page_number": paragraph_row.page_number,
            "pdf_rects": pdf_rects,
            "pdf_locations": pdf_locations,
        })

    return returned_elements


# Internal helper for generate initial overview.
def _generate_initial_overview(db: Session, paper: Paper, elements: list[dict]) -> None:
    logger.info("Initial overview generation started user_id=%s paper_id=%s elements=%s", paper.user_id, paper.id, len(elements))

    overview_data = generate_overview(elements)
    logger.info("Initial paper overview generated user_id=%s paper_id=%s", paper.user_id, paper.id)

    section_summaries = generate_section_summaries(elements)
    logger.info("Initial section summaries generated user_id=%s paper_id=%s sections=%s", paper.user_id, paper.id, len(section_summaries))

    abstract_summary = generate_abstract_summary(elements)
    logger.info("Initial abstract summary generated user_id=%s paper_id=%s", paper.user_id, paper.id)

    db.query(PaperOverview).filter(PaperOverview.paper_id == paper.id).delete()

    overview_row = PaperOverview(
        paper_id=paper.id,
        language="en",
        abstract_summary=abstract_summary,
        overall_summary=overview_data["overall_summary"],
        overall_key_points=json.dumps(overview_data["overall_key_points"], ensure_ascii=False),
        highlight_element_ids=json.dumps(overview_data["highlight_element_ids"], ensure_ascii=False),
        highlight_summaries=json.dumps(overview_data["highlight_summaries"], ensure_ascii=False),
        section_summaries=json.dumps(section_summaries, ensure_ascii=False),
    )
    db.add(overview_row)

    paper.overview_status = "completed"
    paper.overview_error = None
    paper.overview_finished_at = utc_now()
    db.commit()
    logger.info("Initial overview completed user_id=%s paper_id=%s", paper.user_id, paper.id)


# Worker implementation for parsing a paper and writing initial overview rows.
def process_parse_overview_task(db: Session, paper_id: int) -> None:
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise ValueError(f"Paper not found: {paper_id}")

    if not paper.stored_file_path or not Path(paper.stored_file_path).exists():
        raise ValueError("Original PDF file not found.")

    paper.parse_status = "processing"
    paper.parse_error = None
    paper.parse_started_at = paper.parse_started_at or utc_now()
    paper.parse_finished_at = None
    paper.overview_status = "processing"
    paper.overview_error = None
    paper.overview_started_at = paper.overview_started_at or utc_now()
    paper.overview_finished_at = None
    paper.last_error_message = None
    db.commit()
    db.refresh(paper)

    try:
        result = process_uploaded_paper(
            paper_id=paper.id,
            pdf_path=paper.stored_file_path,
            original_filename=paper.original_filename,
            debug=settings.ENABLE_DEBUG_EXPORTS,
        )
        elements = result.get("elements", [])
        logger.info("Paper parse completed user_id=%s paper_id=%s elements=%s", paper.user_id, paper.id, len(elements))

        _insert_paragraphs_from_elements(db, paper.id, elements)
        db.commit()

        paper.parse_status = "processed"
        paper.parse_error = None
        paper.parse_finished_at = utc_now()
        db.commit()
        db.refresh(paper)

        try:
            _generate_initial_overview(db, paper, elements)
        except Exception as overview_error:
            db.rollback()
            logger.exception("Initial overview generation failed user_id=%s paper_id=%s", paper.user_id, paper.id)
            error_message = _short("Overview generation failed", overview_error)
            paper = db.query(Paper).filter(Paper.id == paper_id).first()
            if paper:
                paper.overview_status = "failed"
                paper.overview_error = error_message
                paper.overview_finished_at = utc_now()
                paper.last_error_message = error_message
                db.commit()
            raise

        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if paper:
            paper.parse_status = "processed"
            paper.parse_error = None
            paper.parse_finished_at = paper.parse_finished_at or utc_now()
            paper.last_error_message = None
            db.commit()

        logger.info("Parse overview task completed paper_id=%s", paper_id)

    except Exception as e:
        db.rollback()
        logger.exception("Parse overview task failed paper_id=%s", paper_id)
        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if paper:
            parse_already_completed = paper.parse_status == "processed"
            error_prefix = "Overview generation failed" if parse_already_completed else "Paper processing failed"
            error_message = _short(error_prefix, e)

            if not parse_already_completed:
                paper.parse_status = "failed"
                paper.parse_error = error_message
                paper.parse_finished_at = utc_now()

            paper.overview_status = "failed"
            paper.overview_error = error_message
            paper.overview_finished_at = utc_now()
            paper.last_error_message = error_message
            db.commit()
        raise
