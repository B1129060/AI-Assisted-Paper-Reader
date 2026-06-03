# API route for queueing Traditional Chinese translation after prerequisites are ready.

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.paper import Paper
from app.models.paragraph import Paragraph
from app.models.user import User
from app.models.paper_overview import PaperOverview
from app.services.auth_service import get_current_user
from app.services.ownership_service import get_owned_paper_or_404
from app.services.resource_guard import ensure_can_start_processing_task
from app.services.task_service import (
    TASK_TRANSLATE_ZH,
    create_translate_zh_task,
    get_active_task_for_paper,
)

router = APIRouter(prefix="/papers", tags=["Translation"])
logger = logging.getLogger(__name__)


# Detect older translated bullet lists missing intro_text_zh.
def _has_missing_intro_text_zh(paragraphs: list[Paragraph]) -> bool:
    return any(
        p.type == "bullet_list"
        and bool((p.intro_text or "").strip())
        and not bool((p.intro_text_zh or "").strip())
        for p in paragraphs
    )


@router.post("/{paper_id}/translate-zh")
# Queue Chinese translation once parse and overview are complete.
def translate_paper_to_zh(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    paper = get_owned_paper_or_404(db, paper_id, current_user)

    if paper.parse_status != "processed" or paper.overview_status != "completed":
        raise HTTPException(
            status_code=409,
            detail="這篇論文尚未完成 PDF 解析與全文摘要，請等背景處理完成後再翻譯。",
        )

    overview = (
        db.query(PaperOverview)
        .filter(PaperOverview.paper_id == paper_id)
        .first()
    )
    if not overview:
        error_message = "Chinese translation failed: Paper overview not found."
        paper.zh_translation_status = "failed"
        paper.zh_translation_error = error_message
        paper.last_error_message = error_message
        db.commit()
        logger.warning("Translation rejected because overview was missing paper_id=%s user_id=%s", paper_id, current_user.id)
        raise HTTPException(status_code=404, detail="Paper overview not found.")

    paragraphs = (
        db.query(Paragraph)
        .filter(Paragraph.paper_id == paper_id)
        .order_by(Paragraph.paragraph_index.asc())
        .all()
    )

    missing_intro_text_zh = _has_missing_intro_text_zh(paragraphs)

    if paper.zh_translation_status == "completed" and not missing_intro_text_zh:
        logger.info("Translation skipped because already completed paper_id=%s user_id=%s", paper_id, current_user.id)
        return {
            "paper_id": paper_id,
            "status": "already_exists",
        }

    if paper.zh_translation_status in ("queued", "processing"):
        logger.info(
            "Translation skipped because already active paper_id=%s user_id=%s status=%s",
            paper_id,
            current_user.id,
            paper.zh_translation_status,
        )
        return {
            "paper_id": paper_id,
            "status": paper.zh_translation_status,
        }

    active_task = get_active_task_for_paper(db, paper_id=paper.id, task_type=TASK_TRANSLATE_ZH)
    if active_task:
        if paper.zh_translation_status not in ("queued", "processing"):
            paper.zh_translation_status = active_task.status
            paper.zh_translation_error = None
            paper.last_error_message = None
            db.commit()
        return {
            "paper_id": paper_id,
            "status": active_task.status,
        }

    ensure_can_start_processing_task(db, current_user)

    try:
        task = create_translate_zh_task(db, paper=paper, user=current_user)
        db.commit()
        logger.info(
            "Translation queued paper_id=%s user_id=%s task_id=%s",
            paper_id,
            current_user.id,
            task.id,
        )
        return {
            "paper_id": paper_id,
            "status": "queued",
        }
    except Exception as e:
        db.rollback()
        logger.exception("Failed to queue translation paper_id=%s user_id=%s", paper_id, current_user.id)
        raise HTTPException(status_code=500, detail=f"Failed to queue Chinese translation: {str(e)}")
