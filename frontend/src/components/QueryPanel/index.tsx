"use client";

import GeoQueryInput from "@/components/GeoQueryInput";
import GeographyControls from "@/components/GeographyControls";
import AgentTrace from "@/components/AgentTrace";
import RequestPreview from "@/components/RequestPreview";
import ResultsPanel from "@/components/ResultsPanel";
import { Layers, Map, MessageSquarePlus, PanelLeft, Settings, Sparkles } from "lucide-react";
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
  onOpenLayers: () => void;
  onNewChat: () => void;
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
  onOpenLayers,
  onNewChat,
}: QueryPanelProps) {
  const canRun = queryText.trim().length > 0 && !isSubmitting;

  return (
    <aside className="query-panel">
      <nav className="chat-sidebar" aria-label="Application navigation">
        <div className="chat-brand">
          <span className="chat-brand-mark"><Map size={18} /></span>
          <span>LocatoAI</span>
          <PanelLeft size={17} className="chat-sidebar-collapse" />
        </div>
        <button type="button" className="new-chat-button" onClick={onNewChat}>
          <MessageSquarePlus size={17} />
          New geo query
        </button>
        <p className="chat-sidebar-label">Today</p>
        {lastRequest && <div className="chat-history-item">{lastRequest.query}</div>}
        <button
          type="button"
          className="chat-settings-button chat-sidebar-bottom"
          onClick={onOpenLayers}
        >
          <Layers size={17} />
          Available layers
        </button>
        <button
          type="button"
          className="chat-settings-button"
          onClick={onOpenSettings}
        >
          <Settings size={17} />
          Settings
        </button>
      </nav>

      <section className="chat-main">
        <header className="query-panel-header">
          <div className="header-row">
            <h1>LocatoAI <span className="model-pill">Geo assistant</span></h1>
          <button
            type="button"
            className="settings-button"
            onClick={onOpenSettings}
            aria-label="Open settings"
            title="Settings"
          >
            <Settings size={18} />
          </button>
          </div>
        </header>

        <div className="query-panel-body">
          {!lastRequest && !isSubmitting ? (
            <div className="chat-welcome">
              <span className="welcome-mark"><Sparkles size={25} /></span>
              <h2>How can I help you explore the map?</h2>
              <p>Ask about places, relationships, distances, or events in natural language.</p>
            </div>
          ) : (
            <div className="chat-conversation">
              {lastRequest && (
                <div className="chat-message user-message" dir="auto">
                  {lastRequest.query}
                </div>
              )}
              <div className="assistant-message">
                <span className="assistant-avatar"><Sparkles size={16} /></span>
                <div className="assistant-content">
                  <AgentTrace
                    response={lastResponse}
                    isSubmitting={isSubmitting}
                    query={lastRequest?.query ?? ""}
                  />
                  {!isSubmitting && lastResponse && <ResultsPanel response={lastResponse} />}
                  {lastRequest && <RequestPreview request={lastRequest} response={lastResponse} />}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="chat-composer-area">
          <div className="composer-tools">
            <GeographyControls
              mode={geographyMode}
              onModeChange={onGeographyModeChange}
              hasDrawnGeometry={hasDrawnGeometry}
            />
          </div>
          <div className="composer-row">
            <GeoQueryInput
              value={queryText}
              onChange={onQueryTextChange}
              onSubmit={onRunQuery}
            />
            <button
              type="button"
              className="run-query-button"
              onClick={onRunQuery}
              disabled={!canRun}
              aria-label="Send query"
            >
              {isSubmitting ? "…" : "↑"}
            </button>
          </div>
          <p className="composer-disclaimer">LocatoAI can make mistakes. Check important geographic results.</p>
        </div>
      </section>
    </aside>
  );
}
