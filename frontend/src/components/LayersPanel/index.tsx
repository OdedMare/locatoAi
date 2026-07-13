"use client";

import { useEffect, useMemo, useState } from "react";
import { createLayer, getLayers, syncMqsLayers } from "@/services/catalogService";
import type { CatalogLayer } from "@/types/catalog";

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
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

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

  const handleSyncMqs = async () => {
    if (syncing) return;
    setSyncing(true);
    setSyncMessage(null);
    try {
      const result = await syncMqsLayers();
      const refreshed = await getLayers();
      setLayers(refreshed.layers);
      setSyncMessage(
        `סונכרן ✓ — נוספו ${result.added}, עודכנו ${result.updated}` +
          (result.skipped ? `, דולגו ${result.skipped}` : "")
      );
    } catch (err) {
      setSyncMessage(err instanceof Error ? err.message : "סנכרון שכבות MQS נכשל");
    } finally {
      setSyncing(false);
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

        <button
          type="button"
          className="add-layer-toggle"
          onClick={handleSyncMqs}
          disabled={syncing}
        >
          {syncing ? "מסנכרן…" : "סנכרון שכבות MQS"}
        </button>
        {syncMessage && <p className="settings-message" dir="auto">{syncMessage}</p>}

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
