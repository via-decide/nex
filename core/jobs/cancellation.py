def request_cancel(run): run['status']='CANCEL_REQUESTED'
def is_cancelled(run): return run.get('status') in {'CANCEL_REQUESTED','CANCELLED'}
