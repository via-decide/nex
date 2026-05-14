#!/usr/bin/env python3
"""
Nex Deep Research Engine - Research Assistant Interface
=======================================================

This module provides the core command-line research assistant interface for Nex.
It allows users to query distilled knowledge, extract reasoning traces, retrieve
related evidence, and synthesize insights from the Nex knowledge graph.

It operates in two modes:
1. Single-shot query mode (via CLI arguments).
2. Interactive REPL mode (for continuous question-answer interactions).

Usage:
    python -m assistant.research_assistant --query "What are the latest advancements in solid-state batteries?"
    python -m assistant.research_assistant --interactive
"""

import argparse
import dataclasses
import json
import logging
import os
import sys
import textwrap
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("NexResearchAssistant")

# Attempt to import rich for enhanced CLI output. Fallback to standard print if unavailable.
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Prompt
    from rich.table import Table
    from rich.text import Text
    from rich.theme import Theme

    custom_theme = Theme({
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "concept": "magenta",
        "claim": "blue",
    })
    console = Console(theme=custom_theme)
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    logger.warning("The 'rich' library is not installed. Falling back to standard console output.")
    logger.warning("For an enhanced experience, run: pip install rich")

    class ConsoleFallback:
        def print(self, *args, **kwargs):
            print(*args)
        def rule(self, title=""):
            print(f"\n--- {title} ---\n")
        def clear(self):
            os.system('cls' if os.name == 'nt' else 'clear')

    console = ConsoleFallback()


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class Evidence:
    """Represents a piece of evidence retrieved from a source."""
    evidence_id: str
    source_url: str
    snippet: str
    relevance_score: float
    publication_date: Optional[str] = None
    authors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class Claim:
    """Represents a verified claim extracted during the research phase."""
    claim_id: str
    statement: str
    confidence: float
    supporting_evidence: List[Evidence] = field(default_factory=list)
    refuting_evidence: List[Evidence] = field(default_factory=list)

    @property
    def is_verified(self) -> bool:
        return self.confidence > 0.7 and len(self.supporting_evidence) > 0


@dataclass
class Concept:
    """Represents a core concept in the knowledge graph."""
    concept_id: str
    name: str
    definition: str
    related_concepts: List[str] = field(default_factory=list)


@dataclass
class ReasoningTrace:
    """Represents the step-by-step reasoning taken by the agent."""
    step_number: int
    action: str
    observation: str
    conclusion: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class Insight:
    """A synthesized insight derived from multiple claims and concepts."""
    summary: str
    key_takeaways: List[str]
    confidence_level: str  # e.g., "High", "Medium", "Low"
    limitations: List[str]


@dataclass
class QueryResponse:
    """The complete response payload returned to the user."""
    original_query: str
    answer: str
    insights: Insight
    concepts_explored: List[Concept]
    primary_claims: List[Claim]
    reasoning_traces: List[ReasoningTrace]
    execution_time_ms: float


# =============================================================================
# Interfaces
# =============================================================================

class KnowledgeRetriever(ABC):
    """Abstract interface for retrieving knowledge from the Nex Engine."""

    @abstractmethod
    def search_concepts(self, query: str, top_k: int = 5) -> List[Concept]:
        """Search the knowledge graph for related concepts."""
        pass

    @abstractmethod
    def search_claims(self, query: str, top_k: int = 5) -> List[Claim]:
        """Search the knowledge graph for verified claims related to the query."""
        pass

    @abstractmethod
    def get_evidence_for_claim(self, claim_id: str) -> Tuple[List[Evidence], List[Evidence]]:
        """Retrieve supporting and refuting evidence for a specific claim."""
        pass


class InsightSynthesizer(ABC):
    """Abstract interface for synthesizing claims and concepts into insights."""

    @abstractmethod
    def synthesize(self, query: str, concepts: List[Concept], claims: List[Claim]) -> Insight:
        """Synthesize retrieved data into a structured Insight object."""
        pass

    @abstractmethod
    def generate_answer(self, query: str, insight: Insight, claims: List[Claim]) -> str:
        """Generate a natural language answer based on the synthesized insights."""
        pass


# =============================================================================
# Mock / Default Implementations (Fallback if core Nex modules are unavailable)
# =============================================================================

