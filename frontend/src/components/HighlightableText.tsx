import { useMemo } from "react";
import { createTextHighlight, deleteTextHighlight } from "../api/highlights";
import type { HighlightColor, TextHighlight } from "../types/highlight";

type Props = {
  paperId: number;
  paragraphId?: number | null;
  scope: "paragraph" | "overview";
  fieldName: string;
  itemIndex?: number | null;
  language: "en" | "zh";
  text: string;
  color: HighlightColor;
  highlights: TextHighlight[];
  enabled?: boolean;
  onCreated: (highlight: TextHighlight) => void;
  onDeleted: (highlightId: number) => void;
};

type Segment =
  | { type: "plain"; text: string }
  | { type: "highlight"; text: string; highlight: TextHighlight };

export default function HighlightableText({
  paperId,
  paragraphId = null,
  scope,
  fieldName,
  itemIndex = null,
  language,
  text,
  color,
  highlights,
  enabled = false,
  onCreated,
  onDeleted,
}: Props) {
  const relevantHighlights = useMemo(() => {
    return highlights
      .filter(
        (h) =>
          h.paper_id === paperId &&
          h.paragraph_id === paragraphId &&
          h.scope === scope &&
          h.field_name === fieldName &&
          h.item_index === itemIndex &&
          h.language === language
      )
      .sort((a, b) => a.start_offset - b.start_offset);
  }, [highlights, paperId, paragraphId, scope, fieldName, itemIndex, language]);

  // 避免重疊 highlight 造成文字重複、刪除不乾淨
  const normalizedHighlights = useMemo(() => {
    const result: TextHighlight[] = [];

    for (const h of relevantHighlights) {
      if (!result.length) {
        result.push(h);
        continue;
      }

      const last = result[result.length - 1];

      // 重疊就先忽略後來這筆，避免渲染切段錯亂
      if (h.start_offset < last.end_offset) {
        continue;
      }

      result.push(h);
    }

    return result;
  }, [relevantHighlights]);

  const segments = useMemo<Segment[]>(() => {
    if (!normalizedHighlights.length) return [{ type: "plain", text }];

    const result: Segment[] = [];
    let cursor = 0;

    for (const h of normalizedHighlights) {
      if (h.start_offset > cursor) {
        result.push({
          type: "plain",
          text: text.slice(cursor, h.start_offset),
        });
      }

      result.push({
        type: "highlight",
        text: text.slice(h.start_offset, h.end_offset),
        highlight: h,
      });

      cursor = h.end_offset;
    }

    if (cursor < text.length) {
      result.push({ type: "plain", text: text.slice(cursor) });
    }

    return result;
  }, [text, normalizedHighlights]);

  function getSelectionOffsets(
    container: HTMLElement
  ): { start: number; end: number } | null {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return null;

    const range = selection.getRangeAt(0);
    if (!container.contains(range.commonAncestorContainer)) return null;

    const preRange = range.cloneRange();
    preRange.selectNodeContents(container);
    preRange.setEnd(range.startContainer, range.startOffset);
    const start = preRange.toString().length;

    const selectedText = range.toString();
    const end = start + selectedText.length;

    if (!selectedText.trim()) return null;
    return { start, end };
  }

  async function handleMouseUp(e: React.MouseEvent<HTMLElement>) {
    if (!enabled) return;

    const container = e.currentTarget;
    const offsets = getSelectionOffsets(container);
    if (!offsets) return;
    if (!text.trim()) return;

    const exactMatch = normalizedHighlights.find(
        (h) =>
        h.start_offset === offsets.start &&
        h.end_offset === offsets.end
    );

    if (exactMatch) {
        try {
        await deleteTextHighlight(exactMatch.id);
        onDeleted(exactMatch.id);
        window.getSelection()?.removeAllRanges();
        } catch (err) {
        console.error(err);
        }
        return;
    }

    const hasOverlap = normalizedHighlights.some(
        (h) => !(offsets.end <= h.start_offset || offsets.start >= h.end_offset)
    );
    if (hasOverlap) {
        window.getSelection()?.removeAllRanges();
        return;
    }

    try {
        const created = await createTextHighlight({
        paper_id: paperId,
        paragraph_id: paragraphId,
        scope,
        field_name: fieldName,
        item_index: itemIndex,
        language,
        start_offset: offsets.start,
        end_offset: offsets.end,
        color,
        });
        onCreated(created);
        window.getSelection()?.removeAllRanges();
    } catch (err) {
        console.error(err);
    }
    }

  async function handleDeleteHighlight(highlightId: number) {
    try {
      await deleteTextHighlight(highlightId);
      onDeleted(highlightId);
    } catch (err) {
      console.error(err);
    }
  }

  return (
    <span className="highlightable-text" onMouseUp={handleMouseUp}>
      {segments.map((seg, idx) => {
        if (seg.type === "plain") {
          return <span key={idx}>{seg.text}</span>;
        }

        return (
          <mark
            key={idx}
            className={`hl-${seg.highlight.color}`}
            title={
              enabled
                ? "Select the same range again to remove highlight"
                : undefined
            }
          >
            {seg.text}
          </mark>
        );
      })}
    </span>
  );
}