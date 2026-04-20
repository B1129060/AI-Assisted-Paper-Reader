import json
import re
from typing import List, Dict, Any, Tuple
import time

from openai import OpenAI

from app.config import settings


client_kwargs: Dict[str, Any] = {
    "api_key": settings.LLM_API_KEY,
}
if getattr(settings, "LLM_BASE_URL", None):
    client_kwargs["base_url"] = settings.LLM_BASE_URL

client = OpenAI(**client_kwargs)


def _normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_markdown_emphasis(text: str) -> str:
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"_(.*?)_", r"\1", text)
    return text.strip()


def _looks_like_caption(text: str) -> bool:
    t = text.strip()
    return bool(
        re.match(r"^(FIGURE|TABLE)\s+\d+\b", t)
        or re.match(r"^(fig|fig\.|figure|table)\s*\d+[.:](?:\s|$)", t, flags=re.IGNORECASE)
    )


def _looks_like_header_footer(text: str) -> bool:
    t = text.lower()
    if "ieee transactions on" in t:
        return True
    if "authorized licensed use limited to" in t:
        return True
    if "downloaded on" in t and "ieee xplore" in t:
        return True
    return False


def _looks_like_formula_noise(text: str) -> bool:
    t = text.strip()

    if len(t) < 20:
        return True

    symbol_count = sum(
        1 for ch in t
        if not ch.isalnum() and not ch.isspace()
    )
    ratio = symbol_count / max(len(t), 1)
    return ratio > 0.45


def _is_good_reading_text(text: str) -> bool:
    t = text.strip()

    if not t:
        return False
    if _looks_like_caption(t):
        return False
    if _looks_like_header_footer(t):
        return False
    if _looks_like_formula_noise(t):
        return False

    return True

def _looks_like_subsection_heading(text: str) -> bool:
    t = text.strip()

    # A. xxx / B. xxx / C. xxx
    if re.match(r"^[A-Z]\.\s+\S+", t):
        return True

    # (a) xxx / (b) xxx
    if re.match(r"^\([a-zA-Z]\)\s+\S+", t):
        return True

    # 3.1 xxx / 2.4.1 xxx
    if re.match(r"^\d+\.\d+(\.\d+)*\s+\S+", t):
        return True

    return False


def _looks_like_inline_label(text: str) -> bool:
    t = text.strip()

    if t.endswith(":"):
        return True

    if len(t) > 120:
        return True

    return False


def _looks_like_main_section_heading(text: str) -> bool:
    t = text.strip()

    if not t:
        return False

    # ABSTRACT 永遠保留
    if t.upper() == "ABSTRACT":
        return True

    # 明確排除副標題
    if _looks_like_subsection_heading(t):
        return False

    # 排除段內提示語
    if _looks_like_inline_label(t):
        return False

    # 常見主標題 1：Roman numeral
    if re.match(r"^[IVXLCM]+\.\s+\S+", t):
        return True

    # 常見主標題 2：整數編號
    if re.match(r"^\d+\.\s+\S+", t):
        return True

    # 常見主標題 3：全大寫短標題
    words = t.split()
    if 1 <= len(words) <= 8 and t == t.upper():
        return True

    return False

def _is_decimal_subsection_heading(text: str) -> bool:
    t = text.strip()
    return bool(re.match(r"^\d+\.\d+(\.\d+)*\s+\S+", t))


def _is_alpha_subsection_heading(text: str) -> bool:
    t = text.strip()
    return bool(
        re.match(r"^[A-Z]\.\s+\S+", t)
        or re.match(r"^\([a-zA-Z]\)\s+\S+", t)
    )


def _looks_like_fake_heading(text: str) -> bool:
    t = text.strip()

    if not t:
        return True

    if t.endswith(":"):
        return True

    if len(t) > 120:
        return True

    return False


def _fallback_split_chunk(chunk_text: str) -> List[str]:
    text = _normalize_text(chunk_text)
    parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    return [p for p in parts if _is_good_reading_text(p)]


