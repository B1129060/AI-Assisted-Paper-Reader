import json
import re
from typing import Any, Dict, List

from openai import OpenAI

from app.config import settings


client_kwargs: Dict[str, Any] = {
    "api_key": settings.LLM_API_KEY,
}
if getattr(settings, "LLM_BASE_URL", None):
    client_kwargs["base_url"] = settings.LLM_BASE_URL

client = OpenAI(**client_kwargs)


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
        try:
            return json.loads(match.group(0))
        except Exception:
            pass

    return {}


def _call_json_llm(prompt: str) -> dict:
    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a precise academic summarizer. Return only valid JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2,
    )

    content = response.choices[0].message.content or ""
    return _extract_json_object(content)


def make_section_key(section_title: str) -> str:
    text = (section_title or "").strip().lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", "_", text).strip("_")
    return text


def _is_decimal_subsection_heading(text: str) -> bool:
    t = text.strip()
    return bool(re.match(r"^\d+\.\d+(\.\d+)*\s+\S+", t))


def _is_alpha_subsection_heading(text: str) -> bool:
    t = text.strip()
    return bool(
        re.match(r"^[A-Z]\.\s+\S+", t)
        or re.match(r"^\([a-zA-Z]\)\s+\S+", t)
    )


def _heading_style_family(text: str) -> str:
    t = text.strip()

    if t.upper() == "ABSTRACT":
        return "abstract"

    if re.match(r"^[IVXLCM]+\.\s+\S+", t):
        return "roman"

    if re.match(r"^\d+\.\s+\S+", t):
        return "integer"

    if 1 <= len(t.split()) <= 8 and t == t.upper():
        return "all_caps"

    return "other"


def normalize_heading_levels(elements: List[dict]) -> List[dict]:
    normalized = [dict(el) for el in elements]

    first_main_family = None
    for el in normalized:
        if el.get("type") != "heading":
            continue

        text = (el.get("text") or "").strip()
        if not text:
            continue

        if text.upper() == "ABSTRACT":
            continue

        if _is_decimal_subsection_heading(text) or _is_alpha_subsection_heading(text):
            continue

        first_main_family = _heading_style_family(text)
        if first_main_family != "other":
            break

    for el in normalized:
        if el.get("type") != "heading":
            continue

        text = (el.get("text") or "").strip()
        if not text:
            continue

        if text.upper() == "ABSTRACT":
            el["level"] = "section"
            continue

        if _is_decimal_subsection_heading(text):
            el["level"] = "subsection"
            continue

        if _is_alpha_subsection_heading(text):
            el["level"] = "subsection"
            continue

        fam = _heading_style_family(text)

        if first_main_family and fam == first_main_family:
            el["level"] = "section"
        else:
            el["level"] = "subsection"

    return normalized


def _build_overview_source(elements: List[dict]) -> str:
    lines: List[str] = []

    for el in elements:
        el_type = el.get("type")

        if el_type == "heading":
            heading = (el.get("text") or "").strip()
            level = (el.get("level") or "").strip()
            if heading:
                lines.append(f"[HEADING|{level}] {heading}")
            continue

        summary = (el.get("summary") or "").strip()
        key_points = el.get("key_points") or []
        element_id = el.get("id")

        if summary:
            lines.append(f"[ELEMENT {element_id} SUMMARY] {summary}")

        if key_points:
            for kp in key_points:
                kp = str(kp).strip()
                if kp:
                    lines.append(f"[ELEMENT {element_id} KEYPOINT] {kp}")

    return "\n".join(lines)


def _build_overview_prompt(elements: List[dict]) -> str:
    source = _build_overview_source(elements)

    return f"""
You are generating a paper-level overview from structured scientific paper elements.

Your task:
1. Write one overall summary of the whole paper.
2. Write 3 to 5 overall key points.
3. Select 3 to 6 most important element IDs.
4. For each selected element ID, provide:
   - element_id
   - title
   - summary

Rules:
- Use ONLY the provided structured evidence.
- Do NOT hallucinate.
- Keep titles short and informative.
- Keep the overall summary concise but complete.
- highlight_element_ids must come from the provided element IDs only.
- highlight_summaries must match the chosen highlight IDs.

Return ONLY valid JSON in this exact format:

{{
  "overall_summary": "...",
  "overall_key_points": ["...", "..."],
  "highlight_element_ids": [1, 2, 3],
  "highlight_summaries": [
    {{
      "element_id": 1,
      "title": "...",
      "summary": "..."
    }}
  ]
}}

SOURCE:
{source}
""".strip()



