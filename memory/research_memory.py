"""
Nex Research Memory Engine

This module provides a persistent, append-only memory layer for the Nex Autonomous
Research Agent. It is designed to store reasoning chains, insights, and conclusions
generated during deep research sessions. The stored data can later be exported to
feed the Zayvora corpus or reconstructed to view the evolutionary timeline of a
specific research topic.

Features:
- Append-only file-based storage (JSON/JSONL) to prevent data loss.
- Atomic write operations to ensure storage integrity.
- Dataclass-based strict schema for memory records.
- Advanced retrieval API (by topic, keyword, confidence, date range).
- Timeline reconstruction for tracking research evolution.
- JSON and Markdown export capabilities.
- Full CLI interface for interacting with the memory store.

Usage (CLI):
    python research_memory.py append --topic "Quantum Gravity" --reasoning "Step 1..." "Step 2..." --conclusion "It's complex." --confidence 0.85
    python research_memory.py query --keyword "Gravity"
    python research_memory.py timeline --topic "Quantum Gravity"
    python research_memory.py export --format markdown --output memory_dump.md
"""

import os
import json
import uuid
import logging
import argparse
import tempfile
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Union

# =============================================================================
# Logging Configuration
# =============================================================================

logger = logging.getLogger("nex.memory.research_memory")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# =============================================================================
# Exceptions
# =============================================================================

class ResearchMemoryError(Exception):
    """Base exception for Research Memory Engine errors."""
    pass

class MemoryStorageError(ResearchMemoryError):
    """Raised when there is an issue reading or writing to the storage medium."""
    pass

class RecordValidationError(ResearchMemoryError):
    """Raised when a memory record fails validation checks."""
    pass

# =============================================================================
# Data Models
# =============================================================================

