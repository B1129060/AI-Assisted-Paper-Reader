import type { HighlightColor } from "../types/highlight";

type Props = {
  color: HighlightColor;
  onChange: (color: HighlightColor) => void;
};

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