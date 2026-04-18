import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Union

# ==============================================================================
# Logging Configuration
# ==============================================================================
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# ==============================================================================
# Custom Exceptions
# ==============================================================================
class DecisionBridgeError(Exception):
    """Base exception for all errors within the Decision Engine Bridge."""
    pass


class InvalidInsightError(DecisionBridgeError):
    """Raised when the provided Nex insight is malformed or invalid."""
    pass


class CriteriaMappingError(DecisionBridgeError):
    """Raised when there is a failure in mapping claims to decision criteria."""
    pass


class PayloadExportError(DecisionBridgeError):
    """Raised when the decision payload cannot be serialized or exported."""
    pass


# ==============================================================================
# Data Models: Nex Research Agent (Input Domain)
# ==============================================================================
@dataclass
class NexSource:
    """Represents an open-access source queried by the Nex engine."""
    url: str
    title: Optional[str] = None
    credibility_score: float = 0.0
    access_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        if not (0.0 <= self.credibility_score <= 1.0):
            logger.warning(f"Source credibility score {self.credibility_score} out of bounds (0-1). Clamping.")
            self.credibility_score = max(0.0, min(1.0, self.credibility_score))


@dataclass
class NexClaim:
    """Represents a verified claim extracted by the Nex knowledge graph."""
    claim_id: str
    text: str
    is_verified: bool
    confidence_score: float
    sources: List[NexSource]
    keywords: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.claim_id:
            self.claim_id = f"claim_{uuid.uuid4().hex[:8]}"
        if not (0.0 <= self.confidence_score <= 1.0):
            logger.warning(f"Claim confidence score {self.confidence_score} out of bounds (0-1). Clamping.")
            self.confidence_score = max(0.0, min(1.0, self.confidence_score))


@dataclass
class NexInsight:
    """Represents a synthesized finding from the Nex research report."""
    insight_id: str
    summary: str
    claims: List[NexClaim]
    synthesis_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class NexResearchReport:
    """The root object representing a complete Nex autonomous research report."""
    report_id: str
    original_query: str
    insights: List[NexInsight]
    global_confidence: float
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ==============================================================================
# Data Models: Decide Engine Tools (Output Domain)
# ==============================================================================
@dataclass
class DecisionEvidence:
    """Evidence backing a specific decision criterion."""
    evidence_id: str
    description: str
    source_urls: List[str]
    reliability_score: float


@dataclass
class DecisionCriterion:
    """A mapped criterion ready for evaluation by decide.engine-tools."""
    criterion_id: str
    name: str
    satisfaction_level: float  # 0.0 to 1.0 indicating how well the criterion is met
    evidence: List[DecisionEvidence]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionInputPayload:
    """The final JSON-ready payload to be fed into the decision engine."""
    decision_session_id: str
    context_query: str
    criteria: List[DecisionCriterion]
    aggregate_reliability: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    bridge_version: str = "1.0.0"

    def to_json(self, indent: int = 2) -> str:
        """Serializes the payload to a JSON string."""
        try:
            return json.dumps(asdict(self), indent=indent)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize DecisionInputPayload: {e}")
            raise PayloadExportError("Failed to convert payload to JSON.") from e


# ==============================================================================
# Mapping Strategies
# ==============================================================================
class CriteriaMappingStrategy(ABC):
    """Abstract base class for strategies that map Nex claims to Decision criteria."""
    
    @abstractmethod
    def map_claims(self, claims: List[NexClaim]) -> List[DecisionCriterion]:
        """
        Maps a list of Nex claims to a list of Decision criteria.
        
        Args:
            claims: List of verified claims from the research report.
            
        Returns:
            List of DecisionCriterion objects.
        """
        pass


