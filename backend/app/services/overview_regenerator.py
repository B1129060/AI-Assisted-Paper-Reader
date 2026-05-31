import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.paragraph import Paragraph
from app.models.paper_overview import PaperOverview
from app.models.paper import Paper
from app.models.highlight import TextHighlight
from app.services.overview_generator import (
    generate_overview,
    generate_section_summaries,
    generate_abstract_summary,
)
from app.services.translation_service import translate_overview_to_zh


def _parse_json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []



def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _has_non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def _validate_overview_payload(
    overview_data: dict,
    section_summaries: list,
    abstract_summary: str,
) -> None:
    """
    Prevent an incomplete regenerate result from overwriting the last usable
    overview. If generation is incomplete, the caller marks the task failed and
    the old PaperOverview row remains unchanged.
    """
    missing: list[str] = []

    if not _has_text(abstract_summary):
        missing.append("abstract_summary")

    if not _has_text(overview_data.get("overall_summary")):
        missing.append("overall_summary")

    if not _has_non_empty_list(overview_data.get("overall_key_points")):
        missing.append("overall_key_points")

    if not _has_non_empty_list(overview_data.get("highlight_summaries")):
        missing.append("highlight_summaries")

    if not _has_non_empty_list(section_summaries):
        missing.append("section_summaries")

    if missing:
        raise ValueError(
            "Generated overview was incomplete; old overview was kept. "
            f"Missing or empty fields: {', '.join(missing)}."
        )

def rebuild_elements_from_db(db: Session, paper_id: int, lang: str = "en") -> List[dict]:
    rows = (
        db.query(Paragraph)
        .filter(Paragraph.paper_id == paper_id)
        .order_by(Paragraph.paragraph_index.asc())
        .all()
    )

    elements: List[Dict[str, Any]] = []

    for row in rows:
        if lang == "zh":
            text = row.text_zh or row.text
            summary = row.summary_zh or row.summary
            key_points = _parse_json_list(row.key_points_zh) if row.key_points_zh else _parse_json_list(row.key_points)
            items = _parse_json_list(row.items_zh) if row.items_zh else _parse_json_list(row.items)
        else:
            text = row.text
            summary = row.summary
            key_points = _parse_json_list(row.key_points)
            items = _parse_json_list(row.items)

        elements.append({
            "id": row.paragraph_index,
            "paragraph_id": row.id,
            "type": row.type,
            "section_title": row.section_title,
            "text": text,
            "summary": summary,
            "key_points": key_points,
            "level": row.level,
            "intro_text": row.intro_text,
            "items": items,
        })

    return elements


def regenerate_full_overview(db: Session, paper_id: int) -> dict:
    elements_en = rebuild_elements_from_db(db, paper_id, lang="en")

    if not elements_en:
        raise ValueError("No elements found for this paper.")

    overview_data = generate_overview(elements_en)
    section_summaries = generate_section_summaries(elements_en)
    abstract_summary = generate_abstract_summary(elements_en)

    _validate_overview_payload(
        overview_data=overview_data,
        section_summaries=section_summaries,
        abstract_summary=abstract_summary,
    )

    overview_payload = {
        "abstract_summary": abstract_summary,
        "overall_summary": overview_data["overall_summary"],
        "overall_key_points": overview_data["overall_key_points"],
        "highlight_summaries": overview_data["highlight_summaries"],
        "section_summaries": section_summaries,
    }

    translated_overview = translate_overview_to_zh(overview_payload)

    overview = db.query(PaperOverview).filter(PaperOverview.paper_id == paper_id).first()

    if overview is None:
        overview = PaperOverview(
            paper_id=paper_id,
            language="en",
        )
        db.add(overview)
        db.flush()

    overview.abstract_summary = abstract_summary
    overview.overall_summary = overview_data["overall_summary"]
    overview.overall_key_points = json.dumps(overview_data["overall_key_points"], ensure_ascii=False)
    overview.highlight_element_ids = json.dumps(overview_data["highlight_element_ids"], ensure_ascii=False)
    overview.highlight_summaries = json.dumps(overview_data["highlight_summaries"], ensure_ascii=False)
    overview.section_summaries = json.dumps(section_summaries, ensure_ascii=False)

    overview.abstract_summary_zh = translated_overview["abstract_summary_zh"]
    overview.overall_summary_zh = translated_overview["overall_summary_zh"]
    overview.overall_key_points_zh = json.dumps(translated_overview["overall_key_points_zh"], ensure_ascii=False)
    overview.highlight_summaries_zh = json.dumps(translated_overview["highlight_summaries_zh"], ensure_ascii=False)
    overview.section_summaries_zh = json.dumps(translated_overview["section_summaries_zh"], ensure_ascii=False)

    db.commit()
    db.refresh(overview)

    return {
        "paper_id": paper_id,
        "status": "regenerated",
    }

def _delete_overview_text_highlights(db: Session, paper_id: int) -> None:
    (
        db.query(TextHighlight)
        .filter(
            TextHighlight.paper_id == paper_id,
            TextHighlight.scope == "overview",
        )
        .delete(synchronize_session=False)
    )


def process_regenerate_overview_task(db: Session, paper_id: int) -> dict:
    result = regenerate_full_overview(db, paper_id)

    _delete_overview_text_highlights(db, paper_id)

    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise ValueError("Paper not found.")

    paper.overview_status = "completed"
    paper.overview_error = None
    paper.overview_finished_at = datetime.now(timezone.utc)
    paper.last_error_message = None

    db.commit()

    return result
