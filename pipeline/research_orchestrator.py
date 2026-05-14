#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Nex Deep Research Engine - Research Pipeline Orchestrator
=========================================================

This module provides the core orchestration engine for the Nex autonomous research
agent. It manages the complex, multi-stage lifecycle of transforming raw notes,
queries, and retrieved sources into distilled knowledge graphs and comprehensive
book-length outputs.

Key Capabilities:
    - Directed Acyclic Graph (DAG) based pipeline stage execution.
    - Asynchronous concurrency for independent research stages.
    - Comprehensive state management and checkpointing.
    - Deep integration hooks for the Zayvora corpus export system.
    - Robust error handling, retries, and execution logging.

Usage:
    orchestrator = ResearchOrchestrator(config=PipelineConfig(...))
    orchestrator.register_stage(RawNotesIngestionStage())
    orchestrator.register_stage(KnowledgeExtractionStage(dependencies=["RawNotesIngestionStage"]))
    ...
    context = await orchestrator.run_pipeline(initial_query="Impact of AGI on global economics")
"""

import abc
import asyncio
import dataclasses
import datetime
import enum
import json
import logging
import os
import pathlib
import time
import traceback
import uuid
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union

# =============================================================================
# Logging Configuration
# =============================================================================

logger = logging.getLogger("Nex.ResearchOrchestrator")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# =============================================================================
# Exceptions
# =============================================================================

class OrchestratorError(Exception):
    """Base exception for all Orchestrator-related errors."""
    pass

class CyclicDependencyError(OrchestratorError):
    """Raised when a cyclic dependency is detected in pipeline stages."""
    pass

class MissingDependencyError(OrchestratorError):
    """Raised when a stage declares a dependency that is not registered."""
    pass

class StageExecutionError(OrchestratorError):
    """Raised when an individual pipeline stage fails during execution."""
    def __init__(self, stage_name: str, original_error: Exception):
        super().__init__(f"Stage '{stage_name}' failed: {str(original_error)}")
        self.stage_name = stage_name
        self.original_error = original_error

# =============================================================================
# Enums and Data Structures
# =============================================================================

class StageStatus(enum.Enum):
    """Represents the lifecycle state of a pipeline stage."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"

class ExportFormat(enum.Enum):
    """Supported export formats for the Zayvora corpus."""
    JSONL = "jsonl"
    MARKDOWN = "markdown"
    KNOWLEDGE_GRAPH_JSON = "kg_json"
    ZAYVORA_BUNDLE = "zayvora_bundle"

@dataclasses.dataclass
class ResearchMetrics:
    """Tracks performance and resource metrics across the research pipeline."""
    start_time: float = dataclasses.field(default_factory=time.time)
    end_time: Optional[float] = None
    total_sources_analyzed: int = 0
    claims_verified: int = 0
    tokens_consumed: int = 0
    api_calls_made: int = 0
    nodes_generated: int = 0
    edges_generated: int = 0

    @property
    def execution_duration_seconds(self) -> float:
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time

@dataclasses.dataclass
class PipelineConfig:
    """Configuration parameters for the Research Orchestrator."""
    workspace_dir: pathlib.Path = dataclasses.field(default_factory=lambda: pathlib.Path("./workspace"))
    max_concurrent_stages: int = 5
    enable_checkpointing: bool = True
    fail_fast: bool = True
    zayvora_endpoint: Optional[str] = None
    zayvora_api_key: Optional[str] = None
    max_retries_per_stage: int = 3
    debug_mode: bool = False

