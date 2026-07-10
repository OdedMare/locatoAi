"use client";

const EXAMPLES = [
  "Find schools near train stations in Tel Aviv",
  "Show accidents from yesterday on Highway 6",
  "Give me the northernmost school in Tel Aviv",
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
      <label className="sr-only" htmlFor="geo-query-text">Ask a geographic question</label>
      <textarea
        id="geo-query-text"
        className="geo-query-textarea"
        placeholder="Message LocatoAI"
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
