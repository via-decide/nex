import argparse
import dataclasses
import datetime
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Pattern

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("BiasDetector")

# ANSI Color Codes for Terminal Output
class TerminalColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


@dataclasses.dataclass
class BiasAlert:
    """
    Represents a single detected cognitive bias in the founder's narrative.

    Attributes:
        bias_type (str): The name/category of the cognitive bias.
        severity (int): The risk level of the bias (1-10).
        evidence (str): The specific phrase or keyword that triggered the detection.
        counter_question (str): A Socratic question designed to challenge the bias.
        source_segment (str): The full sentence or paragraph where the bias was found.
        detected_at (str): ISO 8601 timestamp of when the detection occurred.
    """
    bias_type: str
    severity: int
    evidence: str
    counter_question: str
    source_segment: str
    detected_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Converts the BiasAlert instance to a dictionary."""
        return dataclasses.asdict(self)


@dataclasses.dataclass
class AnalysisReport:
    """
    Aggregate report containing all detected biases and the overall health score.

    Attributes:
        document_id (str): Identifier for the analyzed document.
        health_score (int): Overall Decision Health Score (0-100).
        total_biases_detected (int): Number of biases found.
        alerts (List[BiasAlert]): List of individual bias alerts.
        analyzed_at (str): ISO 8601 timestamp of the analysis.
    """
    document_id: str
    health_score: int
    total_biases_detected: int
    alerts: List[BiasAlert]
    analyzed_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Converts the AnalysisReport instance to a dictionary."""
        return dataclasses.asdict(self)