class LocalMockKnowledgeRetriever(KnowledgeRetriever):
    """A mock implementation of the KnowledgeRetriever for testing and demonstration."""
    
    def search_concepts(self, query: str, top_k: int = 5) -> List[Concept]:
        logger.debug(f"Searching concepts for query: '{query}'")
        time.sleep(0.5)  # Simulate network/DB latency
        return [
            Concept(
                concept_id="c_001",
                name="Autonomous Agents",
                definition="AI systems capable of performing tasks without continuous human intervention.",
                related_concepts=["c_002", "c_003"]
            ),
            Concept(
                concept_id="c_002",
                name="Retrieval-Augmented Generation (RAG)",
                definition="A technique that enhances LLMs by retrieving facts from an external knowledge base.",
                related_concepts=["c_001"]
            )
        ][:top_k]

    def search_claims(self, query: str, top_k: int = 5) -> List[Claim]:
        logger.debug(f"Searching claims for query: '{query}'")
        time.sleep(0.8)  # Simulate network/DB latency
        evidence_1 = Evidence(
            evidence_id="e_101",
            source_url="https://arxiv.org/abs/fake1",
            snippet="Our experiments show that autonomous agents reduce research time by 40%.",
            relevance_score=0.92,
            publication_date="2023-10-01",
            authors=["Smith, J.", "Doe, A."]
        )
        return [
            Claim(
                claim_id="cl_001",
                statement="Autonomous research agents significantly reduce literature review time.",
                confidence=0.88,
                supporting_evidence=[evidence_1],
                refuting_evidence=[]
            )
        ][:top_k]

    def get_evidence_for_claim(self, claim_id: str) -> Tuple[List[Evidence], List[Evidence]]:
        time.sleep(0.3)
        return [], []


class HeuristicInsightSynthesizer(InsightSynthesizer):
    """A basic heuristic-based synthesizer for demonstration purposes."""
    
    def synthesize(self, query: str, concepts: List[Concept], claims: List[Claim]) -> Insight:
        logger.debug("Synthesizing insights...")
        time.sleep(1.2)  # Simulate LLM synthesis latency
        
        takeaways = [f"Found {len(concepts)} core concepts related to the query."]
        for claim in claims:
            takeaways.append(f"Verified claim: {claim.statement} (Confidence: {claim.confidence:.2f})")
            
        return Insight(
            summary=f"The research engine analyzed the query '{query}' and extracted several verified claims supported by academic evidence.",
            key_takeaways=takeaways,
            confidence_level="High" if any(c.confidence > 0.8 for c in claims) else "Medium",
            limitations=["Synthesis is based on a limited local knowledge subset."]
        )

    def generate_answer(self, query: str, insight: Insight, claims: List[Claim]) -> str:
        logger.debug("Generating natural language answer...")
        time.sleep(0.7)
        answer = f"Based on the analysis of your query, here is the synthesized answer:\n\n"
        answer += f"{insight.summary}\n\n"
        answer += "Key Points:\n"
        for ta in insight.key_takeaways:
            answer += f"- {ta}\n"
        return answer


# =============================================================================
# Core Assistant Engine
# =============================================================================

