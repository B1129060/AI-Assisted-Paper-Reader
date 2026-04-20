import { useEffect, useMemo, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import type { HighlightColor, PdfHighlight } from "../types/highlight";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

type PdfLocation = {
  page: number;
  bbox: [number, number, number, number];
};

type LoadedPage = {
  pageNumber: number;
  getViewport: (params: { scale: number }) => any;
};

type Props = {
  paperId: number;
  pdfUrl: string;
  highlightLocations?: PdfLocation[];
  pdfHighlights: PdfHighlight[];
  pdfHighlightMode: boolean;
  highlightColor: HighlightColor;
  flashToken?: number;
  onCreatePdfHighlight: (payload: {
    page_number: number;
    rects: [number, number, number, number][];
  }) => Promise<void>;
  onDeletePdfHighlight: (highlightId: number) => Promise<void>;
};

function pdfRectToViewportRect(
  viewport: any,
  bbox: [number, number, number, number]
) {
  const [x0, y0, x1, y1] = bbox;
  const scale = viewport.scale;

  return {
    left: x0 * scale,
    top: y0 * scale,
    width: (x1 - x0) * scale,
    height: (y1 - y0) * scale,
  };
}

function ratioRectToViewportRect(
  viewport: any,
  rect: [number, number, number, number]
) {
  const [x0, y0, x1, y1] = rect;
  return {
    left: x0 * viewport.width,
    top: y0 * viewport.height,
    width: (x1 - x0) * viewport.width,
    height: (y1 - y0) * viewport.height,
  };
}

function buildRect(
  start: { x: number; y: number },
  end: { x: number; y: number }
) {
  return {
    left: Math.min(start.x, end.x),
    top: Math.min(start.y, end.y),
    width: Math.abs(end.x - start.x),
    height: Math.abs(end.y - start.y),
  };
}

export default function PdfViewer({
  paperId,
  pdfUrl,
  highlightLocations = [],
  pdfHighlights,
  pdfHighlightMode,
  highlightColor,
  flashToken = 0,
  onCreatePdfHighlight,
  onDeletePdfHighlight,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const pageRefs = useRef<Record<number, HTMLDivElement | null>>({});

  const [numPages, setNumPages] = useState(0);
  const [containerWidth, setContainerWidth] = useState(0);
  const [pageViewports, setPageViewports] = useState<Record<number, any>>({});

  const [draggingPage, setDraggingPage] = useState<number | null>(null);
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const [dragCurrent, setDragCurrent] = useState<{ x: number; y: number } | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const el = containerRef.current;

    const updateWidth = () => {
      const nextWidth = Math.max(el.clientWidth - 24, 200);
      setContainerWidth(nextWidth);
    };

    updateWidth();

    const observer = new ResizeObserver(() => {
      updateWidth();
    });

    observer.observe(el);

    return () => observer.disconnect();
  }, []);

  const locationsByPage = useMemo(() => {
    const map: Record<number, PdfLocation[]> = {};
    for (const loc of highlightLocations) {
      if (!map[loc.page]) {
        map[loc.page] = [];
      }
      map[loc.page].push(loc);
    }
    return map;
  }, [highlightLocations]);

  const userHighlightsByPage = useMemo(() => {
    const map: Record<number, PdfHighlight[]> = {};
    for (const h of pdfHighlights) {
      const zeroBasedPage = h.page_number - 1;
      if (!map[zeroBasedPage]) {
        map[zeroBasedPage] = [];
      }
      map[zeroBasedPage].push(h);
    }
    return map;
  }, [pdfHighlights]);

  useEffect(() => {
    if (!highlightLocations.length) return;

    const firstPageZeroBased = highlightLocations[0].page;
    const pageNumber = firstPageZeroBased + 1;

    const timer = window.setTimeout(() => {
      const target = pageRefs.current[pageNumber];
      if (target) {
        target.scrollIntoView({
          behavior: "smooth",
          block: "center",
        });
      }
    }, 80);

    return () => window.clearTimeout(timer);
  }, [flashToken, highlightLocations]);

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages);
    setPageViewports({});
  }

  function onPageLoadSuccess(page: LoadedPage) {
    const baseViewport = page.getViewport({ scale: 1 });

    const actualWidth =
      containerRef.current?.clientWidth
        ? Math.max(containerRef.current.clientWidth - 24, 200)
        : containerWidth || 800;

    const actualScale = actualWidth / baseViewport.width;
    const viewport = page.getViewport({ scale: actualScale });

    setPageViewports((prev) => ({
      ...prev,
      [page.pageNumber]: viewport,
    }));
  }

  return (
    <div
      ref={containerRef}
      className="pdf-viewer"
      style={{
        width: "100%",
        height: "100%",
        overflow: "auto",
        padding: "8px 12px",
        boxSizing: "border-box",
        background: "#f6f6f6",
      }}
    >
      <Document
        file={pdfUrl}
        onLoadSuccess={onDocumentLoadSuccess}
        loading={<div className="pdf-loading">Loading PDF...</div>}
        error={<div className="pdf-error">Failed to load PDF.</div>}
      >
        {Array.from({ length: numPages }, (_, i) => {
          const pageNumber = i + 1;
          const pageHighlights = locationsByPage[i] || [];
          const pageUserHighlights = userHighlightsByPage[i] || [];
          const viewport = pageViewports[pageNumber];

          return (
            <div
              key={`${paperId}-${pageNumber}`}
              ref={(node) => {
                pageRefs.current[pageNumber] = node;
              }}
              className="pdf-page-shell"
              style={{
                marginBottom: 24,
                display: "flex",
                justifyContent: "center",
              }}
            >
              <div
                style={{
                  position: "relative",
                  width: containerWidth || undefined,
                }}
              >
                {containerWidth > 0 && (
                  <Page
                    pageNumber={pageNumber}
                    width={containerWidth}
                    renderTextLayer={!pdfHighlightMode}
                    renderAnnotationLayer={false}
                    onLoadSuccess={onPageLoadSuccess}
                  />
                )}

                {/* 原本段落定位用高亮：藍色、持續顯示 */}
                {viewport && pageHighlights.length > 0 && (
                  <div
                    className="pdf-highlight-layer"
                    key={`${pageNumber}-${flashToken}`}
                    style={{
                      position: "absolute",
                      left: 0,
                      top: 0,
                      width: viewport.width,
                      height: viewport.height,
                      pointerEvents: "none",
                    }}
                  >
                    {pageHighlights.map((loc, idx) => {
                      const rect = pdfRectToViewportRect(viewport, loc.bbox);

                      return (
                        <div
                          key={`${pageNumber}-system-${idx}`}
                          className="pdf-highlight-box"
                          style={{
                            position: "absolute",
                            left: rect.left,
                            top: rect.top,
                            width: rect.width,
                            height: rect.height,
                            background: "rgba(80, 160, 255, 0.22)",
                            border: "2px solid rgba(40, 110, 220, 0.85)",
                            borderRadius: 4,
                            boxShadow: "0 0 0 2px rgba(80, 160, 255, 0.14)",
                            animation: "pdfFlash 1.2s ease-out",
                            boxSizing: "border-box",
                          }}
                        />
                      );
                    })}
                  </div>
                )}

                {/* 使用者自己的 PDF highlights
                    ON: 可刪除
                    OFF: 僅顯示，不攔事件，讓底下 text layer 可選字複製 */}
                {viewport &&
                  pageUserHighlights.map((h) =>
                    h.rects.map((rect, idx) => {
                      const rendered = ratioRectToViewportRect(
                        viewport,
                        rect as [number, number, number, number]
                      );

                      return (
                        <div
                          key={`${h.id}-${idx}`}
                          className={`pdf-user-highlight-box hl-${h.color}`}
                          style={{
                            position: "absolute",
                            left: rendered.left,
                            top: rendered.top,
                            width: rendered.width,
                            height: rendered.height,
                            borderRadius: 4,
                            zIndex: 30,
                            pointerEvents: pdfHighlightMode ? "auto" : "none",
                            background:
                              h.color === "yellow"
                                ? "rgba(255, 235, 59, 0.35)"
                                : h.color === "green"
                                ? "rgba(76, 175, 80, 0.28)"
                                : "rgba(244, 143, 177, 0.30)",
                            border:
                              h.color === "yellow"
                                ? "1px solid rgba(255, 193, 7, 0.85)"
                                : h.color === "green"
                                ? "1px solid rgba(56, 142, 60, 0.85)"
                                : "1px solid rgba(216, 27, 96, 0.85)",
                            boxSizing: "border-box",
                          }}
                          onDoubleClick={(e) => {
                            if (!pdfHighlightMode) return;
                            e.stopPropagation();
                            void onDeletePdfHighlight(h.id);
                          }}
                          title={
                            pdfHighlightMode
                              ? "Double click to remove highlight"
                              : undefined
                          }
                        />
                      );
                    })
                  )}

                {/* ON 時才可畫新框 */}
                {viewport && pdfHighlightMode && (
                  <div
                    style={{
                      position: "absolute",
                      left: 0,
                      top: 0,
                      width: viewport.width,
                      height: viewport.height,
                      cursor: "crosshair",
                      zIndex: 20,
                    }}
                    onMouseDown={(e) => {
                      const rect = e.currentTarget.getBoundingClientRect();
                      setDraggingPage(pageNumber);
                      setDragStart({
                        x: e.clientX - rect.left,
                        y: e.clientY - rect.top,
                      });
                      setDragCurrent({
                        x: e.clientX - rect.left,
                        y: e.clientY - rect.top,
                      });
                    }}
                    onMouseMove={(e) => {
                      if (draggingPage !== pageNumber || !dragStart) return;
                      const rect = e.currentTarget.getBoundingClientRect();
                      setDragCurrent({
                        x: e.clientX - rect.left,
                        y: e.clientY - rect.top,
                      });
                    }}
                    onMouseUp={async (e) => {
                      if (draggingPage !== pageNumber || !dragStart) return;
                      const rect = e.currentTarget.getBoundingClientRect();
                      const end = {
                        x: e.clientX - rect.left,
                        y: e.clientY - rect.top,
                      };

                      const box = buildRect(dragStart, end);

                      if (box.width > 4 && box.height > 4) {
                        const normalized: [number, number, number, number] = [
                          box.left / viewport.width,
                          box.top / viewport.height,
                          (box.left + box.width) / viewport.width,
                          (box.top + box.height) / viewport.height,
                        ];

                        await onCreatePdfHighlight({
                          page_number: pageNumber,
                          rects: [normalized],
                        });
                      }

                      setDraggingPage(null);
                      setDragStart(null);
                      setDragCurrent(null);
                    }}
                  />
                )}

                {viewport &&
                  pdfHighlightMode &&
                  draggingPage === pageNumber &&
                  dragStart &&
                  dragCurrent && (
                    <div
                      style={{
                        position: "absolute",
                        ...buildRect(dragStart, dragCurrent),
                        background:
                          highlightColor === "yellow"
                            ? "rgba(255, 235, 59, 0.20)"
                            : highlightColor === "green"
                            ? "rgba(76, 175, 80, 0.18)"
                            : "rgba(244, 143, 177, 0.18)",
                        border:
                          highlightColor === "yellow"
                            ? "2px dashed rgba(255, 193, 7, 0.85)"
                            : highlightColor === "green"
                            ? "2px dashed rgba(56, 142, 60, 0.85)"
                            : "2px dashed rgba(216, 27, 96, 0.85)",
                        zIndex: 21,
                        pointerEvents: "none",
                        boxSizing: "border-box",
                      }}
                    />
                  )}
              </div>
            </div>
          );
        })}
      </Document>
    </div>
  );
}