class BiasPatternEngine:
    """
    Engine responsible for compiling and evaluating regex patterns against text 
    to detect cognitive biases. Contains a built-in taxonomy of 20+ biases.
    """

    # Built-in taxonomy of cognitive biases mapping to severity, regex patterns, and Socratic questions.
    TAXONOMY = {
        "Sunk Cost Fallacy": {
            "severity": 8,
            "patterns": [
                r"already (spent|invested)", r"too much (time|money) in", r"can'?t turn back now",
                r"wasted if we stop", r"put so much into", r"already committed", r"gone too far to"
            ],
            "question": "If you had not already invested resources into this, would you still make this decision today?"
        },
        "Confirmation Bias": {
            "severity": 7,
            "patterns": [
                r"proves (my|our) point", r"just as I thought", r"obviously true",
                r"everyone agrees", r"validates my assumption", r"exactly what I expected"
            ],
            "question": "What evidence exists that completely contradicts your current assumption? Have you actively sought it out?"
        },
        "Anchoring Bias": {
            "severity": 6,
            "patterns": [
                r"initial (price|estimate|thought)", r"originally thought", r"starting point",
                r"based on the first", r"compared to the original"
            ],
            "question": "Are you overly relying on the first piece of information you received? How would you decide if you never saw that initial number?"
        },
        "Survivorship Bias": {
            "severity": 9,
            "patterns": [
                r"look at (apple|google|facebook|amazon|steve jobs|elon musk)", r"successful companies always",
                r"they made it by", r"billionaires do", r"worked for them"
            ],
            "question": "For every successful example you cited, how many invisible failures did the exact same thing and still failed?"
        },
        "Availability Heuristic": {
            "severity": 6,
            "patterns": [
                r"I just saw", r"recently happened", r"everyone is talking about",
                r"in the news", r"top of mind", r"lately, I'?ve noticed"
            ],
            "question": "Are you prioritizing this because it is statistically probable, or simply because it is easy to recall right now?"
        },
        "Dunning-Kruger / Overconfidence": {
            "severity": 9,
            "patterns": [
                r"100% sure", r"can'?t fail", r"guaranteed to work",
                r"I know everything about", r"foolproof", r"absolute certainty", r"no doubt in my mind"
            ],
            "question": "What are the specific unknown variables in this scenario? If this fails catastrophically, what will be the most likely reason?"
        },
        "Bandwagon Effect": {
            "severity": 7,
            "patterns": [
                r"everyone is doing", r"industry standard", r"all our competitors",
                r"trending", r"jumping on the", r"following the market"
            ],
            "question": "If your competitors were not doing this, would it still make fundamental business sense for your specific company?"
        },
        "Optimism Bias": {
            "severity": 8,
            "patterns": [
                r"best case scenario", r"will definitely succeed", r"nothing can go wrong",
                r"easy win", r"smooth sailing", r"slam dunk"
            ],
            "question": "Have you conducted a premortem? Assume it is one year from now and this project completely failed. Why did it fail?"
        },
        "Pessimism Bias": {
            "severity": 5,
            "patterns": [
                r"bound to fail", r"always goes wrong", r"worst case",
                r"hopeless", r"no way this works", r"doomed"
            ],
            "question": "Are you letting past negative experiences cloud the objective probability of success for this specific instance?"
        },
        "Illusion of Control": {
            "severity": 8,
            "patterns": [
                r"I can control the market", r"completely in my hands", r"my sheer willpower",
                r"I will make it happen", r"we dictate the terms"
            ],
            "question": "What external macroeconomic or market factors exist that are 100% outside of your control?"
        },
        "Planning Fallacy": {
            "severity": 7,
            "patterns": [
                r"will only take a (day|week)", r"quick fix", r"done by tomorrow",
                r"under budget", r"easy to implement", r"won'?t take long"
            ],
            "question": "Historically, how accurate have your time and budget estimates been? Should you apply a 2x or 3x multiplier to this estimate?"
        },
        "Status Quo Bias": {
            "severity": 6,
            "patterns": [
                r"always done it this way", r"change is too risky", r"let'?s stick to what we know",
                r"if it ain'?t broke", r"don'?t rock the boat"
            ],
            "question": "Is the cost of inaction actually higher than the cost of changing? Are you avoiding change purely out of comfort?"
        },
        "Endowment Effect": {
            "severity": 7,
            "patterns": [
                r"my idea is worth more", r"because I built it", r"my baby",
                r"our proprietary", r"we created it so"
            ],
            "question": "If you were acquiring this asset from a third party, would you value it as highly as you do now?"
        },
        "Loss Aversion": {
            "severity": 8,
            "patterns": [
                r"can'?t afford to lose", r"protect what we have", r"avoid losing at all costs",
                r"play it safe", r"minimize loss"
            ],
            "question": "Are you missing out on a massive asymmetric upside because you are disproportionately afraid of a small, manageable downside?"
        },
        "Recency Bias": {
            "severity": 6,
            "patterns": [
                r"the last customer said", r"our latest feedback", r"just yesterday",
                r"most recent data", r"the last meeting"
            ],
            "question": "Does the most recent data point align with the long-term historical trend, or is it an anomaly?"
        },
        "False Consensus Effect": {
            "severity": 7,
            "patterns": [
                r"everyone knows", r"obviously everyone thinks", r"it'?s common sense",
                r"nobody would want", r"users clearly prefer"
            ],
            "question": "Do you have hard quantitative data proving that the majority of your target market shares this belief, or are you projecting?"
        },
        "Action Bias": {
            "severity": 8,
            "patterns": [
                r"do something rather than nothing", r"just ship it", r"act now think later",
                r"move fast and break things", r"we need to act immediately"
            ],
            "question": "Is taking immediate action actually better than waiting for more information? What is the cost of pausing for 24 hours?"
        },
        "Not Invented Here Syndrome": {
            "severity": 7,
            "patterns": [
                r"didn'?t build it ourselves", r"external tools are bad", r"we must build in-house",
                r"custom built is better", r"off the shelf is garbage"
            ],
            "question": "Is building this internally a core competitive advantage, or is it a distraction from your actual product offering?"
        },
        "Authority Bias": {
            "severity": 8,
            "patterns": [
                r"elon musk said", r"the vc told me", r"experts declare",
                r"because the advisor said", r"my mentor thinks"
            ],
            "question": "Even though an authority figure suggested this, does it mathematically and logically apply to your specific company's context?"
        },
        "Scarcity Heuristic": {
            "severity": 7,
            "patterns": [
                r"running out of time", r"limited window", r"now or never",
                r"last chance", r"exploding offer"
            ],
            "question": "Are you making this decision because it's fundamentally sound, or simply because you feel artificial time pressure?"
        },
        "Zero-Risk Bias": {
            "severity": 6,
            "patterns": [
                r"eliminate all risk", r"100% safe", r"absolutely secure",
                r"guarantee no loss", r"completely de-risked"
            ],
            "question": "Is the cost of eliminating the final 1% of risk actually higher than the cost of the risk itself occurring?"
        }
    }

    def __init__(self):
        """Initializes the engine and compiles the regex corpus."""
        self.compiled_patterns: Dict[str, Dict[str, Any]] = {}
        self._compile_corpus()

    def _compile_corpus(self) -> None:
        """Compiles the regex patterns for performance."""
        for bias_name, data in self.TAXONOMY.items():
            compiled_regexes = []
            for pattern in data["patterns"]:
                # Use word boundaries and ignore case for robust matching
                try:
                    compiled = re.compile(rf"\b{pattern}\b", re.IGNORECASE)
                    compiled_regexes.append(compiled)
                except re.error as e:
                    logger.error(f"Failed to compile regex '{pattern}' for {bias_name}: {e}")

            self.compiled_patterns[bias_name] = {
                "severity": data["severity"],
                "question": data["question"],
                "regexes": compiled_regexes
            }

    def scan_segment(self, segment: str) -> List[BiasAlert]:
        """
        Scans a single logical segment (e.g., a sentence) for cognitive biases.

        Args:
            segment (str): The text segment to analyze.

        Returns:
            List[BiasAlert]: A list of detected biases in the segment.
        """
        alerts = []
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"

        for bias_name, data in self.compiled_patterns.items():
            for regex in data["regexes"]:
                match = regex.search(segment)
                if match:
                    alert = BiasAlert(
                        bias_type=bias_name,
                        severity=data["severity"],
                        evidence=match.group(0),
                        counter_question=data["question"],
                        source_segment=segment.strip(),
                        detected_at=timestamp
                    )
                    alerts.append(alert)
                    # Break after first match of a specific bias type in a segment to avoid duplicates
                    break 

        return alerts


