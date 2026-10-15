"""Helpers for the local stage (fact extraction on a 3-4B model via Ollama; SPEC §4/§7.8). The actual call goes through
common/llm.py (an `ollama:<model>` slug uses Ollama's OpenAI-compatible endpoint); this module only checks availability."""
from __future__ import annotations

import os

import httpx


def host() -> str:
    return os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")


def available_models(timeout: float = 3.0) -> list[str] | None:
    """Names of pulled models, or None if Ollama is not reachable."""
    try:
        r = httpx.get(f"{host()}/api/tags", timeout=timeout)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return None


def status(model: str) -> str:
    """Human-readable setup status used by `python -m local.ollama_client <model>`."""
    models = available_models()
    if models is None:
        return f"Ollama is not running at {host()} (install from https://ollama.com, then `ollama serve`)."
    if not any(m == model or m.split(":")[0] == model.split(":")[0] and ":" not in model for m in models):
        return f"Ollama is running but `{model}` is not pulled. Run: ollama pull {model}"
    return f"OK: {model} is available at {host()}"


if __name__ == "__main__":
    import sys

    print(status(sys.argv[1] if len(sys.argv) > 1 else os.getenv("OLLAMA_MODEL", "qwen3:4b")))
