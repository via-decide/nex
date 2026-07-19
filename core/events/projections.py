def project_run(events):
    status='QUEUED'; stages=[]
    for e in events:
        t=e['event_type']
        if t=='STAGE_STARTED': status='RUNNING'; stages.append(e['payload'].get('stage'))
        elif t=='RUN_COMPLETED': status='COMPLETED'
        elif t=='RUN_FAILED': status='FAILED'
        elif t=='RUN_CANCELLED': status='CANCELLED'
    return {'status':status,'stages':stages,'event_count':len(events)}
