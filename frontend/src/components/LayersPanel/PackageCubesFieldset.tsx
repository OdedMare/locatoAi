interface PackageCubesFieldsetProps {
  inputCubeName: string;
  inputCubeParameter: string;
  outputCubeName: string;
  onChangeInputCubeName: (value: string) => void;
  onChangeInputCubeParameter: (value: string) => void;
  onChangeOutputCubeName: (value: string) => void;
  busy: boolean;
}

/** flunks input/output cube config: the input cube name and its time-range
 * cube_parameter that drives parallel runs, and the output cube to read back.
 * The time range itself comes from the query at execution time. */
export default function PackageCubesFieldset({
  inputCubeName,
  inputCubeParameter,
  outputCubeName,
  onChangeInputCubeName,
  onChangeInputCubeParameter,
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
        <label
          className="field-label"
          htmlFor="package-input-cube-parameter"
        >
          פרמטר טווח הזמן (cube_parameter)
        </label>
        <input
          id="package-input-cube-parameter"
          className="settings-input"
          type="text"
          value={inputCubeParameter}
          onChange={(event) => onChangeInputCubeParameter(event.target.value)}
          disabled={busy}
          placeholder="שם פרמטר טווח הזמן"
          dir="ltr"
        />
        <small dir="auto">
          הפרמטר מקבל את טווח הזמן (start_time / end_time) שנגזר מהשאילתה
          בזמן הריצה.
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