def _fallback_overview(elements: List[dict]) -> dict:
    """
    Deterministic fallback used when the LLM returns invalid JSON or an incomplete
    overview. It uses paragraph-level summaries/key points that already exist in
    the database, so the paper-level overview never becomes an empty successful
    result.
    """
    evidence_items: List[dict] = []
    current_section = ""

    for el in elements:
        el_type = el.get("type")

        if el_type == "heading":
            heading = str(el.get("text") or "").strip()
            if heading:
                current_section = heading
            continue

        if el_type not in ("paragraph", "bullet_list"):
            continue

        element_id = el.get("id")
        summary = str(el.get("summary") or "").strip()
        key_points = [str(kp).strip() for kp in (el.get("key_points") or []) if str(kp).strip()]

        if not summary and not key_points:
            continue

        evidence_items.append({
            "element_id": element_id,
            "section_title": current_section,
            "summary": summary,
            "key_points": key_points,
        })

    summary_parts = [item["summary"] for item in evidence_items if item["summary"]]
    overall_summary = " ".join(summary_parts[:3]).strip()
    if len(overall_summary) > 1200:
        overall_summary = overall_summary[:1200].rsplit(" ", 1)[0].strip() + "."

    overall_key_points: List[str] = []
    for item in evidence_items:
        for kp in item["key_points"]:
            if kp not in overall_key_points:
                overall_key_points.append(kp)
            if len(overall_key_points) >= 5:
                break
        if len(overall_key_points) >= 5:
            break

    if len(overall_key_points) < 3:
        for summary in summary_parts:
            if summary and summary not in overall_key_points:
                overall_key_points.append(summary)
            if len(overall_key_points) >= 3:
                break

    highlight_summaries: List[dict] = []
    highlight_element_ids: List[int] = []
    for item in evidence_items:
        summary = item["summary"]
        if not summary:
            continue

        try:
            element_id = int(item["element_id"])
        except Exception:
            continue

        title = item["section_title"] or f"Element {element_id}"
        highlight_element_ids.append(element_id)
        highlight_summaries.append({
            "element_id": element_id,
            "title": title[:120],
            "summary": summary,
        })

        if len(highlight_summaries) >= 5:
            break

    return {
        "overall_summary": overall_summary,
        "overall_key_points": overall_key_points[:5],
        "highlight_element_ids": highlight_element_ids,
        "highlight_summaries": highlight_summaries,
    }

def generate_overview(elements: List[dict]) -> dict:
    data = _call_json_llm(_build_overview_prompt(elements))

    overall_summary = str(data.get("overall_summary", "")).strip()
    overall_key_points = [
        str(x).strip()
        for x in data.get("overall_key_points", [])
        if str(x).strip()
    ]

    highlight_element_ids = []
    for x in data.get("highlight_element_ids", []):
        try:
            highlight_element_ids.append(int(x))
        except Exception:
            continue

    highlight_summaries = []
    for item in data.get("highlight_summaries", []):
        if not isinstance(item, dict):
            continue
        try:
            element_id = int(item.get("element_id"))
        except Exception:
            continue

        title = str(item.get("title", "")).strip()
        summary = str(item.get("summary", "")).strip()

        if not title and not summary:
            continue

        highlight_summaries.append({
            "element_id": element_id,
            "title": title,
            "summary": summary,
        })

    result = {
        "overall_summary": overall_summary,
        "overall_key_points": overall_key_points,
        "highlight_element_ids": highlight_element_ids,
        "highlight_summaries": highlight_summaries,
    }

    fallback = _fallback_overview(elements)

    if not result["overall_summary"]:
        result["overall_summary"] = fallback["overall_summary"]

    if not result["overall_key_points"]:
        result["overall_key_points"] = fallback["overall_key_points"]

    if not result["highlight_summaries"]:
        result["highlight_summaries"] = fallback["highlight_summaries"]
        result["highlight_element_ids"] = fallback["highlight_element_ids"]
    elif not result["highlight_element_ids"]:
        result["highlight_element_ids"] = [
            item["element_id"] for item in result["highlight_summaries"]
        ]

    return result


def _group_main_sections(elements: List[dict]) -> List[dict]:
    sections: List[dict] = []
    current = None

    for el in elements:
        if el.get("type") == "heading" and el.get("level") == "section":
            if current:
                sections.append(current)

            current = {
                "section_title": (el.get("text") or "").strip(),
                "elements": [],
            }
            continue

        if current is not None:
            if el.get("type") in ("paragraph", "bullet_list"):
                current["elements"].append(el)

    if current:
        sections.append(current)

    return [s for s in sections if s["section_title"] and s["elements"]]


def _build_section_prompt(section_title: str, section_elements: List[dict]) -> str:
    parts: List[str] = []

    for el in section_elements:
        summary = (el.get("summary") or "").strip()
        key_points = el.get("key_points") or []

        if summary:
            parts.append(f"[SUMMARY] {summary}")

        if key_points:
            for kp in key_points:
                kp = str(kp).strip()
                if kp:
                    parts.append(f"[KEYPOINT] {kp}")

    source = "\n".join(parts)

    return f"""
You are summarizing one main section of a scientific paper.

Section title:
{section_title}

Your task:
Write ONE concise summary paragraph for this section using only the provided evidence.

Rules:
- Use only the source evidence.
- Do not hallucinate.
- Keep the summary compact but informative.

Return ONLY valid JSON in this format:

{{
  "summary": "..."
}}

SOURCE:
{source}
""".strip()