def _fallback_summary(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    first = sentences[0].strip() if sentences else text.strip()
    return first[:180]


def _fallback_key_points(text: str) -> List[str]:
    text = text.strip()
    if len(text) <= 120:
        return [text]

    first = text[:120].strip()
    second = text[120:240].strip()

    points = [first]
    if second:
        points.append(second)

    return points


def _build_prompt(chunk_text: str, section_title: str) -> str:
    return f"""
You are processing a chunk from a scientific paper.

Your job:
1. Clean and reconstruct the text
2. Preserve document structure
3. Generate summaries

--------------------------------
STRUCTURE TYPES
--------------------------------

Output a JSON with "elements". Each element must be exactly one of:

1. heading
2. paragraph
3. bullet_list

--------------------------------
HEADING RULES
--------------------------------

- The provided section title is metadata only.
- DO NOT output the section title unless that heading text explicitly appears in the chunk.
- Keep headings ONLY if they exist explicitly in the chunk text.
- ONLY keep major section headings.
- DO NOT output subsection headings.
- DO NOT invent headings from semantic topic shifts.
- Do NOT turn emphasized sentences, inline labels, explanatory phrases, or list introductions into heading elements.
- If there is any uncertainty, keep the text as a paragraph instead of a heading.
- Use only:
  - "level": "section" for major headings
- Do NOT place major headings inside paragraph text.

Valid heading examples:
- "ABSTRACT"
- "I. INTRODUCTION"
- "II. A PRIMER ON MULTI-LINK OPERATION"
- "3. SYSTEM MODEL"
- "4. RESULTS"
- "CONCLUSION"

Invalid heading examples (keep as paragraph text instead):
- "A. Multi-link Flavors"
- "B. A Close-Up of STR EMLMR"
- "3.1 Channel Assignment"
- "3.2 Delay Reduction"
- "Delay anomaly in STR EMLMR:"
- "Mitigation strategies:"

--------------------------------
LIST / BULLET RULES
--------------------------------

- Detect logical lists such as:
  - lines starting with "-", "•"
  - enumerations like "(a)", "(b)"
- Group related consecutive bullet points into ONE bullet_list
- If there is an introducing sentence for the list, place it in "intro_text"
- DO NOT flatten a logical list into one paragraph
- DO NOT keep bullet markers ("-", "•") inside items
- DO NOT split one logical list into multiple separate lists unless the topic clearly changes

Each bullet_list must include:
- intro_text (optional; empty string allowed)
- items (list of strings)
- summary (ONE sentence summarizing the whole list)
- key_points (2 to 4 concise points summarizing the whole list)

--------------------------------
GENERAL RULES
--------------------------------

- Remove captions, headers, page footers, and obvious noise
- Keep meaning faithful to the source
- Do NOT hallucinate
- Keep wording close to original
- Fix obvious formatting artifacts when possible
- Return ONLY valid JSON
- No markdown fences

--------------------------------
OUTPUT FORMAT
--------------------------------

Return ONLY valid JSON in this format:

{{
  "elements": [
    {{
      "type": "heading",
      "text": "I. INTRODUCTION",
      "level": "section"
    }},
    {{
      "type": "heading",
      "text": "A. Multi-link Flavors",
      "level": "subsection"
    }},
    {{
      "type": "paragraph",
      "text": "....",
      "summary": "....",
      "key_points": ["....", "...."]
    }},
    {{
      "type": "bullet_list",
      "intro_text": "Our main takeaways can be summarized as follows:",
      "items": ["....", "....", "...."],
      "summary": "....",
      "key_points": ["....", "...."]
    }}
  ]
}}

--------------------------------

SECTION (metadata only):
{section_title}

TEXT:
{chunk_text}
""".strip()


def _extract_json_object(content: str) -> dict:
    content = content.strip()

    try:
        return json.loads(content)
    except Exception:
        pass

    fenced = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
    fenced = re.sub(r"\s*```$", "", fenced)
    fenced = fenced.strip()

    try:
        return json.loads(fenced)
    except Exception:
        pass

    match = re.search(r"\{.*\}", fenced, flags=re.DOTALL)
    if match:
        candidate = match.group(0)
        try:
            return json.loads(candidate)
        except Exception:
            pass

    return {"elements": []}


def _empty_usage() -> dict:
    return {
        "input": 0,
        "output": 0,
        "total": 0,
    }


def _call_llm(prompt: str, chunk_index: int) -> Tuple[dict, dict]:
    max_attempts = 3  # 第1次 + 額外重試2次

    for attempt in range(1, max_attempts + 1):
        try:
            response = client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise academic text processor. Return only valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    },
                ],
                temperature=0.2,
            )

            content = response.choices[0].message.content or ""

            usage_obj = getattr(response, "usage", None)
            usage = {
                "input": getattr(usage_obj, "prompt_tokens", 0) if usage_obj else 0,
                "output": getattr(usage_obj, "completion_tokens", 0) if usage_obj else 0,
                "total": getattr(usage_obj, "total_tokens", 0) if usage_obj else 0,
            }

            print(
                f"[LLM] chunk={chunk_index} "
                f"input={usage['input']} "
                f"output={usage['output']} "
                f"total={usage['total']}"
            )

            return _extract_json_object(content), usage

        except Exception as e:
            if attempt < max_attempts:
                time.sleep(1.0 * attempt)
                continue

            print(f"[LLM][ERROR] chunk={chunk_index} error={type(e).__name__}: {e}")
            return {"elements": []}, _empty_usage()


