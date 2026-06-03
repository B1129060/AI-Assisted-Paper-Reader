# PDF/ZIP export utilities for original PDFs, annotated PDFs, overviews, paragraphs, and highlights.

import io
import json
import os
import re
import zipfile
from typing import Any

import fitz
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

FONT_NAME = "NotoSansTC"
_FONT_READY = False


# Register the CJK-capable export font once per process.
def ensure_export_font():
    global _FONT_READY
    if _FONT_READY:
        return

    font_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "assets",
        "fonts",
        "NotoSansTC-Regular.ttf",
    )

    if not os.path.exists(font_path):
        raise FileNotFoundError(
            f"Font file not found: {font_path}. Please place NotoSansTC-Regular.ttf there."
        )

    pdfmetrics.registerFont(TTFont(FONT_NAME, font_path))
    _FONT_READY = True


# Convert a paper title or filename into a safe export filename stem.
def safe_filename(name: str) -> str:
    if not name:
        return "paper"
    name = re.sub(r"\.[Pp][Dd][Ff]$", "", name)
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    name = re.sub(r"\s+", "_", name).strip("_")
    return name[:80] or "paper"


# Escape text before passing it to reportlab Paragraph markup.
def escape_text(text: str | None) -> str:
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


# Parse a JSON-string field with a safe default fallback.
def parse_json_field(raw: str | None, default: Any):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


# Build reportlab paragraph styles used by export PDFs.
def build_styles():
    ensure_export_font()
    base = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "ExportTitle",
            parent=base["Title"],
            fontName=FONT_NAME,
            fontSize=22,
            leading=28,
            spaceAfter=14,
            textColor=colors.HexColor("#111111"),
        ),
        "h1": ParagraphStyle(
            "ExportH1",
            parent=base["Heading1"],
            fontName=FONT_NAME,
            fontSize=16,
            leading=22,
            spaceBefore=14,
            spaceAfter=8,
            textColor=colors.HexColor("#111111"),
        ),
        "h2": ParagraphStyle(
            "ExportH2",
            parent=base["Heading2"],
            fontName=FONT_NAME,
            fontSize=13.5,
            leading=19,
            spaceBefore=10,
            spaceAfter=6,
            textColor=colors.HexColor("#1F2937"),
        ),
        "section_heading": ParagraphStyle(
            "SectionHeading",
            parent=base["Heading2"],
            fontName=FONT_NAME,
            fontSize=15,
            leading=21,
            spaceBefore=14,
            spaceAfter=8,
            textColor=colors.HexColor("#0F172A"),
            borderPadding=(0, 0, 4, 0),
        ),
        "paragraph_heading": ParagraphStyle(
            "ParagraphHeading",
            parent=base["Heading3"],
            fontName=FONT_NAME,
            fontSize=14,
            leading=20,
            spaceBefore=12,
            spaceAfter=8,
            textColor=colors.HexColor("#0F172A"),
            borderWidth=0,
        ),
        "label": ParagraphStyle(
            "ExportLabel",
            parent=base["BodyText"],
            fontName=FONT_NAME,
            fontSize=10.2,
            leading=14,
            spaceBefore=4,
            spaceAfter=3,
            textColor=colors.HexColor("#374151"),
        ),
        "body": ParagraphStyle(
            "ExportBody",
            parent=base["BodyText"],
            fontName=FONT_NAME,
            fontSize=10.8,
            leading=18,
            spaceAfter=7,
            textColor=colors.HexColor("#111111"),
        ),
        "small": ParagraphStyle(
            "ExportSmall",
            parent=base["BodyText"],
            fontName=FONT_NAME,
            fontSize=9.8,
            leading=15,
            spaceAfter=4,
            textColor=colors.HexColor("#374151"),
        ),
    }


# Map highlight color names to export background colors.
def color_hex(color: str) -> str:
    return {
        "yellow": "#FFF3A3",
        "green": "#CDECCD",
        "pink": "#F8D1E0",
    }.get(color, "#FFF3A3")


