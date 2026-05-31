import type { PaperOverview } from "../types/paper";

import { API_BASE } from "./apiConfig";

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
