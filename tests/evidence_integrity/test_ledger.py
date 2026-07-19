from core.evidence_ledger.ledger import EvidenceLedger

def test_claim_link_offsets_and_failures_visible():
    ledger=EvidenceLedger(); ledger.append("SOURCE_FETCH_FAILED",{"url":"x"}); c=ledger.create_claim("hello")
    link=ledger.link(c,"a"*64,"hello world",0,5)
    assert link.support_type=="DIRECT"
    assert ledger.coverage()["sources_failed"]==1
