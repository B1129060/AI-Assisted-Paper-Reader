import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.paper import Paper
from app.models.task import Task
from app.services.task_service import (
    ACTIVE_TASK_STATUSES,
    TASK_PARSE_OVERVIEW,
    TASK_REGENERATE_OVERVIEW,
    TASK_TRANSLATE_ZH,
    create_task,
)

logger = logging.getLogger(__name__)

DEFAULT_STALE_MINUTES = 15
TRANSLATION_STALE_MINUTES = 10
EXPORT_STALE_MINUTES = 10


ACTIVE_PAPER_STATUSES = ("queued", "processing")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _is_stale(started_at: datetime | None, minutes: int) -> bool:
    started = _as_aware(started_at)
    if started is None:
        return True
    return utc_now() - started > timedelta(minutes=minutes)


def _short(message: str) -> str:
    return message[:500]


def _active_task_exists(
    db: Session,
    *,
    paper_id: int,
    task_type: str | None = None,
) -> bool:
    query = (
        db.query(Task.id)
        .filter(Task.paper_id == paper_id)
        .filter(Task.status.in_(ACTIVE_TASK_STATUSES))
    )
    if task_type:
        query = query.filter(Task.task_type == task_type)
    return query.first() is not None


def _paper_has_any_active_task(db: Session, paper_id: int) -> bool:
    return _active_task_exists(db, paper_id=paper_id)


def _queue_parse_overview_task(db: Session, paper: Paper) -> None:
    paper.parse_status = "queued"
    paper.parse_error = None
    paper.parse_finished_at = None

    if paper.overview_status in ("not_started", "queued", "processing", "failed"):
        paper.overview_status = "queued"
        paper.overview_error = None
        paper.overview_finished_at = None

    paper.last_error_message = None

    create_task(
        db,
        task_type=TASK_PARSE_OVERVIEW,
        paper_id=paper.id,
        user_id=paper.user_id,
        payload={
            "pdf_path": paper.stored_file_path,
            "original_filename": paper.original_filename,
            "repaired_missing_task": True,
        },
    )


def _queue_regenerate_overview_task(db: Session, paper: Paper) -> None:
    paper.overview_status = "queued"
    paper.overview_error = None
    paper.overview_finished_at = None
    paper.last_error_message = None

    create_task(
        db,
        task_type=TASK_REGENERATE_OVERVIEW,
        paper_id=paper.id,
        user_id=paper.user_id,
        payload={
            "scope": "full",
            "repaired_missing_task": True,
        },
    )


def _queue_translate_zh_task(db: Session, paper: Paper) -> None:
    paper.zh_translation_status = "queued"
    paper.zh_translation_error = None
    paper.zh_translation_finished_at = None
    paper.last_error_message = None

    create_task(
        db,
        task_type=TASK_TRANSLATE_ZH,
        paper_id=paper.id,
        user_id=paper.user_id,
        payload={
            "language": "zh",
            "repaired_missing_task": True,
        },
    )


def _reset_impossible_translation_state(paper: Paper) -> bool:
    """Translation cannot run before parse + overview are complete.

    If a paper somehow says translation is queued/processing while prerequisites
    are not ready and there is no active task, reset it to not_started so the
    normal trigger can start it later.
    """
    if paper.zh_translation_status not in ACTIVE_PAPER_STATUSES:
        return False

    if paper.parse_status == "processed" and paper.overview_status == "completed":
        return False

    message = _short("Chinese translation was reset because its prerequisites are not completed.")
    paper.zh_translation_status = "not_started"
    paper.zh_translation_error = None
    paper.zh_translation_started_at = None
    paper.zh_translation_finished_at = None
    paper.last_error_message = message
    logger.warning("Reset impossible translation state paper_id=%s", paper.id)
    return True


def repair_missing_active_task_for_paper(db: Session, paper: Paper) -> bool:
    """Repair paper/task mismatch for one paper.

    The worker only consumes rows from the tasks table. If a paper is marked as
    queued/processing but there is no active task row, the UI can be stuck in a
    processing state forever. This function conservatively recreates exactly one
    missing heavy task per paper, using this priority:

    1. parse_overview, if parsing is not finished
    2. regenerate_overview, if parse is finished but overview is queued/processing
    3. translate_zh, if parse + overview are finished and translation is queued/processing

    Returns True if it changed the paper or created a task. Caller should commit.
    """
    if _paper_has_any_active_task(db, paper.id):
        return False

    if paper.parse_status in ACTIVE_PAPER_STATUSES:
        _queue_parse_overview_task(db, paper)
        logger.warning(
            "Repaired missing parse_overview task paper_id=%s user_id=%s parse_status=%s overview_status=%s",
            paper.id,
            paper.user_id,
            paper.parse_status,
            paper.overview_status,
        )
        return True

    if paper.parse_status == "processed" and paper.overview_status in ACTIVE_PAPER_STATUSES:
        _queue_regenerate_overview_task(db, paper)
        logger.warning(
            "Repaired missing regenerate_overview task paper_id=%s user_id=%s overview_status=%s",
            paper.id,
            paper.user_id,
            paper.overview_status,
        )
        return True

    if paper.zh_translation_status in ACTIVE_PAPER_STATUSES:
        if paper.parse_status == "processed" and paper.overview_status == "completed":
            _queue_translate_zh_task(db, paper)
            logger.warning(
                "Repaired missing translate_zh task paper_id=%s user_id=%s zh_translation_status=%s",
                paper.id,
                paper.user_id,
                paper.zh_translation_status,
            )
            return True

        return _reset_impossible_translation_state(paper)

    return False


