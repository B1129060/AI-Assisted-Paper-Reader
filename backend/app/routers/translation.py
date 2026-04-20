import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.paper import Paper
from app.models.paragraph import Paragraph
from app.models.paper_overview import PaperOverview
from app.services.translation_service import (
    translate_elements_to_zh,
    translate_overview_to_zh,
)

router = APIRouter(prefix="/papers", tags=["Translation"])

TRANSLATION_STALE_MINUTES = 10


def _refresh_stale_translation_status(paper: Paper, db: Session) -> None:
    """
    如果 paper 卡在 processing 太久，視為失敗。
    """
    if paper.zh_translation_status != "processing":
        return

    if not paper.zh_translation_started_at:
        paper.zh_translation_status = "failed"
        db.commit()
        db.refresh(paper)
        return

    now = datetime.now(timezone.utc)
    started_at = paper.zh_translation_started_at

    # 保險：避免 naive/aware 問題
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)

    if now - started_at > timedelta(minutes=TRANSLATION_STALE_MINUTES):
        paper.zh_translation_status = "failed"
        db.commit()
        db.refresh(paper)


@router.post("/{paper_id}/translate-zh")
def translate_paper_to_zh(paper_id: int, db: Session = Depends(get_db)):
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found.")

    _refresh_stale_translation_status(paper, db)

    overview = (
        db.query(PaperOverview)
        .filter(PaperOverview.paper_id == paper_id)
        .first()
    )
    if not overview:
        raise HTTPException(status_code=404, detail="Paper overview not found.")

    paragraphs = (
        db.query(Paragraph)
        .filter(Paragraph.paper_id == paper_id)
        .order_by(Paragraph.paragraph_index.asc())
        .all()
    )

    # 已完成就直接回
    if paper.zh_translation_status == "completed":
        return {
            "paper_id": paper_id,
            "status": "already_exists",
        }

    # 如果現在真的正在處理中
    if paper.zh_translation_status == "processing":
        return {
            "paper_id": paper_id,
            "status": "processing",
        }

    try:
        paper.zh_translation_status = "processing"
        paper.zh_translation_started_at = datetime.now(timezone.utc)
        paper.zh_translation_finished_at = None
        db.commit()
        db.refresh(paper)

        elements = []
        for p in paragraphs:
            try:
                key_points = json.loads(p.key_points) if p.key_points else None
            except Exception:
                key_points = None

            try:
                items = json.loads(p.items) if p.items else None
            except Exception:
                items = None

            elements.append({
                "id": p.paragraph_index,
                "type": p.type,
                "level": p.level,
                "text": p.text,
                "summary": p.summary,
                "key_points": key_points,
                "items": items,
            })

        translated_elements = translate_elements_to_zh(elements)

        for p in paragraphs:
            tr = translated_elements.get(p.paragraph_index)
            if not tr:
                continue

            if tr.get("text_zh") is not None:
                p.text_zh = tr["text_zh"]

            if tr.get("summary_zh") is not None:
                p.summary_zh = tr["summary_zh"]

            if tr.get("key_points_zh") is not None:
                p.key_points_zh = json.dumps(tr["key_points_zh"], ensure_ascii=False)

            if tr.get("items_zh") is not None:
                p.items_zh = json.dumps(tr["items_zh"], ensure_ascii=False)

        overview_payload = {
            "abstract_summary": overview.abstract_summary,
            "overall_summary": overview.overall_summary,
            "overall_key_points": json.loads(overview.overall_key_points),
            "highlight_summaries": json.loads(overview.highlight_summaries),
            "section_summaries": json.loads(overview.section_summaries),
        }

        translated_overview = translate_overview_to_zh(overview_payload)

        overview.abstract_summary_zh = translated_overview["abstract_summary_zh"]
        overview.overall_summary_zh = translated_overview["overall_summary_zh"]
        overview.overall_key_points_zh = json.dumps(
            translated_overview["overall_key_points_zh"],
            ensure_ascii=False
        )
        overview.highlight_summaries_zh = json.dumps(
            translated_overview["highlight_summaries_zh"],
            ensure_ascii=False
        )
        overview.section_summaries_zh = json.dumps(
            translated_overview["section_summaries_zh"],
            ensure_ascii=False
        )

        paper.zh_translation_status = "completed"
        paper.zh_translation_finished_at = datetime.now(timezone.utc)
        db.commit()

        return {
            "paper_id": paper_id,
            "status": "translated",
        }

    except Exception as e:
        db.rollback()

        try:
            paper = db.query(Paper).filter(Paper.id == paper_id).first()
            if paper:
                paper.zh_translation_status = "failed"
                paper.zh_translation_finished_at = None
                db.commit()
        except Exception:
            db.rollback()

        raise HTTPException(status_code=500, detail=f"Chinese translation failed: {str(e)}")