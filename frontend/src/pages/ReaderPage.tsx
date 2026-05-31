import {
  createRef,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import type {
  PaperDetail,
  PaperOverview,
  Element,
  PdfLocation,
} from "../types/paper";
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
  deletePaper,
  updatePaperTitle,
} from "../api/papers";
import { fetchPaperOverview, regenerateOverview } from "../api/overview";
import {
  fetchHighlights,
  createPdfHighlight,
  deletePdfHighlight,
} from "../api/highlights";
import ElementRow from "../components/ElementRow";
import PdfViewer, { type PdfViewerHandle, type PdfViewState } from "../components/PdfViewer";
import OverviewPanel from "../components/OverviewPanel";
import OverviewAudioPlayer from "../components/OverviewAudioPlayer";
import HighlightColorToolbar from "../components/HighlightColorToolbar";
import ExportModal from "../components/ExportModal";
import { API_BASE } from "../api/apiConfig";

type Props = {
  paperId: number;
  onBack: () => void;
};

function normalizeSectionKey(text: string) {
  return text.trim().toLowerCase();
}

function normalizeTaskStatus(status?: string | null) {
  return (status || "").toLowerCase();
}

function getFriendlyReaderError(
  message?: string | null,
  fallbackType?: "parse" | "overview" | "translation" | "processing",
) {
  const lower = (message || "").toLowerCase();

  if (
    lower.includes("insufficient_quota") ||
    lower.includes("quota") ||
    lower.includes("billing") ||
    lower.includes("額度不足") ||
    lower.includes("帳單")
  ) {
    return "LLM API 額度不足或帳單設定不可用，請確認 API key 的額度 / billing 後再重新嘗試。";
  }

  if (
    lower.includes("invalid_api_key") ||
    lower.includes("invalid api key") ||
    lower.includes("incorrect api key") ||
    lower.includes("unauthorized") ||
    lower.includes("未授權") ||
    lower.includes("key 無效")
  ) {
    return "LLM API key 無效或未授權，請確認 API key 設定後再重新嘗試。";
  }

  if (lower.includes("rate limit") || lower.includes("ratelimit") || lower.includes("請求過於頻繁")) {
    return "LLM API 請求過於頻繁，請稍後再重新嘗試。";
  }

  if (fallbackType === "parse" || lower.includes("parse") || lower.includes("processing failed")) {
    return "這份 PDF 解析失敗，請刪除後重新上傳，或改用另一份 PDF。";
  }

  if (lower.includes("timed out") || lower.includes("timeout")) {
    return "系統處理時間過長，已停止本次任務。你可以重新嘗試，若仍失敗請稍後再試。";
  }

  if (
    fallbackType === "translation" ||
    lower.includes("translation") ||
    lower.includes("chinese") ||
    lower.includes("中文")
  ) {
    return "中文翻譯失敗。你可以使用 Retry Translation 重新嘗試翻譯。";
  }

  if (fallbackType === "overview" || lower.includes("overview") || lower.includes("summary")) {
    return "全文摘要生成失敗。你可以使用 Retry Overview 重新生成全文摘要。";
  }

  if (lower.includes("pdf file not found") || lower.includes("original pdf file not found")) {
    return "找不到原始 PDF 檔案，請重新上傳。";
  }

  if (fallbackType === "processing") {
    return "系統正在處理內容，完成後會更新狀態；若長時間未完成，系統會自動轉為失敗並提供恢復方式。";
  }

  return "系統處理時發生錯誤，請重新整理狀態或稍後再試。";
}

