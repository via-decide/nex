import re
import json
import logging
import argparse
import dataclasses
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple, Pattern


# ============================================================================
# ENUMS & DATACLASSES
# ============================================================================

class Severity(Enum):
    """Enumeration representing the severity level of a detected cognitive bias."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    def __str__(self) -> str:
        return self.name

    def __ge__(self, other: 'Severity') -> bool:
        if self.__class__ is other.__class__:
            return self.value >= other.value
        return NotImplemented


@dataclasses.dataclass
class BiasAlert:
    """
    Data structure representing a single detected cognitive bias.
    
    Attributes:
        bias_type (str): The specific cognitive bias identified (e.g., "Sunk Cost Fallacy").
        severity (Severity): The assessed severity of the bias.
        evidence (str): The exact substring that triggered the detection.
        counter_question (str): A Socratic question designed to challenge the bias.
        source_segment (str): The broader sentence or paragraph containing the bias.
        detected_at (str): ISO 8601 timestamp of when the detection occurred.
    """
    bias_type: str
    severity: Severity
    evidence: str
    counter_question: str
    source_segment: str
    detected_at: str = dataclasses.field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Converts the BiasAlert to a dictionary for JSON serialization."""
        return {
            "bias_type": self.bias_type,
            "severity": self.severity.name,
            "evidence": self.evidence,
            "counter_question": self.counter_question,
            "source_segment": self.source_segment,
            "detected_at": self.detected_at
        }