# Apply non-overlapping text highlights to escaped reportlab markup.
def apply_text_highlights(
    text: str | None,
    highlights: list[dict[str, Any]],
) -> str:
    if not text:
        return ""

    if not highlights:
        return escape_text(text)

    valid = []
    for h in sorted(highlights, key=lambda x: x["start_offset"]):
        s = h["start_offset"]
        e = h["end_offset"]
        if s < 0 or e > len(text) or s >= e:
            continue
        if valid and s < valid[-1]["end_offset"]:
            continue
        valid.append(h)

    if not valid:
        return escape_text(text)

    parts: list[str] = []
    cursor = 0

    for h in valid:
        s = h["start_offset"]
        e = h["end_offset"]
        if s > cursor:
            parts.append(escape_text(text[cursor:s]))

        highlighted = escape_text(text[s:e])
        parts.append(
            f'<font backcolor="{color_hex(h["color"])}">{highlighted}</font>'
        )
        cursor = e

    if cursor < len(text):
        parts.append(escape_text(text[cursor:]))

    return "".join(parts)


# Select highlights for one paper field, item, language, and paragraph.
def filter_text_highlights(
    text_highlights: list[dict[str, Any]],
    *,
    paper_id: int,
    paragraph_id: int | None,
    scope: str,
    field_name: str,
    item_index: int | None,
    language: str,
) -> list[dict[str, Any]]:
    return [
        h
        for h in text_highlights
        if h["paper_id"] == paper_id
        and h["paragraph_id"] == paragraph_id
        and h["scope"] == scope
        and h["field_name"] == field_name
        and h["item_index"] == item_index
        and h["language"] == language
    ]


# Draw stored PDF highlights onto the original PDF and return PDF bytes.
def create_annotated_pdf(
    original_pdf_path: str,
    pdf_highlights: list[dict[str, Any]],
) -> bytes:
    doc = fitz.open(original_pdf_path)

    color_map = {
        "yellow": (1.0, 0.92, 0.23),
        "green": (0.30, 0.69, 0.31),
        "pink": (0.96, 0.56, 0.69),
    }

    for h in pdf_highlights:
        page_number = h["page_number"]
        rects = h["rects"]
        color = color_map.get(h["color"], color_map["yellow"])

        if page_number < 1 or page_number > len(doc):
            continue

        page = doc[page_number - 1]
        page_rect = page.rect

        for rect in rects:
            if len(rect) != 4:
                continue

            x0, y0, x1, y1 = rect
            abs_rect = fitz.Rect(
                x0 * page_rect.width,
                y0 * page_rect.height,
                x1 * page_rect.width,
                y1 * page_rect.height,
            )

            annot = page.add_rect_annot(abs_rect)
            annot.set_colors(stroke=color, fill=color)
            annot.set_opacity(0.22)
            annot.update()

    buffer = io.BytesIO()
    doc.save(buffer)
    doc.close()
    buffer.seek(0)
    return buffer.getvalue()


# Build English/Chinese text blocks according to export language mode.
def build_bilingual_blocks(
    *,
    language_mode: str,
    en_label: str,
    en_text: str | None,
    zh_label: str,
    zh_text: str | None,
) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []

    if language_mode in ("en", "both") and en_text:
        blocks.append((en_label, en_text))

    if language_mode in ("zh", "both") and zh_text:
        blocks.append((zh_label, zh_text))

    return blocks


