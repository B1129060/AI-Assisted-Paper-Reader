from pathlib import Path
from app.services.pdf_parser import parse_pdf_to_chunks


def main():
    pdf_path = Path(r"D:\homework\2026_project\paper_reader\backend\uploads\ed46c970-583b-4384-a794-89de852aa01d.pdf")
    #ed46c970-583b-4384-a794-89de852aa01d
    #d3832510-1cce-40a8-8a19-5f501801e2fd
    #80a6ab09-9e30-4ebf-8feb-1c111b9e89c6
    #"D:\homework\2026_project\test_paper_4.pdf"
    #D:\homework\2026_project\paper_reader\backend\uploads\80a6ab09-9e30-4ebf-8feb-1c111b9e89c6.pdf

    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        return

    result = parse_pdf_to_chunks(str(pdf_path), debug=True)

    print("=" * 80)
    print("PARSE RESULT")
    print("=" * 80)
    print(f"Extractor: {result['extractor']}")
    print(f"PDF path: {result['pdf_path']}")
    print(f"Raw block count: {result['raw_block_count']}")
    print(f"Front matter block count: {result['front_matter_block_count']}")
    print(f"Body block count before merge: {result['body_block_count_before_merge']}")
    print(f"Body block count after merge: {result['body_block_count_after_merge']}")
    print(f"Caption block count: {result['caption_block_count']}")
    print(f"Removed block count: {result['removed_block_count']}")
    print(f"Section count: {result['section_count']}")
    print(f"Chunk count: {result['chunk_count']}")
    print("=" * 80)

    print("\nFIRST 3 CHUNKS PREVIEW\n")
    for chunk in result["chunks"][:3]:
        print(f"[Chunk {chunk['chunk_index']}]")
        print(f"section_title: {chunk.get('section_title')}")
        print(chunk["text"][:500])
        print("-" * 80)


if __name__ == "__main__":
    main()