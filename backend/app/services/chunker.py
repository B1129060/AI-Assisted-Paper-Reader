import re
from typing import List, Dict, Any, Optional


TAIL_HEADINGS = {
    "REFERENCES",
    "REFERENCE",
    "BIBLIOGRAPHY",
    "ACKNOWLEDGMENT",
    "ACKNOWLEDGMENTS",
    "ACKNOWLEDGEMENT",
    "ACKNOWLEDGEMENTS",
    "APPENDIX",
    "APPENDICES",
    "BIOGRAPHY",
    "BIOGRAPHIES",
}


DOMAIN_RE = re.compile(
    r"\b(?:[a-zA-Z0-9-]+\.)+(?:org|com|net|edu|gov|io|ai|co)\b",
    flags=re.IGNORECASE,
)

DOI_RE = re.compile(
    r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b",
    flags=re.IGNORECASE,
)


def strip_md(text: str) -> str:
    text = re.sub(r"[*_#`]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_markdown_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_markdown_blocks(markdown_text: str) -> List[str]:
    text = normalize_markdown_text(markdown_text)
    return [b.strip() for b in text.split("\n\n") if b.strip()]


def is_page_number(text: str) -> bool:
    t = strip_md(text)
    return bool(re.fullmatch(r"\d{1,4}", t))


def is_running_header_like(text: str) -> bool:
    """
    泛化版 running header / footer 偵測：
    抓短 block 中常見的網址、DOI、作者 running header、期刊標頭等。
    盡量避免只寫死單一期刊名稱。
    """
    t = strip_md(text)
    lowered = t.lower()
    word_count = len(t.split())

    if not t:
        return False

    # 既有較穩定規則
    if "ieee transactions on" in lowered:
        return True
    if "journal of " in lowered and "vol." in lowered:
        return True
    if "downloaded on" in lowered and "ieee xplore" in lowered:
        return True
    if "authorized licensed use limited to" in lowered:
        return True
    if re.search(r"\bvol\.\s*\d+", lowered):
        return True

    # 常見網址 / publisher domain
    if DOMAIN_RE.search(t) and len(t) < 160:
        return True

    # 短 block + DOI + author style，常見於頁首頁尾
    if DOI_RE.search(t) and len(t) < 180:
        return True

    # 期刊 running header 風格：短、含 et al.
    if len(t) < 160 and "et al." in lowered:
        return True

    # 短 block，含期刊/前沿類詞，又不像自然句
    journalish_keywords = [
        "frontiers",
        "journal",
        "proceedings",
        "transactions",
        "review",
        "letters",
    ]
    if (
        len(t) < 180
        and any(k in lowered for k in journalish_keywords)
        and not re.search(r"[.!?]\s*$", t)
    ):
        return True

    # 特別短，而且包含 DOI / domain / 作者樣式，通常不是正文
    if word_count <= 12:
        if DOMAIN_RE.search(t):
            return True
        if DOI_RE.search(t):
            return True
        if "et al." in lowered:
            return True

    return False


def is_header_footer(text: str) -> bool:
    return is_running_header_like(text)


def is_license_or_copyright(text: str) -> bool:
    """
    保守版：
    只刪明顯純版權/授權/DOI 類 metadata block，
    避免像 abstract 這種長正文被誤刪。
    """
    t = strip_md(text).lower()
    wc = len(t.split())

    if "personal use is permitted" in t:
        return True
    if "republication/redistribution requires ieee permission" in t:
        return True
    if "rights/index.html" in t:
        return True
    if "see front matter" in t:
        return True
    if "digital object identifier" in t:
        return True
    if "copyright" in t and wc <= 40:
        return True
    if "creative commons attribution license" in t:
        return True

    # 很短的 DOI / 版權訊息才刪
    if "doi" in t and "10." in t and wc <= 25:
        return True
    if "© 20" in t and wc <= 20:
        return True
    if "published by elsevier science" in t and wc <= 30:
        return True

    return False


def is_footnote(text: str) -> bool:
    t = text.strip()
    return bool(re.match(r"^>\s*[\d∗*]+", t))


def is_image_placeholder(text: str) -> bool:
    t = strip_md(text).lower()
    return (
        ("picture" in t and "omitted" in t)
        or ("start of picture text" in t)
        or ("end of picture text" in t)
    )


def is_affiliation_or_manuscript(text: str) -> bool:
    raw = text.strip()
    t = strip_md(text).lower()

    if "manuscript received" in t:
        return True
    if "corresponding author" in t:
        return True
    if "e-mail:" in t or "email:" in t:
        return True
    if " is with " in t:
        return True
    if "institute of " in t or "school of " in t or "university" in t:
        return True
    if "supported by" in t and "grant" in t:
        return True
    if "national natural science foundation" in t:
        return True
    if "fundamental research fund" in t:
        return True
    if "received " in t and "accepted " in t:
        return True
    if "published " in t and len(raw) < 200:
        return True
    if "reviewed by" in t:
        return True
    if "edited by" in t:
        return True
    if "open access" in t and len(raw) < 120:
        return True
    if "citation" in t and len(raw) < 150:
        return True
    if "keywords" == t.strip():
        return True

    # very metadata-like affiliation line
    if len(raw) < 250 and raw.count("@") >= 1:
        return True

    return False


def is_table_like_block(text: str) -> bool:
    """
    抓表格 markdown / 表格殘片。
    這類通常不適合當正文 paragraph。
    """
    raw = text.strip()

    if not raw:
        return False

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        return False

    pipe_heavy_lines = sum(1 for line in lines if line.count("|") >= 2)
    dash_table_lines = sum(1 for line in lines if re.search(r"\|\s*[:-]+", line))

    if pipe_heavy_lines >= 2:
        return True
    if dash_table_lines >= 1:
        return True

    # 很短但很多欄位分隔符，也像表格殘片
    if raw.count("|") >= 6:
        return True

    return False


def is_caption_block(text: str) -> bool:
    t = text.strip()

    if not t:
        return False

    # 全大寫 FIGURE / TABLE + 空格 + 數字：直接刪
    if re.match(r"^(FIGURE|TABLE)\s+\d+\b", t):
        return True

    # fig / fig. / figure / table + 數字，且數字後面必須接 . 或 :
    if re.match(r"^(fig|fig\.|figure|table)\s*\d+[.:](?:\s|$)", t, flags=re.IGNORECASE):
        return True

    # 子圖標記
    if re.match(r"^\([a-z]\)\s", t):
        return True

    return False


def is_bullet_block(text: str) -> bool:
    t = strip_md(text)
    return bool(re.match(r"^[-•]\s*", t))


def is_intro_heading_title(title: str | None) -> bool:
    """
    判斷 section title 是否像 Introduction。
    支援：
    - Introduction
    - 1 Introduction
    - 1. Introduction
    - I. INTRODUCTION
    """
    if not title:
        return False

    t = strip_md(title).strip().lower()

    return bool(
        re.fullmatch(r"(?:\d+\.?\s+|[ivxlcdm]+\.\s+)?introduction", t)
    )


def looks_like_keywords_metadata_block(text: str) -> bool:
    """
    抓 Keywords / Index Terms 這類 metadata block。
    """
    t = strip_md(text).strip().lower()

    return (
        t.startswith("keywords:")
        or t.startswith("keywords ")
        or t.startswith("index terms")
        or t.startswith("key words")
    )


def looks_like_jel_block(text: str) -> bool:
    """
    抓 JEL / classification 類 metadata block。
    例如：
    - JEL classification: C 72; C 73; D 83
    - C 72; C 73; D 83
    """
    t = strip_md(text).strip()

    if re.match(r"(?i)^jel\s+classification\b", t):
        return True

    # 例如: C 72; C 73; D 83
    if re.fullmatch(r"(?:[A-Z]\s*\d{1,3})(?:\s*;\s*[A-Z]\s*\d{1,3}){1,10}", t):
        return True

    return False


def looks_like_abstract_section_candidate(blocks: list[str]) -> bool:
    """
    用來判斷文件最前面的 UNKNOWN section 是否其實是 abstract。
    條件盡量保守，只抓：
    - block 數量不多
    - 主要內容像自然語言正文
    - 不像 metadata
    """
    if not blocks:
        return False

    joined = "\n\n".join(blocks).strip()
    clean = strip_md(joined)

    if not clean:
        return False

    if looks_like_keywords_metadata_block(joined):
        return False

    if looks_like_jel_block(joined):
        return False

    # 至少要像一段摘要正文
    word_count = len(clean.split())
    if word_count < 60:
        return False

    # 至少兩個句子
    sentence_like = len(re.findall(r"[.!?]", clean))
    if sentence_like < 2:
        return False

    return True


def extract_section_title_from_text(text: str) -> Optional[str]:
    t = strip_md(text)

    if not t:
        return None

    upper = t.upper()

    # ABSTRACT
    if re.search(r"^\s*ABSTRACT\b", upper):
        return "ABSTRACT"

    # Tail headings
    if upper in TAIL_HEADINGS:
        return upper

    # Roman numeral major sections: I. INTRODUCTION
    m = re.match(r"^([IVXLC]+\.\s+[A-Z][A-Z0-9 \-–—,:()']{0,120})", t)
    if m:
        candidate = m.group(1).strip()
        words = candidate.split()
        if len(words) > 12:
            candidate = " ".join(words[:12])
        return candidate

    # Numbered headings with dot: 1. Introduction / 2.1 Background
    m = re.match(r"^(\d+(\.\d+)*\.?\s+[A-Z][A-Za-z0-9 \-–—,:()']{0,120})", t)
    if m:
        candidate = m.group(1).strip()
        words = candidate.split()
        if len(words) > 12:
            candidate = " ".join(words[:12])
        return candidate

    # Bare numbered heading: 3.
    if re.fullmatch(r"\d+\.", t):
        return t

    return None


def is_tail_heading(block: str) -> bool:
    title = extract_section_title_from_block(block)
    return title in TAIL_HEADINGS if title else False


def get_section_title(block: str) -> Optional[str]:
    return extract_section_title_from_block(block)


def is_major_section_heading(block: str) -> bool:
    title = extract_section_title_from_block(block)
    if not title:
        return False
    return title not in TAIL_HEADINGS


def should_remove_from_body(text: str) -> bool:
    return (
        is_page_number(text)
        or is_header_footer(text)
        or is_license_or_copyright(text)
        or is_footnote(text)
        or is_image_placeholder(text)
        or is_affiliation_or_manuscript(text)
        or is_table_like_block(text)
        or looks_like_keywords_metadata_block(text)
        or looks_like_jel_block(text)
    )


def looks_like_keywords_block(text: str) -> bool:
    t = strip_md(text).lower()
    return t.startswith("keywords") or t.startswith("index terms")


def looks_like_natural_body_paragraph(text: str) -> bool:
    """
    用來在前言區判斷某 block 是否像無標題 abstract / 正文段落。
    保守，不要太 aggressive。
    """
    t = strip_md(text)

    if not t:
        return False

    if should_remove_from_body(text):
        return False

    if is_caption_block(text):
        return False

    if is_bullet_block(text):
        return False

    if looks_like_keywords_block(text):
        return False

    wc = len(t.split())

    if wc < 35:
        return False

    # 至少像正常敘述句
    if not re.search(r"[.!?]", t):
        return False

    # 全大寫短句通常更像 heading，不像 abstract
    if wc <= 12 and t.upper() == t:
        return False

    return True


def split_document_blocks(blocks: List[str]) -> Dict[str, List[str]]:
    """
    將抽出的 blocks 分成：
    - front_matter_blocks
    - body_blocks
    - caption_blocks
    - removed_blocks

    新策略：
    - 不再用「第一個大標題前全部丟掉」
    - 在第一個 major section 前，允許保留像無標題 abstract 的長正文 block
    """
    front_matter_blocks: List[str] = []
    body_blocks: List[str] = []
    caption_blocks: List[str] = []
    removed_blocks: List[str] = []

    started_body = False
    abstract_candidate_blocks: List[str] = []

    for block in blocks:
        if should_remove_from_body(block):
            removed_blocks.append(block)
            continue

        if is_caption_block(block):
            caption_blocks.append(block)
            continue

        title = extract_section_title_from_block(block)
        clean = strip_md(block).lower()

        if not started_body:
            # 明確 abstract 標題
            if title == "ABSTRACT":
                started_body = True
                body_blocks.append(block)
                continue

            # 在正文開始前，如果有長而像自然正文的 block，
            # 先視為 abstract candidate 暫存，不立刻丟掉
            if looks_like_natural_body_paragraph(block):
                abstract_candidate_blocks.append(block)
                continue

            # 第一個 major section 出現 -> 正式開始正文
            if title is not None and title not in TAIL_HEADINGS:
                started_body = True

                # 若前面累積了 abstract candidate，先補回正文最前面
                if abstract_candidate_blocks:
                    body_blocks.extend(abstract_candidate_blocks)
                    abstract_candidate_blocks = []

                body_blocks.append(block)
                continue

            # 舊 fallback：某些情況 abstract 字樣出現在前 80 字
            if "abstract" in clean[:80]:
                started_body = True
                body_blocks.append(block)
                continue

            front_matter_blocks.append(block)
        else:
            if is_tail_heading(block):
                removed_blocks.append(block)
                break

            body_blocks.append(block)

    # 如果一直沒開始正文，但前面其實有 abstract-like block，就保留它們
    if not started_body and abstract_candidate_blocks:
        body_blocks.extend(abstract_candidate_blocks)

    # fallback：如果完全沒抓到正文，從第一個 major section-like block 開始，
    # 再不行就從第一個像長正文的 block 開始
    if not body_blocks:
        fallback_started = False
        new_front: List[str] = []

        for block in blocks:
            if should_remove_from_body(block) or is_caption_block(block):
                continue

            title = extract_section_title_from_block(block)
            clean = strip_md(block)

            if not fallback_started:
                if title is not None and title not in TAIL_HEADINGS:
                    fallback_started = True
                elif len(clean.split()) >= 20 and not clean.lower().startswith(("keywords", "index terms")):
                    fallback_started = True

            if fallback_started:
                body_blocks.append(block)
            else:
                new_front.append(block)

        if body_blocks:
            front_matter_blocks = new_front

    return {
        "front_matter_blocks": front_matter_blocks,
        "body_blocks": body_blocks,
        "caption_blocks": caption_blocks,
        "removed_blocks": removed_blocks,
    }


def starts_with_lowercase_alpha(text: str) -> bool:
    """
    找出文字中第一個英文字母，判斷是否為小寫。
    用來偵測跨頁續句，例如：
    'which ...', 'and ...', 'or ...'
    """
    text = text.strip()
    if not text:
        return False

    for ch in text:
        if ch.isalpha():
            return ch.islower()

    return False


def is_markdown_heading_block(text: str) -> bool:
    """
    判斷 block 是否明顯是 markdown heading。
    例如：
    ## I. INTRODUCTION
    ## _A. Multi-link Flavors_
    """
    first_line = text.splitlines()[0].strip() if text.strip() else ""
    return first_line.startswith("## ")


def should_merge_continuation(prev_text: str, curr_text: str) -> bool:
    prev_clean = strip_md(prev_text)
    curr_clean = strip_md(curr_text)

    if not prev_clean or not curr_clean:
        return False

    # 1. 明顯結構邊界：不要合併
    if is_markdown_heading_block(prev_text):
        return False
    if is_markdown_heading_block(curr_text):
        return False

    if is_major_section_heading(prev_text):
        return False
    if is_major_section_heading(curr_text):
        return False

    if is_bullet_block(curr_text):
        return False

    if is_caption_block(curr_text):
        return False

    if should_remove_from_body(curr_text):
        return False

    # 2. 前一塊若已完整結束，通常不要合併
    # 句號、問號、驚嘆號、冒號、分號結尾都視為完整
    if re.search(r"[.!?:;]\s*$", prev_clean):
        return False

    # 3. 典型 continuation：下一塊首字母是小寫
    # 例如 which / and / or / where / that ...
    if starts_with_lowercase_alpha(curr_clean):
        return True

    # 4. 常見續接詞開頭
    continuation_starters = {
        "which", "that", "where", "when", "and", "or", "but",
        "while", "because", "however", "thus", "therefore",
        "then", "also", "meanwhile"
    }
    first_word = curr_clean.split()[0].lower() if curr_clean.split() else ""
    if first_word in continuation_starters:
        return True

    # 5. 若下一塊以括號/數字/符號開頭，也可能是續接殘段
    if re.match(r"^[\(\[\{_\-–—=≤≥+\d\.]", curr_clean):
        return True

    # 6. 其餘情況保守處理：不要合併
    return False


def merge_continuation_blocks(blocks: List[str]) -> List[str]:
    if not blocks:
        return []

    merged: List[str] = [blocks[0]]

    for curr in blocks[1:]:
        prev = merged[-1]

        if should_merge_continuation(prev, curr):
            merged[-1] = prev.rstrip() + " " + curr.lstrip()
        else:
            merged.append(curr)

    return merged


def get_first_line(text: str) -> str:
    return text.splitlines()[0].strip()


def extract_section_title_from_block(block: str) -> Optional[str]:
    first_line = get_first_line(block)

    if not first_line:
        return None

    # abstract 特判：支援 _**Abstract**_ / **Abstract** / Abstract
    cleaned_first = first_line.replace("*", "").replace("_", "").replace("`", "").strip()
    if re.search(r"^\s*ABSTRACT\b", cleaned_first.upper()):
        return "ABSTRACT"

    # markdown heading：## 開頭
    if first_line.startswith("## "):
        heading_text = first_line[3:].strip()
        title = extract_section_title_from_text(heading_text)
        if title:
            return title

    # fallback：第一行本身就可能是純 major section
    title = extract_section_title_from_text(first_line)
    if title:
        return title

    return None


def split_blocks_into_sections_safe(blocks: list[str]):
    sections = []

    current_section = {
        "section_title": "UNKNOWN",
        "blocks": []
    }

    for block in blocks:
        title = extract_section_title_from_block(block)

        if title:
            if current_section["blocks"]:
                sections.append(current_section)

            current_section = {
                "section_title": title,
                "blocks": [block]
            }
        else:
            current_section["blocks"].append(block)

    if current_section["blocks"]:
        sections.append(current_section)

    # ---- abstract fallback heuristic ----
    # 若文件最前面是 UNKNOWN，且下一節是 Introduction，
    # 而 UNKNOWN 內容看起來像一段真正摘要，則將其改標為 ABSTRACT
    if len(sections) >= 2:
        first_section = sections[0]
        second_section = sections[1]

        if (
            first_section["section_title"] == "UNKNOWN"
            and is_intro_heading_title(second_section["section_title"])
            and looks_like_abstract_section_candidate(first_section["blocks"])
        ):
            first_section["section_title"] = "ABSTRACT"

    return sections


def build_chunks_from_sections(
    sections: List[Dict[str, Any]],
    max_chars: int = 2200,
) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    chunk_index = 0

    for section in sections:
        section_title = section["section_title"]
        blocks = section["blocks"]

        if not blocks:
            continue

        current_text = ""
        current_block_indices: List[int] = []

        for local_block_idx, block in enumerate(blocks):
            candidate = (current_text + "\n\n" + block).strip() if current_text else block

            if len(candidate) <= max_chars:
                current_text = candidate
                current_block_indices.append(local_block_idx)
            else:
                if current_text.strip():
                    chunks.append({
                        "chunk_index": chunk_index,
                        "section_title": section_title,
                        "source_block_indices_in_section": current_block_indices[:],
                        "text": current_text.strip(),
                    })
                    chunk_index += 1

                current_text = block
                current_block_indices = [local_block_idx]

        if current_text.strip():
            chunks.append({
                "chunk_index": chunk_index,
                "section_title": section_title,
                "source_block_indices_in_section": current_block_indices[:],
                "text": current_text.strip(),
            })
            chunk_index += 1

    return chunks
#v8