export default function ReaderPage({ paperId, onBack }: Props) {
  const [paper, setPaper] = useState<PaperDetail | null>(null);
  const [overview, setOverview] = useState<PaperOverview | null>(null);
  const [hoverPaperZh, setHoverPaperZh] = useState<PaperDetail | null>(null);
  const [hoverOverviewZh, setHoverOverviewZh] = useState<PaperOverview | null>(
    null,
  );
  const [audioPaperEn, setAudioPaperEn] = useState<PaperDetail | null>(null);
  const [audioOverviewEn, setAudioOverviewEn] = useState<PaperOverview | null>(null);
  const [audioPaperZh, setAudioPaperZh] = useState<PaperDetail | null>(null);
  const [audioOverviewZh, setAudioOverviewZh] = useState<PaperOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [showPdf, setShowPdf] = useState(true);
  const [language, setLanguage] = useState<"en" | "zh">("en");

  const [switchingLanguage, setSwitchingLanguage] = useState(false);
  const [regeneratingOverview, setRegeneratingOverview] = useState(false);
  const [retryingTranslation, setRetryingTranslation] = useState(false);
  const [refreshingStatus, setRefreshingStatus] = useState(false);

  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const toastTimerRef = useRef<number | null>(null);
  const notFoundRedirectingRef = useRef(false);
  const notFoundRedirectTimerRef = useRef<number | null>(null);

  const [activeElementId, setActiveElementId] = useState<number | null>(null);
  const [highlightLocations, setHighlightLocations] = useState<PdfLocation[]>(
    [],
  );

  const [flashElementId, setFlashElementId] = useState<number | null>(null);
  const [flashToken, setFlashToken] = useState(0);
  const [pdfFlashToken, setPdfFlashToken] = useState(0);

  const [highlightColor, setHighlightColor] =
    useState<HighlightColor>("yellow");
  const [textHighlights, setTextHighlights] = useState<TextHighlight[]>([]);
  const [pdfHighlights, setPdfHighlights] = useState<PdfHighlight[]>([]);
  const [pdfHighlightMode, setPdfHighlightMode] = useState(false);
  const [textHighlightMode, setTextHighlightMode] = useState(false);

  const [pdfZoom, setPdfZoom] = useState(1);
  const [showExportModal, setShowExportModal] = useState(false);
  const [showDeletePaperModal, setShowDeletePaperModal] = useState(false);
  const [deletingPaper, setDeletingPaper] = useState(false);
  const [editingPaperTitle, setEditingPaperTitle] = useState(false);
  const [paperTitleDraft, setPaperTitleDraft] = useState("");
  const [savingPaperTitle, setSavingPaperTitle] = useState(false);

  const pdfViewerRef = useRef<PdfViewerHandle | null>(null);
  const pdfViewStateRef = useRef<PdfViewState | null>(null);
  const leftPanelRef = useRef<HTMLDivElement | null>(null);

  const pendingRestoreRef = useRef<
    | { mode: "top" }
    | { mode: "overview"; anchorViewportTop: number; overviewOffsetRatio: number; scrollRatio: number }
    | { mode: "paragraph"; paragraphId: number; anchorViewportTop: number; rowOffsetRatio: number }
    | { mode: "scroll"; scrollTop: number; scrollRatio: number }
    | null
  >(null);

  useEffect(() => {
    void loadPaper("en", { fullPageLoading: true });
    return () => {
      if (toastTimerRef.current) {
        window.clearTimeout(toastTimerRef.current);
      }
      if (notFoundRedirectTimerRef.current) {
        window.clearTimeout(notFoundRedirectTimerRef.current);
      }
    };
  }, [paperId]);

  useEffect(() => {
    if (!paper || loading) return;

    const activeStatuses = [
      normalizeTaskStatus(paper.parse_status),
      normalizeTaskStatus(paper.overview_status),
      normalizeTaskStatus(paper.zh_translation_status),
    ];

    const shouldPoll = activeStatuses.some((status) =>
      status === "queued" || status === "processing"
    );

    if (!shouldPoll) return;

    const timer = window.setInterval(() => {
      void refreshCurrentLanguageData().catch((err) => {
        if (handlePaperNotFound(err)) return;
        console.error("Failed to refresh processing paper status:", err);
      });
    }, 5000);

    return () => window.clearInterval(timer);
  }, [
    paper?.parse_status,
    paper?.overview_status,
    paper?.zh_translation_status,
    language,
    loading,
    paperId,
  ]);

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

  function getUserFacingErrorMessage(err: unknown, fallback: string) {
    if (err instanceof Error && err.message.trim()) {
      return err.message;
    }

    return fallback;
  }

  function isPaperNotFoundError(err: unknown) {
    if (!(err instanceof Error)) return false;

    const lower = err.message.toLowerCase();
    return (
      lower.includes("paper not found") ||
      lower.includes("論文已被刪除") ||
      lower.includes("論文不存在") ||
      lower.includes("paper has been deleted")
    );
  }

  function handlePaperNotFound(err: unknown) {
    if (!isPaperNotFoundError(err)) return false;
    if (notFoundRedirectingRef.current) return true;

    notFoundRedirectingRef.current = true;
    setShowDeletePaperModal(false);
    setShowExportModal(false);
    showToast("這篇論文已被刪除或不存在，將返回列表。", 1200);

    notFoundRedirectTimerRef.current = window.setTimeout(() => {
      notFoundRedirectTimerRef.current = null;
      onBack();
    }, 1200);

    return true;
  }

  async function loadHoverZhData() {
    try {
      const [paperZhData, overviewZhData] = await Promise.all([
        fetchPaperDetail(paperId, "zh"),
        fetchPaperOverview(paperId, "zh"),
      ]);

      setHoverPaperZh(paperZhData);
      setHoverOverviewZh(overviewZhData);
      setAudioPaperZh(paperZhData);
      setAudioOverviewZh(overviewZhData);
    } catch (err) {
      if (handlePaperNotFound(err)) return;
      console.error("Failed to load hover Chinese translation data:", err);
      setHoverPaperZh(null);
      setHoverOverviewZh(null);
    }
  }

  async function triggerBackgroundZhTranslation(currentPaper?: PaperDetail) {
    const targetPaper = currentPaper ?? paper;
    if (!targetPaper) return;

    if (normalizeTaskStatus(targetPaper.parse_status) !== "processed") {
      return;
    }

    if (normalizeTaskStatus(targetPaper.overview_status) !== "completed") {
      return;
    }

    if (targetPaper.zh_translation_status === "completed") {
      void loadHoverZhData();
      return;
    }

    if (
      targetPaper.zh_translation_status === "queued" ||
      targetPaper.zh_translation_status === "processing"
    ) {
      return;
    }

    if (targetPaper.zh_translation_status === "failed") {
      return;
    }

    try {
      const result = await translatePaperToZh(paperId);

      if (
        result.status === "translated" ||
        result.status === "already_exists"
      ) {
        setPaper((prev) =>
          prev ? { ...prev, zh_translation_status: "completed" } : prev,
        );
        showToast("中文內容已準備完成，可以切換查看。");
        void loadHoverZhData();
      } else if (result.status === "queued" || result.status === "processing") {
        setPaper((prev) =>
          prev ? { ...prev, zh_translation_status: result.status } : prev,
        );
      }
    } catch (err) {
      if (handlePaperNotFound(err)) return;
      console.error("Background Chinese translation failed:", err);
      setPaper((prev) =>
        prev ? { ...prev, zh_translation_status: "failed" } : prev,
      );
    }
  }

  async function loadPaper(
    lang: "en" | "zh",
    options: { fullPageLoading?: boolean } = {},
  ) {
    const useFullPageLoading = options.fullPageLoading ?? false;

    if (useFullPageLoading) {
      setLoading(true);
    }

    try {
      const paperData = await fetchPaperDetail(paperId, lang);

      let overviewData: PaperOverview | null = null;
      try {
        overviewData = await fetchPaperOverview(paperId, lang);
      } catch (err) {
        const overviewStatus = normalizeTaskStatus(paperData.overview_status);
        if (!["queued", "processing", "not_started", "failed"].includes(overviewStatus)) {
          throw err;
        }
        console.warn("Overview is unavailable because it is not ready:", err);
      }

      const highlightData = await fetchHighlights(paperId, lang);

      setPaper(paperData);
      setOverview(overviewData);
      setTextHighlights(highlightData.text_highlights);
      setPdfHighlights(highlightData.pdf_highlights);
      setLanguage(lang);

      if (lang === "en") {
        setAudioPaperEn(paperData);
        setAudioOverviewEn(overviewData);
      } else {
        setAudioPaperZh(paperData);
        setAudioOverviewZh(overviewData);
      }

      if (lang === "en") {
        if (paperData.zh_translation_status === "completed") {
          void loadHoverZhData();
        } else {
          setHoverPaperZh(null);
          setHoverOverviewZh(null);
        }

        if (paperData.zh_translation_status === "not_started") {
          void triggerBackgroundZhTranslation(paperData);
        }
      }
    } catch (err) {
      if (handlePaperNotFound(err)) return;
      console.error(err);
      showToast(getUserFacingErrorMessage(err, "載入論文失敗。"));
    } finally {
      if (useFullPageLoading) {
        setLoading(false);
      }
    }
  }

  async function refreshCurrentLanguageData() {
    const paperData = await fetchPaperDetail(paperId, language);

    let overviewData: PaperOverview | null = null;
    try {
      overviewData = await fetchPaperOverview(paperId, language);
    } catch (err) {
      const overviewStatus = normalizeTaskStatus(paperData.overview_status);
      if (!["queued", "processing", "not_started", "failed"].includes(overviewStatus)) {
        throw err;
      }
      console.warn("Overview is unavailable because it is not ready:", err);
    }

    const highlightData = await fetchHighlights(paperId, language);

    setPaper(paperData);
    setOverview(overviewData);
    setTextHighlights(highlightData.text_highlights);
    setPdfHighlights(highlightData.pdf_highlights);

    if (language === "en") {
      setAudioPaperEn(paperData);
      setAudioOverviewEn(overviewData);
    } else {
      setAudioPaperZh(paperData);
      setAudioOverviewZh(overviewData);
    }

    if (language === "en") {
      if (paperData.zh_translation_status === "completed") {
        void loadHoverZhData();
      } else if (paperData.zh_translation_status === "not_started") {
        void triggerBackgroundZhTranslation(paperData);
      }
    }
  }

  function clampRatio(value: number) {
    if (!Number.isFinite(value)) return 0;
    return Math.min(1, Math.max(0, value));
  }

  function getScrollRatio(container: HTMLElement) {
    const maxScrollTop = container.scrollHeight - container.clientHeight;
    if (maxScrollTop <= 0) return 0;
    return clampRatio(container.scrollTop / maxScrollTop);
  }

  function captureReadingAnchor() {
    const container = leftPanelRef.current;
    if (!container) return;

    if (container.scrollTop <= 24) {
      pendingRestoreRef.current = { mode: "top" };
      return;
    }

    const containerRect = container.getBoundingClientRect();
    const anchorViewportTop = containerRect.height * 0.45;
    const scrollRatio = getScrollRatio(container);

    const firstContentRow = container.querySelector<HTMLElement>(
      ".content-row[data-paragraph-id]",
    );

    if (firstContentRow) {
      const firstRowRect = firstContentRow.getBoundingClientRect();
      const firstRowRelativeTop = firstRowRect.top - containerRect.top;

      // If the current visual anchor is still above the first paragraph row,
      // the user is reading the overview area. Do not force the restore target
      // to the first paragraph, otherwise switching languages jumps from the
      // overview to the paragraph table.
      if (firstRowRelativeTop > anchorViewportTop) {
        const overviewPanel = container.querySelector<HTMLElement>(".overview-panel");
        if (overviewPanel) {
          const overviewRect = overviewPanel.getBoundingClientRect();
          const overviewRelativeTop = overviewRect.top - containerRect.top;
          const overviewOffsetRatio = clampRatio(
            (anchorViewportTop - overviewRelativeTop) /
              Math.max(1, overviewRect.height),
          );

          pendingRestoreRef.current = {
            mode: "overview",
            anchorViewportTop,
            overviewOffsetRatio,
            scrollRatio,
          };
          return;
        }

        pendingRestoreRef.current = {
          mode: "scroll",
          scrollTop: container.scrollTop,
          scrollRatio,
        };
        return;
      }
    }

    const rows = Array.from(
      container.querySelectorAll<HTMLElement>(
        ".content-row[data-paragraph-id]",
      ),
    );

    if (rows.length === 0) {
      pendingRestoreRef.current = {
        mode: "scroll",
        scrollTop: container.scrollTop,
        scrollRatio,
      };
      return;
    }

    let bestParagraphId: number | null = null;
    let bestRowOffsetRatio = 0;
    let bestDistance = Number.POSITIVE_INFINITY;

    for (const row of rows) {
      const rect = row.getBoundingClientRect();
      const rawId = row.getAttribute("data-paragraph-id");
      const paragraphId = rawId ? Number(rawId) : NaN;
      if (Number.isNaN(paragraphId)) continue;

      const relativeTop = rect.top - containerRect.top;
      const relativeBottom = rect.bottom - containerRect.top;
      const rowHeight = Math.max(1, rect.height);
      const rowCenter = relativeTop + rowHeight / 2;
      const distance =
        anchorViewportTop >= relativeTop && anchorViewportTop <= relativeBottom
          ? 0
          : Math.abs(rowCenter - anchorViewportTop);

      if (distance < bestDistance) {
        bestDistance = distance;
        bestParagraphId = paragraphId;
        bestRowOffsetRatio = clampRatio(
          (anchorViewportTop - relativeTop) / rowHeight,
        );
      }
    }

    if (bestParagraphId == null) {
      pendingRestoreRef.current = {
        mode: "scroll",
        scrollTop: container.scrollTop,
        scrollRatio,
      };
      return;
    }

    pendingRestoreRef.current = {
      mode: "paragraph",
      paragraphId: bestParagraphId,
      anchorViewportTop,
      rowOffsetRatio: bestRowOffsetRatio,
    };
  }

  function restoreScrollFallback(
    container: HTMLElement,
    fallback: { scrollTop: number; scrollRatio: number },
  ) {
    const maxScrollTop = container.scrollHeight - container.clientHeight;
    const targetByRatio = maxScrollTop > 0 ? fallback.scrollRatio * maxScrollTop : 0;
    const targetScrollTop = Number.isFinite(targetByRatio)
      ? targetByRatio
      : fallback.scrollTop;

    container.scrollTo({
      top: Math.max(0, targetScrollTop),
      behavior: "auto",
    });
  }

  function restoreReadingAnchorIfNeeded(attempt = 0) {
    const pending = pendingRestoreRef.current;
    const container = leftPanelRef.current;
    if (!pending || !container) return;

    if (pending.mode === "top") {
      container.scrollTo({ top: 0, behavior: "auto" });
    } else if (pending.mode === "overview") {
      const overviewPanel = container.querySelector<HTMLElement>(".overview-panel");
      if (overviewPanel) {
        const containerRect = container.getBoundingClientRect();
        const overviewRect = overviewPanel.getBoundingClientRect();
        const overviewAbsoluteTop =
          overviewRect.top - containerRect.top + container.scrollTop;
        const targetScrollTop =
          overviewAbsoluteTop +
          pending.overviewOffsetRatio * overviewRect.height -
          pending.anchorViewportTop;

        container.scrollTo({
          top: Math.max(0, targetScrollTop),
          behavior: "auto",
        });
      } else {
        restoreScrollFallback(container, {
          scrollTop: container.scrollTop,
          scrollRatio: pending.scrollRatio,
        });
      }
    } else if (pending.mode === "paragraph") {
      const target = container.querySelector(
        `.content-row[data-paragraph-id="${pending.paragraphId}"]`,
      ) as HTMLElement | null;

      if (target) {
        const containerRect = container.getBoundingClientRect();
        const targetRect = target.getBoundingClientRect();
        const absoluteTop =
          targetRect.top - containerRect.top + container.scrollTop;
        const targetScrollTop =
          absoluteTop +
          pending.rowOffsetRatio * targetRect.height -
          pending.anchorViewportTop;

        container.scrollTo({
          top: Math.max(0, targetScrollTop),
          behavior: "auto",
        });
      }
    } else {
      restoreScrollFallback(container, pending);
    }

    if (attempt < 2) {
      window.requestAnimationFrame(() => restoreReadingAnchorIfNeeded(attempt + 1));
      return;
    }

    pendingRestoreRef.current = null;
  }

  function scrollWithOffset(
    element: HTMLElement,
    behavior: ScrollBehavior = "smooth",
  ) {
    const container = leftPanelRef.current;
    if (!container) return;

    const containerRect = container.getBoundingClientRect();
    const elementRect = element.getBoundingClientRect();
    const relativeTop =
      elementRect.top - containerRect.top + container.scrollTop;

    container.scrollTo({
      top: Math.max(0, relativeTop - 24),
      behavior,
    });
  }

  function savePdfViewState() {
    if (!showPdf) return;

    const state = pdfViewerRef.current?.captureViewState();
    if (state) {
      pdfViewStateRef.current = state;
    }
  }

  function restorePdfViewStateIfNeeded() {
    const state = pdfViewStateRef.current;
    if (!state || !showPdf) return;

    window.setTimeout(() => {
      pdfViewerRef.current?.restoreViewState(state);
    }, 80);
  }

  function handleTogglePdf() {
    if (showPdf) {
      savePdfViewState();
    }
    setShowPdf((prev) => !prev);
  }

  async function handleSwitchLanguage(lang: "en" | "zh") {
    if (lang === language) return;

    captureReadingAnchor();
    savePdfViewState();

    if (lang === "en") {
      await loadPaper("en", { fullPageLoading: false });
      return;
    }

    if (!paper) return;

    if (paper.zh_translation_status === "completed") {
      try {
        setSwitchingLanguage(true);
        await loadPaper("zh", { fullPageLoading: false });
      } catch (err) {
        if (handlePaperNotFound(err)) return;
        console.error(err);
        showToast(getUserFacingErrorMessage(err, "切換中文失敗。"));
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
      showToast("中文翻譯失敗，請使用頁面上的 Retry Translation 重新嘗試。");
      pendingRestoreRef.current = null;
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
      if (handlePaperNotFound(err)) return;
      console.error(err);
      showToast(getUserFacingErrorMessage(err, "更新段落失敗。"));
      throw err;
    }
  }

  async function handleSaveBulletList(
    paragraphId: number,
    introText: string,
    items: string[],
  ) {
    try {
      await updateBulletList(paragraphId, introText, items);
      showToast("條列段落已更新，並重新生成摘要。");
      await refreshCurrentLanguageData();
    } catch (err) {
      if (handlePaperNotFound(err)) return;
      console.error(err);
      showToast(getUserFacingErrorMessage(err, "更新條列段落失敗。"));
      throw err;
    }
  }

  async function handleInsertParagraphAfter(paragraphId: number, text: string) {
    try {
      await insertParagraphAfter(paragraphId, text);
      showToast("新段落已新增。");
      await refreshCurrentLanguageData();
    } catch (err) {
      if (handlePaperNotFound(err)) return;
      console.error(err);
      showToast(getUserFacingErrorMessage(err, "新增段落失敗。"));
      throw err;
    }
  }

  async function handleDeleteParagraph(paragraphId: number) {
    try {
      await deleteParagraph(paragraphId);
      showToast("段落已刪除。");
      await refreshCurrentLanguageData();
    } catch (err) {
      if (handlePaperNotFound(err)) return;
      console.error(err);
      showToast(getUserFacingErrorMessage(err, "刪除段落失敗。"));
      throw err;
    }
  }

  async function handleRefreshStatus() {
    if (refreshingStatus) return;

    try {
      setRefreshingStatus(true);
      await refreshCurrentLanguageData();
      showToast("狀態已更新。");
    } catch (err) {
      if (handlePaperNotFound(err)) return;
      console.error(err);
      showToast("更新狀態失敗，請稍後再試。");
    } finally {
      setRefreshingStatus(false);
    }
  }

  async function handleRegenerateOverview() {
    if (regeneratingOverview || parseFailed || overviewProcessing) return;

    try {
      setRegeneratingOverview(true);
      const result = await regenerateOverview(paperId);

      if (result.status === "queued" || result.status === "processing") {
        setPaper((prev) =>
          prev ? { ...prev, overview_status: result.status } : prev,
        );
        showToast(
          result.status === "queued"
            ? "全文摘要已排入背景重新生成佇列。"
            : "全文摘要仍在背景重新生成中，請稍後再試。",
        );
      } else {
        showToast("全文摘要與 highlights 已重新生成。");
      }

      await refreshCurrentLanguageData();
    } catch (err) {
      if (handlePaperNotFound(err)) return;
      console.error(err);
      showToast(getUserFacingErrorMessage(err, "重新生成全文摘要失敗。請稍後再試。"));
      await refreshCurrentLanguageData().catch((refreshErr) => {
        if (!handlePaperNotFound(refreshErr)) {
          console.error("Failed to refresh after regenerate error:", refreshErr);
        }
      });
    } finally {
      setRegeneratingOverview(false);
    }
  }

  async function handleRetryTranslation() {
    if (retryingTranslation || switchingLanguage || parseFailed || overviewProcessing || translationProcessing) return;

    try {
      setRetryingTranslation(true);
      const result = await translatePaperToZh(paperId);
      if (
        result.status === "translated" ||
        result.status === "already_exists"
      ) {
        showToast("中文內容已重新生成。");
        await refreshCurrentLanguageData();
        if (language === "zh") {
          await loadPaper("zh", { fullPageLoading: false });
        } else {
          void loadHoverZhData();
        }
      } else if (result.status === "queued" || result.status === "processing") {
        showToast(result.status === "queued" ? "中文翻譯已排入背景處理佇列。" : "中文翻譯仍在處理中，請稍後再試。");
        await refreshCurrentLanguageData();
      }
    } catch (err) {
      if (handlePaperNotFound(err)) return;
      console.error(err);
      showToast(getUserFacingErrorMessage(err, "中文翻譯重新嘗試失敗。請稍後再試。"));
      await refreshCurrentLanguageData().catch((refreshErr) => {
        if (!handlePaperNotFound(refreshErr)) {
          console.error("Failed to refresh after translation retry error:", refreshErr);
        }
      });
    } finally {
      setRetryingTranslation(false);
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
      if (handlePaperNotFound(err)) return;
      console.error(err);
      showToast(getUserFacingErrorMessage(err, "新增 PDF 重點失敗。"));
    }
  }

  async function handleDeletePdfHighlight(highlightId: number) {
    try {
      await deletePdfHighlight(highlightId);
      handlePdfHighlightDeleted(highlightId);
      showToast("PDF 重點已刪除。");
    } catch (err) {
      if (handlePaperNotFound(err)) return;
      console.error(err);
      showToast(getUserFacingErrorMessage(err, "刪除 PDF 重點失敗。"));
    }
  }

  async function handleDeletePaper() {
    try {
      setDeletingPaper(true);
      await deletePaper(paperId);
      setShowDeletePaperModal(false);
      showToast("論文已刪除。");
      onBack();
    } catch (err) {
      if (handlePaperNotFound(err)) return;
      console.error(err);
      setShowDeletePaperModal(false);
      showToast(getUserFacingErrorMessage(err, "刪除論文失敗。這篇論文可能正在處理中，或已不存在。"));
    } finally {
      setDeletingPaper(false);
    }
  }

  async function handleSavePaperTitle() {
    const nextTitle = paperTitleDraft.trim();

    if (!nextTitle) {
      showToast("論文名稱不能為空。");
      return;
    }

    try {
      setSavingPaperTitle(true);

      const result = await updatePaperTitle(paperId, nextTitle);

      setPaper((prev) =>
        prev
          ? {
              ...prev,
              title: result.title,
            }
          : prev,
      );

      setEditingPaperTitle(false);
      showToast("論文名稱已更新。");
    } catch (err) {
      if (handlePaperNotFound(err)) return;
      console.error(err);
      showToast(getUserFacingErrorMessage(err, "更新論文名稱失敗。"));
    } finally {
      setSavingPaperTitle(false);
    }
  }

  function startEditingPaperTitle() {
    if (!paper) return;

    setPaperTitleDraft(paper.title || paper.original_filename);
    setEditingPaperTitle(true);
  }

  function cancelEditingPaperTitle() {
    if (!paper) return;

    setPaperTitleDraft(paper.title || paper.original_filename);
    setEditingPaperTitle(false);
  }

  function handlePaperTitleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      void handleSavePaperTitle();
      return;
    }

    if (e.key === "Escape") {
      e.preventDefault();
      cancelEditingPaperTitle();
    }
  }

  function handleSelectElement(element: Element) {
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

  const hoverZhElementById = useMemo(() => {
    const map = new Map<number, Element>();

    for (const el of hoverPaperZh?.elements || []) {
      map.set(el.id, el);
    }

    return map;
  }, [hoverPaperZh]);

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

  useEffect(() => {
    if (loading || !paper || !showPdf) return;
    restorePdfViewStateIfNeeded();
  }, [loading, paper?.paper_id, paper?.pdf_url, showPdf, language]);

  useEffect(() => {
    if (!paper) return;
    setPaperTitleDraft(paper.title || paper.original_filename);
  }, [paper]);

  function handleJumpToSection(sectionTitle: string) {
    if (!overview) return;

    const clickedIndex = overview.section_summaries.findIndex(
      (section) => section.section_title === sectionTitle,
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
      (entry) => entry.normalizedHeadingText === fallbackKey,
    );

    if (fallbackEntry?.ref.current) {
      scrollWithOffset(fallbackEntry.ref.current, "smooth");
    }
  }

  function zoomOutPdf() {
    pdfViewerRef.current?.captureZoomAnchor();
    setPdfZoom((prev) => Math.max(0.75, Number((prev - 0.1).toFixed(2))));
  }

  function zoomInPdf() {
    pdfViewerRef.current?.captureZoomAnchor();
    setPdfZoom((prev) => Math.min(2.5, Number((prev + 0.1).toFixed(2))));
  }

  function resetPdfZoom() {
    pdfViewerRef.current?.captureZoomAnchor();
    setPdfZoom(1);
  }

  if (loading) {
    return <div className="reader-page">Loading...</div>;
  }

  if (!paper) {
    return <div className="reader-page">Paper not found</div>;
  }

  const parseStatus = normalizeTaskStatus(paper.parse_status);
  const overviewStatus = normalizeTaskStatus(paper.overview_status);
  const translationStatus = normalizeTaskStatus(paper.zh_translation_status);
  const parseFailed = parseStatus === "failed";
  const overviewFailed = overviewStatus === "failed";
  const parseProcessing = parseStatus === "queued" || parseStatus === "processing";
  const overviewProcessing = overviewStatus === "queued" || overviewStatus === "processing";
  const translationFailed = translationStatus === "failed";
  const translationProcessing = translationStatus === "queued" || translationStatus === "processing";
  const taskHasIssue = parseFailed || overviewFailed || translationFailed;
  const taskIsProcessing = parseProcessing || overviewProcessing || translationProcessing;
  const contentEditingDisabled = taskIsProcessing || regeneratingOverview || retryingTranslation || switchingLanguage;
  const readerErrorType = parseFailed
    ? "parse"
    : overviewFailed
    ? "overview"
    : translationFailed
    ? "translation"
    : taskIsProcessing
    ? "processing"
    : undefined;
  const readerErrorMessage = getFriendlyReaderError(
    paper.last_error_message ||
      paper.parse_error ||
      paper.overview_error ||
      paper.zh_translation_error ||
      null,
    readerErrorType,
  );

  let currentSectionHeadingIndex = 0;

  return (
    <div className="reader-page">
      <div className="reader-sticky-top">
        <div className="reader-header compact-reader-header">
          <div className="reader-header-left">
            <button
              className="back-button compact-back-button"
              onClick={onBack}
            >
              ← Back
            </button>

            <div className="reader-title-area">
              {editingPaperTitle ? (
                <div className="paper-title-edit-row compact-title-edit-row">
                  <input
                    type="text"
                    value={paperTitleDraft}
                    onChange={(e) => setPaperTitleDraft(e.target.value)}
                    onKeyDown={handlePaperTitleKeyDown}
                    className="paper-title-input compact-title-input"
                    maxLength={255}
                    autoFocus
                  />
                  <button
                    className="paper-title-action-button primary compact-title-action"
                    onClick={() => void handleSavePaperTitle()}
                    disabled={savingPaperTitle}
                  >
                    {savingPaperTitle ? "Saving..." : "Save"}
                  </button>
                  <button
                    className="paper-title-action-button compact-title-action"
                    onClick={cancelEditingPaperTitle}
                    disabled={savingPaperTitle}
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <>
                  <h1
                    className="editable-paper-title"
                    onDoubleClick={startEditingPaperTitle}
                    title="Double-click to rename"
                  >
                    {paper.title ?? paper.original_filename}
                  </h1>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="reader-toolbar">
          <div className="reader-toolbar-main-row">
            <div className="toolbar-section">
              <div className="toolbar-section-label">Language</div>
              <div className="toolbar-segmented">
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
            </div>

            <div className="toolbar-section">
              <div className="toolbar-section-label">View</div>
              <button
                className={showPdf ? "active" : ""}
                onClick={handleTogglePdf}
              >
                {showPdf ? "PDF On" : "PDF Off"}
              </button>
            </div>

            <div className="toolbar-section toolbar-audio-section">
              <div className="toolbar-section-label">Audio</div>
              {overview ? (
                <OverviewAudioPlayer
                  currentLanguage={language}
                  activeElementId={activeElementId}
                  englishOverview={language === "en" ? overview : audioOverviewEn}
                  englishElements={language === "en" ? paper.elements : audioPaperEn?.elements ?? []}
                  chineseOverview={language === "zh" ? overview : audioOverviewZh ?? hoverOverviewZh}
                  chineseElements={language === "zh" ? paper.elements : audioPaperZh?.elements ?? hoverPaperZh?.elements ?? []}
                />
              ) : (
                <button disabled>Audio</button>
              )}
            </div>
          </div>

          <div className="reader-toolbar-secondary-row">
            <div className="toolbar-section">
              <div className="toolbar-section-label">Overview</div>
              <button
                onClick={handleRegenerateOverview}
                disabled={switchingLanguage || regeneratingOverview || parseProcessing || overviewProcessing}
              >
                {regeneratingOverview ? "Regenerating..." : "Regenerate"}
              </button>
            </div>

            <div className="toolbar-section toolbar-highlight-section">
              <div className="toolbar-section-label">Highlight Color</div>
              <HighlightColorToolbar
                color={highlightColor}
                onChange={setHighlightColor}
              />
            </div>

            <div className="toolbar-section">
              <div className="toolbar-section-label">Highlight</div>
              <div className="toolbar-button-row">
                <button
                  className={`toolbar-mode-button ${textHighlightMode ? "active text-active" : ""}`}
                  onClick={() => setTextHighlightMode((prev) => !prev)}
                  title={textHighlightMode ? "Text highlight mode is on" : "Text highlight mode is off"}
                >
                  Text
                </button>

                <button
                  className={`toolbar-mode-button ${pdfHighlightMode ? "active pdf-active" : ""}`}
                  onClick={() => setPdfHighlightMode((prev) => !prev)}
                  title={pdfHighlightMode ? "PDF highlight mode is on" : "PDF highlight mode is off"}
                >
                  PDF
                </button>
              </div>
            </div>

            <div className="toolbar-section toolbar-file-section">
              <div className="toolbar-section-label">Paper</div>
              <div className="toolbar-button-row">
                <button onClick={() => setShowExportModal(true)}>
                  Download
                </button>
                <button
                  className="toolbar-danger-button"
                  onClick={() => setShowDeletePaperModal(true)}
                  disabled={deletingPaper}
                >
                  Delete
                </button>
              </div>
            </div>

            <div className="toolbar-section">
              <div className="toolbar-section-label">PDF Zoom</div>
              <div className="toolbar-button-row toolbar-zoom-group">
                <button
                  onClick={zoomOutPdf}
                  disabled={!showPdf}
                  aria-label="Zoom out PDF"
                >
                  −
                </button>
                <button onClick={resetPdfZoom} disabled={!showPdf}>
                  {Math.round(pdfZoom * 100)}%
                </button>
                <button
                  onClick={zoomInPdf}
                  disabled={!showPdf}
                  aria-label="Zoom in PDF"
                >
                  ＋
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {toastMessage && <div className="toast-notice">{toastMessage}</div>}

      {(taskHasIssue || taskIsProcessing) && (
        <div
          className={`reader-status-alert ${taskHasIssue ? "failed" : "processing"}`}
        >
          <div>
            <div className="reader-status-alert-title">
              {parseFailed
                ? "PDF processing failed"
                : parseProcessing
                ? "PDF is queued for processing"
                : taskHasIssue
                ? "Some generated content needs attention"
                : "Generated content is still processing"}
            </div>
            <div className="reader-status-alert-message">
              {readerErrorMessage}
            </div>
          </div>

          <div className="reader-status-alert-actions">
            {parseFailed && (
              <>
                <button type="button" onClick={onBack}>
                  Back to Home
                </button>
                <button
                  type="button"
                  className="danger"
                  onClick={() => setShowDeletePaperModal(true)}
                  disabled={deletingPaper}
                >
                  Delete Paper
                </button>
              </>
            )}

            {!parseFailed && overviewFailed && (
              <button
                type="button"
                onClick={() => void handleRegenerateOverview()}
                disabled={regeneratingOverview}
              >
                {regeneratingOverview ? "Retrying..." : "Retry Overview"}
              </button>
            )}

            {!parseFailed && translationFailed && (
              <button
                type="button"
                onClick={() => void handleRetryTranslation()}
                disabled={retryingTranslation || switchingLanguage || overviewProcessing || translationProcessing}
              >
                {retryingTranslation ? "Retrying..." : "Retry Translation"}
              </button>
            )}

            <button
              type="button"
              onClick={() => void handleRefreshStatus()}
              disabled={refreshingStatus}
            >
              {refreshingStatus ? "Refreshing..." : "Refresh Status"}
            </button>
          </div>
        </div>
      )}

      <div className={`reader-layout ${showPdf ? "with-pdf" : "no-pdf"}`}>
        <div className="reader-left" ref={leftPanelRef}>
          {overview && (
            <OverviewPanel
              paperId={paperId}
              overview={overview}
              hoverOverview={language === "en" ? hoverOverviewZh : null}
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
                  hoverElement={
                    language === "en"
                      ? (hoverZhElementById.get(element.id) ?? null)
                      : null
                  }
                  headingRef={headingRef}
                  currentLanguage={language}
                  textHighlightMode={textHighlightMode}
                  editDisabled={contentEditingDisabled}
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

        <div
          className="reader-right"
          style={{ display: showPdf ? undefined : "none" }}
          aria-hidden={!showPdf}
        >
          <PdfViewer
            ref={pdfViewerRef}
            paperId={paperId}
            pdfUrl={`${API_BASE}${paper.pdf_url}`}
            highlightLocations={highlightLocations}
            pdfHighlights={pdfHighlights}
            pdfHighlightMode={pdfHighlightMode}
            highlightColor={highlightColor}
            pdfZoom={pdfZoom}
            flashToken={pdfFlashToken}
            onCreatePdfHighlight={handleCreatePdfHighlight}
            onDeletePdfHighlight={handleDeletePdfHighlight}
          />
        </div>
      </div>

      {showExportModal && (
        <ExportModal
          paperId={paperId}
          onClose={() => setShowExportModal(false)}
        />
      )}

      {showDeletePaperModal && (
        <div
          className="modal-backdrop"
          onClick={() => {
            if (!deletingPaper) setShowDeletePaperModal(false);
          }}
        >
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()}>
            <h2>是否確定要刪除此論文生成內容?</h2>
            <p className="confirm-warning">這個操作無法復原，請確保已保存所需內容。</p>

            <div className="confirm-modal-actions">
              <button
                onClick={() => setShowDeletePaperModal(false)}
                disabled={deletingPaper}
              >
                Cancel
              </button>
              <button
                className="danger-button"
                onClick={() => void handleDeletePaper()}
                disabled={deletingPaper}
              >
                {deletingPaper ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
