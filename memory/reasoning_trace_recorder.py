import os
import json
import logging
import threading
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Union
from uuid import uuid4
from pathlib import Path
import re

# Configure module-level logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)


class TraceRecorderError(Exception):
    """Base exception for TraceRecorder operations."""
    pass


class TraceNotFoundError(TraceRecorderError):
    """Raised when a requested reasoning trace cannot be found."""
    pass


class TraceStorageError(TraceRecorderError):
    """Raised when there is an issue saving or loading traces from disk."""
    pass


@dataclass
class Source:
    """
    Represents a source of information used during the reasoning process.
    """
    url: str
    title: str
    snippet: Optional[str] = None
    credibility_score: Optional[float] = None
    accessed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Source':
        return cls(**data)


@dataclass
class ReasoningStep:
    """
    Represents a single atomic step in a chain of reasoning.
    """
    step_number: int
    description: str
    logic_applied: Optional[str] = None
    confidence: float = 1.0
    evidence_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ReasoningStep':
        return cls(**data)


@dataclass
class ReasoningTrace:
    """
    Core data structure representing a complete analytical reasoning chain.
    Designed for ingestion by Zayvora and other decision engines.
    """
    trace_id: str
    topic: str
    question: str
    reasoning_steps: List[ReasoningStep]
    conclusion: str
    sources: List[Source]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the reasoning trace to a dictionary."""
        return {
            "trace_id": self.trace_id,
            "topic": self.topic,
            "question": self.question,
            "reasoning_steps": [step.to_dict() for step in self.reasoning_steps],
            "conclusion": self.conclusion,
            "sources": [source.to_dict() for source in self.sources],
            "created_at": self.created_at,
            "tags": self.tags,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ReasoningTrace':
        """Deserializes a dictionary into a ReasoningTrace instance."""
        try:
            steps = [ReasoningStep.from_dict(step_data) for step_data in data.get('reasoning_steps', [])]
            sources = [Source.from_dict(source_data) for source_data in data.get('sources', [])]
            
            return cls(
                trace_id=data['trace_id'],
                topic=data['topic'],
                question=data['question'],
                reasoning_steps=steps,
                conclusion=data['conclusion'],
                sources=sources,
                created_at=data.get('created_at', datetime.now(timezone.utc).isoformat()),
                tags=data.get('tags', []),
                metadata=data.get('metadata', {})
            )
        except KeyError as e:
            logger.error(f"Missing required field during trace deserialization: {e}")
            raise TraceStorageError(f"Invalid trace data format: missing {e}")

    def to_markdown(self) -> str:
        """
        Converts the reasoning trace into a human-readable Markdown document.
        Ideal for research documentation and review.
        """
        md_lines = [
            f"# Reasoning Trace: {self.topic}",
            f"**Trace ID:** `{self.trace_id}`",
            f"**Created At:** {self.created_at}",
            f"**Tags:** {', '.join(self.tags) if self.tags else 'None'}",
            "---",
            "## ❓ Question / Objective",
            f"> {self.question}",
            "",
            "## 🧠 Reasoning Steps",
        ]

        if not self.reasoning_steps:
            md_lines.append("*No reasoning steps recorded.*")
        else:
            for step in sorted(self.reasoning_steps, key=lambda s: s.step_number):
                md_lines.append(f"### Step {step.step_number}")
                md_lines.append(f"**Description:** {step.description}")
                if step.logic_applied:
                    md_lines.append(f"**Logic/Heuristic:** {step.logic_applied}")
                md_lines.append(f"**Confidence:** {step.confidence * 100:.1f}%")
                if step.evidence_refs:
                    md_lines.append(f"**Evidence References:** {', '.join(step.evidence_refs)}")
                md_lines.append("")

        md_lines.extend([
            "## 🎯 Conclusion",
            f"{self.conclusion}",
            "",
            "## 📚 Sources Cited",
        ])

        if not self.sources:
            md_lines.append("*No sources cited.*")
        else:
            for i, source in enumerate(self.sources, 1):
                md_lines.append(f"{i}. **[{source.title}]({source.url})**")
                if source.snippet:
                    md_lines.append(f"   > *\"{source.snippet}\"*")
                if source.credibility_score is not None:
                    md_lines.append(f"   - *Credibility Score: {source.credibility_score}*")
                md_lines.append(f"   - *Accessed: {source.accessed_at}*")

        return "\n".join(md_lines)


class TraceRecorder:
    """
    Manages the lifecycle of Reasoning Traces.
    Responsible for recording, indexing, searching, and exporting analytical chains.
    Thread-safe implementation for use in concurrent agent environments.
    """

    def __init__(self, storage_dir: Union[str, Path] = ".nex/memory/traces"):
        """
        Initializes the TraceRecorder.
        
        Args:
            storage_dir (Union[str, Path]): Directory where JSON traces will be stored.
        """
        self.storage_dir = Path(storage_dir)
        self._lock = threading.RLock()
        self._cache: Dict[str, ReasoningTrace] = {}
        
        self._initialize_storage()
        self._load_all_traces_into_cache()

    def _initialize_storage(self) -> None:
        """Creates the storage directory if it does not exist."""
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"TraceRecorder initialized. Storage directory: {self.storage_dir}")
        except Exception as e:
            logger.critical(f"Failed to create trace storage directory {self.storage_dir}: {e}")
            raise TraceStorageError(f"Initialization failed: {e}")

    def _load_all_traces_into_cache(self) -> None:
        """Loads all existing traces from disk into memory for fast querying."""
        with self._lock:
            self._cache.clear()
            if not self.storage_dir.exists():
                return

            for file_path in self.storage_dir.glob("*.json"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        trace = ReasoningTrace.from_dict(data)
                        self._cache[trace.trace_id] = trace
                except json.JSONDecodeError:
                    logger.error(f"Corrupted trace file found and skipped: {file_path}")
                except Exception as e:
                    logger.error(f"Error loading trace {file_path}: {e}")
            
            logger.info(f"Loaded {len(self._cache)} reasoning traces into memory cache.")

    def record_trace(
        self,
        topic: str,
        question: str,
        reasoning_steps: List[Union[Dict[str, Any], ReasoningStep]],
        conclusion: str,
        sources: List[Union[Dict[str, Any], Source]],
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Records a new reasoning trace and persists it to disk.

        Args:
            topic: Broad category or subject of the reasoning.
            question: The specific query or objective being analyzed.
            reasoning_steps: List of steps taken to reach the conclusion.
            conclusion: The final synthesized answer or finding.
            sources: List of evidence sources used.
            tags: Optional list of tags for easier filtering.
            metadata: Optional dictionary for extended machine-readable context.

        Returns:
            str: The unique trace_id of the recorded trace.
        """
        trace_id = f"trace_{uuid4().hex[:12]}"
        
        # Normalize steps
        normalized_steps = []
        for step in reasoning_steps:
            if isinstance(step, dict):
                normalized_steps.append(ReasoningStep.from_dict(step))
            elif isinstance(step, ReasoningStep):
                normalized_steps.append(step)
            else:
                raise ValueError("reasoning_steps must be a list of dicts or ReasoningStep objects.")

        # Normalize sources
        normalized_sources = []
        for source in sources:
            if isinstance(source, dict):
                normalized_sources.append(Source.from_dict(source))
            elif isinstance(source, Source):
                normalized_sources.append(source)
            else:
                raise ValueError("sources must be a list of dicts or Source objects.")

        trace = ReasoningTrace(
            trace_id=trace_id,
            topic=topic,
            question=question,
            reasoning_steps=normalized_steps,
            conclusion=conclusion,
            sources=normalized_sources,
            tags=tags or [],
            metadata=metadata or {}
        )

        self._save_trace(trace)
        return trace_id

    def _save_trace(self, trace: ReasoningTrace) -> None:
        """Internal method to save a trace to disk and update cache."""
        file_path = self.storage_dir / f"{trace.trace_id}.json"
        
        with self._lock:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(trace.to_dict(), f, indent=4, ensure_ascii=False)
                self._cache[trace.trace_id] = trace
                logger.debug(f"Successfully saved trace {trace.trace_id} to {file_path}")
            except Exception as e:
                logger.error(f"Failed to save trace {trace.trace_id}: {e}")
                raise TraceStorageError(f"Could not save trace: {e}")

    def get_trace(self, trace_id: str) -> ReasoningTrace:
        """
        Retrieves a specific reasoning trace by its ID.

        Args:
            trace_id: The unique identifier of the trace.

        Returns:
            ReasoningTrace: The requested trace.

        Raises:
            TraceNotFoundError: If the trace does not exist.
        """
        with self._lock:
            trace = self._cache.get(trace_id)
            if not trace:
                raise TraceNotFoundError(f"Trace with ID {trace_id} not found.")
            return trace

    def search_by_topic(self, topic: str, exact_match: bool = False) -> List[ReasoningTrace]:
        """
        Finds all traces matching a specific topic.

        Args:
            topic: The topic string to search for.
            exact_match: If True, requires exact string match. If False, does a case-insensitive substring match.

        Returns:
            List[ReasoningTrace]: Traces matching the topic.
        """
        results = []
        with self._lock:
            for trace in self._cache.values():
                if exact_match:
                    if trace.topic.lower() == topic.lower():
                        results.append(trace)
                else:
                    if topic.lower() in trace.topic.lower():
                        results.append(trace)
        
        # Sort by newest first
        return sorted(results, key=lambda t: t.created_at, reverse=True)

    def search_by_keyword(self, keyword: str) -> List[ReasoningTrace]:
        """
        Performs a deep search across questions, conclusions, and reasoning steps for a keyword.

        Args:
            keyword: The search term.

        Returns:
            List[ReasoningTrace]: Traces containing the keyword.
        """
        results = []
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        
        with self._lock:
            for trace in self._cache.values():
                # Check top level fields
                if pattern.search(trace.question) or pattern.search(trace.conclusion) or pattern.search(trace.topic):
                    results.append(trace)
                    continue
                
                # Check steps
                step_match = False
                for step in trace.reasoning_steps:
                    if pattern.search(step.description) or (step.logic_applied and pattern.search(step.logic_applied)):
                        step_match = True
                        break
                
                if step_match:
                    results.append(trace)
                    continue
                    
                # Check tags
                if any(pattern.search(tag) for tag in trace.tags):
                    results.append(trace)

        return sorted(results, key=lambda t: t.created_at, reverse=True)

    def export_to_markdown(self, trace_id: str, output_path: Union[str, Path]) -> str:
        """
        Exports a specific trace to a Markdown file.

        Args:
            trace_id: The ID of the trace to export.
            output_path: The file path where the markdown should be saved.

        Returns:
            str: The absolute path to the exported file.
        """
        trace = self.get_trace(trace_id)
        out_file = Path(output_path)
        
        try:
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, 'w', encoding='utf-8') as f:
                f.write(trace.to_markdown())
            logger.info(f"Exported trace {trace_id} to Markdown: {out_file.absolute()}")
            return str(out_file.absolute())
        except Exception as e:
            logger.error(f"Failed to export trace {trace_id} to Markdown: {e}")
            raise TraceStorageError(f"Export failed: {e}")

    def export_to_json(self, trace_id: str, output_path: Union[str, Path]) -> str:
        """
        Exports a specific trace to a standalone JSON file.

        Args:
            trace_id: The ID of the trace to export.
            output_path: The file path where the JSON should be saved.

        Returns:
            str: The absolute path to the exported file.
        """
        trace = self.get_trace(trace_id)
        out_file = Path(output_path)
        
        try:
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, 'w', encoding='utf-8') as f:
                json.dump(trace.to_dict(), f, indent=4, ensure_ascii=False)
            logger.info(f"Exported trace {trace_id} to JSON: {out_file.absolute()}")
            return str(out_file.absolute())
        except Exception as e:
            logger.error(f"Failed to export trace {trace_id} to JSON: {e}")
            raise TraceStorageError(f"Export failed: {e}")

    def export_corpus_to_json(self, output_path: Union[str, Path], topic: Optional[str] = None) -> str:
        """
        Exports multiple traces as a single JSON array, suitable for machine-readable
        corpus ingestion (e.g., fine-tuning, RAG indexing).

        Args:
            output_path: The file path for the corpus JSON file.
            topic: If provided, only exports traces matching this topic.

        Returns:
            str: The absolute path to the exported corpus file.
        """
        out_file = Path(output_path)
        
        with self._lock:
            if topic:
                traces = self.search_by_topic(topic)
            else:
                traces = list(self._cache.values())
                
            corpus_data = [trace.to_dict() for trace in traces]

        try:
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, 'w', encoding='utf-8') as f:
                json.dump(corpus_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Exported corpus containing {len(corpus_data)} traces to {out_file.absolute()}")
            return str(out_file.absolute())
        except Exception as e:
            logger.error(f"Failed to export trace corpus to JSON: {e}")
            raise TraceStorageError(f"Corpus export failed: {e}")

    def delete_trace(self, trace_id: str) -> bool:
        """
        Deletes a reasoning trace from both memory and disk.

        Args:
            trace_id: The ID of the trace to delete.

        Returns:
            bool: True if deleted successfully, False if trace was not found.
        """
        with self._lock:
            if trace_id not in self._cache:
                logger.warning(f"Attempted to delete non-existent trace: {trace_id}")
                return False

            file_path = self.storage_dir / f"{trace_id}.json"
            try:
                if file_path.exists():
                    file_path.unlink()
                del self._cache[trace_id]
                logger.info(f"Deleted trace {trace_id}")
                return True
            except Exception as e:
                logger.error(f"Error deleting trace {trace_id}: {e}")
                raise TraceStorageError(f"Deletion failed: {e}")