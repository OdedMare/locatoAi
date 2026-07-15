"use client";

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
    </div>
  );
}
