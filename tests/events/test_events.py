import pytest
from core.events.event_store import EventStore
from core.events.projections import project_run

def test_append_only_hash_projection():
    es=EventStore(); es.append('r','RUN_CREATED'); es.append('r','RUN_COMPLETED')
    assert project_run(es.list('r'))['status']=='COMPLETED'
    with pytest.raises(RuntimeError): es.delete('x')
