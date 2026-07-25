import type { FlapiParameterDefinition } from "@/types/catalog";

interface PackageCubesFieldsetProps {
  definitions: FlapiParameterDefinition[];
  inputParameter: string;
  onChangeInputParameter: (name: string) => void;
  availableOutputFields: string[];
  outputFields: string[];
  onToggleOutputField: (field: string) => void;
  busy: boolean;
}

/** flunks input/output cube config: which parameter drives chunking, and which
 * response fields the output cube should carry. */
export default function PackageCubesFieldset({
  definitions,
  inputParameter,
  onChangeInputParameter,
  availableOutputFields,
  outputFields,
  onToggleOutputField,
  busy,
}: PackageCubesFieldsetProps) {
  return (
    <>
      <fieldset className="cubes-query-mode">
        <legend>Input Cube — פרמטר הפיצול לריצות מקבילות</legend>
        <label className="field-label" htmlFor="package-input-parameter">
          פרמטר{" "}
          <span className="optional">
            (אופציונלי; ריק = ריצה בודדת ללא פיצול)
          </span>
        </label>
        <select
          id="package-input-parameter"
          className="settings-input"
          value={inputParameter}
          onChange={(event) => onChangeInputParameter(event.target.value)}
          disabled={busy || definitions.length === 0}
          dir="ltr"
        >
          <option value="">ללא פיצול</option>
          {definitions.map((definition) => (
            <option key={definition.name} value={definition.name}>
              {definition.display_name || definition.name} ({definition.name})
            </option>
          ))}
        </select>
        <small dir="auto">
          פרמטר מזהים (רשימת ערכים) יפוצל ל-chunks; פרמטר זמן יפוצל לטווחי זמן.
          הערכים עצמם נקבעים בשדה המתאים למטה.
        </small>
      </fieldset>
      <fieldset className="cubes-query-mode">
        <legend>Output Cube — שדות תוצאה</legend>
        {availableOutputFields.length === 0 ? (
          <small dir="auto">
            צרו הצעות metadata כדי לטעון את רשימת השדות האמיתית מהתגובה.
          </small>
        ) : (
          <div className="cubes-query-mode-options">
            {availableOutputFields.map((field) => (
              <button
                key={field}
                type="button"
                className={outputFields.includes(field) ? "active" : ""}
                aria-pressed={outputFields.includes(field)}
                disabled={busy}
                onClick={() => onToggleOutputField(field)}
              >
                <strong dir="ltr">{field}</strong>
              </button>
            ))}
          </div>
        )}
        <small dir="auto">
          אופציונלי; ריק = כל השדות שמוחזרים בתוצאה.
        </small>
      </fieldset>
    </>
  );
}
