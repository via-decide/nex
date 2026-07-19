def release_decision(claims, coverage, contradictions=None, parser_uncertain=False, reviewer_malformed=False, target='VERIFIED'):
    contradictions=contradictions or []
    if reviewer_malformed or parser_uncertain: return {"status":"DRAFT","reasons":["grounding_or_parser_uncertain"]}
    if coverage.get('citation_coverage',0)<0.8: return {"status":"RESEARCH_INCOMPLETE","reasons":["citation_coverage_below_policy"]}
    if contradictions: return {"status":"CONFLICTING_EVIDENCE","reasons":["critical_contradictions_unresolved"]}
    if any(c.get('major') and c.get('state') not in {'SUPPORTED_DIRECT','SUPPORTED_DERIVED'} for c in claims): return {"status":"RESEARCH_INCOMPLETE","reasons":["major_claim_without_support"]}
    return {"status":"VERIFIED","reasons":[]}
