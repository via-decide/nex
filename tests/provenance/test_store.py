from core.artifacts.store import ArtifactStore

def test_content_addressed(tmp_path):
    s=ArtifactStore(tmp_path); a=s.put(b"abc","https://example.com","text/plain"); b=s.put(b"abc","https://example.org","text/plain")
    assert a.sha256==b.sha256 and s.verify(a.sha256)
