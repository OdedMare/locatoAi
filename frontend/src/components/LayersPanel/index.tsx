"use client";

import { useEffect, useMemo, useState } from "react";
import { createLayer, getLayers } from "@/services/catalogService";
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
  const [tags, setTags] = useState("");
  const [provider, setProvider] = useState("arcgis");
  const [sourceUrl, setSourceUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [formMessage, setFormMessage] = useState<string | null>(null);

  useEffect(() => {
    getLayers()
      .then((data) => setLayers(data.layers))
      .catch(() => setError("Could not load layers — is the backend running?"));
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

  const handleAddLayer = async () => {
    if (!name.trim() || !sourceUrl.trim() || saving) return;
    setSaving(true);
    setFormMessage(null);
    try {
      const created = await createLayer({
        name: name.trim(),
        description: description.trim(),
        tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean),
        provider: provider.trim(),
        source_url: sourceUrl.trim(),
      });
      setLayers((current) => [...(current ?? []), created]);
      setName("");
      setDescription("");
      setTags("");
      setSourceUrl("");
      setFormMessage("Layer added to PostgreSQL ✓");
    } catch (err) {
      setFormMessage(err instanceof Error ? err.message : "Could not add layer");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div
        className="settings-card layers-card"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Available layers"
      >
        <header className="settings-header">
          <h2>
            Available layers
            {layers && <span className="layers-count"> · {layers.length}</span>}
          </h2>
          <button type="button" className="settings-close" onClick={onClose}>
            ✕
          </button>
        </header>

        <input
          className="settings-input"
          placeholder="Search layers… (name, tags, description)"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          dir="auto"
        />

        <button
          type="button"
          className="add-layer-toggle"
          onClick={() => setShowAddForm((open) => !open)}
        >
          {showAddForm ? "Cancel" : "+ Add layer"}
        </button>

        {showAddForm && (
          <section className="add-layer-form" aria-label="Add a catalog layer">
            <h3>Add layer to PostgreSQL</h3>
            <div className="settings-input-row">
              <div>
                <label className="field-label" htmlFor="layer-name">Name</label>
                <input id="layer-name" className="settings-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Schools" dir="auto" />
              </div>
              <div>
                <label className="field-label" htmlFor="layer-provider">Provider</label>
                <input id="layer-provider" className="settings-input" value={provider} onChange={(e) => setProvider(e.target.value)} placeholder="arcgis" />
              </div>
            </div>
            <label className="field-label" htmlFor="layer-description">Description</label>
            <textarea id="layer-description" className="settings-input layer-description-input" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What geographic data this layer contains" dir="auto" />
            <label className="field-label" htmlFor="layer-tags">Tags <span className="optional">(comma-separated)</span></label>
            <input id="layer-tags" className="settings-input" value={tags} onChange={(e) => setTags(e.target.value)} placeholder="education, school, children" dir="auto" />
            <label className="field-label" htmlFor="layer-source-url">Source URL</label>
            <input id="layer-source-url" className="settings-input" value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder="https://provider.example/layer" />
            {formMessage && <p className="settings-message">{formMessage}</p>}
            <button type="button" className="run-query-button" onClick={handleAddLayer} disabled={!name.trim() || !sourceUrl.trim() || saving}>
              {saving ? "Adding…" : "Add layer"}
            </button>
          </section>
        )}

        {error && <p className="panel-placeholder">⚠️ {error}</p>}
        {layers === null && !error && (
          <p className="panel-placeholder">Loading layers…</p>
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
            <p className="panel-placeholder">No layers match “{search}”.</p>
          )}
        </ul>
      </div>
    </div>
  );
}
