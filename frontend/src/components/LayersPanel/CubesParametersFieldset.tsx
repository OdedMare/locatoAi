import { useState } from "react";

import type {
  CubesAutocompleteOption,
  CubesParameterDefinition,
} from "@/types/catalog";

interface CubesParametersFieldsetProps {
  definitions: CubesParameterDefinition[];
  options: Record<string, CubesAutocompleteOption[]>;
  values: Record<string, string>;
  loadingParameter: string | null;
  busy: boolean;
  sourceConfigured: boolean;
  onAddManual: (name: string) => boolean;
  onFetchOptions: (name: string) => void;
  onSelect: (name: string, value: string) => void;
  onChangeValue: (name: string, value: string) => void;
}

export default function CubesParametersFieldset({
  definitions,
  options,
  values,
  loadingParameter,
  busy,
  sourceConfigured,
  onAddManual,
  onFetchOptions,
  onSelect,
  onChangeValue,
}: CubesParametersFieldsetProps) {
  const [manualName, setManualName] = useState("");

  const addManual = () => {
    const name = manualName.trim();
    if (name && onAddManual(name)) setManualName("");
  };

  return (
    <fieldset className="cubes-dynamic-parameters">
      <legend>
        פרמטרים נדרשים ל-Cubes{" "}
        <span className="optional">
          (נשמרים בהגדרת השכבה לפני טעינת התוצאות)
        </span>
      </legend>
      <div className="cubes-dynamic-parameter">
        <label className="field-label" htmlFor="dynamic-param-name">
          הוספת פרמטר דינמי ידנית{" "}
          <span className="optional">(לדוגמה vehicleType או fl:dynamic)</span>
        </label>
        <input
          id="dynamic-param-name"
          className="settings-input"
          value={manualName}
          onChange={(event) => setManualName(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.nativeEvent.isComposing) {
              event.preventDefault();
              addManual();
            }
          }}
          placeholder="vehicleType"
          dir="ltr"
        />
        <button
          type="button"
          className="add-layer-toggle"
          onClick={addManual}
          disabled={!manualName.trim() || busy || loadingParameter !== null}
        >
          + הוספת פרמטר דינמי
        </button>
      </div>
      {definitions.map((definition) => {
        const parameterOptions = options[definition.name];
        const isLoading = loadingParameter === definition.name;
        const inputId = `cube-param-${definition.name}`;
        return (
          <div key={definition.name} className="cubes-dynamic-parameter">
            <label className="field-label" htmlFor={inputId} dir="ltr">
              {definition.display_name || definition.name}
              {definition.display_name && ` (${definition.name})`}
            </label>
            {parameterOptions && parameterOptions.length > 0 ? (
              <select
                id={inputId}
                className="settings-input"
                value={values[definition.name] ?? ""}
                onChange={(event) => onSelect(definition.name, event.target.value)}
                disabled={busy || isLoading}
                dir="auto"
              >
                <option value="" disabled>בחירת ערך…</option>
                {parameterOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.name || option.value}
                  </option>
                ))}
              </select>
            ) : definition.dynamic ? (
              <button
                id={inputId}
                type="button"
                className="add-layer-toggle"
                onClick={() => onFetchOptions(definition.name)}
                disabled={!sourceConfigured || isLoading}
              >
                {isLoading
                  ? "טוען אפשרויות…"
                  : `טעינת אפשרויות עבור ${definition.name}`}
              </button>
            ) : (
              <input
                id={inputId}
                className="settings-input"
                value={values[definition.name] ?? ""}
                onChange={(event) => onChangeValue(
                  definition.name, event.target.value
                )}
                onBlur={(event) => {
                  const value = event.target.value.trim();
                  if (value) onSelect(definition.name, value);
                }}
                disabled={busy}
                placeholder="הזנת ערך נדרש"
                dir="ltr"
              />
            )}
          </div>
        );
      })}
    </fieldset>
  );
}
