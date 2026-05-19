#!/usr/bin/env python3
"""
Sovereign Decision Intelligence Extraction Engine

This module provides a production-grade pipeline for analyzing raw text inputs
and extracting structured decision insights. Designed for the ViaDecide reasoning
pipeline, it utilizes pattern matching, heuristic scoring, and multi-dimensional
classification to extract strategic, operational, financial, technical, risk,
and opportunity insights.

Features:
- Rule-based multi-dimensional classification using a rich keyword corpus.
- TF-IDF style keyword weighting and contextual proximity scoring.
- Batch processing and multi-format export (JSON, CSV, Markdown).
- Comprehensive CLI and logging capabilities.

Author: Antigravity Synthesis Orchestrator (v3.0.0-beast)
"""

import argparse
import csv
import json
import logging
import math
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Pattern, Set, Tuple, Union


# =============================================================================
# Logging Configuration
# =============================================================================

def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Configures and returns a standard logger for the decision engine.

    Args:
        name (str): The name of the logger.
        level (int): The logging level (e.g., logging.INFO, logging.DEBUG).

    Returns:
        logging.Logger: The configured logger instance.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


logger = setup_logger("DecisionEngine")


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class DecisionInsight:
    """
    A structured representation of an extracted decision insight.

    Attributes:
        title (str): A concise summary or title of the decision.
        category (str): The classification category (e.g., strategic, risk).
        confidence (float): A normalized score (0.0 to 1.0) indicating extraction confidence.
        reasoning_trace (List[str]): Steps or matched patterns that led to this extraction.
        source_context (str): The raw text segment containing the decision.
        timestamp (str): ISO-8601 formatted timestamp of when the insight was extracted.
    """
    title: str
    category: str
    confidence: float
    reasoning_trace: List[str]
    source_context: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the dataclass instance to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary representation of the insight.
        """
        return asdict(self)


# =============================================================================
# Corpus and Constants
# =============================================================================

# A built-in corpus of 50+ decision-relevant keyword patterns organized by category.
# These act as the foundational heuristic triggers for the InsightClassifier.
DECISION_CORPUS: Dict[str, List[str]] = {
    "strategic": [
        r"\bvision\b", r"\blong-term\b", r"\broadmap\b", r"\bpivot\b",
        r"\bacquisition\b", r"\bmarket share\b", r"\bcompetitive advantage\b",
        r"\bpositioning\b", r"\bcore competency\b", r"\bstrategic\b",
        r"\bmerger\b", r"\bgo-to-market\b", r"\bdiversification\b"
    ],
    "operational": [
        r"\befficiency\b", r"\bsupply chain\b", r"\blogistics\b", r"\bworkflow\b",
        r"\bbottleneck\b", r"\bcapacity\b", r"\bthroughput\b", r"\bstreamline\b",
        r"\boptimization\b", r"\boutsourcing\b", r"\bautomation\b",
        r"\bday-to-day\b", r"\boperational\b"
    ],
    "financial": [
        r"\brevenue\b", r"\bmargin\b", r"\broi\b", r"\bebitda\b", r"\bcash flow\b",
        r"\bbudget\b", r"\bcost reduction\b", r"\bprofitability\b", r"\bcapex\b",
        r"\bopex\b", r"\bfunding\b", r"\binvestment\b", r"\bfinancial\b"
    ],
    "technical": [
        r"\barchitecture\b", r"\bscalability\b", r"\blatency\b", r"\brefactor\b",
        r"\bapi\b", r"\bdeployment\b", r"\binfrastructure\b", r"\btech stack\b",
        r"\bmigration\b", r"\bcloud\b", r"\bframework\b", r"\btechnical\b",
        r"\bcodebase\b"
    ],
    "risk": [
        r"\bcompliance\b", r"\bvulnerability\b", r"\bliability\b", r"\bmitigation\b",
        r"\bexposure\b", r"\bthreat\b", r"\bvolatility\b", r"\bregulatory\b",
        r"\bsecurity\b", r"\bcontingency\b", r"\bdownside\b", r"\brisk\b",
        r"\bbreach\b"
    ],
    "opportunity": [
        r"\bexpansion\b", r"\bpartnership\b", r"\buntapped\b", r"\bsynergy\b",
        r"\bgrowth\b", r"\binnovation\b", r"\bemerging market\b", r"\bwhite space\b",
        r"\bnew market\b", r"\bupsell\b", r"\bjoint venture\b", r"\bopportunity\b",
        r"\bcapitalise\b"
    ]
}

# Indicators that suggest a decision has been made or is being recommended
DECISION_INDICATORS: List[str] = [
    r"\bdecided\b", r"\bconcluded\b", r"\brecommend\b", r"\bresolved\b",
    r"\bwe will\b", r"\bpropose\b", r"\bapprove\b", r"\bagreed\b",
    r"\bmandate\b", r"\bopted\b", r"\bcommit to\b", r"\bdetermined\b"
]


# =============================================================================
# Core Engine Components
# =============================================================================

class RelevanceScorer:
    """
    Computes a relevance and confidence score for a text segment based on
    TF-IDF style keyword weighting and contextual proximity to decision verbs.
    """

    def __init__(self):
        """Initializes the RelevanceScorer with pre-compiled indicator patterns."""
        self.indicator_patterns: List[Pattern] = [
            re.compile(ind, re.IGNORECASE) for ind in DECISION_INDICATORS
        ]
        logger.debug("RelevanceScorer initialized with %d indicator patterns.", len(self.indicator_patterns))

    def _calculate_term_frequency(self, text: str, keywords: List[str]) -> float:
        """
        Calculates a normalized term frequency for the matched keywords in the text.

        Args:
            text (str): The source text.
            keywords (List[str]): The keywords found in the text.

        Returns:
            float: A frequency score between 0.0 and 1.0.
        """
        words = re.findall(r'\w+', text.lower())
        if not words:
            return 0.0
        
        total_words = len(words)
        keyword_count = sum(1 for word in words if any(kw.replace('\\b', '') in word for kw in keywords))
        
        # Logarithmic scaling to prevent keyword stuffing from dominating the score
        tf_score = math.log1p(keyword_count) / math.log1p(total_words)
        return min(tf_score * 2.0, 1.0) # Scale up slightly for shorter sentences

    def _calculate_proximity_score(self, text: str, keyword_matches: List[str]) -> float:
        """
        Calculates a score based on the proximity of category keywords to decision indicators.

        Args:
            text (str): The source text.
            keyword_matches (List[str]): The keywords found in the text.

        Returns:
            float: A proximity score between 0.0 and 1.0.
        """
        if not keyword_matches:
            return 0.0

        text_lower = text.lower()
        indicator_positions = []
        
        # Find positions of all decision indicators
        for pattern in self.indicator_patterns:
            for match in pattern.finditer(text_lower):
                indicator_positions.append(match.start())

        if not indicator_positions:
            return 0.0

        best_proximity = float('inf')
        
        # Find positions of category keywords and calculate minimum distance
        for kw in keyword_matches:
            kw_clean = kw.replace('\\b', '')
            for match in re.finditer(re.escape(kw_clean), text_lower):
                kw_pos = match.start()
                for ind_pos in indicator_positions:
                    distance = abs(kw_pos - ind_pos)
                    if distance < best_proximity:
                        best_proximity = distance

        # Convert distance to a score: closer is better. 
        # Assuming typical sentence length ~100-200 characters.
        if best_proximity == float('inf'):
            return 0.0
            
        proximity_score = math.exp(-best_proximity / 50.0) # Decay factor
        return max(0.0, min(proximity_score, 1.0))

    def score(self, text: str, matched_keywords: List[str]) -> float:
        """
        Generates a composite confidence score for the extracted insight.

        Args:
            text (str): The raw text segment.
            matched_keywords (List[str]): Keywords that triggered the classification.

        Returns:
            float: A composite confidence score (0.0 to 1.0).
        """
        tf_score = self._calculate_term_frequency(text, matched_keywords)
        prox_score = self._calculate_proximity_score(text, matched_keywords)
        
        # Weighted combination: Proximity to a decision verb is highly indicative
        composite_score = (tf_score * 0.4) + (prox_score * 0.6)
        
        # Apply a base threshold boost if there are multiple unique keywords
        unique_kws = len(set(matched_keywords))
        if unique_kws > 1:
            composite_score += 0.1 * unique_kws
            
        return round(min(max(composite_score, 0.1), 0.99), 3)


class InsightClassifier:
    """
    Rule-based classification engine that maps text segments to predefined
    decision categories using regular expressions.
    """

    def __init__(self):
        """Initializes the classifier and compiles regex patterns for performance."""
        self.compiled_corpus: Dict[str, List[Pattern]] = {
            category: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
            for category, patterns in DECISION_CORPUS.items()
        }
        logger.debug("InsightClassifier initialized with %d categories.", len(self.compiled_corpus))

    def classify(self, text: str) -> Tuple[Optional[str], List[str], List[str]]:
        """
        Classifies a given text into the most dominant decision category.

        Args:
            text (str): The text segment to classify.

        Returns:
            Tuple[Optional[str], List[str], List[str]]: 
                - The dominant category (or None if unclassified).
                - List of matched keywords.
                - A reasoning trace detailing the matches.
        """
        category_scores: Dict[str, int] = defaultdict(int)
        matched_keywords_by_cat: Dict[str, List[str]] = defaultdict(list)
        reasoning_trace: List[str] = []

        for category, patterns in self.compiled_corpus.items():
            for pattern in patterns:
                matches = pattern.findall(text)
                if matches:
                    count = len(matches)
                    category_scores[category] += count
                    # Store the raw string representation of the pattern
                    matched_keywords_by_cat[category].append(pattern.pattern)
                    reasoning_trace.append(
                        f"Matched pattern '{pattern.pattern}' {count} time(s) for category '{category}'."
                    )

        if not category_scores:
            return None, [], ["No category patterns matched."]

        # Determine dominant category
        dominant_category = max(category_scores.items(), key=lambda x: x[1])[0]
        dominant_keywords = matched_keywords_by_cat[dominant_category]
        
        reasoning_trace.append(
            f"Selected dominant category '{dominant_category}' with {category_scores[dominant_category]} total matches."
        )

        return dominant_category, dominant_keywords, reasoning_trace


class DecisionExtractor:
    """
    Main engine class that orchestrates the extraction pipeline.
    Chains text segmentation, classification, and scoring to produce DecisionInsights.
    """

    def __init__(self):
        """Initializes the extraction pipeline components."""
        self.classifier = InsightClassifier()
        self.scorer = RelevanceScorer()
        logger.info("DecisionExtractor pipeline initialized successfully.")

    def _segment_text(self, text: str) -> List[str]:
        """
        Splits raw text into processable sentence-like chunks using regex heuristics.

        Args:
            text (str): The raw input document.

        Returns:
            List[str]: A list of text segments.
        """
        # Basic heuristic splitting on punctuation followed by space or newline
        segments = re.split(r'(?<=[.!?])\s+|\n+', text.strip())
        # Filter out extremely short segments that lack context
        valid_segments = [seg.strip() for seg in segments if len(seg.strip()) > 20]
        logger.debug("Segmented text into %d valid chunks.", len(valid_segments))
        return valid_segments

    def _generate_title(self, text: str, category: str) -> str:
        """
        Generates a concise title for the insight based on the text.

        Args:
            text (str): The source text.
            category (str): The classification category.

        Returns:
            str: A short title.
        """
        words = text.split()
        if len(words) <= 8:
            title_base = text
        else:
            title_base = " ".join(words[:8]) + "..."
            
        return f"{category.capitalize()} Insight: {title_base}"

    def extract(self, text: str, confidence_threshold: float = 0.3) -> List[DecisionInsight]:
        """
        Processes a single document and extracts a list of decision insights.

        Args:
            text (str): The raw text document.
            confidence_threshold (float): Minimum confidence score to retain an insight.

        Returns:
            List[DecisionInsight]: A list of extracted insights.
        """
        logger.info("Starting extraction on text of length %d.", len(text))
        insights: List[DecisionInsight] = []
        segments = self._segment_text(text)

        for segment in segments:
            category, keywords, trace = self.classifier.classify(segment)
            
            if not category:
                continue

            confidence = self.scorer.score(segment, keywords)
            
            if confidence >= confidence_threshold:
                trace.append(f"Calculated confidence score: {confidence:.3f}")
                title = self._generate_title(segment, category)
                
                insight = DecisionInsight(
                    title=title,
                    category=category,
                    confidence=confidence,
                    reasoning_trace=trace,
                    source_context=segment
                )
                insights.append(insight)
                logger.debug("Extracted %s insight with confidence %.2f.", category, confidence)

        # Sort by confidence descending
        insights.sort(key=lambda x: x.confidence, reverse=True)
        logger.info("Extraction complete. Found %d insights above threshold.", len(insights))
        return insights

    def batch_extract(self, texts: Dict[str, str], confidence_threshold: float = 0.3) -> Dict[str, List[DecisionInsight]]:
        """
        Processes multiple documents in batch.

        Args:
            texts (Dict[str, str]): A dictionary mapping document IDs/names to raw text.
            confidence_threshold (float): Minimum confidence score.

        Returns:
            Dict[str, List[DecisionInsight]]: A dictionary mapping document IDs to their insights.
        """
        logger.info("Starting batch extraction for %d documents.", len(texts))
        results = {}
        for doc_id, text in texts.items():
            logger.info("Processing document: %s", doc_id)
            results[doc_id] = self.extract(text, confidence_threshold)
        return results

    # =========================================================================
    # Export Methods
    # =========================================================================

    def export_to_json(self, insights: Union[List[DecisionInsight], Dict[str, List[DecisionInsight]]], filepath: str) -> None:
        """
        Exports insights to a JSON file.

        Args:
            insights: A list of insights or a dictionary of insights (batch mode).
            filepath (str): Destination file path.
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                if isinstance(insights, dict):
                    data = {doc_id: [i.to_dict() for i in lst] for doc_id, lst in insights.items()}
                else:
                    data = [i.to_dict() for i in insights]
                json.dump(data, f, indent=4, ensure_ascii=False)
            logger.info("Successfully exported insights to JSON: %s", filepath)
        except Exception as e:
            logger.error("Failed to export to JSON: %s", str(e))
            raise

    def export_to_csv(self, insights: List[DecisionInsight], filepath: str) -> None:
        """
        Exports a list of insights to a CSV file.

        Args:
            insights (List[DecisionInsight]): The insights to export.
            filepath (str): Destination file path.
        """
        if not insights:
            logger.warning("No insights to export to CSV.")
            return

        try:
            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                # Write header
                writer.writerow(['Timestamp', 'Category', 'Confidence', 'Title', 'Source Context', 'Reasoning Trace'])
                for ins in insights:
                    writer.writerow([
                        ins.timestamp,
                        ins.category,
                        f"{ins.confidence:.3f}",
                        ins.title,
                        ins.source_context,
                        " | ".join(ins.reasoning_trace)
                    ])
            logger.info("Successfully exported insights to CSV: %s", filepath)
        except Exception as e:
            logger.error("Failed to export to CSV: %s", str(e))
            raise

    def export_to_markdown(self, insights: List[DecisionInsight], filepath: str) -> None:
        """
        Exports a list of insights to a Markdown summary report.

        Args:
            insights (List[DecisionInsight]): The insights to export.
            filepath (str): Destination file path.
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("# Decision Intelligence Extraction Report\n\n")
                f.write(f"**Generated:** {datetime.now(timezone.utc).isoformat()}\n")
                f.write(f"**Total Insights:** {len(insights)}\n\n")
                
                # Group by category
                grouped: Dict[str, List[DecisionInsight]] = defaultdict(list)
                for ins in insights:
                    grouped[ins.category].append(ins)
                    
                for category, ins_list in sorted(grouped.items()):
                    f.write(f"## {category.capitalize()} Insights\n\n")
                    for ins in ins_list:
                        f.write(f"### {ins.title}\n")
                        f.write(f"- **Confidence:** {ins.confidence:.2f}\n")
                        f.write(f"- **Context:** > {ins.source_context}\n")
                        f.write(f"- **Trace:** {ins.reasoning_trace[-1]}\n\n")
                        
            logger.info("Successfully exported insights to Markdown: %s", filepath)
        except Exception as e:
            logger.error("Failed to export to Markdown: %s", str(e))
            raise


# =============================================================================
# CLI Interface
# =============================================================================

def parse_args() -> argparse.Namespace:
    """
    Parses command line arguments for the standalone CLI.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Antigravity Decision Intelligence Extraction Engine",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("-t", "--text", type=str, help="Raw text string to analyze.")
    input_group.add_argument("-f", "--file", type=str, help="Path to a text file to analyze.")
    input_group.add_argument("-d", "--dir", type=str, help="Path to a directory of text files for batch processing.")
    
    parser.add_argument("-o", "--output", type=str, default="insights", help="Base name for output files (default: 'insights').")
    parser.add_argument("--format", type=str, choices=["json", "csv", "md", "all"], default="json", 
                        help="Output format (default: json).")
    parser.add_argument("--threshold", type=float, default=0.3, help="Minimum confidence threshold (0.0 to 1.0).")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose DEBUG logging.")
    
    return parser.parse_args()


