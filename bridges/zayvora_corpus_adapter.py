#!/usr/bin/env python3
"""
Zayvora Corpus Adapter
======================

This module serves as the primary bridge between the Nex Deep Research Engine's
distilled research outputs and the Zayvora knowledge corpus. It handles the 
transformation, deduplication, incremental updating, and export of autonomous 
research data into a structured format optimized for downstream retrieval systems 
(e.g., RAG pipelines, vector databases, and knowledge graphs).

Key Features:
- Structured `CorpusEntry` dataclass for strict schema validation.
- Incremental updates with intelligent merging of claims, evidence, and sources.
- Robust JSON/JSONL exporting for retrieval system compatibility.
- Command-Line Interface (CLI) for automated corpus synchronization.

Usage:
    python bridges/zayvora_corpus_adapter.py sync --input-dir ./research_outputs --corpus ./zayvora_corpus.json
    python bridges/zayvora_corpus_adapter.py export --corpus ./zayvora_corpus.json --output ./export.jsonl --format jsonl
"""

import os
import sys
import json
import uuid
import logging
import argparse
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Set, Union


# =============================================================================
# Logging Configuration
# =============================================================================

def setup_logger() -> logging.Logger:
    """Configures and returns a production-ready logger for the adapter."""
    logger = logging.getLogger("ZayvoraCorpusAdapter")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

logger = setup_logger()


# =============================================================================
# Custom Exceptions
# =============================================================================

class ZayvoraAdapterError(Exception):
    """Base exception for all Zayvora Corpus Adapter errors."""
    pass

class CorpusLoadError(ZayvoraAdapterError):
    """Raised when the corpus file cannot be read or parsed."""
    pass

class CorpusSaveError(ZayvoraAdapterError):
    """Raised when the corpus file cannot be written to disk."""
    pass