def repair_missing_active_tasks_for_papers(db: Session, papers: list[Paper]) -> int:
    changed_count = 0
    for paper in papers:
        if repair_missing_active_task_for_paper(db, paper):
            changed_count += 1

    if changed_count:
        db.commit()
        for paper in papers:
            try:
                db.refresh(paper)
            except Exception:
                pass

    return changed_count


def repair_all_missing_active_tasks(db: Session) -> int:
    """Repair every paper that is active on paper status but has no active task."""
    papers = (
        db.query(Paper)
        .filter(
            or_(
                Paper.parse_status.in_(ACTIVE_PAPER_STATUSES),
                Paper.overview_status.in_(ACTIVE_PAPER_STATUSES),
                Paper.zh_translation_status.in_(ACTIVE_PAPER_STATUSES),
            )
        )
        .all()
    )
    return repair_missing_active_tasks_for_papers(db, papers)


def refresh_stale_processing_status(paper: Paper, db: Session | None = None) -> bool:
    """
    Convert paper-level processing states that have been stuck too long into
    failed states. This catches cases where the backend was stopped, crashed,
    or a request ended before the status could be finalized.

    If a matching active task still exists, this function does not mark the
    paper failed. The task heartbeat / stale-task recovery is the source of
    truth for background tasks.

    Returns True if any field was changed. Caller should commit.
    """
    changed = False

    if paper.parse_status == "processing" and _is_stale(
        paper.parse_started_at or paper.created_at,
        DEFAULT_STALE_MINUTES,
    ):
        if db is not None and _active_task_exists(db, paper_id=paper.id, task_type=TASK_PARSE_OVERVIEW):
            logger.info("Skipped stale parse paper failure because active task exists paper_id=%s", paper.id)
        else:
            message = _short("PDF processing failed: processing timed out. Please delete and re-upload this paper.")
            paper.parse_status = "failed"
            paper.parse_error = message
            paper.parse_finished_at = utc_now()
            paper.last_error_message = message
            changed = True
            logger.warning("Marked stale parse as failed paper_id=%s", paper.id)

    if paper.overview_status == "processing" and _is_stale(
        paper.overview_started_at,
        DEFAULT_STALE_MINUTES,
    ):
        if db is not None and (
            _active_task_exists(db, paper_id=paper.id, task_type=TASK_PARSE_OVERVIEW)
            or _active_task_exists(db, paper_id=paper.id, task_type=TASK_REGENERATE_OVERVIEW)
        ):
            logger.info("Skipped stale overview paper failure because active task exists paper_id=%s", paper.id)
        else:
            message = _short("Overview generation failed: processing timed out. Please retry overview generation.")
            paper.overview_status = "failed"
            paper.overview_error = message
            paper.overview_finished_at = utc_now()
            paper.last_error_message = message
            changed = True
            logger.warning("Marked stale overview as failed paper_id=%s", paper.id)

    if paper.zh_translation_status == "processing" and _is_stale(
        paper.zh_translation_started_at,
        TRANSLATION_STALE_MINUTES,
    ):
        if db is not None and _active_task_exists(db, paper_id=paper.id, task_type=TASK_TRANSLATE_ZH):
            logger.info("Skipped stale translation paper failure because active task exists paper_id=%s", paper.id)
        else:
            message = _short("Chinese translation failed: processing timed out. Please retry translation.")
            paper.zh_translation_status = "failed"
            paper.zh_translation_error = message
            paper.zh_translation_finished_at = None
            paper.last_error_message = message
            changed = True
            logger.warning("Marked stale translation as failed paper_id=%s", paper.id)

    if paper.export_status == "processing" and _is_stale(
        paper.export_started_at,
        EXPORT_STALE_MINUTES,
    ):
        message = _short("Export failed: processing timed out. Please try downloading again.")
        paper.export_status = "failed"
        paper.export_error = message
        paper.export_finished_at = utc_now()
        # Export is not a core paper-readiness state, but keeping last_error helps
        # the user see why the latest export/download failed.
        paper.last_error_message = message
        changed = True
        logger.warning("Marked stale export as failed paper_id=%s", paper.id)

    return changed


def refresh_stale_papers(db: Session, papers: list[Paper]) -> None:
    repaired_count = repair_missing_active_tasks_for_papers(db, papers)

    changed = False
    for paper in papers:
        if refresh_stale_processing_status(paper, db):
            changed = True
    if changed:
        db.commit()
        for paper in papers:
            try:
                db.refresh(paper)
            except Exception:
                pass

    if repaired_count:
        logger.warning("Repaired missing active tasks while refreshing papers count=%s", repaired_count)


def refresh_all_stale_processing_papers(db: Session) -> int:
    """
    Refresh every paper currently marked as processing.

    This is intended for backend startup recovery: if the server was stopped
    while a parse / overview / translation / export request was in progress,
    the stale processing status is finalized as failed before users interact
    with the system again.

    Returns the number of paper rows whose status was changed.
    """
    papers = (
        db.query(Paper)
        .filter(
            or_(
                Paper.parse_status == "processing",
                Paper.overview_status == "processing",
                Paper.zh_translation_status == "processing",
                Paper.export_status == "processing",
            )
        )
        .all()
    )

    changed_count = 0
    for paper in papers:
        if refresh_stale_processing_status(paper, db):
            changed_count += 1

    if changed_count:
        db.commit()

    return changed_count


def repair_and_refresh_all_processing_papers(db: Session) -> dict[str, int]:
    """Startup-level consistency recovery.

    First recreates missing active task rows for papers that are marked
    queued/processing. Then marks truly stale paper-level processing states as
    failed only when no matching active task exists.
    """
    repaired_count = repair_all_missing_active_tasks(db)
    stale_failed_count = refresh_all_stale_processing_papers(db)
    return {
        "repaired_missing_tasks": repaired_count,
        "stale_failed_papers": stale_failed_count,
    }
