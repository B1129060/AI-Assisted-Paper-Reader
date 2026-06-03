# API route for validating PDF uploads, storing files, creating paper rows, and queueing parse tasks.

import os
import shutil
import uuid
import logging
from datetime import timezone, datetime

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.paper import Paper
from app.schemas.paper import UploadResponse
from app.config import settings

from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.resource_guard import ensure_can_upload_paper
from app.services.task_service import create_parse_overview_task

router = APIRouter(prefix="/upload", tags=["Upload"])
logger = logging.getLogger(__name__)

UPLOAD_DIR = str(settings.upload_dir_path)
INCOMING_DIR = os.path.join(UPLOAD_DIR, "_incoming")
os.makedirs(INCOMING_DIR, exist_ok=True)


# Build the final per-user/per-paper upload directory path.
def _get_paper_upload_dir(user_id: int, paper_id: int) -> str:
    return os.path.join(UPLOAD_DIR, f"user_{user_id}", f"paper_{paper_id}")


# Build the final stored PDF path for a paper.
def _get_paper_pdf_path(user_id: int, paper_id: int) -> str:
    return os.path.join(_get_paper_upload_dir(user_id, paper_id), "original.pdf")


# Remove a failed upload file or paper directory after rollback.
def _cleanup_uploaded_file_path(file_path: str | None, user_id: int | None = None, paper_id: int | None = None) -> None:
    if user_id is not None and paper_id is not None:
        paper_dir = _get_paper_upload_dir(user_id, paper_id)
        if os.path.isdir(paper_dir):
            shutil.rmtree(paper_dir, ignore_errors=True)

            user_dir = os.path.dirname(paper_dir)
            try:
                os.rmdir(user_dir)
            except OSError:
                pass
            return

    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass

# Validate the uploaded filename, extension, and content type.
def _validate_pdf_upload_metadata(file: UploadFile) -> str:
    original_filename = file.filename or ""
    if not original_filename.strip():
        raise HTTPException(status_code=400, detail="請選擇要上傳的 PDF 檔案。")

    if len(original_filename) > settings.MAX_FILENAME_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"檔名過長，請將檔名縮短到 {settings.MAX_FILENAME_LENGTH} 個字元以內。",
        )

    if not original_filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="只能上傳 PDF 檔案。")

    content_type = (file.content_type or "").lower()
    allowed_content_types = {"", "application/pdf", "application/x-pdf", "application/octet-stream"}
    if content_type not in allowed_content_types:
        raise HTTPException(
            status_code=400,
            detail="檔案類型不是 PDF，請確認後重新上傳。",
        )

    return original_filename


# Stream the PDF to disk while validating header and size limits.
def _save_and_validate_pdf_file(file: UploadFile, save_path: str) -> int:
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    chunk_size = settings.PDF_UPLOAD_CHUNK_BYTES
    total_bytes = 0

    try:
        first_chunk = file.file.read(min(chunk_size, max_bytes + 1))
        if not first_chunk:
            raise HTTPException(status_code=400, detail="上傳的 PDF 檔案是空的。")

        if not first_chunk.startswith(b"%PDF"):
            raise HTTPException(
                status_code=400,
                detail="檔案內容不是有效的 PDF，請確認檔案後重新上傳。",
            )

        with open(save_path, "wb") as buffer:
            buffer.write(first_chunk)
            total_bytes += len(first_chunk)

            if total_bytes > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"PDF 檔案過大，單檔上限為 {settings.MAX_UPLOAD_MB} MB。",
                )

            while True:
                chunk = file.file.read(chunk_size)
                if not chunk:
                    break

                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"PDF 檔案過大，單檔上限為 {settings.MAX_UPLOAD_MB} MB。",
                    )

                buffer.write(chunk)

        return total_bytes

    except HTTPException:
        if os.path.exists(save_path):
            os.remove(save_path)
        raise
    except Exception as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")


@router.post("/pdf", response_model=UploadResponse)
# Validate upload, create the paper row, move the PDF, and queue parse_overview.
async def upload_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    original_filename = file.filename or ""
    save_path: str | None = None

    try:
        original_filename = _validate_pdf_upload_metadata(file)
        logger.info(
            "Upload requested user_id=%s filename=%s content_type=%s",
            current_user.id,
            original_filename,
            file.content_type,
        )
        ensure_can_upload_paper(db, current_user)

        unique_filename = f"{uuid.uuid4()}.pdf"
        save_path = os.path.join(INCOMING_DIR, unique_filename)
        uploaded_bytes = _save_and_validate_pdf_file(file, save_path)
        logger.info(
            "Upload stored in incoming user_id=%s filename=%s bytes=%s path=%s",
            current_user.id,
            original_filename,
            uploaded_bytes,
            save_path,
        )
    except HTTPException as exc:
        log_method = logger.error if exc.status_code >= 500 else logger.warning
        log_method(
            "Upload rejected user_id=%s filename=%s content_type=%s status_code=%s reason=%s",
            current_user.id,
            original_filename,
            file.content_type,
            exc.status_code,
            exc.detail,
        )
        if save_path:
            _cleanup_uploaded_file_path(save_path)
        raise

    new_paper = None

    try:
        new_paper = Paper(
            user_id=current_user.id,
            title=original_filename,
            original_filename=original_filename,
            stored_file_path=save_path,
            parse_status="queued",
            parse_error=None,
            parse_started_at=None,
            parse_finished_at=None,
            overview_status="queued",
            overview_error=None,
            overview_started_at=None,
            overview_finished_at=None,
            last_error_message=None,
        )

        db.add(new_paper)
        db.commit()
        db.refresh(new_paper)
        logger.info("Paper record created user_id=%s paper_id=%s filename=%s", current_user.id, new_paper.id, original_filename)

        final_pdf_path = _get_paper_pdf_path(current_user.id, new_paper.id)
        os.makedirs(os.path.dirname(final_pdf_path), exist_ok=True)
        os.replace(save_path, final_pdf_path)
        save_path = None

        new_paper.stored_file_path = final_pdf_path
        create_parse_overview_task(db, paper=new_paper, user=current_user)
        db.commit()
        db.refresh(new_paper)
        logger.info(
            "Upload queued parse_overview task user_id=%s paper_id=%s path=%s",
            current_user.id,
            new_paper.id,
            final_pdf_path,
        )

        return {
            "paper_id": new_paper.id,
            "title": new_paper.title or new_paper.original_filename,
            "original_filename": new_paper.original_filename,
            "parse_status": new_paper.parse_status,
            "parse_error": new_paper.parse_error,
            "overview_status": new_paper.overview_status,
            "overview_error": new_paper.overview_error,
            "zh_translation_status": new_paper.zh_translation_status,
            "zh_translation_error": new_paper.zh_translation_error,
            "export_status": new_paper.export_status,
            "export_error": new_paper.export_error,
            "last_error_message": new_paper.last_error_message,
            "pdf_url": f"/papers/{new_paper.id}/pdf",
            "elements": [],
        }

    except Exception as e:
        logger.exception(
            "Upload queueing failed user_id=%s paper_id=%s filename=%s",
            current_user.id,
            getattr(new_paper, "id", None),
            original_filename,
        )

        db.rollback()

        if new_paper is not None:
            _cleanup_uploaded_file_path(
                new_paper.stored_file_path,
                user_id=current_user.id,
                paper_id=new_paper.id,
            )
            try:
                db.delete(new_paper)
                db.commit()
            except Exception:
                db.rollback()
        else:
            _cleanup_uploaded_file_path(save_path)

        raise HTTPException(status_code=500, detail=f"Failed to queue paper processing: {str(e)}")
