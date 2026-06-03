# Background task creation, claiming, retry, heartbeat, failure classification, and completion logic.

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.paper import Paper
from app.models.user import User
from app.config import settings

logger = logging.getLogger(__name__)

TASK_PARSE_OVERVIEW = "parse_overview"
TASK_TRANSLATE_ZH = "translate_zh"
TASK_REGENERATE_OVERVIEW = "regenerate_overview"
ACTIVE_TASK_STATUSES = ("queued", "processing")


# Utc now.
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Internal helper for as aware.
def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


# Internal helper for short.
def _short(message: str, limit: int = 1000) -> str:
    return (message or "Unknown task error")[:limit]


# Internal helper for get error attr.
def _get_error_attr(error: Exception | str, name: str) -> str | None:
    value = getattr(error, name, None)
    if value is None:
        return None
    return str(value)


# Classify task errors into user-facing messages and retryability.
def classify_task_error(error: Exception | str) -> tuple[str, bool]:
    """Return a user-facing message and whether the task is worth retrying.

    LLM quota / invalid-key errors usually do not become successful after an
    immediate retry, so they should fail fast with a clear message instead of
    consuming all attempts and surfacing a long provider traceback to users.
    Temporary rate limits, timeouts, and network errors can still be retried by
    the queue.
    """
    raw_message = str(error or "").strip()
    pieces = [raw_message, error.__class__.__name__ if not isinstance(error, str) else ""]

    for attr in ("code", "type", "status_code"):
        attr_value = _get_error_attr(error, attr)
        if attr_value:
            pieces.append(attr_value)

    combined = " ".join(pieces).lower()

    if (
        "insufficient_quota" in combined
        or "quota" in combined
        or "exceeded your current quota" in combined
        or "billing" in combined
        or "額度不足" in combined
        or "帳單" in combined
    ):
        return (
            "LLM API 額度不足或帳單設定不可用，請確認 API key 的額度 / billing 後再重新嘗試。",
            False,
        )

    if (
        "invalid_api_key" in combined
        or "incorrect api key" in combined
        or "invalid api key" in combined
        or "unauthorized" in combined
        or "401" in combined
        or "api key 無效" in combined
        or "未授權" in combined
    ):
        return (
            "LLM API key 無效或未授權，請確認 API key 設定後再重新嘗試。",
            False,
        )

    if "rate limit" in combined or "ratelimit" in combined or "429" in combined:
        return (
            "LLM API 請求過於頻繁，系統會稍後自動重試；若持續失敗，請稍後再試。",
            True,
        )

    if (
        "timeout" in combined
        or "timed out" in combined
        or "connection" in combined
        or "network" in combined
        or "temporarily unavailable" in combined
        or "503" in combined
        or "502" in combined
        or "500" in combined
    ):
        return (
            "LLM 服務暫時無法完成請求，系統會稍後自動重試；若持續失敗，請稍後再試。",
            True,
        )

    return (_short(raw_message or "Unknown task error", 1000), True)


# Internal helper for mark parse overview paper queued.
def _mark_parse_overview_paper_queued(paper: Paper | None, message: str | None = None) -> None:
    if not paper:
        return

    if paper.parse_status in ("queued", "processing"):
        paper.parse_status = "queued"
        paper.parse_error = None
        paper.parse_finished_at = None

    if paper.overview_status in ("queued", "processing", "not_started"):
        paper.overview_status = "queued"
        paper.overview_error = None
        paper.overview_finished_at = None

    if message:
        paper.last_error_message = _short(message, 500)



# Internal helper for mark parse overview paper processing.
def _mark_parse_overview_paper_processing(paper: Paper | None) -> None:
    if not paper:
        return

    now = utc_now()

    if paper.parse_status in ("queued", "uploaded"):
        paper.parse_status = "processing"
        paper.parse_started_at = paper.parse_started_at or now
        paper.parse_finished_at = None
        paper.parse_error = None

    if paper.overview_status in ("queued", "not_started"):
        paper.overview_status = "processing"
        paper.overview_started_at = paper.overview_started_at or now
        paper.overview_finished_at = None
        paper.overview_error = None

    paper.last_error_message = None



