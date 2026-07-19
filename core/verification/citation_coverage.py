def calculate_coverage(claims):
    total=len(claims); direct=sum(1 for c in claims if c.get('state') in {'SUPPORTED_DIRECT','SUPPORTED_DERIVED'})
    return {"major_factual_claims":total,"claims_with_direct_support":direct,"claims_with_no_evidence":total-direct,"citation_coverage":direct/total if total else 1.0,"citation_precision":direct/total if total else 1.0,"source_lineage_diversity":len({c.get('lineage') for c in claims})}
