import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent,
} from "react";
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
  hoverTranslation?: string | string[] | null;
  hoverDelayMs?: number;
  onCreated: (highlight: TextHighlight) => void;
  onDeleted: (highlightId: number) => void;
};

type Segment =
  | { type: "plain"; text: string }
  | { type: "highlight"; text: string; highlight: TextHighlight };

type TranslationPopoverStyle = CSSProperties & {
  "--translation-arrow-left"?: string;
};

function normalizeHoverTranslation(
  hoverTranslation?: string | string[] | null
): string | null {
  if (Array.isArray(hoverTranslation)) {
    const text = hoverTranslation
      .map((item) => item.trim())
      .filter(Boolean)
      .join("\n");
    return text || null;
  }

  const text = hoverTranslation?.trim();
  return text || null;
}

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
  hoverTranslation = null,
  hoverDelayMs = 1200,
  onCreated,
  onDeleted,
}: Props) {
  const [showTranslation, setShowTranslation] = useState(false);
  const [translationPopoverStyle, setTranslationPopoverStyle] =
    useState<TranslationPopoverStyle>({});
  const wrapperRef = useRef<HTMLSpanElement | null>(null);
  const openTimerRef = useRef<number | null>(null);
  const closeTimerRef = useRef<number | null>(null);

  const normalizedHoverTranslation = useMemo(
    () => normalizeHoverTranslation(hoverTranslation),
    [hoverTranslation]
  );

  const canShowTranslation =
    language === "en" && !enabled && Boolean(normalizedHoverTranslation);

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

  useEffect(() => {
    return () => {
      if (openTimerRef.current) {
        window.clearTimeout(openTimerRef.current);
      }
      if (closeTimerRef.current) {
        window.clearTimeout(closeTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    setShowTranslation(false);
    if (openTimerRef.current) {
      window.clearTimeout(openTimerRef.current);
      openTimerRef.current = null;
    }
    if (closeTimerRef.current) {
      window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  }, [text, normalizedHoverTranslation, language, enabled]);

  useEffect(() => {
    if (!showTranslation) return;

    updateTranslationPopoverLayout();

    window.addEventListener("resize", updateTranslationPopoverLayout);
    return () => {
      window.removeEventListener("resize", updateTranslationPopoverLayout);
    };
  }, [showTranslation]);

  function clearOpenTimer() {
    if (openTimerRef.current) {
      window.clearTimeout(openTimerRef.current);
      openTimerRef.current = null;
    }
  }

  function clearCloseTimer() {
    if (closeTimerRef.current) {
      window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
  }

  function scheduleShowTranslation() {
    if (!canShowTranslation) return;

    clearOpenTimer();
    clearCloseTimer();

    openTimerRef.current = window.setTimeout(() => {
      updateTranslationPopoverLayout();
      setShowTranslation(true);
      openTimerRef.current = null;
    }, hoverDelayMs);
  }

  function scheduleHideTranslation() {
    clearOpenTimer();
    clearCloseTimer();

    closeTimerRef.current = window.setTimeout(() => {
      setShowTranslation(false);
      closeTimerRef.current = null;
    }, 140);
  }

  function keepTranslationVisible() {
    if (!canShowTranslation) return;
    clearOpenTimer();
    clearCloseTimer();
    updateTranslationPopoverLayout();
    setShowTranslation(true);
  }

  function findPopoverBoundary(wrapper: HTMLElement): HTMLElement | null {
    return wrapper.closest<HTMLElement>(
      ".reader-left, .overview-panel, .reader-grid, .content-row"
    );
  }

  function updateTranslationPopoverLayout() {
    const wrapper = wrapperRef.current;
    if (!wrapper) return;

    const boundary = findPopoverBoundary(wrapper);
    const wrapperRect = wrapper.getBoundingClientRect();
    const boundaryRect = boundary?.getBoundingClientRect();

    const safeGap = 18;
    const viewportWidth = window.innerWidth || document.documentElement.clientWidth;

    const leftBoundary = boundaryRect ? boundaryRect.left + safeGap : safeGap;
    const rightBoundary = boundaryRect
      ? boundaryRect.right - safeGap
      : viewportWidth - safeGap;

    const boundaryWidth = Math.max(280, rightBoundary - leftBoundary);
    const preferredWidth = Math.min(760, Math.max(460, boundaryWidth * 0.82));
    const width = Math.floor(Math.min(preferredWidth, boundaryWidth));

    let leftOffset = 0;
    const popoverLeft = wrapperRect.left + leftOffset;
    const popoverRight = popoverLeft + width;

    if (popoverRight > rightBoundary) {
      leftOffset -= popoverRight - rightBoundary;
    }

    if (wrapperRect.left + leftOffset < leftBoundary) {
      leftOffset += leftBoundary - (wrapperRect.left + leftOffset);
    }

    const arrowLeft = Math.max(18, Math.min(width - 18, 18 - leftOffset));

    setTranslationPopoverStyle({
      width,
      maxWidth: width,
      left: leftOffset,
      "--translation-arrow-left": `${arrowLeft}px`,
    });
  }

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

  async function handleMouseUp(e: MouseEvent<HTMLElement>) {
    if (!enabled) return;

    const container = e.currentTarget;
    const offsets = getSelectionOffsets(container);
    if (!offsets) return;
    if (!text.trim()) return;

    const exactMatch = normalizedHighlights.find(
      (h) => h.start_offset === offsets.start && h.end_offset === offsets.end
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

  return (
    <span
      ref={wrapperRef}
      className="highlightable-wrapper"
      onMouseEnter={scheduleShowTranslation}
      onMouseLeave={scheduleHideTranslation}
    >
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

      {showTranslation && normalizedHoverTranslation && (
        <span
          className="translation-popover"
          style={translationPopoverStyle}
          onMouseEnter={keepTranslationVisible}
          onMouseLeave={scheduleHideTranslation}
          onClick={(e) => e.stopPropagation()}
          role="note"
        >
          <span className="translation-popover-label">中文翻譯</span>
          <span className="translation-popover-content">
            {normalizedHoverTranslation}
          </span>
        </span>
      )}
    </span>
  );
}
