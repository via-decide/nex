/**
 * Nex Research Store — Zustand global state
 *
 * Manages the full research pipeline state, UI interactions,
 * subchat threads, and pipeline events.
 */

import { create } from 'zustand';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type Confidence = 'VERIFIED' | 'LIKELY' | 'LOW_CONFIDENCE';
export type PipelineStatus = 'idle' | 'queued' | 'running' | 'completed' | 'error';

export interface ResearchFinding {
  id: string;
  headline: string;
  detail: string;
  confidence: Confidence;
  supporting_sources: string[];
  related_concepts: string[];
  subchat_seed: string;
}

export interface ResearchReport {
  title: string;
  topic: string;
  depth: string;
  generated_at: string;
  total_sources_analyzed: number;
  executive_summary: string;
  key_findings: ResearchFinding[];
  evidence_sections: Array<{ title: string; content: string }>;
  limitations: string;
  future_research: string[];
  sources: Array<{ url: string; title: string; type: string }>;
  knowledge_graph: {
    nodes: Array<{ id: string; label: string; type: string; confidence: string; description: string }>;
    edges: Array<{ source: string; target: string; relation: string; weight: number }>;
  };
}

export interface PipelineEvent {
  stage: string;
  status: string;
  message: string;
  data?: Record<string, unknown>;
}

export interface SubchatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface SubchatThread {
  thread_id: string;
  finding_id: string;
  finding_headline: string;
  messages: SubchatMessage[];
  isLoading: boolean;
}

export interface ResearchConfig {
  depth: 'standard' | 'deep' | 'exhaustive';
  maxSources: number;
  enableZayvora: boolean;
  sourceTypes: string[];
}

// ---------------------------------------------------------------------------
// Store state & actions
// ---------------------------------------------------------------------------

interface ResearchState {
  // Pipeline
  runId: string | null;
  question: string;
  pipelineStatus: PipelineStatus;
  pipelineEvents: PipelineEvent[];
  pipelineStats: Record<string, number>;
  config: ResearchConfig;

  // Report
  report: ResearchReport | null;

  // UI state
  selectedFindingId: string | null;
  rightPanelMode: 'evidence' | 'graph' | 'sources' | null;
  isSubmitting: boolean;
  error: string | null;

  // Subchat
  threads: Record<string, SubchatThread>;   // keyed by finding_id
  activeThreadId: string | null;

  // Actions
  setQuestion: (q: string) => void;
  setConfig: (c: Partial<ResearchConfig>) => void;
  startResearch: (question: string) => Promise<void>;
  selectFinding: (findingId: string) => void;
  setRightPanelMode: (mode: 'evidence' | 'graph' | 'sources' | null) => void;
  openSubchat: (findingId: string) => Promise<void>;
  sendSubchatMessage: (findingId: string, message: string) => Promise<void>;
  reset: () => void;
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API error');
  }
  return res.json();
}

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API error');
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Poll helper
// ---------------------------------------------------------------------------

