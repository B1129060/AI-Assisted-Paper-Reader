import type { PaperOverview } from "../types/paper";
import type { HighlightColor, TextHighlight } from "../types/highlight";
import HighlightableText from "./HighlightableText";

type Props = {
  paperId: number;
  overview: PaperOverview;
  language: "en" | "zh";
  highlightColor: HighlightColor;
  textHighlights: TextHighlight[];
  onTextHighlightCreated: (highlight: TextHighlight) => void;
  onTextHighlightDeleted: (highlightId: number) => void;
  onJumpToSection: (sectionTitle: string) => void;
  textHighlightMode: boolean;
};

export default function OverviewPanel({
  paperId,
  overview,
  language,
  textHighlightMode,
  highlightColor,
  textHighlights,
  onTextHighlightCreated,
  onTextHighlightDeleted,
  onJumpToSection,
}: Props) {
  return (
    <div className="overview-panel">
      {overview.abstract_summary && (
        <div className="overview-block">
          <h2>Abstract Summary</h2>
          <HighlightableText
            paperId={paperId}
            paragraphId={null}
            scope="overview"
            fieldName="abstract_summary"
            language={language}
            text={overview.abstract_summary}
            color={highlightColor}
            highlights={textHighlights}
            enabled={textHighlightMode}
            onCreated={onTextHighlightCreated}
            onDeleted={onTextHighlightDeleted}
          />
        </div>
      )}

      <div className="overview-block">
        <h2>Paper Overview</h2>
        <HighlightableText
          paperId={paperId}
          paragraphId={null}
          scope="overview"
          fieldName="overall_summary"
          language={language}
          text={overview.overall_summary}
          color={highlightColor}
          highlights={textHighlights}
          enabled={textHighlightMode}
          onCreated={onTextHighlightCreated}
          onDeleted={onTextHighlightDeleted}
        />
      </div>

      <div className="overview-block">
        <h3>Key Points</h3>
        <ul className="overview-list">
          {overview.overall_key_points.map((point, idx) => (
            <li key={idx}>
              <HighlightableText
                paperId={paperId}
                paragraphId={null}
                scope="overview"
                fieldName="overall_key_points"
                itemIndex={idx}
                language={language}
                text={point}
                color={highlightColor}
                highlights={textHighlights}
                enabled={textHighlightMode}
                onCreated={onTextHighlightCreated}
                onDeleted={onTextHighlightDeleted}
              />
            </li>
          ))}
        </ul>
      </div>

      <div className="overview-block">
        <h3>Main Sections</h3>
        <div className="section-summary-list">
          {overview.section_summaries.map((sec, idx) => (
            <div
              key={idx}
              className="section-summary-card clickable-card"
            >
              <div className="section-summary-header">
                <h4>{sec.section_title}</h4>
                <button
                  type="button"
                  onClick={() => onJumpToSection(sec.section_title)}
                >
                  Jump
                </button>
              </div>

              <HighlightableText
                paperId={paperId}
                paragraphId={null}
                scope="overview"
                fieldName="section_summary"
                itemIndex={idx}
                language={language}
                text={sec.summary}
                color={highlightColor}
                highlights={textHighlights}
                enabled={textHighlightMode}
                onCreated={onTextHighlightCreated}
                onDeleted={onTextHighlightDeleted}
              />
            </div>
          ))}
        </div>
      </div>

      <div className="overview-block">
        <h3>Highlights</h3>
        <div className="highlight-list">
          {overview.highlight_summaries.map((item, idx) => (
            <div key={item.element_id} className="highlight-card">
              <h4>{item.title}</h4>
              <HighlightableText
                paperId={paperId}
                paragraphId={null}
                scope="overview"
                fieldName="highlight_summary"
                itemIndex={idx}
                language={language}
                text={item.summary}
                color={highlightColor}
                highlights={textHighlights}
                enabled={textHighlightMode}
                onCreated={onTextHighlightCreated}
                onDeleted={onTextHighlightDeleted}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}