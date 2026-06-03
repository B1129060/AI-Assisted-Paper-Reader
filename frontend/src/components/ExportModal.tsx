// Modal for choosing export contents and downloading the generated PDF or ZIP.

import { useState } from "react";
import { exportPaper } from "../api/papers";

// Component props for this file.
type Props = {
  paperId: number;
  onClose: () => void;
};

// Collect export options and trigger a file download from the export API.
export default function ExportModal({ paperId, onClose }: Props) {
  const [includePdf, setIncludePdf] = useState(true);
  const [includeOverview, setIncludeOverview] = useState(true);
  const [includeParagraphs, setIncludeParagraphs] = useState(true);
  const [languageMode, setLanguageMode] = useState<"en" | "zh" | "both">("both");
  const [includePdfHighlights, setIncludePdfHighlights] = useState(true);
  const [includeTextHighlights, setIncludeTextHighlights] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleExport() {
    if (!includePdf && !includeOverview && !includeParagraphs) {
      setErrorMessage("請至少選擇一種下載內容。");
      return;
    }

    try {
      setErrorMessage(null);
      setSubmitting(true);

      const { blob, filename } = await exportPaper(paperId, {
        include_pdf: includePdf,
        include_overview: includeOverview,
        include_paragraphs: includeParagraphs,
        language_mode: languageMode,
        include_pdf_highlights: includePdfHighlights,
        include_text_highlights: includeTextHighlights,
      });

      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);

      onClose();
    } catch (err) {
      console.error(err);
      setErrorMessage("下載失敗，請稍後再試。");
    } finally {
      setSubmitting(false);
    }
  }

  function clearError() {
    if (errorMessage) setErrorMessage(null);
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="export-modal" onClick={(e) => e.stopPropagation()}>
        <div className="export-modal-header">
          <h2>下載內容</h2>
          <button
            type="button"
            className="modal-icon-button"
            onClick={onClose}
            disabled={submitting}
            aria-label="Close download dialog"
          >
            ×
          </button>
        </div>

        <div className="export-section">
          <div className="export-section-title">PDF</div>

          <label className="export-option">
            <input
              type="checkbox"
              checked={includePdf}
              onChange={(e) => {
                clearError();
                setIncludePdf(e.target.checked);
              }}
            />
            <span>PDF 原文檔</span>
          </label>

          <label className="export-option export-suboption">
            <input
              type="checkbox"
              checked={includePdfHighlights}
              onChange={(e) => {
                clearError();
                setIncludePdfHighlights(e.target.checked);
              }}
              disabled={!includePdf}
            />
            <span>包含重點</span>
          </label>
        </div>

        <div className="export-section">
          <div className="export-section-title">Text</div>

          <label className="export-option">
            <input
              type="checkbox"
              checked={includeOverview}
              onChange={(e) => {
                clearError();
                setIncludeOverview(e.target.checked);
              }}
            />
            <span>全文摘要</span>
          </label>

          <label className="export-option">
            <input
              type="checkbox"
              checked={includeParagraphs}
              onChange={(e) => {
                clearError();
                setIncludeParagraphs(e.target.checked);
              }}
            />
            <span>分段落摘要</span>
          </label>

          <label className="export-option export-suboption">
            <input
              type="checkbox"
              checked={includeTextHighlights}
              onChange={(e) => {
                clearError();
                setIncludeTextHighlights(e.target.checked);
              }}
              disabled={!includeOverview && !includeParagraphs}
            />
            <span>包含重點</span>
          </label>
        </div>

        <div className="export-section export-language-block">
          <div className="export-section-title">語言模式</div>

          <div className="export-radio-group">
            <label className="export-option export-radio-option">
              <input
                type="radio"
                name="language_mode"
                checked={languageMode === "both"}
                onChange={() => {
                  clearError();
                  setLanguageMode("both");
                }}
              />
              <span>中英文對照</span>
            </label>

            <label className="export-option export-radio-option">
              <input
                type="radio"
                name="language_mode"
                checked={languageMode === "en"}
                onChange={() => {
                  clearError();
                  setLanguageMode("en");
                }}
              />
              <span>英文</span>
            </label>

            <label className="export-option export-radio-option">
              <input
                type="radio"
                name="language_mode"
                checked={languageMode === "zh"}
                onChange={() => {
                  clearError();
                  setLanguageMode("zh");
                }}
              />
              <span>中文</span>
            </label>
          </div>
        </div>

        {errorMessage && (
          <div className="modal-inline-alert" role="alert">
            {errorMessage}
          </div>
        )}

        <div className="export-modal-actions">
          <button className="modal-secondary-button" onClick={onClose} disabled={submitting}>
            Cancel
          </button>
          <button className="modal-primary-button" onClick={handleExport} disabled={submitting}>
            {submitting ? "Exporting..." : "Download"}
          </button>
        </div>
      </div>
    </div>
  );
}