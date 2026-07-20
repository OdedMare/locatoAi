"use client";

import { useEffect, useMemo, useState } from "react";
import {
  activateTycheLayer,
  createLayer,
  fetchCubesAutocompleteOptions,
  generateLayerMetadata,
  getLayers,
  getMqsLayers,
  updateLayer,
} from "@/services/catalogService";
import type {
  CatalogLayer,
  CubesAutocompleteOption,
  CubesParameterDefinition,
  CubesQueryMode,
  RemoteMqsLayer,
} from "@/types/catalog";
import type { GeoJSONMultiPolygon } from "@/types/geo-query";
import CubesParametersFieldset from "./CubesParametersFieldset";

interface LayersPanelProps {
  onClose: () => void;
  drawnSampleBoundary: GeoJSONMultiPolygon | null;
  viewportSampleBoundary: GeoJSONMultiPolygon;
}

function mergeTags(current: string[], value: string, limit: number): string[] {
  const additions = value.split(",").map((tag) => tag.trim()).filter(Boolean);
  const seen = new Set(current.map((tag) => tag.toLocaleLowerCase()));
  return [...current, ...additions.filter((tag) => {
    const key = tag.toLocaleLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  })].slice(0, limit);
}

/**
 * Catalog browser: every data layer the agent can query, searchable by
 * name / description / tags — so users know what they can ask about.
 */
