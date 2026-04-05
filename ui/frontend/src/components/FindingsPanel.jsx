import React, { useState } from "react";

export default function FindingsPanel({ findings }) {
  const [expanded, setExpanded] = useState({});

  const toggle = (id) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const confidenceClass = (c) => {
    if (!c) return "";
    const lower = c.toLowerCase();
    if (lower === "verified" || lower === "high") return "verified";
    if (lower === "likely" || lower === "medium") return "likely";
    return "low";
  };

  return (
    <div className="findings-section">
      <div className="findings-header">
        Key Findings ({findings.length})
      </div>

      {findings.map((f) => {
        const isExpanded = expanded[f.id];
        return (
          <div
            key={f.id}
            className={`finding-card ${isExpanded ? "expanded" : ""}`}
            onClick={() => toggle(f.id)}
          >
            <div className="finding-headline">
              <span>{f.headline}</span>
              {f.confidence && (
                <span
                  className={`finding-confidence ${confidenceClass(f.confidence)}`}
                >
                  {f.confidence}
                </span>
              )}
            </div>

            {isExpanded && (
              <>
                <div className="finding-detail">{f.detail}</div>
                {f.related_concepts && f.related_concepts.length > 0 && (
                  <div className="finding-meta">
                    {f.related_concepts.map((c) => (
                      <span key={c} className="finding-concept">
                        {c}
                      </span>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}