class FounderNarrativeAnalyzer:
    """
    Processes raw decision text, splits it into logical segments, and runs 
    multi-pass bias detection using the BiasPatternEngine.
    """

    def __init__(self, severity_threshold: int = 1):
        """
        Args:
            severity_threshold (int): Minimum severity (1-10) for an alert to be included.
        """
        self.engine = BiasPatternEngine()
        self.severity_threshold = severity_threshold

    def _split_into_segments(self, text: str) -> List[str]:
        """
        Splits raw text into logical sentences/segments.

        Args:
            text (str): The raw narrative text.

        Returns:
            List[str]: A list of sentence segments.
        """
        # Replace newlines with spaces
        text = text.replace('\n', ' ')
        # Split by common sentence terminators followed by a space
        segments = re.split(r'(?<=[.!?]) +', text)
        return [seg.strip() for seg in segments if len(seg.strip()) > 5]

    def _calculate_health_score(self, alerts: List[BiasAlert]) -> int:
        """
        Computes the Decision Health Score (0-100) based on bias density and severity.
        
        Args:
            alerts (List[BiasAlert]): Detected biases.

        Returns:
            int: Health score from 0 to 100.
        """
        base_score = 100
        penalty = 0

        for alert in alerts:
            # Higher severity biases carry exponentially more weight
            if alert.severity >= 9:
                penalty += 15
            elif alert.severity >= 7:
                penalty += 10
            elif alert.severity >= 5:
                penalty += 5
            else:
                penalty += 2

        final_score = base_score - penalty
        return max(0, min(final_score, 100))

    def analyze(self, narrative_text: str, document_id: str = "unknown") -> AnalysisReport:
        """
        Analyzes a founder's narrative for cognitive biases.

        Args:
            narrative_text (str): The raw decision text.
            document_id (str): Optional identifier for the document.

        Returns:
            AnalysisReport: The comprehensive analysis report.
        """
        logger.info(f"Starting analysis for document: {document_id}")
        segments = self._split_into_segments(narrative_text)
        all_alerts: List[BiasAlert] = []

        for segment in segments:
            alerts = self.engine.scan_segment(segment)
            filtered_alerts = [a for a in alerts if a.severity >= self.severity_threshold]
            all_alerts.extend(filtered_alerts)

        health_score = self._calculate_health_score(all_alerts)
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"

        report = AnalysisReport(
            document_id=document_id,
            health_score=health_score,
            total_biases_detected=len(all_alerts),
            alerts=all_alerts,
            analyzed_at=timestamp
        )

        logger.info(f"Analysis complete. Score: {health_score}, Biases found: {len(all_alerts)}")
        return report


