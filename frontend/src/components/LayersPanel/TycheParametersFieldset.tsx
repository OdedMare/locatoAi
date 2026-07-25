import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

interface TycheParametersFieldsetProps {
  values: Record<string, string>;
  busy: boolean;
  onChange: (values: Record<string, string>) => void;
}

export default function TycheParametersFieldset({
  values,
  busy,
  onChange,
}: TycheParametersFieldsetProps) {
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  const [error, setError] = useState("");

  const addParameter = () => {
    const key = name.trim();
    const configuredValue = value.trim();
    if (!key || !configuredValue) return;
    if (Object.prototype.hasOwnProperty.call(values, key)) {
      setError(`הפרמטר ${key} כבר מוגדר.`);
      return;
    }
    onChange({ ...values, [key]: configuredValue });
    setName("");
    setValue("");
    setError("");
  };

  const updateParameter = (key: string, configuredValue: string) => {
    onChange({ ...values, [key]: configuredValue });
  };

  const removeParameter = (key: string) => {
    onChange(Object.fromEntries(
      Object.entries(values).filter(([name]) => name !== key)
    ));
  };

  return (
    <fieldset className="cubes-dynamic-parameters">
      <legend>
        פרמטרים קבועים לבקשת Tyche{" "}
        <span className="optional">(אופציונלי, נשלחים בגוף כל בקשה)</span>
      </legend>
      {Object.entries(values).map(([key, configuredValue], index) => {
        const inputId = `tyche-parameter-${index}`;
        return (
          <div key={key} className="settings-input-row tyche-parameter-row">
            <div>
              <label className="field-label" htmlFor={`${inputId}-name`}>
                שם הפרמטר
              </label>
              <input
                id={`${inputId}-name`}
                className="settings-input"
                value={key}
                disabled
                dir="ltr"
              />
            </div>
            <div>
              <label className="field-label" htmlFor={inputId}>ערך</label>
              <div className="tyche-parameter-value">
                <input
                  id={inputId}
                  className="settings-input"
                  value={configuredValue}
                  onChange={(event) => updateParameter(key, event.target.value)}
                  disabled={busy}
                  dir="ltr"
                />
                <button
                  type="button"
                  className="catalog-delete-button"
                  onClick={() => removeParameter(key)}
                  disabled={busy}
                  aria-label={`הסרת הפרמטר ${key}`}
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </div>
          </div>
        );
      })}
      <div className="settings-input-row">
        <div>
          <label className="field-label" htmlFor="tyche-new-parameter-name">
            שם פרמטר חדש
          </label>
          <input
            id="tyche-new-parameter-name"
            className="settings-input"
            value={name}
            onChange={(event) => {
              setName(event.target.value);
              setError("");
            }}
            placeholder="environment"
            disabled={busy}
            dir="ltr"
          />
        </div>
        <div>
          <label className="field-label" htmlFor="tyche-new-parameter-value">
            ערך
          </label>
          <input
            id="tyche-new-parameter-value"
            className="settings-input"
            value={value}
            onChange={(event) => {
              setValue(event.target.value);
              setError("");
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.nativeEvent.isComposing) {
                event.preventDefault();
                addParameter();
              }
            }}
            placeholder='prod, false, 3 או ["a","b"]'
            disabled={busy}
            dir="ltr"
          />
        </div>
      </div>
      <small className="tyche-parameter-help">
        ערכי JSON כמו מספר, boolean או מערך יישלחו לפי הטיפוס; טקסט רגיל יישלח כמחרוזת.
      </small>
      {error && <p className="settings-message" role="alert">{error}</p>}
      <button
        type="button"
        className="add-layer-toggle"
        onClick={addParameter}
        disabled={busy || !name.trim() || !value.trim()}
      >
        <Plus size={15} />
        הוספת פרמטר
      </button>
    </fieldset>
  );
}
