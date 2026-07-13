"use client";

import { useEffect, useMemo, useState } from "react";
import { createLayer, getLayers, getMqsLayers } from "@/services/catalogService";
import type { CatalogLayer, RemoteMqsLayer } from "@/types/catalog";

interface LayersPanelProps {
  onClose: () => void;
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
  const [provider, setProvider] = useState("arcgis");
  const [sourceUrl, setSourceUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [formMessage, setFormMessage] = useState<string | null>(null);
  const [showMqsBrowser, setShowMqsBrowser] = useState(false);
  const [mqsLayers, setMqsLayers] = useState<RemoteMqsLayer[] | null>(null);
  const [mqsSearch, setMqsSearch] = useState("");
  const [mqsMessage, setMqsMessage] = useState<string | null>(null);

  useEffect(() => {
    getLayers()
      .then((data) => setLayers(data.layers))
      .catch(() => setError("לא ניתן לטעון שכבות — האם השרת פועל?"));
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
    const additions = value
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean);
    if (additions.length === 0) return;
    setTags((current) => {
      const seen = new Set(current.map((tag) => tag.toLocaleLowerCase()));
      const unique = additions.filter((tag) => {
        const key = tag.toLocaleLowerCase();
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
      return [...current, ...unique].slice(0, 20);
    });
    setTagDraft("");
  };

  const removeTag = (tagToRemove: string) => {
    setTags((current) => current.filter((tag) => tag !== tagToRemove));
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
      });
      setLayers((current) => [...(current ?? []), created]);
      setName("");
      setDescription("");
      setTags([]);
      setTagDraft("");
      setSourceUrl("");
      setFormMessage("השכבה נוספה ל-PostgreSQL ✓");
    } catch (err) {
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
      setMqsMessage(err instanceof Error ? err.message : "טעינת שכבות MQS נכשלה");
    }
  };

  const selectMqsLayer = (layer: RemoteMqsLayer) => {
    setName(layer.name);
    setDescription(layer.description);
    setTags(layer.tags);
    setTagDraft("");
    setProvider(layer.provider);
    setSourceUrl(layer.source_url);
    setFormMessage(null);
    setShowAddForm(true);
    setShowMqsBrowser(false);
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
                <input id="layer-provider" className="settings-input" value={provider} onChange={(e) => setProvider(e.target.value)} placeholder="arcgis" dir="ltr" />
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
            <label className="field-label" htmlFor="layer-source-url">כתובת המקור</label>
            <input id="layer-source-url" className="settings-input" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder="https://provider.example/layer" dir="ltr" />
            {formMessage && <p className="settings-message">{formMessage}</p>}
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
              </div>
              {layer.description && (
                <p className="layers-item-description">{layer.description}</p>
              )}
              <p className="layers-item-tags">{layer.tags.join(" · ")}</p>
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
