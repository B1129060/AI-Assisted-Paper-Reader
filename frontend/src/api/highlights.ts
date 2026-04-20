import type {
  CreatePdfHighlightPayload,
  CreateTextHighlightPayload,
  PaperHighlightsResponse,
  PdfHighlight,
  TextHighlight,
} from "../types/highlight";

const API_BASE = "http://127.0.0.1:8000";

export async function fetchHighlights(
  paperId: number,
  language: "en" | "zh"
): Promise<PaperHighlightsResponse> {
  const res = await fetch(`${API_BASE}/papers/${paperId}/highlights?language=${language}`);
  if (!res.ok) throw new Error("Failed to fetch highlights");
  return res.json();
}

export async function createTextHighlight(
  payload: CreateTextHighlightPayload
): Promise<TextHighlight> {
  const res = await fetch(`${API_BASE}/highlights/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to create text highlight");
  return res.json();
}

export async function deleteTextHighlight(highlightId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/highlights/text/${highlightId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete text highlight");
}

export async function createPdfHighlight(
  payload: CreatePdfHighlightPayload
): Promise<PdfHighlight> {
  const res = await fetch(`${API_BASE}/highlights/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to create PDF highlight");
  return res.json();
}

export async function deletePdfHighlight(highlightId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/highlights/pdf/${highlightId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete PDF highlight");
}