class ReportExporter:
    """Handles exporting the AnalysisReport to various formats (JSON, Markdown, Terminal)."""

    @staticmethod
    def to_json(report: AnalysisReport, filepath: Optional[str] = None) -> str:
        """Exports report to a JSON string, optionally saving to a file."""
        json_data = json.dumps(report.to_dict(), indent=4)
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(json_data)
            logger.info(f"JSON report saved to {filepath}")
        return json_data

    @staticmethod
    def to_markdown(report: AnalysisReport, filepath: Optional[str] = None) -> str:
        """Exports report to a formatted Markdown string, optionally saving to a file."""
        lines = [
            f"# Cognitive Bias Analysis Report",
            f"**Document ID:** `{report.document_id}`",
            f"**Analyzed At:** `{report.analyzed_at}`",
            f"**Decision Health Score:** `{report.health_score}/100`",
            f"**Total Biases Detected:** `{report.total_biases_detected}`",
            "\n## Detected Biases\n"
        ]

        if not report.alerts:
            lines.append("*No significant cognitive biases detected. Reasoning appears sound.*")
        else:
            for i, alert in enumerate(report.alerts, 1):
                lines.extend([
                    f"### {i}. {alert.bias_type} (Severity: {alert.severity}/10)",
                    f"- **Trigger Evidence:** \"{alert.evidence}\"",
                    f"- **Context Segment:** > {alert.source_segment}",
                    f"- **Socratic Challenge:** **{alert.counter_question}**",
                    ""
                ])

        md_data = "\n".join(lines)
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md_data)
            logger.info(f"Markdown report saved to {filepath}")
        return md_data

    @staticmethod
    def to_terminal(report: AnalysisReport) -> None:
        """Prints a color-formatted summary of the report to the terminal."""
        c = TerminalColors
        print(f"\n{c.HEADER}{c.BOLD}=== ANTIGRAVITY BIAS DETECTOR: ANALYSIS REPORT ==={c.ENDC}")
        print(f"Document ID: {c.OKCYAN}{report.document_id}{c.ENDC}")
        
        # Color code the health score
        score_color = c.OKGREEN
        if report.health_score < 50:
            score_color = c.FAIL
        elif report.health_score < 80:
            score_color = c.WARNING
            
        print(f"Decision Health Score: {score_color}{c.BOLD}{report.health_score}/100{c.ENDC}")
        print(f"Total Biases Detected: {c.WARNING}{report.total_biases_detected}{c.ENDC}\n")

        if not report.alerts:
            print(f"{c.OKGREEN}Excellent! No significant cognitive biases detected.{c.ENDC}\n")
            return

        print(f"{c.UNDERLINE}Detailed Alerts:{c.ENDC}\n")
        for alert in report.alerts:
            severity_color = c.FAIL if alert.severity >= 8 else c.WARNING
            print(f"[{severity_color}Severity {alert.severity}{c.ENDC}] {c.BOLD}{alert.bias_type}{c.ENDC}")
            print(f"  {c.OKBLUE}Evidence:{c.ENDC} \"{alert.evidence}\"")
            print(f"  {c.OKBLUE}Context:{c.ENDC}  {alert.source_segment}")
            print(f"  {c.FAIL}Challenge:{c.ENDC} {alert.counter_question}\n")
        
        print(f"{c.HEADER}=================================================={c.ENDC}\n")


