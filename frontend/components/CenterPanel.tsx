/**
 * Center Panel — Research findings bullets + report display
 */

'use client';

import React from 'react';
import { useResearchStore, ResearchFinding, Confidence } from '../store/research';

function ConfidenceBadge({ confidence }: { confidence: Confidence }) {
  const map: Record<Confidence, { label: string; cls: string }> = {
    VERIFIED: { label: '✓ Verified', cls: 'badge badge-verified' },
    LIKELY: { label: '~ Likely', cls: 'badge badge-likely' },
    LOW_CONFIDENCE: { label: '? Low', cls: 'badge badge-low' },
  };
  const { label, cls } = map[confidence];
  return <span className={cls}>{label}</span>;
}

function FindingBullet({
  finding,
  isSelected,
  onSelect,
  onOpenSubchat,
}: {
  finding: ResearchFinding;
  isSelected: boolean;
  onSelect: () => void;
  onOpenSubchat: () => void;
}) {
  return (
    <div
      onClick={onSelect}
      style={{
        padding: '14px 16px',
        borderRadius: 'var(--radius-md)',
        border: `1px solid ${isSelected ? 'var(--accent)' : 'var(--border-subtle)'}`,
        background: isSelected ? 'var(--bg-panel-active)' : 'var(--bg-panel)',
        cursor: 'pointer',
        transition: 'all 0.15s',
        marginBottom: 8,
      }}
      onMouseEnter={(e) => {
        if (!isSelected) (e.currentTarget as HTMLDivElement).style.background = 'var(--bg-panel-hover)';
      }}
      onMouseLeave={(e) => {
        if (!isSelected) (e.currentTarget as HTMLDivElement).style.background = 'var(--bg-panel)';
      }}
    >
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
        <p style={{ fontWeight: 600, fontSize: 14, lineHeight: 1.4, flex: 1 }}>
          {finding.headline}
        </p>
        <ConfidenceBadge confidence={finding.confidence} />
      </div>

      {/* Detail (shown when selected) */}
      {isSelected && (
        <p style={{ marginTop: 8, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          {finding.detail}
        </p>
      )}

      {/* Footer row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
        {finding.supporting_sources.length > 0 && (
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
            {finding.supporting_sources.length} source{finding.supporting_sources.length !== 1 ? 's' : ''}
          </span>
        )}
        {finding.related_concepts.length > 0 && (
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {finding.related_concepts.slice(0, 3).map((c) => (
              <span key={c} style={{
                fontSize: 10,
                background: 'var(--bg-secondary)',
                color: 'var(--text-tertiary)',
                padding: '1px 6px',
                borderRadius: 10,
                border: '1px solid var(--border-subtle)',
              }}>
                {c}
              </span>
            ))}
          </div>
        )}
        <button
          onClick={(e) => { e.stopPropagation(); onOpenSubchat(); }}
          style={{
            marginLeft: 'auto',
            fontSize: 11,
            fontWeight: 600,
            color: 'var(--accent)',
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            padding: '2px 6px',
            borderRadius: 'var(--radius-sm)',
          }}
        >
          Explore →
        </button>
      </div>
    </div>
  );
}

export function CenterPanel() {
  const { report, pipelineStatus, selectedFindingId, selectFinding, openSubchat, question } =
    useResearchStore();

  if (pipelineStatus === 'idle') {
    return (
      <main style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexDirection: 'column',
        gap: 12,
        color: 'var(--text-tertiary)',
        padding: '2rem',
      }}>
        <div style={{ fontSize: 48, opacity: 0.3 }}>◎</div>
        <p style={{ fontSize: 16, fontWeight: 500 }}>Enter a research question to begin</p>
        <p style={{ fontSize: 13, textAlign: 'center', maxWidth: 400 }}>
          Nex will autonomously research your topic across multiple sources,
          verify claims, and synthesise a structured research report.
        </p>
      </main>
    );
  }

  if (pipelineStatus === 'queued' || pipelineStatus === 'running') {
    return (
      <main style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexDirection: 'column',
        gap: 16,
        padding: '2rem',
      }}>
        <div style={{
          width: 40,
          height: 40,
          borderRadius: '50%',
          border: '3px solid var(--border-subtle)',
          borderTop: '3px solid var(--accent)',
          animation: 'spin 1s linear infinite',
        }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        <p style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-secondary)' }}>
          Researching...
        </p>
        <p style={{ fontSize: 13, color: 'var(--text-tertiary)', textAlign: 'center', maxWidth: 400 }}>
          "{question}"
        </p>
      </main>
    );
  }

  if (pipelineStatus === 'error') {
    return (
      <main style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
        <div style={{
          background: 'var(--low-confidence-bg)',
          border: '1px solid var(--low-confidence-border)',
          borderRadius: 'var(--radius-md)',
          padding: 20,
          maxWidth: 400,
          textAlign: 'center',
        }}>
          <p style={{ fontWeight: 700, color: 'var(--low-confidence)', marginBottom: 8 }}>Research Failed</p>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
            An error occurred during the research pipeline. Please try again.
          </p>
        </div>
      </main>
    );
  }

  if (!report) return null;

  return (
    <main style={{
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Report header */}
      <div style={{
        padding: '16px 24px',
        borderBottom: '1px solid var(--border-subtle)',
        background: 'var(--bg-panel)',
        flexShrink: 0,
      }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.02em', marginBottom: 4 }}>
          {report.title}
        </h1>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
            {report.total_sources_analyzed} sources · {report.depth} research
          </span>
          <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
            {new Date(report.generated_at).toLocaleString()}
          </span>
        </div>
      </div>

      {/* Scrollable content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
        {/* Executive summary */}
        <section style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>
            Executive Summary
          </h2>
          <p style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--text-primary)' }}>
            {report.executive_summary}
          </p>
        </section>

        {/* Key findings */}
        <section>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <h2 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Key Findings
            </h2>
            <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
              Click a finding to explore evidence
            </span>
          </div>

          {report.key_findings.map((finding) => (
            <FindingBullet
              key={finding.id}
              finding={finding}
              isSelected={selectedFindingId === finding.id}
              onSelect={() => selectFinding(finding.id)}
              onOpenSubchat={() => openSubchat(finding.id)}
            />
          ))}
        </section>

        {/* Evidence sections */}
        {report.evidence_sections.length > 0 && (
          <section style={{ marginTop: 32 }}>
            <h2 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 16 }}>
              Evidence Analysis
            </h2>
            {report.evidence_sections.map((section, i) => (
              <div key={i} style={{ marginBottom: 20 }}>
                <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>{section.title}</h3>
                <div className="prose" style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
                  {section.content.split('\n').map((para, j) =>
                    para.trim() ? <p key={j}>{para}</p> : null
                  )}
                </div>
              </div>
            ))}
          </section>
        )}

        {/* Limitations */}
        {report.limitations && (
          <section style={{ marginTop: 24 }}>
            <h2 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
              Limitations
            </h2>
            <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              {report.limitations}
            </p>
          </section>
        )}

        {/* Future research */}
        {report.future_research.length > 0 && (
          <section style={{ marginTop: 24, marginBottom: 40 }}>
            <h2 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
              Future Research
            </h2>
            <ul style={{ paddingLeft: 16, fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
              {report.future_research.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </main>
  );
}
