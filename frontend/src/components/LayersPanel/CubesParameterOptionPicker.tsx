import { useMemo, useState } from "react";

import type { CubesAutocompleteOption } from "@/types/catalog";

interface CubesParameterOptionPickerProps {
  inputId: string;
  options: CubesAutocompleteOption[];
  value: string;
  disabled: boolean;
  onSelect: (value: string) => void;
}

/** Above this size a plain dropdown is unusable, so a local search box appears. */
const SEARCH_THRESHOLD = 12;
/** Cap rendered options so a many-thousand-value list never stalls the dropdown. */
const MAX_VISIBLE_OPTIONS = 200;

/**
 * Value picker for one Cubes parameter. The full autocomplete list is already
 * loaded into memory; big lists get a client-side search field that filters by
 * option name or value before selection.
 */
export default function CubesParameterOptionPicker({
  inputId,
  options,
  value,
  disabled,
  onSelect,
}: CubesParameterOptionPickerProps) {
  const [search, setSearch] = useState("");
  const searchable = options.length > SEARCH_THRESHOLD;

  const filtered = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase();
    if (!needle) return options;
    return options.filter((option) =>
      `${option.name} ${option.value}`.toLocaleLowerCase().includes(needle)
    );
  }, [options, search]);

  const visible = filtered.slice(0, MAX_VISIBLE_OPTIONS);
  const selected = value
    ? options.find((option) => option.value === value)
    : undefined;
  const selectedHidden =
    selected && !visible.some((option) => option.value === value);

  return (
    <>
      {searchable && (
        <input
          className="settings-input"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={`חיפוש בין ${options.length} ערכים…`}
          disabled={disabled}
          aria-label="חיפוש ערך לפרמטר"
          dir="auto"
        />
      )}
      <select
        id={inputId}
        className="settings-input"
        value={value}
        onChange={(event) => onSelect(event.target.value)}
        disabled={disabled}
        dir="auto"
      >
        <option value="" disabled>
          {filtered.length === 0 ? "לא נמצאו ערכים תואמים" : "בחירת ערך…"}
        </option>
        {selectedHidden && selected && (
          <option value={selected.value}>{selected.name || selected.value}</option>
        )}
        {visible.map((option, index) => (
          <option key={`${option.value}-${index}`} value={option.value}>
            {option.name || option.value}
          </option>
        ))}
      </select>
      {filtered.length > MAX_VISIBLE_OPTIONS && (
        <p className="settings-message" dir="auto">
          מציג {MAX_VISIBLE_OPTIONS} מתוך {filtered.length} ערכים — כדאי לצמצם בחיפוש.
        </p>
      )}
    </>
  );
}
