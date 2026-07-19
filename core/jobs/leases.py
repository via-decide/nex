from datetime import datetime, timedelta, timezone
def renew(job, seconds=30): job.heartbeat_at=datetime.now(timezone.utc); job.lease_expires_at=job.heartbeat_at+timedelta(seconds=seconds)
def expired(job): return job.lease_expires_at is not None and job.lease_expires_at<datetime.now(timezone.utc)
