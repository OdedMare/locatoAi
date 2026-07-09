"use client";

/**
 * Placeholder results panel.
 *
 * FUTURE: this panel will render the spatial results returned by the
 * geo-query backend (feature lists, counts, links to map highlights).
 */
export default function ResultsPanel() {
  return (
    <section className="results-panel">
      <header className="panel-section-header">
        <h2>Results</h2>
      </header>
      <p className="panel-placeholder">
        Results will appear here in the next stage.
      </p>
    </section>
  );
}
