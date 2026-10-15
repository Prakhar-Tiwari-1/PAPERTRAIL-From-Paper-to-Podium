"""The only door to a model (CLAUDE.md rule 2).

`Harness.call(role, prompt, output_type=...)` resolves the role in config/models.yaml, loads the role's
skills into the system prompt, checks the budget, consults the disk cache, calls the model through
PydanticAI (OpenRouter, or Ollama for `ollama:` slugs), retries/falls back, then traces and costs the call.
PydanticAI is only the typed-call layer; it never decides what happens next.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence, TypeVar

import yaml
from pydantic import BaseModel, TypeAdapter, ValidationError

from common.budget import Budget, BudgetExceeded, estimate_cost
from common.skills import skills_prompt
from common.trace import Trace

ROOT = Path(__file__).resolve().parent.parent
T = TypeVar("T")

IMAGE_TOKENS = 1500  # rough per-image input cost used only for the worst-case pre-call estimate


class MissingAPIKey(RuntimeError):
    pass


@dataclass
class RoleConfig:
    name: str
    model: str
    dev_model: str
    fallback: str
    temperature: float = 0.2
    max_tokens: int = 4000
    skills: list[str] = field(default_factory=list)
    vision: bool = False
    prompted: bool = False  # use prompted JSON output instead of tool-call output (weaker models)


def load_models(path: Path | None = None) -> tuple[dict[str, RoleConfig], dict[str, tuple[float, float]]]:
    raw = yaml.safe_load((path or ROOT / "config" / "models.yaml").read_text(encoding="utf-8"))
    roles = {}
    for name, r in raw["roles"].items():
        roles[name] = RoleConfig(
            name=name,
            model=r["model"],
            dev_model=r.get("dev_model", r["model"]),
            fallback=r["fallback"],
            temperature=r.get("temperature", 0.2),
            max_tokens=r.get("max_tokens", 4000),
            skills=r.get("skills", []),
            vision=r.get("vision", False),
            prompted=r.get("prompted", False),
        )
    prices = {k: tuple(v) for k, v in raw.get("prices", {}).items()}
    return roles, prices


def vendor(slug: str) -> str:
    return slug.split(":")[0] if slug.startswith("ollama:") else slug.split("/")[0]


def check_vendor_rules(roles: dict[str, RoleConfig], rules: list[list[str]], dev: bool = False) -> list[str]:
    """Author != judge, author != student critic (SPEC §5.1). `author` is also the Anthropic role family."""
    problems = []
    for a, b in rules:
        if a in roles and b in roles:
            ma = roles[a].dev_model if dev else roles[a].model
            mb = roles[b].dev_model if dev else roles[b].model
            if vendor(ma) == vendor(mb):
                problems.append(f"{a} ({ma}) and {b} ({mb}) share a vendor")
    return problems


def _is_text_only(slug: str) -> bool:
    return slug.startswith("deepseek/") and "vision" not in slug


class Harness:
    def __init__(
        self,
        run_dir: Path,
        *,
        dev: bool = False,
        models_path: Path | None = None,
        budget: Budget | None = None,
        cache_dir: Path | None = None,
        model_factory: Callable[[str], Any] | None = None,
    ):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.dev = dev
        self.roles, self.prices = load_models(models_path)
        self.budget = budget or Budget(self.run_dir)
        self.trace = Trace(self.run_dir)
        self.cache_dir = Path(cache_dir or os.getenv("P2D_CACHE_DIR") or ROOT / ".cache" / "llm")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.model_factory = model_factory  # tests inject FunctionModel/TestModel here
        self.stage = ""
        self.retry_wait = 0.0 if model_factory is not None else 15.0  # seconds x attempt number, after a connection error

    # ------------------------------------------------------------------ helpers
    def slug_for(self, role: str, *, fallback: bool = False) -> str:
        cfg = self.roles[role]
        return cfg.fallback if fallback else (cfg.dev_model if self.dev else cfg.model)

    def _price(self, slug: str) -> tuple[float, float]:
        return self.prices.get(slug, (3.0, 15.0))  # unknown model: assume pricey so the guard stays safe

    def _build_model(self, slug: str):
        if self.model_factory:
            return self.model_factory(slug)
        if slug.startswith("ollama:"):
            from pydantic_ai.models.openai import OpenAIChatModel
            from pydantic_ai.providers.openai import OpenAIProvider

            host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
            return OpenAIChatModel(
                slug.split(":", 1)[1], provider=OpenAIProvider(base_url=f"{host}/v1", api_key="ollama")
            )
        key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not key:
            raise MissingAPIKey("OPENROUTER_API_KEY is empty; put it in .env (see .env.example)")
        from pydantic_ai.models.openrouter import OpenRouterModel
        from pydantic_ai.providers.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            api_key=key,
            app_url=os.getenv("OPENROUTER_APP_URL"),
            app_title=os.getenv("OPENROUTER_APP_NAME", "papertrail"),
        )
        return OpenRouterModel(slug, provider=provider)

    def cache_key(self, slug: str, system: str, prompt: str, images: Sequence[bytes], params: dict,
                  repeat_idx: int, schema_name: str) -> str:
        payload = json.dumps(
            {
                "model": slug,
                "system": hashlib.sha256(system.encode()).hexdigest(),
                "prompt": hashlib.sha256(prompt.encode()).hexdigest(),
                "images": [hashlib.sha256(i).hexdigest() for i in images],
                "params": params,
                "repeat_idx": repeat_idx,  # MUST be in the key so repeated judge runs are real
                "schema": schema_name,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def _estimate_in_tokens(self, system: str, prompt: str, n_images: int) -> int:
        return int((len(system) + len(prompt)) / 3.2) + n_images * IMAGE_TOKENS

    @staticmethod
    def _actual_cost(result, slug: str, price: tuple[float, float]) -> tuple[float, int, int, bool]:
        """Prefer OpenRouter's returned cost; fall back to a YAML price estimate."""
        usage = result.usage() if callable(result.usage) else result.usage  # property in pydantic-ai 2.x
        in_t, out_t = usage.input_tokens or 0, usage.output_tokens or 0
        total, found = 0.0, False
        for m in result.all_messages():
            details = getattr(m, "provider_details", None)
            if isinstance(details, dict) and details.get("cost") is not None:
                total += float(details["cost"])
                found = True
        if found:
            return total, in_t, out_t, True
        return (in_t * price[0] + out_t * price[1]) / 1_000_000, in_t, out_t, False

    def _ollama_up(self) -> bool:
        """Checked once per run. Tests inject a model factory and never touch the network."""
        if self.model_factory is not None:
            return True
        if not hasattr(self, "_ollama_ok"):
            from local.ollama_client import available_models

            self._ollama_ok = available_models() is not None
            if not self._ollama_ok:
                self.trace.log(stage=self.stage, event="ollama_unavailable",
                               note="local model not reachable; hosted fallback used for roles that prefer a local model")
        return self._ollama_ok

    # ------------------------------------------------------------------ the call
    def call(
        self,
        role: str,
        prompt: str,
        *,
        output_type: type[T] | Any = str,
        repeat_idx: int = 0,
        images: Sequence[bytes] | None = None,
        tools: Sequence[Callable] = (),
        system_extra: str = "",
        use_cache: bool = True,
        max_tool_calls: int = 4,
    ) -> T:
        cfg = self.roles[role]
        images = list(images or [])
        system = "\n\n".join(p for p in (system_extra, skills_prompt(cfg.skills)) if p)
        slug = self.slug_for(role)

        for candidate in (slug, cfg.fallback):
            if images and _is_text_only(candidate):
                raise ValueError(f"role {role!r}: {candidate} is text-only; cannot send images (CLAUDE.md rule 6)")

        params = {"t": cfg.temperature, "max": cfg.max_tokens, "tools": [t.__name__ for t in tools]}
        schema_name = getattr(output_type, "__name__", str(output_type))
        adapter = TypeAdapter(output_type)

        def cached_for(s: str):
            key = self.cache_key(s, system, prompt, images, params, repeat_idx, schema_name)
            return key, self.cache_dir / f"{key}.json"

        # cache lookup (primary model only; a fallback result is cached under the fallback slug)
        if use_cache:
            for s in (slug, cfg.fallback):
                _, path = cached_for(s)
                if path.exists():
                    out = adapter.validate_json(path.read_text(encoding="utf-8"))
                    self.trace.log(stage=self.stage, role=role, model=s, cached=True, repeat_idx=repeat_idx,
                                   cost=0.0, in_tokens=0, out_tokens=0)
                    return out

        last_err: Exception | None = None
        attempts = [(slug, 3), (cfg.fallback, 2)]  # 3 tries on the primary, 2 on the fallback; waits only after network errors
        if slug.startswith("ollama:") and not self._ollama_up():
            attempts = [(cfg.fallback, 1)]  # local model not running: go straight to the hosted fallback instead of failing every call
        for idx, (candidate, tries) in enumerate(attempts):
            price = self._price(candidate)
            in_est = self._estimate_in_tokens(system, prompt, len(images))
            # every tool round-trip re-sends the whole prompt, so the worst case scales with the tool-call cap
            rounds = 1 + (max_tool_calls if tools else 0)
            est = estimate_cost(in_est * rounds, cfg.max_tokens * rounds, price)
            self.budget.check(est)  # raises BudgetExceeded: never retried or fallen back
            for attempt in range(tries):
                t0 = time.time()
                try:
                    result = self._run_agent(candidate, cfg, system, prompt, images, tools, output_type, max_tool_calls)
                except BudgetExceeded:
                    raise
                except MissingAPIKey:
                    raise
                except Exception as e:  # 429/5xx/invalid output
                    last_err = e
                    self.trace.log(stage=self.stage, role=role, model=candidate, error=repr(e)[:400],
                                   attempt=attempt, fallback_used=idx == 1, seconds=round(time.time() - t0, 2))
                    if "onnection" in repr(e) or "imeout" in repr(e):  # short network drop: wait before the next try instead of failing instantly
                        time.sleep(self.retry_wait * (attempt + 1))
                    continue
                cost, in_t, out_t, from_or = self._actual_cost(result, candidate, price)
                self.budget.add(cost, model=candidate, role=role)
                out = result.output
                if use_cache:
                    _, path = cached_for(candidate)
                    path.write_text(adapter.dump_json(out).decode("utf-8"), encoding="utf-8")
                self.trace.log(stage=self.stage, role=role, model=candidate, cached=False, repeat_idx=repeat_idx,
                               cost=round(cost, 6), cost_source="openrouter" if from_or else "estimate",
                               in_tokens=in_t, out_tokens=out_t, fallback_used=idx == 1,
                               seconds=round(time.time() - t0, 2))
                return out
        raise RuntimeError(f"role {role!r}: all attempts failed; last error: {last_err!r}")

    def _run_agent(self, slug, cfg: RoleConfig, system, prompt, images, tools, output_type, max_tool_calls=4):
        from pydantic_ai import Agent, BinaryContent, PromptedOutput
        from pydantic_ai.settings import ModelSettings

        model = self._build_model(slug)
        settings: dict[str, Any] = {"temperature": cfg.temperature, "max_tokens": cfg.max_tokens}
        if not slug.startswith("ollama:") and self.model_factory is None:
            settings["openrouter_usage"] = {"include": True}  # makes OpenRouter return the real cost
        out = PromptedOutput(output_type) if (cfg.prompted and output_type is not str) else output_type
        agent = Agent(
            model,
            output_type=out,
            system_prompt=system or (),
            tools=list(tools),
            model_settings=ModelSettings(**settings),
            retries=1,
        )
        user: Any = prompt
        if images:
            user = [prompt] + [BinaryContent(data=i, media_type="image/png") for i in images]
        from pydantic_ai.usage import UsageLimits

        limits = UsageLimits(tool_calls_limit=max_tool_calls, request_limit=max_tool_calls + 4) if tools else UsageLimits(request_limit=6)
        return agent.run_sync(user, usage_limits=limits)
