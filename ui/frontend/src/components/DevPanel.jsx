import React, { useState } from "react";

export default function DevPanel({ result, events }) {
  const [section, setSection] = useState("stats");

  return (
    <div className="dev-panel">
      <div className="dev-panel-header">Developer Mode</div>

      <div className="nav-tabs" style={{ marginBottom: 12 }}>
        <button
          className={`nav-tab ${section === "stats" ? "active" : ""}`}
          onClick={() => setSection("stats")}
        >
          Stats
        </button>
        <button
          className={`nav-tab ${section === "events" ? "active" : ""}`}
          onClick={() => setSection("events")}
        >
          Pipeline Events
        </button>
        <button
          className={`nav-tab ${section === "sources" ? "active" : ""}`}
          onClick={() => setSection("sources")}
        >
          Raw Sources
        </button>
        <button
          className={`nav-tab ${section === "findings" ? "active" : ""}`}
          onClick={() => setSection("findings")}
        >
          Raw Findings
        </button>
        <button
          className={`nav-tab ${section === "graph" ? "active" : ""}`}
          onClick={() => setSection("graph")}
        >
          Knowledge Graph
        </button>
      </div>

      {section === "stats" && (
        <div className="dev-section">
          <div className="dev-section-title">Search Diagnostics</div>
          <div className="dev-json">
            {JSON.stringify(result.stats || {}, null, 2)}
          </div>
        </div>
      )}

      {section === "events" && (
        <div className="dev-section">
          <div className="dev-section-title">Pipeline Events ({events.length})</div>
          <div className="dev-json">
            {JSON.stringify(events, null, 2)}
          </div>
        </div>
      )}

      {section === "sources" && (
        <div className="dev-section">
          <div className="dev-section-title">
            Raw Sources ({result.sources?.length || 0})
          </div>
          <div className="dev-json">
            {JSON.stringify(
              (result.sources || []).map((s) => ({
                title: s.title,
                type: s.source_type,
                score: s.relevance_score,
                url: s.url,
              })),
              null,
              2
            )}
          </div>
        </div>
      )}

      {section === "findings" && (
        <div className="dev-section">
          <div className="dev-section-title">
            Raw Findings ({result.findings?.length || 0})
          </div>
          <div className="dev-json">
            {JSON.stringify(result.findings || [], null, 2)}
          </div>
        </div>
      )}

      {section === "graph" && (
        <div className="dev-section">
          <div className="dev-section-title">Knowledge Graph Data</div>
          <div className="dev-json">
            {JSON.stringify(result.knowledge_graph || {}, null, 2)}
          </div>
        </div>
      )}
    </div>
  );
}
