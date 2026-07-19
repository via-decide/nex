import pytest
from core.verification.claim_normalizer import normalize_claim
from core.verification.entailment import decide_entailment
from core.verification.independence import independent_lineage_count
from core.verification.release_gate import release_decision
from core.verification.reviewer import LLMGroundingReviewer

def test_claim_entailment_and_gate():
    c=normalize_claim('TPS voltage is 3.3V')
    assert decide_entailment(c,'TPS voltage is 3.3V in recommended conditions').decision=='ENTAILED_DIRECT'
    assert independent_lineage_count([{'publisher':'A','dataset':'D'},{'publisher':'A','dataset':'D'}])==1
    assert release_decision([{'major':True,'state':'INSUFFICIENT_EVIDENCE'}], {'citation_coverage':0.1})['status']=='RESEARCH_INCOMPLETE'
    with pytest.raises(Exception): LLMGroundingReviewer().validate_output({'claim_id':'c'})
