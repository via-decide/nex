#!/usr/bin/env python3
from __future__ import annotations
import json, re, subprocess, urllib.request, xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
RAW, TXT, META, DIAG = [ROOT / d for d in ("corpus_raw", "corpus_text", "metadata", "diagram_index")]
DOMAINS = ["power electronics","motor control","battery","smart grid","emi","emc","thermal","pcb","adc","dac","rf","fpga","nvme","signal integrity","mixed-signal","control theory","numerical","fourier","optimization","graph theory","queueing","distributed"]
SEEDS = {
    "rss": ["https://rss.arxiv.org/rss/eess.SY", "https://github.blog/engineering/feed/"],
    "arxiv": ["https://export.arxiv.org/api/query?search_query=all:(control+systems+OR+power+electronics)&start=0&max_results=8"],
    "docs": ["https://www.rfc-editor.org/", "https://opensource.google/documentation/reference"],
    "whitepapers": ["https://www.nrel.gov/grid/"],
    "repos": ["https://api.github.com/search/repositories?q=embedded+control+systems&sort=stars&order=desc&per_page=6"],
}

@dataclass
class Artifact:
    source: str; title: str; kind: str; domain_hits: list[str]; raw_path: str; text_path: str; diagram_ref_path: str

def ensure_dirs():
    for p in (RAW, TXT, META, DIAG): p.mkdir(parents=True, exist_ok=True)

def fetch(url: str, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": "nex-harvester/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r: return r.read() if binary else r.read().decode("utf-8", "ignore")

def detect_kind(url: str, content_type=""):
    u = url.lower(); ct = content_type.lower()
    if u.endswith(".pdf") or "pdf" in ct: return "pdf"
    if u.endswith(".epub") or "epub" in ct: return "epub"
    if u.endswith(".md") or "markdown" in ct: return "markdown"
    if "arxiv" in u: return "arxiv"
    return "web"

def strip_markup(s: str): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()
def diagrams(s: str): return sorted(set(re.findall(r"(?:figure|fig\.|diagram|schematic|block\s+diagram)\s*\d*", s, flags=re.I)))

def rss_links(url: str) -> list[str]:
    xml = fetch(url)
    root = ET.fromstring(xml)
    return [e.text.strip() for e in root.findall(".//item/link") if e.text] + [e.attrib.get("href","") for e in root.findall(".//{http://www.w3.org/2005/Atom}link") if e.attrib.get("href")]

def github_repo_docs(url: str) -> list[str]:
    data = json.loads(fetch(url)); return [i.get("html_url","") for i in data.get("items", []) if i.get("html_url")]

def ingest(urls: Iterable[str]) -> list[Artifact]:
    out=[]
    for i,url in enumerate(dict.fromkeys(u for u in urls if u), start=1):
        try:
            html = fetch(url); text = strip_markup(html); hits = sorted([d for d in DOMAINS if d in text.lower()])
            if not hits: continue
            kind=detect_kind(url); stem=f"artifact_{i:05d}"; raw=RAW/f"{stem}.{ 'txt' if kind in ('markdown','arxiv','web') else kind }"; txt=TXT/f"{stem}.txt"; dref=DIAG/f"{stem}.json"
            raw.write_text(html); txt.write_text(text); dref.write_text(json.dumps({"source":url,"references":diagrams(text)}, indent=2))
            out.append(Artifact(url, url.rsplit("/",1)[-1] or stem, kind, hits, str(raw), str(txt), str(dref)))
        except Exception:
            continue
    return out

def run_pipeline():
    for s in ("clean_books.py", "extract_metadata.py", "generate_domain_tags.py"):
        p = ROOT/"scripts"/s
        if p.exists(): subprocess.run(["python", str(p)], cwd=ROOT, check=False)

def main():
    ensure_dirs(); sources=[]
    for r in SEEDS["rss"]: sources.extend(rss_links(r))
    for a in SEEDS["arxiv"]+SEEDS["docs"]+SEEDS["whitepapers"]: sources.append(a)
    sources.extend(github_repo_docs(SEEDS["repos"][0]))
    artifacts=ingest(sources)
    (META/"harvest_manifest.json").write_text(json.dumps([asdict(a) for a in artifacts], indent=2))
    run_pipeline(); print(f"Harvested {len(artifacts)} engineering artifacts")

if __name__ == "__main__": main()
