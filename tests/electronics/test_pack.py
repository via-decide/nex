import json
from pathlib import Path
from domain_packs.electronics.exporters.pack import build_pack

def test_pack_review_and_no_hardware_authority():
    fixture=json.loads(Path('domain_packs/electronics/fixtures/example_board/pack_fixture.json').read_text())
    pack=build_pack(fixture)
    assert pack['reviewed_component_identities'][0]['exact_ordering_code']=='TPS7A0233PDBVR'
    assert 'hardware_authorization' not in pack and pack['datasheet_facts'][0]['review_status']=='CONFIRMED_OFFICIAL'
