import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.paragraph import Paragraph
from app.models.paper_overview import PaperOverview
from app.models.highlight import TextHighlight, PdfHighlight
from app.schemas.paragraph_edit import (
    ParagraphUpdateRequest,
    BulletListUpdateRequest,
    ParagraphInsertRequest,
    ParagraphUpdateResponse,
)
from app.services.edit_service import (
    regenerate_paragraph_fields,
    regenerate_bullet_fields,
    regenerate_section_summary_en,
    regenerate_section_summary_zh,
    update_section_summary_in_overview,
    build_section_summaries_for_regeneration,
)
from app.services.translation_service import translate_elements_to_zh


router = APIRouter(prefix="/paragraphs", tags=["Paragraphs"])


def _rebuild_bullet_content(intro_text: str | None, items: list[str]) -> str:
    parts = []
    if intro_text and intro_text.strip():
        parts.append(intro_text.strip())
    parts.extend([str(x).strip() for x in items if str(x).strip()])
    return "\n".join(parts)


def _refresh_section_summaries(db: Session, paragraph: Paragraph) -> None:
    if not paragraph.section_title:
        return

    same_section_rows = (
        db.query(Paragraph)
        .filter(
            Paragraph.paper_id == paragraph.paper_id,
            Paragraph.section_title == paragraph.section_title,
            Paragraph.type.in_(["paragraph", "bullet_list"]),
        )
        .order_by(Paragraph.paragraph_index.asc())
        .all()
    )

    paragraph_summaries_en = [p.summary for p in same_section_rows if p.summary]
    paragraph_summaries_zh = [p.summary_zh for p in same_section_rows if p.summary_zh]

    paragraph_summaries_en, paragraph_summaries_zh = build_section_summaries_for_regeneration(
        paragraph_summaries_en=paragraph_summaries_en,
        paragraph_summaries_zh=paragraph_summaries_zh,
    )

    if paragraph_summaries_en:
        section_summary_en = regenerate_section_summary_en(
            paragraph.section_title,
            paragraph_summaries_en,
        )

        section_summary_zh = regenerate_section_summary_zh(
            paragraph.section_title,
            paragraph_summaries_zh,
        )

        update_section_summary_in_overview(
            db=db,
            paper_id=paragraph.paper_id,
            section_title=paragraph.section_title,
            section_summary_en=section_summary_en,
            section_summary_zh=section_summary_zh,
        )

        db.commit()


def _shift_paragraph_indices_after_insert(db: Session, paper_id: int, after_index: int) -> None:
    rows = (
        db.query(Paragraph)
        .filter(
            Paragraph.paper_id == paper_id,
            Paragraph.paragraph_index > after_index,
        )
        .order_by(Paragraph.paragraph_index.desc())
        .all()
    )

    for row in rows:
        row.paragraph_index += 1


def _shift_paragraph_indices_after_delete(db: Session, paper_id: int, deleted_index: int) -> None:
    rows = (
        db.query(Paragraph)
        .filter(
            Paragraph.paper_id == paper_id,
            Paragraph.paragraph_index > deleted_index,
        )
        .order_by(Paragraph.paragraph_index.asc())
        .all()
    )

    for row in rows:
        row.paragraph_index -= 1


def _delete_paragraph_text_highlights(
    db: Session,
    paragraph_id: int,
    field_names: list[str],
) -> None:
    (
        db.query(TextHighlight)
        .filter(
            TextHighlight.paragraph_id == paragraph_id,
            TextHighlight.scope == "paragraph",
            TextHighlight.field_name.in_(field_names),
        )
        .delete(synchronize_session=False)
    )


def _delete_paragraph_pdf_highlights(
    db: Session,
    paragraph_id: int,
) -> None:
    (
        db.query(PdfHighlight)
        .filter(PdfHighlight.paragraph_id == paragraph_id)
        .delete(synchronize_session=False)
    )


