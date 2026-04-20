import re
from statistics import mean


def is_heading_like(text: str) -> bool:
    text = text.strip()
    if not text:
        return False

    # 例如：I. INTRODUCTION
    if re.match(r"^[IVXLC]+\.\s+[A-Z]", text):
        return True

    # 短的大寫標題
    if len(text.split()) <= 10 and text.upper() == text and len(text) < 120:
        return True

    return False


def is_caption_like(text: str) -> bool:
    lowered = text.strip().lower()
    if not lowered:
        return False

    patterns = [
        r"^(fig\.?|figure)\s*\d+",
        r"^(table)\s*\d+",
        r"^(fig\.?|figure)\s*[:\-]",
        r"^(table)\s*[:\-]",
        r"^\([a-z]\)\s",   # (a) (b) (c)
    ]
    return any(re.match(pattern, lowered) for pattern in patterns)


def metadata_score(
    text: str,
    y0: float | None = None,
    y1: float | None = None,
    page_height: float | None = None,
) -> int:
    score = 0
    t = text.strip()
    lowered = t.lower()

    if not t:
        return 0

    # 1. 平台 / 出版來源關鍵字
    platform_keywords = [
        "arxiv", "openreview", "ieee", "acm", "springer", "elsevier",
        "neurips", "iclr", "icml", "cvpr", "aaai", "ijcai", "acl",
        "proceedings", "journal", "doi"
    ]
    if any(k in lowered for k in platform_keywords):
        score += 2

    # 2. 投稿 / 出版狀態關鍵字
    status_keywords = [
        "preprint", "submitted", "accepted", "under review",
        "to appear", "camera-ready", "published", "copyright"
    ]
    if any(k in lowered for k in status_keywords):
        score += 2

    # 3. 明確格式訊號
    if re.search(r"arxiv:\S+", lowered):
        score += 3

    # 類似 [cs.NI]
    if re.search(r"\[[A-Za-z0-9.\-]+\]", t):
        score += 1

    # DOI
    if re.search(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b", t):
        score += 2

    # 日期格式：14 Oct 2022
    if re.search(r"\b\d{1,2}\s+[A-Z][a-z]{2,8}\s+\d{4}\b", t):
        score += 1

    # 日期格式：October 2022 / Oct 2022
    if re.search(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{4}\b", lowered):
        score += 1

    # 年份
    if re.search(r"\b20\d{2}\b", t):
        score += 1

    # 4. 長度特徵：metadata 常偏短
    if len(t) < 100:
        score += 1
    if len(t) < 50:
        score += 1

    # 5. 位置特徵：頂部 / 底部更像 metadata
    if y0 is not None and page_height is not None and y0 < page_height * 0.08:
        score += 2

    if y1 is not None and page_height is not None and y1 > page_height * 0.92:
        score += 2

    # 6. 不像自然正文句子的短區塊
    if not re.search(r"[.!?]$", t) and len(t) < 120:
        score += 1

    return score


def is_metadata_like(
    text: str,
    y0: float | None = None,
    y1: float | None = None,
    page_height: float | None = None,
) -> bool:
    return metadata_score(text, y0=y0, y1=y1, page_height=page_height) >= 4


def is_reference_heading(text: str) -> bool:
    return text.strip().upper() == "REFERENCES"


def is_biography_heading(text: str) -> bool:
    t = text.strip().upper()
    return t in {"BIOGRAPHIES", "BIOGRAPHY"}


def has_hyphenation_artifact(text: str) -> bool:
    text = text.strip()

    # 段落尾端直接以單字-結尾
    if re.search(r"[A-Za-z]{3,}-$", text):
        return True

    # 段內出現明顯斷詞
    if re.search(r"[A-Za-z]{3,}-\s+[a-z]{2,}", text):
        return True

    return False


def looks_like_heading_body_merged(text: str) -> bool:
    text = text.strip()

    # 例如：
    # VI. RECAP AND CONCLUDING REMARKS Our study confirmed ...
    if re.match(r"^[IVXLC]+\.\s+[A-Z][A-Z\s\-&,]{4,}\s+[A-Z][a-z]", text):
        return True

    return False


def paragraph_quality_warnings(
    paragraph: str,
    y0: float | None = None,
    y1: float | None = None,
    page_height: float | None = None,
) -> list[str]:
    warnings = []
    text = paragraph.strip()

    if not text:
        warnings.append("empty_paragraph")
        return warnings

    length = len(text)

    if length < 20 and not is_heading_like(text):
        warnings.append("too_short")

    if length > 2500:
        warnings.append("too_long")

    if is_caption_like(text):
        warnings.append("caption_like")

    if is_metadata_like(text, y0=y0, y1=y1, page_height=page_height):
        warnings.append("metadata_like")

    if has_hyphenation_artifact(text):
        warnings.append("hyphenation_artifact")

    if looks_like_heading_body_merged(text):
        warnings.append("heading_body_merged")

    if length > 300 and not re.search(r"[.!?]$", text):
        warnings.append("no_sentence_ending")

    if re.search(r"\b[a-zA-Z]{1,2}\s+[a-zA-Z]{1,2}\s+[a-zA-Z]{1,2}\b", text):
        warnings.append("fragmented_tokens_possible")

    return warnings


def compute_paragraph_stats(paragraphs: list[str]) -> dict:
    if not paragraphs:
        return {
            "count": 0,
            "avg_length": 0,
            "min_length": 0,
            "max_length": 0,
            "heading_like_count": 0,
            "caption_like_count": 0,
            "metadata_like_count": 0,
            "too_short_count": 0,
            "too_long_count": 0,
            "hyphenation_artifact_count": 0,
            "heading_body_merged_count": 0,
            "reference_heading_count": 0,
            "biography_heading_count": 0,
        }

    lengths = [len(p.strip()) for p in paragraphs]

    heading_like_count = sum(1 for p in paragraphs if is_heading_like(p))
    caption_like_count = sum(1 for p in paragraphs if is_caption_like(p))
    metadata_like_count = sum(1 for p in paragraphs if metadata_score(p) >= 4)
    too_short_count = sum(1 for p in paragraphs if len(p.strip()) < 20 and not is_heading_like(p))
    too_long_count = sum(1 for p in paragraphs if len(p.strip()) > 2500)
    hyphenation_artifact_count = sum(1 for p in paragraphs if has_hyphenation_artifact(p))
    heading_body_merged_count = sum(1 for p in paragraphs if looks_like_heading_body_merged(p))
    reference_heading_count = sum(1 for p in paragraphs if is_reference_heading(p))
    biography_heading_count = sum(1 for p in paragraphs if is_biography_heading(p))

    return {
        "count": len(paragraphs),
        "avg_length": round(mean(lengths), 2),
        "min_length": min(lengths),
        "max_length": max(lengths),
        "heading_like_count": heading_like_count,
        "caption_like_count": caption_like_count,
        "metadata_like_count": metadata_like_count,
        "too_short_count": too_short_count,
        "too_long_count": too_long_count,
        "hyphenation_artifact_count": hyphenation_artifact_count,
        "heading_body_merged_count": heading_body_merged_count,
        "reference_heading_count": reference_heading_count,
        "biography_heading_count": biography_heading_count,
    }


def validate_page_result(
    page_number: int,
    layout_type: str,
    strategy: str,
    paragraphs: list[str],
    features: dict | None = None,
    parser_warnings: list[str] | None = None,
) -> dict:
    features = features or {}
    parser_warnings = parser_warnings or []

    stats = compute_paragraph_stats(paragraphs)
    warnings = list(parser_warnings)

    if stats["count"] == 0:
        warnings.append("no_paragraphs")
    elif stats["count"] == 1:
        warnings.append("only_one_paragraph")

    if stats["avg_length"] > 1800:
        warnings.append("average_paragraph_too_long")

    if stats["too_long_count"] >= 1:
        warnings.append("contains_very_long_paragraphs")

    if stats["too_short_count"] >= max(3, stats["count"] // 3):
        warnings.append("too_many_short_paragraphs")

    if stats["caption_like_count"] >= max(2, stats["count"] // 4):
        warnings.append("too_many_caption_like_paragraphs")

    if stats["metadata_like_count"] >= 1:
        warnings.append("contains_metadata_like_text")

    if stats["hyphenation_artifact_count"] >= 1:
        warnings.append("contains_hyphenation_artifacts")

    if stats["heading_body_merged_count"] >= 1:
        warnings.append("contains_heading_body_merged_paragraphs")

    if stats["reference_heading_count"] >= 1:
        warnings.append("contains_references_section")

    if stats["biography_heading_count"] >= 1:
        warnings.append("contains_biographies_section")

    if layout_type == "complex":
        warnings.append("complex_layout_page")

    if strategy == "blocks" and features.get("block_count", 0) > 25:
        warnings.append("many_blocks_page")

    risk_score = 0

    weight_map = {
        "no_paragraphs": 45,
        "only_one_paragraph": 25,
        "average_paragraph_too_long": 20,
        "contains_very_long_paragraphs": 20,
        "too_many_short_paragraphs": 15,
        "too_many_caption_like_paragraphs": 18,
        "contains_metadata_like_text": 20,
        "contains_hyphenation_artifacts": 25,
        "contains_heading_body_merged_paragraphs": 18,
        "contains_references_section": 15,
        "contains_biographies_section": 15,
        "complex_layout_page": 20,
        "many_blocks_page": 10,
        "many_short_blocks": 10,
        "many_blocks": 10,
        "no_text_blocks": 30,
    }

    for w in warnings:
        risk_score += weight_map.get(w, 6)

    compound_flags = 0
    for key in [
        "contains_metadata_like_text",
        "contains_hyphenation_artifacts",
        "contains_heading_body_merged_paragraphs",
        "too_many_caption_like_paragraphs",
        "contains_references_section",
        "contains_biographies_section",
    ]:
        if key in warnings:
            compound_flags += 1

    if compound_flags >= 2:
        risk_score += 10
    if compound_flags >= 3:
        risk_score += 10

    risk_score = min(risk_score, 100)
    confidence = round(max(0.0, 1 - risk_score / 100), 2)

    if risk_score >= 60:
        risk_level = "high"
    elif risk_score >= 30:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "page_number": page_number,
        "layout_type": layout_type,
        "strategy": strategy,
        "paragraph_stats": stats,
        "warnings": warnings,
        "risk_score": risk_score,
        "confidence": confidence,
        "risk_level": risk_level,
    }


def validate_document_result(page_reports: list[dict]) -> dict:
    if not page_reports:
        return {
            "overall_confidence": 0.0,
            "needs_manual_review": True,
            "high_risk_pages": [],
            "medium_risk_pages": [],
            "summary_warnings": ["no_pages"],
        }

    confidences = [p["confidence"] for p in page_reports]
    overall_confidence = round(mean(confidences), 2)

    high_risk_pages = [p["page_number"] for p in page_reports if p["risk_level"] == "high"]
    medium_risk_pages = [p["page_number"] for p in page_reports if p["risk_level"] == "medium"]

    summary_warnings = []
    if high_risk_pages:
        summary_warnings.append("contains_high_risk_pages")
    if len(medium_risk_pages) >= max(2, len(page_reports) // 3):
        summary_warnings.append("many_medium_risk_pages")

    # v2：比之前更保守
    needs_manual_review = bool(high_risk_pages) or overall_confidence < 0.85

    return {
        "overall_confidence": overall_confidence,
        "needs_manual_review": needs_manual_review,
        "high_risk_pages": high_risk_pages,
        "medium_risk_pages": medium_risk_pages,
        "summary_warnings": summary_warnings,
    }