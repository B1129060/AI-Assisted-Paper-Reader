import json
import os
from typing import List, Dict, Any


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def save_text(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_chunks_txt(path: str, chunks: List[Dict[str, Any]], include_context: bool = False) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("CHUNKS\n")
        f.write("=" * 80 + "\n\n")

        for ch in chunks:
            f.write(f"[Chunk {ch['chunk_index']}]\n")
            f.write(f"section_title: {ch.get('section_title')}\n")
            f.write(f"source_block_indices_in_section: {ch.get('source_block_indices_in_section')}\n\n")

            f.write("<<< TEXT >>>\n")
            f.write(ch["text"])
            f.write("\n\n")
            f.write("-" * 80 + "\n\n")