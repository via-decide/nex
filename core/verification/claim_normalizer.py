from dataclasses import dataclass, field
@dataclass(frozen=True)
class NormalizedClaim:
    original_sentence:str; subject:str; predicate:str; object:str; qualifiers:dict=field(default_factory=dict); population:str|None=None; location:str|None=None; time_range:str|None=None; measurement_conditions:str|None=None; units:str|None=None; uncertainty:float|None=None; modality:str="factual"
def normalize_claim(sentence:str)->NormalizedClaim:
    parts=sentence.split(); return NormalizedClaim(sentence, parts[0] if parts else "", " ".join(parts[1:-1]), parts[-1] if len(parts)>1 else "")
