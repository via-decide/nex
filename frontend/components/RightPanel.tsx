/**
 * Right Panel — Context viewer: evidence, knowledge graph, sources + Subchat
 */

'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useResearchStore } from '../store/research';

type Tab = 'evidence' | 'subchat' | 'sources';

function EvidenceView() {
  const { report, selectedFindingId } = useResearchStore();
  const finding = report?.key_findings.find((f) => f.id === selectedFindingId);
  if (!finding) return (
    <p style={{ fontSize: 13, color: 'var(--text-tertiary)', textAlign: 'center', marginTop: 40 }}>
      Select a finding from the center panel to view evidence.
    </p>
  );

  return (
    <div>
      <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12, lineHeight: 1.4 }}>
        {finding.headline}
      </h3>
      <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16, lineHeight: 1.6 }}>
        {finding.detail}
      </p>

      {finding.related_concepts.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.04em', display: 'block', marginBottom: 6 }}>
            Related Concepts
          </span>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {finding.related_concepts.map((c) => (
              <span key={c} style={{
                fontSize: 12,
                background: 'var(--accent-light)',
                color: 'var(--accent)',
                padding: '2px 8px',
                borderRadius: 20,
                border: '1px solid var(--accent)',
                opacity: 0.8,
              }}>
                {c}
              </span>
            ))}
          </div>
        </div>
      )}

      {finding.supporting_sources.length > 0 && (
        <div>
          <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.04em', display: 'block', marginBottom: 6 }}>
            Supporting Sources
          </span>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {finding.supporting_sources.map((url, i) => (
              <a
                key={i}
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  fontSize: 12,
                  color: 'var(--text-link)',
                  display: 'block',
                  padding: '6px 10px',
                  background: 'var(--bg-secondary)',
                  borderRadius: 'var(--radius-sm)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {i + 1}. {url.replace(/^https?:\/\//, '')}
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function SourcesView() {
  const { report } = useResearchStore();
  if (!report) return null;
  const typeColors: Record<string, string> = {
    arxiv: 'var(--verified)',
    wikipedia: 'var(--accent)',
    gov: 'var(--likely)',
    web: 'var(--text-tertiary)',
    engineering_blog: 'var(--text-secondary)',
  };
  return (
    <div>
      <p style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 12 }}>
        {report.sources.length} sources analysed
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {report.sources.map((src, i) => (
          <div
            key={i}
            style={{
              padding: '8px 10px',
              background: 'var(--bg-secondary)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
              <span style={{
                fontSize: 10,
                fontWeight: 700,
                color: typeColors[src.type] || 'var(--text-tertiary)',
                textTransform: 'uppercase',
              }}>
                {src.type}
              </span>
            </div>
            <a
              href={src.url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                fontSize: 12,
                color: 'var(--text-link)',
                display: 'block',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {src.url.replace(/^https?:\/\//, '')}
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}

function SubchatView() {
  const {
    selectedFindingId, threads, openSubchat, sendSubchatMessage, report,
  } = useResearchStore();
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  const thread = selectedFindingId ? threads[selectedFindingId] : null;
  const finding = report?.key_findings.find((f) => f.id === selectedFindingId);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [thread?.messages]);

  if (!selectedFindingId || !finding) {
    return (
      <p style={{ fontSize: 13, color: 'var(--text-tertiary)', textAlign: 'center', marginTop: 40 }}>
        Select a finding to start a research thread.
      </p>
    );
  }

  if (!thread) {
    return (
      <div style={{ textAlign: 'center', marginTop: 40 }}>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 12 }}>
          Start a research thread for this finding.
        </p>
        <button
          onClick={() => openSubchat(selectedFindingId)}
          style={{
            padding: '8px 16px',
            background: 'var(--accent)',
            color: 'white',
            border: 'none',
            borderRadius: 'var(--radius-md)',
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Open Thread
        </button>
      </div>
    );
  }

  const handleSend = () => {
    if (!input.trim() || thread.isLoading) return;
    sendSubchatMessage(selectedFindingId, input.trim());
    setInput('');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Thread header */}
      <div style={{
        padding: '8px 0 12px',
        borderBottom: '1px solid var(--border-subtle)',
        marginBottom: 12,
        flexShrink: 0,
      }}>
        <p style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
          Thread: {thread.finding_headline}
        </p>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {thread.messages.map((msg, i) => (
          <div
            key={i}
            style={{
              alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
              maxWidth: '90%',
            }}
          >
            <div style={{
              padding: '8px 12px',
              borderRadius: msg.role === 'user' ? '12px 12px 4px 12px' : '12px 12px 12px 4px',
              background: msg.role === 'user' ? 'var(--accent)' : 'var(--bg-secondary)',
              color: msg.role === 'user' ? 'white' : 'var(--text-primary)',
              fontSize: 13,
              lineHeight: 1.5,
              border: msg.role === 'assistant' ? '1px solid var(--border-subtle)' : 'none',
            }}>
              {msg.content}
            </div>
          </div>
        ))}
        {thread.isLoading && (
          <div style={{ alignSelf: 'flex-start', fontSize: 12, color: 'var(--text-tertiary)', padding: '4px 12px' }}>
            <span style={{ animation: 'pulse 1.2s infinite', display: 'inline-block' }}>Thinking...</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{
        marginTop: 12,
        display: 'flex',
        gap: 8,
        flexShrink: 0,
        borderTop: '1px solid var(--border-subtle)',
        paddingTop: 12,
      }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
          placeholder="Ask about this finding..."
          disabled={thread.isLoading}
          style={{
            flex: 1,
            padding: '8px 12px',
            border: '1px solid var(--border-medium)',
            borderRadius: 'var(--radius-md)',
            fontFamily: 'var(--font-sans)',
            fontSize: 13,
            outline: 'none',
            background: 'white',
          }}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || thread.isLoading}
          style={{
            padding: '8px 12px',
            background: !input.trim() || thread.isLoading ? 'var(--border-medium)' : 'var(--accent)',
            color: 'white',
            border: 'none',
            borderRadius: 'var(--radius-md)',
            cursor: !input.trim() || thread.isLoading ? 'not-allowed' : 'pointer',
            fontSize: 16,
          }}
        >
          ↑
        </button>
      </div>
    </div>
  );
}

export function RightPanel() {
  const { report, pipelineStatus } = useResearchStore();
  const [tab, setTab] = useState<Tab>('evidence');

  if (pipelineStatus === 'idle' || pipelineStatus === 'queued' || pipelineStatus === 'running') {
    return (
      <aside style={{
        width: 'var(--right-panel-width)',
        flexShrink: 0,
        borderLeft: '1px solid var(--border-subtle)',
        background: 'var(--bg-panel)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'var(--text-tertiary)',
        fontSize: 13,
        padding: 'var(--panel-padding)',
        textAlign: 'center',
      }}>
        Evidence and context will appear here after research completes.
      </aside>
    );
  }

  if (!report) return null;

  const tabs: { id: Tab; label: string }[] = [
    { id: 'evidence', label: 'Evidence' },
    { id: 'subchat', label: 'Thread' },
    { id: 'sources', label: 'Sources' },
  ];

  return (
    <aside style={{
      width: 'var(--right-panel-width)',
      flexShrink: 0,
      borderLeft: '1px solid var(--border-subtle)',
      background: 'var(--bg-panel)',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Tab bar */}
      <div style={{
        display: 'flex',
        borderBottom: '1px solid var(--border-subtle)',
        flexShrink: 0,
      }}>
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              flex: 1,
              padding: '12px 8px',
              background: 'transparent',
              border: 'none',
              borderBottom: `2px solid ${tab === t.id ? 'var(--accent)' : 'transparent'}`,
              color: tab === t.id ? 'var(--accent)' : 'var(--text-secondary)',
              fontFamily: 'var(--font-sans)',
              fontSize: 13,
              fontWeight: tab === t.id ? 700 : 400,
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{
        flex: 1,
        overflowY: tab === 'subchat' ? 'hidden' : 'auto',
        padding: 'var(--panel-padding)',
        display: 'flex',
        flexDirection: 'column',
      }}>
        {tab === 'evidence' && <EvidenceView />}
        {tab === 'subchat' && <SubchatView />}
        {tab === 'sources' && <SourcesView />}
      </div>
    </aside>
  );
}
