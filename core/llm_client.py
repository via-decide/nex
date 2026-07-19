"""Local Ollama/Zayvora LLM client.

This module is the sole LLM transport for Nex. It talks to a local Ollama
instance and never requires cloud API keys.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx


DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_ZAYVORA_MODEL = "zayvora"


def strip_json_fences(text: str) -> str:
    """Remove common markdown fences around model JSON output."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _llama_prompt(system: str, prompt: str) -> str:
    """Build a Llama 3 compatible prompt while remaining safe for Ollama."""
    if not system:
        return prompt
    return (
        "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
        f"{system}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n"
        f"{prompt}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
    )


class LocalLLMClient:
    """Small Ollama `/api/generate` client with sync, async, and streaming APIs."""

    def __init__(self, model: str | None = None, base_url: str | None = None, timeout: float = 120.0) -> None:
        self.model = model or os.environ.get("ZAYVORA_MODEL", DEFAULT_ZAYVORA_MODEL)
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)).rstrip("/")
        self.timeout = timeout

    def _payload(self, prompt: str, system: str = "", max_tokens: int = 1024, temperature: float = 0.1, json_mode: bool = False, stream: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": _llama_prompt(system, prompt),
            "stream": stream,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        }
        if json_mode:
            payload["format"] = "json"
        return payload

    async def generate(self, prompt: str, system: str = "", max_tokens: int = 1024, temperature: float = 0.1, json_mode: bool = False) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/api/generate", json=self._payload(prompt, system, max_tokens, temperature, json_mode))
            resp.raise_for_status()
            return resp.json().get("response", "")

    def generate_sync(self, prompt: str, system: str = "", max_tokens: int = 1024, temperature: float = 0.1, json_mode: bool = False) -> str:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/api/generate", json=self._payload(prompt, system, max_tokens, temperature, json_mode))
            resp.raise_for_status()
            return resp.json().get("response", "")

    async def generate_json(self, prompt: str, system: str = "", max_tokens: int = 1024, temperature: float = 0.1) -> dict[str, Any]:
        return json.loads(strip_json_fences(await self.generate(prompt, system, max_tokens, temperature, json_mode=True)))

    def generate_json_sync(self, prompt: str, system: str = "", max_tokens: int = 1024, temperature: float = 0.1) -> dict[str, Any]:
        return json.loads(strip_json_fences(self.generate_sync(prompt, system, max_tokens, temperature, json_mode=True)))

    async def stream(self, prompt: str, system: str = "", max_tokens: int = 1024, temperature: float = 0.2) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{self.base_url}/api/generate", json=self._payload(prompt, system, max_tokens, temperature, stream=True)) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("response"):
                        yield data["response"]
                    if data.get("done"):
                        break

    def stream_sync(self, prompt: str, system: str = "", max_tokens: int = 1024, temperature: float = 0.2) -> Iterator[str]:
        with httpx.Client(timeout=None) as client:
            with client.stream("POST", f"{self.base_url}/api/generate", json=self._payload(prompt, system, max_tokens, temperature, stream=True)) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("response"):
                        yield data["response"]
                    if data.get("done"):
                        break


def run_async(coro: Any) -> Any:
    """Run an async LLM call from synchronous code without cloud dependencies."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("Cannot run synchronous local LLM call inside an active event loop") from None
