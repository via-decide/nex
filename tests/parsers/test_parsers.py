from core.parsers import parse_artifact

def test_html_json_xml_text_parse():
    assert parse_artifact(b"<h1>A</h1><p>B</p>","text/html").headings==["A"]
    assert '"a"' in parse_artifact(b'{"a":1}',"application/json").normalized_text
    assert parse_artifact(b"<r>v</r>","application/xml").normalized_text=="v"
    assert parse_artifact(b"hello","text/plain").spans[0].end_offset==5
