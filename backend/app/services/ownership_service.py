from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.highlight import PdfHighlight, TextHighlight
from app.models.paper import Paper
from app.models.paragraph import Paragraph
from app.models.user import User


def get_owned_paper_or_404(
    db: Session,
    paper_id: int,
    current_user: User,
) -> Paper:
    """
    Return the paper only when it belongs to the current user.

    Use 404 instead of 403 so callers cannot distinguish between a missing paper
    and a paper owned by another user.
    """
    paper = (
        db.query(Paper)
        .filter(Paper.id == paper_id, Paper.user_id == current_user.id)
        .first()
    )
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found.")
    return paper


def get_owned_paragraph_or_404(
    db: Session,
    paragraph_id: int,
    current_user: User,
) -> Paragraph:
    """
    Return the paragraph only when its parent paper belongs to the current user.
    """
    paragraph = (
        db.query(Paragraph)
        .join(Paper, Paragraph.paper_id == Paper.id)
        .filter(Paragraph.id == paragraph_id, Paper.user_id == current_user.id)
        .first()
    )
    if not paragraph:
        raise HTTPException(status_code=404, detail="Paragraph not found.")
    return paragraph


def ensure_paragraph_belongs_to_owned_paper(
    db: Session,
    paragraph_id: int | None,
    paper_id: int,
    current_user: User,
) -> Paragraph | None:
    """
    Validate optional paragraph_id in highlight requests.

    If a highlight is attached to a paragraph, the paragraph must both belong to
    the current user and belong to the same paper_id carried by the request.
    """
    if paragraph_id is None:
        return None

    paragraph = get_owned_paragraph_or_404(db, paragraph_id, current_user)
    if paragraph.paper_id != paper_id:
        raise HTTPException(
            status_code=400,
            detail="Paragraph does not belong to the specified paper.",
        )
    return paragraph


def get_owned_text_highlight_or_404(
    db: Session,
    highlight_id: int,
    current_user: User,
) -> TextHighlight:
    """
    Return a text highlight only when its parent paper belongs to the current user.
    """
    highlight = (
        db.query(TextHighlight)
        .join(Paper, TextHighlight.paper_id == Paper.id)
        .filter(TextHighlight.id == highlight_id, Paper.user_id == current_user.id)
        .first()
    )
    if not highlight:
        raise HTTPException(status_code=404, detail="Text highlight not found.")
    return highlight


def get_owned_pdf_highlight_or_404(
    db: Session,
    highlight_id: int,
    current_user: User,
) -> PdfHighlight:
    """
    Return a PDF highlight only when its parent paper belongs to the current user.
    """
    highlight = (
        db.query(PdfHighlight)
        .join(Paper, PdfHighlight.paper_id == Paper.id)
        .filter(PdfHighlight.id == highlight_id, Paper.user_id == current_user.id)
        .first()
    )
    if not highlight:
        raise HTTPException(status_code=404, detail="PDF highlight not found.")
    return highlight
