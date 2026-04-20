import type { PaperOverview } from "../types/paper";

const API_BASE = "http://127.0.0.1:8000";

export async function fetchPaperOverview(
  paperId: number,
  lang: "en" | "zh" = "en"
): Promise<PaperOverview> {
  const res = await fetch(`${API_BASE}/papers/${paperId}/overview?lang=${lang}`);
  if (!res.ok) {
    throw new Error("Failed to fetch paper overview");
  }
  return res.json();
}

export async function regenerateOverview(
  paperId: number
): Promise<{ paper_id: number; status: string }> {
  const res = await fetch(`http://127.0.0.1:8000/papers/${paperId}/regenerate-overview`, {
    method: "POST",
  });

  if (!res.ok) {
    throw new Error("Failed to regenerate overview");
  }

  return res.json();
}