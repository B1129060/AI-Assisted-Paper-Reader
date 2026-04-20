type Props = {
  title: string;
  filename: string;
  onBack: () => void;
};

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