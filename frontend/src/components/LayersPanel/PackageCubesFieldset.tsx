interface PackageCubesFieldsetProps {
  inputCubeName: string;
  inputCubeParameter: string;
  inputCubeKind: "time" | "geo";
  outputCubeName: string;
  onChangeInputCubeName: (value: string) => void;
  onChangeInputCubeParameter: (value: string) => void;
  onChangeInputCubeKind: (value: "time" | "geo") => void;
  onChangeOutputCubeName: (value: string) => void;
  busy: boolean;
}

/** flunks input/output cube config: the input cube name and its cube_parameter
 * that drives parallel runs, and the output cube to read back. The
 * cube_parameter receives either the query time range (kind="time") or the
 * query boundary polygons as a list of WKT multipolygons (kind="geo"), both
 * supplied from the query at execution time. */
export default function PackageCubesFieldset({
  inputCubeName,
  inputCubeParameter,
  inputCubeKind,
  outputCubeName,
  onChangeInputCubeName,
  onChangeInputCubeParameter,
  onChangeInputCubeKind,
  onChangeOutputCubeName,
  busy,
}: PackageCubesFieldsetProps) {
  return (
    <>
      <fieldset className="cubes-query-mode">
        <legend>Input Cube — קוביית הקלט לריצות מקבילות</legend>
        <label className="field-label" htmlFor="package-input-cube-name">
          שם קוביית הקלט (cube_name)
        </label>
        <input
          id="package-input-cube-name"
          className="settings-input"
          type="text"
          value={inputCubeName}
          onChange={(event) => onChangeInputCubeName(event.target.value)}
          disabled={busy}
          placeholder="שם קוביית הקלט"
          dir="ltr"
        />
        <label className="field-label" htmlFor="package-input-cube-kind">
          סוג הקלט של הפרמטר
        </label>
        <select
          id="package-input-cube-kind"
          className="settings-input"
          value={inputCubeKind}
          onChange={(event) =>
            onChangeInputCubeKind(event.target.value === "geo" ? "geo" : "time")
          }
          disabled={busy}
        >
          <option value="time">טווח זמן (start_time / end_time)</option>
          <option value="geo">שאילתה גאוגרפית — רשימת מצולעים (WKT)</option>
        </select>
        <label
          className="field-label"
          htmlFor="package-input-cube-parameter"
        >
          שם הפרמטר (cube_parameter)
        </label>
        <input
          id="package-input-cube-parameter"
          className="settings-input"
          type="text"
          value={inputCubeParameter}
          onChange={(event) => onChangeInputCubeParameter(event.target.value)}
          disabled={busy}
          placeholder="שם הפרמטר"
          dir="ltr"
        />
        <small dir="auto">
          {inputCubeKind === "geo"
            ? "הפרמטר מקבל את גבולות השאילתה כרשימת מצולעים (MULTIPOLYGON WKT) בזמן הריצה."
            : "הפרמטר מקבל את טווח הזמן (start_time / end_time) שנגזר מהשאילתה בזמן הריצה."}
        </small>
      </fieldset>
      <fieldset className="cubes-query-mode">
        <legend>Output Cube — קוביית הפלט</legend>
        <label className="field-label" htmlFor="package-output-cube-name">
          שם קוביית הפלט (cube_name)
        </label>
        <input
          id="package-output-cube-name"
          className="settings-input"
          type="text"
          value={outputCubeName}
          onChange={(event) => onChangeOutputCubeName(event.target.value)}
          disabled={busy}
          placeholder="שם קוביית הפלט"
          dir="ltr"
        />
        <small dir="auto">
          שם הקובייה שממנה נקראת התוצאה הסופית.
        </small>
      </fieldset>
    </>
  );
}
