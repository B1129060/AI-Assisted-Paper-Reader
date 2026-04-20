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

    return {
        "overall_summary": overall_summary,
        "overall_key_points": overall_key_points,
        "highlight_element_ids": highlight_element_ids,
        "highlight_summaries": highlight_summaries,
    }


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

        try:
            data = _call_json_llm(_build_section_prompt(section_title, sec_elements))
            summary = str(data.get("summary", "")).strip()
        except Exception:
            summary = ""

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


def generate_abstract_summary(elements: List[dict]) -> str:
    abstract_elements: List[dict] = []
    in_abstract = False

    for el in elements:
        if el.get("type") == "heading":
            text = (el.get("text") or "").strip()

            if text.upper() == "ABSTRACT":
                in_abstract = True
                continue

            if in_abstract and el.get("level") == "section":
                break

        if in_abstract and el.get("type") in ("paragraph", "bullet_list"):
            abstract_elements.append(el)

    if not abstract_elements:
        return ""

    parts: List[str] = []
    for el in abstract_elements:
        s = (el.get("summary") or "").strip()
        if s:
            parts.append(f"[SUMMARY] {s}")
        for kp in el.get("key_points") or []:
            kp = str(kp).strip()
            if kp:
                parts.append(f"[KEYPOINT] {kp}")

    source = "\n".join(parts)

    prompt = f"""
You are summarizing the ABSTRACT section of a scientific paper.

Write ONE concise abstract summary using only the provided evidence.

Return ONLY valid JSON in this format:
{{
  "summary": "..."
}}

SOURCE:
{source}
""".strip()

    try:
        data = _call_json_llm(prompt)
        summary = str(data.get("summary", "")).strip()
        if summary:
            return summary
    except Exception:
        pass

    collected = []
    for el in abstract_elements:
        s = (el.get("summary") or "").strip()
        if s:
            collected.append(s)
        if len(collected) >= 2:
            break

    return " ".join(collected).strip()