import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.logging_config import setup_logging
from app.database import Base, engine, SessionLocal
from app.routers import upload, papers, overview, translation, paragraphs, highlights

from app.models.paper import Paper
from app.models.paragraph import Paragraph
from app.models.paper_overview import PaperOverview
from app.models.highlight import TextHighlight, PdfHighlight
from app.models.task import Task
from app.services.status_service import repair_and_refresh_all_processing_papers
from app.services.storage_cleanup_service import run_startup_storage_cleanup

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Paper Reader MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)


@app.on_event("startup")
def recover_stale_processing_tasks_on_startup():
    """Repair paper/task consistency after a backend restart.

    The worker consumes rows from the tasks table. If a paper says it is
    queued/processing but the matching task row is missing, recreate a safe
    background task so the paper does not stay stuck forever. Truly stale
    paper-level processing states are still finalized as failed when there is
    no matching active task.
    """
    db = SessionLocal()
    try:
        recovery = repair_and_refresh_all_processing_papers(db)
        repaired_count = recovery["repaired_missing_tasks"]
        stale_failed_count = recovery["stale_failed_papers"]

        if repaired_count or stale_failed_count:
            logger.warning(
                "Paper/task startup recovery completed repaired_missing_tasks=%s stale_failed_papers=%s",
                repaired_count,
                stale_failed_count,
            )
        else:
            logger.info("No paper/task startup recovery needed.")

        run_startup_storage_cleanup(db)
    except Exception:
        db.rollback()
        logger.exception("Failed to recover paper/task consistency on startup.")
    finally:
        db.close()

app.include_router(upload.router)
app.include_router(papers.router)
app.include_router(overview.router)
app.include_router(translation.router)
app.include_router(paragraphs.router)
app.include_router(highlights.router)


@app.get("/")
def root():
    return {"message": "Paper Reader API is running"}
