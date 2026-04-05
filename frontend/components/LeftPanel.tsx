/**
 * Left Panel — Research question input + constraint selection
 */

'use client';

import React, { useState } from 'react';
import { useResearchStore } from '../store/research';

const DEPTH_OPTIONS = [
  { value: 'standard', label: 'Standard', desc: '10–30 sources, ~45s' },
  { value: 'deep', label: 'Deep', desc: '30–60 sources, ~90s' },
  { value: 'exhaustive', label: 'Exhaustive', desc: '60–100 sources, ~2min' },
] as const;

const SOURCE_TYPE_OPTIONS = [
  { value: 'wikipedia', label: 'Wikipedia' },
  { value: 'arxiv', label: 'arXiv / Academic' },
  { value: 'semanticscholar', label: 'Semantic Scholar' },
];

export function LeftPanel() {
  const {
    question, setQuestion, config, setConfig,
    startResearch, pipelineStatus, isSubmitting, pipelineEvents, pipelineStats,
    reset,
  } = useResearchStore();

  const [localQuestion, setLocalQuestion] = useState(question);
  const isRunning = pipelineStatus === 'running' || pipelineStatus === 'queued' || isSubmitting;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!localQuestion.trim() || isRunning) return;
    setQuestion(localQuestion.trim());
    startResearch(localQuestion.trim());
  };

  const toggleSourceType = (type: string) => {
    const types = config.sourceTypes.includes(type)
      ? config.sourceTypes.filter((t) => t !== type)
      : [...config.sourceTypes, type];
    setConfig({ sourceTypes: types.length ? types : config.sourceTypes });
  };

  return (
    <aside
      style={{
        width: 'var(--left-panel-width)',
        flexShrink: 0,
        background: 'var(--bg-panel)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div style={{ padding: '16px var(--panel-padding)', borderBottom: '1px solid var(--border-subtle)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <span style={{ fontSize: 18 }}>◎</span>
          <span style={{ fontWeight: 700, fontSize: 16, letterSpacing: '-0.02em' }}>Nex</span>
          <span style={{
            fontSize: 10, fontWeight: 600, letterSpacing: '0.06em',
            color: 'var(--text-tertiary)', textTransform: 'uppercase', marginLeft: 2,
          }}>
            Deep Research
          </span>
        </div>
        <p style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
          Autonomous multi-source research engine
        </p>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 'var(--panel-padding)' }}>
        <form onSubmit={handleSubmit}>
          {/* Question */}
          <label style={{ display: 'block', marginBottom: 6 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>
              RESEARCH QUESTION
            </span>
          </label>
          <textarea
            value={localQuestion}
            onChange={(e) => setLocalQuestion(e.target.value)}
            placeholder="What would you like to research?"
            disabled={isRunning}
            rows={4}
            style={{
              width: '100%',
              padding: '10px 12px',
              border: '1px solid var(--border-medium)',
              borderRadius: 'var(--radius-md)',
              fontFamily: 'var(--font-sans)',
              fontSize: 14,
              lineHeight: 1.5,
              resize: 'none',
              background: isRunning ? 'var(--bg-secondary)' : 'white',
              color: 'var(--text-primary)',
              outline: 'none',
              transition: 'border-color 0.15s',
            }}
            onFocus={(e) => { e.target.style.borderColor = 'var(--accent)'; }}
            onBlur={(e) => { e.target.style.borderColor = 'var(--border-medium)'; }}
          />

          {/* Depth */}
          <div style={{ marginTop: 16 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 8 }}>
              RESEARCH DEPTH
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {DEPTH_OPTIONS.map((opt) => (
                <label
                  key={opt.value}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    cursor: 'pointer',
                    padding: '8px 10px',
                    borderRadius: 'var(--radius-sm)',
                    border: `1px solid ${config.depth === opt.value ? 'var(--accent)' : 'var(--border-subtle)'}`,
                    background: config.depth === opt.value ? 'var(--accent-light)' : 'transparent',
                    transition: 'all 0.15s',
                  }}
                >
                  <input
                    type="radio"
                    name="depth"
                    value={opt.value}
                    checked={config.depth === opt.value}
                    onChange={() => setConfig({ depth: opt.value })}
                    style={{ accentColor: 'var(--accent)' }}
                    disabled={isRunning}
                  />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{opt.label}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{opt.desc}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Source types */}
          <div style={{ marginTop: 16 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 8 }}>
              SOURCE TYPES
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {SOURCE_TYPE_OPTIONS.map((opt) => (
                <label key={opt.value} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13 }}>
                  <input
                    type="checkbox"
                    checked={config.sourceTypes.includes(opt.value)}
                    onChange={() => toggleSourceType(opt.value)}
                    style={{ accentColor: 'var(--accent)' }}
                    disabled={isRunning}
                  />
                  {opt.label}
                </label>
              ))}
            </div>
          </div>

          {/* Zayvora toggle */}
          <div style={{ marginTop: 16 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13 }}>
              <input
                type="checkbox"
                checked={config.enableZayvora}
                onChange={(e) => setConfig({ enableZayvora: e.target.checked })}
                style={{ accentColor: 'var(--accent)' }}
                disabled={isRunning}
              />
              <div>
                <div style={{ fontWeight: 600 }}>Enable Zayvora</div>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Run simulations & technical models</div>
              </div>
            </label>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={isRunning || !localQuestion.trim()}
            style={{
              width: '100%',
              marginTop: 20,
              padding: '10px 16px',
              background: isRunning || !localQuestion.trim() ? 'var(--border-medium)' : 'var(--accent)',
              color: isRunning || !localQuestion.trim() ? 'var(--text-tertiary)' : 'white',
              border: 'none',
              borderRadius: 'var(--radius-md)',
              fontFamily: 'var(--font-sans)',
              fontSize: 14,
              fontWeight: 600,
              cursor: isRunning || !localQuestion.trim() ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s',
            }}
          >
            {isRunning ? 'Researching...' : 'Start Research'}
          </button>

          {pipelineStatus === 'completed' && (
            <button
              type="button"
              onClick={reset}
              style={{
                width: '100%',
                marginTop: 8,
                padding: '8px 16px',
                background: 'transparent',
                color: 'var(--text-secondary)',
                border: '1px solid var(--border-medium)',
                borderRadius: 'var(--radius-md)',
                fontFamily: 'var(--font-sans)',
                fontSize: 13,
                cursor: 'pointer',
              }}
            >
              New Research
            </button>
          )}
        </form>

        {/* Pipeline progress */}
        {(isRunning || pipelineStatus === 'completed' || pipelineStatus === 'error') && (
          <div style={{ marginTop: 24 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 8 }}>
              PIPELINE
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {pipelineEvents.map((evt, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                  <div
                    className={`stage-dot stage-dot-${evt.status === 'completed' ? 'completed' : evt.status === 'error' ? 'error' : 'running'}`}
                    style={{ marginTop: 6 }}
                  />
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'capitalize' }}>
                      {evt.stage.replace(/_/g, ' ')}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{evt.message}</div>
                  </div>
                </div>
              ))}
              {isRunning && (
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <div className="stage-dot stage-dot-running" />
                  <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>Processing...</span>
                </div>
              )}
            </div>

            {/* Stats */}
            {Object.keys(pipelineStats).length > 0 && (
              <div style={{ marginTop: 12, padding: '10px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
                {Object.entries(pipelineStats).map(([k, v]) => (
                  <div key={k} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                    <span style={{ color: 'var(--text-secondary)' }}>{k.replace(/_/g, ' ')}</span>
                    <span style={{ fontWeight: 600 }}>{v}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
