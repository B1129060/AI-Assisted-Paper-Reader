export type HighlightColor = "yellow" | "green" | "pink";

export type TextHighlight = {
  id: number;
  paper_id: number;
  paragraph_id: number | null;
  scope: "paragraph" | "overview";
  field_name: string;
  item_index: number | null;
  language: "en" | "zh";
  start_offset: number;
  end_offset: number;
  color: HighlightColor;
};

export type PdfHighlight = {
  id: number;
  paper_id: number;
  paragraph_id: number | null;
  page_number: number;
  rects: number[][];
  color: HighlightColor;
};

export type PaperHighlightsResponse = {
  text_highlights: TextHighlight[];
  pdf_highlights: PdfHighlight[];
};

export type CreateTextHighlightPayload = {
  paper_id: number;
  paragraph_id?: number | null;
  scope: "paragraph" | "overview";
  field_name: string;
  item_index?: number | null;
  language: "en" | "zh";
  start_offset: number;
  end_offset: number;
  color: HighlightColor;
};

export type CreatePdfHighlightPayload = {
  paper_id: number;
  paragraph_id?: number | null;
  page_number: number;
  rects: number[][];
  color: HighlightColor;
};