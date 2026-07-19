from core.jobs.leases import expired
def recover_expired_leases(queue):
    recovered=[]
    for j in queue.jobs:
        if j.status=='LEASED' and expired(j): j.status='QUEUED'; j.lease_owner=None; recovered.append(j.job_id)
    return recovered
