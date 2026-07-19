from dataclasses import dataclass
@dataclass
class EntailmentResult:
    decision:str; confidence:float; scope_comparison:str="compatible"; unresolved_questions:list[str]=None
def decide_entailment(claim, evidence_text:str)->EntailmentResult:
    c=claim.original_sentence.lower(); e=evidence_text.lower()
    if c in e: return EntailmentResult("ENTAILED_DIRECT",0.95)
    if any(w in e for w in c.split()[:2]): return EntailmentResult("PARTIAL_SUPPORT",0.5)
    return EntailmentResult("UNRELATED",0.1)