class ResearchContext:
    """
    The central memory and state repository passed through the pipeline.
    Stages read from and write to this context.
    """
    def __init__(self, query: str, config: PipelineConfig):
        self.run_id: str = str(uuid.uuid4())
        self.query: str = query
        self.config: PipelineConfig = config
        self.metrics: ResearchMetrics = ResearchMetrics()
        
        # Core Data Stores
        self.raw_notes: List[Dict[str, Any]] = []
        self.retrieved_sources: List[Dict[str, Any]] = []
        self.verified_claims: List[Dict[str, Any]] = []
        self.knowledge_graph: Dict[str, Any] = {"nodes": [], "edges": []}
        self.distilled_knowledge: str = ""
        self.book_chapters: List[Dict[str, str]] = []
        
        # Shared key-value store for arbitrary stage-to-stage communication
        self.shared_state: Dict[str, Any] = {}
        
        # Stage status tracking
        self.stage_statuses: Dict[str, StageStatus] = {}
        self.stage_errors: Dict[str, str] = {}

        # Setup workspace
        self.run_dir = self.config.workspace_dir / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(self, stage_name: str) -> None:
        """Serializes the current context state to disk."""
        if not self.config.enable_checkpointing:
            return
            
        checkpoint_file = self.run_dir / f"checkpoint_{stage_name}.json"
        
        # We selectively serialize to avoid non-serializable objects
        state_dict = {
            "run_id": self.run_id,
            "query": self.query,
            "metrics": dataclasses.asdict(self.metrics),
            "raw_notes_count": len(self.raw_notes),
            "sources_count": len(self.retrieved_sources),
            "claims_count": len(self.verified_claims),
            "stage_statuses": {k: v.value for k, v in self.stage_statuses.items()},
            "shared_state_keys": list(self.shared_state.keys())
        }
        
        try:
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(state_dict, f, indent=2)
            logger.debug(f"Checkpoint saved for stage '{stage_name}' at {checkpoint_file}")
        except Exception as e:
            logger.warning(f"Failed to save checkpoint for '{stage_name}': {e}")

# =============================================================================
# Pipeline Stage Architecture
# =============================================================================

class PipelineStage(abc.ABC):
    """
    Abstract Base Class representing a single, discrete step in the research pipeline.
    """
    
    def __init__(self, name: str, dependencies: Optional[List[str]] = None, retries: int = 0):
        self.name = name
        self.dependencies = dependencies or []
        self.retries = retries
        self.logger = logging.getLogger(f"Nex.Stage.{self.name}")

    @abc.abstractmethod
    async def execute(self, context: ResearchContext) -> None:
        """
        The core logic of the pipeline stage.
        
        Args:
            context (ResearchContext): The shared state of the research run.
            
        Raises:
            Exception: Any exception raised will be caught by the orchestrator
                       and mark the stage as FAILED.
        """
        pass

    async def validate(self, context: ResearchContext) -> bool:
        """
        Optional pre-execution validation. If it returns False, the stage is SKIPPED.
        """
        return True

    async def rollback(self, context: ResearchContext) -> None:
        """
        Optional cleanup logic executed if the stage fails or the pipeline is cancelled.
        """
        self.logger.debug(f"No rollback defined for {self.name}")

# =============================================================================
# Core Orchestrator Implementation
# =============================================================================

