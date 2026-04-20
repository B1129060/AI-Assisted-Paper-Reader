from app.services.pdf_parser import parse_pdf_to_chunks
from app.services.llm_processor import process_chunk_with_llm
from app.services.paragraph_builder import build_paragraph_results


def process_uploaded_paper(
    paper_id: int,
    pdf_path: str,
    original_filename: str,
    debug: bool = True,
) -> dict:
    parsed = parse_pdf_to_chunks(pdf_path, debug=debug)
    chunks = parsed.get("chunks", [])
    position_data = parsed.get("position_data")

    raw_paragraphs: list[dict] = []

    total_input_tokens = 0
    total_output_tokens = 0
    total_tokens = 0

    for chunk in chunks:
        chunk_result, usage = process_chunk_with_llm(
            chunk_text=chunk["text"],
            section_title=chunk["section_title"],
            chunk_index=chunk["chunk_index"],
        )

        raw_paragraphs.extend(chunk_result)

        total_input_tokens += usage["input"]
        total_output_tokens += usage["output"]
        total_tokens += usage["total"]

    print("\n====== LLM TOKEN USAGE SUMMARY ======")
    print(f"Total input tokens:  {total_input_tokens}")
    print(f"Total output tokens: {total_output_tokens}")
    print(f"Total tokens:        {total_tokens}")
    print("====================================\n")

    # ⭐ 把 position_data 傳進 paragraph_builder
    paragraphs = build_paragraph_results(
        raw_paragraphs,
        position_data=position_data,
    )

    # 標準化成前端 / DB 之後都能吃的格式
    elements: list[dict] = []
    for idx, p in enumerate(paragraphs):
        normalized = dict(p)

        if "id" not in normalized:
            normalized["id"] = normalized.get("global_paragraph_index", idx)

        # 確保新欄位一定存在
        normalized.setdefault("page_number", None)
        normalized.setdefault("pdf_rects", [])

        elements.append(normalized)

    return {
        "paper_id": paper_id,
        "title": original_filename,
        "original_filename": original_filename,
        "stored_file_path": pdf_path,
        "parse_status": "processed",

        # 新格式：前端 detail API 使用
        "elements": elements,

        # 舊格式：暫時保留，避免你現有 response_model / 其他地方炸掉
        "paragraphs": elements,
    }