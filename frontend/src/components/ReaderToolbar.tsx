type ViewMode = "text" | "pdf";

type Props = {
  viewMode: ViewMode;
  onChange: (mode: ViewMode) => void;
};

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