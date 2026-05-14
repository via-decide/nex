#!/usr/bin/env python3
"""Cross-domain engineering research harvester for NEX."""
from __future__ import annotations
import json, re, subprocess, urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
RAW, TXT, META, DIAG = [ROOT / d for d in ("corpus_raw", "corpus_text", "metadata", "diagram_index")]

@dataclass
class Artifact:
    source: str; title: str; kind: str; raw_path: str; text_path: str; diagrams: list[str]

DOMAIN_KEYWORDS = ["electrical engineering","power electronics","motor control","battery management","smart grid","emi","emc","thermal","pcb","adc","dac","rf","fpga","signal integrity","mixed-signal","control theory","fourier","optimization","graph theory","queueing","distributed systems"]


def ensure_dirs():
    for p in (RAW, TXT, META, DIAG): p.mkdir(parents=True, exist_ok=True)

def fetch_url(url: str) -> str:
    with urllib.request.urlopen(url, timeout=20) as r: return r.read().decode("utf-8", "ignore")

def clean_text(s: str) -> str: return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()

def extract_diagrams(text: str) -> list[str]: return sorted(set(re.findall(r"(?:figure|fig\.|diagram|schematic)\s*\d+", text, flags=re.I)))

def harvest_links(urls: Iterable[str]) -> list[Artifact]:
    out = []
    for i, url in enumerate(urls, start=1):
        try:
            html = fetch_url(url); text = clean_text(html)
            if not any(k in text.lower() for k in DOMAIN_KEYWORDS): continue
            stem = f"artifact_{i:04d}"; raw = RAW / f"{stem}.html"; txt = TXT / f"{stem}.txt"
            raw.write_text(html); txt.write_text(text)
            diagrams = extract_diagrams(text)
            (DIAG / f"{stem}.json").write_text(json.dumps({"source": url, "diagrams": diagrams}, indent=2))
            out.append(Artifact(url, url.split("/")[-1] or stem, "web", str(raw), str(txt), diagrams))
        except Exception as e:
            out.append(Artifact(url, f"error:{e}", "error", "", "", []))
    return out

def run_downstream():
    for script in ("clean_books.py", "extract_metadata.py", "generate_domain_tags.py"):
        p = ROOT / "scripts" / script
        if p.exists(): subprocess.run(["python", str(p)], cwd=ROOT, check=False)

def main():
    ensure_dirs()
    seed_sources = [
        "https://export.arxiv.org/api/query?search_query=all:power+electronics&start=0&max_results=5",
        "https://www.ieee.org/", "https://github.blog/engineering/", "https://www.rfc-editor.org/",
    ]
    artifacts = harvest_links(seed_sources)
    (META / "harvest_manifest.json").write_text(json.dumps([asdict(a) for a in artifacts], indent=2))
    run_downstream(); print(f"Harvested {len(artifacts)} artifacts")

if __name__ == "__main__": main()