def generate_section_summaries(elements: List[dict]) -> List[dict]:
    grouped_sections = _group_main_sections(elements)
    outputs: List[dict] = []

    for sec in grouped_sections:
        section_title = sec["section_title"]
        sec_elements = sec["elements"]

        data = _call_json_llm(_build_section_prompt(section_title, sec_elements))
        summary = str(data.get("summary", "")).strip()

        if not summary:
            collected = []
            for el in sec_elements:
                s = (el.get("summary") or "").strip()
                if s:
                    collected.append(s)
                if len(collected) >= 2:
                    break
            summary = " ".join(collected).strip()

        if summary:
            outputs.append({
                "section_key": make_section_key(section_title),
                "section_title": section_title,
                "summary": summary,
            })

    return outputs


def _element_has_text_evidence(el: dict) -> bool:
    if (el.get("summary") or "").strip():
        return True

    key_points = el.get("key_points") or []
    if any(str(kp).strip() for kp in key_points):
        return True

    if (el.get("text") or "").strip():
        return True

    if (el.get("intro_text") or "").strip():
        return True

    items = el.get("items") or []
    return any(str(item).strip() for item in items)


def _is_abstract_heading_text(text: str) -> bool:
    normalized = re.sub(r"[^a-z]", "", (text or "").lower())
    return normalized == "abstract" or normalized.startswith("abstract")


def _collect_abstract_candidates(elements: List[dict]) -> List[dict]:
    """
    The parser does not always emit an exact heading with text == ABSTRACT.
    This collector therefore tries several safe signals before falling back to
    the first evidence-bearing paragraphs, so regenerate does not get stuck
    forever with an empty abstract_summary.
    """
    candidates: List[dict] = []
    in_abstract = False

    for el in elements:
        if el.get("type") == "heading":
            text = (el.get("text") or "").strip()

            if _is_abstract_heading_text(text):
                in_abstract = True
                continue

            if in_abstract and el.get("level") == "section":
                break

        if in_abstract and el.get("type") in ("paragraph", "bullet_list"):
            if _element_has_text_evidence(el):
                candidates.append(el)

    if candidates:
        return candidates

    for el in elements:
        if el.get("type") not in ("paragraph", "bullet_list"):
            continue

        section_title = str(el.get("section_title") or "")
        if "abstract" in section_title.lower() and _element_has_text_evidence(el):
            candidates.append(el)

    if candidates:
        return candidates

    fallback: List[dict] = []
    for el in elements:
        if el.get("type") not in ("paragraph", "bullet_list"):
            continue
        if not _element_has_text_evidence(el):
            continue

        fallback.append(el)
        if len(fallback) >= 3:
            break

    return fallback


def _build_abstract_source(abstract_elements: List[dict]) -> str:
    parts: List[str] = []

    for el in abstract_elements:
        s = (el.get("summary") or "").strip()
        if s:
            parts.append(f"[SUMMARY] {s}")

        for kp in el.get("key_points") or []:
            kp = str(kp).strip()
            if kp:
                parts.append(f"[KEYPOINT] {kp}")

        if not s and not el.get("key_points"):
            text = (el.get("text") or el.get("intro_text") or "").strip()
            if text:
                parts.append(f"[TEXT] {text[:1200]}")

            for item in el.get("items") or []:
                item_text = str(item).strip()
                if item_text:
                    parts.append(f"[ITEM] {item_text[:800]}")

    return "\n".join(parts)


def _fallback_abstract_summary(abstract_elements: List[dict], all_elements: List[dict]) -> str:
    collected: List[str] = []

    for source_elements in (abstract_elements, all_elements):
        for el in source_elements:
            if el.get("type") not in ("paragraph", "bullet_list"):
                continue

            summary = (el.get("summary") or "").strip()
            if summary:
                collected.append(summary)
            else:
                text = (el.get("text") or el.get("intro_text") or "").strip()
                if text:
                    collected.append(text[:500])

            if len(collected) >= 2:
                break

        if collected:
            break

    summary = " ".join(collected).strip()
    if len(summary) > 1200:
        summary = summary[:1200].rsplit(" ", 1)[0].strip() + "."

    return summary


def generate_abstract_summary(elements: List[dict]) -> str:
    abstract_elements = _collect_abstract_candidates(elements)

    if not abstract_elements:
        return _fallback_abstract_summary([], elements)

    source = _build_abstract_source(abstract_elements)

    if not source.strip():
        return _fallback_abstract_summary(abstract_elements, elements)

    prompt = f"""
You are summarizing the abstract or opening evidence of a scientific paper.

Write ONE concise abstract-style summary using only the provided evidence.

Return ONLY valid JSON in this format:
{{
  "summary": "..."
}}

SOURCE:
{source}
""".strip()

    data = _call_json_llm(prompt)
    summary = str(data.get("summary", "")).strip()
    if summary:
        return summary

    return _fallback_abstract_summary(abstract_elements, elements)
