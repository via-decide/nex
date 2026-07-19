from datetime import datetime, timedelta, timezone
from core.jobs.queue import JobQueue
from core.jobs.recovery import recover_expired_leases

def test_recover_expired():
    q=JobQueue(); q.enqueue('r','s',{}); j=q.acquire('w'); j.lease_expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
    assert recover_expired_leases(q)==[j.job_id]
