"use client";

import { useEffect, useMemo, useState } from "react";
import { getLayers } from "@/services/catalogService";
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
