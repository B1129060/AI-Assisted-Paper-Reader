// Frontend API client for paper, upload, translation, edit, export, delete, and title operations.

import type { PaperDetail, PaperListItem } from "../types/paper";

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

// Fetch the current user's paper list.
export async function fetchPapers(): Promise<PaperListItem[]> {
  const res = await fetch(`${API_BASE}/papers/`);
  if (!res.ok) {
    throw new Error(await getErrorMessage(res, "Failed to fetch papers"));
  }
  return res.json();
}

// Fetch one paper detail payload for the selected language.
export async function fetchPaperDetail(
  paperId: number,
  lang: "en" | "zh" = "en"
): Promise<PaperDetail> {
  const res = await fetch(`${API_BASE}/papers/${paperId}?lang=${lang}`);
  if (!res.ok) {
    throw new Error(await getErrorMessage(res, "Failed to fetch paper detail"));
  }
  return res.json();
}

// Upload a PDF file and return the queued paper status.
export async function uploadPaper(file: File): Promise<{
  paper_id: number;
  parse_status: string;
  overview_status?: string;
  last_error_message?: string | null;
}> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/upload/pdf`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error(await getErrorMessage(res, "Failed to upload paper"));
  }

  return res.json();
}

// Translate paper to zh.
export async function translatePaperToZh(
  paperId: number
): Promise<{ paper_id: number; status: string }> {
  const res = await fetch(`${API_BASE}/papers/${paperId}/translate-zh`, {
    method: "POST",
  });

  if (!res.ok) {
    throw new Error(await getErrorMessage(res, "Failed to translate paper to Chinese"));
  }

  return res.json();
}

// Update paragraph.
export async function updateParagraph(
  paragraphId: number,
  text: string
): Promise<{ paragraph_id: number; paper_id: number; section_title: string | null; status: string }> {
  const res = await fetch(`${API_BASE}/paragraphs/${paragraphId}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ text }),
  });

  if (!res.ok) {
    throw new Error(await getErrorMessage(res, "Failed to update paragraph"));
  }

  return res.json();
}

// Update bullet list.
export async function updateBulletList(
  paragraphId: number,
  introText: string,
  items: string[]
): Promise<{ paragraph_id: number; paper_id: number; section_title: string | null; status: string }> {
  const res = await fetch(`${API_BASE}/paragraphs/${paragraphId}/bullet-list`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      intro_text: introText,
      items,
    }),
  });

  if (!res.ok) {
    throw new Error(await getErrorMessage(res, "Failed to update bullet list"));
  }

  return res.json();
}

// Insert paragraph after.
export async function insertParagraphAfter(
  paragraphId: number,
  text: string
): Promise<{ paragraph_id: number; paper_id: number; section_title: string | null; status: string }> {
  const res = await fetch(`${API_BASE}/paragraphs/${paragraphId}/insert-after`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ text }),
  });

  if (!res.ok) {
    throw new Error(await getErrorMessage(res, "Failed to insert paragraph"));
  }

  return res.json();
}

// Delete paragraph.
export async function deleteParagraph(
  paragraphId: number
): Promise<{ paragraph_id: number; paper_id: number; section_title: string | null; status: string }> {
  const res = await fetch(`${API_BASE}/paragraphs/${paragraphId}`, {
    method: "DELETE",
  });

  if (!res.ok) {
    throw new Error(await getErrorMessage(res, "Failed to delete paragraph"));
  }

  return res.json();
}

// Request options controlling which export files and highlights are included.
export type ExportOptions = {
  include_pdf: boolean;
  include_overview: boolean;
  include_paragraphs: boolean;
  language_mode: "en" | "zh" | "both";
  include_pdf_highlights: boolean;
  include_text_highlights: boolean;
};

// Export paper.
export async function exportPaper(
  paperId: number,
  options: ExportOptions
): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(`${API_BASE}/papers/${paperId}/export`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(options),
  });

  if (!res.ok) {
    throw new Error(await getErrorMessage(res, "Failed to export paper"));
  }

  const blob = await res.blob();

  const contentDisposition = res.headers.get("Content-Disposition") || "";
  const match = contentDisposition.match(/filename="(.+)"/);
  const filename = match ? match[1] : "export";

  return { blob, filename };
}

// Delete paper.
export async function deletePaper(
  paperId: number
): Promise<{
  message: string;
  paper_id: number;
  deleted_pdf: boolean;
  deleted_debug_files: boolean;
}> {
  const res = await fetch(`${API_BASE}/papers/${paperId}/with-file`, {
    method: "DELETE",
  });

  if (!res.ok) {
    throw new Error(await getErrorMessage(res, "Failed to delete paper"));
  }

  return res.json();
}

// Update paper title.
export async function updatePaperTitle(
  paperId: number,
  title: string
): Promise<{
  paper_id: number;
  title: string;
  original_filename: string;
  message: string;
}> {
  const res = await fetch(`${API_BASE}/papers/${paperId}/title`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ title }),
  });

  if (!res.ok) {
    throw new Error(await getErrorMessage(res, "Failed to update paper title"));
  }

  return res.json();
}
