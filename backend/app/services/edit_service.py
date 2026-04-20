import json
import re
from typing import Any, Dict, List

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import settings
from app.models.paper_overview import PaperOverview


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


def regenerate_paragraph_fields(text: str) -> dict:
    prompt = f"""
You are processing one academic paragraph.

Task:
1. Write one concise summary sentence.
2. Write 2 to 4 key points.

Rules:
- Use only the given paragraph.
- Do not hallucinate.
- Keep the meaning faithful.
- Return ONLY valid JSON.

Return format:
{{
  "summary": "...",
  "key_points": ["...", "..."]
}}

PARAGRAPH:
{text}
""".strip()

    data = _call_json_llm(prompt)

    summary = str(data.get("summary", "")).strip()
    key_points = [
        str(x).strip()
        for x in data.get("key_points", [])
        if str(x).strip()
    ]

    return {
        "summary": summary,
        "key_points": key_points,
    }


def regenerate_section_summary_en(section_title: str, paragraph_summaries: List[str]) -> str:
    source = "\n".join([f"- {s}" for s in paragraph_summaries if s and s.strip()])

    prompt = f"""
You are summarizing one main section of an academic paper.

Section title:
{section_title}

Task:
Write one concise section summary paragraph using only the paragraph summaries below.

Rules:
- Do not hallucinate.
- Keep it faithful and compact.
- Return ONLY valid JSON.

Return format:
{{
  "summary": "..."
}}

SOURCE:
{source}
""".strip()

    data = _call_json_llm(prompt)
    return str(data.get("summary", "")).strip()


def regenerate_section_summary_zh(section_title: str, paragraph_summaries_zh: List[str]) -> str:
    source = "\n".join([f"- {s}" for s in paragraph_summaries_zh if s and s.strip()])

    prompt = f"""
你正在為學術論文的一個主章節撰寫中文摘要。

章節標題：
{section_title}

任務：
根據下面提供的中文段落摘要，寫出一段精簡、自然的繁體中文章節摘要。

規則：
- 不要虛構內容
- 保持忠實
- 請只回傳 JSON

格式：
{{
  "summary": "..."
}}

來源：
{source}
""".strip()

    data = _call_json_llm(prompt)
    return str(data.get("summary", "")).strip()


def build_section_summaries_for_regeneration(
    paragraph_summaries_en: List[str],
    paragraph_summaries_zh: List[str],
) -> tuple[List[str], List[str]]:
    clean_en = [s.strip() for s in paragraph_summaries_en if s and s.strip()]
    clean_zh = [s.strip() for s in paragraph_summaries_zh if s and s.strip()]

    # 中文沒資料時，先 fallback 用英文 summary 生成中文章節摘要
    if not clean_zh:
        clean_zh = clean_en.copy()

    return clean_en, clean_zh


def update_section_summary_in_overview(
    db: Session,
    paper_id: int,
    section_title: str,
    section_summary_en: str,
    section_summary_zh: str,
) -> None:
    overview = db.query(PaperOverview).filter(PaperOverview.paper_id == paper_id).first()
    if not overview:
        return

    try:
        section_summaries = json.loads(overview.section_summaries) if overview.section_summaries else []
    except Exception:
        section_summaries = []

    try:
        section_summaries_zh = json.loads(overview.section_summaries_zh) if overview.section_summaries_zh else []
    except Exception:
        section_summaries_zh = []

    target_key = make_section_key(section_title)

    # 英文
    updated = False
    for item in section_summaries:
        item_key = item.get("section_key") or make_section_key(item.get("section_title"))
        if item_key == target_key:
            item["section_key"] = target_key
            item["section_title"] = section_title
            item["summary"] = section_summary_en
            updated = True
            break

    if not updated:
        section_summaries.append({
            "section_key": target_key,
            "section_title": section_title,
            "summary": section_summary_en,
        })

    # 中文
    updated_zh = False
    for item in section_summaries_zh:
        item_key = item.get("section_key") or make_section_key(item.get("section_title"))
        if item_key == target_key:
            item["section_key"] = target_key
            # 中文標題保留原本，不強制蓋成英文
            if not item.get("section_title"):
                item["section_title"] = section_title
            item["summary"] = section_summary_zh
            updated_zh = True
            break

    if not updated_zh:
        section_summaries_zh.append({
            "section_key": target_key,
            "section_title": section_title,
            "summary": section_summary_zh,
        })

    overview.section_summaries = json.dumps(section_summaries, ensure_ascii=False)
    overview.section_summaries_zh = json.dumps(section_summaries_zh, ensure_ascii=False)

def regenerate_bullet_fields(intro_text: str | None, items: List[str]) -> dict:
    intro = (intro_text or "").strip()
    clean_items = [str(x).strip() for x in items if str(x).strip()]

    source_parts = []
    if intro:
        source_parts.append(f"Intro text: {intro}")

    for idx, item in enumerate(clean_items, start=1):
        source_parts.append(f"Item {idx}: {item}")

    source = "\n".join(source_parts)

    prompt = f"""
You are processing one academic bullet list block.

Task:
1. Write one concise summary sentence.
2. Write 2 to 4 key points.

Rules:
- Use only the given bullet-list content.
- Do not hallucinate.
- Keep the meaning faithful.
- Return ONLY valid JSON.

Return format:
{{
  "summary": "...",
  "key_points": ["...", "..."]
}}

SOURCE:
{source}
""".strip()

    data = _call_json_llm(prompt)

    summary = str(data.get("summary", "")).strip()
    key_points = [
        str(x).strip()
        for x in data.get("key_points", [])
        if str(x).strip()
    ]

    return {
        "summary": summary,
        "key_points": key_points,
    }