def process_chunk_with_llm(
    chunk_text: str,
    section_title: str,
    chunk_index: int,
) -> Tuple[List[dict], dict]:
    chunk_text = _normalize_text(chunk_text)

    if not chunk_text:
        print(f"[LLM] chunk={chunk_index} skipped=empty_chunk")
        return [], _empty_usage()

    prompt = _build_prompt(chunk_text, section_title)
    result, usage = _call_llm(prompt, chunk_index)

    elements = result.get("elements", [])
    outputs: List[dict] = []

    if isinstance(elements, list) and elements:
        for i, elem in enumerate(elements):
            if not isinstance(elem, dict):
                continue

            elem_type = str(elem.get("type", "")).strip().lower()

            # heading
            if elem_type == "heading":
                continue

            # bullet_list
            if elem_type == "bullet_list":
                intro_text = _strip_markdown_emphasis(
                    _normalize_text(str(elem.get("intro_text", "")).strip())
                )

                raw_items = elem.get("items", [])
                items: List[str] = []
                if isinstance(raw_items, list):
                    for item in raw_items:
                        item_clean = _strip_markdown_emphasis(
                            _normalize_text(str(item))
                        )
                        item_clean = re.sub(r"^[-•]\s*", "", item_clean).strip()
                        if item_clean and _is_good_reading_text(item_clean):
                            items.append(item_clean)

                if not items:
                    continue

                summary = _normalize_text(str(elem.get("summary", "")).strip())

                raw_key_points = elem.get("key_points", [])
                key_points: List[str] = []
                if isinstance(raw_key_points, list):
                    for kp in raw_key_points:
                        kp_clean = _normalize_text(str(kp))
                        if kp_clean:
                            key_points.append(kp_clean)

                outputs.append({
                    "chunk_index": chunk_index,
                    "paragraph_index_within_chunk": i,
                    "section_title": section_title,
                    "type": "bullet_list",
                    "intro_text": intro_text,
                    "items": items,
                    "summary": summary or _fallback_summary(" ".join(items)),
                    "key_points": key_points[:4] if key_points else _fallback_key_points(" ".join(items)),
                })
                continue

            # paragraph
            if elem_type != "paragraph":
                continue

            text = _strip_markdown_emphasis(
                _normalize_text(str(elem.get("text", "")).strip())
            )
            if not text:
                continue

            summary = _normalize_text(str(elem.get("summary", "")).strip())

            raw_key_points = elem.get("key_points", [])
            key_points: List[str] = []
            if isinstance(raw_key_points, list):
                for kp in raw_key_points:
                    kp_clean = _normalize_text(str(kp))
                    if kp_clean:
                        key_points.append(kp_clean)

            if not _is_good_reading_text(text):
                continue

            outputs.append({
                "chunk_index": chunk_index,
                "paragraph_index_within_chunk": i,
                "section_title": section_title,
                "type": "paragraph",
                "text": text,
                "summary": summary or _fallback_summary(text),
                "key_points": key_points[:4] if key_points else _fallback_key_points(text),
            })

    # fallback: 只保底 paragraph
    if not outputs:
        fallback_paragraphs = _fallback_split_chunk(chunk_text)

        print(
            f"[LLM][FALLBACK] chunk={chunk_index} "
            f"paragraphs={len(fallback_paragraphs)}"
        )

        for i, text in enumerate(fallback_paragraphs):
            outputs.append({
                "chunk_index": chunk_index,
                "paragraph_index_within_chunk": i,
                "section_title": section_title,
                "type": "paragraph",
                "text": _strip_markdown_emphasis(text),
                "summary": _fallback_summary(text),
                "key_points": _fallback_key_points(text),
            })

    print(f"[LLM] chunk={chunk_index} output_elements={len(outputs)}")
    return outputs, usage