@dataclass
class MemoryRecord:
    """
    Represents a single discrete unit of research memory, capturing the reasoning
    process and the final conclusion derived by the Nex agent.
    """
    topic: str
    conclusion: str
    reasoning_chain: List[str] = field(default_factory=list)
    confidence: float = 0.0
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def __post_init__(self):
        """Validates the data types and constraints after initialization."""
        if not isinstance(self.topic, str) or not self.topic.strip():
            raise RecordValidationError("Topic must be a non-empty string.")
        if not isinstance(self.conclusion, str) or not self.conclusion.strip():
            raise RecordValidationError("Conclusion must be a non-empty string.")
        if not isinstance(self.reasoning_chain, list):
            raise RecordValidationError("Reasoning chain must be a list of strings.")
        if not (0.0 <= self.confidence <= 1.0):
            raise RecordValidationError("Confidence must be a float between 0.0 and 1.0.")

    def to_dict(self) -> Dict[str, Any]:
        """Converts the MemoryRecord to a dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryRecord":
        """
        Creates a MemoryRecord instance from a dictionary.
        
        Args:
            data (Dict[str, Any]): The dictionary containing record data.
            
        Returns:
            MemoryRecord: The instantiated record.
        """
        try:
            return cls(
                topic=data["topic"],
                conclusion=data["conclusion"],
                reasoning_chain=data.get("reasoning_chain", []),
                confidence=float(data.get("confidence", 0.0)),
                record_id=data.get("record_id", str(uuid.uuid4())),
                timestamp=data.get("timestamp", datetime.utcnow().isoformat() + "Z")
            )
        except KeyError as e:
            raise RecordValidationError(f"Missing required field in record data: {e}")
        except ValueError as e:
            raise RecordValidationError(f"Invalid data format in record data: {e}")

# =============================================================================
# Core Engine
# =============================================================================

class MemoryStore:
    """
    Manages the persistent, append-only storage of research memory records.
    Provides APIs for appending, retrieving, and exporting research timelines.
    """

    def __init__(self, storage_path: Optional[Union[str, Path]] = None):
        """
        Initializes the MemoryStore.

        Args:
            storage_path (Optional[Union[str, Path]]): Path to the JSON storage file.
                Defaults to '~/.nex/research_memory.json'.
        """
        if storage_path is None:
            home_dir = Path.home()
            self.storage_path = home_dir / ".nex" / "research_memory.json"
        else:
            self.storage_path = Path(storage_path)

        self._ensure_storage_exists()
        self._records: List[MemoryRecord] = self._load_memory()

    def _ensure_storage_exists(self) -> None:
        """Ensures the directory and storage file exist."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.storage_path.exists():
                logger.info(f"Creating new memory storage at {self.storage_path}")
                self._atomic_write([])
        except Exception as e:
            raise MemoryStorageError(f"Failed to initialize storage at {self.storage_path}: {e}")

    def _atomic_write(self, data: List[Dict[str, Any]]) -> None:
        """
        Writes data to the storage file atomically to prevent corruption during crashes.
        
        Args:
            data (List[Dict[str, Any]]): The serialized records to write.
        """
        try:
            fd, temp_path = tempfile.mkstemp(dir=self.storage_path.parent, prefix=".tmp_memory_")
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            
            # Atomic replace
            os.replace(temp_path, self.storage_path)
        except Exception as e:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
            raise MemoryStorageError(f"Failed to write memory data atomically: {e}")

    def _load_memory(self) -> List[MemoryRecord]:
        """
        Loads memory records from the persistent storage.
        
        Returns:
            List[MemoryRecord]: List of loaded memory records.
        """
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, list):
                    logger.warning("Storage file format invalid (not a list). Resetting memory.")
                    return []
                
                records = []
                for item in data:
                    try:
                        records.append(MemoryRecord.from_dict(item))
                    except RecordValidationError as ve:
                        logger.warning(f"Skipping invalid record during load: {ve}")
                
                logger.debug(f"Loaded {len(records)} records from {self.storage_path}")
                return records
        except json.JSONDecodeError:
            logger.error("Storage file is corrupted (invalid JSON). Starting with empty memory.")
            return []
        except Exception as e:
            raise MemoryStorageError(f"Failed to load memory data: {e}")

    def _save_memory(self) -> None:
        """Serializes and saves the current state of memory to disk."""
        data = [record.to_dict() for record in self._records]
        self._atomic_write(data)

    def append_record(self, topic: str, reasoning_chain: List[str], conclusion: str, confidence: float = 0.0) -> MemoryRecord:
        """
        Appends a new research record to the memory store.
        (Append-only operation: existing records are never modified or deleted).

        Args:
            topic (str): The subject of the research.
            reasoning_chain (List[str]): Steps taken to reach the conclusion.
            conclusion (str): The final insight or fact derived.
            confidence (float): Confidence score (0.0 to 1.0).

        Returns:
            MemoryRecord: The newly created and stored record.
        """
        record = MemoryRecord(
            topic=topic,
            reasoning_chain=reasoning_chain,
            conclusion=conclusion,
            confidence=confidence
        )
        self._records.append(record)
        self._save_memory()
        logger.info(f"Appended new memory record for topic: '{topic}' (ID: {record.record_id})")
        return record

    def search_by_topic(self, topic: str, exact: bool = False) -> List[MemoryRecord]:
        """
        Retrieves memory records matching a specific topic.

        Args:
            topic (str): The topic to search for.
            exact (bool): If True, requires exact match. If False, does a substring match.

        Returns:
            List[MemoryRecord]: Matching records.
        """
        results = []
        search_term = topic.lower()
        for record in self._records:
            record_topic = record.topic.lower()
            if exact and record_topic == search_term:
                results.append(record)
            elif not exact and search_term in record_topic:
                results.append(record)
        return results

    def search_by_keyword(self, keyword: str, min_confidence: float = 0.0) -> List[MemoryRecord]:
        """
        Retrieves memory records containing a specific keyword anywhere in the
        topic, reasoning chain, or conclusion.

        Args:
            keyword (str): The keyword to search for.
            min_confidence (float): Minimum confidence threshold for results.

        Returns:
            List[MemoryRecord]: Matching records.
        """
        results = []
        search_term = keyword.lower()
        for record in self._records:
            if record.confidence < min_confidence:
                continue
            
            searchable_text = (
                record.topic + " " + 
                record.conclusion + " " + 
                " ".join(record.reasoning_chain)
            ).lower()
            
            if search_term in searchable_text:
                results.append(record)
        return results

    def get_timeline(self, topic: Optional[str] = None) -> List[MemoryRecord]:
        """
        Reconstructs the research evolution timeline. Sorts records chronologically.

        Args:
            topic (Optional[str]): If provided, filters timeline to a specific topic.

        Returns:
            List[MemoryRecord]: Chronologically sorted list of records.
        """
        records = self._records
        if topic:
            records = self.search_by_topic(topic, exact=False)
        
        # Sort by timestamp ascending
        return sorted(records, key=lambda r: r.timestamp)

    def export_to_json(self, filepath: Union[str, Path]) -> None:
        """
        Exports the entire memory store to a specified JSON file.
        Useful for feeding the Zayvora corpus.

        Args:
            filepath (Union[str, Path]): Destination file path.
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [record.to_dict() for record in self._records]
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logger.info(f"Exported memory store to JSON: {path}")

    def export_to_markdown(self, filepath: Union[str, Path]) -> None:
        """
        Exports the memory store to a human-readable Markdown file.
        Groups by topic and constructs a narrative timeline.

        Args:
            filepath (Union[str, Path]): Destination file path.
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Group records by topic
        grouped_records: Dict[str, List[MemoryRecord]] = {}
        for record in self._records:
            grouped_records.setdefault(record.topic, []).append(record)
            
        with open(path, 'w', encoding='utf-8') as f:
            f.write("# Nex Research Memory Timeline\n\n")
            f.write(f"*Generated on: {datetime.utcnow().isoformat()}Z*\n\n")
            f.write("---\n\n")
            
            for topic, records in grouped_records.items():
                f.write(f"## Topic: {topic}\n\n")
                # Sort chronologically within the topic
                records.sort(key=lambda r: r.timestamp)
                
                for r in records:
                    f.write(f"### Record ID: `{r.record_id}`\n")
                    f.write(f"**Timestamp:** {r.timestamp}  \n")
                    f.write(f"**Confidence:** {r.confidence:.2f}\n\n")
                    
                    f.write("**Reasoning Chain:**\n")
                    if r.reasoning_chain:
                        for step in r.reasoning_chain:
                            f.write(f"- {step}\n")
                    else:
                        f.write("- *No reasoning steps recorded.*\n")
                    f.write("\n")
                    
                    f.write(f"**Conclusion:**\n> {r.conclusion}\n\n")
                    f.write("---\n\n")
                    
        logger.info(f"Exported memory store to Markdown: {path}")