@dataclasses.dataclass
class AnalysisResult:
    """
    Data structure representing the full result of a narrative analysis.
    
    Attributes:
        document_id (str): Identifier for the analyzed document.
        health_score (float): Calculated Decision Health Score (0.0 to 100.0).
        alerts (List[BiasAlert]): All bias alerts detected in the document.
        segment_count (int): Total number of logical segments analyzed.
        analyzed_at (str): ISO 8601 timestamp of the analysis.
    """
    document_id: str
    health_score: float
    alerts: List[BiasAlert]
    segment_count: int
    analyzed_at: str = dataclasses.field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Converts the AnalysisResult to a dictionary for JSON serialization."""
        return {
            "document_id": self.document_id,
            "health_score": round(self.health_score, 2),
            "segment_count": self.segment_count,
            "analyzed_at": self.analyzed_at,
            "alerts": [alert.to_dict() for alert in self.alerts]
        }


@dataclasses.dataclass
class BiasDefinition:
    """
    Definition of a cognitive bias including detection patterns and mitigation strategies.
    
    Attributes:
        name (str): The standard name of the bias.
        severity (Severity): Default severity assigned to this bias in a founder context.
        patterns (List[str]): List of regex pattern strings used to detect the bias.
        counter_questions (List[str]): Socratic questions to challenge the founder's reasoning.
    """
    name: str
    severity: Severity
    patterns: List[str]
    counter_questions: List[str]


# ============================================================================
# CORE ENGINE: TAXONOMY & PATTERN MATCHING
# ============================================================================

class BiasPatternEngine:
    """
    Engine responsible for maintaining the bias taxonomy and executing regex-based
    pattern matching against text segments.
    """

    def __init__(self) -> None:
        """Initializes the engine and compiles the regex corpus."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.taxonomy: List[BiasDefinition] = self._build_taxonomy()
        self.compiled_patterns: Dict[str, List[Tuple[Pattern, str]]] = self._compile_corpus()
        self.logger.debug(f"Initialized BiasPatternEngine with {len(self.taxonomy)} biases.")

    def _build_taxonomy(self) -> List[BiasDefinition]:
        """
        Constructs the built-in taxonomy of 20+ cognitive biases relevant to solo founders.
        
        Returns:
            List[BiasDefinition]: The complete bias taxonomy.
        """
        return [
            BiasDefinition(
                name="Sunk Cost Fallacy",
                severity=Severity.CRITICAL,
                patterns=[
                    r"\b(?:already spent|invested too much|can'?t give up now|too late to stop|put so much time into|already built)\b"
                ],
                counter_questions=[
                    "If you had invested $0 and 0 hours so far, would you make this same decision today?",
                    "Are you continuing because it's the optimal path, or because you fear wasting past effort?"
                ]
            ),
            BiasDefinition(
                name="Confirmation Bias",
                severity=Severity.HIGH,
                patterns=[
                    r"\b(?:proves my point|just as I thought|obviously true|everyone agrees|as expected, this shows)\b"
                ],
                counter_questions=[
                    "What specific evidence would prove this assumption completely wrong?",
                    "Are you selectively ignoring data that contradicts your preferred outcome?"
                ]
            ),
            BiasDefinition(
                name="Anchoring Bias",
                severity=Severity.MEDIUM,
                patterns=[
                    r"\b(?:initial price|original estimate|first thought|started at|baseline assumption)\b"
                ],
                counter_questions=[
                    "Is your current evaluation heavily skewed by the very first number or idea you encountered?",
                    "If you were presented with this situation blindly today, what would your estimate be?"
                ]
            ),
            BiasDefinition(
                name="Survivorship Bias",
                severity=Severity.HIGH,
                patterns=[
                    r"\b(?:they succeeded so|look at (?:steve jobs|elon musk|mark zuckerberg)|all successful founders|unicorns do this)\b"
                ],
                counter_questions=[
                    "How many failed startups did the exact same thing but aren't around to tell the story?",
                    "Are you optimizing for outlier success tactics rather than fundamental business mechanics?"
                ]
            ),
            BiasDefinition(
                name="Availability Heuristic",
                severity=Severity.MEDIUM,
                patterns=[
                    r"\b(?:saw a tweet|read an article|just happened|everyone is talking about|trending right now)\b"
                ],
                counter_questions=[
                    "Are you overvaluing this information just because it's recent or highly visible?",
                    "Is there broader, less exciting historical data that contradicts this 'trend'?"
                ]
            ),
            BiasDefinition(
                name="Dunning-Kruger Effect",
                severity=Severity.CRITICAL,
                patterns=[
                    r"\b(?:it'?s super easy|anyone can do it|I know exactly how|100% sure|foolproof|no brainer)\b"
                ],
                counter_questions=[
                    "What are the unknown unknowns in this domain that experts worry about?",
                    "If this is so easy, why hasn't it been completely solved by incumbents?"
                ]
            ),
            BiasDefinition(
                name="Bandwagon Effect",
                severity=Severity.MEDIUM,
                patterns=[
                    r"\b(?:everyone is doing|industry trend|all the competitors|hottest new|standard practice now)\b"
                ],
                counter_questions=[
                    "Does this actually serve your specific users, or are you just copying competitors out of FOMO?",
                    "What is the strategic advantage of doing exactly what everyone else is doing?"
                ]
            ),
            BiasDefinition(
                name="Overconfidence Bias",
                severity=Severity.HIGH,
                patterns=[
                    r"\b(?:guaranteed to work|can'?t fail|no risk|absolute certainty|definitely going to)\b"
                ],
                counter_questions=[
                    "Let's assume this fails catastrophically. What was the most likely cause of that failure?",
                    "Are you confusing your high conviction with actual statistical probability?"
                ]
            ),
            BiasDefinition(
                name="Illusion of Control",
                severity=Severity.HIGH,
                patterns=[
                    r"\b(?:I can control|if I just work harder|up to me entirely|force it to happen|will it into existence)\b"
                ],
                counter_questions=[
                    "What external market forces or macroeconomic factors could destroy this plan regardless of your effort?",
                    "Are you underestimating the role of luck and timing in this outcome?"
                ]
            ),
            BiasDefinition(
                name="Optimism Bias",
                severity=Severity.MEDIUM,
                patterns=[
                    r"\b(?:best case scenario|will definitely happen|nothing can go wrong|smooth sailing|easy win)\b"
                ],
                counter_questions=[
                    "Have you built a realistic worst-case scenario model?",
                    "Why do you believe you are immune to the standard friction and delays typical in this process?"
                ]
            ),
            BiasDefinition(
                name="Planning Fallacy",
                severity=Severity.HIGH,
                patterns=[
                    r"\b(?:will only take a day|quick fix|done by tomorrow|easy weekend project|just a few lines of code)\b"
                ],
                counter_questions=[
                    "Historically, how accurate have your time estimates been for similar tasks?",
                    "If you multiply your current time estimate by 3, does the ROI still make sense?"
                ]
            ),
            BiasDefinition(
                name="Status Quo Bias",
                severity=Severity.MEDIUM,
                patterns=[
                    r"\b(?:always done it this way|don'?t change it|stick to what we know|if it ain'?t broke)\b"
                ],
                counter_questions=[
                    "Are you avoiding change because it's optimal, or because the transition requires uncomfortable effort?",
                    "What is the hidden opportunity cost of maintaining the current state?"
                ]
            ),
            BiasDefinition(
                name="Loss Aversion",
                severity=Severity.HIGH,
                patterns=[
                    r"\b(?:can'?t afford to lose|protect what we have|too risky to change|play it safe|don'?t want to risk)\b"
                ],
                counter_questions=[
                    "Are you prioritizing not losing over actually winning?",
                    "If you had nothing to lose right now, what aggressive move would you make?"
                ]
            ),
            BiasDefinition(
                name="Hindsight Bias",
                severity=Severity.LOW,
                patterns=[
                    r"\b(?:I knew it all along|was obvious from the start|inevitable|bound to happen)\b"
                ],
                counter_questions=[
                    "Did you actually document this prediction beforehand, or are you rewriting history?",
                    "How does claiming this was 'obvious' help you make better decisions for the future?"
                ]
            ),
            BiasDefinition(
                name="Base Rate Fallacy",
                severity=Severity.HIGH,
                patterns=[
                    r"\b(?:exception to the rule|doesn'?t apply to us|we are different|unique situation)\b"
                ],
                counter_questions=[
                    "What empirical data proves you are the exception rather than the rule?",
                    "If 90% of startups fail doing this, why exactly are you in the 10%?"
                ]
            ),
            BiasDefinition(
                name="Halo Effect",
                severity=Severity.MEDIUM,
                patterns=[
                    r"\b(?:they are ex-google so|famous investor|top tier firm|brilliant because they)\b"
                ],
                counter_questions=[
                    "Are you assuming competence in this specific area just because they have high status in another?",
                    "If an unknown person gave you this exact same advice, would you follow it?"
                ]
            ),
            BiasDefinition(
                name="Not Invented Here Syndrome",
                severity=Severity.HIGH,
                patterns=[
                    r"\b(?:didn'?t build it ourselves|external tools suck|we can build it better|roll our own)\b"
                ],
                counter_questions=[
                    "Is building this in-house actually your core competency and competitive advantage?",
                    "Are you reinventing the wheel out of ego rather than business utility?"
                ]
            ),
            BiasDefinition(
                name="False Consensus Effect",
                severity=Severity.HIGH,
                patterns=[
                    r"\b(?:everyone wants this feature|users obviously need|nobody likes|it'?s common sense that users)\b"
                ],
                counter_questions=[
                    "Do you have quantitative user data to back this up, or are you projecting your own preferences?",
                    "Have you actually spoken to users who violently disagree with this assumption?"
                ]
            ),
            BiasDefinition(
                name="Action Bias",
                severity=Severity.MEDIUM,
                patterns=[
                    r"\b(?:need to do something|can'?t just sit here|better than doing nothing|just ship it and see)\b"
                ],
                counter_questions=[
                    "Is taking immediate action actually better than waiting for clearer data?",
                    "Are you acting out of anxiety rather than strategic necessity?"
                ]
            ),
            BiasDefinition(
                name="Information Bias",
                severity=Severity.MEDIUM,
                patterns=[
                    r"\b(?:need more data|let'?s wait for more research|not enough information yet|need to analyze further)\b"
                ],
                counter_questions=[
                    "Will more information actually change your decision, or are you just delaying execution?",
                    "What is the cost of waiting for perfect information?"
                ]
            ),
            BiasDefinition(
                name="Endowment Effect",
                severity=Severity.HIGH,
                patterns=[
                    r"\b(?:our code is worth more|my idea is brilliant|can'?t give up equity for that|worth more because I made it)\b"
                ],
                counter_questions=[
                    "If you were an objective third-party buyer, what would you genuinely pay for this?",
                    "Are you overvaluing this asset simply because you own it?"
                ]
            )
        ]

    def _compile_corpus(self) -> Dict[str, List[Tuple[Pattern, str]]]:
        """
        Compiles all regex patterns for performance.
        
        Returns:
            Dict mapping bias names to a list of tuples containing the compiled regex and the raw pattern string.
        """
        compiled = {}
        for bias in self.taxonomy:
            compiled[bias.name] = []
            for pattern in bias.patterns:
                try:
                    # Use IGNORECASE and DOTALL for robust matching
                    compiled_regex = re.compile(pattern, re.IGNORECASE | re.DOTALL)
                    compiled[bias.name].append((compiled_regex, pattern))
                except re.error as e:
                    self.logger.error(f"Failed to compile regex for {bias.name}: {pattern}. Error: {e}")
        return compiled

    def scan_segment(self, segment: str) -> List[BiasAlert]:
        """
        Scans a single text segment against the compiled regex corpus.
        
        Args:
            segment (str): The text segment (e.g., a sentence or paragraph) to analyze.
            
        Returns:
            List[BiasAlert]: A list of detected biases in the segment.
        """
        alerts = []
        if not segment.strip():
            return alerts

        for bias in self.taxonomy:
            patterns = self.compiled_patterns.get(bias.name, [])
            for compiled_regex, raw_pattern in patterns:
                match = compiled_regex.search(segment)
                if match:
                    # Select the first counter question (could be randomized in future iterations)
                    counter_q = bias.counter_questions[0] if bias.counter_questions else "Why do you believe this is absolutely true?"
                    
                    alert = BiasAlert(
                        bias_type=bias.name,
                        severity=bias.severity,
                        evidence=match.group(0),
                        counter_question=counter_q,
                        source_segment=segment.strip()
                    )
                    alerts.append(alert)
                    self.logger.debug(f"Detected {bias.name} in segment.")
                    # Break after first match per bias type per segment to avoid alert fatigue
                    break 
        return alerts


