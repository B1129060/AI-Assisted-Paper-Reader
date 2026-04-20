import os
from app.config import settings
from app.services.extractors.pymupdf4llm_extractor import (
    extract_markdown_with_pymupdf4llm,
    extract_position_data_with_page_boxes,
)
from app.services.chunker import (
    split_markdown_blocks,
    split_document_blocks,
    merge_continuation_blocks,
    split_blocks_into_sections_safe,
    build_chunks_from_sections,
)
from app.services.debug_exporter import ensure_dir, save_text, save_json, save_chunks_txt


DEBUG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "debug"
)


def parse_pdf_to_chunks(pdf_path: str, debug: bool = False):
    extractor = settings.PDF_EXTRACTOR.lower()

    if extractor != "pymupdf4llm":
        raise ValueError("This parser version currently supports only pymupdf4llm.")

    # ========= 主線：維持原本 markdown parsing 流程 =========
    raw_markdown = extract_markdown_with_pymupdf4llm(pdf_path)
    raw_blocks = split_markdown_blocks(raw_markdown)

    split_result = split_document_blocks(raw_blocks)
    front_matter_blocks = split_result["front_matter_blocks"]
    body_blocks = split_result["body_blocks"]
    caption_blocks = split_result["caption_blocks"]
    removed_blocks = split_result["removed_blocks"]

    merged_body_blocks = merge_continuation_blocks(body_blocks)
    sections = split_blocks_into_sections_safe(merged_body_blocks)

    chunks = build_chunks_from_sections(
        sections,
        max_chars=settings.CHUNK_MAX_CHARS,
    )

    # ========= 支線：改用 pymupdf4llm page_boxes 抽位置資訊 =========
    position_data = extract_position_data_with_page_boxes(pdf_path)

    result = {
        "extractor": extractor,
        "pdf_path": pdf_path,

        # 主線統計
        "raw_block_count": len(raw_blocks),
        "front_matter_block_count": len(front_matter_blocks),
        "body_block_count_before_merge": len(body_blocks),
        "body_block_count_after_merge": len(merged_body_blocks),
        "caption_block_count": len(caption_blocks),
        "removed_block_count": len(removed_blocks),
        "section_count": len(sections),
        "chunk_count": len(chunks),

        # 主線資料
        "front_matter_blocks": front_matter_blocks,
        "caption_blocks": caption_blocks,
        "removed_blocks": removed_blocks,
        "sections": sections,
        "chunks": chunks,

        # 支線資料
        "position_data": position_data,
    }

    if debug:
        ensure_dir(DEBUG_DIR)
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        prefix = f"{base_name}_{extractor}_{settings.CHUNK_MAX_CHARS}"

        save_text(
            os.path.join(DEBUG_DIR, f"{prefix}_raw.md"),
            raw_markdown
        )

        save_json(
            os.path.join(DEBUG_DIR, f"{prefix}_raw_blocks.json"),
            [{"block_index": i, "text": b} for i, b in enumerate(raw_blocks)]
        )

        save_json(
            os.path.join(DEBUG_DIR, f"{prefix}_front_matter_blocks.json"),
            [{"block_index": i, "text": b} for i, b in enumerate(front_matter_blocks)]
        )

        save_json(
            os.path.join(DEBUG_DIR, f"{prefix}_body_blocks_before_merge.json"),
            [{"block_index": i, "text": b} for i, b in enumerate(body_blocks)]
        )

        save_json(
            os.path.join(DEBUG_DIR, f"{prefix}_body_blocks_after_merge.json"),
            [{"block_index": i, "text": b} for i, b in enumerate(merged_body_blocks)]
        )

        save_json(
            os.path.join(DEBUG_DIR, f"{prefix}_caption_blocks.json"),
            [{"block_index": i, "text": b} for i, b in enumerate(caption_blocks)]
        )

        save_json(
            os.path.join(DEBUG_DIR, f"{prefix}_removed_blocks.json"),
            [{"block_index": i, "text": b} for i, b in enumerate(removed_blocks)]
        )

        save_json(
            os.path.join(DEBUG_DIR, f"{prefix}_sections.json"),
            sections
        )

        save_json(
            os.path.join(DEBUG_DIR, f"{prefix}_chunks.json"),
            chunks
        )

        save_chunks_txt(
            os.path.join(DEBUG_DIR, f"{prefix}_chunks.txt"),
            chunks,
            include_context=False,
        )

        save_json(
            os.path.join(DEBUG_DIR, f"{prefix}_position_data.json"),
            position_data
        )

    return result