export default function LayersPanel({
  onClose,
  drawnSampleBoundary,
  viewportSampleBoundary,
}: LayersPanelProps) {
  const [layers, setLayers] = useState<CatalogLayer[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [tagDraft, setTagDraft] = useState("");
  const [provider, setProvider] = useState("mqs");
  const [sourceUrl, setSourceUrl] = useState("");
  const [cubesQueryMode, setCubesQueryMode] = useState<CubesQueryMode>("auto");
  const [dynamicParameterNames, setDynamicParameterNames] = useState<string[]>([]);
  const [parameterDefinitions, setParameterDefinitions] =
    useState<CubesParameterDefinition[]>([]);
  const [manualDynamicParameterNames, setManualDynamicParameterNames] = useState<string[]>([]);
  const [dynamicParameterOptions, setDynamicParameterOptions] =
    useState<Record<string, CubesAutocompleteOption[]>>({});
  const [dynamicParameterValues, setDynamicParameterValues] =
    useState<Record<string, string>>({});
  const [requiresSamplePolygon, setRequiresSamplePolygon] = useState(false);
  const [cubesSampleBoundary, setCubesSampleBoundary] =
    useState<GeoJSONMultiPolygon | null>(null);
  const [cubesSampleBoundarySource, setCubesSampleBoundarySource] =
    useState<"drawn" | "viewport" | null>(null);
  const [loadingDynamicParameter, setLoadingDynamicParameter] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [generatingMetadata, setGeneratingMetadata] = useState(false);
  const [formMessage, setFormMessage] = useState<string | null>(null);
  const [activatingTyche, setActivatingTyche] = useState(false);
  const [tycheMessage, setTycheMessage] = useState<string | null>(null);
  const [showMqsBrowser, setShowMqsBrowser] = useState(false);
  const [mqsLayers, setMqsLayers] = useState<RemoteMqsLayer[] | null>(null);
  const [mqsSearch, setMqsSearch] = useState("");
  const [mqsMessage, setMqsMessage] = useState<string | null>(null);
  const [editingLayerId, setEditingLayerId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editTags, setEditTags] = useState<string[]>([]);
  const [editTagDraft, setEditTagDraft] = useState("");
  const [editMessage, setEditMessage] = useState<string | null>(null);
  const [editSaving, setEditSaving] = useState(false);

  useEffect(() => {
    getLayers()
      .then((data) => setLayers(data.layers))
      .catch((err) => {
        console.error("Layer loading failed", err);
        setError(err instanceof Error ? err.message : "לא ניתן לטעון שכבות");
      });
  }, []);

  const filtered = useMemo(() => {
    if (!layers) return [];
    const needle = search.trim().toLowerCase();
    if (!needle) return layers;
    return layers.filter((layer) =>
      [layer.name, layer.description, ...layer.tags]
        .join(" ")
        .toLowerCase()
        .includes(needle)
    );
  }, [layers, search]);

  const filteredMqs = useMemo(() => {
    if (!mqsLayers) return [];
    const needle = mqsSearch.trim().toLocaleLowerCase();
    if (!needle) return mqsLayers;
    return mqsLayers.filter((layer) =>
      [layer.name, layer.description, ...layer.tags].join(" ").toLocaleLowerCase().includes(needle)
    );
  }, [mqsLayers, mqsSearch]);

  const commitTags = (value: string) => {
    setTags((current) => mergeTags(current, value, 20));
    setTagDraft("");
  };

  const removeTag = (tagToRemove: string) => {
    setTags((current) => current.filter((tag) => tag !== tagToRemove));
  };

  const startEditing = (layer: CatalogLayer) => {
    setEditingLayerId(layer.id);
    setEditName(layer.name);
    setEditDescription(layer.description);
    setEditTags(layer.tags);
    setEditTagDraft("");
    setEditMessage(null);
  };

  const cancelEditing = () => {
    setEditingLayerId(null);
    setEditMessage(null);
    setEditTagDraft("");
  };

  const commitEditTags = (value: string) => {
    setEditTags((current) => mergeTags(current, value, 40));
    setEditTagDraft("");
  };

  const handleSaveEdit = async () => {
    if (!editingLayerId || !editName.trim() || editSaving) return;
    const finalTags = mergeTags(editTags, editTagDraft, 40);
    setEditSaving(true);
    setEditMessage(null);
    try {
      const updated = await updateLayer(editingLayerId, {
        name: editName.trim(), description: editDescription.trim(), tags: finalTags,
      });
      setLayers((current) => (current ?? []).map(
        (layer) => layer.id === updated.id ? updated : layer
      ));
      setEditingLayerId(null);
    } catch (err) {
      console.error("Catalog layer update failed", err);
      setEditMessage(err instanceof Error ? err.message : "עדכון השכבה נכשל");
    } finally {
      setEditSaving(false);
    }
  };

  const handleAddLayer = async () => {
    if (!name.trim() || !sourceUrl.trim() || saving) return;
    setSaving(true);
    setFormMessage(null);
    try {
      const created = await createLayer({
        name: name.trim(),
        description: description.trim(),
        tags,
        provider: provider.trim(),
        source_url: sourceUrl.trim(),
        cubes_query_mode: cubesQueryMode,
        cubes_parameters: dynamicParameterValues,
      });
      setLayers((current) => [...(current ?? []), created]);
      setName("");
      setDescription("");
      setTags([]);
      setTagDraft("");
      setSourceUrl("");
      setCubesQueryMode("auto");
      setDynamicParameterNames([]);
      setParameterDefinitions([]);
      setManualDynamicParameterNames([]);
      setDynamicParameterOptions({});
      setDynamicParameterValues({});
      setRequiresSamplePolygon(false);
      setCubesSampleBoundary(null);
      setCubesSampleBoundarySource(null);
      setFormMessage("השכבה נוספה ל-PostgreSQL ✓");
    } catch (err) {
      console.error("Layer creation failed", err);
      setFormMessage(err instanceof Error ? err.message : "לא ניתן להוסיף את השכבה");
    } finally {
      setSaving(false);
    }
  };

  const handleBrowseMqs = async () => {
    const opening = !showMqsBrowser;
    setShowMqsBrowser(opening);
    if (!opening || mqsLayers) return;
    setMqsMessage(null);
    try {
      const result = await getMqsLayers();
      setMqsLayers(result.layers);
      if (result.skipped) setMqsMessage(`${result.skipped} רשומות לא תקינות דולגו`);
    } catch (err) {
      console.error("MQS layer browsing failed", err);
      setMqsMessage(err instanceof Error ? err.message : "טעינת שכבות MQS נכשלה");
    }
  };

  const loadDynamicParameterOptions = async (
    cubeSource: string,
    parameterNames: string[],
  ) => {
    let optionsError: string | null = null;
    for (const parameterName of parameterNames) {
      setLoadingDynamicParameter(parameterName);
      try {
        const result = await fetchCubesAutocompleteOptions({
          source_url: cubeSource,
          parameter_name: parameterName,
        });
        setDynamicParameterOptions((current) => ({
          ...current,
          [parameterName]: result.options,
        }));
      } catch (err) {
        console.error(`Cubes ${parameterName} autocomplete fetch failed`, err);
        optionsError = err instanceof Error
          ? err.message
          : `טעינת אפשרויות ${parameterName} נכשלה`;
      } finally {
        setLoadingDynamicParameter(null);
      }
    }
    if (optionsError) {
      setFormMessage(`${optionsError} — אפשר לנסות לטעון שוב.`);
    }
  };

  const handleGenerateMetadata = async (
    selected?: RemoteMqsLayer,
    selectedDynamicValues: Record<string, string> = dynamicParameterValues,
    selectedBoundary: GeoJSONMultiPolygon | null = cubesSampleBoundary,
  ) => {
    const target = {
      name: selected?.name ?? name,
      provider: selected?.provider ?? provider,
      source_url: selected?.source_url ?? sourceUrl,
      cubes_query_mode: cubesQueryMode,
      cubes_parameters: selectedDynamicValues,
      cubes_sample_boundary: selectedBoundary,
    };
    if (!target.name.trim() || !target.provider.trim() || !target.source_url.trim()) return;
    setGeneratingMetadata(true);
    setFormMessage("דוגם עד 10 ישויות ומייצר תיאור ותגיות…");
    try {
      const generated = await generateLayerMetadata(target);
      setRequiresSamplePolygon(generated.requires_sample_polygon);
      if (generated.sample_count > 0) {
        setDescription(generated.description);
        setTags(generated.tags);
        setTagDraft("");
      }
      const definitions = [...generated.configurable_parameters];
      for (const manualName of manualDynamicParameterNames) {
        if (!definitions.some(
          (item) => item.name.toLocaleLowerCase() === manualName.toLocaleLowerCase()
        )) {
          definitions.push({
            name: manualName,
            display_name: "",
            required: true,
            dynamic: true,
            options: [],
          });
        }
      }
      const parameterNames = definitions.map((item) => item.name);
      setParameterDefinitions(definitions);
      setDynamicParameterNames(parameterNames);
      setDynamicParameterOptions((current) => Object.fromEntries(
        definitions
          .map((item) => {
            const staticOptions = item.options.map((value) => ({ value, name: value }));
            return [
              item.name,
              item.dynamic
                ? current[item.name]
                : staticOptions.length > 0 ? staticOptions : undefined,
            ] as const;
          })
          .filter((entry): entry is readonly [string, CubesAutocompleteOption[]] =>
            Boolean(entry[1])
          )
      ));
      setDynamicParameterValues((current) => Object.fromEntries(
        parameterNames
          .filter((parameterName) => current[parameterName])
          .map((parameterName) => [parameterName, current[parameterName]])
      ));
      const missingParameters = parameterNames.some(
        (parameterName) => !selectedDynamicValues[parameterName]
      );
      const missingPolygon = generated.requires_sample_polygon && !selectedBoundary;
      setFormMessage(
        missingParameters && missingPolygon
          ? "יש לבחור ערכים לפרמטרים הנדרשים ופוליגון לדגימת ה-metadata."
          : missingPolygon
          ? "ה-Cube דורש פוליגון לדגימת metadata — בחרו פוליגון שצויר במפה או את תחום התצוגה."
          : missingParameters
          ? "נמצאו פרמטרים נדרשים — יש לבחור ערכים לפני טעינת התוצאות."
          : parameterNames.length > 0
          ? `נטענו ${generated.sample_count} תוצאות עבור הפרמטרים שהוגדרו ונוצרו הצעות ✓`
          : `נוצרו הצעות מ-${generated.sample_count} ישויות אקראיות — אפשר לערוך לפני ההוספה ✓`
      );
      const dynamicNames = definitions
        .filter((item) => item.dynamic)
        .map((item) => item.name);
      if (dynamicNames.length > 0) {
        // Required controls are already visible. Autocomplete hydration runs
        // separately so a slow child cube cannot keep metadata generation
        // in its busy state or hide the parameters from the user.
        void loadDynamicParameterOptions(
          target.source_url.trim(), dynamicNames
        );
      }
    } catch (err) {
      console.error("Layer metadata generation failed", err);
      setFormMessage(err instanceof Error ? err.message : "יצירת התיאור והתגיות נכשלה");
    } finally {
      setGeneratingMetadata(false);
    }
  };

  const handleFetchDynamicOptions = async (parameterName: string) => {
    if (!sourceUrl.trim() || loadingDynamicParameter) return;
    setLoadingDynamicParameter(parameterName);
    setFormMessage(null);
    try {
      const result = await fetchCubesAutocompleteOptions({
        source_url: sourceUrl.trim(), parameter_name: parameterName,
      });
      setDynamicParameterOptions((current) => ({ ...current, [parameterName]: result.options }));
    } catch (err) {
      console.error("Cubes autocomplete fetch failed", err);
      setFormMessage(err instanceof Error ? err.message : "טעינת אפשרויות הפרמטר נכשלה");
    } finally {
      setLoadingDynamicParameter(null);
    }
  };

  const handleSelectDynamicParameter = (parameterName: string, value: string) => {
    const selectedDynamicValues = {
      ...dynamicParameterValues,
      [parameterName]: value,
    };
    setDynamicParameterValues(selectedDynamicValues);
    const allDynamicParametersSelected = dynamicParameterNames.every(
      (name) => Boolean(selectedDynamicValues[name])
    );
    if (allDynamicParametersSelected && (!requiresSamplePolygon || cubesSampleBoundary)) {
      void handleGenerateMetadata(undefined, selectedDynamicValues);
    } else if (requiresSamplePolygon && !cubesSampleBoundary) {
      setFormMessage("יש לבחור פוליגון לדגימת ה-metadata.");
    } else {
      setFormMessage("יש לבחור ערך לכל הפרמטרים הנדרשים.");
    }
  };

  const handleUseSampleBoundary = (
    boundary: GeoJSONMultiPolygon,
    source: "drawn" | "viewport",
  ) => {
    setCubesSampleBoundary(boundary);
    setCubesSampleBoundarySource(source);
    const allParametersSelected = dynamicParameterNames.every(
      (parameterName) => Boolean(dynamicParameterValues[parameterName])
    );
    if (allParametersSelected) {
      void handleGenerateMetadata(undefined, dynamicParameterValues, boundary);
    } else {
      setFormMessage("הפוליגון נבחר. כעת יש לבחור ערך לכל הפרמטרים הנדרשים.");
    }
  };

  const handleAddDynamicParameter = (parameterName: string): boolean => {
    if (dynamicParameterNames.some(
      (name) => name.toLocaleLowerCase() === parameterName.toLocaleLowerCase()
    )) {
      setFormMessage(`הפרמטר ${parameterName} כבר נוסף.`);
      return false;
    }
    setManualDynamicParameterNames((current) => [...current, parameterName]);
    setDynamicParameterNames((current) => [...current, parameterName]);
    setParameterDefinitions((current) => [...current, {
      name: parameterName,
      display_name: "",
      required: true,
      dynamic: true,
      options: [],
    }]);
    if (sourceUrl.trim()) {
      void handleFetchDynamicOptions(parameterName);
    } else {
      setFormMessage("יש להזין קודם שם Cube, ואז לטעון את אפשרויות הפרמטר.");
    }
    return true;
  };

  const selectMqsLayer = (layer: RemoteMqsLayer) => {
    setName(layer.name);
    setDescription(layer.description);
    setTags(layer.tags);
    setTagDraft("");
    setProvider(layer.provider);
    setSourceUrl(layer.source_url);
    setCubesQueryMode("auto");
    setDynamicParameterNames([]);
    setParameterDefinitions([]);
    setManualDynamicParameterNames([]);
    setDynamicParameterOptions({});
    setDynamicParameterValues({});
    setRequiresSamplePolygon(false);
    setCubesSampleBoundary(null);
    setCubesSampleBoundarySource(null);
    setFormMessage(null);
    setShowAddForm(true);
    setShowMqsBrowser(false);
    void handleGenerateMetadata(layer, {}, null);
  };

  const startCubesLayer = () => {
    setProvider("cubes");
    setSourceUrl("");
    setDynamicParameterNames([]);
    setParameterDefinitions([]);
    setManualDynamicParameterNames([]);
    setDynamicParameterOptions({});
    setDynamicParameterValues({});
    setRequiresSamplePolygon(false);
    setCubesSampleBoundary(null);
    setCubesSampleBoundarySource(null);
    setName("");
    setDescription("");
    setTags([]);
    setCubesQueryMode("auto");
    setFormMessage("הזינו שם שכבה ושם Cube, ואז הפעילו יצירת תיאור ותגיות.");
    setShowAddForm(true);
  };

  const handleActivateTyche = async () => {
    if (activatingTyche) return;
    setActivatingTyche(true);
    setTycheMessage("בודק חיבור ל-Tyche ומפעיל את השכבה…");
    try {
      const activated = await activateTycheLayer();
      setLayers((current) => {
        const remaining = (current ?? []).filter((item) => item.id !== activated.id);
        return [...remaining, activated];
      });
      setTycheMessage("שכבת כוחותינו פעילה בקטלוג ✓");
    } catch (err) {
      console.error("Tyche layer activation failed", err);
      setTycheMessage(err instanceof Error ? err.message : "הפעלת Tyche נכשלה");
    } finally {
      setActivatingTyche(false);
    }
  };

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div
        className="settings-card layers-card"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="שכבות זמינות"
      >
        <header className="settings-header">
          <h2>
            שכבות זמינות
            {layers && <span className="layers-count"> · {layers.length}</span>}
          </h2>
          <button type="button" className="settings-close" onClick={onClose}>
            ✕
          </button>
        </header>

        <input
          className="settings-input"
          placeholder="חיפוש שכבות… (שם, תגיות, תיאור)"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          dir="auto"
        />

        <button
          type="button"
          className="add-layer-toggle"
          onClick={() => setShowAddForm((open) => !open)}
        >
          {showAddForm ? "ביטול" : "+ הוספת שכבה"}
        </button>

        <button type="button" className="add-layer-toggle" onClick={startCubesLayer}>
          + הוספת שכבת Cubes
        </button>

        <button
          type="button"
          className="add-layer-toggle"
          onClick={() => void handleActivateTyche()}
          disabled={activatingTyche}
        >
          {activatingTyche ? "מפעיל שכבת Tyche…" : "+ הפעלת שכבת Tyche"}
        </button>
        {tycheMessage && <p className="settings-message" dir="auto">{tycheMessage}</p>}

        <button
          type="button"
          className="add-layer-toggle"
          onClick={handleBrowseMqs}
        >
          {showMqsBrowser ? "סגירת מאגר MQS" : "בחירת שכבה מ-MQS"}
        </button>
        {mqsMessage && <p className="settings-message" dir="auto">{mqsMessage}</p>}

        {showMqsBrowser && (
          <section className="mqs-browser" aria-label="בחירת שכבת MQS">
            <input className="settings-input" value={mqsSearch} onChange={(e) => setMqsSearch(e.target.value)} placeholder="חיפוש במאגר MQS…" dir="auto" />
            {mqsLayers === null && !mqsMessage && <p className="panel-placeholder">שכבות MQS נטענות…</p>}
            <ul className="mqs-picker-list">
              {filteredMqs.map((layer) => (
                <li key={layer.id}>
                  <button type="button" className="mqs-picker-item" onClick={() => selectMqsLayer(layer)}>
                    <strong dir="auto">{layer.name}</strong>
                    {layer.description && <span dir="auto">{layer.description}</span>}
                    <small dir="auto">{layer.tags.join(" · ")}</small>
                  </button>
                </li>
              ))}
            </ul>
            {mqsLayers !== null && filteredMqs.length === 0 && <p className="panel-placeholder">לא נמצאו שכבות MQS מתאימות.</p>}
          </section>
        )}

        {showAddForm && (
          <section className="add-layer-form" aria-label="הוספת שכבה לקטלוג">
            <h3>הוספת שכבה ל-PostgreSQL</h3>
            <div className="settings-input-row">
              <div>
                <label className="field-label" htmlFor="layer-name">שם</label>
                <input id="layer-name" className="settings-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="בתי ספר" dir="auto" />
              </div>
              <div>
                <label className="field-label" htmlFor="layer-provider">ספק</label>
                <input
                  id="layer-provider"
                  className="settings-input"
                  value={provider}
                  onChange={(e) => {
                    setProvider(e.target.value);
                    setDynamicParameterNames([]);
                    setParameterDefinitions([]);
                    setManualDynamicParameterNames([]);
                    setDynamicParameterOptions({});
                    setDynamicParameterValues({});
                    setRequiresSamplePolygon(false);
                    setCubesSampleBoundary(null);
                    setCubesSampleBoundarySource(null);
                  }}
                  placeholder="mqs"
                  dir="ltr"
                />
              </div>
            </div>
            <label className="field-label" htmlFor="layer-description">תיאור</label>
            <textarea id="layer-description" className="settings-input layer-description-input" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="איזה מידע גיאוגרפי השכבה מכילה" dir="auto" />
            <label className="field-label" htmlFor="layer-tags">תגיות <span className="optional">(Enter או פסיק להוספה)</span></label>
            <div className="tag-editor" onClick={() => document.getElementById("layer-tags")?.focus()}>
              {tags.map((tag) => (
                <span key={tag} className="tag-editor-chip" dir="auto">
                  {tag}
                  <button type="button" onClick={(e) => { e.stopPropagation(); removeTag(tag); }} aria-label={`הסרת התגית ${tag}`}>×</button>
                </span>
              ))}
              <input
                id="layer-tags"
                className="tag-editor-input"
                value={tagDraft}
                onChange={(e) => {
                  const value = e.target.value;
                  if (value.includes(",")) commitTags(value);
                  else setTagDraft(value);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.nativeEvent.isComposing) {
                    e.preventDefault();
                    commitTags(tagDraft);
                  } else if (e.key === "Backspace" && !tagDraft && tags.length > 0) {
                    removeTag(tags[tags.length - 1]);
                  }
                }}
                onBlur={() => commitTags(tagDraft)}
                placeholder={tags.length === 0 ? "חינוך, בית ספר, ילדים" : "תגית נוספת…"}
                dir="auto"
              />
            </div>
            <label className="field-label" htmlFor="layer-source-url">
              {provider.trim().toLowerCase() === "cubes"
                ? "שם Cube / database"
                : provider.trim().toLowerCase() === "tyche"
                  ? "מקור Tyche"
                  : "כתובת המקור"}
            </label>
            <input
              id="layer-source-url"
              className="settings-input"
              value={sourceUrl}
              onChange={(e) => {
                setSourceUrl(e.target.value);
                setRequiresSamplePolygon(false);
                setCubesSampleBoundary(null);
                setCubesSampleBoundarySource(null);
              }}
              placeholder={provider.trim().toLowerCase() === "cubes" ? "transport (or cubes://db/transport)" : provider.trim().toLowerCase() === "tyche" ? "ourforces (or tyche://ourforces)" : "https://provider.example/layer"}
              dir="ltr"
            />
            {provider.trim().toLowerCase() === "cubes" && (
              <fieldset className="cubes-query-mode">
                <legend>מבנה שאילתת זמן וגיאוגרפיה</legend>
                <div className="cubes-query-mode-options">
                  {([
                    ["auto", "אוטומטי", "לפי ה-metadata של ה-Cube"],
                    ["match_not", "match / not", "From/To, TimeBack ו-Location"],
                    ["legacy", "Legacy", "מבנה השעה היחסית הקיים"],
                  ] as const).map(([value, title, detail]) => (
                    <button
                      key={value}
                      type="button"
                      className={cubesQueryMode === value ? "active" : ""}
                      aria-pressed={cubesQueryMode === value}
                      onClick={() => setCubesQueryMode(value)}
                    >
                      <strong dir={value === "auto" ? "rtl" : "ltr"}>{title}</strong>
                      <small>{detail}</small>
                    </button>
                  ))}
                </div>
              </fieldset>
            )}
            {provider.trim().toLowerCase() === "cubes" && (
              <CubesParametersFieldset
                definitions={parameterDefinitions}
                options={dynamicParameterOptions}
                values={dynamicParameterValues}
                loadingParameter={loadingDynamicParameter}
                busy={generatingMetadata}
                sourceConfigured={Boolean(sourceUrl.trim())}
                onAddManual={handleAddDynamicParameter}
                onFetchOptions={(parameterName) => {
                  void handleFetchDynamicOptions(parameterName);
                }}
                onSelect={handleSelectDynamicParameter}
                onChangeValue={(parameterName, value) => {
                  setDynamicParameterValues((current) => ({
                    ...current,
                    [parameterName]: value,
                  }));
                }}
              />
            )}
            {provider.trim().toLowerCase() === "cubes" && requiresSamplePolygon && (
              <fieldset className="cubes-query-mode cubes-sample-polygon">
                <legend>פוליגון לדגימת metadata</legend>
                <div className="cubes-query-mode-options cubes-sample-polygon-options">
                  <button
                    type="button"
                    className={cubesSampleBoundarySource === "drawn" ? "active" : ""}
                    aria-pressed={cubesSampleBoundarySource === "drawn"}
                    disabled={!drawnSampleBoundary || generatingMetadata}
                    onClick={() => {
                      if (drawnSampleBoundary) {
                        handleUseSampleBoundary(drawnSampleBoundary, "drawn");
                      }
                    }}
                  >
                    <strong>שימוש בפוליגון שצויר</strong>
                    <small>{drawnSampleBoundary ? "פוליגון/מלבן הקיים במפה" : "סגרו, ציירו פוליגון ופתחו שוב"}</small>
                  </button>
                  <button
                    type="button"
                    className={cubesSampleBoundarySource === "viewport" ? "active" : ""}
                    aria-pressed={cubesSampleBoundarySource === "viewport"}
                    disabled={generatingMetadata}
                    onClick={() => handleUseSampleBoundary(
                      viewportSampleBoundary, "viewport"
                    )}
                  >
                    <strong>שימוש בתחום התצוגה</strong>
                    <small>האזור שמוצג כרגע במפה</small>
                  </button>
                </div>
              </fieldset>
            )}
            {formMessage && <p className="settings-message">{formMessage}</p>}
            <button
              type="button"
              className="add-layer-toggle"
              onClick={() => void handleGenerateMetadata()}
              disabled={!name.trim() || !provider.trim() || !sourceUrl.trim() || generatingMetadata}
            >
              {generatingMetadata ? "מייצר תיאור ותגיות…" : "✨ יצירת תיאור ותגיות באמצעות AI"}
            </button>
            <button
              type="button"
              className="run-query-button"
              onClick={handleAddLayer}
              disabled={
                !name.trim() || !sourceUrl.trim() || saving ||
                dynamicParameterNames.some((parameterName) => !dynamicParameterValues[parameterName])
              }
            >
              {saving ? "מוסיף…" : "הוספת שכבה"}
            </button>
          </section>
        )}

        {error && <p className="panel-placeholder">⚠️ {error}</p>}
        {layers === null && !error && (
          <p className="panel-placeholder">השכבות נטענות…</p>
        )}

        <ul className="layers-list">
          {filtered.map((layer) => (
            <li key={layer.id} className="layers-item" dir="auto">
              <div className="layers-item-head">
                <span className="layers-item-name">{layer.name}</span>
                {editingLayerId !== layer.id && (
                  <button
                    type="button"
                    className="catalog-edit-button"
                    onClick={() => startEditing(layer)}
                  >
                    עריכה
                  </button>
                )}
              </div>
              {editingLayerId === layer.id ? (
                <div className="catalog-edit-form">
                  <label className="field-label" htmlFor={`edit-name-${layer.id}`}>שם</label>
                  <input
                    id={`edit-name-${layer.id}`}
                    className="settings-input"
                    value={editName}
                    onChange={(event) => setEditName(event.target.value)}
                    dir="auto"
                  />
                  <label className="field-label" htmlFor={`edit-description-${layer.id}`}>תיאור</label>
                  <textarea
                    id={`edit-description-${layer.id}`}
                    className="settings-input layer-description-input"
                    value={editDescription}
                    onChange={(event) => setEditDescription(event.target.value)}
                    dir="auto"
                  />
                  <label className="field-label" htmlFor={`edit-tags-${layer.id}`}>תגיות</label>
                  <div className="tag-editor">
                    {editTags.map((tag) => (
                      <span key={tag} className="tag-editor-chip" dir="auto">
                        {tag}
                        <button
                          type="button"
                          onClick={() => setEditTags((current) => current.filter((item) => item !== tag))}
                          aria-label={`הסרת התגית ${tag}`}
                        >×</button>
                      </span>
                    ))}
                    <input
                      id={`edit-tags-${layer.id}`}
                      className="tag-editor-input"
                      value={editTagDraft}
                      onChange={(event) => {
                        const value = event.target.value;
                        if (value.includes(",")) commitEditTags(value);
                        else setEditTagDraft(value);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" && !event.nativeEvent.isComposing) {
                          event.preventDefault();
                          commitEditTags(editTagDraft);
                        } else if (event.key === "Backspace" && !editTagDraft && editTags.length > 0) {
                          setEditTags((current) => current.slice(0, -1));
                        }
                      }}
                      onBlur={() => commitEditTags(editTagDraft)}
                      placeholder="תגית נוספת…"
                      dir="auto"
                    />
                  </div>
                  {editMessage && <p className="settings-message" dir="auto">{editMessage}</p>}
                  <div className="catalog-edit-actions">
                    <button
                      type="button"
                      className="run-query-button"
                      onClick={() => void handleSaveEdit()}
                      disabled={!editName.trim() || editSaving}
                    >
                      {editSaving ? "שומר…" : "שמירה"}
                    </button>
                    <button
                      type="button"
                      className="catalog-edit-button"
                      onClick={cancelEditing}
                      disabled={editSaving}
                    >
                      ביטול
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  {layer.description && (
                    <p className="layers-item-description">{layer.description}</p>
                  )}
                  <p className="layers-item-tags">{layer.tags.join(" · ")}</p>
                </>
              )}
            </li>
          ))}
          {layers !== null && filtered.length === 0 && (
            <p className="panel-placeholder">לא נמצאו שכבות התואמות ל״{search}״.</p>
          )}
        </ul>
      </div>
    </div>
  );
}