# =============================================================================
# CLI Interface
# =============================================================================

def main():
    """Command Line Interface for the Nex Research Memory Engine."""
    parser = argparse.ArgumentParser(
        description="Nex Research Memory Engine - Persistent append-only memory layer."
    )
    parser.add_argument(
        "--store", 
        type=str, 
        help="Path to the memory storage JSON file. Defaults to ~/.nex/research_memory.json",
        default=None
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Append Command
    append_parser = subparsers.add_parser("append", help="Append a new memory record")
    append_parser.add_argument("--topic", type=str, required=True, help="Research topic")
    append_parser.add_argument("--reasoning", type=str, nargs='+', required=True, help="Reasoning steps (multiple allowed)")
    append_parser.add_argument("--conclusion", type=str, required=True, help="Final conclusion/insight")
    append_parser.add_argument("--confidence", type=float, default=1.0, help="Confidence score (0.0 to 1.0)")

    # Query Command
    query_parser = subparsers.add_parser("query", help="Search memory records")
    query_group = query_parser.add_mutually_exclusive_group(required=True)
    query_group.add_argument("--topic", type=str, help="Search by topic")
    query_group.add_argument("--keyword", type=str, help="Search by keyword across all fields")
    query_parser.add_argument("--min-confidence", type=float, default=0.0, help="Minimum confidence threshold")

    # Timeline Command
    timeline_parser = subparsers.add_parser("timeline", help="Reconstruct research timeline")
    timeline_parser.add_argument("--topic", type=str, help="Filter timeline by topic", default=None)

    # Export Command
    export_parser = subparsers.add_parser("export", help="Export memory store")
    export_parser.add_argument("--format", type=str, choices=['json', 'markdown'], required=True, help="Export format")
    export_parser.add_argument("--output", type=str, required=True, help="Output file path")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        memory_store = MemoryStore(storage_path=args.store)

        if args.command == "append":
            record = memory_store.append_record(
                topic=args.topic,
                reasoning_chain=args.reasoning,
                conclusion=args.conclusion,
                confidence=args.confidence
            )
            print(f"Successfully appended record: {record.record_id}")

        elif args.command == "query":
            if args.topic:
                results = memory_store.search_by_topic(args.topic)
            else:
                results = memory_store.search_by_keyword(args.keyword, min_confidence=args.min_confidence)
            
            print(f"Found {len(results)} matching records:")
            for r in results:
                print(json.dumps(r.to_dict(), indent=2))

        elif args.command == "timeline":
            timeline = memory_store.get_timeline(topic=args.topic)
            print(f"Timeline reconstruction ({len(timeline)} records):")
            for r in timeline:
                print(f"[{r.timestamp}] [Conf: {r.confidence:.2f}] {r.topic} -> {r.conclusion[:50]}...")

        elif args.command == "export":
            if args.format == 'json':
                memory_store.export_to_json(args.output)
            elif args.format == 'markdown':
                memory_store.export_to_markdown(args.output)
            print(f"Successfully exported memory to {args.output}")

    except ResearchMemoryError as e:
        logger.error(f"Memory Engine Error: {e}")
        exit(1)
    except Exception as e:
        logger.error(f"Unexpected Error: {e}")
        exit(1)

if __name__ == "__main__":
    main()