# Internal helper for mark parse overview paper failed.
def _mark_parse_overview_paper_failed(paper: Paper | None, message: str) -> None:
    if not paper:
        return

    now = utc_now()
    short_message = _short(message, 500)

    if paper.parse_status in ("queued", "processing", "uploaded"):
        paper.parse_status = "failed"
        paper.parse_error = short_message
        paper.parse_finished_at = now

    if paper.overview_status in ("queued", "processing", "not_started"):
        paper.overview_status = "failed"
        paper.overview_error = short_message
        paper.overview_finished_at = now

    paper.last_error_message = short_message


# Internal helper for mark translate zh paper queued.
def _mark_translate_zh_paper_queued(paper: Paper | None, message: str | None = None) -> None:
    if not paper:
        return

    paper.zh_translation_status = "queued"
    paper.zh_translation_error = None
    paper.zh_translation_finished_at = None

    if message:
        paper.last_error_message = _short(message, 500)


# Internal helper for mark translate zh paper processing.
def _mark_translate_zh_paper_processing(paper: Paper | None) -> None:
    if not paper:
        return

    now = utc_now()
    paper.zh_translation_status = "processing"
    paper.zh_translation_started_at = paper.zh_translation_started_at or now
    paper.zh_translation_finished_at = None
    paper.zh_translation_error = None
    paper.last_error_message = None


# Internal helper for mark translate zh paper failed.
def _mark_translate_zh_paper_failed(paper: Paper | None, message: str) -> None:
    if not paper:
        return

    now = utc_now()
    short_message = _short(message, 500)
    paper.zh_translation_status = "failed"
    paper.zh_translation_error = short_message
    paper.zh_translation_finished_at = now
    paper.last_error_message = short_message


# Internal helper for mark regenerate overview paper queued.
def _mark_regenerate_overview_paper_queued(paper: Paper | None, message: str | None = None) -> None:
    if not paper:
        return

    paper.overview_status = "queued"
    paper.overview_error = None
    paper.overview_finished_at = None

    if message:
        paper.last_error_message = _short(message, 500)


# Internal helper for mark regenerate overview paper processing.
def _mark_regenerate_overview_paper_processing(paper: Paper | None) -> None:
    if not paper:
        return

    now = utc_now()
    paper.overview_status = "processing"
    paper.overview_started_at = now
    paper.overview_finished_at = None
    paper.overview_error = None
    paper.last_error_message = None


# Internal helper for mark regenerate overview paper completed.
def _mark_regenerate_overview_paper_completed(paper: Paper | None) -> None:
    if not paper:
        return

    paper.overview_status = "completed"
    paper.overview_error = None
    paper.overview_finished_at = utc_now()
    paper.last_error_message = None


# Internal helper for mark regenerate overview paper failed.
def _mark_regenerate_overview_paper_failed(paper: Paper | None, message: str) -> None:
    if not paper:
        return

    now = utc_now()
    short_message = _short(message, 500)
    paper.overview_status = "failed"
    paper.overview_error = short_message
    paper.overview_finished_at = now
    paper.last_error_message = short_message



# Insert a queued background task row.
def create_task(
    db: Session,
    *,
    task_type: str,
    paper_id: int,
    user_id: int,
    payload: dict[str, Any] | None = None,
    max_attempts: int | None = None,
) -> Task:
    task = Task(
        task_type=task_type,
        paper_id=paper_id,
        user_id=user_id,
        status="queued",
        attempts=0,
        max_attempts=max_attempts or settings.WORKER_MAX_ATTEMPTS,
        payload_json=json.dumps(payload or {}, ensure_ascii=False),
    )
    db.add(task)
    db.flush()
    logger.info(
        "Task created task_id=%s task_type=%s paper_id=%s user_id=%s",
        task.id,
        task.task_type,
        task.paper_id,
        task.user_id,
    )
    return task



