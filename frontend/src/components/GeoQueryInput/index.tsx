"use client";

const EXAMPLES = [
  "מצא בתי ספר ליד תחנות רכבת בתל אביב",
  "הצג תאונות מאתמול בכביש 6",
  "מצא את בית הספר הצפוני ביותר בתל אביב",
];

interface GeoQueryInputProps {
  value: string;
  onChange: (value: string) => void;
  /** Called on Cmd/Ctrl+Enter as a submit shortcut. */
  onSubmit: () => void;
}

/** ChatGPT-style free-text input for the natural-language geo query. */
export default function GeoQueryInput({
  value,
  onChange,
  onSubmit,
}: GeoQueryInputProps) {
  return (
    <div className="geo-query-input">
      <label className="sr-only" htmlFor="geo-query-text">שאלו שאלה גיאוגרפית</label>
      <textarea
        id="geo-query-text"
        className="geo-query-textarea"
        placeholder="כתבו הודעה ל-LocatoAI"
        rows={2}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
            e.preventDefault();
            onSubmit();
          }
        }}
      />
      <div className="query-examples">
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            className="example-chip"
            onClick={() => onChange(example)}
          >
            {example}
          </button>
        ))}
      </div>
    </div>
  );
}
