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
  CubesQueryMode,
  RemoteMqsLayer,
} from "@/types/catalog";

interface LayersPanelProps {
  onClose: () => void;
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
export default function LayersPanel({ onClose }: LayersPanelProps) {
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
  const [dynamicParameterOptions, setDynamicParameterOptions] =
    useState<Record<string, CubesAutocompleteOption[]>>({});
  const [dynamicParameterValues, setDynamicParameterValues] =
    useState<Record<string, string>>({});
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
        cubes_dynamic_parameters: dynamicParameterValues,
      });
      setLayers((current) => [...(current ?? []), created]);
      setName("");
      setDescription("");
      setTags([]);
      setTagDraft("");
      setSourceUrl("");
      setCubesQueryMode("auto");
      setDynamicParameterNames([]);
      setDynamicParameterOptions({});
      setDynamicParameterValues({});
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

  const handleGenerateMetadata = async (selected?: RemoteMqsLayer) => {
    const target = {
      name: selected?.name ?? name,
      provider: selected?.provider ?? provider,
      source_url: selected?.source_url ?? sourceUrl,
      cubes_query_mode: cubesQueryMode,
    };
    if (!target.name.trim() || !target.provider.trim() || !target.source_url.trim()) return;
    setGeneratingMetadata(true);
    setFormMessage("דוגם עד 10 ישויות ומייצר תיאור ותגיות…");
    try {
      const generated = await generateLayerMetadata(target);
      setDescription(generated.description);
      setTags(generated.tags);
      setTagDraft("");
      setDynamicParameterNames(generated.dynamic_parameters);
      setDynamicParameterOptions({});
      setDynamicParameterValues({});
      setFormMessage(
        generated.dynamic_parameters.length > 0
          ? `נוצרו הצעות מ-${generated.sample_count} ישויות אקראיות — יש לבחור ערך לכל פרמטר דינמי לפני ההוספה ✓`
          : `נוצרו הצעות מ-${generated.sample_count} ישויות אקראיות — אפשר לערוך לפני ההוספה ✓`
      );
    } catch (err) {
      console.error("Layer metadata generation failed", err);
      setFormMessage(err instanceof Error ? err.message : "יצירת התיאור והתגיות נכשלה");
    } finally {
      setGeneratingMetadata(false);
    }
  };

  const selectMqsLayer = (layer: RemoteMqsLayer) => {
    setName(layer.name);
    setDescription(layer.description);
    setTags(layer.tags);
    setTagDraft("");
    setProvider(layer.provider);
    setSourceUrl(layer.source_url);
    setCubesQueryMode("auto");
    setFormMessage(null);
    setShowAddForm(true);
    setShowMqsBrowser(false);
    void handleGenerateMetadata(layer);
  };

  const startCubesLayer = () => {
    setProvider("cubes");
    setSourceUrl("");
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
                <input id="layer-provider" className="settings-input" value={provider} onChange={(e) => setProvider(e.target.value)} placeholder="mqs" dir="ltr" />
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
            <input id="layer-source-url" className="settings-input" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder={provider.trim().toLowerCase() === "cubes" ? "transport (or cubes://db/transport)" : provider.trim().toLowerCase() === "tyche" ? "ourforces (or tyche://ourforces)" : "https://provider.example/layer"} dir="ltr" />
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
            {formMessage && <p className="settings-message">{formMessage}</p>}
            <button
              type="button"
              className="add-layer-toggle"
              onClick={() => void handleGenerateMetadata()}
              disabled={!name.trim() || !provider.trim() || !sourceUrl.trim() || generatingMetadata}
            >
              {generatingMetadata ? "מייצר תיאור ותגיות…" : "✨ יצירת תיאור ותגיות באמצעות AI"}
            </button>
            <button type="button" className="run-query-button" onClick={handleAddLayer} disabled={!name.trim() || !sourceUrl.trim() || saving}>
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
