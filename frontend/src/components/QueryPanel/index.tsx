"use client";

import GeoQueryInput from "@/components/GeoQueryInput";
import GeographyControls from "@/components/GeographyControls";
import AgentTrace from "@/components/AgentTrace";
import RequestPreview from "@/components/RequestPreview";
import ResultsPanel from "@/components/ResultsPanel";
import {
  Activity, ArrowUp, Bot, Clock3, Layers, LoaderCircle, MessageSquarePlus, Moon,
  Radar, Settings, Sparkles, Sun,
} from "lucide-react";
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
  lastDisplayQuery: string;
  history: Array<{
    request: GeoQueryRequest;
    response: GeoQueryResponse;
    displayQuery: string;
  }>;
  onOpenSettings: () => void;
  onOpenLayers: () => void;
  onOpenAgentStudio: () => void;
  onNewChat: () => void;
  isDarkMode: boolean;
  onToggleTheme: () => void;
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
  lastDisplayQuery,
  history,
  onOpenSettings,
  onOpenLayers,
  onOpenAgentStudio,
  onNewChat,
  isDarkMode,
  onToggleTheme,
}: QueryPanelProps) {
  const needsDrawing = geographyMode === "polygon" || geographyMode === "rectangle";
  const canRun =
    queryText.trim().length > 0 &&
    !isSubmitting &&
    (!needsDrawing || hasDrawnGeometry);

  return (
    <aside className="query-panel">
      <nav className="chat-sidebar" aria-label="ניווט באפליקציה">
        <div className="chat-brand">
          <span className="chat-brand-mark"><Radar size={18} /></span>
          <span>LOCATO<span className="brand-ai">AI</span></span>
        </div>
        <div className="workspace-chip"><span /> מרחב מבצעי חי</div>
        <button type="button" className="new-chat-button" onClick={onNewChat}>
          <MessageSquarePlus size={17} />
          שאילתה חדשה
        </button>
        <p className="chat-sidebar-label">היום</p>
        {history.slice(-4).map((turn, index) => (
          <div key={`${turn.displayQuery}-${index}`} className="chat-history-item">
            {turn.displayQuery}
          </div>
        ))}
        {lastRequest && <div className="chat-history-item active">{lastDisplayQuery}</div>}
        <button
          type="button"
          className="chat-settings-button chat-sidebar-bottom"
          onClick={onOpenAgentStudio}
        >
          <Bot size={17} />
          Agent Studio
        </button>
        <button
          type="button"
          className="chat-settings-button"
          onClick={onOpenLayers}
        >
          <Layers size={17} />
          שכבות זמינות
        </button>
        <button
          type="button"
          className="chat-settings-button"
          onClick={onToggleTheme}
          aria-label={isDarkMode ? "מעבר למצב בהיר" : "מעבר למצב כהה"}
          title={isDarkMode ? "מצב בהיר" : "מצב כהה"}
        >
          {isDarkMode ? <Sun size={17} /> : <Moon size={17} />}
          {isDarkMode ? "מצב בהיר" : "מצב כהה"}
        </button>
        <button
          type="button"
          className="chat-settings-button"
          onClick={onOpenSettings}
        >
          <Settings size={17} />
          הגדרות
        </button>
      </nav>

      <section className="chat-main" aria-busy={isSubmitting}>
        <header className="query-panel-header">
          <div className="header-row">
            <div>
              <h1>מרכז חקירה <span className="model-pill"><Activity size={10} /> LIVE</span></h1>
              <p className="header-context">מודיעין גיאוגרפי מבוסס סוכן</p>
            </div>
            <div className="header-actions">
              <div className="mobile-header-actions">
                <button type="button" onClick={onOpenAgentStudio} aria-label="פתיחת Agent Studio" title="Agent Studio">
                  <Bot size={18} />
                </button>
                <button type="button" onClick={onOpenLayers} aria-label="פתיחת שכבות זמינות" title="שכבות זמינות">
                  <Layers size={18} />
                </button>
                <button
                  type="button"
                  onClick={onToggleTheme}
                  aria-label={isDarkMode ? "מעבר למצב בהיר" : "מעבר למצב כהה"}
                  title={isDarkMode ? "מצב בהיר" : "מצב כהה"}
                >
                  {isDarkMode ? <Sun size={18} /> : <Moon size={18} />}
                </button>
              </div>
              <button
                type="button"
                className="settings-button"
                onClick={onOpenSettings}
                aria-label="פתיחת הגדרות"
                title="הגדרות"
              >
                <Settings size={18} />
              </button>
            </div>
          </div>
        </header>

        <div className="query-panel-body">
          {!lastRequest && !isSubmitting ? (
            <div className="chat-welcome">
              <div className="welcome-visual">
                <span className="welcome-orbit orbit-one" />
                <span className="welcome-orbit orbit-two" />
                <span className="welcome-mark"><Radar size={27} /></span>
              </div>
              <span className="welcome-eyebrow"><Sparkles size={12} /> GEO AGENT ONLINE</span>
              <h2>מה תרצו לגלות על המרחב?</h2>
              <p>חברו בין מיקומים, זמן ותנועה. הסוכן יבחר שכבות, יבנה תוכנית ויציג את התוצאה על המפה.</p>
              <div className="capability-strip">
                <span><Radar size={12} /> ניתוח מרחבי</span>
                <span><Clock3 size={12} /> נתוני זמן אמת</span>
                <span><Layers size={12} /> מקורות מרובים</span>
              </div>
            </div>
          ) : (
            <div className="chat-conversation">
              {history.map((turn, index) => (
                <div className="chat-turn" key={`${turn.displayQuery}-${index}`}>
                  <div className="chat-message user-message" dir="auto">{turn.displayQuery}</div>
                  <div className="assistant-message compact-turn">
                    <span className="assistant-avatar"><Sparkles size={14} /></span>
                    <div className="assistant-content">
                      <ResultsPanel response={turn.response} />
                    </div>
                  </div>
                </div>
              ))}
              {lastRequest && (
                <div className="chat-message user-message" dir="auto">
                  {lastDisplayQuery}
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
              aria-label="שליחת שאילתה"
            >
              {isSubmitting
                ? <LoaderCircle className="submit-spinner" size={18} />
                : <ArrowUp size={18} />}
            </button>
          </div>
          <p className="composer-disclaimer">LocatoAI עלול לטעות. מומלץ לבדוק תוצאות גיאוגרפיות חשובות.</p>
        </div>
      </section>
    </aside>
  );
}
