from datetime import datetime, timedelta, timezone
def schedule_retry(job, error, base=1):
    job.attempt += 1; job.last_error=str(error)
    if job.attempt>=job.maximum_attempts: job.status='FAILED'; return False
    job.status='WAITING_RETRY'; job.available_at=datetime.now(timezone.utc)+timedelta(seconds=base*(2**job.attempt)); return True