async function pollUntilComplete(
  runId: string,
  onEvent: (event: PipelineEvent) => void,
  onComplete: (data: { report: ResearchReport; stats: Record<string, number> }) => void,
  onError: (err: string) => void
): Promise<void> {
  const poll = async () => {
    try {
      const run = await apiGet<{
        status: string;
        error?: string;
        events: PipelineEvent[];
        stats?: Record<string, number>;
        report?: ResearchReport;
      }>(`/api/research/${runId}`);

      run.events?.forEach(onEvent);

      if (run.status === 'completed' && run.report) {
        onComplete({ report: run.report, stats: run.stats || {} });
      } else if (run.status === 'error') {
        onError(run.error || 'Pipeline failed.');
      } else {
        setTimeout(poll, 2000);
      }
    } catch (e) {
      onError((e as Error).message);
    }
  };
  poll();
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

const DEFAULT_CONFIG: ResearchConfig = {
  depth: 'standard',
  maxSources: 30,
  enableZayvora: false,
  sourceTypes: ['wikipedia', 'arxiv', 'semanticscholar'],
};

export const useResearchStore = create<ResearchState>((set, get) => ({
  // Initial state
  runId: null,
  question: '',
  pipelineStatus: 'idle',
  pipelineEvents: [],
  pipelineStats: {},
  config: DEFAULT_CONFIG,
  report: null,
  selectedFindingId: null,
  rightPanelMode: null,
  isSubmitting: false,
  error: null,
  threads: {},
  activeThreadId: null,

  setQuestion: (q) => set({ question: q }),

  setConfig: (c) =>
    set((s) => ({ config: { ...s.config, ...c } })),

  startResearch: async (question) => {
    const { config } = get();
    set({
      isSubmitting: true,
      pipelineStatus: 'queued',
      pipelineEvents: [],
      pipelineStats: {},
      report: null,
      selectedFindingId: null,
      rightPanelMode: null,
      error: null,
      threads: {},
      activeThreadId: null,
      question,
    });
    try {
      const res = await apiPost<{ run_id: string; status: string }>('/api/research/start', {
        question,
        depth: config.depth,
        max_sources: config.maxSources,
        enable_zayvora: config.enableZayvora,
        source_types: config.sourceTypes,
      });
      set({ runId: res.run_id, pipelineStatus: 'running', isSubmitting: false });

      const seenStages = new Set<string>();
      pollUntilComplete(
        res.run_id,
        (event) => {
          const key = `${event.stage}-${event.status}`;
          if (!seenStages.has(key)) {
            seenStages.add(key);
            set((s) => ({ pipelineEvents: [...s.pipelineEvents, event] }));
          }
        },
        ({ report, stats }) => {
          set({
            pipelineStatus: 'completed',
            report,
            pipelineStats: stats,
          });
        },
        (err) => {
          set({ pipelineStatus: 'error', error: err });
        }
      );
    } catch (e) {
      set({ isSubmitting: false, pipelineStatus: 'error', error: (e as Error).message });
    }
  },

  selectFinding: (findingId) =>
    set({ selectedFindingId: findingId, rightPanelMode: 'evidence' }),

  setRightPanelMode: (mode) => set({ rightPanelMode: mode }),

  openSubchat: async (findingId) => {
    const { runId, threads } = get();
    if (!runId) return;

    // Reuse existing thread
    if (threads[findingId]) {
      set({ activeThreadId: threads[findingId].thread_id, selectedFindingId: findingId });
      return;
    }

    try {
      const thread = await apiPost<{
        thread_id: string;
        finding_id: string;
        finding_headline: string;
        messages: SubchatMessage[];
      }>('/api/subchat/create', { run_id: runId, finding_id: findingId });

      set((s) => ({
        threads: {
          ...s.threads,
          [findingId]: {
            thread_id: thread.thread_id,
            finding_id: thread.finding_id,
            finding_headline: thread.finding_headline,
            messages: thread.messages,
            isLoading: false,
          },
        },
        activeThreadId: thread.thread_id,
        selectedFindingId: findingId,
      }));
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  sendSubchatMessage: async (findingId, message) => {
    const { threads } = get();
    const thread = threads[findingId];
    if (!thread) return;

    // Optimistically add user message
    set((s) => ({
      threads: {
        ...s.threads,
        [findingId]: {
          ...s.threads[findingId],
          messages: [
            ...s.threads[findingId].messages,
            { role: 'user', content: message, timestamp: new Date().toISOString() },
          ],
          isLoading: true,
        },
      },
    }));

    try {
      const res = await fetch(
        `${API_BASE}/api/subchat/${thread.thread_id}/message`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message }),
        }
      );

      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      let assistantText = '';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value);
          const lines = chunk.split('\n').filter((l) => l.startsWith('data:'));
          for (const line of lines) {
            const data = JSON.parse(line.replace('data: ', ''));
            if (data.delta) assistantText += data.delta;
          }
        }
      }

      set((s) => ({
        threads: {
          ...s.threads,
          [findingId]: {
            ...s.threads[findingId],
            messages: [
              ...s.threads[findingId].messages,
              {
                role: 'assistant',
                content: assistantText,
                timestamp: new Date().toISOString(),
              },
            ],
            isLoading: false,
          },
        },
      }));
    } catch (e) {
      set((s) => ({
        threads: {
          ...s.threads,
          [findingId]: { ...s.threads[findingId], isLoading: false },
        },
        error: (e as Error).message,
      }));
    }
  },

  reset: () =>
    set({
      runId: null,
      question: '',
      pipelineStatus: 'idle',
      pipelineEvents: [],
      pipelineStats: {},
      report: null,
      selectedFindingId: null,
      rightPanelMode: null,
      isSubmitting: false,
      error: null,
      threads: {},
      activeThreadId: null,
    }),
}));
