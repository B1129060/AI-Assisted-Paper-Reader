// Frontend highlight types shared across highlight UI and API clients.

// Allowed highlight colors shared by text and PDF highlights.
export type HighlightColor = "yellow" | "green" | "pink";

// Stored text highlight represented by offsets into a rendered field.
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

// Stored PDF highlight represented by normalized page rectangles.
export type PdfHighlight = {
  id: number;
  paper_id: number;
  paragraph_id: number | null;
  page_number: number;
  rects: number[][];
  color: HighlightColor;
};

// Combined highlight response for one paper.
export type PaperHighlightsResponse = {
  text_highlights: TextHighlight[];
  pdf_highlights: PdfHighlight[];
};

// Request payload for creating a text highlight.
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

// Request payload for creating a PDF highlight.
export type CreatePdfHighlightPayload = {
  paper_id: number;
  paragraph_id?: number | null;
  page_number: number;
  rects: number[][];
  color: HighlightColor;
};