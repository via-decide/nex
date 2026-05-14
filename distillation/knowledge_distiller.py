#!/usr/bin/env python3
"""
Knowledge Distiller Engine for Nex.

This module provides a lightweight, heuristic-based pipeline to transform unstructured 
research notes, PDFs, and articles into structured reasoning units. It extracts key concepts, 
declarative claims, and supporting evidence, synthesizing them into `DistilledConcept` objects.
These objects are highly compatible with the Zayvora corpus format.

Features:
- ConceptExtractor: Identifies technical concepts using NLP heuristics and regex patterns.
- ClaimDetector: Extracts declarative claims based on linguistic markers.
- EvidenceMatcher: Links claims to statistical, empirical, or citation-backed evidence.
- InsightSynthesizer: Generates cohesive insights from claim-evidence clusters.
- CorpusFormatter: Exports distilled knowledge to Zayvora JSON, Markdown cards, and Graph Nodes.
- CLI Interface: Supports file, directory, and standard input processing.

Usage:
    python knowledge_distiller.py --input raw_research.txt --format json --output distilled.json
"""

import argparse
import dataclasses
import datetime
import json
import logging
import os
import re
import sys
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("KnowledgeDistiller")

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclasses.dataclass
class DistilledConcept:
    """
    Represents a structured reasoning unit distilled from raw research text.
    Designed for compatibility with the Zayvora corpus.
    """
    concept: str
    claims: List[str]
    evidence: List[str]
    sources: List[str]
    tags: List[str]
    created_at: str
    
    # Additional fields for internal tracking and graph generation
    concept_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))
    insight_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Converts the dataclass to a dictionary."""
        return dataclasses.asdict(self)


# =============================================================================
# TEXT PROCESSING UTILITIES
# =============================================================================

class TextUtils:
    """Utility class for common text preprocessing and tokenization tasks."""

    # Regex to split text into sentences while ignoring common abbreviations
    SENTENCE_SPLIT_REGEX = re.compile(
        r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s'
    )

    @staticmethod
    def clean_text(text: str) -> str:
        """Removes excessive whitespace and normalizes text."""
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @staticmethod
    def extract_sentences(text: str) -> List[str]:
        """Splits text into a list of sentences using heuristic regex."""
        cleaned = TextUtils.clean_text(text)
        sentences = TextUtils.SENTENCE_SPLIT_REGEX.split(cleaned)
        return [s.strip() for s in sentences if len(s.strip()) > 10]


# =============================================================================
# PIPELINE COMPONENTS
# =============================================================================

class ConceptExtractor:
    """
    Identifies key technical concepts using pattern heuristics.
    Looks for capitalized phrases, acronyms, and domain-specific terminology.
    """
    
    def __init__(self):
        # Matches Title Case phrases (e.g., "Quantum Computing", "Large Language Models")
        self.title_case_pattern = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b')
        # Matches acronyms (e.g., "LLM", "TF-IDF", "NASA")
        self.acronym_pattern = re.compile(r'\b([A-Z]{2,}(?:-[A-Z]{2,})?)\b')
        # Matches specific noun phrases commonly found in research
        self.technical_suffix_pattern = re.compile(r'\b(\w+(?:ology|ization|ity|ism|ics|algorithm|framework|model|network))\b', re.IGNORECASE)

    def extract(self, text: str, top_k: int = 5) -> List[str]:
        """
        Extracts the most prominent concepts from the text.
        
        Args:
            text (str): The raw text to analyze.
            top_k (int): Number of top concepts to return.
            
        Returns:
            List[str]: A list of extracted concept strings.
        """
        try:
            concepts = []
            
            # Extract via heuristics
            concepts.extend(self.title_case_pattern.findall(text))
            concepts.extend(self.acronym_pattern.findall(text))
            concepts.extend(self.technical_suffix_pattern.findall(text))
            
            # Normalize and filter
            normalized = [c.lower().strip() for c in concepts if len(c) > 2]
            
            # Frequency counting to find the most relevant concepts
            counter = Counter(normalized)
            
            # Return the top_k most common concepts
            top_concepts = [item[0] for item in counter.most_common(top_k)]
            logger.debug(f"Extracted concepts: {top_concepts}")
            return top_concepts
            
        except Exception as e:
            logger.error(f"Error during concept extraction: {e}")
            return []


class ClaimDetector:
    """
    Extracts declarative claims from research text.
    Uses linguistic markers and active verbs to identify assertions.
    """
    
    def __init__(self):
        # Verbs that typically indicate a research claim or finding
        self.claim_verbs = [
            "demonstrates", "proves", "shows", "indicates", "suggests", 
            "results in", "leads to", "increases", "decreases", "improves",
            "outperforms", "establishes", "reveals", "concludes", "argues"
        ]
        self.claim_pattern = re.compile(r'\b(?:' + '|'.join(self.claim_verbs) + r')\b', re.IGNORECASE)

    def extract_claims(self, text: str) -> List[str]:
        """
        Finds sentences that make declarative claims.
        
        Args:
            text (str): Raw research text.
            
        Returns:
            List[str]: A list of sentence strings identified as claims.
        """
        claims = []
        try:
            sentences = TextUtils.extract_sentences(text)
            for sentence in sentences:
                if self.claim_pattern.search(sentence):
                    claims.append(sentence)
            logger.debug(f"Detected {len(claims)} claims.")
            return claims
        except Exception as e:
            logger.error(f"Error during claim detection: {e}")
            return []


class EvidenceMatcher:
    """
    Links claims with supporting evidence snippets.
    Evidence is identified via statistical markers, data references, or citations.
    """
    
    def __init__(self):
        # Patterns indicating evidence (numbers, percentages, citations like [1], (Smith, 2020))
        self.evidence_markers = re.compile(
            r'(\d+\.?\d*\s?%)|'                  # Percentages e.g. 95%
            r'(p\s?[<>=]\s?\d+\.\d+)|'           # p-values e.g. p < 0.05
            r'(\b(?:table|fig\.|figure)\s\d+)|'  # Data references
            r'(\[\d+\])|'                        # Bracket citations [1]
            r'(\([A-Za-z]+(?: et al\.)?, \d{4}\))', # Author-year citations
            re.IGNORECASE
        )

    def extract_evidence(self, text: str) -> List[str]:
        """Extracts all sentences containing evidence markers."""
        evidence = []
        sentences = TextUtils.extract_sentences(text)
        for sentence in sentences:
            if self.evidence_markers.search(sentence):
                evidence.append(sentence)
        return evidence

    def match(self, claims: List[str], text: str) -> Dict[str, List[str]]:
        """
        Matches claims to nearby or relevant evidence snippets.
        For this heuristic implementation, we associate all found evidence 
        with the general text context, but structure it for the claims.
        
        Args:
            claims (List[str]): Extracted claims.
            text (str): Source text.
            
        Returns:
            Dict[str, List[str]]: Mapping of claims to their supporting evidence.
        """
        try:
            all_evidence = self.extract_evidence(text)
            matched_evidence = {}
            
            # Heuristic: Assign evidence to the claim if they share vocabulary, 
            # otherwise just pool the evidence. 
            # For simplicity in this lightweight version, we pool relevant evidence.
            for claim in claims:
                claim_words = set(re.findall(r'\w+', claim.lower()))
                relevant = []
                for ev in all_evidence:
                    ev_words = set(re.findall(r'\w+', ev.lower()))
                    # Jaccard-like overlap
                    overlap = len(claim_words.intersection(ev_words))
                    if overlap > 2:  # Arbitrary threshold for relevance
                        relevant.append(ev)
                
                # Fallback: if no specific evidence matches, attach general evidence
                matched_evidence[claim] = relevant if relevant else all_evidence[:2]
                
            logger.debug(f"Matched evidence for {len(claims)} claims.")
            return matched_evidence
        except Exception as e:
            logger.error(f"Error during evidence matching: {e}")
            return {}


class InsightSynthesizer:
    """
    Generates distilled insights from claim-evidence clusters.
    Creates a cohesive summary string representing the core finding.
    """
    
    def synthesize(self, concept: str, claims: List[str], evidence_map: Dict[str, List[str]]) -> str:
        """
        Synthesizes a high-level insight.
        
        Args:
            concept (str): The main concept.
            claims (List[str]): Associated claims.
            evidence_map (Dict[str, List[str]]): Evidence mapped to claims.
            
        Returns:
            str: A synthesized insight paragraph.
        """
        try:
            if not claims:
                return f"Research notes regarding {concept} lack definitive claims."
                
            primary_claim = claims[0]
            supporting_ev = evidence_map.get(primary_claim, [])
            
            insight = f"Core finding on '{concept}': {primary_claim}"
            if supporting_ev:
                insight += f" This is supported by data indicating that: {supporting_ev[0]}"
                
            if len(claims) > 1:
                insight += f" Furthermore, research suggests: {claims[1]}"
                
            return insight
        except Exception as e:
            logger.error(f"Error during insight synthesis: {e}")
            return "Synthesis failed due to processing error."


# =============================================================================
# ORCHESTRATOR
# =============================================================================

class KnowledgeDistiller:
    """
    Main orchestration engine.
    Coordinates extraction, detection, matching, and synthesis.
    """
    
    def __init__(self):
        self.concept_extractor = ConceptExtractor()
        self.claim_detector = ClaimDetector()
        self.evidence_matcher = EvidenceMatcher()
        self.insight_synthesizer = InsightSynthesizer()

    def process_text(self, text: str, source_uri: str = "unknown") -> List[DistilledConcept]:
        """
        Processes raw text and distills it into structured reasoning units.
        
        Args:
            text (str): Raw unstructured text.
            source_uri (str): Identifier for the source material.
            
        Returns:
            List[DistilledConcept]: A list of distilled concepts.
        """
        logger.info(f"Distilling knowledge from source: {source_uri}")
        
        if not text or len(text.strip()) < 50:
            logger.warning("Text is too short for meaningful distillation.")
            return []

        distilled_results = []
        
        # 1. Extract Concepts
        concepts = self.concept_extractor.extract(text, top_k=3)
        if not concepts:
            concepts = ["General Research Finding"]
            
        # 2. Extract Claims
        all_claims = self.claim_detector.extract_claims(text)
        
        # 3. Match Evidence
        evidence_map = self.evidence_matcher.match(all_claims, text)
        
        # 4. Synthesize per concept (distributing claims heuristically)
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        
        for i, concept in enumerate(concepts):
            # Distribute claims among concepts based on simple chunking to avoid duplication
            chunk_size = max(1, len(all_claims) // len(concepts))
            start_idx = i * chunk_size
            end_idx = start_idx + chunk_size if i < len(concepts) - 1 else len(all_claims)
            
            concept_claims = all_claims[start_idx:end_idx]
            
            # Gather evidence for these specific claims
            concept_evidence = []
            for claim in concept_claims:
                concept_evidence.extend(evidence_map.get(claim, []))
            # Deduplicate evidence
            concept_evidence = list(dict.fromkeys(concept_evidence))
            
            # Synthesize insight
            insight = self.insight_synthesizer.synthesize(concept, concept_claims, evidence_map)
            
            # Build tags
            tags = [concept.lower().replace(" ", "-"), "distilled-insight"]
            
            distilled_obj = DistilledConcept(
                concept=concept,
                claims=concept_claims,
                evidence=concept_evidence,
                sources=[source_uri],
                tags=tags,
                created_at=timestamp,
                insight_summary=insight
            )
            distilled_results.append(distilled_obj)
            
        logger.info(f"Successfully distilled {len(distilled_results)} concepts.")
        return distilled_results


# =============================================================================
# FORMATTERS & EXPORTERS
# =============================================================================

class CorpusFormatter:
    """
    Converts distilled knowledge into various formats:
    - Zayvora-compatible JSON
    - Markdown knowledge cards
    - Graph Node format (Nodes & Edges)
    """

    @staticmethod
    def to_zayvora_json(concepts: List[DistilledConcept]) -> str:
        """
        Exports to a Zayvora corpus compatible JSON format.
        """
        payload = {
            "corpus_version": "1.0",
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
            "reasoning_units": [c.to_dict() for c in concepts]
        }
        return json.dumps(payload, indent=2)

    @staticmethod
    def to_markdown_cards(concepts: List[DistilledConcept]) -> str:
        """
        Exports to readable Markdown knowledge cards.
        """
        lines = ["# Distilled Knowledge Cards\n"]
        for c in concepts:
            lines.append(f"## Concept: {c.concept.title()}")
            lines.append(f"**ID:** `{c.concept_id}`")
            lines.append(f"**Date:** {c.created_at}")
            lines.append(f"**Tags:** {', '.join(c.tags)}\n")
            
            lines.append("### Insight")
            lines.append(f"> {c.insight_summary}\n")
            
            lines.append("### Key Claims")
            for claim in c.claims:
                lines.append(f"- {claim}")
            lines.append("")
            
            lines.append("### Supporting Evidence")
            for ev in c.evidence:
                lines.append(f"- *{ev}*")
            lines.append("")
            
            lines.append("### Sources")
            for src in c.sources:
                lines.append(f"- {src}")
            lines.append("\n---\n")
            
        return "\n".join(lines)

    @staticmethod
    def to_graph_nodes(concepts: List[DistilledConcept]) -> str:
        """
        Exports to a JSON format suitable for graph databases (Nodes and Edges).
        """
        nodes = []
        edges = []
        
        for c in concepts:
            # Concept Node
            nodes.append({
                "id": c.concept_id,
                "label": "Concept",
                "properties": {"name": c.concept, "summary": c.insight_summary}
            })
            
            # Claim Nodes and Edges
            for i, claim in enumerate(c.claims):
                claim_id = f"claim_{c.concept_id}_{i}"
                nodes.append({
                    "id": claim_id,
                    "label": "Claim",
                    "properties": {"text": claim}
                })
                edges.append({
                    "source": c.concept_id,
                    "target": claim_id,
                    "relationship": "HAS_CLAIM"
                })
                
            # Evidence Nodes and Edges
            for i, ev in enumerate(c.evidence):
                ev_id = f"ev_{c.concept_id}_{i}"
                nodes.append({
                    "id": ev_id,
                    "label": "Evidence",
                    "properties": {"text": ev}
                })
                edges.append({
                    "source": c.concept_id,
                    "target": ev_id,
                    "relationship": "SUPPORTED_BY"
                })
                
            # Source Nodes and Edges
            for i, src in enumerate(c.sources):
                src_id = f"src_{hash(src)}"
                nodes.append({
                    "id": src_id,
                    "label": "Source",
                    "properties": {"uri": src}
                })
                edges.append({
                    "source": c.concept_id,
                    "target": src_id,
                    "relationship": "DERIVED_FROM"
                })
                
        graph_data = {
            "nodes": nodes,
            "edges": edges
        }
        return json.dumps(graph_data, indent=2)


# =============================================================================
# CLI INTERFACE
# =============================================================================

def process_file(file_path: Path, distiller: KnowledgeDistiller) -> List[DistilledConcept]:
    """Reads a file and distills its content."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        return distiller.process_text(text, source_uri=f"file://{file_path.absolute()}")
    except Exception as e:
        logger.error(f"Failed to process file {file_path}: {e}")
        return []

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Nex Knowledge Distiller Engine: Converts raw research text into structured reasoning units."
    )
    
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input", type=str, help="Path to a single text file.")
    input_group.add_argument("--dir", type=str, help="Path to a directory containing text files.")
    input_group.add_argument("--stdin", action="store_true", help="Read raw text from standard input.")
    
    parser.add_argument(
        "--format", 
        type=str, 
        choices=["json", "markdown", "graph"], 
        default="json",
        help="Output format (default: json)."
    )
    
    parser.add_argument(
        "--output", 
        type=str, 
        help="Path to save the output. If not provided, prints to stdout."
    )
    
    parser.add_argument(
        "--verbose", 
        action="store_true", 
        help="Enable debug logging."
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    distiller = KnowledgeDistiller()
    all_concepts: List[DistilledConcept] = []

    # 1. Ingest Data
    if args.stdin:
        logger.info("Reading from stdin...")
        text = sys.stdin.read()
        all_concepts.extend(distiller.process_text(text, source_uri="stdin"))
        
    elif args.input:
        file_path = Path(args.input)
        if not file_path.exists() or not file_path.is_file():
            logger.error(f"Input file not found: {args.input}")
            sys.exit(1)
        all_concepts.extend(process_file(file_path, distiller))
        
    elif args.dir:
        dir_path = Path(args.dir)
        if not dir_path.exists() or not dir_path.is_dir():
            logger.error(f"Input directory not found: {args.dir}")
            sys.exit(1)
            
        for file_path in dir_path.rglob("*.txt"):
            all_concepts.extend(process_file(file_path, distiller))

    if not all_concepts:
        logger.warning("No concepts were extracted. Exiting.")
        sys.exit(0)

    # 2. Format Output
    output_str = ""
    if args.format == "json":
        output_str = CorpusFormatter.to_zayvora_json(all_concepts)
    elif args.format == "markdown":
        output_str = CorpusFormatter.to_markdown_cards(all_concepts)
    elif args.format == "graph":
        output_str = CorpusFormatter.to_graph_nodes(all_concepts)

    # 3. Export Output
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output_str)
            logger.info(f"Successfully wrote output to {args.output}")
        except Exception as e:
            logger.error(f"Failed to write to {args.output}: {e}")
            sys.exit(1)
    else:
        print(output_str)

if __name__ == "__main__":
    main()