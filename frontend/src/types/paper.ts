export type PaperListItem = {
  paper_id: number;
  title: string | null;
  original_filename: string;
  parse_status: string;
  zh_translation_status: string;
  zh_translation_started_at?: string | null;
  zh_translation_finished_at?: string | null;
};

export type PdfLocation = {
  page: number;
  bbox: [number, number, number, number];
};

export type PaperDetail = {
  paper_id: number;
  title: string | null;
  original_filename: string;
  parse_status: string;
  zh_translation_status: string;
  zh_translation_started_at?: string | null;
  zh_translation_finished_at?: string | null;
  pdf_url: string;
  elements: Element[];
};

export type Element = {
  id: number;
  paragraph_id: number;
  type: "heading" | "paragraph" | "bullet_list";

  text?: string | null;
  summary?: string | null;
  key_points?: string[] | null;

  level?: string | null;

  intro_text?: string | null;
  items?: string[] | null;
  section_key?: string | null;

  // 新增：PDF 定位資訊
  page_number?: number | null;
  pdf_rects?: number[][];
  pdf_locations?: PdfLocation[];
};

export type HighlightSummary = {
  element_id: number;
  title: string;
  summary: string;
};

export type SectionSummary = {
  section_key?: string;
  section_title: string;
  summary: string;
};

export type PaperOverview = {
  paper_id: number;
  language: string;
  abstract_summary: string;
  overall_summary: string;
  overall_key_points: string[];
  highlight_element_ids: number[];
  highlight_summaries: HighlightSummary[];
  section_summaries: SectionSummary[];
};