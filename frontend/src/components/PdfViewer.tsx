import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import type { HighlightColor, PdfHighlight } from "../types/highlight";
import "react-pdf/dist/Page/TextLayer.css";
import pdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker;

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
  pdfZoom: number;
  flashToken?: number;
  onCreatePdfHighlight: (payload: {
    page_number: number;
    rects: [number, number, number, number][];
  }) => Promise<void>;
  onDeletePdfHighlight: (highlightId: number) => Promise<void>;
};

export type PdfViewState = {
  pageNumber: number;
  offsetRatioX: number;
  offsetRatioY: number;
  viewportX: number;
  viewportY: number;
};

export type PdfViewerHandle = {
  captureZoomAnchor: () => void;
  captureViewState: () => PdfViewState | null;
  restoreViewState: (state: PdfViewState) => void;
};

type ZoomAnchor = {
  pageNumber: number;
  offsetRatioX: number;
  offsetRatioY: number;
  viewportX: number;
  viewportY: number;
};

function clamp(value: number, min: number, max: number) {
  if (!Number.isFinite(value)) return min;
  return Math.min(max, Math.max(min, value));
}

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

const PdfViewer = forwardRef<PdfViewerHandle, Props>(function PdfViewer({
  paperId,
  pdfUrl,
  highlightLocations = [],
  pdfHighlights,
  pdfHighlightMode,
  highlightColor,
  pdfZoom,
  flashToken = 0,
  onCreatePdfHighlight,
  onDeletePdfHighlight,
}: Props, ref) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const pageRefs = useRef<Record<number, HTMLDivElement | null>>({});

  const [numPages, setNumPages] = useState(0);
  const [containerWidth, setContainerWidth] = useState(0);
  const [pageViewports, setPageViewports] = useState<Record<number, any>>({});

  const [draggingPage, setDraggingPage] = useState<number | null>(null);
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const [dragCurrent, setDragCurrent] = useState<{ x: number; y: number } | null>(null);

  const prevPdfZoomRef = useRef(pdfZoom);
  const isZoomRestoringRef = useRef(false);
  const zoomRestoreTokenRef = useRef(0);
  const zoomAnchorRef = useRef<ZoomAnchor | null>(null);
  const lastAutoScrollFlashTokenRef = useRef<number | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageInput, setPageInput] = useState("1");
  const currentPageRef = useRef(1);
  const lastPdfUrlRef = useRef(pdfUrl);

  function updateCurrentPageState(pageNumber: number) {
    const safePage = Math.max(1, Math.min(pageNumber, numPages || pageNumber));
    currentPageRef.current = safePage;
    setCurrentPage(safePage);
    setPageInput(String(safePage));
  }
  
  const renderWidth = Math.max(containerWidth * pdfZoom, 200);

  useEffect(() => {
    if (lastPdfUrlRef.current === pdfUrl) return;

    lastPdfUrlRef.current = pdfUrl;
    pageRefs.current = {};
    setNumPages(0);
    setPageViewports({});
    updateCurrentPageState(1);

    const container = containerRef.current;
    if (container) {
      container.scrollTo({ top: 0, left: 0, behavior: "auto" });
    }
  }, [pdfUrl]);

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

  function getZoomAnchorFromDom(): ZoomAnchor | null {
    const container = containerRef.current;
    if (!container || numPages <= 0) return null;
    if (container.clientWidth <= 0 || container.clientHeight <= 0) return null;

    const viewportX = container.clientWidth * 0.5;
    const viewportY = container.clientHeight * 0.45;
    const absoluteX = container.scrollLeft + viewportX;
    const absoluteY = container.scrollTop + viewportY;

    let bestPageNumber = currentPageRef.current || currentPage || 1;
    let bestDistance = Number.POSITIVE_INFINITY;

    for (let pageNumber = 1; pageNumber <= numPages; pageNumber += 1) {
      const node = pageRefs.current[pageNumber];
      if (!node || node.offsetHeight <= 0 || node.offsetWidth <= 0) continue;

      const top = node.offsetTop;
      const bottom = node.offsetTop + node.offsetHeight;
      const center = top + node.offsetHeight / 2;
      const distance = absoluteY >= top && absoluteY <= bottom ? 0 : Math.abs(center - absoluteY);

      if (distance < bestDistance) {
        bestDistance = distance;
        bestPageNumber = pageNumber;
      }
    }

    const pageNode = pageRefs.current[bestPageNumber];
    if (!pageNode) return null;

    return {
      pageNumber: bestPageNumber,
      offsetRatioX: clamp((absoluteX - pageNode.offsetLeft) / Math.max(1, pageNode.offsetWidth), 0, 1),
      offsetRatioY: clamp((absoluteY - pageNode.offsetTop) / Math.max(1, pageNode.offsetHeight), 0, 1),
      viewportX,
      viewportY,
    };
  }

  function captureZoomAnchor() {
    // During a zoom restore, the PDF DOM is still changing size. Recapturing
    // from that unstable DOM is what caused rapid zoom clicks to drift upward
    // or downward. Keep the original stable anchor and only invalidate older
    // restore callbacks.
    if (isZoomRestoringRef.current && zoomAnchorRef.current) {
      zoomRestoreTokenRef.current += 1;
      return;
    }

    const anchor = getZoomAnchorFromDom();
    if (anchor) {
      zoomAnchorRef.current = anchor;
      isZoomRestoringRef.current = true;
      zoomRestoreTokenRef.current += 1;
    }
  }

  function captureViewState(): PdfViewState | null {
    return getZoomAnchorFromDom();
  }

  function restoreViewState(state: PdfViewState) {
    zoomAnchorRef.current = state;
    isZoomRestoringRef.current = true;
    zoomRestoreTokenRef.current += 1;

    const token = zoomRestoreTokenRef.current;

    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => restoreZoomAnchor(token));
    });
  }

  function restoreZoomAnchor(token: number, attempt = 0) {
    window.requestAnimationFrame(() => {
      if (token !== zoomRestoreTokenRef.current) return;

      const container = containerRef.current;
      const anchor = zoomAnchorRef.current;
      if (!container || !anchor) {
        isZoomRestoringRef.current = false;
        return;
      }

      const pageNode = pageRefs.current[anchor.pageNumber];
      if (!pageNode || pageNode.offsetHeight <= 0) {
        if (attempt < 10) {
          window.setTimeout(() => restoreZoomAnchor(token, attempt + 1), 40);
        }
        return;
      }

      const targetTop =
        pageNode.offsetTop + pageNode.offsetHeight * anchor.offsetRatioY - anchor.viewportY;
      const targetLeft =
        pageNode.offsetLeft + pageNode.offsetWidth * anchor.offsetRatioX - anchor.viewportX;

      const maxScrollTop = Math.max(container.scrollHeight - container.clientHeight, 0);
      const maxScrollLeft = Math.max(container.scrollWidth - container.clientWidth, 0);

      container.scrollTo({
        top: clamp(targetTop, 0, maxScrollTop),
        left: clamp(targetLeft, 0, maxScrollLeft),
        behavior: "auto",
      });

      updateCurrentPageState(anchor.pageNumber);

      if (attempt < 5) {
        window.setTimeout(() => restoreZoomAnchor(token, attempt + 1), attempt < 2 ? 0 : 50);
        return;
      }

      zoomAnchorRef.current = null;
      isZoomRestoringRef.current = false;
    });
  }

  useImperativeHandle(ref, () => ({
    captureZoomAnchor,
    captureViewState,
    restoreViewState,
  }));

  useEffect(() => {
    if (prevPdfZoomRef.current === pdfZoom) return;

    if (!zoomAnchorRef.current) {
      zoomAnchorRef.current = getZoomAnchorFromDom();
      zoomRestoreTokenRef.current += 1;
    }

    prevPdfZoomRef.current = pdfZoom;
    isZoomRestoringRef.current = true;
    const token = zoomRestoreTokenRef.current;

    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => restoreZoomAnchor(token));
    });
  }, [pdfZoom, renderWidth, numPages]);

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages);
    setPageViewports({});

    // A fresh document load should start with page 1 in the page control.
    // Language switches should keep the same pdfUrl, so they should not trigger
    // a fresh document load or reset the actual PDF view.
    updateCurrentPageState(1);
  }

  function onPageLoadSuccess(page: LoadedPage) {
    const baseViewport = page.getViewport({ scale: 1 });

    const baseWidth =
      containerRef.current?.clientWidth
        ? Math.max(containerRef.current.clientWidth - 24, 200)
        : containerWidth || 800;

    const actualWidth = Math.max(baseWidth * pdfZoom, 200);
    const actualScale = actualWidth / baseViewport.width;
    const viewport = page.getViewport({ scale: actualScale });

    setPageViewports((prev) => ({
      ...prev,
      [page.pageNumber]: viewport,
    }));
  }

  function goToPage(pageNumber: number, behavior: ScrollBehavior = "smooth") {
    const container = containerRef.current;
    const targetNode = pageRefs.current[pageNumber];

    if (!container || !targetNode) return;

    const clamped = Math.max(1, Math.min(pageNumber, numPages));

    const node = pageRefs.current[clamped];
    if (!node) return;

    const targetTop = Math.max(0, node.offsetTop - 8);

    container.scrollTo({
      top: targetTop,
      behavior,
    });

    updateCurrentPageState(clamped);
  }

  function goToPrevPage() {
    goToPage(currentPage - 1);
  }

  function goToNextPage() {
    goToPage(currentPage + 1);
  }

  

  useEffect(() => {
    if (isZoomRestoringRef.current) return;
    if (!highlightLocations.length) return;
    if (!containerRef.current) return;

    // Only auto-scroll when the caller explicitly changes flashToken, such as
    // clicking a paragraph on the left. Toggling PDF highlight mode can cause
    // PDF pages / viewports to rerender, and pageViewports updates used to
    // retrigger this effect and pull the viewer back to the last highlighted
    // paragraph. Keep pageViewports in the dependency list so a pending jump can
    // still run after pages finish rendering, but do not run again for the same
    // flashToken after a successful jump.
    if (flashToken <= 0) return;
    if (lastAutoScrollFlashTokenRef.current === flashToken) return;

    const firstLoc = highlightLocations[0];
    const pageNumber = firstLoc.page + 1;
    const viewport = pageViewports[pageNumber];
    const pageNode = pageRefs.current[pageNumber];
    const container = containerRef.current;

    if (!viewport || !pageNode) return;

    const timer = window.setTimeout(() => {
      if (isZoomRestoringRef.current) return;

      const rect = pdfRectToViewportRect(viewport, firstLoc.bbox);

      const targetLeft =
        pageNode.offsetLeft + rect.left + rect.width / 2 - container.clientWidth / 2;

      const targetTop =
        pageNode.offsetTop + rect.top + rect.height / 2 - container.clientHeight / 2;

      const maxScrollLeft = Math.max(container.scrollWidth - container.clientWidth, 0);
      const maxScrollTop = Math.max(container.scrollHeight - container.clientHeight, 0);

      lastAutoScrollFlashTokenRef.current = flashToken;
      updateCurrentPageState(pageNumber);

      container.scrollTo({
        left: Math.min(Math.max(targetLeft, 0), maxScrollLeft),
        top: Math.min(Math.max(targetTop, 0), maxScrollTop),
        behavior: "smooth",
      });
    }, 80);

    return () => window.clearTimeout(timer);
  }, [flashToken, highlightLocations, pageViewports]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || numPages === 0) return;

    function updateCurrentPageFromScroll() {
      const currentContainer = containerRef.current;
      if (!currentContainer || isZoomRestoringRef.current) return;

      const viewportCenter =
        currentContainer.scrollTop + currentContainer.clientHeight / 2;

      let bestPage = 1;
      let bestDistance = Number.POSITIVE_INFINITY;

      for (let pageNumber = 1; pageNumber <= numPages; pageNumber += 1) {
        const node = pageRefs.current[pageNumber];
        if (!node || node.offsetHeight <= 0) continue;

        const pageCenter = node.offsetTop + node.offsetHeight / 2;
        const distance = Math.abs(pageCenter - viewportCenter);

        if (distance < bestDistance) {
          bestDistance = distance;
          bestPage = pageNumber;
        }
      }

      updateCurrentPageState(bestPage);
    }

    const initialSync = window.setTimeout(updateCurrentPageFromScroll, 120);

    container.addEventListener("scroll", updateCurrentPageFromScroll, {
      passive: true,
    });

    return () => {
      window.clearTimeout(initialSync);
      container.removeEventListener("scroll", updateCurrentPageFromScroll);
    };
  }, [numPages]);

  return (
      <div className="pdf-viewer-shell">
        <div className="pdf-page-controls">
          <button onClick={goToPrevPage} disabled={currentPage <= 1}>
            Prev
          </button>

          <div className="pdf-page-jump">
            <input
              type="number"
              min={1}
              max={numPages || 1}
              value={pageInput}
              onChange={(e) => setPageInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  const next = Number(pageInput);
                  if (!Number.isNaN(next)) {
                    goToPage(next);
                  }
                }
              }}
              onBlur={() => {
                const next = Number(pageInput);
                if (!Number.isNaN(next)) {
                  goToPage(next, "auto");
                } else {
                  setPageInput(String(currentPage));
                }
              }}
            />
            <span>/ {numPages || 0}</span>
          </div>

          <button onClick={goToNextPage} disabled={currentPage >= numPages}>
            Next
          </button>
        </div>

        <div
          ref={containerRef}
          className="pdf-viewer"
          style={{
            width: "100%",
            height: "100%",
            minHeight: 0,
            overflow: "auto",
            padding: "8px 12px",
            boxSizing: "border-box",
            background: "#f6f6f6",
            position: "relative",
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
                    width: "max-content",
                    minWidth: "100%",
                  }}
                >
                  <div
                    style={{
                      position: "relative",
                      width: renderWidth || undefined,
                      marginLeft: "auto",
                      marginRight: "auto",
                    }}
                  >
                    {containerWidth > 0 && (
                      <Page
                        key={`page-${pageNumber}-${Math.round(renderWidth)}`}
                        pageNumber={pageNumber}
                        width={renderWidth}
                        renderTextLayer={true}
                        renderAnnotationLayer={false}
                        onLoadSuccess={onPageLoadSuccess}
                        onRenderSuccess={onPageLoadSuccess}
                      />
                    )}

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
    </div>
  );
});

export default PdfViewer;

// v217