class NexResearchAssistant:
    """
    The orchestrator for the Nex Deep Research Engine's interactive assistant.
    Coordinates retrieval, reasoning trace logging, and synthesis.
    """

    def __init__(
        self,
        retriever: Optional[KnowledgeRetriever] = None,
        synthesizer: Optional[InsightSynthesizer] = None
    ):
        """
        Initializes the Research Assistant.
        
        Args:
            retriever: Component responsible for fetching data from the knowledge graph.
            synthesizer: Component responsible for summarizing and generating answers.
        """
        # Inject dependencies or fallback to mocks
        self.retriever = retriever or LocalMockKnowledgeRetriever()
        self.synthesizer = synthesizer or HeuristicInsightSynthesizer()
        self.session_history: List[QueryResponse] = []

    def process_query(self, query: str, max_concepts: int = 5, max_claims: int = 5) -> QueryResponse:
        """
        Processes a natural language query end-to-end.
        
        Args:
            query: The user's research question.
            max_concepts: Maximum number of concepts to retrieve.
            max_claims: Maximum number of claims to retrieve.
            
        Returns:
            QueryResponse: The structured response containing answers, insights, and evidence.
        """
        start_time = time.time()
        reasoning_traces = []

        def log_trace(action: str, observation: str, conclusion: str):
            step = len(reasoning_traces) + 1
            trace = ReasoningTrace(step, action, observation, conclusion)
            reasoning_traces.append(trace)
            logger.debug(f"Trace [{step}]: {action} -> {conclusion}")

        try:
            # Step 1: Concept Retrieval
            log_trace("Querying Concepts", f"Searching KG for '{query}'", "Awaiting results")
            concepts = self.retriever.search_concepts(query, top_k=max_concepts)
            log_trace("Concept Analysis", f"Found {len(concepts)} concepts", f"Extracted keys: {[c.name for c in concepts]}")

            # Step 2: Claim Retrieval
            log_trace("Querying Claims", f"Searching verified claims for '{query}'", "Awaiting results")
            claims = self.retriever.search_claims(query, top_k=max_claims)
            log_trace("Claim Analysis", f"Found {len(claims)} claims", f"Highest confidence: {max([c.confidence for c in claims] + [0]):.2f}")

            # Step 3: Insight Synthesis
            log_trace("Synthesizing Insights", "Aggregating concepts and claims", "Awaiting LLM synthesis")
            insight = self.synthesizer.synthesize(query, concepts, claims)
            log_trace("Insight Generation", "Synthesis complete", f"Confidence level: {insight.confidence_level}")

            # Step 4: Answer Generation
            log_trace("Generating Final Answer", "Formatting insights for user", "Awaiting generation")
            answer = self.synthesizer.generate_answer(query, insight, claims)
            log_trace("Finalization", "Answer generated successfully", "Ready to return")

            execution_time = (time.time() - start_time) * 1000

            response = QueryResponse(
                original_query=query,
                answer=answer,
                insights=insight,
                concepts_explored=concepts,
                primary_claims=claims,
                reasoning_traces=reasoning_traces,
                execution_time_ms=execution_time
            )

            self.session_history.append(response)
            return response

        except Exception as e:
            logger.error(f"Error processing query '{query}': {str(e)}", exc_info=True)
            raise RuntimeError(f"Assistant failed to process query: {str(e)}") from e


# =============================================================================
# CLI Interface & Output Formatting
# =============================================================================

class CLIInterface:
    """Handles the command-line interface, formatting, and user interaction loop."""

    def __init__(self, assistant: NexResearchAssistant):
        self.assistant = assistant

    def display_welcome(self):
        """Displays the welcome banner for the interactive mode."""
        if RICH_AVAILABLE:
            banner = Text("Nex — Deep Research Engine", style="bold magenta", justify="center")
            subtitle = Text("Autonomous Research Agent | Knowledge Synthesizer", style="italic cyan", justify="center")
            panel = Panel(
                Text.assemble(banner, "\n", subtitle),
                border_style="blue",
                padding=(1, 2)
            )
            console.print(panel)
            console.print("[dim]Type 'exit' or 'quit' to end the session. Type 'history' to view previous queries.[/dim]\n")
        else:
            print("=" * 60)
            print(" Nex — Deep Research Engine ")
            print(" Autonomous Research Agent | Knowledge Synthesizer ")
            print("=" * 60)
            print("Type 'exit' or 'quit' to end the session.\n")

    def format_and_print_response(self, response: QueryResponse):
        """Formats the QueryResponse object into a readable console output."""
        if not RICH_AVAILABLE:
            self._print_standard(response)
            return

        # 1. Main Answer Panel
        console.print(Panel(Markdown(response.answer), title="[bold green]Synthesized Answer", border_style="green"))

        # 2. Insights & Takeaways
        insight_text = Text()
        insight_text.append(f"Confidence Level: {response.insights.confidence_level}\n\n", style="bold yellow")
        for i, takeaway in enumerate(response.insights.key_takeaways, 1):
            insight_text.append(f"{i}. {takeaway}\n")
        
        console.print(Panel(insight_text, title="[bold cyan]Key Insights", border_style="cyan"))

        # 3. Evidence & Claims Table
        if response.primary_claims:
            table = Table(title="Verified Claims & Evidence", show_header=True, header_style="bold magenta")
            table.add_column("Confidence", justify="right", style="cyan", no_wrap=True)
            table.add_column("Claim Statement", style="white")
            table.add_column("Sources", style="dim")

            for claim in response.primary_claims:
                sources = len(claim.supporting_evidence)
                table.add_row(
                    f"{claim.confidence*100:.1f}%",
                    claim.statement,
                    f"{sources} sources"
                )
            console.print(table)

        # 4. Concepts Explored
        if response.concepts_explored:
            concepts_str = ", ".join([f"[concept]{c.name}[/concept]" for c in response.concepts_explored])
            console.print(f"\n[bold]Concepts Explored:[/bold] {concepts_str}")

        # 5. Footer / Meta
        console.print(f"\n[dim]Execution Time: {response.execution_time_ms:.2f}ms | Reasoning Steps: {len(response.reasoning_traces)}[/dim]")
        console.rule()

    def _print_standard(self, response: QueryResponse):
        """Fallback printing for standard terminal without rich."""
        print("\n" + "="*40)
        print(" SYNTHESIZED ANSWER")
        print("="*40)
        print(textwrap.fill(response.answer, width=80))
        
        print("\n--- Key Insights ---")
        print(f"Confidence: {response.insights.confidence_level}")
        for ta in response.insights.key_takeaways:
            print(f" * {textwrap.fill(ta, width=76, subsequent_indent='   ')}")
            
        if response.primary_claims:
            print("\n--- Verified Claims ---")
            for claim in response.primary_claims:
                print(f" [{claim.confidence*100:.1f}%] {claim.statement}")
                
        print(f"\n[Execution Time: {response.execution_time_ms:.2f}ms]")
        print("="*40 + "\n")

    def run_interactive_loop(self):
        """Runs the continuous REPL loop for user interaction."""
        self.display_welcome()
        
        while True:
            try:
                if RICH_AVAILABLE:
                    query = Prompt.ask("\n[bold yellow]Nex Query[/bold yellow]")
                else:
                    query = input("\nNex Query > ")

                query = query.strip()
                if not query:
                    continue
                    
                if query.lower() in ['exit', 'quit']:
                    console.print("[bold red]Terminating Nex Research Session. Goodbye.[/bold red]")
                    break
                    
                if query.lower() == 'history':
                    self._show_history()
                    continue

                self._execute_query(query)

            except KeyboardInterrupt:
                console.print("\n[bold red]Session interrupted by user. Exiting...[/bold red]")
                break
            except EOFError:
                break
            except Exception as e:
                console.print(f"[bold red]An unexpected error occurred:[/bold red] {str(e)}")
                logger.exception("Interactive loop error")

    def _execute_query(self, query: str):
        """Executes a single query with progress indication."""
        if RICH_AVAILABLE:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                task = progress.add_task("[cyan]Synthesizing knowledge graph...", total=None)
                response = self.assistant.process_query(query)
                progress.update(task, completed=True)
        else:
            print("Synthesizing knowledge graph... please wait.")
            response = self.assistant.process_query(query)
            
        self.format_and_print_response(response)

    def _show_history(self):
        """Displays the history of queries in the current session."""
        if not self.assistant.session_history:
            console.print("[dim]No queries in current session history.[/dim]")
            return
            
        console.print("\n[bold]Session History:[/bold]")
        for i, req in enumerate(self.assistant.session_history, 1):
            console.print(f" {i}. {req.original_query} [dim]({req.execution_time_ms:.0f}ms)[/dim]")


