import { createRef, useEffect, useMemo, useRef, useState } from "react";
import type { PaperDetail, PaperOverview, Element, PdfLocation } from "../types/paper";
import type {
  HighlightColor,
  TextHighlight,
  PdfHighlight,
} from "../types/highlight";
import {
  fetchPaperDetail,
  translatePaperToZh,
  updateParagraph,
  updateBulletList,
  insertParagraphAfter,
  deleteParagraph,
} from "../api/papers";
import { fetchPaperOverview, regenerateOverview } from "../api/overview";
import {
  fetchHighlights,
  createPdfHighlight,
  deletePdfHighlight,
} from "../api/highlights";
import ElementRow from "../components/ElementRow";
import PdfViewer from "../components/PdfViewer";
import ReaderHeader from "../components/ReaderHeader";
import OverviewPanel from "../components/OverviewPanel";
import OverviewAudioPlayer from "../components/OverviewAudioPlayer";
import HighlightColorToolbar from "../components/HighlightColorToolbar";

type Props = {
  paperId: number;
  onBack: () => void;
};

function normalizeSectionKey(text: string) {
  return text.trim().toLowerCase();
}

function getStickyOffset() {
  const stickyTop = document.querySelector(".reader-sticky-top") as HTMLElement | null;
  if (!stickyTop) return 160;
  return stickyTop.getBoundingClientRect().height + 24;
}

function scrollWithOffset(element: HTMLElement, behavior: ScrollBehavior = "smooth") {
  const offset = getStickyOffset();
  const top = element.getBoundingClientRect().top + window.scrollY - offset;
  window.scrollTo({
    top: Math.max(0, top),
    behavior,
  });
}

