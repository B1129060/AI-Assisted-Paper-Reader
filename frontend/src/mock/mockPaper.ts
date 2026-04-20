import type { PaperDetail } from "../types/paper";

export const mockPaper: PaperDetail = {
  paper_id: 1,
  title: "Sample Paper",
  original_filename: "sample.pdf",
  parse_status: "processed",
  pdf_url: "/sample.pdf",
  elements: [
    {
      id: 0,
      type: "heading",
      text: "1 Introduction",
      level: "section",
    },
    {
      id: 1,
      type: "paragraph",
      text: "The El Farol Bar problem is a classic example of bounded rationality and repeated decision-making under uncertainty.",
      summary: "This paragraph introduces the El Farol Bar problem as a classic bounded-rationality setting.",
      key_points: [
        "Introduces the El Farol Bar problem.",
        "Focuses on repeated decision-making.",
        "Highlights bounded rationality.",
      ],
    },
    {
      id: 2,
      type: "bullet_list",
      intro_text: "Main contributions:",
      items: [
        "An epidemiological dimension is added to the classic El Farol problem.",
        "The model is implemented as an agent-based simulation.",
        "The results show that information and social structure affect infection containment.",
      ],
      summary: "The paper contributes an epidemiological El Farol extension implemented as an agent-based model.",
      key_points: [
        "Adds epidemiological dynamics.",
        "Uses agent-based modeling.",
        "Studies information and structure effects.",
      ],
    },
  ],
};