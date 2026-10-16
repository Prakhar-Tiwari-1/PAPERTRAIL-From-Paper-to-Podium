"""Call a role, validate the result with plain Python rules, and re-ask with the violations listed (bounded)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, TypeVar

from papertrail.common.ctx import RunCtx

T = TypeVar("T")
from papertrail.paths import PROMPTS


def load_prompt(name: str) -> str:
    return (PROMPTS / name).read_text(encoding="utf-8")


def fill(template: str, **values: str) -> str:
    """Replace {key} tokens only. Prompt files contain literal JSON braces, so str.format cannot be used."""
    for k, v in values.items():
        template = template.replace("{" + k + "}", str(v))
    return template


def call_validated(
    ctx: RunCtx,
    role: str,
    prompt: str,
    output_type: type[T],
    validate: Callable[[T], list[str]],
    *,
    max_repairs: int = 2,
    **kw: Any,
) -> T:
    """Returns the first output with no violations. After `max_repairs` re-asks, raises with the violations."""
    out = ctx.h.call(role, prompt, output_type=output_type, **kw)
    for attempt in range(max_repairs + 1):
        problems = validate(out)
        if not problems:
            return out
        ctx.h.trace.log(stage=ctx.h.stage, role=role, event="validation_failed", attempt=attempt, problems=problems[:12])
        if attempt == max_repairs:
            raise ValueError(f"{role}: output still violates rules after {max_repairs} repairs: {problems}")
        fix = (
            prompt
            + "\n\n# Your previous answer broke these rules. Return a corrected, complete answer.\n"
            + "\n".join(f"- {p}" for p in problems)
            + "\n\n# Previous answer (JSON)\n"
            + out.model_dump_json()  # type: ignore[attr-defined]
        )
        out = ctx.h.call(role, fix, output_type=output_type, **kw)
    return out
