// Frontend paper, element, PDF location, and overview types.

// Home-page paper list item returned by the backend.
export type PaperListItem = {
  paper_id: number;
  title: string | null;
  original_filename: string;
  parse_status: string;
  parse_error?: string | null;
  parse_started_at?: string | null;
  parse_finished_at?: string | null;
  overview_status: string;
  overview_error?: string | null;
  overview_started_at?: string | null;
  overview_finished_at?: string | null;
  zh_translation_status: string;
  zh_translation_error?: string | null;
  zh_translation_started_at?: string | null;
  zh_translation_finished_at?: string | null;
  export_status?: string | null;
  export_error?: string | null;
  export_started_at?: string | null;
  export_finished_at?: string | null;
  last_error_message?: string | null;
};

// Normalized PDF location used to jump/highlight generated paragraph matches.
export type PdfLocation = {
  page: number;
  bbox: [number, number, number, number];
};

// Reader-page paper detail payload.
export type PaperDetail = {
  paper_id: number;
  title: string | null;
  original_filename: string;
  parse_status: string;
  parse_error?: string | null;
  parse_started_at?: string | null;
  parse_finished_at?: string | null;
  overview_status: string;
  overview_error?: string | null;
  overview_started_at?: string | null;
  overview_finished_at?: string | null;
  zh_translation_status: string;
  zh_translation_error?: string | null;
  zh_translation_started_at?: string | null;
  zh_translation_finished_at?: string | null;
  export_status?: string | null;
  export_error?: string | null;
  export_started_at?: string | null;
  export_finished_at?: string | null;
  last_error_message?: string | null;
  pdf_url: string;
  elements: Element[];
};

// Structured reader element displayed in the paragraph table.
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

// Paper-level highlight summary item.
export type HighlightSummary = {
  element_id: number;
  title: string;
  summary: string;
};

// Paper-level section summary item.
export type SectionSummary = {
  section_key?: string;
  section_title: string;
  summary: string;
};

// Paper-level overview payload.
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