class KeywordCriteriaMapper(CriteriaMappingStrategy):
    """
    A concrete mapping strategy that uses keyword intersection to map claims
    to predefined decision criteria.
    """

    def __init__(self, criteria_definitions: Dict[str, List[str]]):
        """
        Initializes the KeywordCriteriaMapper.

        Args:
            criteria_definitions: A dictionary mapping criterion names to a list of keywords.
                                  Example: {"Financial Viability": ["cost", "revenue", "roi"]}
        """
        self.criteria_definitions = criteria_definitions
        logger.info(f"Initialized KeywordCriteriaMapper with {len(criteria_definitions)} criteria definitions.")

    def map_claims(self, claims: List[NexClaim]) -> List[DecisionCriterion]:
        """
        Maps claims to criteria based on keyword overlap. Aggregates confidence
        and builds evidence lists for each matched criterion.
        """
        criteria_map: Dict[str, DecisionCriterion] = {}

        for claim in claims:
            if not claim.is_verified:
                logger.debug(f"Skipping unverified claim: {claim.claim_id}")
                continue

            claim_keywords = set(k.lower() for k in claim.keywords)
            
            for crit_name, crit_keywords in self.criteria_definitions.items():
                crit_keyword_set = set(k.lower() for k in crit_keywords)
                
                # Check for intersection between claim keywords and criteria keywords
                if claim_keywords.intersection(crit_keyword_set):
                    logger.debug(f"Claim {claim.claim_id} mapped to criterion '{crit_name}'")
                    
                    if crit_name not in criteria_map:
                        criteria_map[crit_name] = DecisionCriterion(
                            criterion_id=f"crit_{uuid.uuid4().hex[:8]}",
                            name=crit_name,
                            satisfaction_level=0.0,
                            evidence=[]
                        )
                    
                    # Create evidence from the claim
                    evidence = DecisionEvidence(
                        evidence_id=f"ev_{uuid.uuid4().hex[:8]}",
                        description=claim.text,
                        source_urls=[src.url for src in claim.sources if src.url],
                        reliability_score=claim.confidence_score
                    )
                    criteria_map[crit_name].evidence.append(evidence)

        # Post-process to calculate aggregated satisfaction levels
        return self._calculate_aggregates(list(criteria_map.values()))

    def _calculate_aggregates(self, criteria: List[DecisionCriterion]) -> List[DecisionCriterion]:
        """Calculates the overall satisfaction level for each criterion based on its evidence."""
        for crit in criteria:
            if crit.evidence:
                # Simple average of evidence reliability scores for satisfaction level
                # In a more advanced implementation, this could be weighted by source credibility
                total_reliability = sum(ev.reliability_score for ev in crit.evidence)
                crit.satisfaction_level = total_reliability / len(crit.evidence)
                logger.debug(f"Criterion '{crit.name}' satisfaction calculated at {crit.satisfaction_level:.2f}")
            else:
                crit.satisfaction_level = 0.0
        return criteria


