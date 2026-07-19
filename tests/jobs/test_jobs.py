from core.jobs.queue import JobQueue
from core.jobs.worker import Worker
from core.events.event_store import EventStore

def test_job_once_and_events():
    q=JobQueue(); es=EventStore(); q.enqueue('r','discover',{})
    j=Worker(q,es).run_once(); assert j.status=='COMPLETED'; assert len(es.list('r'))==2
