// Frontend API client for text and PDF highlight operations.

import type {
  CreatePdfHighlightPayload,
  CreateTextHighlightPayload,
  PaperHighlightsResponse,
  PdfHighlight,
  TextHighlight,
} from "../types/highlight";

import { API_BASE } from "./apiConfig";

// Get error message.
async function getErrorMessage(res: Response, fallback: string) {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") {
      return data.detail;
    }
    if (Array.isArray(data?.detail)) {
      return data.detail
        .map((item: unknown) => {
          if (typeof item === "object" && item !== null && "msg" in item) {
            const msg = (item as { msg?: unknown }).msg;
            return typeof msg === "string" ? msg : String(msg);
          }
          return String(item);
        })
        .join("; ");
    }
  } catch {
    // Ignore JSON parse errors and use fallback.
  }

  if (res.status === 404) {
    return "Paper not found.";
  }

  return fallback;
}

// Fetch text and PDF highlights for one paper and language.
export async function fetchHighlights(
  paperId: number,
  language: "en" | "zh"
): Promise<PaperHighlightsResponse> {
  const res = await fetch(`${API_BASE}/papers/${paperId}/highlights?language=${language}`);
  if (!res.ok) {
    throw new Error(await getErrorMessage(res, "Failed to fetch highlights"));
  }
  return res.json();
}

// Create text highlight.
export async function createTextHighlight(
  payload: CreateTextHighlightPayload
): Promise<TextHighlight> {
  const res = await fetch(`${API_BASE}/highlights/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(await getErrorMessage(res, "Failed to create text highlight"));
  }
  return res.json();
}

// Delete text highlight.
export async function deleteTextHighlight(highlightId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/highlights/text/${highlightId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error(await getErrorMessage(res, "Failed to delete text highlight"));
  }
}

// Create pdf highlight.
export async function createPdfHighlight(
  payload: CreatePdfHighlightPayload
): Promise<PdfHighlight> {
  const res = await fetch(`${API_BASE}/highlights/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(await getErrorMessage(res, "Failed to create PDF highlight"));
  }
  return res.json();
}

// Delete pdf highlight.
export async function deletePdfHighlight(highlightId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/highlights/pdf/${highlightId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error(await getErrorMessage(res, "Failed to delete PDF highlight"));
  }
}
