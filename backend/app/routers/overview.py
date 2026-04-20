import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.paper_overview import PaperOverview
from app.schemas.paper import PaperOverviewResponse
from app.services.overview_regenerator import regenerate_full_overview
from app.models.highlight import TextHighlight

router = APIRouter(prefix="/papers", tags=["Overview"])


def _delete_overview_text_highlights(db: Session, paper_id: int) -> None:
    (
        db.query(TextHighlight)
        .filter(
            TextHighlight.paper_id == paper_id,
            TextHighlight.scope == "overview",
        )
        .delete(synchronize_session=False)
    )


@router.get("/{paper_id}/overview", response_model=PaperOverviewResponse)
def get_paper_overview(
    paper_id: int,
    lang: str = Query("en", pattern="^(en|zh)$"),
    db: Session = Depends(get_db),
):
    overview = db.query(PaperOverview).filter(PaperOverview.paper_id == paper_id).first()
    if not overview:
        raise HTTPException(status_code=404, detail="Paper overview not found.")

    if lang == "zh":
        abstract_summary = overview.abstract_summary_zh or overview.abstract_summary
        overall_summary = overview.overall_summary_zh or overview.overall_summary
        overall_key_points_raw = overview.overall_key_points_zh or overview.overall_key_points
        highlight_summaries_raw = overview.highlight_summaries_zh or overview.highlight_summaries
        section_summaries_raw = overview.section_summaries_zh or overview.section_summaries
    else:
        abstract_summary = overview.abstract_summary
        overall_summary = overview.overall_summary
        overall_key_points_raw = overview.overall_key_points
        highlight_summaries_raw = overview.highlight_summaries
        section_summaries_raw = overview.section_summaries

    try:
        overall_key_points = json.loads(overall_key_points_raw) if overall_key_points_raw else []
    except Exception:
        overall_key_points = []

    try:
        highlight_summaries = json.loads(highlight_summaries_raw) if highlight_summaries_raw else []
    except Exception:
        highlight_summaries = []

    try:
        section_summaries = json.loads(section_summaries_raw) if section_summaries_raw else []
    except Exception:
        section_summaries = []

    try:
        highlight_element_ids = json.loads(overview.highlight_element_ids) if overview.highlight_element_ids else []
    except Exception:
        highlight_element_ids = []

    return {
        "paper_id": overview.paper_id,
        "language": lang,
        "abstract_summary": abstract_summary or "",
        "overall_summary": overall_summary or "",
        "overall_key_points": overall_key_points,
        "highlight_element_ids": highlight_element_ids,
        "highlight_summaries": highlight_summaries,
        "section_summaries": section_summaries,
    }


@router.post("/{paper_id}/regenerate-overview")
def regenerate_paper_overview(
    paper_id: int,
    db: Session = Depends(get_db),
):
    try:
        _delete_overview_text_highlights(db, paper_id)
        db.commit()
        return regenerate_full_overview(db, paper_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to regenerate overview: {str(e)}")