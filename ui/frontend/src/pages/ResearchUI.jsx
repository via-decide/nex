import React, { useState, useRef, useCallback } from "react";
import SearchBar from "../components/SearchBar";
import PipelineProgress from "../components/PipelineProgress";
import AnswerPanel from "../components/AnswerPanel";
import FindingsPanel from "../components/FindingsPanel";
import SourcesPanel from "../components/SourcesPanel";
import FollowUpChat from "../components/FollowUpChat";
import DevPanel from "../components/DevPanel";

const STAGES = [
  "planning",
  "discovery",
  "collection",
  "verification",
  "knowledge_graph",
  "synthesis",
];

export default function ResearchUI({ researchMode, devMode }) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [events, setEvents] = useState([]);
  const [activeStage, setActiveStage] = useState(null);
  const [completedStages, setCompletedStages] = useState([]);
  const abortRef = useRef(null);

  const handleSearch = useCallback(
    async (searchQuery) => {
      const q = searchQuery || query;
      if (!q.trim() || loading) return;

      setLoading(true);
      setResult(null);
      setError(null);
      setEvents([]);
      setActiveStage(null);
      setCompletedStages([]);

      try {
        const params = new URLSearchParams({
          q: q.trim(),
          depth: "standard",
          research_mode: researchMode.toString(),
        });

        const response = await fetch(`/query/stream?${params}`);
        if (!response.ok) {
          throw new Error(`Server error: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === "event") {
                setEvents((prev) => [...prev, data]);
                if (data.status === "started") {
                  setActiveStage(data.stage);
                } else if (data.status === "completed") {
                  setCompletedStages((prev) => [...prev, data.stage]);
                  setActiveStage(null);
                }
              } else if (data.type === "result") {
                setResult(data);
              } else if (data.type === "error") {
                setError(data.message);
              }
            } catch {
              // skip malformed JSON
            }
          }
        }
      } catch (err) {
        if (err.name !== "AbortError") {
          setError(err.message);
          // Fallback: try synchronous /query endpoint
          try {
            const res = await fetch("/query", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                query: q.trim(),
                depth: "standard",
                research_mode: researchMode,
                source_types: researchMode
                  ? ["wikipedia", "arxiv", "semanticscholar"]
                  : ["wikipedia"],
              }),
            });
            const data = await res.json();
            if (data.status === "completed") {
              setResult({
                run_id: data.run_id,
                answer: data.answer,
                sources: data.sources,
                findings: data.findings,
                stats: data.stats,
              });
              setError(null);
              setCompletedStages(STAGES);
            } else if (data.error) {
              setError(data.error);
            }
          } catch (fallbackErr) {
            setError(fallbackErr.message);
          }
        }
      } finally {
        setLoading(false);
        setActiveStage(null);
      }
    },
    [query, loading, researchMode]
  );

  const hasResult = result !== null;

  return (
    <>
      <div className={`search-section ${hasResult ? "compact" : ""}`}>
        <SearchBar
          value={query}
          onChange={setQuery}
          onSubmit={handleSearch}
          loading={loading}
          compact={hasResult}
        />
      </div>

      {(loading || events.length > 0) && (
        <PipelineProgress
          stages={STAGES}
          activeStage={activeStage}
          completedStages={completedStages}
          events={events}
        />
      )}

      {error && !result && (
        <div className="answer-section" style={{ borderColor: "var(--accent-red)" }}>
          <div className="answer-label" style={{ color: "var(--text-error)" }}>
            Error
          </div>
          <div className="answer-text" style={{ color: "var(--text-error)" }}>
            {error}
          </div>
        </div>
      )}

      {result && (
        <div className="result-panel">
          {result.stats && (
            <div className="stats-bar">
              <div className="stat-item">
                Sources <span className="stat-value">{result.stats.sources_discovered ?? 0}</span>
              </div>
              <div className="stat-item">
                Evidence <span className="stat-value">{result.stats.evidence_items ?? 0}</span>
              </div>
              <div className="stat-item">
                Verified <span className="stat-value">{result.stats.verified_claims ?? 0}</span>
              </div>
              <div className="stat-item">
                Findings <span className="stat-value">{result.stats.findings_count ?? 0}</span>
              </div>
            </div>
          )}

          <AnswerPanel answer={result.answer} title={result.title} />

          {result.findings && result.findings.length > 0 && (
            <FindingsPanel findings={result.findings} />
          )}

          {result.sources && result.sources.length > 0 && (
            <SourcesPanel sources={result.sources} />
          )}

          <FollowUpChat runId={result.run_id} findings={result.findings} />

          {devMode && (
            <DevPanel result={result} events={events} />
          )}
        </div>
      )}

      {!loading && !result && !error && (
        <div className="empty-state">
          <div className="empty-state-icon">N</div>
          <div className="empty-state-title">Ask Nex anything</div>
          <div className="empty-state-text">
            Nex runs a deep research pipeline — discovering sources, extracting
            evidence, verifying claims, and synthesizing a report with full
            citations.
          </div>
        </div>
      )}
    </>
  );
}
