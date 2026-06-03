# Startup storage maintenance for temporary uploads and orphaned paper files.

import logging
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models.paper import Paper

logger = logging.getLogger(__name__)


# Internal helper for as aware timestamp.
def _as_aware_timestamp(timestamp: float) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


# Delete old temporary files left in uploads/_incoming.
def cleanup_stale_incoming_files() -> int:
    """Delete old temporary files in uploads/_incoming.

    These files are created before a paper gets its final
    uploads/user_{user_id}/paper_{paper_id}/original.pdf path. If the backend
    is stopped during upload, a file may remain here with no DB record.
    """
    ttl_hours = settings.INCOMING_FILE_TTL_HOURS
    if ttl_hours <= 0:
        logger.info("Incoming file cleanup skipped because INCOMING_FILE_TTL_HOURS=%s", ttl_hours)
        return 0

    incoming_dir = settings.upload_dir_path / "_incoming"
    if not incoming_dir.exists():
        logger.info("Incoming file cleanup skipped because directory does not exist path=%s", incoming_dir)
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)
    deleted_count = 0

    for path in incoming_dir.iterdir():
        if not path.is_file():
            continue

        try:
            modified_at = _as_aware_timestamp(path.stat().st_mtime)
            if modified_at >= cutoff:
                continue

            path.unlink()
            deleted_count += 1
            logger.warning(
                "Deleted stale incoming upload file path=%s modified_at=%s ttl_hours=%s",
                path,
                modified_at.isoformat(),
                ttl_hours,
            )
        except Exception:
            logger.exception("Failed to delete stale incoming upload file path=%s", path)

    if deleted_count:
        logger.warning("Incoming file cleanup completed deleted_count=%s", deleted_count)
    else:
        logger.info("Incoming file cleanup completed deleted_count=0")

    return deleted_count


# Internal helper for existing paper ids.
def _existing_paper_ids(db: Session) -> set[int]:
    return {paper_id for (paper_id,) in db.query(Paper.id).all()}


# Internal helper for existing stored paths.
def _existing_stored_paths(db: Session) -> set[Path]:
    paths: set[Path] = set()
    for (raw_path,) in db.query(Paper.stored_file_path).all():
        if not raw_path:
            continue
        try:
            paths.add(Path(raw_path).resolve())
        except Exception:
            logger.warning("Failed to normalize stored_file_path value=%s", raw_path)
    return paths


# Internal helper for parse structured paper id.
def _parse_structured_paper_id(paper_dir: Path) -> int | None:
    name = paper_dir.name
    if not name.startswith("paper_"):
        return None
    try:
        return int(name.removeprefix("paper_"))
    except ValueError:
        return None


# Find or optionally delete upload files no longer referenced by the database.
def scan_orphan_uploaded_files(db: Session) -> dict[str, int]:
    """Scan uploaded files that are no longer referenced by the database.

    By default this only logs warnings. Set AUTO_DELETE_ORPHAN_FILES=true to
    remove orphan structured paper directories and orphan legacy root-level PDF
    files automatically.
    """
    if not settings.ENABLE_ORPHAN_FILE_SCAN:
        logger.info("Orphan file scan skipped because ENABLE_ORPHAN_FILE_SCAN=false")
        return {"orphan_dirs": 0, "orphan_files": 0, "deleted": 0}

    upload_root = settings.upload_dir_path
    if not upload_root.exists():
        logger.info("Orphan file scan skipped because upload root does not exist path=%s", upload_root)
        return {"orphan_dirs": 0, "orphan_files": 0, "deleted": 0}

    paper_ids = _existing_paper_ids(db)
    stored_paths = _existing_stored_paths(db)
    auto_delete = settings.AUTO_DELETE_ORPHAN_FILES

    orphan_dirs = 0
    orphan_files = 0
    deleted = 0

    # Structured storage: uploads/user_{user_id}/paper_{paper_id}/
    for user_dir in upload_root.glob("user_*"):
        if not user_dir.is_dir():
            continue

        for paper_dir in user_dir.glob("paper_*"):
            if not paper_dir.is_dir():
                continue

            paper_id = _parse_structured_paper_id(paper_dir)
            if paper_id is not None and paper_id in paper_ids:
                continue

            orphan_dirs += 1
            logger.warning(
                "Orphan structured paper directory found path=%s parsed_paper_id=%s auto_delete=%s",
                paper_dir,
                paper_id,
                auto_delete,
            )

            if auto_delete:
                try:
                    shutil.rmtree(paper_dir)
                    deleted += 1
                    logger.warning("Deleted orphan structured paper directory path=%s", paper_dir)
                except Exception:
                    logger.exception("Failed to delete orphan structured paper directory path=%s", paper_dir)

        if auto_delete:
            try:
                user_dir.rmdir()
            except OSError:
                pass

    # Legacy root-level files: uploads/{uuid}.pdf from older versions.
    for child in upload_root.iterdir():
        if child.name == "_incoming" or child.name.startswith("user_"):
            continue
        if not child.is_file():
            continue

        try:
            child_path = child.resolve()
        except Exception:
            child_path = child

        if child_path in stored_paths:
            continue

        orphan_files += 1
        logger.warning(
            "Orphan uploaded root-level file found path=%s auto_delete=%s",
            child,
            auto_delete,
        )

        if auto_delete:
            try:
                child.unlink()
                deleted += 1
                logger.warning("Deleted orphan uploaded root-level file path=%s", child)
            except Exception:
                logger.exception("Failed to delete orphan uploaded root-level file path=%s", child)

    logger.info(
        "Orphan file scan completed orphan_dirs=%s orphan_files=%s deleted=%s auto_delete=%s",
        orphan_dirs,
        orphan_files,
        deleted,
        auto_delete,
    )

    return {"orphan_dirs": orphan_dirs, "orphan_files": orphan_files, "deleted": deleted}


# Run safe storage cleanup tasks during API startup.
def run_startup_storage_cleanup(db: Session) -> None:
    """Run safe storage maintenance tasks during backend startup."""
    cleanup_stale_incoming_files()
    scan_orphan_uploaded_files(db)
