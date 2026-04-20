import re
from typing import Any, Dict, List

import pymupdf4llm


def extract_markdown_with_pymupdf4llm(pdf_path: str) -> str:
    """
    主線：保留你現在原本的 markdown 抽取方式。
    這條線不要動，避免影響既有 chunk / summary / overview 結果。
    """
    markdown = pymupdf4llm.to_markdown(pdf_path)
    return markdown or ""


def _normalize_text(text: str) -> str:
    """
    給位置映射用的文字正規化：
    - 去掉多餘空白
    - 把換行壓成單一空格
    - 移除常見連字號斷行痕跡
    - 弱化 markdown 符號差異
    - 統一成小寫，避免和 paragraph_builder 的 matching 規則不一致
    """
    if not text:
        return ""

    text = text.replace("\u00a0", " ")
    text = text.replace("\r", "\n")

    # exam-\nple -> example
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)

    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()

    # markdown 標記與常見字元差異
    text = text.replace("**", "")
    text = text.replace("__", "")
    text = text.replace("*", "")
    text = text.replace("_", "")
    text = text.replace("`", "")
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")
    text = text.replace("WiFi", "Wi-Fi")
    text = text.replace("–", "-").replace("—", "-")
    text = text.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    text = text.replace("•", "")

    return text.lower().strip()


def extract_position_data_with_page_boxes(pdf_path: str) -> Dict[str, Any]:
    """
    支線：用 pymupdf4llm 的 page_chunks + page_boxes 提供
    text 與 bbox 同源的定位資料。

    重點：
    - 不影響主線 markdown / chunk / summary 結果
    - 直接保留每個 box 在 page_text 中的 pos(start, stop)
    - page_number 用 enumerate 保證正確，不依賴 metadata["page"]
    - 先把 list-item 一起保留下來，修正 bullet 遺失問題
    """
    chunks = pymupdf4llm.to_markdown(pdf_path, page_chunks=True) or []

    pages: List[Dict[str, Any]] = []

    for page_idx, chunk in enumerate(chunks):
        metadata = chunk.get("metadata", {}) or {}
        page_number = page_idx
        page_text = chunk.get("text", "") or ""
        page_boxes = chunk.get("page_boxes", []) or []

        parsed_boxes = []

        for idx, box in enumerate(page_boxes):
            box_class = box.get("class")
            bbox = box.get("bbox")
            pos = box.get("pos")

            if not bbox or not pos:
                continue

            if not isinstance(pos, (list, tuple)) or len(pos) != 2:
                continue

            start, stop = pos
            if start is None or stop is None:
                continue

            start = int(start)
            stop = int(stop)

            if start < 0 or stop <= start or stop > len(page_text):
                continue

            box_text = page_text[start:stop].strip()
            if not box_text:
                continue

            # 先保留正文與 bullet/list item
            # picture / caption / page-header 暫時不納入 paragraph 對齊
            if box_class not in {"text", "list-item"}:
                continue

            parsed_boxes.append({
                "block_index": int(box.get("index", idx)),
                "bbox": [float(x) for x in bbox],
                "text": box_text,
                "normalized_text": _normalize_text(box_text),
                "class": box_class,
                "pos": [start, stop],
            })

        pages.append({
            "page_number": page_number,
            "boxes": parsed_boxes,
            "page_text": page_text,
            "normalized_page_text": _normalize_text(page_text),
            "metadata": metadata,
        })

    return {
        "pdf_path": pdf_path,
        "page_count": len(pages),
        "pages": pages,
    }