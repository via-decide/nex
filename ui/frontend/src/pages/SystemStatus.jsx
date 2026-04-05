import React, { useState, useEffect } from "react";

export default function SystemStatus() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchStatus() {
      try {
        const res = await fetch("/status");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!cancelled) {
          setStatus(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (loading) {
    return (
      <div className="status-page">
        <div className="status-header">System Status</div>
        <div style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>
          <span className="loading-spinner" style={{ marginRight: 8 }} />
          Loading status...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="status-page">
        <div className="status-header">System Status</div>
        <div className="answer-section" style={{ borderColor: "var(--accent-red)" }}>
          <div className="answer-label" style={{ color: "var(--text-error)" }}>
            Connection Error
          </div>
          <div className="answer-text" style={{ color: "var(--text-error)" }}>
            Cannot reach Nex backend at localhost:8000. Make sure the server is
            running: <code>python ui/backend_api/server.py</code>
          </div>
        </div>
      </div>
    );
  }

  const corpus = status.corpus || {};
  const caps = status.capabilities || {};

  return (
    <div className="status-page">
      <div className="status-header">Corpus Status Dashboard</div>

      <div className="status-grid">
        <div className="status-card">
          <div className="status-card-label">Engine Status</div>
          <div
            className="status-card-value"
            style={{
              color:
                status.status === "online"
                  ? "var(--text-success)"
                  : "var(--text-error)",
            }}
          >
            {status.status === "online" ? "Online" : "Offline"}
          </div>
          <div className="status-card-note">v{status.version}</div>
        </div>

        <div className="status-card">
          <div className="status-card-label">Books Indexed</div>
          <div className="status-card-value">{corpus.books_indexed ?? 0}</div>
        </div>

        <div className="status-card">
          <div className="status-card-label">Chunks Generated</div>
          <div className="status-card-value">
            {corpus.chunks_generated ?? 0}
          </div>
        </div>

        <div className="status-card">
          <div className="status-card-label">Vector Indexes</div>
          <div className="status-card-value">
            {corpus.vector_indexes_loaded ?? 0}
          </div>
        </div>

        <div className="status-card">
          <div className="status-card-label">Packs Processed</div>
          <div className="status-card-value">
            {corpus.packs_processed ?? 0}
          </div>
        </div>

        <div className="status-card">
          <div className="status-card-label">Active Runs</div>
          <div className="status-card-value">{status.active_runs ?? 0}</div>
        </div>

        <div className="status-card">
          <div className="status-card-label">Completed Runs</div>
          <div className="status-card-value">{status.completed_runs ?? 0}</div>
        </div>
      </div>

      <div style={{ marginBottom: 24 }}>
        <div
          className="sources-header"
          style={{ marginTop: 8 }}
        >
          Capabilities
        </div>
        <div
          className="answer-section"
          style={{ padding: 16 }}
        >
          <CapRow label="Wikipedia" online={caps.wikipedia} />
          <CapRow label="arXiv" online={caps.arxiv} />
          <CapRow label="Semantic Scholar" online={caps.semantic_scholar} />
          <CapRow label="Zayvora Tools" online={caps.zayvora} />
          <CapRow label="Local Corpus" online={caps.local_corpus} />
        </div>
      </div>

      {corpus.note && (
        <div
          style={{
            fontSize: "0.8rem",
            color: "var(--text-tertiary)",
            fontStyle: "italic",
          }}
        >
          {corpus.note}
        </div>
      )}
    </div>
  );
}

function CapRow({ label, online }) {
  return (
    <div className="status-capability">
      <div className={`status-dot ${online ? "online" : "offline"}`} />
      <span>{label}</span>
      <span
        style={{
          marginLeft: "auto",
          fontSize: "0.75rem",
          fontFamily: "var(--font-mono)",
          color: online ? "var(--text-success)" : "var(--text-tertiary)",
        }}
      >
        {online ? "available" : "unavailable"}
      </span>
    </div>
  );
}
