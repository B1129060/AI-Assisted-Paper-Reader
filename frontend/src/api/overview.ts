// Frontend API client for paper overview loading and regeneration.

import type { PaperOverview } from "../types/paper";

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
  return fallback;
}

// Fetch the paper-level overview for one language.
export async function fetchPaperOverview(
  paperId: number,
  lang: "en" | "zh" = "en"
): Promise<PaperOverview> {
  const res = await fetch(`${API_BASE}/papers/${paperId}/overview?lang=${lang}`);
  if (!res.ok) {
    throw new Error(await getErrorMessage(res, "Failed to fetch paper overview"));
  }
  return res.json();
}

// Regenerate overview.
export async function regenerateOverview(
  paperId: number
): Promise<{ paper_id: number; status: string }> {
  const res = await fetch(`${API_BASE}/papers/${paperId}/regenerate-overview`, {
    method: "POST",
  });

  if (!res.ok) {
    throw new Error(await getErrorMessage(res, "Failed to regenerate overview"));
  }

  return res.json();
}