# Queue parse and initial overview generation for a paper.
def create_parse_overview_task(db: Session, *, paper: Paper, user: User) -> Task:
    return create_task(
        db,
        task_type=TASK_PARSE_OVERVIEW,
        paper_id=paper.id,
        user_id=user.id,
        payload={
            "pdf_path": paper.stored_file_path,
            "original_filename": paper.original_filename,
        },
    )


# Return the oldest active task for a paper and optional task type.
def get_active_task_for_paper(
    db: Session,
    *,
    paper_id: int,
    task_type: str | None = None,
) -> Task | None:
    query = (
        db.query(Task)
        .filter(Task.paper_id == paper_id)
        .filter(Task.status.in_(ACTIVE_TASK_STATUSES))
    )
    if task_type:
        query = query.filter(Task.task_type == task_type)
    return query.order_by(Task.created_at.asc(), Task.id.asc()).first()


# Queue translation unless a matching active task already exists.
def create_translate_zh_task(db: Session, *, paper: Paper, user: User) -> Task:
    existing = get_active_task_for_paper(
        db,
        paper_id=paper.id,
        task_type=TASK_TRANSLATE_ZH,
    )
    if existing:
        return existing

    _mark_translate_zh_paper_queued(paper)
    return create_task(
        db,
        task_type=TASK_TRANSLATE_ZH,
        paper_id=paper.id,
        user_id=user.id,
        payload={"language": "zh"},
    )



# Queue overview regeneration unless a matching active task already exists.
def create_regenerate_overview_task(db: Session, *, paper: Paper, user: User) -> Task:
    existing = get_active_task_for_paper(
        db,
        paper_id=paper.id,
        task_type=TASK_REGENERATE_OVERVIEW,
    )
    if existing:
        return existing

    _mark_regenerate_overview_paper_queued(paper)
    return create_task(
        db,
        task_type=TASK_REGENERATE_OVERVIEW,
        paper_id=paper.id,
        user_id=user.id,
        payload={"scope": "full"},
    )



# Claim the oldest queued task and mark the matching paper status processing.
def claim_next_queued_task(db: Session) -> Task | None:
    query = (
        db.query(Task)
        .filter(Task.status == "queued")
        .order_by(Task.created_at.asc(), Task.id.asc())
    )

    try:
        task = query.with_for_update(skip_locked=True).first()
    except TypeError:
        # Fallback for DBs that do not support skip_locked in local testing.
        # Do not use this fallback with multiple workers in production.
        task = query.first()

    if not task:
        return None

    task.status = "processing"
    task.attempts += 1
    task.locked_at = utc_now()
    task.started_at = task.started_at or task.locked_at
    task.error_message = None

    if task.task_type == TASK_PARSE_OVERVIEW:
        paper = db.query(Paper).filter(Paper.id == task.paper_id).first()
        _mark_parse_overview_paper_processing(paper)
    elif task.task_type == TASK_TRANSLATE_ZH:
        paper = db.query(Paper).filter(Paper.id == task.paper_id).first()
        _mark_translate_zh_paper_processing(paper)
    elif task.task_type == TASK_REGENERATE_OVERVIEW:
        paper = db.query(Paper).filter(Paper.id == task.paper_id).first()
        _mark_regenerate_overview_paper_processing(paper)

    db.commit()
    db.refresh(task)

    logger.info(
        "Task claimed task_id=%s task_type=%s paper_id=%s user_id=%s attempt=%s/%s",
        task.id,
        task.task_type,
        task.paper_id,
        task.user_id,
        task.attempts,
        task.max_attempts,
    )
    return task