class BatchProcessor:
    """Handles processing multiple decision documents from a directory."""

    def __init__(self, analyzer: FounderNarrativeAnalyzer):
        self.analyzer = analyzer

    def process_directory(self, dir_path: str, output_dir: str, format_type: str = "json") -> None:
        """
        Scans a directory for .txt files, analyzes them, and exports reports.

        Args:
            dir_path (str): Path to the directory containing input texts.
            output_dir (str): Path to the directory where reports will be saved.
            format_type (str): Output format ('json', 'md', or 'both').
        """
        input_path = Path(dir_path)
        out_path = Path(output_dir)
        
        if not input_path.is_dir():
            logger.error(f"Input directory does not exist: {dir_path}")
            sys.exit(1)

        out_path.mkdir(parents=True, exist_ok=True)
        
        text_files = list(input_path.glob("*.txt"))
        if not text_files:
            logger.warning(f"No .txt files found in {dir_path}")
            return

        logger.info(f"Found {len(text_files)} files to process in batch mode.")

        for file_path in text_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                report = self.analyzer.analyze(content, document_id=file_path.name)
                
                base_name = file_path.stem
                if format_type in ["json", "both"]:
                    ReportExporter.to_json(report, str(out_path / f"{base_name}_report.json"))
                if format_type in ["md", "both"]:
                    ReportExporter.to_markdown(report, str(out_path / f"{base_name}_report.md"))
                    
            except Exception as e:
                logger.error(f"Error processing file {file_path.name}: {e}")


def main():
    """CLI Entry point for the Bias Detector."""
    parser = argparse.ArgumentParser(
        description="Antigravity Cognitive Bias Detector & Reasoning Auditor",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--text", type=str, help="Raw text string to analyze")
    input_group.add_argument("--file", type=str, help="Path to a single text file to analyze")
    input_group.add_argument("--dir", type=str, help="Path to a directory of text files for batch processing")

    parser.add_argument("--threshold", type=int, default=1, choices=range(1, 11), 
                        help="Minimum severity threshold (1-10) to flag an alert")
    parser.add_argument("--format", type=str, default="term", choices=["term", "json", "md", "all"],
                        help="Output format for single file/text analysis")
    parser.add_argument("--outdir", type=str, default="./bias_reports",
                        help="Output directory for reports (used with --dir or --format json/md)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging")

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    analyzer = FounderNarrativeAnalyzer(severity_threshold=args.threshold)

    # Handle Batch Directory Mode
    if args.dir:
        batch_format = "both" if args.format == "all" else args.format
        if batch_format == "term":
            batch_format = "json" # Default to json for batch if term is selected
            logger.info("Terminal format not supported for batch, defaulting to JSON output.")
            
        processor = BatchProcessor(analyzer)
        processor.process_directory(args.dir, args.outdir, format_type=batch_format)
        sys.exit(0)

    # Handle Single Text or File Mode
    narrative_text = ""
    doc_id = "cli_input"

    if args.text:
        narrative_text = args.text
    elif args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            logger.error(f"File not found: {args.file}")
            sys.exit(1)
        with open(file_path, 'r', encoding='utf-8') as f:
            narrative_text = f.read()
        doc_id = file_path.name

    if not narrative_text.strip():
        logger.error("Input text is empty.")
        sys.exit(1)

    # Run Analysis
    report = analyzer.analyze(narrative_text, document_id=doc_id)

    # Handle Output
    if args.format in ["term", "all"]:
        ReportExporter.to_terminal(report)
    
    if args.format in ["json", "all"]:
        out_path = Path(args.outdir)
        out_path.mkdir(parents=True, exist_ok=True)
        ReportExporter.to_json(report, str(out_path / f"{doc_id}_report.json"))
        
    if args.format in ["md", "all"]:
        out_path = Path(args.outdir)
        out_path.mkdir(parents=True, exist_ok=True)
        ReportExporter.to_markdown(report, str(out_path / f"{doc_id}_report.md"))


if __name__ == "__main__":
    main()