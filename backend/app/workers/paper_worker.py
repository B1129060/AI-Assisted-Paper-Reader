# Queue consumer loop for parse, translation, and overview regeneration tasks.

import logging
import threading
import time

from app.config import settings
from app.database import SessionLocal
from app.models.task import Task
from app.services.paper_processing_service import process_parse_overview_task
from app.services.translation_service import process_translate_zh_task
from app.services.overview_regenerator import process_regenerate_overview_task
from app.services.task_service import (
    TASK_PARSE_OVERVIEW,
    TASK_TRANSLATE_ZH,
    TASK_REGENERATE_OVERVIEW,
    claim_next_queued_task,
    mark_task_completed,
    mark_task_failed,
    reclaim_stale_processing_tasks,
    refresh_task_heartbeat,
)

logger = logging.getLogger(__name__)


# Start a daemon heartbeat thread for the claimed task.
def _start_heartbeat(task_id: int) -> tuple[threading.Event, threading.Thread]:
    stop_event = threading.Event()
    interval = max(1, settings.WORKER_HEARTBEAT_INTERVAL_SECONDS)

    def heartbeat_loop() -> None:
        # Send the first heartbeat after one interval; claim_next_queued_task()
        # already set locked_at immediately when the task was claimed.
        while not stop_event.wait(interval):
            db = SessionLocal()
            try:
                refresh_task_heartbeat(db, task_id)
            except Exception:
                logger.exception("Failed to refresh task heartbeat task_id=%s", task_id)
                db.rollback()
            finally:
                db.close()

    thread = threading.Thread(
        target=heartbeat_loop,
        name=f"task-heartbeat-{task_id}",
        daemon=True,
    )
    thread.start()
    return stop_event, thread


# Dispatch one claimed task to the service that owns its task type.
def process_task(task: Task) -> None:
    db = SessionLocal()
    try:
        if task.task_type == TASK_PARSE_OVERVIEW:
            process_parse_overview_task(db, task.paper_id)
            return

        if task.task_type == TASK_TRANSLATE_ZH:
            process_translate_zh_task(db, task.paper_id, task.user_id)
            return

        if task.task_type == TASK_REGENERATE_OVERVIEW:
            process_regenerate_overview_task(db, task.paper_id)
            return

        raise ValueError(f"Unsupported task type: {task.task_type}")
    finally:
        db.close()


# Recover stale work, claim one queued task, and process it once.
def run_worker_once() -> bool:
    db = SessionLocal()
    try:
        reclaimed = reclaim_stale_processing_tasks(db)
        if reclaimed["requeued"] or reclaimed["failed"]:
            logger.warning(
                "Stale task recovery completed requeued=%s failed=%s",
                reclaimed["requeued"],
                reclaimed["failed"],
            )

        task = claim_next_queued_task(db)
    finally:
        db.close()

    if not task:
        return False

    stop_heartbeat, heartbeat_thread = _start_heartbeat(task.id)
    db = SessionLocal()
    try:
        process_task(task)
        fresh_task = db.query(Task).filter(Task.id == task.id).first()
        if fresh_task:
            mark_task_completed(db, fresh_task)
        return True
    except Exception as e:
        logger.exception("Worker task failed task_id=%s task_type=%s paper_id=%s", task.id, task.task_type, task.paper_id)
        fresh_task = db.query(Task).filter(Task.id == task.id).first()
        if fresh_task:
            mark_task_failed(db, fresh_task, e)
        return True
    finally:
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=2)
        db.close()


# Run the worker polling loop until the process is stopped.
def run_worker_forever() -> None:
    logger.info(
        "Paper worker started poll_interval_seconds=%s max_attempts=%s task_timeout_minutes=%s heartbeat_interval_seconds=%s",
        settings.WORKER_POLL_INTERVAL_SECONDS,
        settings.WORKER_MAX_ATTEMPTS,
        settings.WORKER_TASK_TIMEOUT_MINUTES,
        settings.WORKER_HEARTBEAT_INTERVAL_SECONDS,
    )

    while True:
        did_work = run_worker_once()
        if not did_work:
            time.sleep(settings.WORKER_POLL_INTERVAL_SECONDS)