export default function ReaderPage({ paperId, onBack }: Props) {
  const [paper, setPaper] = useState<PaperDetail | null>(null);
  const [overview, setOverview] = useState<PaperOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [showPdf, setShowPdf] = useState(true);
  const [language, setLanguage] = useState<"en" | "zh">("en");

  const [switchingLanguage, setSwitchingLanguage] = useState(false);
  const [regeneratingOverview, setRegeneratingOverview] = useState(false);

  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const toastTimerRef = useRef<number | null>(null);

  const [activeElementId, setActiveElementId] = useState<number | null>(null);
  const [highlightLocations, setHighlightLocations] = useState<PdfLocation[]>([]);

  const [flashElementId, setFlashElementId] = useState<number | null>(null);
  const [flashToken, setFlashToken] = useState(0);
  const [pdfFlashToken, setPdfFlashToken] = useState(0);

  const [highlightColor, setHighlightColor] = useState<HighlightColor>("yellow");
  const [textHighlights, setTextHighlights] = useState<TextHighlight[]>([]);
  const [pdfHighlights, setPdfHighlights] = useState<PdfHighlight[]>([]);
  const [pdfHighlightMode, setPdfHighlightMode] = useState(false);
  const [textHighlightMode, setTextHighlightMode] = useState(false);

  const pendingRestoreRef = useRef<{
    keepTop: boolean;
    paragraphId: number | null;
    paragraphViewportTop: number;
  } | null>(null);

  useEffect(() => {
    void loadPaper("en");
    return () => {
      if (toastTimerRef.current) {
        window.clearTimeout(toastTimerRef.current);
      }
    };
  }, [paperId]);

  function showToast(message: string, duration = 2600) {
    setToastMessage(message);

    if (toastTimerRef.current) {
      window.clearTimeout(toastTimerRef.current);
    }

    toastTimerRef.current = window.setTimeout(() => {
      setToastMessage(null);
      toastTimerRef.current = null;
    }, duration);
  }

  async function triggerBackgroundZhTranslation(currentPaper?: PaperDetail) {
    const targetPaper = currentPaper ?? paper;
    if (!targetPaper) return;

    if (
      targetPaper.zh_translation_status === "processing" ||
      targetPaper.zh_translation_status === "completed"
    ) {
      return;
    }

    if (targetPaper.zh_translation_status === "failed") {
      showToast("偵測到上次翻譯未完成，正在重新嘗試。");
    }

    try {
      const result = await translatePaperToZh(paperId);

      if (result.status === "translated" || result.status === "already_exists") {
        setPaper((prev) =>
          prev ? { ...prev, zh_translation_status: "completed" } : prev
        );
        showToast("中文內容已準備完成，可以切換查看。");
      } else if (result.status === "processing") {
        setPaper((prev) =>
          prev ? { ...prev, zh_translation_status: "processing" } : prev
        );
      }
    } catch (err) {
      console.error("Background Chinese translation failed:", err);
      setPaper((prev) =>
        prev ? { ...prev, zh_translation_status: "failed" } : prev
      );
    }
  }

  async function loadPaper(lang: "en" | "zh") {
    setLoading(true);
    try {
      const [paperData, overviewData, highlightData] = await Promise.all([
        fetchPaperDetail(paperId, lang),
        fetchPaperOverview(paperId, lang),
        fetchHighlights(paperId, lang),
      ]);

      setPaper(paperData);
      setOverview(overviewData);
      setTextHighlights(highlightData.text_highlights);
      setPdfHighlights(highlightData.pdf_highlights);
      setLanguage(lang);

      if (lang === "en") {
        void triggerBackgroundZhTranslation(paperData);
      }
    } catch (err) {
      console.error(err);
      alert("Failed to load paper");
    } finally {
      setLoading(false);
    }
  }

  async function refreshCurrentLanguageData() {
    const [paperData, overviewData, highlightData] = await Promise.all([
      fetchPaperDetail(paperId, language),
      fetchPaperOverview(paperId, language),
      fetchHighlights(paperId, language),
    ]);

    setPaper(paperData);
    setOverview(overviewData);
    setTextHighlights(highlightData.text_highlights);
    setPdfHighlights(highlightData.pdf_highlights);
  }

  function captureReadingAnchor() {
    if (window.scrollY <= 24) {
      pendingRestoreRef.current = {
        keepTop: true,
        paragraphId: null,
        paragraphViewportTop: 0,
      };
      return;
    }

    const rows = Array.from(
      document.querySelectorAll<HTMLElement>(".content-row[data-paragraph-id]")
    );

    if (rows.length === 0) {
      pendingRestoreRef.current = {
        keepTop: false,
        paragraphId: null,
        paragraphViewportTop: 0,
      };
      return;
    }

    const anchorY = getStickyOffset() + 24;

    let bestParagraphId: number | null = null;
    let bestViewportTop = 0;
    let bestDistance = Number.POSITIVE_INFINITY;

    for (const row of rows) {
      const rect = row.getBoundingClientRect();
      const rawId = row.getAttribute("data-paragraph-id");
      const paragraphId = rawId ? Number(rawId) : NaN;
      if (Number.isNaN(paragraphId)) continue;

      const distance = Math.abs(rect.top - anchorY);
      if (distance < bestDistance) {
        bestDistance = distance;
        bestParagraphId = paragraphId;
        bestViewportTop = rect.top;
      }
    }

    pendingRestoreRef.current = {
      keepTop: false,
      paragraphId: bestParagraphId,
      paragraphViewportTop: bestViewportTop,
    };
  }

  function restoreReadingAnchorIfNeeded() {
    const pending = pendingRestoreRef.current;
    if (!pending) return;

    if (pending.keepTop) {
      window.scrollTo({ top: 0, behavior: "auto" });
      pendingRestoreRef.current = null;
      return;
    }

    if (pending.paragraphId == null) {
      pendingRestoreRef.current = null;
      return;
    }

    const target = document.querySelector(
      `.content-row[data-paragraph-id="${pending.paragraphId}"]`
    ) as HTMLElement | null;

    if (target) {
      const absoluteTop =
        target.getBoundingClientRect().top + window.scrollY;

      const targetScrollTop = absoluteTop - pending.paragraphViewportTop;

      window.scrollTo({
        top: Math.max(0, targetScrollTop),
        behavior: "auto",
      });
    }

    pendingRestoreRef.current = null;
  }

  async function handleSwitchLanguage(lang: "en" | "zh") {
    if (lang === language) return;

    captureReadingAnchor();

    if (lang === "en") {
      await loadPaper("en");
      return;
    }

    if (!paper) return;

    if (paper.zh_translation_status === "completed") {
      try {
        setSwitchingLanguage(true);
        await loadPaper("zh");
      } catch (err) {
        console.error(err);
        alert("Failed to switch to Chinese");
      } finally {
        setSwitchingLanguage(false);
      }
      return;
    }

    if (paper.zh_translation_status === "processing") {
      showToast("中文內容仍在準備中，若長時間未完成，系統稍後會自動重試。");
      pendingRestoreRef.current = null;
      return;
    }

    if (paper.zh_translation_status === "failed") {
      showToast("先前中文翻譯失敗，正在重新嘗試。");
      try {
        setSwitchingLanguage(true);
        const result = await translatePaperToZh(paperId);
        if (result.status === "translated" || result.status === "already_exists") {
          setPaper((prev) =>
            prev ? { ...prev, zh_translation_status: "completed" } : prev
          );
          await loadPaper("zh");
        }
      } catch (err) {
        console.error(err);
        showToast("中文翻譯重新嘗試失敗。");
      } finally {
        setSwitchingLanguage(false);
      }
      return;
    }

    showToast("中文內容仍在準備中，請稍後再試。");
    pendingRestoreRef.current = null;
    void triggerBackgroundZhTranslation(paper);
  }

  async function handleSaveParagraph(paragraphId: number, text: string) {
    try {
      await updateParagraph(paragraphId, text);
      showToast("段落已更新，並重新生成摘要。");
      await refreshCurrentLanguageData();
    } catch (err) {
      console.error(err);
      showToast("更新段落失敗。");
      throw err;
    }
  }

  async function handleSaveBulletList(paragraphId: number, introText: string, items: string[]) {
    try {
      await updateBulletList(paragraphId, introText, items);
      showToast("條列段落已更新，並重新生成摘要。");
      await refreshCurrentLanguageData();
    } catch (err) {
      console.error(err);
      showToast("更新條列段落失敗。");
      throw err;
    }
  }

  async function handleInsertParagraphAfter(paragraphId: number, text: string) {
    try {
      await insertParagraphAfter(paragraphId, text);
      showToast("新段落已新增。");
      await refreshCurrentLanguageData();
    } catch (err) {
      console.error(err);
      showToast("新增段落失敗。");
      throw err;
    }
  }

  async function handleDeleteParagraph(paragraphId: number) {
    try {
      await deleteParagraph(paragraphId);
      showToast("段落已刪除。");
      await refreshCurrentLanguageData();
    } catch (err) {
      console.error(err);
      showToast("刪除段落失敗。");
      throw err;
    }
  }

  async function handleRegenerateOverview() {
    try {
      setRegeneratingOverview(true);
      await regenerateOverview(paperId);
      showToast("全文摘要與 highlights 已重新生成。");
      await refreshCurrentLanguageData();
    } catch (err) {
      console.error(err);
      showToast("重新生成全文摘要失敗。");
    } finally {
      setRegeneratingOverview(false);
    }
  }

  function handleTextHighlightCreated(highlight: TextHighlight) {
    setTextHighlights((prev) => [...prev, highlight]);
  }

  function handleTextHighlightDeleted(highlightId: number) {
    setTextHighlights((prev) => prev.filter((h) => h.id !== highlightId));
  }

  function handlePdfHighlightCreated(highlight: PdfHighlight) {
    setPdfHighlights((prev) => [...prev, highlight]);
  }

  function handlePdfHighlightDeleted(highlightId: number) {
    setPdfHighlights((prev) => prev.filter((h) => h.id !== highlightId));
  }

  async function handleCreatePdfHighlight(payload: {
    page_number: number;
    rects: [number, number, number, number][];
  }) {
    try {
      const created = await createPdfHighlight({
        paper_id: paperId,
        paragraph_id: null,
        page_number: payload.page_number,
        rects: payload.rects,
        color: highlightColor,
      });
      handlePdfHighlightCreated(created);
      showToast("PDF 重點已新增。");
    } catch (err) {
      console.error(err);
      showToast("新增 PDF 重點失敗。");
    }
  }

  async function handleDeletePdfHighlight(highlightId: number) {
    try {
      await deletePdfHighlight(highlightId);
      handlePdfHighlightDeleted(highlightId);
      showToast("PDF 重點已刪除。");
    } catch (err) {
      console.error(err);
      showToast("刪除 PDF 重點失敗。");
    }
  }

  function handleSelectElement(element: Element) {
    // 點同一段第二次就取消原本定位高亮
    if (activeElementId === element.id) {
      setActiveElementId(null);
      setHighlightLocations([]);
      setFlashElementId(null);
      return;
    }

    setActiveElementId(element.id);
    setHighlightLocations([...(element.pdf_locations || [])]);
    setFlashElementId(element.id);
    setFlashToken((prev) => prev + 1);
    setPdfFlashToken((prev) => prev + 1);
  }

  const sectionHeadingRefs = useMemo(() => {
    const refs: Array<ReturnType<typeof createRef<HTMLDivElement>>> = [];
    if (!paper) return refs;

    for (const el of paper.elements) {
      if (el.type === "heading" && el.level === "section") {
        refs.push(createRef<HTMLDivElement>());
      }
    }

    return refs;
  }, [paper]);

  const sectionHeadingEntries = useMemo(() => {
    if (!paper) return [];

    const entries: Array<{
      index: number;
      headingText: string;
      normalizedHeadingText: string;
      ref: ReturnType<typeof createRef<HTMLDivElement>>;
    }> = [];

    let sectionIndex = 0;
    for (const el of paper.elements) {
      if (el.type === "heading" && el.level === "section") {
        entries.push({
          index: sectionIndex,
          headingText: el.text || "",
          normalizedHeadingText: normalizeSectionKey(el.text || ""),
          ref: sectionHeadingRefs[sectionIndex],
        });
        sectionIndex += 1;
      }
    }

    return entries;
  }, [paper, sectionHeadingRefs]);

  useEffect(() => {
    if (loading) return;
    if (!paper) return;

    const timer = window.setTimeout(() => {
      restoreReadingAnchorIfNeeded();
    }, 80);

    return () => window.clearTimeout(timer);
  }, [loading, paper, overview, language]);

  function handleJumpToSection(sectionTitle: string) {
    if (!overview) return;

    const clickedIndex = overview.section_summaries.findIndex(
      (section) => section.section_title === sectionTitle
    );

    if (clickedIndex >= 0) {
      const targetEntry = sectionHeadingEntries[clickedIndex];
      if (targetEntry?.ref.current) {
        scrollWithOffset(targetEntry.ref.current, "smooth");
        return;
      }
    }

    const fallbackKey = normalizeSectionKey(sectionTitle);
    const fallbackEntry = sectionHeadingEntries.find(
      (entry) => entry.normalizedHeadingText === fallbackKey
    );

    if (fallbackEntry?.ref.current) {
      scrollWithOffset(fallbackEntry.ref.current, "smooth");
    }
  }

  if (loading) {
    return <div className="reader-page">Loading...</div>;
  }

  if (!paper) {
    return <div className="reader-page">Paper not found</div>;
  }

  let currentSectionHeadingIndex = 0;

  return (
    <div className="reader-page">
      <div className="reader-sticky-top">
        <ReaderHeader
          title={paper.title ?? paper.original_filename}
          filename={paper.original_filename}
          onBack={onBack}
        />

        <div className="reader-toolbar">
          <div className="reader-toolbar-row">
            <div className="toolbar-group">
              <button
                onClick={handleRegenerateOverview}
                disabled={switchingLanguage || regeneratingOverview}
              >
                {regeneratingOverview ? "Regenerating..." : "Regenerate Overview"}
              </button>
            </div>

            <div className="toolbar-group">
              <button
                className={language === "en" ? "active" : ""}
                onClick={() => handleSwitchLanguage("en")}
                disabled={switchingLanguage || regeneratingOverview}
              >
                English
              </button>
              <button
                className={language === "zh" ? "active" : ""}
                onClick={() => handleSwitchLanguage("zh")}
                disabled={switchingLanguage || regeneratingOverview}
              >
                中文
              </button>
            </div>

            <div className="toolbar-group">
              <button
                className={showPdf ? "active" : ""}
                onClick={() => setShowPdf((prev) => !prev)}
              >
                {showPdf ? "Hide PDF" : "Show PDF"}
              </button>
            </div>
          </div>

          <div className="reader-toolbar-row">
            <div className="toolbar-group">
              <HighlightColorToolbar
                color={highlightColor}
                onChange={setHighlightColor}
              />
            </div>

            <div className="toolbar-group">
              <button
                className={textHighlightMode ? "active" : ""}
                onClick={() => setTextHighlightMode((prev) => !prev)}
              >
                {textHighlightMode ? "Text Highlight Mode: ON" : "Text Highlight Mode: OFF"}
              </button>
            </div>

            <div className="toolbar-group">
              <button
                className={pdfHighlightMode ? "active" : ""}
                onClick={() => setPdfHighlightMode((prev) => !prev)}
              >
                {pdfHighlightMode ? "PDF Highlight Mode: ON" : "PDF Highlight Mode: OFF"}
              </button>
            </div>

            <div className="toolbar-group toolbar-audio-group">
              {overview && (
                <OverviewAudioPlayer overview={overview} language={language} />
              )}
            </div>
          </div>
        </div>
      </div>

      {toastMessage && <div className="toast-notice">{toastMessage}</div>}

      <div className={`reader-layout ${showPdf ? "with-pdf" : "no-pdf"}`}>
        <div className="reader-left">
          {overview && (
            <OverviewPanel
              paperId={paperId}
              overview={overview}
              language={language}
              textHighlightMode={textHighlightMode}
              highlightColor={highlightColor}
              textHighlights={textHighlights}
              onTextHighlightCreated={handleTextHighlightCreated}
              onTextHighlightDeleted={handleTextHighlightDeleted}
              onJumpToSection={handleJumpToSection}
            />
          )}

          <div className="reader-grid">
            <div className="column-header keypoints-header">Key Points</div>
            <div className="column-header summary-header">Summary</div>
            <div className="column-header text-header">Extracted Text</div>

            {paper.elements.map((element) => {
              let headingRef = undefined;

              if (element.type === "heading" && element.level === "section") {
                headingRef = sectionHeadingRefs[currentSectionHeadingIndex];
                currentSectionHeadingIndex += 1;
              }

              return (
                <ElementRow
                  key={element.id}
                  paperId={paperId}
                  element={element}
                  headingRef={headingRef}
                  currentLanguage={language}
                  textHighlightMode={textHighlightMode}
                  highlightColor={highlightColor}
                  textHighlights={textHighlights}
                  onTextHighlightCreated={handleTextHighlightCreated}
                  onTextHighlightDeleted={handleTextHighlightDeleted}
                  onSaveParagraph={handleSaveParagraph}
                  onSaveBulletList={handleSaveBulletList}
                  onInsertParagraphAfter={handleInsertParagraphAfter}
                  onDeleteParagraph={handleDeleteParagraph}
                  onSelectElement={handleSelectElement}
                  isFlashing={flashElementId === element.id}
                  flashToken={flashToken}
                />
              );
            })}
          </div>
        </div>

        {showPdf && (
          <div className="reader-right">
            <PdfViewer
              paperId={paperId}
              pdfUrl={`http://127.0.0.1:8000${paper.pdf_url}`}
              highlightLocations={highlightLocations}
              pdfHighlights={pdfHighlights}
              pdfHighlightMode={pdfHighlightMode}
              highlightColor={highlightColor}
              flashToken={pdfFlashToken}
              onCreatePdfHighlight={handleCreatePdfHighlight}
              onDeletePdfHighlight={handleDeletePdfHighlight}
            />
          </div>
        )}
      </div>
    </div>
  );
}

//save
    