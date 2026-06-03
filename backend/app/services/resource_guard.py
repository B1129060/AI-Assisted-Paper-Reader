# Per-user limits for stored papers and active processing jobs.

import logging

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models.paper import Paper
from app.models.user import User

logger = logging.getLogger(__name__)


PROCESSING_FILTER = or_(
    Paper.parse_status.in_(["queued", "processing"]),
    Paper.overview_status.in_(["queued", "processing"]),
    Paper.zh_translation_status.in_(["queued", "processing"]),
)


# Count all papers owned by one user.
def count_user_papers(db: Session, current_user: User) -> int:
    return (
        db.query(Paper)
        .filter(Paper.user_id == current_user.id)
        .count()
    )


# Count papers whose core processing status is queued or processing.
def count_user_processing_papers(db: Session, current_user: User) -> int:
    return (
        db.query(Paper)
        .filter(Paper.user_id == current_user.id)
        .filter(PROCESSING_FILTER)
        .count()
    )


# Enforce total paper and active processing limits before upload.
def ensure_can_upload_paper(db: Session, current_user: User) -> None:
    max_papers = settings.MAX_PAPERS_PER_USER
    if max_papers > 0 and count_user_papers(db, current_user) >= max_papers:
        logger.warning("Paper limit reached user_id=%s max_papers=%s", current_user.id, max_papers)
        raise HTTPException(
            status_code=429,
            detail=f"已達每位使用者最多 {max_papers} 篇論文的上限。請先刪除不需要的論文後再上傳。",
        )

    ensure_can_start_processing_task(db, current_user)


# Enforce the per-user active processing limit.
def ensure_can_start_processing_task(db: Session, current_user: User) -> None:
    max_processing = settings.MAX_PROCESSING_PAPERS_PER_USER
    if max_processing <= 0:
        return

    processing_count = count_user_processing_papers(db, current_user)
    if processing_count >= max_processing:
        logger.warning("Processing task limit reached user_id=%s processing_count=%s max_processing=%s", current_user.id, processing_count, max_processing)
        raise HTTPException(
            status_code=429,
            detail=(
                f"目前已有 {processing_count} 個處理中的任務。"
                f"每位使用者同時最多只能有 {max_processing} 個處理中任務，請稍後再試。"
            ),
        )
