// Home page for listing papers, uploading PDFs, renaming, deleting, exporting, and polling processing status.

import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import type { PaperListItem } from "../types/paper";
import {
  deletePaper,
  fetchPapers,
  updatePaperTitle,
  uploadPaper,
} from "../api/papers";
import ExportModal from "../components/ExportModal";

// Component props for this file.
type Props = {
  onOpenReader: (paperId: number) => void;
};

// Data structure for overall paper status.
type OverallPaperStatus = "ready" | "processing" | "failed";

// Data structure for load papers options.
type LoadPapersOptions = {
  silent?: boolean;
};

// Get paper display title.
function getPaperDisplayTitle(paper: PaperListItem) {
  return paper.title || paper.original_filename || `Paper ${paper.paper_id}`;
}

// Normalize status.
function normalizeStatus(status: string | null | undefined) {
  return (status || "").toLowerCase();
}

// Get overall paper status.
function getOverallPaperStatus(paper: PaperListItem): OverallPaperStatus {
  const parseStatus = normalizeStatus(paper.parse_status);
  const overviewStatus = normalizeStatus(paper.overview_status);
  const zhStatus = normalizeStatus(paper.zh_translation_status);
  if (
    parseStatus === "failed" ||
    overviewStatus === "failed" ||
    zhStatus === "failed"
  ) {
    return "failed";
  }

  if (
    parseStatus === "queued" ||
    parseStatus === "processing" ||
    overviewStatus === "queued" ||
    overviewStatus === "processing" ||
    zhStatus === "queued" ||
    zhStatus === "processing"
  ) {
    return "processing";
  }

  return "ready";
}

// Get overall status label.
function getOverallStatusLabel(status: OverallPaperStatus) {
  if (status === "failed") return "Failed";
  if (status === "processing") return "Processing";
  return "Ready";
}

// Get overall status message.
function getOverallStatusMessage(status: OverallPaperStatus) {
  if (status === "failed") {
    return "部分生成內容需要處理，請開啟論文查看可用的恢復方式。";
  }

  if (status === "processing") {
    return "";
  }

  return null;
}

// Get friendly paper error.
function getFriendlyPaperError(message?: string | null) {
  if (!message) return null;

  const lower = message.toLowerCase();

  if (lower.includes("parse") || lower.includes("processing failed")) {
    return "PDF 解析失敗，請刪除後重新上傳，或改用另一份 PDF。";
  }

  if (lower.includes("timed out") || lower.includes("timeout")) {
    return "系統處理時間過長，已停止本次任務，請開啟論文後重新嘗試。";
  }

  if (lower.includes("translation") || lower.includes("chinese") || lower.includes("中文")) {
    return "中文翻譯失敗，請開啟論文後重新翻譯。";
  }

  if (lower.includes("overview") || lower.includes("summary")) {
    return "全文摘要生成失敗，請開啟論文後重新生成。";
  }

  if (lower.includes("pdf file not found") || lower.includes("original pdf file not found")) {
    return "找不到原始 PDF 檔案，請重新上傳。";
  }

  return "系統處理時發生錯誤，請開啟論文查看或稍後再試。";
}

// Get primary error message.
function getPrimaryErrorMessage(paper: PaperListItem) {
  const parseStatus = normalizeStatus(paper.parse_status);
  const overviewStatus = normalizeStatus(paper.overview_status);
  const zhStatus = normalizeStatus(paper.zh_translation_status);

  if (parseStatus === "failed") {
    return getFriendlyPaperError(paper.parse_error || paper.last_error_message || null);
  }

  if (zhStatus === "failed") {
    return getFriendlyPaperError(paper.zh_translation_error || paper.last_error_message || null);
  }

  if (overviewStatus === "failed") {
    return getFriendlyPaperError(paper.overview_error || paper.last_error_message || null);
  }

  return getFriendlyPaperError(paper.last_error_message || null);
}

// Has processing paper.
function hasProcessingPaper(papers: PaperListItem[]) {
  return papers.some((paper) => getOverallPaperStatus(paper) === "processing");
}

