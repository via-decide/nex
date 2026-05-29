"""Zero-config embedded persistence for Nex.

SQLite stores run state, reports, evidence rows, local embedding vectors, and
knowledge-graph projections without requiring any external database server.
"""

from __future__ import annotations

import json
import os
import sqlite3
import urllib.request
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any


DB_PATH = Path(os.environ.get("NEX_STATE_DB", "nex_state.db"))
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
EMBED_MODEL = os.environ.get("ZAYVORA_EMBED_MODEL", "nomic-embed-text")


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _json(data: Any) -> str:
    return json.dumps(data, default=lambda o: asdict(o) if hasattr(o, "__dataclass_fields__") else str(o))


def _embed(text: str) -> list[float]:
    """Generate a local Ollama embedding; never calls hosted vector services."""
    payload = json.dumps({"model": EMBED_MODEL, "prompt": text[:6000]}).encode()
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode()).get("embedding", [])
    except Exception:
        return []


class NexDatabase:
    """Small SQLite repository for local-first Nex run state and graph data."""

    def __init__(self, path: Path = DB_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True) if self.path.parent != Path(".") else None
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                  run_id TEXT PRIMARY KEY, question TEXT, status TEXT, depth TEXT,
                  created_at TEXT, completed_at TEXT, error TEXT,
                  events_json TEXT DEFAULT '[]', stats_json TEXT DEFAULT '{}', report_json TEXT
                );
                CREATE TABLE IF NOT EXISTS sources (
                  run_id TEXT, url TEXT, title TEXT, source_type TEXT, PRIMARY KEY(run_id, url)
                );
                CREATE TABLE IF NOT EXISTS evidence (
                  run_id TEXT, evidence_item_id TEXT, source_url TEXT, source_title TEXT,
                  source_type TEXT, summary TEXT, key_claims_json TEXT, citations_json TEXT,
                  raw_text_length INTEGER, extraction_confidence REAL, published_at TEXT,
                  metadata_json TEXT, embedding_json TEXT, PRIMARY KEY(run_id, evidence_item_id)
                );
                CREATE TABLE IF NOT EXISTS graph_nodes (
                  run_id TEXT, node_id TEXT, label TEXT, node_type TEXT, confidence TEXT,
                  description TEXT, claims_json TEXT, sources_json TEXT, PRIMARY KEY(run_id, node_id)
                );
                CREATE TABLE IF NOT EXISTS graph_edges (
                  run_id TEXT, source_id TEXT, target_id TEXT, relation TEXT, weight REAL
                );
                CREATE TABLE IF NOT EXISTS claims (
                  run_id TEXT, claim TEXT, confidence TEXT, supporting_sources_json TEXT
                );
                CREATE TABLE IF NOT EXISTS subchat_threads (
                  thread_id TEXT PRIMARY KEY, run_id TEXT, finding_id TEXT, payload_json TEXT
                );
                """
            )

    def create_run(self, run_id: str, question: str, depth: str) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO runs(run_id, question, status, depth, created_at) VALUES (?, ?, 'queued', ?, ?)",
                (run_id, question, depth, _now()),
            )

    def update_run(self, run_id: str, **fields: Any) -> None:
        if not fields:
            return
        keys = ", ".join(f"{k} = ?" for k in fields)
        with self._connect() as db:
            db.execute(f"UPDATE runs SET {keys} WHERE run_id = ?", (*fields.values(), run_id))

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if not row:
            return None
        data = dict(row)
        data["events"] = json.loads(data.pop("events_json") or "[]")
        data["stats"] = json.loads(data.pop("stats_json") or "{}")
        report_raw = data.pop("report_json", None)
        if report_raw:
            data["report"] = json.loads(report_raw)
        return data

    def save_result(self, run_id: str, result: Any) -> None:
        report_json = result.report.to_json()
        events = [{"stage": e.stage, "status": e.status, "message": e.message, "data": e.data} for e in result.events]
        stats = {
            "sources_discovered": len(result.sources), "evidence_items": len(result.evidence),
            "verified_claims": len(result.verification.verified), "likely_claims": len(result.verification.likely),
            "findings": len(result.report.key_findings), "graph_nodes": len(result.knowledge_graph.nodes),
        }
        with self._connect() as db:
            db.execute("DELETE FROM sources WHERE run_id = ?", (run_id,))
            db.execute("DELETE FROM evidence WHERE run_id = ?", (run_id,))
            db.execute("DELETE FROM graph_nodes WHERE run_id = ?", (run_id,))
            db.execute("DELETE FROM graph_edges WHERE run_id = ?", (run_id,))
            db.execute("DELETE FROM claims WHERE run_id = ?", (run_id,))
            for s in result.sources:
                db.execute("INSERT OR REPLACE INTO sources VALUES (?, ?, ?, ?)", (run_id, s.url, s.title, s.source_type))
            for e in result.evidence:
                embedding = _embed(f"{e.summary}\n" + "\n".join(e.key_claims))
                db.execute("INSERT OR REPLACE INTO evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (run_id, e.evidence_item_id, e.source_url, e.source_title, e.source_type, e.summary,
                     _json(e.key_claims), _json(e.citations), e.raw_text_length, e.extraction_confidence,
                     e.published_at, _json(e.metadata), _json(embedding)))
            for n in result.knowledge_graph.nodes:
                db.execute("INSERT OR REPLACE INTO graph_nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (run_id, n.id, n.label, n.node_type, n.confidence, n.description, _json(n.claims), _json(n.sources)))
            for edge in result.knowledge_graph.edges:
                db.execute("INSERT INTO graph_edges VALUES (?, ?, ?, ?, ?)", (run_id, edge.source_id, edge.target_id, edge.relation, edge.weight))
            for claim in result.verification.all_claims:
                db.execute("INSERT INTO claims VALUES (?, ?, ?, ?)", (run_id, claim.claim, claim.confidence.value, _json(claim.supporting_sources)))
            db.execute("UPDATE runs SET status = 'completed', completed_at = ?, events_json = ?, stats_json = ?, report_json = ? WHERE run_id = ?",
                (_now(), _json(events), _json(stats), report_json, run_id))

    def get_report(self, run_id: str) -> dict[str, Any] | None:
        run = self.get_run(run_id)
        return run.get("report") if run else None

    def save_thread(self, thread: dict[str, Any], run_id: str, finding_id: str) -> None:
        payload = dict(thread)
        payload["run_id"] = run_id
        payload["finding_id"] = finding_id
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO subchat_threads VALUES (?, ?, ?, ?)", (thread["thread_id"], run_id, finding_id, _json(payload)))

    def get_thread(self, thread_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT payload_json FROM subchat_threads WHERE thread_id = ?", (thread_id,)).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def vector_search(self, run_id: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search embedded evidence vectors stored locally in SQLite."""
        query_vec = _embed(query)
        if not query_vec:
            return []
        def _cosine(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            na = sum(x * x for x in a) ** 0.5
            nb = sum(y * y for y in b) ** 0.5
            return dot / (na * nb) if na and nb else 0.0
        with self._connect() as db:
            rows = db.execute("SELECT evidence_item_id, source_url, summary, embedding_json FROM evidence WHERE run_id = ?", (run_id,)).fetchall()
        scored = []
        for row in rows:
            vec = json.loads(row["embedding_json"] or "[]")
            scored.append({"evidence_item_id": row["evidence_item_id"], "source_url": row["source_url"], "summary": row["summary"], "score": _cosine(query_vec, vec)})
        return sorted(scored, key=lambda item: item["score"], reverse=True)[:limit]

    def graph_walk(self, run_id: str, start_node: str, depth: int = 3) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """
                WITH RECURSIVE walk(source_id, target_id, relation, depth) AS (
                  SELECT source_id, target_id, relation, 1 FROM graph_edges WHERE run_id = ? AND source_id = ?
                  UNION ALL
                  SELECT e.source_id, e.target_id, e.relation, walk.depth + 1
                  FROM graph_edges e JOIN walk ON e.source_id = walk.target_id
                  WHERE e.run_id = ? AND walk.depth < ?
                ) SELECT * FROM walk
                """,
                (run_id, start_node, run_id, depth),
            ).fetchall()
        return [dict(r) for r in rows]
