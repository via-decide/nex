"""
Insight Signal Detector module for the Nex Autonomous Research Agent.

This module is responsible for analyzing large collections of research notes and claims,
detecting repeated patterns, calculating topic frequencies, and surfacing high-signal
insights. It employs a dependency-light NLP pipeline (TF-IDF, Cosine Similarity, N-gram
extraction) to cluster similar claims and score them based on frequency, source diversity,
and confidence levels.

Author: Antigravity Synthesis Orchestrator (v3.0.0-beast)
Project: via-decide/nex
"""

import csv
import json
import logging
import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

# Configure logging for the module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class InsightDetectionError(Exception):
    """Base exception for errors occurring during insight detection."""
    pass

class DataIngestionError(InsightDetectionError):
    """Raised when research notes or claims cannot be parsed or ingested."""
    pass

class SignalExportError(InsightDetectionError):
    """Raised when an error occurs while exporting the synthesized signals."""
    pass

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ResearchSource:
    """Represents a distinct source of information in the research process."""
    source_id: str
    url: Optional[str] = None
    title: Optional[str] = None
    credibility_score: float = 1.0  # 0.0 to 1.0
    published_date: Optional[datetime] = None

@dataclass
class Claim:
    """A single verifiable statement extracted from a research note."""
    claim_id: str
    text: str
    source_id: str
    confidence: float = 0.8  # 0.0 to 1.0
    context: Optional[str] = None
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not (0.0 <= self.confidence <= 1.0):
            logger.warning(f"Claim {self.claim_id} confidence out of bounds. Clamping to [0, 1].")
            self.confidence = max(0.0, min(1.0, self.confidence))