// Paper library page with upload, list refresh, rename, export, and delete controls.
export default function HomePage({ onOpenReader }: Props) {
  const [papers, setPapers] = useState<PaperListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [listLoading, setListLoading] = useState(false);

  const [editingPaperId, setEditingPaperId] = useState<number | null>(null);
  const [titleDraft, setTitleDraft] = useState("");
  const [savingTitleId, setSavingTitleId] = useState<number | null>(null);

  const [exportPaperId, setExportPaperId] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<PaperListItem | null>(null);
  const [deletingPaperId, setDeletingPaperId] = useState<number | null>(null);

  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const toastTimerRef = useRef<number | null>(null);

  const shouldAutoRefresh = useMemo(() => hasProcessingPaper(papers), [papers]);

  useEffect(() => {
    void loadPapers();

    return () => {
      if (toastTimerRef.current) {
        window.clearTimeout(toastTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!shouldAutoRefresh || loading) return;

    const timer = window.setInterval(() => {
      void loadPapers({ silent: true });
    }, 5000);

    return () => window.clearInterval(timer);
  }, [shouldAutoRefresh, loading]);

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

  async function loadPapers(options: LoadPapersOptions = {}) {
    try {
      if (!options.silent) {
        setListLoading(true);
      }

      const data = await fetchPapers();
      setPapers(data);
    } catch (err) {
      console.error(err);
      if (!options.silent) {
        showToast("讀取論文列表失敗。");
      }
    } finally {
      if (!options.silent) {
        setListLoading(false);
      }
    }
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoading(true);
    try {
      const result = await uploadPaper(file);
      await loadPapers();
      showToast("PDF 已上傳，已排入背景處理佇列。");
      onOpenReader(result.paper_id);
    } catch (err) {
      console.error(err);
      showToast(err instanceof Error ? err.message : "上傳失敗，請確認檔案格式或稍後再試。");
    } finally {
      setLoading(false);
      e.target.value = "";
    }
  }

  function startRename(paper: PaperListItem) {
    setEditingPaperId(paper.paper_id);
    setTitleDraft(getPaperDisplayTitle(paper));
  }

  function cancelRename() {
    setEditingPaperId(null);
    setTitleDraft("");
  }

  async function saveRename(paper: PaperListItem) {
    const nextTitle = titleDraft.trim();

    if (!nextTitle) {
      showToast("論文名稱不能為空。");
      return;
    }

    try {
      setSavingTitleId(paper.paper_id);
      const result = await updatePaperTitle(paper.paper_id, nextTitle);

      setPapers((prev) =>
        prev.map((item) =>
          item.paper_id === paper.paper_id
            ? {
                ...item,
                title: result.title,
                original_filename: result.original_filename,
              }
            : item,
        ),
      );

      setEditingPaperId(null);
      setTitleDraft("");
      showToast("論文名稱已更新。");
    } catch (err) {
      console.error(err);
      showToast("更新論文名稱失敗。");
    } finally {
      setSavingTitleId(null);
    }
  }

  function handleRenameKeyDown(e: KeyboardEvent<HTMLInputElement>, paper: PaperListItem) {
    if (e.key === "Enter") {
      e.preventDefault();
      void saveRename(paper);
      return;
    }

    if (e.key === "Escape") {
      e.preventDefault();
      cancelRename();
    }
  }

  async function confirmDeletePaper() {
    if (!deleteTarget) return;

    try {
      setDeletingPaperId(deleteTarget.paper_id);
      await deletePaper(deleteTarget.paper_id);
      setPapers((prev) =>
        prev.filter((paper) => paper.paper_id !== deleteTarget.paper_id),
      );
      showToast("論文已刪除。");
      setDeleteTarget(null);
    } catch (err) {
      console.error(err);
      showToast("刪除論文失敗。");
    } finally {
      setDeletingPaperId(null);
    }
  }

  const paperCountLabel = papers.length === 1 ? "1 paper" : `${papers.length} papers`;
  const listStatusLabel = listLoading
    ? "Loading papers..."
    : shouldAutoRefresh
      ? `${paperCountLabel} · Auto-refreshing`
      : paperCountLabel;

  return (
    <div className="home-page home-page-refined">
      <div className="home-shell home-shell-refined">
        <header className="home-hero-panel">
          <div>
            <div className="home-eyebrow">AI-Assisted Paper Reader</div>
            <h1 className="home-title">Paper Reader</h1>
            <p className="home-subtitle">
              Upload a PDF, open analyzed papers, and manage generated reading content.
            </p>
          </div>

          <label className={`home-upload-button ${loading ? "disabled" : ""}`}>
            <input
              type="file"
              accept="application/pdf"
              onChange={handleFileChange}
              disabled={loading}
            />
            {loading ? "Processing..." : "Upload PDF"}
          </label>
        </header>

        <section className="home-library-panel">
          <div className="home-section-header">
            <div>
              <h2>Uploaded Papers</h2>
              <p>{listStatusLabel}</p>
            </div>
            <button
              type="button"
              className="home-action-button"
              onClick={() => void loadPapers()}
              disabled={listLoading || loading}
            >
              Refresh
            </button>
          </div>

          {papers.length === 0 ? (
            <div className="home-empty-state">
              <div className="home-empty-title">No papers uploaded yet.</div>
              <p>Upload a PDF to generate summaries, translations, highlights, and exportable reading notes.</p>
            </div>
          ) : (
            <div className="paper-card-grid">
              {papers.map((paper) => {
                const isEditing = editingPaperId === paper.paper_id;
                const isSavingTitle = savingTitleId === paper.paper_id;
                const displayTitle = getPaperDisplayTitle(paper);
                const overallStatus = getOverallPaperStatus(paper);
                const statusMessage = getOverallStatusMessage(overallStatus);
                const primaryErrorMessage =
                  overallStatus === "failed" ? getPrimaryErrorMessage(paper) : null;

                return (
                  <article key={paper.paper_id} className="paper-card">
                    <div className="paper-card-main">
                      <div className="paper-card-title-row">
                        {isEditing ? (
                          <div className="home-title-edit-row">
                            <input
                              className="home-title-input"
                              value={titleDraft}
                              onChange={(e) => setTitleDraft(e.target.value)}
                              onKeyDown={(e) => handleRenameKeyDown(e, paper)}
                              maxLength={255}
                              autoFocus
                            />
                            <button
                              type="button"
                              className="home-action-button primary"
                              onClick={() => void saveRename(paper)}
                              disabled={isSavingTitle}
                            >
                              {isSavingTitle ? "Saving..." : "Save"}
                            </button>
                            <button
                              type="button"
                              className="home-action-button"
                              onClick={cancelRename}
                              disabled={isSavingTitle}
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <div className="paper-card-title-with-status">
                            <button
                              type="button"
                              className="paper-card-title-button"
                              onClick={() => onOpenReader(paper.paper_id)}
                              onDoubleClick={() => startRename(paper)}
                              title="Click to open. Double-click to rename."
                            >
                              {displayTitle}
                            </button>
                            <span className={`paper-overall-status-badge ${overallStatus}`}>
                              {getOverallStatusLabel(overallStatus)}
                            </span>
                          </div>
                        )}
                      </div>

                      {!isEditing && statusMessage && (
                        <div className={`paper-status-hint ${overallStatus}`}>
                          {statusMessage}
                        </div>
                      )}

                      {!isEditing && primaryErrorMessage && (
                        <div className="paper-card-error compact" title={primaryErrorMessage}>
                          {primaryErrorMessage}
                        </div>
                      )}
                    </div>

                    {!isEditing && (
                      <div className="paper-card-actions">
                        <button
                          type="button"
                          className="home-action-button"
                          onClick={() => startRename(paper)}
                        >
                          Rename
                        </button>
                        <button
                          type="button"
                          className="home-action-button"
                          onClick={() => setExportPaperId(paper.paper_id)}
                        >
                          Download
                        </button>
                        <button
                          type="button"
                          className="home-action-button danger"
                          onClick={() => setDeleteTarget(paper)}
                          disabled={deletingPaperId === paper.paper_id}
                        >
                          Delete
                        </button>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>

      {toastMessage && <div className="toast-notice">{toastMessage}</div>}

      {exportPaperId !== null && (
        <ExportModal
          paperId={exportPaperId}
          onClose={() => setExportPaperId(null)}
        />
      )}

      {deleteTarget && (
        <div
          className="modal-backdrop"
          onClick={() => {
            if (deletingPaperId === null) setDeleteTarget(null);
          }}
        >
          <div className="confirm-modal" onClick={(e) => e.stopPropagation()}>
            <h2>是否確定要刪除此論文生成內容?</h2>
            <p className="confirm-warning">這個操作無法復原。</p>
            <p>請確保已保存所需內容。</p>
            <p className="confirm-paper-name">{getPaperDisplayTitle(deleteTarget)}</p>

            <div className="confirm-modal-actions">
              <button
                type="button"
                className="modal-secondary-button"
                onClick={() => setDeleteTarget(null)}
                disabled={deletingPaperId !== null}
              >
                Cancel
              </button>
              <button
                type="button"
                className="danger-button"
                onClick={() => void confirmDeletePaper()}
                disabled={deletingPaperId !== null}
              >
                {deletingPaperId !== null ? "Deleting..." : "Confirm Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