def _delete_related_section_summary_highlights_for_paragraph(
    db: Session,
    paper_id: int,
    section_title: str | None,
) -> None:
    """
    只刪除和目前 paragraph / bullet 所屬 section 對應的 section_summary highlights。
    不會把整篇 paper 的所有 section_summary highlights 全刪。
    """
    if not section_title:
        return

    overview = (
        db.query(PaperOverview)
        .filter(PaperOverview.paper_id == paper_id)
        .first()
    )
    if not overview:
        return

    raw_section_summaries = overview.section_summaries
    if not raw_section_summaries:
        return

    # section_summaries 可能是 JSON string，也可能已經是 list
    if isinstance(raw_section_summaries, str):
        try:
            section_summaries = json.loads(raw_section_summaries)
        except Exception:
            return
    else:
        section_summaries = raw_section_summaries

    if not isinstance(section_summaries, list):
        return

    normalized_target = section_title.strip().lower()
    matched_index = None

    for idx, item in enumerate(section_summaries):
        if not isinstance(item, dict):
            continue

        sec_title = item.get("section_title")
        if not isinstance(sec_title, str):
            continue

        if sec_title.strip().lower() == normalized_target:
            matched_index = idx
            break

    if matched_index is None:
        return

    (
        db.query(TextHighlight)
        .filter(
            TextHighlight.paper_id == paper_id,
            TextHighlight.scope == "overview",
            TextHighlight.field_name == "section_summary",
            TextHighlight.item_index == matched_index,
        )
        .delete(synchronize_session=False)
    )


@router.put("/{paragraph_id}", response_model=ParagraphUpdateResponse)
def update_paragraph(
    paragraph_id: int,
    payload: ParagraphUpdateRequest,
    db: Session = Depends(get_db),
):
    paragraph = db.query(Paragraph).filter(Paragraph.id == paragraph_id).first()

    if not paragraph:
        raise HTTPException(status_code=404, detail="Paragraph not found.")

    if paragraph.type != "paragraph":
        raise HTTPException(status_code=400, detail="Only paragraph editing is supported here.")

    paragraph.text = payload.text
    paragraph.content = payload.text

    # 原文、摘要、重點都會被重寫，所以先刪除舊文字高亮
    _delete_paragraph_text_highlights(
        db,
        paragraph.id,
        ["text", "summary", "key_points"],
    )

    # 只刪除和這段所屬章節對應的 section_summary highlights
    _delete_related_section_summary_highlights_for_paragraph(
        db,
        paper_id=paragraph.paper_id,
        section_title=paragraph.section_title,
    )

    paragraph_result = regenerate_paragraph_fields(paragraph.text)
    paragraph.summary = paragraph_result["summary"]
    paragraph.key_points = json.dumps(paragraph_result["key_points"], ensure_ascii=False)

    translated = translate_elements_to_zh([
        {
            "id": paragraph.paragraph_index,
            "type": paragraph.type,
            "level": paragraph.level,
            "text": paragraph.text,
            "summary": paragraph.summary,
            "key_points": paragraph_result["key_points"],
            "items": None,
        }
    ])

    tr = translated.get(paragraph.paragraph_index)
    if tr:
        paragraph.text_zh = tr.get("text_zh")
        paragraph.summary_zh = tr.get("summary_zh")
        paragraph.key_points_zh = json.dumps(tr.get("key_points_zh", []), ensure_ascii=False)

    db.commit()
    db.refresh(paragraph)

    _refresh_section_summaries(db, paragraph)

    return {
        "paragraph_id": paragraph.id,
        "paper_id": paragraph.paper_id,
        "section_title": paragraph.section_title,
        "status": "updated",
    }


@router.put("/{paragraph_id}/bullet-list", response_model=ParagraphUpdateResponse)
def update_bullet_list(
    paragraph_id: int,
    payload: BulletListUpdateRequest,
    db: Session = Depends(get_db),
):
    row = db.query(Paragraph).filter(Paragraph.id == paragraph_id).first()

    if not row:
        raise HTTPException(status_code=404, detail="Paragraph not found.")

    if row.type != "bullet_list":
        raise HTTPException(status_code=400, detail="Only bullet_list editing is supported here.")

    intro_text = (payload.intro_text or "").strip() or None
    items = [str(x).strip() for x in payload.items if str(x).strip()]

    row.intro_text = intro_text
    row.items = json.dumps(items, ensure_ascii=False)
    row.content = _rebuild_bullet_content(intro_text, items)

    # bullet 相關文字與其摘要都會重寫，所以刪除舊文字高亮
    _delete_paragraph_text_highlights(
        db,
        row.id,
        ["intro_text", "item", "summary", "key_points"],
    )

    # 只刪除和這個 bullet 所屬章節對應的 section_summary highlights
    _delete_related_section_summary_highlights_for_paragraph(
        db,
        paper_id=row.paper_id,
        section_title=row.section_title,
    )

    bullet_result = regenerate_bullet_fields(intro_text, items)
    row.summary = bullet_result["summary"]
    row.key_points = json.dumps(bullet_result["key_points"], ensure_ascii=False)

    translated = translate_elements_to_zh([
        {
            "id": row.paragraph_index,
            "type": row.type,
            "level": row.level,
            "text": None,
            "summary": row.summary,
            "key_points": bullet_result["key_points"],
            "items": items,
        }
    ])

    tr = translated.get(row.paragraph_index)
    if tr:
        row.summary_zh = tr.get("summary_zh")
        row.key_points_zh = json.dumps(tr.get("key_points_zh", []), ensure_ascii=False)
        row.items_zh = json.dumps(tr.get("items_zh", []), ensure_ascii=False)

    db.commit()
    db.refresh(row)

    _refresh_section_summaries(db, row)

    return {
        "paragraph_id": row.id,
        "paper_id": row.paper_id,
        "section_title": row.section_title,
        "status": "updated",
    }


