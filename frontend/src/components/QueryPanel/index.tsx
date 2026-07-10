"use client";

import GeoQueryInput from "@/components/GeoQueryInput";
import GeographyControls from "@/components/GeographyControls";
import RequestPreview from "@/components/RequestPreview";
import ResultsPanel from "@/components/ResultsPanel";
import type {
  GeographyMode,
  GeoQueryRequest,
  GeoQueryResponse,
} from "@/types/geo-query";

interface QueryPanelProps {
  queryText: string;
  onQueryTextChange: (text: string) => void;
  geographyMode: GeographyMode;
  onGeographyModeChange: (mode: GeographyMode) => void;
  hasDrawnGeometry: boolean;
  onRunQuery: () => void;
  isSubmitting: boolean;
  lastRequest: GeoQueryRequest | null;
  lastResponse: GeoQueryResponse | null;
  onOpenSettings: () => void;
}

/** Left-hand panel: query input, geography controls, run button, debug + results. */
export default function QueryPanel({
  queryText,
  onQueryTextChange,
  geographyMode,
  onGeographyModeChange,
  hasDrawnGeometry,
  onRunQuery,
  isSubmitting,
  lastRequest,
  lastResponse,
  onOpenSettings,
}: QueryPanelProps) {
  const canRun = queryText.trim().length > 0 && !isSubmitting;

  return (
    <aside className="query-panel">
      <header className="query-panel-header">
        <div className="header-row">
          <h1>
            Locato<span className="accent">AI</span>
          </h1>
          <button
            type="button"
            className="settings-button"
            onClick={onOpenSettings}
            aria-label="Open settings"
            title="Settings"
          >
            ⚙
          </button>
        </div>
        <p className="tagline">Ask geographic questions in plain language</p>
      </header>

      <div className="query-panel-body">
        <GeoQueryInput
          value={queryText}
          onChange={onQueryTextChange}
          onSubmit={onRunQuery}
        />

        <GeographyControls
          mode={geographyMode}
          onModeChange={onGeographyModeChange}
          hasDrawnGeometry={hasDrawnGeometry}
        />

        <button
          type="button"
          className="run-query-button"
          onClick={onRunQuery}
          disabled={!canRun}
        >
          {isSubmitting ? "Running…" : "Run Query"}
          {!isSubmitting && <kbd>⌘⏎</kbd>}
        </button>

        <ResultsPanel response={lastResponse} />

        <RequestPreview request={lastRequest} response={lastResponse} />
      </div>
    </aside>
  );
}