class ResearchOrchestrator:
    """
    Manages the registration, dependency resolution, and execution of research pipeline stages.
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self.stages: Dict[str, PipelineStage] = {}
        self._execution_events: Dict[str, asyncio.Event] = {}
        self._execution_lock = asyncio.Lock()

    def register_stage(self, stage: PipelineStage) -> None:
        """
        Registers a new stage in the orchestrator.
        
        Args:
            stage: An instance of a subclass of PipelineStage.
        """
        if stage.name in self.stages:
            logger.warning(f"Overwriting existing stage: {stage.name}")
        self.stages[stage.name] = stage
        logger.info(f"Registered stage: {stage.name} (Dependencies: {stage.dependencies})")

    def _validate_dag(self) -> None:
        """
        Validates that all dependencies exist and that there are no cyclic dependencies.
        """
        # 1. Check for missing dependencies
        for stage_name, stage in self.stages.items():
            for dep in stage.dependencies:
                if dep not in self.stages:
                    raise MissingDependencyError(
                        f"Stage '{stage_name}' depends on '{dep}', which is not registered."
                    )

        # 2. Check for cycles using DFS
        visited: Set[str] = set()
        path: Set[str] = set()

        def dfs(node: str):
            if node in path:
                raise CyclicDependencyError(f"Cycle detected involving stage: {node}")
            if node in visited:
                return
            
            path.add(node)
            for dep in self.stages[node].dependencies:
                dfs(dep)
            path.remove(node)
            visited.add(node)

        for stage_name in self.stages:
            dfs(stage_name)
            
        logger.debug("DAG validation passed. No cycles detected.")

    async def _execute_stage_with_retries(self, stage: PipelineStage, context: ResearchContext) -> None:
        """Executes a single stage, handling retries and context updates."""
        context.stage_statuses[stage.name] = StageStatus.RUNNING
        attempts = 0
        max_attempts = stage.retries + 1

        while attempts < max_attempts:
            attempts += 1
            try:
                stage.logger.info(f"Starting execution (Attempt {attempts}/{max_attempts})...")
                
                # Check validation
                should_run = await stage.validate(context)
                if not should_run:
                    stage.logger.info("Validation returned False. Skipping stage.")
                    context.stage_statuses[stage.name] = StageStatus.SKIPPED
                    return

                # Execute
                start_time = time.time()
                await stage.execute(context)
                duration = time.time() - start_time
                
                stage.logger.info(f"Execution completed successfully in {duration:.2f}s.")
                context.stage_statuses[stage.name] = StageStatus.COMPLETED
                context.save_checkpoint(stage.name)
                return

            except Exception as e:
                stage.logger.error(f"Execution failed: {str(e)}\n{traceback.format_exc()}")
                if attempts >= max_attempts:
                    context.stage_statuses[stage.name] = StageStatus.FAILED
                    context.stage_errors[stage.name] = str(e)
                    
                    # Attempt rollback
                    try:
                        await stage.rollback(context)
                    except Exception as rollback_err:
                        stage.logger.error(f"Rollback failed: {rollback_err}")
                        
                    raise StageExecutionError(stage.name, e)
                else:
                    backoff = 2 ** attempts
                    stage.logger.info(f"Retrying in {backoff} seconds...")
                    await asyncio.sleep(backoff)

    async def _wait_for_dependencies(self, stage: PipelineStage, context: ResearchContext) -> bool:
        """
        Waits for all dependencies of a stage to complete.
        Returns True if all dependencies succeeded, False if any failed (or skipped if strict).
        """
        if not stage.dependencies:
            return True

        stage.logger.debug(f"Waiting for dependencies: {stage.dependencies}")
        
        # Wait for all dependency events to be set
        await asyncio.gather(*(self._execution_events[dep].wait() for dep in stage.dependencies))

        # Check the status of dependencies
        for dep in stage.dependencies:
            dep_status = context.stage_statuses.get(dep)
            if dep_status in (StageStatus.FAILED, StageStatus.CANCELLED):
                stage.logger.warning(f"Dependency '{dep}' failed. Cancelling execution.")
                return False
        return True

    async def _stage_runner(self, stage: PipelineStage, context: ResearchContext, semaphore: asyncio.Semaphore) -> None:
        """Wrapper to manage dependency waiting, concurrency limits, and event signaling."""
        try:
            # 1. Wait for DAG dependencies
            deps_ok = await self._wait_for_dependencies(stage, context)
            
            if not deps_ok:
                context.stage_statuses[stage.name] = StageStatus.CANCELLED
                return

            # 2. Acquire concurrency semaphore and run
            async with semaphore:
                # If fail_fast is enabled and another stage failed, abort.
                if self.config.fail_fast and any(s == StageStatus.FAILED for s in context.stage_statuses.values()):
                    stage.logger.warning("Aborting due to fail_fast policy (another stage failed).")
                    context.stage_statuses[stage.name] = StageStatus.CANCELLED
                    return
                    
                await self._execute_stage_with_retries(stage, context)

        except Exception as e:
            logger.error(f"Critical error in stage runner for {stage.name}: {e}")
        finally:
            # 3. Always set the event so dependent stages can unblock (and subsequently fail/cancel)
            self._execution_events[stage.name].set()

    async def run_pipeline(self, query: str) -> ResearchContext:
        """
        Executes the entire research pipeline for a given query.
        
        Args:
            query: The initial natural language research question.
            
        Returns:
            ResearchContext: The final state of the research run.
        """
        async with self._execution_lock:
            logger.info(f"Initializing pipeline run for query: '{query}'")
            self._validate_dag()

            context = ResearchContext(query=query, config=self.config)
            
            # Initialize events and statuses
            self._execution_events = {name: asyncio.Event() for name in self.stages}
            for name in self.stages:
                context.stage_statuses[name] = StageStatus.PENDING

            # Concurrency control
            semaphore = asyncio.Semaphore(self.config.max_concurrent_stages)

            # Create tasks for all stages
            tasks = []
            for stage in self.stages.values():
                task = asyncio.create_task(self._stage_runner(stage, context, semaphore))
                tasks.append(task)

            # Wait for all stages to resolve
            await asyncio.gather(*tasks)

            # Finalize metrics
            context.metrics.end_time = time.time()
            
            # Check overall success
            failed_stages = [name for name, status in context.stage_statuses.items() if status == StageStatus.FAILED]
            if failed_stages:
                logger.error(f"Pipeline completed with errors in stages: {failed_stages}")
            else:
                logger.info(f"Pipeline completed successfully in {context.metrics.execution_duration_seconds:.2f}s")

            return context

# =============================================================================
# Zayvora Integration Hooks
# =============================================================================

class ZayvoraExporter:
    """
    Handles the transformation and transmission of Nex research outputs into
    the Zayvora corpus format.
    """
    
    def __init__(self, endpoint: Optional[str], api_key: Optional[str]):
        self.endpoint = endpoint
        self.api_key = api_key
        self.logger = logging.getLogger("Nex.ZayvoraExporter")

    def format_for_zayvora(self, context: ResearchContext, format_type: ExportFormat) -> str:
        """Transforms the ResearchContext into a specific Zayvora-compatible format."""
        
        self.logger.info(f"Formatting context into {format_type.value} for Zayvora.")
        
        if format_type == ExportFormat.JSONL:
            lines = []
            # Export verified claims as distinct knowledge items
            for claim in context.verified_claims:
                lines.append(json.dumps({
                    "id": str(uuid.uuid4()),
                    "type": "verified_claim",
                    "content": claim.get("text", ""),
                    "confidence": claim.get("confidence", 0.0),
                    "sources": claim.get("source_ids", []),
                    "metadata": {"query": context.query, "run_id": context.run_id}
                }))
            return "\n".join(lines)
            
        elif format_type == ExportFormat.KNOWLEDGE_GRAPH_JSON:
            kg_payload = {
                "corpus_id": f"nex_{context.run_id}",
                "entities": context.knowledge_graph.get("nodes", []),
                "relations": context.knowledge_graph.get("edges", []),
                "provenance": "Nex Autonomous Research Agent"
            }
            return json.dumps(kg_payload, indent=2)
            
        elif format_type == ExportFormat.ZAYVORA_BUNDLE:
            bundle = {
                "metadata": {
                    "query": context.query,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "metrics": dataclasses.asdict(context.metrics)
                },
                "distilled_knowledge": context.distilled_knowledge,
                "book_chapters": context.book_chapters,
                "kg_summary": f"Nodes: {len(context.knowledge_graph.get('nodes', []))} | Edges: {len(context.knowledge_graph.get('edges', []))}"
            }
            return json.dumps(bundle, indent=2)
            
        else:
            raise ValueError(f"Unsupported Zayvora export format: {format_type}")

    async def push_to_corpus(self, payload: str, format_type: ExportFormat) -> bool:
        """
        Pushes the formatted payload to the Zayvora ingestion endpoint.
        Uses a mocked async request for the architecture definition.
        """
        if not self.endpoint:
            self.logger.warning("No Zayvora endpoint configured. Simulating successful export.")
            # Simulate network delay
            await asyncio.sleep(1.5)
            self.logger.info(f"Simulated push of {len(payload)} bytes to Zayvora.")
            return True

        self.logger.info(f"Transmitting {len(payload)} bytes to Zayvora endpoint: {self.endpoint}")
        # In a real implementation, use aiohttp or httpx here.
        # Example:
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(
        #         self.endpoint,
        #         headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        #         data=payload
        #     )
        #     response.raise_for_status()
        
        await asyncio.sleep(2.0) # Mock transmission
        self.logger.info("Successfully pushed payload to Zayvora.")
        return True


class ZayvoraExportStage(PipelineStage):
    """
    Pipeline stage dedicated to exporting the final research results to Zayvora.
    """
    def __init__(self, name: str = "ZayvoraExportStage", dependencies: Optional[List[str]] = None):
        super().__init__(name, dependencies, retries=2)

    async def execute(self, context: ResearchContext) -> None:
        self.logger.info("Initiating Zayvora Corpus Export...")
        
        exporter = ZayvoraExporter(
            endpoint=context.config.zayvora_endpoint,
            api_key=context.config.zayvora_api_key
        )
        
        # Format as a comprehensive bundle
        payload = exporter.format_for_zayvora(context, ExportFormat.ZAYVORA_BUNDLE)
        
        # Save locally for audit
        export_path = context.run_dir / "zayvora_export.json"
        with open(export_path, "w", encoding="utf-8") as f:
            f.write(payload)
        self.logger.debug(f"Saved local copy of export to {export_path}")
        
        # Push to remote
        success = await exporter.push_to_corpus(payload, ExportFormat.ZAYVORA_BUNDLE)
        if not success:
            raise OrchestratorError("Failed to push corpus to Zayvora.")
            
        context.shared_state["zayvora_exported"] = True

# =============================================================================
# Standard Research Pipeline Stages (Implementations)
# =============================================================================

class QueryExpansionStage(PipelineStage):
    """Expands the initial natural language query into multiple targeted search vectors."""
    
    async def execute(self, context: ResearchContext) -> None:
        self.logger.info(f"Expanding query: {context.query}")
        # Mocking LLM query expansion
        await asyncio.sleep(1.0)
        expanded_queries = [
            f"{context.query} academic papers",
            f"{context.query} historical context",
            f"{context.query} statistical data 2020-2025"
        ]
        context.shared_state["search_queries"] = expanded_queries
        context.metrics.api_calls_made += 1
        context.metrics.tokens_consumed += 150
        self.logger.info(f"Generated {len(expanded_queries)} search vectors.")


class SourceRetrievalStage(PipelineStage):
    """Autonomously queries open-access sources (e.g., ArXiv, Wikipedia, Web)."""
    
    async def execute(self, context: ResearchContext) -> None:
        queries = context.shared_state.get("search_queries", [context.query])
        self.logger.info(f"Retrieving sources for {len(queries)} queries...")
        
        # Mocking retrieval process
        await asyncio.sleep(2.5)
        
        for i, q in enumerate(queries):
            context.retrieved_sources.append({
                "id": f"source_{i}",
                "url": f"https://mock-academic-db.org/doc_{i}",
                "title": f"Analysis of {q[:10]}...",
                "content": f"Extensive raw text retrieved for query '{q}'...",
                "reliability_score": 0.85 + (i * 0.02)
            })
            
        context.metrics.total_sources_analyzed += len(context.retrieved_sources)
        self.logger.info(f"Retrieved {len(context.retrieved_sources)} high-quality sources.")


class ClaimVerificationStage(PipelineStage):
    """Extracts claims from sources and cross-references them for veracity."""
    
    async def execute(self, context: ResearchContext) -> None:
        self.logger.info("Extracting and verifying claims from sources...")
        
        if not context.retrieved_sources:
            self.logger.warning("No sources to verify.")
            return

        # Mocking LLM extraction and verification
        await asyncio.sleep(3.0)
        
        for source in context.retrieved_sources:
            # Generate a mock claim for each source
            context.verified_claims.append({
                "claim_id": f"claim_{uuid.uuid4().hex[:8]}",
                "text": f"Derived truth from {source['title']}",
                "confidence": source["reliability_score"] * 0.95,
                "source_ids": [source["id"]]
            })
            
        context.metrics.claims_verified += len(context.verified_claims)
        context.metrics.api_calls_made += len(context.retrieved_sources)
        context.metrics.tokens_consumed += 2500
        self.logger.info(f"Verified {len(context.verified_claims)} distinct claims.")


class KnowledgeGraphBuildStage(PipelineStage):
    """Constructs a structured entity-relationship graph from verified claims."""
    
    async def execute(self, context: ResearchContext) -> None:
        self.logger.info("Building Knowledge Graph...")
        
        await asyncio.sleep(2.0)
        
        nodes = []
        edges = []
        
        # Create a central node for the query
        central_node = {"id": "N0", "label": "Core Subject", "properties": {"name": context.query}}
        nodes.append(central_node)
        
        for i, claim in enumerate(context.verified_claims):
            node_id = f"N{i+1}"
            nodes.append({"id": node_id, "label": "VerifiedFact", "properties": {"text": claim["text"]}})
            edges.append({"source": "N0", "target": node_id, "relation": "SUPPORTS"})
            
        context.knowledge_graph = {"nodes": nodes, "edges": edges}
        context.metrics.nodes_generated = len(nodes)
        context.metrics.edges_generated = len(edges)
        
        self.logger.info(f"Graph built with {len(nodes)} nodes and {len(edges)} edges.")


class SynthesisStage(PipelineStage):
    """Synthesizes the knowledge graph and claims into a cohesive distilled format."""
    
    async def execute(self, context: ResearchContext) -> None:
        self.logger.info("Synthesizing findings into distilled knowledge...")
        
        await asyncio.sleep(3.5)
        
        synthesis = f"# Distilled Research: {context.query}\n\n"
        synthesis += "## Executive Summary\n"
        synthesis += f"Based on {len(context.retrieved_sources)} sources and {len(context.verified_claims)} verified claims, "
        synthesis += "the following synthesis has been generated by the Nex engine.\n\n"
        
        synthesis += "## Core Findings\n"
        for claim in context.verified_claims:
            synthesis += f"- {claim['text']} (Confidence: {claim['confidence']:.2f})\n"
            
        context.distilled_knowledge = synthesis
        context.metrics.api_calls_made += 1
        context.metrics.tokens_consumed += 4000
        self.logger.info("Synthesis complete.")


class BookOutputStage(PipelineStage):
    """Transforms distilled knowledge into structured book chapters."""
    
    async def execute(self, context: ResearchContext) -> None:
        self.logger.info("Generating long-form Book Output...")
        
        if not context.distilled_knowledge:
            raise OrchestratorError("Cannot generate book without distilled knowledge.")
            
        await asyncio.sleep(4.0)
        
        chapters = [
            {"title": "Chapter 1: Introduction and Context", "content": f"Introduction to {context.query}...\n" + context.distilled_knowledge[:200]},
            {"title": "Chapter 2: Evidence and Analysis", "content": "Detailed breakdown of the verified claims..."},
            {"title": "Chapter 3: Implications and Conclusion", "content": "Final synthesized thoughts from the Nex engine."}
        ]
        
        context.book_chapters = chapters
        
        # Save the book to workspace
        book_path = context.run_dir / "final_book.md"
        with open(book_path, "w", encoding="utf-8") as f:
            f.write(f"# {context.query.title()}\n\n")
            for chap in chapters:
                f.write(f"## {chap['title']}\n\n{chap['content']}\n\n")
                
        self.logger.info(f"Book generated with {len(chapters)} chapters. Saved to {book_path}")

# =============================================================================
# Factory Methods
# =============================================================================

def create_default_research_pipeline(config: Optional[PipelineConfig] = None) -> ResearchOrchestrator:
    """
    Factory function to instantiate a fully configured ResearchOrchestrator
    with the standard Nex Deep Research DAG.
    """
    orchestrator = ResearchOrchestrator(config=config)
    
    # 1. Query Expansion
    orchestrator.register_stage(QueryExpansionStage(name="QueryExpansion"))
    
    # 2. Source Retrieval (depends on Expansion)
    orchestrator.register_stage(SourceRetrievalStage(
        name="SourceRetrieval", 
        dependencies=["QueryExpansion"],
        retries=2
    ))
    
    # 3. Claim Verification (depends on Retrieval)
    orchestrator.register_stage(ClaimVerificationStage(
        name="ClaimVerification", 
        dependencies=["SourceRetrieval"],
        retries=1
    ))
    
    # 4. Knowledge Graph Construction (depends on Verification)
    orchestrator.register_stage(KnowledgeGraphBuildStage(
        name="KnowledgeGraphBuild", 
        dependencies=["ClaimVerification"]
    ))
    
    # 5. Synthesis (depends on Graph Build)
    orchestrator.register_stage(SynthesisStage(
        name="Synthesis", 
        dependencies=["KnowledgeGraphBuild"]
    ))
    
    # 6. Book Generation (depends on Synthesis)
    orchestrator.register_stage(BookOutputStage(
        name="BookOutput", 
        dependencies=["Synthesis"]
    ))
    
    # 7. Zayvora Export (depends on Book Output, end of pipeline)
    orchestrator.register_stage(ZayvoraExportStage(
        name="ZayvoraExport", 
        dependencies=["BookOutput"],
        retries=3
    ))
    
    return orchestrator

# =============================================================================
# Example Entrypoint (For testing/standalone execution)
# =============================================================================

if __name__ == "__main__":
    async def main():
        # Configuration setup
        config = PipelineConfig(
            workspace_dir=pathlib.Path("./nex_workspace"),
            max_concurrent_stages=3,
            debug_mode=True,
            zayvora_endpoint="https://api.zayvora.com/v1/corpus/ingest" # Mock endpoint
        )
        
        # Build Pipeline
        orchestrator = create_default_research_pipeline(config)
        
        # Execute
        query = "The role of quantum computing in accelerating material science discovery"
        try:
            final_context = await orchestrator.run_pipeline(query)
            
            # Print summary
            print("\n" + "="*50)
            print("RESEARCH RUN COMPLETE")
            print("="*50)
            print(f"Run ID: {final_context.run_id}")
            print(f"Query: {final_context.query}")
            print(f"Duration: {final_context.metrics.execution_duration_seconds:.2f} seconds")
            print(f"Sources Analyzed: {final_context.metrics.total_sources_analyzed}")
            print(f"Claims Verified: {final_context.metrics.claims_verified}")
            print(f"Graph Entities: {final_context.metrics.nodes_generated} Nodes, {final_context.metrics.edges_generated} Edges")
            print(f"Book Chapters Generated: {len(final_context.book_chapters)}")
            print("="*50 + "\n")
            
        except Exception as e:
            logger.critical(f"Pipeline execution failed critically: {e}")
            
    # Run the async event loop
    asyncio.run(main())