# Render overview content into a standalone PDF.
def create_overview_pdf(
    *,
    paper: dict[str, Any],
    overview_en: dict[str, Any] | None,
    overview_zh: dict[str, Any] | None,
    text_highlights: list[dict[str, Any]],
    language_mode: str,
    include_text_highlights: bool,
) -> bytes:
    styles = build_styles()
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title=paper["display_name"],
    )

    story = []

    story.append(Paragraph(escape_text(paper["display_name"]), styles["title"]))
    story.append(
        Paragraph(
            f"Original file: {escape_text(paper['original_filename'])}",
            styles["small"],
        )
    )
    story.append(Spacer(1, 0.2 * cm))

    def add_text_block(
        title: str,
        field_name: str,
        en_text: str | None,
        zh_text: str | None,
    ):
        blocks = build_bilingual_blocks(
            language_mode=language_mode,
            en_label=title,
            en_text=en_text,
            zh_label="中文",
            zh_text=zh_text,
        )

        if not blocks:
            return

        for lang_label, text in blocks:
            lang = "zh" if lang_label.endswith("中文") else "en"
            highlights = (
                filter_text_highlights(
                    text_highlights,
                    paper_id=paper["paper_id"],
                    paragraph_id=None,
                    scope="overview",
                    field_name=field_name,
                    item_index=None,
                    language=lang,
                )
                if include_text_highlights
                else []
            )

            story.append(Paragraph(escape_text(lang_label), styles["h1"]))
            story.append(Paragraph(apply_text_highlights(text, highlights), styles["body"]))

        story.append(Spacer(1, 0.1 * cm))
        story.append(HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#D1D5DB")))
        story.append(Spacer(1, 0.18 * cm))

    en = overview_en or {}
    zh = overview_zh or {}

    add_text_block(
        "Abstract Summary",
        "abstract_summary",
        en.get("abstract_summary"),
        zh.get("abstract_summary"),
    )

    add_text_block(
        "Paper Overview",
        "overall_summary",
        en.get("overall_summary"),
        zh.get("overall_summary"),
    )

    en_points = en.get("overall_key_points") or []
    zh_points = zh.get("overall_key_points") or []

    if (language_mode in ("en", "both") and en_points) or (
        language_mode in ("zh", "both") and zh_points
    ):
        story.append(Paragraph("Key Points", styles["h1"]))

        if language_mode in ("en", "both") and en_points:

            items = []
            for idx, point in enumerate(en_points):
                highlights = (
                    filter_text_highlights(
                        text_highlights,
                        paper_id=paper["paper_id"],
                        paragraph_id=None,
                        scope="overview",
                        field_name="overall_key_points",
                        item_index=idx,
                        language="en",
                    )
                    if include_text_highlights
                    else []
                )
                items.append(
                    ListItem(
                        Paragraph(apply_text_highlights(point, highlights), styles["body"])
                    )
                )
            story.append(ListFlowable(items, bulletType="bullet", leftIndent=14))
            story.append(Spacer(1, 0.1 * cm))

        if language_mode in ("zh", "both") and zh_points:
            story.append(Paragraph("重點", styles["h1"]))
            items = []
            for idx, point in enumerate(zh_points):
                highlights = (
                    filter_text_highlights(
                        text_highlights,
                        paper_id=paper["paper_id"],
                        paragraph_id=None,
                        scope="overview",
                        field_name="overall_key_points",
                        item_index=idx,
                        language="zh",
                    )
                    if include_text_highlights
                    else []
                )
                items.append(
                    ListItem(
                        Paragraph(apply_text_highlights(point, highlights), styles["body"])
                    )
                )
            story.append(ListFlowable(items, bulletType="bullet", leftIndent=14))

        story.append(Spacer(1, 0.1 * cm))
        story.append(HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#D1D5DB")))
        story.append(Spacer(1, 0.18 * cm))

    en_sections = en.get("section_summaries") or []
    zh_sections = zh.get("section_summaries") or []

    if en_sections or zh_sections:
        story.append(Paragraph("Main Sections", styles["h1"]))

        max_len = max(len(en_sections), len(zh_sections))
        for idx in range(max_len):
            en_sec = en_sections[idx] if idx < len(en_sections) else None
            zh_sec = zh_sections[idx] if idx < len(zh_sections) else None

            section_title = (
                (en_sec or {}).get("section_title")
                or (zh_sec or {}).get("section_title")
                or f"Section {idx + 1}"
            )

            story.append(Paragraph(escape_text(section_title), styles["h2"]))

            if language_mode in ("en", "both") and en_sec:
                highlights = (
                    filter_text_highlights(
                        text_highlights,
                        paper_id=paper["paper_id"],
                        paragraph_id=None,
                        scope="overview",
                        field_name="section_summary",
                        item_index=idx,
                        language="en",
                    )
                    if include_text_highlights
                    else []
                )
                story.append(Paragraph("Summary", styles["label"]))
                story.append(
                    Paragraph(
                        apply_text_highlights(en_sec.get("summary"), highlights),
                        styles["body"],
                    )
                )

            if language_mode in ("zh", "both") and zh_sec:
                highlights = (
                    filter_text_highlights(
                        text_highlights,
                        paper_id=paper["paper_id"],
                        paragraph_id=None,
                        scope="overview",
                        field_name="section_summary",
                        item_index=idx,
                        language="zh",
                    )
                    if include_text_highlights
                    else []
                )
                story.append(Paragraph("總結", styles["label"]))
                story.append(
                    Paragraph(
                        apply_text_highlights(zh_sec.get("summary"), highlights),
                        styles["body"],
                    )
                )

            story.append(Spacer(1, 0.08 * cm))
            story.append(HRFlowable(width="100%", thickness=0.35, color=colors.lightgrey))
            story.append(Spacer(1, 0.12 * cm))

    en_highlights = en.get("highlight_summaries") or []
    zh_highlights = zh.get("highlight_summaries") or []

    if en_highlights or zh_highlights:
        story.append(Paragraph("Highlights", styles["h1"]))

        max_len = max(len(en_highlights), len(zh_highlights))
        for idx in range(max_len):
            en_item = en_highlights[idx] if idx < len(en_highlights) else None
            zh_item = zh_highlights[idx] if idx < len(zh_highlights) else None

            title = (
                (en_item or {}).get("title")
                or (zh_item or {}).get("title")
                or f"Highlight {idx + 1}"
            )
            story.append(Paragraph(escape_text(title), styles["h2"]))

            if language_mode in ("en", "both") and en_item:
                highlights = (
                    filter_text_highlights(
                        text_highlights,
                        paper_id=paper["paper_id"],
                        paragraph_id=None,
                        scope="overview",
                        field_name="highlight_summary",
                        item_index=idx,
                        language="en",
                    )
                    if include_text_highlights
                    else []
                )
                story.append(
                    Paragraph(
                        apply_text_highlights(en_item.get("summary"), highlights),
                        styles["body"],
                    )
                )

            if language_mode in ("zh", "both") and zh_item:
                highlights = (
                    filter_text_highlights(
                        text_highlights,
                        paper_id=paper["paper_id"],
                        paragraph_id=None,
                        scope="overview",
                        field_name="highlight_summary",
                        item_index=idx,
                        language="zh",
                    )
                    if include_text_highlights
                    else []
                )
                story.append(
                    Paragraph(
                        apply_text_highlights(zh_item.get("summary"), highlights),
                        styles["body"],
                    )
                )

            story.append(Spacer(1, 0.08 * cm))
            story.append(HRFlowable(width="100%", thickness=0.35, color=colors.lightgrey))
            story.append(Spacer(1, 0.12 * cm))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# Render paragraph-level content into a standalone PDF.
def create_paragraphs_pdf(
    *,
    paper: dict[str, Any],
    paragraphs: list[dict[str, Any]],
    text_highlights: list[dict[str, Any]],
    language_mode: str,
    include_text_highlights: bool,
) -> bytes:
    styles = build_styles()
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title=f"{paper['display_name']} - Paragraphs",
    )

    story = []
    story.append(Paragraph(escape_text(paper["display_name"]), styles["title"]))
    story.append(Paragraph("Paragraph-level Content", styles["h1"]))

    para_counter = 0

    for p in paragraphs:
        p_type = p["type"]

        if p_type == "heading":
            heading_text = p.get("text") or ""
            heading_zh = p.get("text_zh") or ""

            story.append(Spacer(1, 0.12 * cm))
            story.append(Paragraph(escape_text(heading_text), styles["section_heading"]))
            story.append(Spacer(1, 0.08 * cm))

            if language_mode in ("zh", "both") and heading_zh and heading_zh != heading_text:
                story.append(Paragraph(escape_text(heading_zh), styles["section_heading"]))
                story.append(Spacer(1, 0.08 * cm))

            continue

        para_counter += 1

        # paragraph text
        if p_type == "paragraph":
            if language_mode in ("en", "both") and p.get("text"):
                highlights = (
                    filter_text_highlights(
                        text_highlights,
                        paper_id=paper["paper_id"],
                        paragraph_id=p["paragraph_id"],
                        scope="paragraph",
                        field_name="text",
                        item_index=None,
                        language="en",
                    )
                    if include_text_highlights
                    else []
                )
                story.append(Paragraph("Original Text", styles["label"]))
                story.append(
                    Paragraph(
                        apply_text_highlights(p.get("text"), highlights),
                        styles["body"],
                    )
                )

            if language_mode in ("zh", "both") and p.get("text_zh"):
                highlights = (
                    filter_text_highlights(
                        text_highlights,
                        paper_id=paper["paper_id"],
                        paragraph_id=p["paragraph_id"],
                        scope="paragraph",
                        field_name="text",
                        item_index=None,
                        language="zh",
                    )
                    if include_text_highlights
                    else []
                )
                story.append(Paragraph("原文", styles["label"]))
                story.append(
                    Paragraph(
                        apply_text_highlights(p.get("text_zh"), highlights),
                        styles["body"],
                    )
                )

        # bullet list body
        if p_type == "bullet_list":
            if language_mode in ("en", "both") and p.get("intro_text"):
                highlights = (
                    filter_text_highlights(
                        text_highlights,
                        paper_id=paper["paper_id"],
                        paragraph_id=p["paragraph_id"],
                        scope="paragraph",
                        field_name="intro_text",
                        item_index=None,
                        language="en",
                    )
                    if include_text_highlights
                    else []
                )
                story.append(Paragraph("Intro Text", styles["label"]))
                story.append(
                    Paragraph(
                        apply_text_highlights(p.get("intro_text"), highlights),
                        styles["body"],
                    )
                )

            if language_mode in ("zh", "both") and p.get("intro_text_zh"):
                highlights = (
                    filter_text_highlights(
                        text_highlights,
                        paper_id=paper["paper_id"],
                        paragraph_id=p["paragraph_id"],
                        scope="paragraph",
                        field_name="intro_text",
                        item_index=None,
                        language="zh",
                    )
                    if include_text_highlights
                    else []
                )
                story.append(Paragraph("說明文字", styles["label"]))
                story.append(
                    Paragraph(
                        apply_text_highlights(p.get("intro_text_zh"), highlights),
                        styles["body"],
                    )
                )

            en_items = p.get("items") or []
            zh_items = p.get("items_zh") or []

            if language_mode in ("en", "both") and en_items:
                story.append(Paragraph("Bullet Items", styles["label"]))
                items_flow = []
                for idx, item in enumerate(en_items):
                    highlights = (
                        filter_text_highlights(
                            text_highlights,
                            paper_id=paper["paper_id"],
                            paragraph_id=p["paragraph_id"],
                            scope="paragraph",
                            field_name="item",
                            item_index=idx,
                            language="en",
                        )
                        if include_text_highlights
                        else []
                    )
                    items_flow.append(
                        ListItem(
                            Paragraph(
                                apply_text_highlights(item, highlights),
                                styles["body"],
                            )
                        )
                    )
                story.append(ListFlowable(items_flow, bulletType="bullet", leftIndent=14))
                story.append(Spacer(1, 0.08 * cm))

            if language_mode in ("zh", "both") and zh_items:
                story.append(Paragraph("項目", styles["label"]))
                items_flow = []
                for idx, item in enumerate(zh_items):
                    highlights = (
                        filter_text_highlights(
                            text_highlights,
                            paper_id=paper["paper_id"],
                            paragraph_id=p["paragraph_id"],
                            scope="paragraph",
                            field_name="item",
                            item_index=idx,
                            language="zh",
                        )
                        if include_text_highlights
                        else []
                    )
                    items_flow.append(
                        ListItem(
                            Paragraph(
                                apply_text_highlights(item, highlights),
                                styles["body"],
                            )
                        )
                    )
                story.append(ListFlowable(items_flow, bulletType="bullet", leftIndent=14))
                story.append(Spacer(1, 0.08 * cm))

        # summary
        if language_mode in ("en", "both") and p.get("summary"):
            highlights = (
                filter_text_highlights(
                    text_highlights,
                    paper_id=paper["paper_id"],
                    paragraph_id=p["paragraph_id"],
                    scope="paragraph",
                    field_name="summary",
                    item_index=None,
                    language="en",
                )
                if include_text_highlights
                else []
            )
            story.append(Paragraph("Summary", styles["label"]))
            story.append(
                Paragraph(
                    apply_text_highlights(p.get("summary"), highlights),
                    styles["body"],
                )
            )

        if language_mode in ("zh", "both") and p.get("summary_zh"):
            highlights = (
                filter_text_highlights(
                    text_highlights,
                    paper_id=paper["paper_id"],
                    paragraph_id=p["paragraph_id"],
                    scope="paragraph",
                    field_name="summary",
                    item_index=None,
                    language="zh",
                )
                if include_text_highlights
                else []
            )
            story.append(Paragraph("總結", styles["label"]))
            story.append(
                Paragraph(
                    apply_text_highlights(p.get("summary_zh"), highlights),
                    styles["body"],
                )
            )

        # key points
        en_key_points = p.get("key_points") or []
        zh_key_points = p.get("key_points_zh") or []

        if language_mode in ("en", "both") and en_key_points:
            story.append(Paragraph("Key Points", styles["label"]))
            items_flow = []
            for idx, item in enumerate(en_key_points):
                highlights = (
                    filter_text_highlights(
                        text_highlights,
                        paper_id=paper["paper_id"],
                        paragraph_id=p["paragraph_id"],
                        scope="paragraph",
                        field_name="key_points",
                        item_index=idx,
                        language="en",
                    )
                    if include_text_highlights
                    else []
                )
                items_flow.append(
                    ListItem(
                        Paragraph(
                            apply_text_highlights(item, highlights),
                            styles["body"],
                        )
                    )
                )
            story.append(ListFlowable(items_flow, bulletType="bullet", leftIndent=14))
            story.append(Spacer(1, 0.08 * cm))

        if language_mode in ("zh", "both") and zh_key_points:
            story.append(Paragraph("重點", styles["label"]))
            items_flow = []
            for idx, item in enumerate(zh_key_points):
                highlights = (
                    filter_text_highlights(
                        text_highlights,
                        paper_id=paper["paper_id"],
                        paragraph_id=p["paragraph_id"],
                        scope="paragraph",
                        field_name="key_points",
                        item_index=idx,
                        language="zh",
                    )
                    if include_text_highlights
                    else []
                )
                items_flow.append(
                    ListItem(
                        Paragraph(
                            apply_text_highlights(item, highlights),
                            styles["body"],
                        )
                    )
                )
            story.append(ListFlowable(items_flow, bulletType="bullet", leftIndent=14))
            story.append(Spacer(1, 0.08 * cm))

        story.append(HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#D1D5DB")))
        story.append(Spacer(1, 0.18 * cm))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# Package generated export files into an in-memory ZIP.
def package_files_as_zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files.items():
            zf.writestr(filename, content)
    buffer.seek(0)
    return buffer.getvalue()