# ============================================================================
# ANALYSIS ORCHESTRATOR
# ============================================================================

class FounderNarrativeAnalyzer:
    """
    High-level orchestrator that processes raw decision text, splits it into
    logical segments, runs multi-pass bias detection, and calculates aggregate risk.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.engine = BiasPatternEngine()

    def _split_segments(self, text: str) -> List[str]:
        """
        Splits raw text into logical segments (paragraphs or sentences) for granular analysis.
        
        Args:
            text (str): The raw input text.
            
        Returns:
            List[str]: A list of text segments.
        """
        # First split by double newlines to get paragraphs
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        segments = []
        
        for para in paragraphs:
            # If a paragraph is exceptionally long, split by sentences.
            # Using a simple heuristic: split by period followed by space.
            if len(para) > 300:
                sentences = re.split(r'(?<=\.)\s+', para)
                segments.extend([s.strip() for s in sentences if s.strip()])
            else:
                segments.append(para)
                
        return segments

    def _calculate_health_score(self, alerts: List[BiasAlert], total_segments: int) -> float:
        """
        Computes an overall Decision Health Score (0-100) based on bias density and severity.
        
        Args:
            alerts (List[BiasAlert]): Detected biases.
            total_segments (int): Total number of segments analyzed.
            
        Returns:
            float: The calculated health score.
        """
        if total_segments == 0:
            return 100.0

        score = 100.0
        
        # Deductions based on severity
        severity_weights = {
            Severity.LOW: 2.0,
            Severity.MEDIUM: 5.0,
            Severity.HIGH: 10.0,
            Severity.CRITICAL: 15.0
        }

        total_deduction = sum(severity_weights.get(alert.severity, 0.0) for alert in alerts)
        
        # Density penalty: if a high percentage of segments have biases, penalize further
        bias_density = len(alerts) / total_segments
        density_penalty = (bias_density * 20.0) # Max 20 points penalty for density
        
        final_score = score - total_deduction - density_penalty
        
        # Clamp between 0 and 100
        return max(0.0, min(100.0, final_score))

    def analyze(self, text: str, document_id: str = "doc_unknown") -> AnalysisResult:
        """
        Executes the full reasoning audit pipeline on the provided text.
        
        Args:
            text (str): The founder's decision narrative.
            document_id (str): An identifier for the document.
            
        Returns:
            AnalysisResult: The complete analysis result.
        """
        self.logger.info(f"Starting analysis for document: {document_id}")
        segments = self._split_segments(text)
        all_alerts: List[BiasAlert] = []
        
        for segment in segments:
            alerts = self.engine.scan_segment(segment)
            all_alerts.extend(alerts)
            
        health_score = self._calculate_health_score(all_alerts, len(segments))
        
        result = AnalysisResult(
            document_id=document_id,
            health_score=health_score,
            alerts=all_alerts,
            segment_count=len(segments)
        )
        
        self.logger.info(f"Analysis complete. Score: {health_score:.2f}, Alerts: {len(all_alerts)}")
        return result


# ============================================================================
# EXPORT & REPORTING
# ============================================================================

class ReportGenerator:
    """Handles the formatting and exporting of analysis results to various formats."""

    # ANSI Color Codes for Terminal Output
    C_RESET = "\033[0m"
    C_RED = "\033[91m"
    C_YELLOW = "\033[93m"
    C_GREEN = "\033[92m"
    C_CYAN = "\033[96m"
    C_BOLD = "\033[1m"

    @classmethod
    def export_json(cls, result: AnalysisResult, filepath: Optional[Path] = None) -> str:
        """Exports the result as a JSON string, optionally writing to a file."""
        json_data = json.dumps(result.to_dict(), indent=4)
        if filepath:
            filepath.write_text(json_data, encoding="utf-8")
        return json_data

    @classmethod
    def export_markdown(cls, result: AnalysisResult, filepath: Optional[Path] = None) -> str:
        """Exports the result as a Markdown advisory report."""
        lines = [
            f"# Cognitive Bias Advisory Report: `{result.document_id}`",
            f"**Analyzed At:** {result.analyzed_at}",
            f"**Total Segments Analyzed:** {result.segment_count}",
            "",
            f"## Decision Health Score: **{result.health_score:.2f} / 100**",
            ""
        ]

        if result.health_score >= 80:
            lines.append("> **Status:** Healthy reasoning. Minimal cognitive distortion detected.")
        elif result.health_score >= 50:
            lines.append("> **Status:** Warning. Several biases detected that may compromise judgment. Review counter-questions.")
        else:
            lines.append("> **Status:** CRITICAL. High density of severe cognitive biases. Do not execute decision without peer review.")

        lines.append("\n## Detected Biases\n")
        
        if not result.alerts:
            lines.append("*No significant cognitive biases detected.*")
        else:
            # Sort alerts by severity descending
            sorted_alerts = sorted(result.alerts, key=lambda a: a.severity.value, reverse=True)
            for alert in sorted_alerts:
                lines.extend([
                    f"### {alert.bias_type} `[{alert.severity.name}]`",
                    f"- **Trigger Evidence:** \"{alert.evidence}\"",
                    f"- **Context:** \"{alert.source_segment}\"",
                    f"- **Socratic Challenge:** **{alert.counter_question}**",
                    ""
                ])

        md_data = "\n".join(lines)
        if filepath:
            filepath.write_text(md_data, encoding="utf-8")
        return md_data

    @classmethod
    def export_terminal(cls, result: AnalysisResult) -> str:
        """Exports a color-formatted summary for terminal output."""
        lines = []
        
        # Header
        lines.append(f"\n{cls.C_BOLD}{cls.C_CYAN}=== VIA DECIDE REASONING AUDIT ==={cls.C_RESET}")
        lines.append(f"Document: {result.document_id}")
        
        # Score Color Logic
        if result.health_score >= 80:
            score_color = cls.C_GREEN
        elif result.health_score >= 50:
            score_color = cls.C_YELLOW
        else:
            score_color = cls.C_RED
            
        lines.append(f"Decision Health Score: {cls.C_BOLD}{score_color}{result.health_score:.2f} / 100{cls.C_RESET}")
        lines.append(f"Segments Analyzed: {result.segment_count}")
        lines.append("-" * 40)

        if not result.alerts:
            lines.append(f"{cls.C_GREEN}No cognitive biases detected. Clear reasoning.{cls.C_RESET}")
        else:
            sorted_alerts = sorted(result.alerts, key=lambda a: a.severity.value, reverse=True)
            for alert in sorted_alerts:
                sev_color = cls.C_RED if alert.severity in (Severity.CRITICAL, Severity.HIGH) else cls.C_YELLOW
                lines.append(f"{cls.C_BOLD}{sev_color}[{alert.severity.name}] {alert.bias_type}{cls.C_RESET}")
                lines.append(f"  {cls.C_CYAN}Evidence:{cls.C_RESET} \"{alert.evidence}\"")
                lines.append(f"  {cls.C_YELLOW}Challenge:{cls.C_RESET} {alert.counter_question}")
                lines.append("")

        lines.append(f"{cls.C_BOLD}{cls.C_CYAN}=================================={cls.C_RESET}\n")
        return "\n".join(lines)


# ============================================================================
# BATCH PROCESSING & CLI
# ============================================================================

def process_batch(directory: Path, analyzer: FounderNarrativeAnalyzer, threshold: Severity) -> List[AnalysisResult]:
    """
    Processes all text/markdown files in a given directory.
    
    Args:
        directory (Path): The directory to scan.
        analyzer (FounderNarrativeAnalyzer): The instantiated analyzer.
        threshold (Severity): The minimum severity threshold for alerts.
        
    Returns:
        List[AnalysisResult]: A list of results for all processed documents.
    """
    results = []
    valid_extensions = {".txt", ".md"}
    
    for filepath in directory.rglob("*"):
        if filepath.is_file() and filepath.suffix.lower() in valid_extensions:
            try:
                text = filepath.read_text(encoding="utf-8")
                result = analyzer.analyze(text, document_id=filepath.name)
                
                # Filter alerts by threshold
                filtered_alerts = [a for a in result.alerts if a.severity >= threshold]
                result.alerts = filtered_alerts
                
                # Recalculate score based on filtered alerts
                result.health_score = analyzer._calculate_health_score(filtered_alerts, result.segment_count)
                
                results.append(result)
            except Exception as e:
                logging.error(f"Failed to process {filepath.name}: {e}")
                
    return results

def setup_logging(verbose: bool) -> None:
    """Configures the root logger based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def main() -> None:
    """CLI Entry Point."""
    parser = argparse.ArgumentParser(
        description="Nex Bias Detector: Solo Founder Cognitive Bias & Reasoning Auditor",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--text", type=str, help="Raw narrative text to analyze directly.")
    input_group.add_argument("--file", type=Path, help="Path to a single text or markdown file.")
    input_group.add_argument("--dir", type=Path, help="Path to a directory for batch processing.")
    
    parser.add_argument("--threshold", type=str, choices=[s.name for s in Severity], default="LOW",
                        help="Minimum severity threshold to report.")
    parser.add_argument("--format", type=str, choices=["terminal", "json", "markdown"], default="terminal",
                        help="Output format.")
    parser.add_argument("--outdir", type=Path, default=None,
                        help="Directory to save output reports (JSON/Markdown). If omitted, prints to stdout.")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    
    args = parser.parse_args()
    setup_logging(args.verbose)
    
    analyzer = FounderNarrativeAnalyzer()
    threshold_enum = Severity[args.threshold]
    
    results: List[AnalysisResult] = []
    
    # --- Input Processing ---
    if args.text:
        res = analyzer.analyze(args.text, document_id="inline_text")
        res.alerts = [a for a in res.alerts if a.severity >= threshold_enum]
        res.health_score = analyzer._calculate_health_score(res.alerts, res.segment_count)
        results.append(res)
        
    elif args.file:
        if not args.file.exists():
            logging.error(f"File not found: {args.file}")
            sys.exit(1)
        text = args.file.read_text(encoding="utf-8")
        res = analyzer.analyze(text, document_id=args.file.name)
        res.alerts = [a for a in res.alerts if a.severity >= threshold_enum]
        res.health_score = analyzer._calculate_health_score(res.alerts, res.segment_count)
        results.append(res)
        
    elif args.dir:
        if not args.dir.is_dir():
            logging.error(f"Directory not found: {args.dir}")
            sys.exit(1)
        results = process_batch(args.dir, analyzer, threshold_enum)
        
    if not results:
        logging.info("No documents processed.")
        sys.exit(0)

    # --- Output Generation ---
    if args.outdir:
        args.outdir.mkdir(parents=True, exist_ok=True)
        
    for res in results:
        if args.format == "json":
            out_path = args.outdir / f"{res.document_id}_report.json" if args.outdir else None
            output = ReportGenerator.export_json(res, out_path)
            if not args.outdir:
                print(output)
                
        elif args.format == "markdown":
            out_path = args.outdir / f"{res.document_id}_report.md" if args.outdir else None
            output = ReportGenerator.export_markdown(res, out_path)
            if not args.outdir:
                print(output)
                
        elif args.format == "terminal":
            print(ReportGenerator.export_terminal(res))

if __name__ == "__main__":
    import sys
    main()