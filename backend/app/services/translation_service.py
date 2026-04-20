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


def _sanitize_string_for_json(text: Any) -> str:
    if text is None:
        return ""

    text = str(text)
    text = text.encode("utf-8", "ignore").decode("utf-8", "ignore")
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", text)
    return text


def _sanitize_json_data(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _sanitize_json_data(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_json_data(x) for x in obj]
    if isinstance(obj, tuple):
        return [_sanitize_json_data(x) for x in obj]
    if obj is None:
        return None
    return _sanitize_string_for_json(obj)


def _extract_json_object(content: str) -> dict:
    content = content.strip()

    try:
        return json.loads(content)
    except Exception:
        pass

    fenced = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
    fenced = re.sub(r"\s*```$", "", fenced).strip()

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
    prompt = _sanitize_string_for_json(prompt)

    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a precise academic translator. Return only valid JSON."
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


def _translate_element_batch(batch: List[dict]) -> Dict[int, dict]:
    payload = []
    original_map: Dict[int, dict] = {}

    for el in batch:
        clean_el = {
            "id": int(el["id"]),
            "type": el.get("type"),
            "level": el.get("level"),
            "text": el.get("text"),
            "summary": el.get("summary"),
            "key_points": el.get("key_points"),
            "items": el.get("items"),
        }
        clean_el = _sanitize_json_data(clean_el)
        payload.append(clean_el)
        original_map[int(el["id"])] = clean_el

    prompt = f"""
Translate the following academic reading elements from English to Traditional Chinese.

Important:
- Preserve the exact item structure.
- Do NOT merge items.
- Do NOT split items.
- Do NOT remove items.
- Do NOT add extra items.
- Keep each element's id unchanged.
- Return translations matched to the SAME id.
- Heading elements must stay heading-like text, and must not be converted into paragraph content.
- Paragraphs must stay paragraphs.
- Bullet items must stay item-by-item.

Rules:
- Preserve meaning faithfully.
- Use natural Traditional Chinese used in academic reading.
- Keep technical terms consistent.
- Do NOT omit content.
- The number of translated key_points_zh must match the number of input key_points exactly.
- The number of translated items_zh must match the number of input items exactly.
- Translate each key point independently.
- Translate each list item independently.
- Return ONLY valid JSON.

Return format:
{{
  "elements": [
    {{
      "id": 1,
      "text_zh": "...",
      "summary_zh": "...",
      "key_points_zh": ["...", "..."],
      "items_zh": ["...", "..."]
    }}
  ]
}}

INPUT:
{json.dumps(payload, ensure_ascii=False)}
""".strip()

    data = _call_json_llm(prompt)
    translated = data.get("elements", [])

    results: Dict[int, dict] = {}

    if not isinstance(translated, list):
        return results

    for item in translated:
        if not isinstance(item, dict):
            continue

        try:
            el_id = int(item["id"])
        except Exception:
            continue

        if el_id not in original_map:
            continue

        orig = original_map[el_id]
        orig_key_points = orig.get("key_points") or []
        orig_items = orig.get("items") or []

        translated_key_points = item.get("key_points_zh")
        translated_items = item.get("items_zh")

        if not isinstance(translated_key_points, list) or len(translated_key_points) != len(orig_key_points):
            translated_key_points = [str(x) for x in orig_key_points]

        if not isinstance(translated_items, list) or len(translated_items) != len(orig_items):
            translated_items = [str(x) for x in orig_items]

        results[el_id] = {
            "text_zh": _sanitize_string_for_json(item.get("text_zh")),
            "summary_zh": _sanitize_string_for_json(item.get("summary_zh")),
            "key_points_zh": [_sanitize_string_for_json(x) for x in translated_key_points],
            "items_zh": [_sanitize_string_for_json(x) for x in translated_items],
        }

    return results


def translate_elements_to_zh(elements: List[dict], batch_size: int = 8) -> Dict[int, dict]:
    results: Dict[int, dict] = {}

    for start in range(0, len(elements), batch_size):
        batch = elements[start:start + batch_size]

        try:
            batch_result = _translate_element_batch(batch)
            results.update(batch_result)
        except Exception as e:
            print(f"[translate_elements_to_zh] batch failed, fallback to single element mode: {repr(e)}")

            for el in batch:
                try:
                    single_result = _translate_element_batch([el])
                    results.update(single_result)
                except Exception as single_e:
                    print(f"[translate_elements_to_zh] single element failed: id={el.get('id')} error={repr(single_e)}")
                    results[int(el["id"])] = {
                        "text_zh": el.get("text"),
                        "summary_zh": el.get("summary"),
                        "key_points_zh": el.get("key_points") or [],
                        "items_zh": el.get("items") or [],
                    }

    return results


def translate_overview_to_zh(overview: dict) -> dict:
    payload = {
        "abstract_summary": overview.get("abstract_summary", ""),
        "overall_summary": overview.get("overall_summary", ""),
        "overall_key_points": overview.get("overall_key_points", []),
        "highlight_summaries": overview.get("highlight_summaries", []),
        "section_summaries": overview.get("section_summaries", []),
    }
    payload = _sanitize_json_data(payload)

    prompt = f"""
Translate the following academic overview content from English to Traditional Chinese.

Rules:
- Preserve meaning faithfully.
- Use natural Traditional Chinese used in academic reading.
- Keep technical terms consistent.
- Do NOT omit content.
- Do NOT merge multiple key points into one.
- The number of translated overall_key_points_zh must match the number of input overall_key_points exactly.
- The number of translated section_summaries_zh must match the number of input section_summaries exactly.
- The number of translated highlight_summaries_zh must match the number of input highlight_summaries exactly.
- Keep section_key unchanged.
- Return ONLY valid JSON.

Return format:
{{
  "abstract_summary_zh": "...",
  "overall_summary_zh": "...",
  "overall_key_points_zh": ["...", "..."],
  "highlight_summaries_zh": [
    {{
      "element_id": 1,
      "title": "...",
      "summary": "..."
    }}
  ],
  "section_summaries_zh": [
    {{
      "section_key": "...",
      "section_title": "...",
      "summary": "..."
    }}
  ]
}}

INPUT:
{json.dumps(payload, ensure_ascii=False)}
""".strip()

    data = _call_json_llm(prompt)

    overall_key_points_zh = data.get("overall_key_points_zh", [])
    if not isinstance(overall_key_points_zh, list) or len(overall_key_points_zh) != len(payload["overall_key_points"]):
        overall_key_points_zh = [str(x) for x in payload["overall_key_points"]]

    highlight_summaries_zh = data.get("highlight_summaries_zh", [])
    if not isinstance(highlight_summaries_zh, list) or len(highlight_summaries_zh) != len(payload["highlight_summaries"]):
        highlight_summaries_zh = payload["highlight_summaries"]

    section_summaries_zh = data.get("section_summaries_zh", [])
    if not isinstance(section_summaries_zh, list) or len(section_summaries_zh) != len(payload["section_summaries"]):
        section_summaries_zh = payload["section_summaries"]

    return {
        "abstract_summary_zh": _sanitize_string_for_json(data.get("abstract_summary_zh")),
        "overall_summary_zh": _sanitize_string_for_json(data.get("overall_summary_zh")),
        "overall_key_points_zh": [_sanitize_string_for_json(x) for x in overall_key_points_zh],
        "highlight_summaries_zh": _sanitize_json_data(highlight_summaries_zh),
        "section_summaries_zh": _sanitize_json_data(section_summaries_zh),
    }