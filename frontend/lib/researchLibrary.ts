export type ProjectStatus = 'idea' | 'collecting' | 'verifying' | 'drafting' | 'published' | 'archived';
export type SourceType = 'official documentation' | 'research paper' | 'news' | 'blog' | 'dataset' | 'book' | 'video' | 'forum' | 'internal note';
export type ConfidenceLevel = 'low' | 'medium' | 'high' | 'verified';
export type ReliabilityRating = 'weak' | 'mixed' | 'strong' | 'authoritative';

export interface ResearchTag {
  id: string;
  name: string;
  createdAt: string;
}

export interface ResearchProject {
  id: string;
  title: string;
  description: string;
  topic: string;
  status: ProjectStatus;
  createdAt: string;
  updatedAt: string;
  sourceIds: string[];
  noteIds: string[];
  tags: string[];
}

export interface ResearchSource {
  id: string;
  title: string;
  url: string;
  author: string;
  publicationDate: string;
  dateAccessed: string;
  sourceType: SourceType;
  reliability: ReliabilityRating;
  summary: string;
  notes: string;
  tags: string[];
  linkedProjectId: string;
  createdAt: string;
  updatedAt: string;
}

export interface ResearchNote {
  id: string;
  claim: string;
  evidence: string;
  sourceId: string;
  confidence: ConfidenceLevel;
  contradictionNotes: string;
  tags: string[];
  linkedProjectId: string;
  createdAt: string;
  updatedAt: string;
}

export interface ResearchLibrary {
  projects: ResearchProject[];
  sources: ResearchSource[];
  notes: ResearchNote[];
  tags: ResearchTag[];
}

export interface ResearchFilters {
  projectId: string;
  tag: string;
  sourceType: string;
  confidence: string;
  reliability: string;
  dateAdded: string;
}

export const PROJECT_STATUSES: ProjectStatus[] = ['idea', 'collecting', 'verifying', 'drafting', 'published', 'archived'];
export const SOURCE_TYPES: SourceType[] = ['official documentation', 'research paper', 'news', 'blog', 'dataset', 'book', 'video', 'forum', 'internal note'];
export const CONFIDENCE_LEVELS: ConfidenceLevel[] = ['low', 'medium', 'high', 'verified'];
export const RELIABILITY_RATINGS: ReliabilityRating[] = ['weak', 'mixed', 'strong', 'authoritative'];

export const EMPTY_LIBRARY: ResearchLibrary = { projects: [], sources: [], notes: [], tags: [] };
export const STORAGE_KEY = 'nex.research.library.v1';

export function createId(prefix: string): string {
  const random = typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : Math.random().toString(36).slice(2);
  return `${prefix}_${random}`;
}

export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function timestamp(): string {
  return new Date().toISOString();
}

export function splitTags(value: string): string[] {
  return value.split(',').map((tag) => tag.trim().toLowerCase()).filter(Boolean);
}

export function loadResearchLibrary(): ResearchLibrary {
  if (typeof window === 'undefined') return EMPTY_LIBRARY;
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (!stored) return EMPTY_LIBRARY;
  const parsed = JSON.parse(stored) as Partial<ResearchLibrary>;
  return {
    projects: parsed.projects ?? [],
    sources: parsed.sources ?? [],
    notes: parsed.notes ?? [],
    tags: parsed.tags ?? [],
  };
}

export function saveResearchLibrary(library: ResearchLibrary): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalizeLibrary(library)));
}

export function normalizeLibrary(library: ResearchLibrary): ResearchLibrary {
  const names = new Set<string>();
  library.projects.forEach((project) => project.tags.forEach((tag) => names.add(tag)));
  library.sources.forEach((source) => source.tags.forEach((tag) => names.add(tag)));
  library.notes.forEach((note) => note.tags.forEach((tag) => names.add(tag)));
  const existing = new Map(library.tags.map((tag) => [tag.name, tag]));
  return {
    projects: library.projects.map((project) => ({
      ...project,
      sourceIds: library.sources.filter((source) => source.linkedProjectId === project.id).map((source) => source.id),
      noteIds: library.notes.filter((note) => note.linkedProjectId === project.id).map((note) => note.id),
      updatedAt: project.updatedAt || project.createdAt,
    })),
    sources: library.sources,
    notes: library.notes,
    tags: Array.from(names).sort().map((name) => existing.get(name) ?? { id: createId('tag'), name, createdAt: timestamp() }),
  };
}

export function qualityWarnings(source: ResearchSource, notes: ResearchNote[]): string[] {
  const warnings: string[] = [];
  if (!source.url.trim() && source.sourceType !== 'internal note') warnings.push('missing URL');
  if (!source.dateAccessed) warnings.push('missing date accessed');
  if (source.reliability === 'weak' || source.reliability === 'mixed') warnings.push('weak source');
  if (!notes.some((note) => note.sourceId === source.id && note.evidence.trim())) warnings.push('no supporting evidence');
  if (notes.some((note) => note.sourceId === source.id && note.contradictionNotes.trim())) warnings.push('conflicting sources');
  if (isOutdated(source.publicationDate)) warnings.push('outdated source');
  return warnings;
}

export function isOutdated(publicationDate: string): boolean {
  if (!publicationDate) return false;
  const date = new Date(publicationDate);
  if (Number.isNaN(date.getTime())) return false;
  const fourYears = 1000 * 60 * 60 * 24 * 365 * 4;
  return Date.now() - date.getTime() > fourYears;
}

