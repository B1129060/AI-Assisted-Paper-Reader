import os
import shutil
import uuid
import json
from pathlib import Path
import traceback

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.paper import Paper
from app.models.paragraph import Paragraph
from app.schemas.paper import UploadResponse
from app.services.paper_processor import process_uploaded_paper

from app.models.paper_overview import PaperOverview
from app.services.overview_generator import (
    generate_overview,
    generate_section_summaries,
    generate_abstract_summary,
)

router = APIRouter(prefix="/upload", tags=["Upload"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/pdf", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    unique_filename = f"{uuid.uuid4()}.pdf"
    save_path = os.path.join(UPLOAD_DIR, unique_filename)

    try:
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    new_paper = None

    try:
        new_paper = Paper(
            title=file.filename,
            original_filename=file.filename,
            stored_file_path=save_path,
            parse_status="processing",
        )

        db.add(new_paper)
        db.commit()
        db.refresh(new_paper)

        result = process_uploaded_paper(
            paper_id=new_paper.id,
            pdf_path=save_path,
            original_filename=file.filename,
            debug=True,
        )

        elements = result.get("elements", [])

        db.query(Paragraph).filter(Paragraph.paper_id == new_paper.id).delete()
        db.flush()

        returned_elements = []

        # 檢查 Paragraph model 是否已有 pdf_locations 欄位
        paragraph_has_pdf_locations = hasattr(Paragraph, "pdf_locations")

        for idx, el in enumerate(elements):
            el_type = el.get("type", "paragraph")
            text = el.get("text")
            level = el.get("level")
            summary = el.get("summary")
            key_points = el.get("key_points")
            intro_text = el.get("intro_text")
            items = el.get("items")
            section_title = el.get("section_title")

            page_number = el.get("page_number")
            pdf_rects = el.get("pdf_rects") or []
            pdf_locations = el.get("pdf_locations") or []

            if el_type == "heading":
                content = text or ""
            elif el_type == "bullet_list":
                parts = []
                if intro_text:
                    parts.append(intro_text)
                if items:
                    parts.extend(items)
                content = "\n".join(parts)
            else:
                content = text or ""

            paragraph_kwargs = dict(
                paper_id=new_paper.id,
                paragraph_index=el.get("id", idx),
                content=content,
                type=el_type,
                section_title=section_title,
                text=text,
                level=level,
                summary=summary,
                key_points=json.dumps(key_points, ensure_ascii=False) if key_points is not None else None,
                intro_text=intro_text,
                items=json.dumps(items, ensure_ascii=False) if items is not None else None,
                page_number=page_number,
                pdf_rects=json.dumps(pdf_rects, ensure_ascii=False) if pdf_rects is not None else None,
            )

            # 只有當 DB model 真的有這個欄位時才寫入，避免舊 DB/model 炸掉
            if paragraph_has_pdf_locations:
                paragraph_kwargs["pdf_locations"] = (
                    json.dumps(pdf_locations, ensure_ascii=False)
                    if pdf_locations is not None else None
                )

            paragraph_row = Paragraph(**paragraph_kwargs)

            db.add(paragraph_row)
            db.flush()

            returned_elements.append({
                "id": paragraph_row.paragraph_index,
                "paragraph_id": paragraph_row.id,
                "type": paragraph_row.type,
                "text": paragraph_row.text,
                "summary": paragraph_row.summary,
                "key_points": key_points,
                "level": paragraph_row.level,
                "intro_text": paragraph_row.intro_text,
                "items": items,
                "page_number": paragraph_row.page_number,
                "pdf_rects": pdf_rects,
                "pdf_locations": pdf_locations,
            })

        db.commit()

        try:
            print("DEBUG: elements ready, count =", len(elements))

            overview_data = generate_overview(elements)
            print("DEBUG: overview generated")

            section_summaries = generate_section_summaries(elements)
            print("DEBUG: section summaries generated")

            abstract_summary = generate_abstract_summary(elements)
            print("DEBUG: abstract summary generated")

            db.query(PaperOverview).filter(PaperOverview.paper_id == new_paper.id).delete()
            print("DEBUG: old overview deleted")

            overview_row = PaperOverview(
                paper_id=new_paper.id,
                language="en",
                abstract_summary=abstract_summary,
                overall_summary=overview_data["overall_summary"],
                overall_key_points=json.dumps(overview_data["overall_key_points"], ensure_ascii=False),
                highlight_element_ids=json.dumps(overview_data["highlight_element_ids"], ensure_ascii=False),
                highlight_summaries=json.dumps(overview_data["highlight_summaries"], ensure_ascii=False),
                section_summaries=json.dumps(section_summaries, ensure_ascii=False),
            )
            db.add(overview_row)
            print("DEBUG: overview row added")

            db.commit()

        except Exception as overview_error:
            db.rollback()
            print("OVERVIEW ERROR:", repr(overview_error))

        new_paper.parse_status = "processed"
        db.commit()
        db.refresh(new_paper)

        pdf_filename = Path(new_paper.stored_file_path).name if new_paper.stored_file_path else ""

        return {
            "paper_id": new_paper.id,
            "title": new_paper.title or new_paper.original_filename,
            "original_filename": new_paper.original_filename,
            "parse_status": new_paper.parse_status,
            "pdf_url": f"/uploads/{pdf_filename}" if pdf_filename else "",
            "elements": returned_elements,
        }

    except Exception as e:
        traceback.print_exc()
        print("UPLOAD ERROR:", repr(e))

        db.rollback()

        if new_paper is not None:
            try:
                new_paper.parse_status = "failed"
                db.commit()
            except Exception:
                db.rollback()

        if os.path.exists(save_path):
            os.remove(save_path)

        raise HTTPException(status_code=500, detail=f"Paper processing failed: {str(e)}")