# ==============================================================================
# Core Adapter: InsightToDecisionAdapter
# ==============================================================================
class InsightToDecisionAdapter:
    """
    The primary bridge component responsible for converting Nex research reports
    and insights into decision-ready inputs for decide.engine-tools.
    """

    def __init__(
        self, 
        mapping_strategy: CriteriaMappingStrategy,
        min_global_confidence_threshold: float = 0.5,
        strict_mode: bool = False
    ):
        """
        Initializes the InsightToDecisionAdapter.

        Args:
            mapping_strategy: The strategy injected to handle claim-to-criteria mapping.
            min_global_confidence_threshold: The minimum global confidence required to process a report.
            strict_mode: If True, raises exceptions on low confidence rather than skipping/warning.
        """
        self.mapping_strategy = mapping_strategy
        self.min_confidence = min_global_confidence_threshold
        self.strict_mode = strict_mode
        logger.info(
            f"InsightToDecisionAdapter initialized. "
            f"Threshold: {self.min_confidence}, Strict: {self.strict_mode}"
        )

    def process_report(self, report: NexResearchReport) -> DecisionInputPayload:
        """
        Processes a full NexResearchReport and converts it into a DecisionInputPayload.

        Args:
            report: The complete research report generated by Nex.

        Returns:
            A DecisionInputPayload ready for the decision engine.

        Raises:
            InvalidInsightError: If the report fails validation.
            CriteriaMappingError: If the mapping strategy fails.
        """
        logger.info(f"Processing NexResearchReport: {report.report_id}")

        self._validate_report(report)

        all_claims: List[NexClaim] = []
        for insight in report.insights:
            all_claims.extend(insight.claims)

        logger.info(f"Extracted {len(all_claims)} total claims from {len(report.insights)} insights.")

        try:
            mapped_criteria = self.map_claims_to_criteria(all_claims)
        except Exception as e:
            logger.error(f"Failed to map claims to criteria: {str(e)}")
            raise CriteriaMappingError("Error occurred during claim mapping phase.") from e

        # Calculate aggregate reliability across all criteria
        aggregate_reliability = self._calculate_payload_reliability(mapped_criteria, report.global_confidence)

        payload = DecisionInputPayload(
            decision_session_id=f"dses_{uuid.uuid4().hex[:12]}",
            context_query=report.original_query,
            criteria=mapped_criteria,
            aggregate_reliability=aggregate_reliability
        )

        logger.info(f"Successfully generated DecisionInputPayload: {payload.decision_session_id}")
        return payload

    def convert_insight_to_decision_input(self, insight: NexInsight, context_query: str = "Implicit Query") -> DecisionInputPayload:
        """
        Converts a single NexInsight into a DecisionInputPayload. Useful for streaming
        or partial report processing.

        Args:
            insight: A single synthesized finding.
            context_query: The query context for this insight.

        Returns:
            DecisionInputPayload.
        """
        logger.info(f"Converting single insight: {insight.insight_id}")
        
        try:
            mapped_criteria = self.map_claims_to_criteria(insight.claims)
        except Exception as e:
            raise CriteriaMappingError(f"Failed to map claims for insight {insight.insight_id}") from e

        # Since it's a single insight, we derive reliability purely from the mapped criteria
        aggregate_reliability = self._calculate_payload_reliability(mapped_criteria, base_confidence=0.5)

        return DecisionInputPayload(
            decision_session_id=f"dses_{uuid.uuid4().hex[:12]}",
            context_query=context_query,
            criteria=mapped_criteria,
            aggregate_reliability=aggregate_reliability
        )

    def map_claims_to_criteria(self, claims: List[NexClaim]) -> List[DecisionCriterion]:
        """
        Delegates the mapping of claims to criteria to the injected mapping strategy.
        """
        if not claims:
            logger.warning("No claims provided for mapping.")
            return []
            
        return self.mapping_strategy.map_claims(claims)

    def export_payload(self, payload: DecisionInputPayload, as_dict: bool = False) -> Union[str, Dict[str, Any]]:
        """
        Exports the DecisionInputPayload to a decision-ready format (JSON string or Dict).

        Args:
            payload: The generated payload object.
            as_dict: If True, returns a Python dictionary instead of a JSON string.

        Returns:
            JSON string or Dictionary representation of the payload.
        """
        logger.info(f"Exporting payload {payload.decision_session_id}")
        if as_dict:
            return asdict(payload)
        return payload.to_json()

    def _validate_report(self, report: NexResearchReport) -> None:
        """Validates the incoming report against configured thresholds."""
        if not report.insights:
            raise InvalidInsightError(f"Report {report.report_id} contains no insights.")

        if report.global_confidence < self.min_confidence:
            msg = f"Report global confidence ({report.global_confidence}) is below threshold ({self.min_confidence})."
            if self.strict_mode:
                logger.error(msg)
                raise InvalidInsightError(msg)
            else:
                logger.warning(msg)

    def _calculate_payload_reliability(self, criteria: List[DecisionCriterion], base_confidence: float) -> float:
        """
        Calculates the aggregate reliability of the final payload, blending the report's
        global confidence with the specific satisfaction levels of the mapped criteria.
        """
        if not criteria:
            return 0.0

        criteria_avg = sum(c.satisfaction_level for c in criteria) / len(criteria)
        
        # Blend base confidence (from Nex report) with criteria specific confidence
        # Weighting: 40% base report confidence, 60% calculated criteria confidence
        blended_reliability = (base_confidence * 0.4) + (criteria_avg * 0.6)
        
        return round(blended_reliability, 4)


# ==============================================================================
# Factory & Utility Functions
# ==============================================================================
def create_default_adapter(criteria_schema: Optional[Dict[str, List[str]]] = None) -> InsightToDecisionAdapter:
    """
    Factory function to quickly instantiate an InsightToDecisionAdapter with a 
    standard KeywordCriteriaMapper.

    Args:
        criteria_schema: Optional dictionary defining the criteria to keyword mapping.
                         If None, a default schema is used.

    Returns:
        Configured InsightToDecisionAdapter instance.
    """
    default_schema = {
        "Technical Feasibility": ["infrastructure", "codebase", "architecture", "latency", "throughput", "api"],
        "Market Viability": ["market", "competitors", "audience", "demand", "trends", "growth"],
        "Financial Impact": ["cost", "revenue", "roi", "investment", "budget", "expenses"],
        "Risk Assessment": ["security", "compliance", "regulation", "vulnerability", "threat", "legal"],
        "Strategic Alignment": ["vision", "roadmap", "goals", "objectives", "core competency"]
    }

    schema_to_use = criteria_schema if criteria_schema is not None else default_schema
    mapper = KeywordCriteriaMapper(criteria_definitions=schema_to_use)
    
    return InsightToDecisionAdapter(
        mapping_strategy=mapper,
        min_global_confidence_threshold=0.6,
        strict_mode=False
    )