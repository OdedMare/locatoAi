import type { FlapiParameterDefinition } from "@/types/catalog";

interface PackageParametersFieldsetProps {
  definitions: FlapiParameterDefinition[];
  values: Record<string, string>;
  busy: boolean;
  onChange: (name: string, value: string) => void;
}

function isTime(definition: FlapiParameterDefinition): boolean {
  return definition.ontology_type.toLowerCase() === "time"
    || ["time", "datetime", "date"].includes(definition.type.toLowerCase());
}

function isGeometry(definition: FlapiParameterDefinition): boolean {
  return [definition.name, definition.type, definition.ontology_type]
    .join(" ")
    .toLowerCase()
    .match(/geometry|polygon|wkt/) !== null;
}

export default function PackageParametersFieldset({
  definitions,
  values,
  busy,
  onChange,
}: PackageParametersFieldsetProps) {
  if (definitions.length === 0) return null;

  return (
    <fieldset className="cubes-dynamic-parameters">
      <legend>
        פרמטרים של Flow Package{" "}
        <span className="optional">(נשלחים לפי טיפוס ה-FLAPI)</span>
      </legend>
      {definitions.map((definition) => {
        const inputId = `package-param-${definition.name}`;
        const kind = definition.type.toLowerCase();
        const value = values[definition.name] ?? "";
        const placeholder = isTime(definition)
          ? '{"TimeBackUnit":"minute","TimeBackValue":15}'
          : isGeometry(definition)
            ? "POINT(35.181397 32.108353) או גבול מהמפה"
            : definition.single_value
              ? "ערך"
              : "ערך 1, ערך 2";

        return (
          <div key={definition.name} className="cubes-dynamic-parameter">
            <label className="field-label" htmlFor={inputId} dir="auto">
              {definition.display_name || definition.name}
              {definition.display_name && ` (${definition.name})`}
              {!definition.required && <span className="optional"> — אופציונלי</span>}
              {definition.has_default && <span className="optional"> — יש ברירת מחדל</span>}
            </label>
            {definition.description && (
              <small dir="auto">{definition.description}</small>
            )}
            {definition.options.length > 0 ? (
              <select
                id={inputId}
                className="settings-input"
                value={value}
                onChange={(event) => onChange(definition.name, event.target.value)}
                disabled={busy}
                dir="ltr"
              >
                <option value="">ברירת מחדל / ללא ערך</option>
                {definition.options.map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            ) : kind === "boolean" || kind === "bool" ? (
              <select
                id={inputId}
                className="settings-input"
                value={value}
                onChange={(event) => onChange(definition.name, event.target.value)}
                disabled={busy}
                dir="ltr"
              >
                <option value="">ברירת מחדל / ללא ערך</option>
                <option value="True">True</option>
                <option value="False">False</option>
              </select>
            ) : isTime(definition) ? (
              <textarea
                id={inputId}
                className="settings-input layer-description-input"
                value={value}
                onChange={(event) => onChange(definition.name, event.target.value)}
                disabled={busy}
                placeholder={placeholder}
                dir="ltr"
              />
            ) : (
              <input
                id={inputId}
                className="settings-input"
                type={["number", "numeric", "integer", "int", "float", "double"].includes(kind)
                  ? "number"
                  : "text"}
                value={value}
                onChange={(event) => onChange(definition.name, event.target.value)}
                disabled={busy}
                placeholder={placeholder}
                dir="ltr"
              />
            )}
          </div>
        );
      })}
    </fieldset>
  );
}
