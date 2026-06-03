// Paper overview renderer with overview-level text highlights and section navigation.

import type { PaperOverview } from "../types/paper";
import type { HighlightColor, TextHighlight } from "../types/highlight";
import HighlightableText from "./HighlightableText";

// Component props for this file.
type Props = {
  paperId: number;
  overview: PaperOverview;
  hoverOverview?: PaperOverview | null;
  language: "en" | "zh";
  highlightColor: HighlightColor;
  textHighlights: TextHighlight[];
  onTextHighlightCreated: (highlight: TextHighlight) => void;
  onTextHighlightDeleted: (highlightId: number) => void;
  onJumpToSection: (sectionTitle: string) => void;
  textHighlightMode: boolean;
};

// Data structure for overview with zh.
type OverviewWithZh = PaperOverview & {
  abstract_summary_zh?: string | null;
  overall_summary_zh?: string | null;
  overall_key_points_zh?: string[] | null;
  section_summaries_zh?: Array<{
    section_title?: string | null;
    summary?: string | null;
  }> | null;
  highlight_summaries_zh?: Array<{
    title?: string | null;
    summary?: string | null;
  }> | null;
};

// Render overview sections and overview-level highlights.
export default function OverviewPanel({
  paperId,
  overview,
  hoverOverview = null,
  language,
  textHighlightMode,
  highlightColor,
  textHighlights,
  onTextHighlightCreated,
  onTextHighlightDeleted,
  onJumpToSection,
}: Props) {
  const overviewWithZh = overview as OverviewWithZh;
  const hoverOverviewWithZh = hoverOverview as OverviewWithZh | null;

  function getHoverTranslation(primary?: string | null, fallback?: string | null) {
    if (language !== "en") return null;
    return primary || fallback || null;
  }

  function getHoverTranslationItem(
    primaryValues: string[] | null | undefined,
    fallbackValues: string[] | null | undefined,
    index: number
  ) {
    if (language !== "en") return null;
    return primaryValues?.[index] || fallbackValues?.[index] || null;
  }

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
            hoverTranslation={getHoverTranslation(hoverOverviewWithZh?.abstract_summary, overviewWithZh.abstract_summary_zh)}
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
          hoverTranslation={getHoverTranslation(hoverOverviewWithZh?.overall_summary, overviewWithZh.overall_summary_zh)}
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
                hoverTranslation={getHoverTranslationItem(hoverOverviewWithZh?.overall_key_points, overviewWithZh.overall_key_points_zh, idx)}
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
                hoverTranslation={getHoverTranslation(hoverOverviewWithZh?.section_summaries?.[idx]?.summary, overviewWithZh.section_summaries_zh?.[idx]?.summary)}
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
                hoverTranslation={getHoverTranslation(hoverOverviewWithZh?.highlight_summaries?.[idx]?.summary, overviewWithZh.highlight_summaries_zh?.[idx]?.summary)}
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