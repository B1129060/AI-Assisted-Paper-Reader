# Optional debug export helpers gated by ENABLE_DEBUG_EXPORTS.

import json
import os
from typing import List, Dict, Any

from app.config import settings


# Read the debug export feature flag.
def debug_exports_enabled() -> bool:
    return bool(getattr(settings, "ENABLE_DEBUG_EXPORTS", False))


# Create a debug output directory only when debug exports are enabled.
def ensure_dir(path: str) -> None:
    if not debug_exports_enabled():
        return
    os.makedirs(path, exist_ok=True)


# Write a debug text file only when debug exports are enabled.
def save_text(path: str, content: str) -> None:
    if not debug_exports_enabled():
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# Write a debug JSON file only when debug exports are enabled.
def save_json(path: str, data: Any) -> None:
    if not debug_exports_enabled():
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# Write a human-readable chunk dump for parser debugging.
def save_chunks_txt(path: str, chunks: List[Dict[str, Any]], include_context: bool = False) -> None:
    if not debug_exports_enabled():
        return
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