class IngestionError(ZayvoraAdapterError):
    """Raised when a research output fails to map to the Zayvora schema."""
    pass


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class CorpusEntry:
    """
    Represents a single conceptual entity within the Zayvora knowledge corpus.
    Aggregates claims, evidence, insights, and sources around a unified concept.
    """
    concept: str
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    claims: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    
    def merge(self, other: 'CorpusEntry') -> None:
        """
        Incrementally updates the current entry by merging data from another entry.
        Deduplicates claims, evidence, insights, and sources while preserving order.
        
        Args:
            other (CorpusEntry): The new entry data to merge into this one.
        """
        if self.concept.lower() != other.concept.lower():
            logger.warning(
                f"Attempting to merge mismatched concepts: '{self.concept}' and '{other.concept}'. "
                "Proceeding, but this may indicate an upstream routing error."
            )

        def deduplicate_append(target_list: List[str], new_items: List[str]) -> None:
            existing = set(target_list)
            for item in new_items:
                if item not in existing:
                    target_list.append(item)
                    existing.add(item)

        deduplicate_append(self.claims, other.claims)
        deduplicate_append(self.evidence, other.evidence)
        deduplicate_append(self.insights, other.insights)
        deduplicate_append(self.sources, other.sources)
        
        self.updated_at = datetime.utcnow().isoformat() + "Z"
        logger.debug(f"Merged updates into concept: {self.concept}")

    def to_dict(self) -> Dict[str, Any]:
        """Converts the dataclass instance to a dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CorpusEntry':
        """
        Instantiates a CorpusEntry from a dictionary, ensuring safe fallback 
        for missing fields.
        """
        return cls(
            concept=data.get("concept", "Unknown Concept"),
            entry_id=data.get("entry_id", str(uuid.uuid4())),
            claims=data.get("claims", []),
            evidence=data.get("evidence", []),
            insights=data.get("insights", []),
            sources=data.get("sources", []),
            created_at=data.get("created_at", datetime.utcnow().isoformat() + "Z"),
            updated_at=data.get("updated_at", datetime.utcnow().isoformat() + "Z")
        )


# =============================================================================
# Core Adapter Logic
# =============================================================================

class ZayvoraCorpusAdapter:
    """
    Manages the lifecycle, synchronization, and transformation of Nex research 
    outputs into the Zayvora Knowledge Corpus.
    """
    
    def __init__(self, corpus_filepath: str):
        """
        Initializes the adapter.
        
        Args:
            corpus_filepath (str): Path to the master JSON file storing the corpus.
        """
        self.corpus_filepath = corpus_filepath
        self.corpus: Dict[str, CorpusEntry] = {}
        self._load_corpus()

    def _load_corpus(self) -> None:
        """
        Loads the existing corpus from disk into memory. 
        If the file does not exist, initializes an empty corpus.
        """
        if not os.path.exists(self.corpus_filepath):
            logger.info(f"Corpus file not found at {self.corpus_filepath}. Initializing new corpus.")
            self.corpus = {}
            return

        try:
            with open(self.corpus_filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if not isinstance(data, dict):
                raise ValueError("Corpus root must be a JSON object mapping concept strings to entry data.")
                
            for concept_key, entry_data in data.items():
                self.corpus[concept_key] = CorpusEntry.from_dict(entry_data)
                
            logger.info(f"Successfully loaded {len(self.corpus)} concepts from {self.corpus_filepath}.")
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from {self.corpus_filepath}: {e}")
            raise CorpusLoadError(f"Invalid JSON format: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading corpus: {e}")
            raise CorpusLoadError(f"Error loading corpus: {e}")

    def save_corpus(self) -> None:
        """
        Persists the in-memory corpus to disk atomically to prevent data corruption.
        """
        temp_filepath = f"{self.corpus_filepath}.tmp"
        try:
            # Convert objects to dicts
            serializable_corpus = {
                concept: entry.to_dict() 
                for concept, entry in self.corpus.items()
            }
            
            with open(temp_filepath, 'w', encoding='utf-8') as f:
                json.dump(serializable_corpus, f, indent=2, ensure_ascii=False)
                
            # Atomic replace
            os.replace(temp_filepath, self.corpus_filepath)
            logger.info(f"Successfully saved {len(self.corpus)} concepts to {self.corpus_filepath}.")
            
        except Exception as e:
            logger.error(f"Failed to save corpus to {self.corpus_filepath}: {e}")
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
            raise CorpusSaveError(f"Error saving corpus: {e}")

    def ingest_research_output(self, research_data: Dict[str, Any]) -> int:
        """
        Parses a single Nex research output dictionary and merges its findings 
        into the Zayvora corpus.
        
        Expected Nex Input Schema (simplified):
        {
            "report_id": "...",
            "findings": [
                {
                    "concept": "Quantum Entanglement",
                    "claims": [...],
                    "evidence": [...],
                    "insights": [...],
                    "sources": [...]
                }
            ]
        }
        
        Args:
            research_data (Dict[str, Any]): The distilled research output from Nex.
            
        Returns:
            int: The number of concepts updated or added.
        """
        findings = research_data.get("findings", [])
        if not findings:
            logger.warning("Research data contains no 'findings'. Skipping ingestion.")
            return 0
            
        updates_count = 0
        
        for finding in findings:
            concept = finding.get("concept")
            if not concept:
                logger.warning("Finding missing 'concept' field. Skipping.")
                continue
                
            # Normalize concept key (lowercase, strip whitespace) for consistent mapping
            concept_key = concept.strip().lower()
            
            # Create a new entry from the finding
            new_entry = CorpusEntry(
                concept=concept.strip(),
                claims=finding.get("claims", []),
                evidence=finding.get("evidence", []),
                insights=finding.get("insights", []),
                sources=finding.get("sources", [])
            )
            
            if concept_key in self.corpus:
                # Incremental Update: Merge with existing concept
                self.corpus[concept_key].merge(new_entry)
                logger.debug(f"Merged new research into existing concept: {concept}")
            else:
                # Add new concept
                self.corpus[concept_key] = new_entry
                logger.debug(f"Added new concept to corpus: {concept}")
                
            updates_count += 1
            
        return updates_count

    def sync_directory(self, input_dir: str) -> None:
        """
        Scans a directory for Nex research output JSON files and ingests them all.
        
        Args:
            input_dir (str): Directory containing `.json` research reports.
        """
        if not os.path.isdir(input_dir):
            logger.error(f"Input directory does not exist: {input_dir}")
            raise FileNotFoundError(f"Directory not found: {input_dir}")
            
        json_files = [f for f in os.listdir(input_dir) if f.endswith('.json')]
        logger.info(f"Found {len(json_files)} JSON files in {input_dir} for sync.")
        
        total_ingested = 0
        for filename in json_files:
            filepath = os.path.join(input_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    research_data = json.load(f)
                    
                updates = self.ingest_research_output(research_data)
                total_ingested += updates
                logger.info(f"Processed {filename}: {updates} concepts updated/added.")
                
            except json.JSONDecodeError:
                logger.error(f"Skipping {filename}: Invalid JSON format.")
            except Exception as e:
                logger.error(f"Error processing {filename}: {e}")
                
        if total_ingested > 0:
            self.save_corpus()
            logger.info(f"Sync complete. {total_ingested} total concept updates applied.")
        else:
            logger.info("Sync complete. No new data ingested.")

    def export_for_retrieval(self, export_path: str, format_type: str = "jsonl") -> None:
        """
        Exports the corpus into a format optimized for downstream retrieval systems 
        (e.g., Elasticsearch, Pinecone, HuggingFace Datasets).
        
        Args:
            export_path (str): The destination file path.
            format_type (str): The export format ('jsonl' or 'json'). Defaults to 'jsonl'.
        """
        logger.info(f"Exporting corpus to {export_path} in {format_type.upper()} format...")
        
        try:
            os.makedirs(os.path.dirname(os.path.abspath(export_path)), exist_ok=True)
            
            if format_type.lower() == "jsonl":
                with open(export_path, 'w', encoding='utf-8') as f:
                    for entry in self.corpus.values():
                        f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + '\n')
            
            elif format_type.lower() == "json":
                export_data = [entry.to_dict() for entry in self.corpus.values()]
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                    
            else:
                raise ValueError(f"Unsupported export format: {format_type}. Use 'json' or 'jsonl'.")
                
            logger.info(f"Export complete. {len(self.corpus)} entries written to {export_path}.")
            
        except Exception as e:
            logger.error(f"Failed to export corpus: {e}")
            raise


# =============================================================================
# CLI Orchestration
# =============================================================================

def build_cli_parser() -> argparse.ArgumentParser:
    """Builds and returns the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        description="Zayvora Corpus Adapter: Bridge Nex research outputs with the Zayvora knowledge corpus.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")
    
    # Sync Command
    sync_parser = subparsers.add_parser(
        "sync", 
        help="Synchronize a directory of Nex research outputs into the corpus."
    )
    sync_parser.add_argument(
        "--input-dir", 
        type=str, 
        required=True, 
        help="Path to the directory containing Nex research JSON files."
    )
    sync_parser.add_argument(
        "--corpus", 
        type=str, 
        default="zayvora_corpus.json", 
        help="Path to the Zayvora master corpus JSON file (default: zayvora_corpus.json)."
    )
    
    # Export Command
    export_parser = subparsers.add_parser(
        "export", 
        help="Export the Zayvora corpus for external retrieval systems (RAG, Vector DBs)."
    )
    export_parser.add_argument(
        "--corpus", 
        type=str, 
        default="zayvora_corpus.json", 
        help="Path to the Zayvora master corpus JSON file."
    )
    export_parser.add_argument(
        "--output", 
        type=str, 
        required=True, 
        help="Path where the exported file should be saved."
    )
    export_parser.add_argument(
        "--format", 
        type=str, 
        choices=["json", "jsonl"], 
        default="jsonl", 
        help="Export format: 'jsonl' (JSON Lines, best for massive datasets) or 'json' (default: jsonl)."
    )
    
    return parser


def main() -> None:
    """Main execution entry point for the CLI."""
    parser = build_cli_parser()
    args = parser.parse_args()
    
    try:
        if args.command == "sync":
            adapter = ZayvoraCorpusAdapter(corpus_filepath=args.corpus)
            adapter.sync_directory(input_dir=args.input_dir)
            
        elif args.command == "export":
            adapter = ZayvoraCorpusAdapter(corpus_filepath=args.corpus)
            if not adapter.corpus:
                logger.warning("Corpus is empty. Exporting an empty dataset.")
            adapter.export_for_retrieval(export_path=args.output, format_type=args.format)
            
    except Exception as e:
        logger.error(f"Process failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()