// Reader toolbar component for switching extracted text and PDF views.

// Data structure for view mode.
type ViewMode = "text" | "pdf";

// Component props for this file.
type Props = {
  viewMode: ViewMode;
  onChange: (mode: ViewMode) => void;
};

// Render extracted-text/PDF-view mode buttons.
export default function ReaderToolbar({ viewMode, onChange }: Props) {
  return (
    <div className="reader-toolbar">
      <button
        className={viewMode === "text" ? "active" : ""}
        onClick={() => onChange("text")}
      >
        Extracted Text
      </button>
      <button
        className={viewMode === "pdf" ? "active" : ""}
        onClick={() => onChange("pdf")}
      >
        PDF Viewer
      </button>
    </div>
  );
}