import type { PaperDetail, PaperListItem } from "../types/paper";

const API_BASE = "http://127.0.0.1:8000";

export async function fetchPapers(): Promise<PaperListItem[]> {
  const res = await fetch(`${API_BASE}/papers/`);
  if (!res.ok) {
    throw new Error("Failed to fetch papers");
  }
  return res.json();
}

export async function fetchPaperDetail(
  paperId: number,
  lang: "en" | "zh" = "en"
): Promise<PaperDetail> {
  const res = await fetch(`${API_BASE}/papers/${paperId}?lang=${lang}`);
  if (!res.ok) {
    throw new Error("Failed to fetch paper detail");
  }
  return res.json();
}

export async function uploadPaper(file: File): Promise<{ paper_id: number; parse_status: string }> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/upload/pdf`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error("Failed to upload paper");
  }

  return res.json();
}

export async function translatePaperToZh(
  paperId: number
): Promise<{ paper_id: number; status: string }> {
  const res = await fetch(`${API_BASE}/papers/${paperId}/translate-zh`, {
    method: "POST",
  });

  if (!res.ok) {
    throw new Error("Failed to translate paper to Chinese");
  }

  return res.json();
}

export async function updateParagraph(
  paragraphId: number,
  text: string
): Promise<{ paragraph_id: number; paper_id: number; section_title: string | null; status: string }> {
  const res = await fetch(`http://127.0.0.1:8000/paragraphs/${paragraphId}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ text }),
  });

  if (!res.ok) {
    throw new Error("Failed to update paragraph");
  }

  return res.json();
}

export async function updateBulletList(
  paragraphId: number,
  introText: string,
  items: string[]
): Promise<{ paragraph_id: number; paper_id: number; section_title: string | null; status: string }> {
  const res = await fetch(`http://127.0.0.1:8000/paragraphs/${paragraphId}/bullet-list`, {
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
    throw new Error("Failed to update bullet list");
  }

  return res.json();
}

export async function insertParagraphAfter(
  paragraphId: number,
  text: string
): Promise<{ paragraph_id: number; paper_id: number; section_title: string | null; status: string }> {
  const res = await fetch(`http://127.0.0.1:8000/paragraphs/${paragraphId}/insert-after`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ text }),
  });

  if (!res.ok) {
    throw new Error("Failed to insert paragraph");
  }

  return res.json();
}

export async function deleteParagraph(
  paragraphId: number
): Promise<{ paragraph_id: number; paper_id: number; section_title: string | null; status: string }> {
  const res = await fetch(`http://127.0.0.1:8000/paragraphs/${paragraphId}`, {
    method: "DELETE",
  });

  if (!res.ok) {
    throw new Error("Failed to delete paragraph");
  }

  return res.json();
}