# =============================================================================
# Main Entry Point
# =============================================================================

def parse_args() -> argparse.Namespace:
    """Parses command line arguments."""
    parser = argparse.ArgumentParser(
        description="Nex Deep Research Engine - Command Line Assistant",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-q", "--query",
        type=str,
        help="A single natural language research question to process."
    )
    group.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Launch the assistant in interactive REPL mode."
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging for reasoning traces and internal states."
    )
    
    parser.add_argument(
        "--export",
        type=str,
        metavar="FILEPATH",
        help="Export the query response to a JSON file (only valid with --query)."
    )

    return parser.parse_args()


def main():
    """Main execution function."""
    args = parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled.")

    # Initialize the Nex Assistant
    # Note: In a full production setup, real Nex KnowledgeRetriever and Synthesizer 
    # instances would be injected here, potentially reading from a config file.
    assistant = NexResearchAssistant()
    cli = CLIInterface(assistant)

    if args.interactive:
        if args.export:
            logger.warning("The --export flag is ignored in interactive mode.")
        cli.run_interactive_loop()
        
    elif args.query:
        try:
            response = assistant.process_query(args.query)
            cli.format_and_print_response(response)
            
            if args.export:
                export_path = os.path.abspath(args.export)
                # Convert dataclass to dict, handling datetime/custom objects
                def custom_serializer(obj):
                    if hasattr(obj, 'to_dict'):
                        return obj.to_dict()
                    if dataclasses.is_dataclass(obj):
                        return dataclasses.asdict(obj)
                    raise TypeError(f"Type {type(obj)} not serializable")

                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(response, f, default=custom_serializer, indent=2)
                console.print(f"[success]Results successfully exported to: {export_path}[/success]")
                
        except Exception as e:
            console.print(f"[error]Failed to process query:[/error] {str(e)}")
            sys.exit(1)


if __name__ == "__main__":
    main()