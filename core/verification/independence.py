def lineage_key(source:dict)->tuple:
    return (source.get('publisher'), source.get('dataset'), source.get('repository'), source.get('press_release'))
def independent_lineage_count(sources:list[dict])->int:
    return len({lineage_key(s) for s in sources})
