import { Plus, Trash2 } from "lucide-react";

export interface AdditionalInputCubeDraft {
  cubeName: string;
  cubeParameter: string;
  kind: "time" | "values";
  values: string;
}

interface PackageCubesFieldsetProps {
  inputCubeName: string;
  inputCubeParameter: string;
  additionalInputCubes: AdditionalInputCubeDraft[];
  outputCubeName: string;
  onChangeInputCubeName: (value: string) => void;
  onChangeInputCubeParameter: (value: string) => void;
  onChangeAdditionalInputCubes: (value: AdditionalInputCubeDraft[]) => void;
  onChangeOutputCubeName: (value: string) => void;
  busy: boolean;
}

const EMPTY_ADDITIONAL_CUBE: AdditionalInputCubeDraft = {
  cubeName: "",
  cubeParameter: "",
  kind: "time",
  values: "",
};

/** Builds the main geographic cube and optional time/static-value cubes. */
export default function PackageCubesFieldset({
  inputCubeName,
  inputCubeParameter,
  additionalInputCubes,
  outputCubeName,
  onChangeInputCubeName,
  onChangeInputCubeParameter,
  onChangeAdditionalInputCubes,
  onChangeOutputCubeName,
  busy,
}: PackageCubesFieldsetProps) {
  const addCube = () => onChangeAdditionalInputCubes([
    ...additionalInputCubes,
    { ...EMPTY_ADDITIONAL_CUBE },
  ]);

  const updateCube = (
    index: number,
    update: Partial<AdditionalInputCubeDraft>,
  ) => onChangeAdditionalInputCubes(additionalInputCubes.map(
    (cube, cubeIndex) => cubeIndex === index ? { ...cube, ...update } : cube,
  ));

  const removeCube = (index: number) => onChangeAdditionalInputCubes(
    additionalInputCubes.filter((_, cubeIndex) => cubeIndex !== index),
  );

  return (
    <>
      <fieldset className="cubes-query-mode">
        <legend>Main Input Cube — קוביית קלט גאוגרפית</legend>
        <label className="field-label" htmlFor="package-input-cube-name">
          שם קוביית הקלט (cube_name)
        </label>
        <input
          id="package-input-cube-name"
          className="settings-input"
          value={inputCubeName}
          onChange={(event) => onChangeInputCubeName(event.target.value)}
          disabled={busy}
          placeholder="שם קוביית הקלט"
          dir="ltr"
        />
        <label className="field-label" htmlFor="package-input-cube-parameter">
          שם הפרמטר (cube_parameter)
        </label>
        <input
          id="package-input-cube-parameter"
          className="settings-input"
          value={inputCubeParameter}
          onChange={(event) => onChangeInputCubeParameter(event.target.value)}
          disabled={busy}
          placeholder="שם הפרמטר הגאוגרפי"
          dir="ltr"
        />
        <small dir="auto">
          הפרמטר מקבל בזמן הריצה את כל גבולות השאילתה כערך WKT מסוג MULTIPOLYGON.
        </small>
      </fieldset>

      <fieldset className="cubes-query-mode package-additional-cubes">
        <legend>Additional Input Cubes — קוביות קלט נוספות</legend>
        <div className="package-additional-cubes-heading">
          <small>כל קובייה יכולה לקבל טווח זמן מהשאילתה או ערכים קבועים.</small>
          <button
            type="button"
            className="package-cube-icon-button"
            onClick={addCube}
            disabled={busy}
            aria-label="הוספת קוביית קלט נוספת"
            title="הוספת קוביית קלט נוספת"
          >
            <Plus size={18} aria-hidden="true" />
          </button>
        </div>
        {additionalInputCubes.length === 0 && (
          <p className="package-additional-cubes-empty">
            אין קוביות נוספות. לחצו על + כדי להוסיף.
          </p>
        )}
        {additionalInputCubes.map((cube, index) => (
          <div
            className="package-additional-cube-row"
            role="group"
            aria-labelledby={`package-additional-cube-${index}-title`}
            key={index}
          >
            <div className="package-additional-cube-row-heading">
              <strong id={`package-additional-cube-${index}-title`}>
                קוביית קלט נוספת {index + 1}
              </strong>
              <button
                type="button"
                className="package-cube-icon-button danger"
                onClick={() => removeCube(index)}
                disabled={busy}
                aria-label={`הסרת קוביית קלט נוספת ${index + 1}`}
                title="הסרת קובייה"
              >
                <Trash2 size={16} aria-hidden="true" />
              </button>
            </div>
            <div className="settings-input-row">
              <div>
                <label className="field-label" htmlFor={`package-additional-cube-${index}-name`}>
                  שם הקובייה (cube_name)
                </label>
                <input
                  id={`package-additional-cube-${index}-name`}
                  className="settings-input"
                  value={cube.cubeName}
                  onChange={(event) => updateCube(index, { cubeName: event.target.value })}
                  disabled={busy}
                  dir="ltr"
                />
              </div>
              <div>
                <label className="field-label" htmlFor={`package-additional-cube-${index}-parameter`}>
                  שם הפרמטר (cube_parameter)
                </label>
                <input
                  id={`package-additional-cube-${index}-parameter`}
                  className="settings-input"
                  value={cube.cubeParameter}
                  onChange={(event) => updateCube(index, { cubeParameter: event.target.value })}
                  disabled={busy}
                  dir="ltr"
                />
              </div>
            </div>
            <label className="field-label" htmlFor={`package-additional-cube-${index}-kind`}>
              מקור הערך
            </label>
            <select
              id={`package-additional-cube-${index}-kind`}
              className="settings-input"
              value={cube.kind}
              onChange={(event) => updateCube(index, {
                kind: event.target.value === "values" ? "values" : "time",
              })}
              disabled={busy}
            >
              <option value="time">טווח הזמן של השאילתה</option>
              <option value="values">ערכים / פרמטרים קבועים</option>
            </select>
            {cube.kind === "values" && (
              <>
                <label className="field-label" htmlFor={`package-additional-cube-${index}-values`}>
                  ערכים <span className="optional">(פסיק או שורה חדשה בין ערכים)</span>
                </label>
                <textarea
                  id={`package-additional-cube-${index}-values`}
                  className="settings-input package-cube-values"
                  value={cube.values}
                  onChange={(event) => updateCube(index, { values: event.target.value })}
                  disabled={busy}
                  placeholder="prod, active"
                  dir="auto"
                />
              </>
            )}
          </div>
        ))}
      </fieldset>

      <fieldset className="cubes-query-mode">
        <legend>Output Cube — קוביית הפלט</legend>
        <label className="field-label" htmlFor="package-output-cube-name">
          שם קוביית הפלט (cube_name)
        </label>
        <input
          id="package-output-cube-name"
          className="settings-input"
          value={outputCubeName}
          onChange={(event) => onChangeOutputCubeName(event.target.value)}
          disabled={busy}
          placeholder="שם קוביית הפלט"
          dir="ltr"
        />
        <small dir="auto">שם הקובייה שממנה נקראת התוצאה הסופית.</small>
      </fieldset>
    </>
  );
}