@dataclass
class ResearchNote:
    """A collection of claims and context derived from a specific research session."""
    note_id: str
    source: ResearchSource
    raw_content: str
    claims: List[Claim] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class InsightSignal:
    """A high-value insight synthesized from multiple repeated claims."""
    signal_id: str
    primary_topic: str
    summary_statement: str
    score: float
    supporting_claims: List[Claim]
    unique_source_ids: Set[str]
    topic_frequencies: Dict[str, int]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the insight signal to a dictionary."""
        return {
            "signal_id": self.signal_id,
            "primary_topic": self.primary_topic,
            "summary_statement": self.summary_statement,
            "score": round(self.score, 4),
            "support_count": len(self.supporting_claims),
            "unique_sources_count": len(self.unique_source_ids),
            "unique_source_ids": list(self.unique_source_ids),
            "topic_frequencies": self.topic_frequencies,
            "created_at": self.created_at.isoformat(),
            "supporting_claims": [
                {
                    "claim_id": c.claim_id,
                    "text": c.text,
                    "confidence": c.confidence,
                    "source_id": c.source_id
                } for c in self.supporting_claims
            ]
        }

# ---------------------------------------------------------------------------
# NLP Utilities (Dependency-Light)
# ---------------------------------------------------------------------------

class TextProcessor:
    """Provides pure Python NLP capabilities for text normalization and vectorization."""
    
    STOPWORDS = {
        "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours",
        "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers",
        "herself", "it", "its", "itself", "they", "them", "their", "theirs", "themselves",
        "what", "which", "who", "whom", "this", "that", "these", "those", "am", "is", "are",
        "was", "were", "be", "been", "being", "have", "has", "had", "having", "do", "does",
        "did", "doing", "a", "an", "the", "and", "but", "if", "or", "because", "as", "until",
        "while", "of", "at", "by", "for", "with", "about", "against", "between", "into",
        "through", "during", "before", "after", "above", "below", "to", "from", "up", "down",
        "in", "out", "on", "off", "over", "under", "again", "further", "then", "once", "here",
        "there", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more",
        "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so",
        "than", "too", "very", "s", "t", "can", "will", "just", "don", "should", "now"
    }

    @staticmethod
    def normalize(text: str) -> str:
        """Lowercases and removes punctuation from text."""
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        return text

    @staticmethod
    def tokenize(text: str, remove_stopwords: bool = True) -> List[str]:
        """Tokenizes text into words, optionally removing stopwords."""
        tokens = TextProcessor.normalize(text).split()
        if remove_stopwords:
            tokens = [t for t in tokens if t not in TextProcessor.STOPWORDS and len(t) > 1]
        return tokens

    @staticmethod
    def get_ngrams(tokens: List[str], n: int) -> List[str]:
        """Generates n-grams from a list of tokens."""
        if len(tokens) < n:
            return []
        return [' '.join(tokens[i:i+n]) for i in range(len(tokens)-n+1)]

class TFIDFVectorizer:
    """A lightweight, pure Python TF-IDF implementation for claim clustering."""
    
    def __init__(self):
        self.vocab: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.is_fitted = False

    def fit(self, corpus: List[str]):
        """Calculates IDF for the given corpus."""
        doc_count = len(corpus)
        df: Dict[str, int] = defaultdict(int)
        
        for document in corpus:
            tokens = set(TextProcessor.tokenize(document))
            for token in tokens:
                df[token] += 1
                
        self.vocab = {term: idx for idx, term in enumerate(df.keys())}
        # Add 1 to numerator and denominator to prevent zero division and smooth IDF
        self.idf = {term: math.log((1 + doc_count) / (1 + count)) + 1 
                    for term, count in df.items()}
        self.is_fitted = True

    def transform(self, corpus: List[str]) -> List[Dict[int, float]]:
        """Transforms a corpus into sparse TF-IDF vectors."""
        if not self.is_fitted:
            raise InsightDetectionError("Vectorizer must be fitted before transform.")
            
        vectors = []
        for document in corpus:
            tokens = TextProcessor.tokenize(document)
            term_counts = Counter(tokens)
            total_terms = len(tokens)
            
            vector = {}
            if total_terms > 0:
                for term, count in term_counts.items():
                    if term in self.vocab:
                        tf = count / total_terms
                        tfidf_val = tf * self.idf[term]
                        vector[self.vocab[term]] = tfidf_val
            
            # L2 Normalization
            norm = math.sqrt(sum(v**2 for v in vector.values()))
            if norm > 0:
                vector = {k: v / norm for k, v in vector.items()}
                
            vectors.append(vector)
        return vectors

    @staticmethod
    def cosine_similarity(vec1: Dict[int, float], vec2: Dict[int, float]) -> float:
        """Calculates cosine similarity between two sparse vectors."""
        intersection = set(vec1.keys()) & set(vec2.keys())
        dot_product = sum(vec1[k] * vec2[k] for k in intersection)
        
        # Vectors are pre-normalized, so dot product is the cosine similarity
        return dot_product

# ---------------------------------------------------------------------------
# Core Detector Logic
# ---------------------------------------------------------------------------

class InsightSignalDetector:
    """
    Detects high-signal insights emerging across multiple research notes.
    
    Features:
    - Repeated claim detection via TF-IDF cosine similarity clustering.
    - Topic frequency analysis via N-gram extraction.
    - Insight scoring based on frequency, source diversity, and confidence.
    """

    def __init__(self, 
                 similarity_threshold: float = 0.65,
                 min_cluster_size: int = 2,
                 score_weights: Dict[str, float] = None):
        """
        Initializes the Insight Signal Detector.
        
        Args:
            similarity_threshold: Cosine similarity threshold to consider claims as repeated.
            min_cluster_size: Minimum number of claims to form a valid insight signal.
            score_weights: Weights for the scoring algorithm (frequency, diversity, confidence).
        """
        self.similarity_threshold = similarity_threshold
        self.min_cluster_size = min_cluster_size
        self.score_weights = score_weights or {
            "frequency": 1.0,
            "diversity": 1.5,
            "confidence": 1.0
        }
        
        self.notes: List[ResearchNote] = []
        self.all_claims: List[Claim] = []
        self.signals: List[InsightSignal] = []
        
        self.vectorizer = TFIDFVectorizer()
        logger.info("InsightSignalDetector initialized with threshold: %f", similarity_threshold)

    def ingest_notes(self, notes: List[ResearchNote]):
        """Ingests a list of ResearchNotes into the detector."""
        try:
            initial_count = len(self.notes)
            self.notes.extend(notes)
            for note in notes:
                self.all_claims.extend(note.claims)
            logger.info(f"Ingested {len(notes)} new notes. Total notes: {len(self.notes)}, Total claims: {len(self.all_claims)}")
        except Exception as e:
            logger.error("Failed to ingest research notes.", exc_info=True)
            raise DataIngestionError(f"Ingestion failed: {str(e)}")

    def _cluster_claims(self) -> List[List[Claim]]:
        """
        Groups similar claims using a greedy clustering algorithm based on TF-IDF.
        
        Returns:
            A list of clusters, where each cluster is a list of Claims.
        """
        if not self.all_claims:
            return []

        logger.info("Starting claim clustering process...")
        corpus = [claim.text for claim in self.all_claims]
        
        # Fit and transform
        self.vectorizer.fit(corpus)
        vectors = self.vectorizer.transform(corpus)
        
        clusters: List[List[int]] = []
        
        # Greedy clustering
        for i, vec in enumerate(vectors):
            added = False
            for cluster in clusters:
                # Compare with the centroid or first element. For speed, compare with first element.
                # In a more rigorous setup, we'd maintain a centroid.
                representative_idx = cluster[0]
                sim = TFIDFVectorizer.cosine_similarity(vec, vectors[representative_idx])
                
                if sim >= self.similarity_threshold:
                    cluster.append(i)
                    added = True
                    break
            
            if not added:
                clusters.append([i])
                
        # Filter by minimum cluster size and map back to Claim objects
        valid_clusters = []
        for cluster_indices in clusters:
            if len(cluster_indices) >= self.min_cluster_size:
                valid_clusters.append([self.all_claims[idx] for idx in cluster_indices])
                
        logger.info(f"Clustering complete. Found {len(valid_clusters)} valid clusters.")
        return valid_clusters

    def _extract_topics(self, claims: List[Claim]) -> Tuple[str, Dict[str, int]]:
        """
        Analyzes topic frequency within a cluster of claims.
        
        Returns:
            A tuple containing the primary topic (string) and a dictionary of topic frequencies.
        """
        all_tokens = []
        all_bigrams = []
        
        for claim in claims:
            tokens = TextProcessor.tokenize(claim.text)
            all_tokens.extend(tokens)
            all_bigrams.extend(TextProcessor.get_ngrams(tokens, 2))
            
        # Count frequencies
        token_counts = Counter(all_tokens)
        bigram_counts = Counter(all_bigrams)
        
        # Combine unigrams and bigrams for topic analysis
        combined_counts = {**dict(token_counts), **dict(bigram_counts)}
        
        # Primary topic is the most common bigram, fallback to unigram
        if bigram_counts:
            primary_topic = bigram_counts.most_common(1)[0][0]
        elif token_counts:
            primary_topic = token_counts.most_common(1)[0][0]
        else:
            primary_topic = "Unknown Topic"
            
        # Top 10 frequencies
        top_frequencies = dict(Counter(combined_counts).most_common(10))
        
        return primary_topic, top_frequencies

    def _generate_summary_statement(self, claims: List[Claim]) -> str:
        """
        Generates a representative summary statement for a cluster of claims.
        In a full LLM setup, this would call an LLM. Here, we extract the longest
        or most central claim as the representative summary.
        """
        # Heuristic: The claim with the highest confidence, fallback to longest text
        best_claim = max(claims, key=lambda c: (c.confidence, len(c.text)))
        return best_claim.text

    def _calculate_signal_score(self, claims: List[Claim], unique_sources: Set[str]) -> float:
        """
        Calculates the insight signal score based on configured weights.
        
        Formula:
        Score = (w1 * log(Frequency)) + (w2 * DiversityRatio) + (w3 * AvgConfidence)
        """
        frequency = len(claims)
        diversity_ratio = len(unique_sources) / frequency if frequency > 0 else 0
        avg_confidence = sum(c.confidence for c in claims) / frequency if frequency > 0 else 0
        
        # Logarithmic scaling for frequency to prevent massive clusters from dominating
        freq_component = self.score_weights["frequency"] * math.log1p(frequency)
        div_component = self.score_weights["diversity"] * diversity_ratio
        conf_component = self.score_weights["confidence"] * avg_confidence
        
        total_score = freq_component + div_component + conf_component
        return total_score

    def detect_signals(self) -> List[InsightSignal]:
        """
        Executes the full pipeline: clustering, topic extraction, scoring, and signal generation.
        
        Returns:
            A list of InsightSignal objects sorted by score (descending).
        """
        logger.info("Initiating signal detection pipeline...")
        clusters = self._cluster_claims()
        self.signals = []
        
        for i, cluster in enumerate(clusters):
            unique_sources = {claim.source_id for claim in cluster}
            primary_topic, topic_freqs = self._extract_topics(cluster)
            summary = self._generate_summary_statement(cluster)
            score = self._calculate_signal_score(cluster, unique_sources)
            
            signal = InsightSignal(
                signal_id=f"SIG-{datetime.now().strftime('%Y%m%d%H%M%S')}-{i:04d}",
                primary_topic=primary_topic,
                summary_statement=summary,
                score=score,
                supporting_claims=cluster,
                unique_source_ids=unique_sources,
                topic_frequencies=topic_freqs
            )
            self.signals.append(signal)
            
        # Sort signals by score descending
        self.signals.sort(key=lambda s: s.score, reverse=True)
        logger.info(f"Signal detection complete. Generated {len(self.signals)} high-signal insights.")
        return self.signals

    # -----------------------------------------------------------------------
    # Export Capabilities
    # -----------------------------------------------------------------------

    def export_signals(self, filepath: str, format: str = "json", top_k: Optional[int] = None):
        """
        Exports the detected signals to a file.
        
        Args:
            filepath: Destination file path.
            format: 'json', 'csv', or 'markdown'.
            top_k: If set, only exports the top K signals.
        """
        if not self.signals:
            logger.warning("No signals to export. Did you run detect_signals()?")
            return

        export_data = self.signals[:top_k] if top_k else self.signals
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

            if format.lower() == "json":
                self._export_json(filepath, export_data)
            elif format.lower() == "csv":
                self._export_csv(filepath, export_data)
            elif format.lower() == "markdown" or format.lower() == "md":
                self._export_markdown(filepath, export_data)
            else:
                raise ValueError(f"Unsupported export format: {format}")
                
            logger.info(f"Successfully exported {len(export_data)} signals to {filepath} (Format: {format})")
            
        except Exception as e:
            logger.error(f"Failed to export signals to {filepath}", exc_info=True)
            raise SignalExportError(f"Export failed: {str(e)}")

    def _export_json(self, filepath: str, signals: List[InsightSignal]):
        with open(filepath, 'w', encoding='utf-8') as f:
            json_data = {"metadata": {"total_signals": len(signals), "generated_at": datetime.now(timezone.utc).isoformat()}, "signals": [s.to_dict() for s in signals]}
            json.dump(json_data, f, indent=2)

    def _export_csv(self, filepath: str, signals: List[InsightSignal]):
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Signal ID", "Score", "Primary Topic", "Summary Statement", "Support Count", "Unique Sources"])
            for s in signals:
                writer.writerow([
                    s.signal_id,
                    round(s.score, 4),
                    s.primary_topic,
                    s.summary_statement,
                    len(s.supporting_claims),
                    len(s.unique_source_ids)
                ])

    def _export_markdown(self, filepath: str, signals: List[InsightSignal]):
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("# Nex Deep Research: Insight Signals Report\n\n")
            f.write(f"*Generated on: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*\n\n")
            f.write("---\n\n")
            
            for i, s in enumerate(signals, 1):
                f.write(f"## {i}. {s.primary_topic.title()} (Score: {s.score:.2f})\n\n")
                f.write(f"**Key Insight:** {s.summary_statement}\n\n")
                f.write(f"- **Supporting Claims:** {len(s.supporting_claims)}\n")
                f.write(f"- **Diverse Sources:** {len(s.unique_source_ids)}\n\n")
                
                f.write("### Evidence:\n")
                for claim in s.supporting_claims:
                    f.write(f"- *\"{claim.text}\"* (Source: {claim.source_id}, Confidence: {claim.confidence:.2f})\n")
                f.write("\n---\n\n")


# ---------------------------------------------------------------------------
# Execution / Demo Block
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Example usage demonstrating the pipeline
    logger.info("Running Insight Signal Detector Demo...")

    # 1. Create mock sources
    source_a = ResearchSource(source_id="SRC-001", url="https://example.com/ai-trends")
    source_b = ResearchSource(source_id="SRC-002", url="https://example.com/future-tech")
    source_c = ResearchSource(source_id="SRC-003", url="https://example.com/robotics-now")

    # 2. Create mock claims
    claims_a = [
        Claim("C1", "Autonomous agents will dominate enterprise workflows by 2026.", "SRC-001", 0.9),
        Claim("C2", "Large Language Models require significant compute resources.", "SRC-001", 0.95),
    ]
    claims_b = [
        Claim("C3", "By 2026, enterprise workflows will be largely driven by autonomous AI agents.", "SRC-002", 0.85),
        Claim("C4", "Data privacy remains a top concern for AI adoption.", "SRC-002", 0.88),
    ]
    claims_c = [
        Claim("C5", "AI agents operating autonomously are set to take over enterprise tasks by 2026.", "SRC-003", 0.92),
        Claim("C6", "Robotics hardware is lagging behind AI software capabilities.", "SRC-003", 0.75),
    ]

    # 3. Create mock notes
    notes = [
        ResearchNote("N1", source_a, "Raw content A...", claims_a),
        ResearchNote("N2", source_b, "Raw content B...", claims_b),
        ResearchNote("N3", source_c, "Raw content C...", claims_c),
    ]

    # 4. Initialize and run detector
    # Lower threshold for demo purposes with short texts
    detector = InsightSignalDetector(similarity_threshold=0.3, min_cluster_size=2)
    detector.ingest_notes(notes)
    
    signals = detector.detect_signals()

    # 5. Output results
    print("\n" + "="*50)
    print("DETECTED INSIGHT SIGNALS")
    print("="*50)
    for sig in signals:
        print(f"\nSignal ID: {sig.signal_id}")
        print(f"Topic:     {sig.primary_topic}")
        print(f"Score:     {sig.score:.2f}")
        print(f"Summary:   {sig.summary_statement}")
        print(f"Evidence:  {len(sig.supporting_claims)} claims across {len(sig.unique_source_ids)} sources.")
        print("-" * 30)

    # 6. Test Exports
    # detector.export_signals("output/insights.json", format="json")
    # detector.export_signals("output/insights.md", format="markdown")
    logger.info("Demo complete.")