from pydantic import BaseModel, Field
class LLMGroundingReview(BaseModel):
    claim_id:str; verdict:str; supporting_evidence_ids:list[str]=Field(default_factory=list); contradicting_evidence_ids:list[str]=Field(default_factory=list); missing_context:list[str]=Field(default_factory=list); reason_code:str; confidence:float
class LLMGroundingReviewer:
    reviewer_version="llm-grounding-reviewer-v1"
    def validate_output(self, data:dict)->LLMGroundingReview: return LLMGroundingReview.model_validate(data)