@router.post("/{paragraph_id}/insert-after", response_model=ParagraphUpdateResponse)
def insert_paragraph_after(
    paragraph_id: int,
    payload: ParagraphInsertRequest,
    db: Session = Depends(get_db),
):
    anchor = db.query(Paragraph).filter(Paragraph.id == paragraph_id).first()

    if not anchor:
        raise HTTPException(status_code=404, detail="Paragraph not found.")

    if anchor.type not in ["paragraph", "bullet_list"]:
        raise HTTPException(
            status_code=400,
            detail="Only insertion after paragraph or bullet_list is supported for now."
        )

    new_text = (payload.text or "").strip()
    if not new_text:
        raise HTTPException(status_code=400, detail="Inserted paragraph text cannot be empty.")

    _shift_paragraph_indices_after_insert(
        db=db,
        paper_id=anchor.paper_id,
        after_index=anchor.paragraph_index,
    )

    paragraph_result = regenerate_paragraph_fields(new_text)

    new_row = Paragraph(
        paper_id=anchor.paper_id,
        paragraph_index=anchor.paragraph_index + 1,
        content=new_text,
        type="paragraph",
        section_title=anchor.section_title,
        text=new_text,
        level=None,
        summary=paragraph_result["summary"],
        key_points=json.dumps(paragraph_result["key_points"], ensure_ascii=False),
        intro_text=None,
        items=None,
    )
    db.add(new_row)
    db.flush()

    translated = translate_elements_to_zh([
        {
            "id": new_row.paragraph_index,
            "type": new_row.type,
            "level": new_row.level,
            "text": new_row.text,
            "summary": new_row.summary,
            "key_points": paragraph_result["key_points"],
            "items": None,
        }
    ])

    tr = translated.get(new_row.paragraph_index)
    if tr:
        new_row.text_zh = tr.get("text_zh")
        new_row.summary_zh = tr.get("summary_zh")
        new_row.key_points_zh = json.dumps(tr.get("key_points_zh", []), ensure_ascii=False)

    db.commit()
    db.refresh(new_row)

    _refresh_section_summaries(db, new_row)

    return {
        "paragraph_id": new_row.id,
        "paper_id": new_row.paper_id,
        "section_title": new_row.section_title,
        "status": "inserted",
    }


@router.delete("/{paragraph_id}", response_model=ParagraphUpdateResponse)
def delete_paragraph(
    paragraph_id: int,
    db: Session = Depends(get_db),
):
    row = db.query(Paragraph).filter(Paragraph.id == paragraph_id).first()

    if not row:
        raise HTTPException(status_code=404, detail="Paragraph not found.")

    if row.type not in ["paragraph", "bullet_list"]:
        raise HTTPException(
            status_code=400,
            detail="Only paragraph or bullet_list deletion is supported for now."
        )

    paper_id = row.paper_id
    section_title = row.section_title
    deleted_index = row.paragraph_index

    _delete_paragraph_text_highlights(
        db,
        row.id,
        ["text", "summary", "key_points", "intro_text", "item"],
    )
    _delete_paragraph_pdf_highlights(db, row.id)

    db.delete(row)
    db.flush()

    _shift_paragraph_indices_after_delete(
        db=db,
        paper_id=paper_id,
        deleted_index=deleted_index,
    )

    db.commit()

    # 刪除後，如果這個 section 還有其他 paragraph/bullet，就重算摘要
    if section_title:
        remaining = (
            db.query(Paragraph)
            .filter(
                Paragraph.paper_id == paper_id,
                Paragraph.section_title == section_title,
                Paragraph.type.in_(["paragraph", "bullet_list"]),
            )
            .first()
        )

        if remaining:
            _refresh_section_summaries(db, remaining)

    return {
        "paragraph_id": paragraph_id,
        "paper_id": paper_id,
        "section_title": section_title,
        "status": "deleted",
    }