import { useEffect, useState } from "react";
import type { PaperListItem } from "../types/paper";
import { fetchPapers, uploadPaper } from "../api/papers";

type Props = {
  onOpenReader: (paperId: number) => void;
};

export default function HomePage({ onOpenReader }: Props) {
  const [papers, setPapers] = useState<PaperListItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadPapers();
  }, []);

  async function loadPapers() {
    try {
      const data = await fetchPapers();
      setPapers(data);
    } catch (err) {
      console.error(err);
      alert("Failed to fetch papers");
    }
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoading(true);
    try {
      const result = await uploadPaper(file);
      await loadPapers();
      onOpenReader(result.paper_id);
    } catch (err) {
      console.error(err);
      alert("Upload failed");
    } finally {
      setLoading(false);
      e.target.value = "";
    }
  }

  return (
    <div className="home-page">
      <div className="home-shell">
        <h1 className="home-title">Paper Reader</h1>
        <p className="home-subtitle">Upload a PDF or open an analyzed paper.</p>

        <div className="upload-panel">
          <label className="upload-label">
            <span>Upload PDF</span>
            <input type="file" accept="application/pdf" onChange={handleFileChange} />
          </label>
          {loading && <p className="loading-text">Processing paper...</p>}
        </div>

        <div className="paper-list-panel">
          <h2>Uploaded Papers</h2>

          {papers.length === 0 ? (
            <p className="empty-text">No papers uploaded yet.</p>
          ) : (
            papers.map((paper) => (
              <button
                key={paper.paper_id}
                className="paper-list-item"
                onClick={() => onOpenReader(paper.paper_id)}
              >
                <div className="paper-list-title">{paper.title}</div>
                <div className="paper-list-meta">{paper.parse_status}</div>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}