export function sourceQualityStatus(library: ResearchLibrary): { label: string; weakCount: number; warningCount: number } {
  const warningCount = library.sources.reduce((total, source) => total + qualityWarnings(source, library.notes).length, 0);
  const weakCount = library.sources.filter((source) => source.reliability === 'weak' || source.reliability === 'mixed').length;
  const label = warningCount === 0 ? 'clear' : warningCount < 4 ? 'needs review' : 'high risk';
  return { label, weakCount, warningCount };
}

export function inlineCitation(source: ResearchSource): string {
  const author = source.author.trim() || 'missing author/organization';
  const year = source.publicationDate ? new Date(source.publicationDate).getFullYear().toString() : 'missing publication date';
  return `(${author}, ${year})`;
}

export function bibliographyEntry(source: ResearchSource): string {
  const author = source.author.trim() || '[missing author/organization]';
  const date = source.publicationDate || '[missing publication date]';
  const title = source.title.trim() || '[missing title]';
  const url = source.url.trim() || '[missing URL]';
  const accessed = source.dateAccessed || '[missing date accessed]';
  return `${author}. (${date}). ${title}. ${source.sourceType}. ${url}. Accessed ${accessed}.`;
}

export function markdownCitationBlock(source: ResearchSource): string {
  return [`> ${bibliographyEntry(source)}`, `> Reliability: ${source.reliability}`, `> Summary: ${source.summary || '[missing summary]'}`].join('\n');
}

export function exportProjectMarkdown(project: ResearchProject, library: ResearchLibrary): string {
  const sources = library.sources.filter((source) => source.linkedProjectId === project.id);
  const notes = library.notes.filter((note) => note.linkedProjectId === project.id);
  return [`# ${project.title}`, '', `**Topic:** ${project.topic || '[missing topic]'}`, `**Status:** ${project.status}`, `**Created:** ${project.createdAt}`, `**Updated:** ${project.updatedAt}`, '', '## Description', project.description || '[missing description]', '', '## Sources', ...sources.map((source) => `- ${bibliographyEntry(source)}`), '', '## Evidence Notes', ...notes.map((note) => `- **Claim:** ${note.claim}\n  - Evidence: ${note.evidence}\n  - Confidence: ${note.confidence}\n  - Source: ${sources.find((source) => source.id === note.sourceId)?.title || '[missing source reference]'}\n  - Contradictions: ${note.contradictionNotes || 'none recorded'}`)].join('\n');
}

export function exportNotesMarkdown(notes: ResearchNote[], sources: ResearchSource[]): string {
  return ['# Nex Evidence Notes', '', ...notes.map((note) => `## ${note.claim || '[missing claim]'}\n- Evidence: ${note.evidence || '[missing evidence]'}\n- Confidence: ${note.confidence}\n- Source: ${sources.find((source) => source.id === note.sourceId)?.title || '[missing source reference]'}\n- Contradictions: ${note.contradictionNotes || 'none recorded'}\n- Tags: ${note.tags.join(', ') || 'none'}`)].join('\n');
}

export function generateDraft(project: ResearchProject, selectedSources: ResearchSource[], selectedNotes: ResearchNote[]): string {
  const thesis = project.description || '[Add thesis: project description is missing.]';
  const sourceById = new Map(selectedSources.map((source) => [source.id, source]));
  const claims = selectedNotes.filter((note) => note.claim.trim());
  return [`# ${project.title}`, '', `## Thesis`, thesis, '', '## Key Claims', ...(claims.length ? claims.map((note) => `- ${note.claim} ${sourceById.get(note.sourceId) ? inlineCitation(sourceById.get(note.sourceId)!) : '[missing source reference]'}`) : ['- [No claims selected]']), '', '## Evidence Sections', ...(claims.length ? claims.map((note) => { const source = sourceById.get(note.sourceId); return `### ${note.claim}\n${note.evidence || '[missing evidence]'}\n\nConfidence: ${note.confidence}\n\nSource: ${source ? bibliographyEntry(source) : '[missing source reference]'}\n\nContradictions/Open conflicts: ${note.contradictionNotes || 'none recorded'}`; }) : ['[No evidence selected]']), '', '## Open Questions', ...claims.filter((note) => note.confidence === 'low' || note.contradictionNotes.trim()).map((note) => `- Resolve: ${note.claim}`), ...(claims.some((note) => note.confidence === 'low' || note.contradictionNotes.trim()) ? [] : ['- None recorded.']), '', '## Source List', ...(selectedSources.length ? selectedSources.map((source) => `- ${bibliographyEntry(source)}`) : ['- [No sources selected]'])].join('\n');
}

export function downloadFile(filename: string, content: string, type = 'text/plain'): void {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function filterSources(sources: ResearchSource[], filters: ResearchFilters): ResearchSource[] {
  return sources.filter((source) => matchesProject(source.linkedProjectId, filters.projectId) && matchesTag(source.tags, filters.tag) && (!filters.sourceType || source.sourceType === filters.sourceType) && (!filters.reliability || source.reliability === filters.reliability) && matchesDate(source.createdAt, filters.dateAdded));
}

export function filterNotes(notes: ResearchNote[], filters: ResearchFilters): ResearchNote[] {
  return notes.filter((note) => matchesProject(note.linkedProjectId, filters.projectId) && matchesTag(note.tags, filters.tag) && (!filters.confidence || note.confidence === filters.confidence) && matchesDate(note.createdAt, filters.dateAdded));
}

function matchesProject(value: string, filter: string): boolean { return !filter || value === filter; }
function matchesTag(tags: string[], filter: string): boolean { return !filter || tags.includes(filter); }
function matchesDate(value: string, filter: string): boolean { return !filter || value.slice(0, 10) === filter; }
