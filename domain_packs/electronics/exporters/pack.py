from __future__ import annotations
import hashlib, json
FORBIDDEN={'hardware_authorization','firmware_flashing_permission','erase_permission','board_verification_status','automatic_component_confirmation','model_generated_destructive_instructions','jtag','relay','power_control'}
def build_pack(fixture:dict)->dict:
    facts=fixture.get('facts',[])
    for f in facts:
        if f.get('review_status') not in {'CONFIRMED_OFFICIAL','CONFIRMED_MEASURED','REJECTED','NEEDS_MORE_EVIDENCE'}: raise ValueError('invalid review')
        if f.get('review_status') not in {'CONFIRMED_OFFICIAL','CONFIRMED_MEASURED'} and f.get('authoritative'): raise ValueError('unsupported fact cannot be authoritative')
        if not f.get('exact_part_scope'): raise ValueError('exact part scope required')
    pack={"schema_version":"electronics_research_pack.v1","pack_id":f"{fixture['project']}:{fixture['board_revision']}","project":fixture['project'],"board_revision":fixture['board_revision'],"component_candidates":fixture.get('components',[]),"reviewed_component_identities":[c for c in fixture.get('components',[]) if c.get('review_status','').startswith('CONFIRMED')],"source_manifest":fixture.get('source_manifest',[]),"datasheet_facts":facts,"claim_to_passage_links":fixture.get('claim_evidence_links',[]),"conflicts":fixture.get('conflicts',[]),"missing_facts":fixture.get('missing_facts',[]),"review_decisions":fixture.get('review_decisions',[]),"model_and_parser_versions":{"extractor":"electronics-fixture-v1","parser":"parser-v1"},"run_event_range":{"first":1,"last":1},"forbidden_capabilities_absent":sorted(FORBIDDEN)}
    if FORBIDDEN & set(pack): raise ValueError('forbidden capability exported')
    body=json.dumps(pack,sort_keys=True,separators=(',',':')).encode(); pack['pack_sha256']=hashlib.sha256(body).hexdigest(); return pack
