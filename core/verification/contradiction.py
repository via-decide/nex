def detect_numeric_contradiction(a:dict,b:dict)->bool:
    return a.get('subject')==b.get('subject') and a.get('unit')==b.get('unit') and a.get('value')!=b.get('value')
def preserve_contradiction(a,b): return {"type":"numeric_disagreement","left":a,"right":b,"status":"UNRESOLVED"}