# Refresh locked_at as the worker heartbeat for a processing task.
def refresh_task_heartbeat(db: Session, task_id: int) -> bool:
    """Refresh locked_at for a processing task.

    locked_at doubles as a heartbeat timestamp in the current schema. A long
    running worker updates it periodically so another worker does not reclaim a
    task that is still actively being processed.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task or task.status != "processing":
        return False

    task.locked_at = utc_now()
    db.commit()
    logger.debug("Task heartbeat task_id=%s task_type=%s paper_id=%s", task.id, task.task_type, task.paper_id)
    return True



# Requeue or fail tasks whose worker heartbeat timed out.
def reclaim_stale_processing_tasks(db: Session, *, limit: int = 50) -> dict[str, int]:
    timeout_minutes = settings.WORKER_TASK_TIMEOUT_MINUTES
    if timeout_minutes <= 0:
        return {"requeued": 0, "failed": 0}

    cutoff = utc_now() - timedelta(minutes=timeout_minutes)
    query = (
        db.query(Task)
        .filter(Task.status == "processing")
        .filter(Task.locked_at.isnot(None))
        .filter(Task.locked_at < cutoff)
        .order_by(Task.locked_at.asc(), Task.id.asc())
        .limit(limit)
    )

    try:
        stale_tasks = query.with_for_update(skip_locked=True).all()
    except TypeError:
        stale_tasks = query.all()

    requeued = 0
    failed = 0

    for task in stale_tasks:
        last_seen = _as_aware(task.locked_at)
        message = (
            "Background task timed out because worker heartbeat stopped "
            f"for more than {timeout_minutes} minutes."
        )

        if task.attempts < task.max_attempts:
            task.status = "queued"
            task.locked_at = None
            task.error_message = message

            if task.task_type == TASK_PARSE_OVERVIEW:
                paper = db.query(Paper).filter(Paper.id == task.paper_id).first()
                _mark_parse_overview_paper_queued(paper, message)
            elif task.task_type == TASK_TRANSLATE_ZH:
                paper = db.query(Paper).filter(Paper.id == task.paper_id).first()
                _mark_translate_zh_paper_queued(paper, message)
            elif task.task_type == TASK_REGENERATE_OVERVIEW:
                paper = db.query(Paper).filter(Paper.id == task.paper_id).first()
                _mark_regenerate_overview_paper_queued(paper, message)

            requeued += 1
            logger.warning(
                "Reclaimed stale task and requeued task_id=%s task_type=%s paper_id=%s attempt=%s/%s last_heartbeat=%s",
                task.id,
                task.task_type,
                task.paper_id,
                task.attempts,
                task.max_attempts,
                last_seen,
            )
            continue

        task.status = "failed"
        task.locked_at = None
        task.finished_at = utc_now()
        task.error_message = message

        if task.task_type == TASK_PARSE_OVERVIEW:
            paper = db.query(Paper).filter(Paper.id == task.paper_id).first()
            _mark_parse_overview_paper_failed(paper, message)
        elif task.task_type == TASK_TRANSLATE_ZH:
            paper = db.query(Paper).filter(Paper.id == task.paper_id).first()
            _mark_translate_zh_paper_failed(paper, message)
        elif task.task_type == TASK_REGENERATE_OVERVIEW:
            paper = db.query(Paper).filter(Paper.id == task.paper_id).first()
            _mark_regenerate_overview_paper_failed(paper, message)

        failed += 1
        logger.error(
            "Stale task reached max attempts and was marked failed task_id=%s task_type=%s paper_id=%s attempts=%s last_heartbeat=%s",
            task.id,
            task.task_type,
            task.paper_id,
            task.attempts,
            last_seen,
        )

    if stale_tasks:
        db.commit()

    return {"requeued": requeued, "failed": failed}



# Internal helper for auto create translate zh task after parse success.
def _auto_create_translate_zh_task_after_parse_success(db: Session, paper: Paper | None) -> Task | None:
    """Queue Chinese translation after parse + initial overview are both complete.

    This is intentionally called from mark_task_completed() for the parse_overview
    task, not from process_parse_overview_task(). That way the parse task is
    marked completed and the translate_zh task is created in the same commit,
    avoiding a short window where another worker can claim translation while the
    parse_overview task is still marked processing.
    """
    if not paper:
        return None

    if not getattr(settings, "AUTO_TRANSLATE_AFTER_PARSE", False):
        return None

    if paper.parse_status != "processed" or paper.overview_status != "completed":
        logger.info(
            "Auto translation skipped because paper is not ready paper_id=%s parse_status=%s overview_status=%s",
            paper.id,
            paper.parse_status,
            paper.overview_status,
        )
        return None

    if paper.zh_translation_status in ("queued", "processing", "completed"):
        logger.info(
            "Auto translation skipped because translation status is already %s paper_id=%s",
            paper.zh_translation_status,
            paper.id,
        )
        return None

    if paper.zh_translation_status == "failed":
        logger.info(
            "Auto translation skipped because previous translation failed paper_id=%s",
            paper.id,
        )
        return None

    existing = get_active_task_for_paper(
        db,
        paper_id=paper.id,
        task_type=TASK_TRANSLATE_ZH,
    )
    if existing:
        return existing

    _mark_translate_zh_paper_queued(paper)
    task = create_task(
        db,
        task_type=TASK_TRANSLATE_ZH,
        paper_id=paper.id,
        user_id=paper.user_id,
        payload={
            "language": "zh",
            "trigger": "auto_after_parse",
        },
    )
    logger.info(
        "Auto translation task queued after parse completion task_id=%s paper_id=%s user_id=%s",
        task.id,
        paper.id,
        paper.user_id,
    )
    return task


# Mark a task completed and run any completion-side effects.
def mark_task_completed(db: Session, task: Task) -> None:
    task.status = "completed"
    task.error_message = None
    task.locked_at = None
    task.finished_at = utc_now()

    if task.task_type == TASK_PARSE_OVERVIEW:
        paper = db.query(Paper).filter(Paper.id == task.paper_id).first()
        _auto_create_translate_zh_task_after_parse_success(db, paper)

    elif task.task_type == TASK_REGENERATE_OVERVIEW:
        paper = db.query(Paper).filter(Paper.id == task.paper_id).first()
        _mark_regenerate_overview_paper_completed(paper)

    db.commit()
    logger.info("Task completed task_id=%s task_type=%s paper_id=%s", task.id, task.task_type, task.paper_id)



# Retry or fail a task after converting the exception into a user-facing message.
def mark_task_failed(db: Session, task: Task, error: Exception | str) -> None:
    message, retryable = classify_task_error(error)
    raw_error = _short(str(error), 1000)

    if retryable and task.attempts < task.max_attempts:
        task.status = "queued"
        task.error_message = message
        task.locked_at = None

        if task.task_type == TASK_PARSE_OVERVIEW:
            paper = db.query(Paper).filter(Paper.id == task.paper_id).first()
            _mark_parse_overview_paper_queued(paper, message)
        elif task.task_type == TASK_TRANSLATE_ZH:
            paper = db.query(Paper).filter(Paper.id == task.paper_id).first()
            _mark_translate_zh_paper_queued(paper, message)
        elif task.task_type == TASK_REGENERATE_OVERVIEW:
            paper = db.query(Paper).filter(Paper.id == task.paper_id).first()
            _mark_regenerate_overview_paper_queued(paper, message)

        db.commit()
        logger.warning(
            "Task failed and requeued task_id=%s task_type=%s paper_id=%s attempt=%s/%s user_message=%s raw_error=%s",
            task.id,
            task.task_type,
            task.paper_id,
            task.attempts,
            task.max_attempts,
            message,
            raw_error,
        )
        return

    task.status = "failed"
    task.error_message = message
    task.locked_at = None
    task.finished_at = utc_now()

    if task.task_type == TASK_PARSE_OVERVIEW:
        paper = db.query(Paper).filter(Paper.id == task.paper_id).first()
        _mark_parse_overview_paper_failed(paper, message)
    elif task.task_type == TASK_TRANSLATE_ZH:
        paper = db.query(Paper).filter(Paper.id == task.paper_id).first()
        _mark_translate_zh_paper_failed(paper, message)
    elif task.task_type == TASK_REGENERATE_OVERVIEW:
        paper = db.query(Paper).filter(Paper.id == task.paper_id).first()
        _mark_regenerate_overview_paper_failed(paper, message)

    db.commit()
    logger.error(
        "Task permanently failed task_id=%s task_type=%s paper_id=%s attempts=%s retryable=%s user_message=%s raw_error=%s",
        task.id,
        task.task_type,
        task.paper_id,
        task.attempts,
        retryable,
        message,
        raw_error,
    )
