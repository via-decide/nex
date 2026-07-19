from __future__ import annotations
import json, re
from dataclasses import dataclass, field
from typing import Any

PARSER_VERSION="parser-v1"
@dataclass
class SourceSpan:
    start_offset:int; end_offset:int; page:int|None=None; section:str|None=None; text:str=""
@dataclass
class ParsedDocument:
    parser_id:str; parser_version:str; content_type:str; normalized_text:str; structure:dict[str,Any]=field(default_factory=dict); spans:list[SourceSpan]=field(default_factory=list); tables:list[Any]=field(default_factory=list); headings:list[str]=field(default_factory=list); links:list[str]=field(default_factory=list); warnings:list[str]=field(default_factory=list); failures:list[str]=field(default_factory=list)

def parse_artifact(data:bytes, content_type:str)->ParsedDocument:
    ct=content_type.split(';')[0]
    if ct in {"text/html","application/xhtml+xml"}:
        raw=data.decode(errors="replace")
        heads=[re.sub(r"<[^>]+>","",m.group(0)).strip() for m in re.finditer(r"<h[1-6][^>]*>.*?</h[1-6]>", raw, re.I|re.S)]
        links=re.findall(r"href=[\"']([^\"']+)[\"']", raw, re.I)
        text=re.sub(r"<[^>]+>","\n", raw); text=re.sub(r"\n+","\n", text).strip()
        return ParsedDocument("html",PARSER_VERSION,ct,text,{"type":"html"},[SourceSpan(0,len(text),section=heads[0] if heads else None,text=text)],headings=heads,links=links)
    if ct in {"application/json"}:
        obj=json.loads(data.decode()); text=json.dumps(obj,sort_keys=True,indent=2); return ParsedDocument("json",PARSER_VERSION,ct,text,{"type":"json"},[SourceSpan(0,len(text),section="json",text=text)])
    if ct in {"application/xml","application/atom+xml"}:
        text=re.sub(r"<[^>]+>"," ",data.decode(errors="replace")); text=re.sub(r"\s+"," ",text).strip(); return ParsedDocument("xml",PARSER_VERSION,ct,text,{"type":"xml"},[SourceSpan(0,len(text),section="xml",text=text)])
    if ct in {"text/plain","text/markdown","application/x-git-snapshot"}:
        text=data.decode(errors="replace"); return ParsedDocument("text",PARSER_VERSION,ct,text,{"type":"text"},[SourceSpan(0,len(text),section="document",text=text)])
    if ct=="application/pdf":
        if not data.startswith(b"%PDF"): raise ValueError("binary PDF signature missing")
        try:
            from pypdf import PdfReader
            import io
            reader=PdfReader(io.BytesIO(data)); parts=[]; spans=[]; off=0; ocr=False
            for i,page in enumerate(reader.pages,1):
                t=page.extract_text() or ""; ocr = ocr or not t.strip(); parts.append(t); spans.append(SourceSpan(off,off+len(t),page=i,section=f"page {i}",text=t)); off += len(t)+1
            doc=ParsedDocument("pdf",PARSER_VERSION,ct,"\n".join(parts),{"type":"pdf","pages":len(reader.pages)},spans)
            if ocr: doc.failures.append("OCR_REQUIRED")
            return doc
        except Exception as e:
            return ParsedDocument("pdf",PARSER_VERSION,ct,"",{"type":"pdf"},failures=["OCR_REQUIRED",str(e)])
    raise ValueError(f"Unsupported content type {ct}")
