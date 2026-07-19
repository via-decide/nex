from fastapi import APIRouter, HTTPException
router=APIRouter(prefix='/api/electronics')
@router.get('/capabilities')
def capabilities():
    return {'nex':['source_discovery','source_preservation','claim_extraction','conflict_detection','provenance','review_workflow','research_pack_export'],'absent':['hardware_authorization','firmware_flashing','jtag','relay','power_control','storage_erasure']}
