import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.paper_overview import PaperOverview
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.ownership_service import get_owned_paper_or_404
from app.schemas.paper import PaperOverviewResponse
from app.services.resource_guard import ensure_can_start_processing_task
from app.services.task_service import (
    TASK_REGENERATE_OVERVIEW,
    create_regenerate_overview_task,
    get_active_task_for_paper,
)

router = APIRouter(prefix="/papers", tags=["Overview"])
logger = logging.getLogger(__name__)


@router.get("/{paper_id}/overview", response_model=PaperOverviewResponse)
def get_paper_overview(
    paper_id: int,
    lang: str = Query("en", pattern="^(en|zh)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_paper_or_404(db, paper_id, current_user)

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
    current_user: User = Depends(get_current_user),
):
    paper = get_owned_paper_or_404(db, paper_id, current_user)

    if paper.parse_status != "processed":
        raise HTTPException(
            status_code=409,
            detail="PDF 仍未完成解析，暫時無法重新生成全文摘要。",
        )

    existing_task = get_active_task_for_paper(
        db,
        paper_id=paper_id,
        task_type=TASK_REGENERATE_OVERVIEW,
    )
    if existing_task:
        logger.info(
            "Regenerate overview skipped because task is already active paper_id=%s user_id=%s task_id=%s status=%s",
            paper_id,
            current_user.id,
            existing_task.id,
            existing_task.status,
        )
        return {
            "paper_id": paper_id,
            "status": existing_task.status,
        }

    if paper.overview_status in ("queued", "processing"):
        logger.warning(
            "Regenerate overview rejected because overview is already active paper_id=%s user_id=%s status=%s",
            paper_id,
            current_user.id,
            paper.overview_status,
        )
        return {
            "paper_id": paper_id,
            "status": paper.overview_status,
        }

    ensure_can_start_processing_task(db, current_user)

    task = create_regenerate_overview_task(db, paper=paper, user=current_user)
    db.commit()
    db.refresh(paper)
    db.refresh(task)

    logger.info(
        "Regenerate overview queued paper_id=%s user_id=%s task_id=%s",
        paper_id,
        current_user.id,
        task.id,
    )

    return {
        "paper_id": paper_id,
        "status": task.status,
    }