def main() -> None:
    """Main entry point for the CLI."""
    args = parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled.")

    engine = DecisionExtractor()
    
    # 1. Gather Input
    texts_to_process: Dict[str, str] = {}
    
    try:
        if args.text:
            texts_to_process["cli_input"] = args.text
        elif args.file:
            with open(args.file, 'r', encoding='utf-8') as f:
                texts_to_process[os.path.basename(args.file)] = f.read()
        elif args.dir:
            for filename in os.listdir(args.dir):
                if filename.endswith(".txt") or filename.endswith(".md"):
                    filepath = os.path.join(args.dir, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        texts_to_process[filename] = f.read()
            if not texts_to_process:
                logger.error("No valid text files (.txt, .md) found in directory: %s", args.dir)
                sys.exit(1)
    except Exception as e:
        logger.error("Failed to read input: %s", str(e))
        sys.exit(1)

    # 2. Extract Insights
    if len(texts_to_process) == 1:
        doc_id, text = list(texts_to_process.items())[0]
        insights = engine.extract(text, confidence_threshold=args.threshold)
        flat_insights = insights
        batch_mode = False
    else:
        batch_results = engine.batch_extract(texts_to_process, confidence_threshold=args.threshold)
        insights = batch_results # type: ignore
        flat_insights = [ins for lst in batch_results.values() for ins in lst]
        batch_mode = True

    if not flat_insights:
        logger.warning("No insights extracted that met the confidence threshold (%.2f).", args.threshold)
        sys.exit(0)

    # 3. Export Results
    base_out = args.output
    formats_to_export = ["json", "csv", "md"] if args.format == "all" else [args.format]
    
    for fmt in formats_to_export:
        out_file = f"{base_out}.{fmt}"
        if fmt == "json":
            engine.export_to_json(insights, out_file)
        elif fmt == "csv":
            engine.export_to_csv(flat_insights, out_file)
        elif fmt == "md":
            engine.export_to_markdown(flat_insights, out_file)

    logger.info("Processing complete. Extracted %d total insights.", len(flat_insights))


if __name__ == "__main__":
    main()