import re
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional, Set, Tuple


def _normalize_for_match(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\u00a0", " ")
    text = text.replace("\r", "\n")
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()

    # markdown / 字元差異弱化
    text = text.replace("**", "")
    text = text.replace("__", "")
    text = text.replace("*", "")
    text = text.replace("_", "")
    text = text.replace("`", "")
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")
    text = text.replace("WiFi", "Wi-Fi")
    text = re.sub(r"\s*[–—]\s*", "-", text)
    text = text.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    text = text.replace("•", "")

    return text.lower().strip()


def _token_overlap_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0

    a_tokens = set(a.split())
    b_tokens = set(b.split())
    if not a_tokens or not b_tokens:
        return 0.0

    return len(a_tokens & b_tokens) / max(len(a_tokens), 1)


def _get_column(bbox):
    x0, y0, x1, y1 = bbox
    cx = (x0 + x1) / 2

    if cx < 250:
        return "left"
    elif cx > 300:
        return "right"
    return "center"


def _dedupe_rects(rects: List[List[float]]) -> List[List[float]]:
    seen = set()
    result = []

    for rect in rects:
        key = tuple(round(float(x), 3) for x in rect)
        if key in seen:
            continue
        seen.add(key)
        result.append([float(x) for x in rect])

    return result


def _extract_roman_heading_prefix(text: str) -> Optional[str]:
    norm = _normalize_for_match(text)
    m = re.match(r"^(i|ii|iii|iv|v|vi|vii|viii|ix|x)\.", norm)
    return m.group(1) if m else None


def _is_heading_like(text: str) -> bool:
    norm = _normalize_for_match(text)
    if not norm:
        return False

    if _extract_roman_heading_prefix(norm):
        return True

    raw = (text or "").strip()
    letters = [ch for ch in raw if ch.isalpha()]
    if letters and len(norm.split()) <= 10:
        upper_ratio = sum(1 for ch in letters if ch.isupper()) / len(letters)
        if upper_ratio > 0.8:
            return True

    return False


def _is_bullet_like(text: str) -> bool:
    stripped = (text or "").strip()
    return stripped.startswith("- ") or stripped.startswith("•")


def _looks_like_metadata_box(text: str) -> bool:
    norm = _normalize_for_match(text)
    if not norm:
        return True

    if "arxiv:" in norm:
        return True

    if "intentionally omitted" in norm:
        return True

    if text.count(",") >= 3 and " and " in norm and len(norm.split()) <= 20:
        return True

    metadata_markers = [
        "supported in part by",
        "is with ",
        "are with ",
        "univ.",
        "university",
        "bell labs",
        "program.",
        # 原本太寬鬆的 "grant", "grants " 拿掉，避免誤傷動詞 grants
        "supported by grant",
        "nsf grant",
        "funded by grant",
        "under grant",
        "ramon y",
        "ram´on y",
        "ramon y cajal",
        "ram´on y cajal",
    ]
    if any(m in norm for m in metadata_markers):
        return True

    # figure / table caption / page number 類
    # 允許 "- fig. 5" 這種前綴
    if re.match(r"^(-\s+)?(fig\.?|figure|table)\s*\d+", norm):
        # 真正圖說通常較短；較長者可能是正文裡引用圖表的句子
        if len(norm.split()) <= 20:
            return True
        
    if re.match(r"^\(?[a-z0-9]\)\s", norm) and len(norm.split()) <= 8:
        return True
    
    if re.match(r"^\d{1,4}$", norm):
        return True

    simple = re.sub(r"[^a-z0-9 ]+", "", norm).strip()
    if simple in {"references", "appendix", "acknowledgment", "acknowledgements"}:
        return True

    return False


def _score_text_match(target_text: str, candidate_text: str) -> float:
    if not target_text or not candidate_text:
        return 0.0

    if target_text == candidate_text:
        return 1.0

    if target_text in candidate_text:
        return 0.97

    if candidate_text in target_text and len(candidate_text) > 60:
        return 0.85

    prefix = target_text[:180]
    if len(prefix) > 40 and prefix in candidate_text:
        return 0.92

    suffix = target_text[-180:]
    if len(suffix) > 40 and suffix in candidate_text:
        return 0.88

    overlap = _token_overlap_ratio(target_text, candidate_text)
    return overlap * 0.72


def _word_count(text: str) -> int:
    return len(_normalize_for_match(text).split())


def _confidence_from_word_ratio(collected_words: int, paragraph_words: int) -> str:
    if paragraph_words <= 0:
        return "low"

    ratio = collected_words / max(paragraph_words, 1)

    if 0.7 <= ratio <= 2.0:
        return "high"
    if 0.4 <= ratio <= 3.0:
        return "medium"
    return "low"


def _merge_bboxes_list(boxes: List[dict]) -> List[List[float]]:
    if not boxes:
        return []

    return _dedupe_rects([b["bbox"] for b in boxes if b.get("bbox")])


def _make_pdf_locations(boxes: List[dict]) -> List[dict]:
    """
    將 matched boxes 轉成帶 page 的 locations。
    這才是前端處理跨頁高亮的正確資料來源。
    """
    seen = set()
    locations = []

    for box in boxes:
        bbox = box.get("bbox")
        page = box.get("page_number")
        if bbox is None or page is None:
            continue

        key = (int(page), tuple(round(float(x), 3) for x in bbox))
        if key in seen:
            continue
        seen.add(key)

        locations.append({
            "page": int(page),
            "bbox": [float(x) for x in bbox],
        })

    return locations


def _locations_to_primary_page(locations: List[dict]) -> Optional[int]:
    """
    為了相容舊前端，仍保留單一 page_number。
    規則：取最常出現的頁碼；若沒有則回 None。
    """
    if not locations:
        return None

    pages = [loc["page"] for loc in locations]
    return max(set(pages), key=pages.count)


def _build_position_page_index(position_data: Optional[dict]) -> List[dict]:
    """
    建立 block index：
    - normalize
    - 過濾垃圾 block
    - 建每頁的文字流與 block 區間
    """
    if not position_data:
        return []

    indexed_pages: List[dict] = []

    for page in position_data.get("pages", []):
        page_number = page.get("page_number")
        boxes = page.get("boxes") or []

        filtered_boxes = []
        stream_parts: List[str] = []
        cursor = 0

        for box in boxes:
            text = box.get("text") or ""
            norm = (box.get("normalized_text") or _normalize_for_match(text)).lower().strip()
            bbox = box.get("bbox")

            if not norm or not bbox:
                continue

            if _looks_like_metadata_box(text):
                continue

            if stream_parts:
                cursor += 1  # separator

            stream_start = cursor
            stream_parts.append(norm)
            cursor += len(norm)
            stream_stop = cursor

            filtered_boxes.append({
                "page_number": page_number,
                "block_index": int(box.get("block_index", 0)),
                "bbox": [float(x) for x in bbox],
                "text": text,
                "normalized_text": norm,
                "class": box.get("class", "text"),
                "pos": box.get("pos"),
                "stream_start": stream_start,
                "stream_stop": stream_stop,
                "column": _get_column(bbox),
                "is_heading_like": _is_heading_like(text),
                "is_bullet_like": _is_bullet_like(text),
                "word_count": _word_count(norm),
            })

        normalized_stream_text = " ".join(stream_parts).strip()

        indexed_pages.append({
            "page_number": page_number,
            "boxes": filtered_boxes,
            "normalized_stream_text": normalized_stream_text,
        })

    return indexed_pages


def _find_best_page_for_text(text: str, indexed_pages: List[dict]) -> Optional[int]:
    target = _normalize_for_match(text)
    if not target:
        return None

    best_page = None
    best_score = 0.0

    prefix = target[:220]
    suffix = target[-220:] if len(target) > 220 else target

    for page in indexed_pages:
        page_text = page["normalized_stream_text"]
        if not page_text:
            continue

        score = 0.0
        if target in page_text:
            score = 1.0
        elif prefix and len(prefix) > 50 and prefix in page_text:
            score = 0.92
        elif suffix and len(suffix) > 50 and suffix in page_text:
            score = 0.88
        else:
            score = _token_overlap_ratio(target, page_text) * 0.55

        if score > best_score:
            best_score = score
            best_page = page["page_number"]

    if best_score < 0.20:
        return None

    return best_page


def _make_anchor_lengths(target: str) -> Tuple[int, int]:
    n = len(target)

    if n >= 100:
        return 40, 40
    if n >= 60:
        return 25, 25
    if n >= 30:
        return 15, 15

    return max(8, n), 0


def _find_all_positions(text: str, pattern: str) -> List[int]:
    if not text or not pattern:
        return []

    positions = []
    start = 0
    while True:
        idx = text.find(pattern, start)
        if idx == -1:
            break
        positions.append(idx)
        start = idx + 1
    return positions


def _find_block_index_for_stream_pos(boxes: List[dict], pos: int) -> Optional[int]:
    for i, box in enumerate(boxes):
        if box["stream_start"] <= pos < box["stream_stop"]:
            return i
    return None


def _collect_boxes_and_confidence(
    matched_boxes: List[dict],
    paragraph_text: str,
) -> Tuple[List[List[float]], List[dict], Optional[int], str]:
    rects = _merge_bboxes_list(matched_boxes)
    locations = _make_pdf_locations(matched_boxes)
    primary_page = _locations_to_primary_page(locations)

    collected_words = sum(b.get("word_count", 0) for b in matched_boxes)
    para_words = _word_count(paragraph_text)
    confidence = _confidence_from_word_ratio(collected_words, para_words)

    return rects, locations, primary_page, confidence


def _get_candidate_pages(
    indexed_pages: List[dict],
    estimated_page: Optional[int],
    backward: int = 1,
    forward: int = 2,
) -> List[dict]:
    """
    取得候選頁。
    比原本 estimated_page ± 1 稍微往後多放一頁，
    以容納跨頁段落的續接內容。
    """
    if estimated_page is None:
        return indexed_pages

    return [
        p for p in indexed_pages
        if estimated_page - backward <= p["page_number"] <= estimated_page + forward
    ]


def _extend_candidate_across_pages(
    candidate_boxes: List[dict],
    paragraph_text: str,
    candidate_pages: List[dict],
    current_page_idx: int,
    max_extra_pages: int = 2,
    max_boxes_per_page: int = 8,
    exclude_bullets: bool = True,
) -> List[dict]:
    """
    當單頁收集到的 box 字數不足時，
    往後續頁補收 box，直到字數足夠或到達上限。
    """
    if not candidate_boxes:
        return candidate_boxes

    target_words = _word_count(paragraph_text)
    collected = list(candidate_boxes)
    collected_words = sum(b.get("word_count", 0) for b in collected)

    if target_words <= 0 or collected_words >= target_words * 0.85:
        return collected

    for offset in range(1, max_extra_pages + 1):
        next_page_idx = current_page_idx + offset
        if next_page_idx >= len(candidate_pages):
            break

        next_page = candidate_pages[next_page_idx]
        next_boxes = [
            b for b in next_page["boxes"]
            if not b["is_heading_like"]
            and (not exclude_bullets or not b["is_bullet_like"])
        ]

        if not next_boxes:
            continue

        for box in next_boxes[:max_boxes_per_page]:
            collected.append(box)
            collected_words += box.get("word_count", 0)

            if collected_words >= target_words * 0.85:
                return collected

    return collected


def _score_ratio_and_size(candidate_words: int, paragraph_words: int, box_count: int) -> float:
    ratio = candidate_words / max(paragraph_words, 1)

    if 0.7 <= ratio <= 1.6:
        ratio_score = 1.0
    elif 0.5 <= ratio <= 2.2:
        ratio_score = 0.5
    else:
        ratio_score = 0.0

    size_penalty = min(box_count, 8) * 0.08
    return ratio_score - size_penalty


def _find_best_heading_match(
    text: str,
    indexed_pages: List[dict],
    last_page: Optional[int],
    used_heading_blocks: Set[Tuple[int, int]],
) -> dict:
    target = _normalize_for_match(text)
    target_roman = _extract_roman_heading_prefix(text)

    best = None
    best_score = 0.0

    for page in indexed_pages:
        if last_page is not None and page["page_number"] < last_page:
            continue

        for box in page["boxes"]:
            if not box["is_heading_like"]:
                continue

            key = (box["page_number"], int(box["block_index"]))
            if key in used_heading_blocks:
                continue

            cand_roman = _extract_roman_heading_prefix(box["text"])
            if target_roman is not None and cand_roman != target_roman:
                continue

            score = _score_text_match(target, box["normalized_text"])
            if last_page is not None and box["page_number"] == last_page:
                score += 0.03
            elif last_page is not None and box["page_number"] == last_page + 1:
                score += 0.02

            if score > best_score:
                best_score = score
                best = box

    if not best or best_score < 0.75:
        return {
            "page_number": None,
            "pdf_rects": [],
            "pdf_locations": [],
            "matched_block": None,
            "match_confidence": "low",
        }

    return {
        "page_number": best["page_number"],
        "pdf_rects": [best["bbox"]],
        "pdf_locations": [{
            "page": int(best["page_number"]),
            "bbox": [float(x) for x in best["bbox"]],
        }],
        "matched_block": (best["page_number"], int(best["block_index"])),
        "match_confidence": "high",
    }


def _head_tail_anchor_match(
    paragraph_text: str,
    page: dict,
    exclude_bullets: bool = True,
) -> Optional[dict]:
    target = _normalize_for_match(paragraph_text)
    if not target:
        return None

    boxes = [
        b for b in page["boxes"]
        if not b["is_heading_like"]
        and (not exclude_bullets or not b["is_bullet_like"])
    ]
    if not boxes:
        return None

    page_text = " ".join(b["normalized_text"] for b in boxes).strip()
    if not page_text:
        return None

    remapped_boxes = []
    cursor = 0
    for box in boxes:
        if remapped_boxes:
            cursor += 1
        stream_start = cursor
        cursor += len(box["normalized_text"])
        stream_stop = cursor

        new_box = dict(box)
        new_box["stream_start"] = stream_start
        new_box["stream_stop"] = stream_stop
        remapped_boxes.append(new_box)

    head_len, tail_len = _make_anchor_lengths(target)
    head = target[:head_len]
    tail = target[-tail_len:] if tail_len > 0 else ""

    head_positions = _find_all_positions(page_text, head) if head else []
    tail_positions = _find_all_positions(page_text, tail) if tail else []

    if not head_positions:
        return None

    if tail_len == 0 or not tail_positions:
        return None

    best_candidate = None
    best_score = -1.0
    para_words = _word_count(paragraph_text)

    for head_pos in head_positions:
        for tail_pos in tail_positions:
            if tail_pos < head_pos:
                continue

            start_idx = _find_block_index_for_stream_pos(remapped_boxes, head_pos)
            end_idx = _find_block_index_for_stream_pos(remapped_boxes, tail_pos)
            if start_idx is None or end_idx is None or end_idx < start_idx:
                continue

            candidate_boxes = remapped_boxes[start_idx:end_idx + 1]
            candidate_text = " ".join(b["normalized_text"] for b in candidate_boxes).strip()
            candidate_words = sum(b["word_count"] for b in candidate_boxes)

            text_score = _score_text_match(target, candidate_text)
            ratio_size_score = _score_ratio_and_size(candidate_words, para_words, len(candidate_boxes))
            score = text_score + ratio_size_score

            if score > best_score:
                best_score = score
                best_candidate = candidate_boxes

    if not best_candidate:
        return None

    rects, locations, primary_page, confidence = _collect_boxes_and_confidence(best_candidate, paragraph_text)
    return {
        "page_number": primary_page,
        "pdf_rects": rects,
        "pdf_locations": locations,
        "match_confidence": confidence,
    }


def _head_only_collect_match(
    paragraph_text: str,
    page: dict,
    page_idx: int,
    candidate_pages: List[dict],
    max_blocks: int = 8,
    exclude_bullets: bool = True,
) -> Optional[dict]:
    target = _normalize_for_match(paragraph_text)
    if not target:
        return None

    boxes = [
        b for b in page["boxes"]
        if not b["is_heading_like"]
        and (not exclude_bullets or not b["is_bullet_like"])
    ]
    if not boxes:
        return None

    page_text = " ".join(b["normalized_text"] for b in boxes).strip()
    if not page_text:
        return None

    remapped_boxes = []
    cursor = 0
    for box in boxes:
        if remapped_boxes:
            cursor += 1
        stream_start = cursor
        cursor += len(box["normalized_text"])
        stream_stop = cursor

        new_box = dict(box)
        new_box["stream_start"] = stream_start
        new_box["stream_stop"] = stream_stop
        remapped_boxes.append(new_box)

    head_len, _ = _make_anchor_lengths(target)
    head = target[:head_len]
    head_positions = _find_all_positions(page_text, head) if head else []
    if not head_positions:
        return None

    para_words = _word_count(paragraph_text)

    best_candidate = None
    best_score = -1.0

    for head_pos in head_positions:
        start_idx = _find_block_index_for_stream_pos(remapped_boxes, head_pos)
        if start_idx is None:
            continue

        collected = []
        collected_words = 0

        for box in remapped_boxes[start_idx:start_idx + max_blocks]:
            collected.append(box)
            collected_words += box["word_count"]
            if collected_words >= para_words * 0.8:
                break

        if not collected:
            continue

        # 單頁收集不足時，往後續頁補收
        collected = _extend_candidate_across_pages(
            candidate_boxes=collected,
            paragraph_text=paragraph_text,
            candidate_pages=candidate_pages,
            current_page_idx=page_idx,
            max_extra_pages=2,
            max_boxes_per_page=max_blocks,
            exclude_bullets=exclude_bullets,
        )

        collected_words = sum(b.get("word_count", 0) for b in collected)
        candidate_text = " ".join(b["normalized_text"] for b in collected).strip()

        text_score = _score_text_match(target, candidate_text)
        ratio_size_score = _score_ratio_and_size(
            collected_words, para_words, len(collected)
        )
        score = text_score + ratio_size_score

        if score > best_score:
            best_score = score
            best_candidate = collected

    if not best_candidate:
        return None

    rects, locations, primary_page, confidence = _collect_boxes_and_confidence(
        best_candidate, paragraph_text
    )
    return {
        "page_number": primary_page,
        "pdf_rects": rects,
        "pdf_locations": locations,
        "match_confidence": confidence,
    }


def _fuzzy_window_match(
    paragraph_text: str,
    indexed_pages: List[dict],
    exclude_bullets: bool = True,
) -> dict:
    target = _normalize_for_match(paragraph_text)
    if not target:
        return {
            "page_number": None,
            "pdf_rects": [],
            "pdf_locations": [],
            "match_confidence": "low",
        }

    estimated_page = _find_best_page_for_text(paragraph_text, indexed_pages)

    candidate_pages = _get_candidate_pages(indexed_pages, estimated_page)

    best_page = None
    best_boxes = None
    best_score = -1.0

    for page in candidate_pages:
        boxes = [
            b for b in page["boxes"]
            if not b["is_heading_like"]
            and (not exclude_bullets or not b["is_bullet_like"])
        ]
        if not boxes:
            continue

        for i in range(len(boxes)):
            combined_text = ""
            combined_boxes = []

            for j in range(i, min(i + 4, len(boxes))):
                combined_boxes.append(boxes[j])
                combined_text = (combined_text + " " + boxes[j]["normalized_text"]).strip()

                score = SequenceMatcher(None, target, combined_text).ratio()
                if score > best_score:
                    best_score = score
                    best_page = page["page_number"]
                    best_boxes = combined_boxes[:]

    if not best_boxes or best_score < 0.35:
        return {
            "page_number": None,
            "pdf_rects": [],
            "pdf_locations": [],
            "match_confidence": "low",
        }

    rects, locations, primary_page, confidence = _collect_boxes_and_confidence(best_boxes, paragraph_text)
    if confidence == "high":
        confidence = "medium"

    return {
        "page_number": primary_page if primary_page is not None else best_page,
        "pdf_rects": rects,
        "pdf_locations": locations,
        "match_confidence": confidence,
    }


def _find_best_paragraph_match(text: str, indexed_pages: List[dict]) -> dict:
    """
    這裡改成 exclude_bullets=False
    因為有些 paragraph 在 PDF 版面上實際就是 list-item 形式。
    """
    if not text or not text.strip():
        return {
            "page_number": None,
            "pdf_rects": [],
            "pdf_locations": [],
            "match_confidence": "low",
        }

    estimated_page = _find_best_page_for_text(text, indexed_pages)

    candidate_pages = _get_candidate_pages(indexed_pages, estimated_page)

    best_anchor_result = None
    best_anchor_rank = -1.0

    for page in candidate_pages:
        result = _head_tail_anchor_match(text, page, exclude_bullets=False)
        if result and result["pdf_rects"]:
            rank = {"high": 3, "medium": 2, "low": 1}[result["match_confidence"]]
            if rank > best_anchor_rank:
                best_anchor_rank = rank
                best_anchor_result = result

    if best_anchor_result:
        return best_anchor_result

    best_head_result = None
    best_head_rank = -1.0

    for page_idx, page in enumerate(candidate_pages):
        result = _head_only_collect_match(
            text,
            page,
            page_idx=page_idx,
            candidate_pages=candidate_pages,
            max_blocks=8,
            exclude_bullets=False,
        )
        if result and result["pdf_rects"]:
            rank = {"high": 3, "medium": 2, "low": 1}[result["match_confidence"]]
            if rank > best_head_rank:
                best_head_rank = rank
                best_head_result = result

    if best_head_result:
        return best_head_result

    return _fuzzy_window_match(text, indexed_pages, exclude_bullets=False)


def _find_best_bullet_item_match(item_text: str, indexed_pages: List[dict]) -> dict:
    if not item_text or not item_text.strip():
        return {
            "page_number": None,
            "pdf_rects": [],
            "pdf_locations": [],
            "match_confidence": "low",
        }

    estimated_page = _find_best_page_for_text(item_text, indexed_pages)

    candidate_pages = _get_candidate_pages(indexed_pages, estimated_page)

    best_anchor_result = None
    best_anchor_rank = -1.0

    for page in candidate_pages:
        result = _head_tail_anchor_match(item_text, page, exclude_bullets=False)
        if result and result["pdf_rects"]:
            rank = {"high": 3, "medium": 2, "low": 1}[result["match_confidence"]]
            if rank > best_anchor_rank:
                best_anchor_rank = rank
                best_anchor_result = result

    if best_anchor_result:
        return best_anchor_result

    best_head_result = None
    best_head_rank = -1.0

    for page_idx, page in enumerate(candidate_pages):
        result = _head_only_collect_match(
            item_text,
            page,
            page_idx=page_idx,
            candidate_pages=candidate_pages,
            max_blocks=4,
            exclude_bullets=False,
        )
        if result and result["pdf_rects"]:
            rank = {"high": 3, "medium": 2, "low": 1}[result["match_confidence"]]
            if rank > best_head_rank:
                best_head_rank = rank
                best_head_result = result

    if best_head_result:
        return best_head_result

    fuzzy_result = _fuzzy_window_match(item_text, indexed_pages, exclude_bullets=False)
    if fuzzy_result["pdf_rects"]:
        return fuzzy_result

    target = _normalize_for_match(item_text)
    best_score = -1.0
    best_page = None
    best_boxes = None

    for page in candidate_pages:
        bullet_boxes = [b for b in page["boxes"] if b["is_bullet_like"]]
        if not bullet_boxes:
            continue

        for i in range(len(bullet_boxes)):
            one_text = bullet_boxes[i]["normalized_text"]
            score = max(
                _score_text_match(target, one_text),
                _token_overlap_ratio(target, one_text) * 0.85,
            )
            if score > best_score:
                best_score = score
                best_page = page["page_number"]
                best_boxes = [bullet_boxes[i]]

            if i + 1 < len(bullet_boxes):
                pair = bullet_boxes[i:i + 2]
                pair_text = " ".join(b["normalized_text"] for b in pair).strip()
                score = max(
                    _score_text_match(target, pair_text),
                    _token_overlap_ratio(target, pair_text) * 0.85,
                )
                if score > best_score:
                    best_score = score
                    best_page = page["page_number"]
                    best_boxes = pair

    if best_boxes and best_score >= 0.35:
        rects, locations, primary_page, confidence = _collect_boxes_and_confidence(best_boxes, item_text)
        return {
            "page_number": primary_page if primary_page is not None else best_page,
            "pdf_rects": rects,
            "pdf_locations": locations,
            "match_confidence": confidence if confidence != "high" else "medium",
        }

    return {
        "page_number": None,
        "pdf_rects": [],
        "pdf_locations": [],
        "match_confidence": "low",
    }


def _find_best_bullet_match(intro_text: str, items: List[str], indexed_pages: List[dict]) -> dict:
    all_rects: List[List[float]] = []
    all_locations: List[dict] = []
    confidences: List[str] = []
    page_numbers: List[int] = []

    for item in items:
        if not item or not str(item).strip():
            continue

        result = _find_best_bullet_item_match(str(item), indexed_pages)
        all_rects.extend(result.get("pdf_rects", []))
        all_locations.extend(result.get("pdf_locations", []))

        if result.get("match_confidence"):
            confidences.append(result["match_confidence"])
        if result.get("page_number") is not None:
            page_numbers.append(result["page_number"])

    all_rects = _dedupe_rects(all_rects)

    seen = set()
    dedup_locations = []
    for loc in all_locations:
        key = (int(loc["page"]), tuple(round(float(x), 3) for x in loc["bbox"]))
        if key in seen:
            continue
        seen.add(key)
        dedup_locations.append({
            "page": int(loc["page"]),
            "bbox": [float(x) for x in loc["bbox"]],
        })
    all_locations = dedup_locations

    if not all_rects:
        return {
            "page_number": None,
            "pdf_rects": [],
            "pdf_locations": [],
            "match_confidence": "low",
        }

    page_number = _locations_to_primary_page(all_locations)
    if page_number is None and page_numbers:
        page_number = max(set(page_numbers), key=page_numbers.count)

    if "low" in confidences:
        confidence = "low"
    elif "medium" in confidences:
        confidence = "medium"
    else:
        confidence = "high"

    return {
        "page_number": page_number,
        "pdf_rects": all_rects,
        "pdf_locations": all_locations,
        "match_confidence": confidence,
    }


def build_paragraph_results(raw_items: List[dict], position_data: Optional[dict] = None) -> List[dict]:
    results: List[Dict[str, Any]] = []

    global_idx = 0
    last_section_title = None
    last_heading_page: Optional[int] = None
    used_heading_blocks: Set[Tuple[int, int]] = set()

    indexed_pages = _build_position_page_index(position_data)

    for item in raw_items:
        current_section_title = (item.get("section_title") or "").strip()

        if (
            current_section_title
            and current_section_title != "UNKNOWN"
            and current_section_title != last_section_title
        ):
            heading_match = _find_best_heading_match(
                current_section_title,
                indexed_pages,
                last_heading_page,
                used_heading_blocks,
            )

            if heading_match.get("matched_block"):
                used_heading_blocks.add(heading_match["matched_block"])

            if heading_match.get("page_number") is not None:
                last_heading_page = heading_match["page_number"]

            results.append({
                "id": global_idx,
                "chunk_index": item.get("chunk_index"),
                "paragraph_index_within_chunk": -1,
                "section_title": current_section_title,
                "type": "heading",
                "text": current_section_title,
                "level": "section",
                "summary": None,
                "key_points": None,
                "items": None,
                "intro_text": None,
                "page_number": heading_match["page_number"],
                "pdf_rects": heading_match["pdf_rects"],
                "pdf_locations": heading_match.get("pdf_locations", []),
                "match_confidence": heading_match.get("match_confidence", "low"),
            })
            global_idx += 1
            last_section_title = current_section_title

        if item.get("type") == "heading":
            continue

        item_type = item.get("type")
        item_text = item.get("text") or ""
        intro_text = item.get("intro_text") or ""
        items = item.get("items") or []

        if item_type == "bullet_list":
            position_match = _find_best_bullet_match(intro_text, items, indexed_pages)
        else:
            position_match = _find_best_paragraph_match(item_text, indexed_pages)

        result = {
            "id": global_idx,
            "chunk_index": item.get("chunk_index"),
            "paragraph_index_within_chunk": item.get("paragraph_index_within_chunk"),
            "section_title": last_section_title,
            "type": item_type,
            "text": item.get("text"),
            "summary": item.get("summary"),
            "key_points": item.get("key_points"),
            "items": item.get("items"),
            "intro_text": item.get("intro_text"),
            "page_number": position_match["page_number"],
            "pdf_rects": position_match["pdf_rects"],
            "pdf_locations": position_match.get("pdf_locations", []),
            "match_confidence": position_match.get("match_confidence", "low"),
        }

        results.append(result)
        global_idx += 1

    return results

#v616