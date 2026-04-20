import json
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.paragraph import Paragraph
from app.models.paper_overview import PaperOverview
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