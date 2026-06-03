// Reader header component for title, filename, and back navigation.

// Component props for this file.
type Props = {
  title: string;
  filename: string;
  onBack: () => void;
};

// Render a simple reader header with back navigation.
export default function ReaderHeader({ title, filename, onBack }: Props) {
  return (
    <div className="reader-header">
      <div className="reader-header-left">
        <button className="back-button" onClick={onBack}>
          ← Back
        </button>
        <div>
          <h1>{title}</h1>
          <p>{filename}</p>
        </div>
      </div>
    </div>
  );
}