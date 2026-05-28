'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  CONFIDENCE_LEVELS,
  EMPTY_LIBRARY,
  PROJECT_STATUSES,
  RELIABILITY_RATINGS,
  SOURCE_TYPES,
  ResearchFilters,
  ResearchLibrary,
  ResearchNote,
  ResearchProject,
  ResearchSource,
  bibliographyEntry,
  createId,
  downloadFile,
  exportNotesMarkdown,
  exportProjectMarkdown,
  filterNotes,
  filterSources,
  generateDraft,
  inlineCitation,
  loadResearchLibrary,
  markdownCitationBlock,
  normalizeLibrary,
  qualityWarnings,
  saveResearchLibrary,
  sourceQualityStatus,
  splitTags,
  timestamp,
  todayIso,
} from '../../lib/researchLibrary';

const blankFilters: ResearchFilters = { projectId: '', tag: '', sourceType: '', confidence: '', reliability: '', dateAdded: '' };

export default function ResearchDashboardPage() {
  const [library, setLibrary] = useState<ResearchLibrary>(EMPTY_LIBRARY);
  const [filters, setFilters] = useState<ResearchFilters>(blankFilters);
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [selectedSourceId, setSelectedSourceId] = useState('');
  const [draftSourceIds, setDraftSourceIds] = useState<string[]>([]);
  const [draftNoteIds, setDraftNoteIds] = useState<string[]>([]);
  const [generatedDraft, setGeneratedDraft] = useState('');
  const [citationOutput, setCitationOutput] = useState('');
  const [importText, setImportText] = useState('');

  useEffect(() => setLibrary(loadResearchLibrary()), []);
  useEffect(() => saveResearchLibrary(library), [library]);

  const quality = sourceQualityStatus(library);
  const activeProjects = library.projects.filter((project) => !['published', 'archived'].includes(project.status));
  const filteredSources = useMemo(() => filterSources(library.sources, filters), [library.sources, filters]);
  const filteredNotes = useMemo(() => filterNotes(library.notes, filters), [library.notes, filters]);
  const selectedProject = library.projects.find((project) => project.id === selectedProjectId) ?? library.projects[0];
  const selectedSource = library.sources.find((source) => source.id === selectedSourceId) ?? library.sources[0];
  const projectSources = selectedProject ? library.sources.filter((source) => source.linkedProjectId === selectedProject.id) : [];
  const projectNotes = selectedProject ? library.notes.filter((note) => note.linkedProjectId === selectedProject.id) : [];

  function updateLibrary(next: ResearchLibrary) {
    setLibrary(normalizeLibrary(next));
  }

  function addProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const now = timestamp();
    const project: ResearchProject = {
      id: createId('project'),
      title: String(form.get('title') || '').trim(),
      description: String(form.get('description') || '').trim(),
      topic: String(form.get('topic') || '').trim(),
      status: String(form.get('status') || 'idea') as ResearchProject['status'],
      createdAt: now,
      updatedAt: now,
      sourceIds: [],
      noteIds: [],
      tags: splitTags(String(form.get('tags') || '')),
    };
    if (!project.title) return;
    updateLibrary({ ...library, projects: [project, ...library.projects] });
    setSelectedProjectId(project.id);
    event.currentTarget.reset();
  }

  function addSource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const now = timestamp();
    const source: ResearchSource = {
      id: createId('source'),
      title: String(form.get('title') || '').trim(),
      url: String(form.get('url') || '').trim(),
      author: String(form.get('author') || '').trim(),
      publicationDate: String(form.get('publicationDate') || ''),
      dateAccessed: String(form.get('dateAccessed') || todayIso()),
      sourceType: String(form.get('sourceType') || 'research paper') as ResearchSource['sourceType'],
      reliability: String(form.get('reliability') || 'mixed') as ResearchSource['reliability'],
      summary: String(form.get('summary') || '').trim(),
      notes: String(form.get('notes') || '').trim(),
      tags: splitTags(String(form.get('tags') || '')),
      linkedProjectId: String(form.get('linkedProjectId') || selectedProject?.id || ''),
      createdAt: now,
      updatedAt: now,
    };
    if (!source.title) return;
    updateLibrary({ ...library, sources: [source, ...library.sources] });
    setSelectedSourceId(source.id);
    event.currentTarget.reset();
  }

  function addNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const now = timestamp();
    const note: ResearchNote = {
      id: createId('note'),
      claim: String(form.get('claim') || '').trim(),
      evidence: String(form.get('evidence') || '').trim(),
      sourceId: String(form.get('sourceId') || selectedSource?.id || ''),
      confidence: String(form.get('confidence') || 'medium') as ResearchNote['confidence'],
      contradictionNotes: String(form.get('contradictionNotes') || '').trim(),
      tags: splitTags(String(form.get('tags') || '')),
      linkedProjectId: String(form.get('linkedProjectId') || selectedProject?.id || ''),
      createdAt: now,
      updatedAt: now,
    };
    if (!note.claim || !note.sourceId) return;
    updateLibrary({ ...library, notes: [note, ...library.notes] });
    event.currentTarget.reset();
  }

  function importSources() {
    const parsed = JSON.parse(importText) as Partial<ResearchSource>[];
    const now = timestamp();
    const sources = parsed.map((item) => ({
      id: item.id || createId('source'),
      title: item.title || '[missing title]',
      url: item.url || '',
      author: item.author || '',
      publicationDate: item.publicationDate || '',
      dateAccessed: item.dateAccessed || todayIso(),
      sourceType: item.sourceType || 'internal note',
      reliability: item.reliability || 'mixed',
      summary: item.summary || '',
      notes: item.notes || '',
      tags: item.tags || [],
      linkedProjectId: item.linkedProjectId || selectedProject?.id || '',
      createdAt: item.createdAt || now,
      updatedAt: now,
    })) as ResearchSource[];
    updateLibrary({ ...library, sources: [...sources, ...library.sources] });
    setImportText('');
  }

  function createDraft() {
    if (!selectedProject) return;
    const sources = projectSources.filter((source) => draftSourceIds.length === 0 || draftSourceIds.includes(source.id));
    const notes = projectNotes.filter((note) => draftNoteIds.length === 0 || draftNoteIds.includes(note.id));
    setGeneratedDraft(generateDraft(selectedProject, sources, notes));
  }

  function toggle(value: string, values: string[], setValues: (next: string[]) => void) {
    setValues(values.includes(value) ? values.filter((item) => item !== value) : [...values, value]);
  }

  return (
    <main className="research-shell">
      <header className="research-hero">
        <div>
          <p className="eyebrow">Nex Research Workstation</p>
          <h1>Research dashboard</h1>
          <p>Track projects, evidence, source quality, citations, and deterministic markdown outputs locally in this browser.</p>
        </div>
        <div className="hero-actions">
          <button onClick={() => downloadFile('nex-sources.json', JSON.stringify(library.sources, null, 2), 'application/json')}>Export sources JSON</button>
          <button onClick={() => downloadFile('nex-notes.md', exportNotesMarkdown(library.notes, library.sources))}>Export notes MD</button>
        </div>
      </header>

      <section className="metric-grid">
        <Metric label="Saved sources" value={library.sources.length} />
        <Metric label="Active projects" value={activeProjects.length} />
        <Metric label="Recent notes" value={library.notes.slice(0, 5).length} />
        <Metric label="Citation count" value={library.sources.length} />
        <Metric label="Source quality" value={quality.label} detail={`${quality.warningCount} warnings · ${quality.weakCount} weak/mixed`} />
      </section>

      <section className="research-grid two">
        <Card title="Create project" subtitle="Projects connect sources, notes, and drafts.">
          <form className="stack" onSubmit={addProject}>
            <input name="title" placeholder="Project title" required />
            <input name="topic" placeholder="Topic" />
            <textarea name="description" placeholder="Description / working thesis" />
            <select name="status">{PROJECT_STATUSES.map((status) => <option key={status}>{status}</option>)}</select>
            <input name="tags" placeholder="tags, comma-separated" />
            <button>Create project</button>
          </form>
        </Card>

        <Card title="Add source" subtitle="Every source keeps URL, title, date accessed, notes, and tags.">
          <form className="stack" onSubmit={addSource}>
            <input name="title" placeholder="Source title" required />
            <input name="url" placeholder="URL" />
            <input name="author" placeholder="Author / organization" />
            <div className="form-row"><label>Published<input name="publicationDate" type="date" /></label><label>Accessed<input name="dateAccessed" type="date" defaultValue={todayIso()} /></label></div>
            <div className="form-row"><select name="sourceType">{SOURCE_TYPES.map((type) => <option key={type}>{type}</option>)}</select><select name="reliability">{RELIABILITY_RATINGS.map((rating) => <option key={rating}>{rating}</option>)}</select></div>
            <select name="linkedProjectId" value={selectedProject?.id || ''} onChange={(event) => setSelectedProjectId(event.target.value)}>{library.projects.map((project) => <option value={project.id} key={project.id}>{project.title}</option>)}</select>
            <textarea name="summary" placeholder="Summary" />
            <textarea name="notes" placeholder="Source notes" />
            <input name="tags" placeholder="tags, comma-separated" />
            <button>Save source</button>
          </form>
        </Card>
      </section>

      <section className="research-grid two">
        <Card title="Evidence note" subtitle="Claims require evidence and source references.">
          <form className="stack" onSubmit={addNote}>
            <input name="claim" placeholder="Claim" required />
            <textarea name="evidence" placeholder="Evidence text" />
            <select name="sourceId" value={selectedSource?.id || ''} onChange={(event) => setSelectedSourceId(event.target.value)}>{library.sources.map((source) => <option value={source.id} key={source.id}>{source.title}</option>)}</select>
            <select name="linkedProjectId" defaultValue={selectedProject?.id || ''}>{library.projects.map((project) => <option value={project.id} key={project.id}>{project.title}</option>)}</select>
            <select name="confidence">{CONFIDENCE_LEVELS.map((confidence) => <option key={confidence}>{confidence}</option>)}</select>
            <textarea name="contradictionNotes" placeholder="Contradiction notes / conflicts" />
            <input name="tags" placeholder="tags, comma-separated" />
            <button>Attach evidence note</button>
          </form>
        </Card>

        <Card title="Import sources" subtitle="Paste an array of source JSON objects. Missing metadata stays marked missing.">
          <textarea className="codebox" value={importText} onChange={(event) => setImportText(event.target.value)} placeholder='[{"title":"...","url":"...","dateAccessed":"2026-05-28"}]' />
          <button onClick={importSources} disabled={!importText.trim()}>Import sources JSON</button>
        </Card>
      </section>

      <Card title="Search and filtering" subtitle="Filter by project, tag, source type, confidence, reliability, and date added.">
        <div className="filter-bar">
          <select value={filters.projectId} onChange={(event) => setFilters({ ...filters, projectId: event.target.value })}><option value="">All projects</option>{library.projects.map((project) => <option value={project.id} key={project.id}>{project.title}</option>)}</select>
          <select value={filters.tag} onChange={(event) => setFilters({ ...filters, tag: event.target.value })}><option value="">All tags</option>{library.tags.map((tag) => <option value={tag.name} key={tag.id}>{tag.name}</option>)}</select>
          <select value={filters.sourceType} onChange={(event) => setFilters({ ...filters, sourceType: event.target.value })}><option value="">All source types</option>{SOURCE_TYPES.map((type) => <option key={type}>{type}</option>)}</select>
          <select value={filters.confidence} onChange={(event) => setFilters({ ...filters, confidence: event.target.value })}><option value="">All confidence</option>{CONFIDENCE_LEVELS.map((confidence) => <option key={confidence}>{confidence}</option>)}</select>
          <select value={filters.reliability} onChange={(event) => setFilters({ ...filters, reliability: event.target.value })}><option value="">All reliability</option>{RELIABILITY_RATINGS.map((rating) => <option key={rating}>{rating}</option>)}</select>
          <input type="date" value={filters.dateAdded} onChange={(event) => setFilters({ ...filters, dateAdded: event.target.value })} />
          <button onClick={() => setFilters(blankFilters)}>Reset</button>
        </div>
      </Card>

      <section className="research-grid two wide-left">
        <Card title="Source library" subtitle={`${filteredSources.length} sources shown`}>
          <div className="item-list">
            {filteredSources.map((source) => {
              const warnings = qualityWarnings(source, library.notes);
              return <article className="research-item" key={source.id} onClick={() => setSelectedSourceId(source.id)}><div><h3>{source.title}</h3><p>{source.author || 'missing author/organization'} · {source.sourceType} · accessed {source.dateAccessed || 'missing'}</p><p>{source.summary}</p></div><div className="pill-row"><span className={`pill ${source.reliability}`}>{source.reliability}</span>{warnings.map((warning) => <span className="pill warn" key={warning}>{warning}</span>)}</div></article>;
            })}
          </div>
        </Card>

        <Card title="Citation builder" subtitle="No missing metadata is invented.">
          {selectedSource ? <div className="stack"><p className="muted">Selected: {selectedSource.title}</p><button onClick={() => setCitationOutput(inlineCitation(selectedSource))}>Inline citation</button><button onClick={() => setCitationOutput(bibliographyEntry(selectedSource))}>Bibliography entry</button><button onClick={() => setCitationOutput(markdownCitationBlock(selectedSource))}>Markdown citation block</button><textarea className="codebox" readOnly value={citationOutput} /><button onClick={() => navigator.clipboard.writeText(citationOutput)} disabled={!citationOutput}>Copy citation output</button></div> : <p className="muted">Save a source to build citations.</p>}
        </Card>
      </section>

      <Card title="Evidence notes" subtitle={`${filteredNotes.length} notes shown`}>
        <div className="item-list compact">
          {filteredNotes.map((note) => <article className="research-item" key={note.id}><div><h3>{note.claim}</h3><p>{note.evidence}</p><p>Source: {library.sources.find((source) => source.id === note.sourceId)?.title || 'missing source reference'}</p>{note.contradictionNotes && <p className="warning-text">Conflict: {note.contradictionNotes}</p>}</div><span className={`pill confidence-${note.confidence}`}>{note.confidence}</span></article>)}
        </div>
      </Card>

      <section className="research-grid two">
        <Card title="Active research projects" subtitle="Export project evidence bundles as markdown.">
          <div className="item-list compact">{library.projects.map((project) => <article className="research-item" key={project.id}><div><h3>{project.title}</h3><p>{project.topic} · {project.status} · {project.sourceIds.length} sources · {project.noteIds.length} notes</p></div><button onClick={() => downloadFile(`${project.title.replace(/\W+/g, '-').toLowerCase()}-research.md`, exportProjectMarkdown(project, library))}>Export MD</button></article>)}</div>
        </Card>

        <Card title="Research output generator" subtitle="Deterministic formatter; no AI API is used.">
          <div className="stack"><select value={selectedProject?.id || ''} onChange={(event) => { setSelectedProjectId(event.target.value); setDraftSourceIds([]); setDraftNoteIds([]); }}>{library.projects.map((project) => <option key={project.id} value={project.id}>{project.title}</option>)}</select><div className="checklist"><strong>Sources</strong>{projectSources.map((source) => <label key={source.id}><input type="checkbox" checked={draftSourceIds.includes(source.id)} onChange={() => toggle(source.id, draftSourceIds, setDraftSourceIds)} />{source.title}</label>)}</div><div className="checklist"><strong>Notes</strong>{projectNotes.map((note) => <label key={note.id}><input type="checkbox" checked={draftNoteIds.includes(note.id)} onChange={() => toggle(note.id, draftNoteIds, setDraftNoteIds)} />{note.claim}</label>)}</div><button onClick={createDraft} disabled={!selectedProject}>Generate markdown draft</button><textarea className="codebox draft" readOnly value={generatedDraft} /><button onClick={() => downloadFile('nex-research-draft.md', generatedDraft)} disabled={!generatedDraft}>Export draft</button></div>
        </Card>
      </section>
    </main>
  );
}

function Metric({ label, value, detail }: { label: string; value: string | number; detail?: string }) {
  return <article className="metric-card"><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</article>;
}

function Card({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return <section className="research-card"><div className="card-heading"><h2>{title}</h2><p>{subtitle}</p></div>{children}</section>;
}
