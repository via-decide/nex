import React, { useState } from "react";

export default function SourcesPanel({ sources }) {
  const [expanded, setExpanded] = useState({});
  const [showAll, setShowAll] = useState(false);

  const toggle = (i) => {
    setExpanded((prev) => ({ ...prev, [i]: !prev[i] }));
  };

  const visible = showAll ? sources : sources.slice(0, 8);

  return (
    <div className="sources-section">
      <div className="sources-header">
        Sources ({sources.length})
      </div>

      {visible.map((s, i) => {
        const isExpanded = expanded[i];
        return (
          <div
            key={i}
            className={`source-card ${isExpanded ? "expanded" : ""}`}
            onClick={() => toggle(i)}
          >
            <div className="source-top">
              <span className="source-title">{s.title || "Untitled"}</span>
              <span className="source-type">{s.source_type || "web"}</span>
              <span className="source-score">
                {(s.relevance_score * 100).toFixed(0)}%
              </span>
            </div>

            {isExpanded && (
              <>
                {s.snippet && (
                  <div className="source-snippet">{s.snippet}</div>
                )}
                {s.url && <div className="source-url">{s.url}</div>}
              </>
            )}
          </div>
        );
      })}

      {sources.length > 8 && (
        <button
          className="search-example"
          style={{ marginTop: 8 }}
          onClick={() => setShowAll((v) => !v)}
        >
          {showAll ? "Show fewer" : `Show all ${sources.length} sources`}
        </button>
      )}
    </div>
  );
}
