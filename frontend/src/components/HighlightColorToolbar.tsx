// Small toolbar for selecting the active highlight color.

import type { HighlightColor } from "../types/highlight";

// Component props for this file.
type Props = {
  color: HighlightColor;
  onChange: (color: HighlightColor) => void;
};

// Render the active highlight-color selector.
export default function HighlightColorToolbar({ color, onChange }: Props) {
  const colors: HighlightColor[] = ["yellow", "green", "pink"];

  return (
    <div className="highlight-toolbar">
      <span>Highlight:</span>
      {colors.map((c) => (
        <button
          key={c}
          type="button"
          onClick={() => onChange(c)}
          className={color === c ? "active" : ""}
        >
          {c}
        </button>
      ))}
    </div>
  );
}