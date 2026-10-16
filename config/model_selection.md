# Model selection log (SPEC §5.2, §17)

## Verified on 2026-10-12 against https://openrouter.ai/api/v1/models (public list, no key needed)

| Role family | Slug in `models.yaml` | $/1M in/out | Context | Notes |
|---|---|---|---|---|
| Author, difficulty map, planner | `anthropic/claude-sonnet-5.5` | 2 / 10 | 1M | text + image |
| Fallback for most roles | `anthropic/claude-haiku-5.5` | 0.1 / 0.5 | 1M | much cheaper than the spec's estimate; also a good dev author |
| Primary judge | `google/gemini-3.1-pro-preview` | 2 / 12 | 1M | different vendor from the author |
| Vision critic (paid candidate), dev judge | `google/gemini-3-flash-preview` | 0.5 / 3 | 1M | |
| DeepSeek chat workhorse | `deepseek/deepseek-v4-flash` | 0.03 / 1.28 | 1M | text only; tools + structured outputs supported. **No `:free` DeepSeek exists on OpenRouter today**, so the paid one (very cheap) is used. |
| DeepSeek reasoning | `deepseek/deepseek-r1-0528` | 0.5 / 2.15 | 164k | used with prompted JSON output (tool calling is unreliable on R1-style models) |
| Free vision model (dev vision critic, free candidate in the F1 grid) | `google/gemma-4-31b-it:free` | 0 / 0 | 262k | text + image + video, tools supported |
| Free long-context text (dev digest) | `nvidia/nemotron-3-super-120b-a12b:free` | 0 / 0 | 262k | tools supported |
| Local fact extractor | `ollama:qwen3:4b` | local | n/a | **Ollama is not installed on this machine yet**: `ollama pull qwen3:4b` (about 2.5 GB, fits 4 GB VRAM at Q4). Until then the stage falls back to `deepseek/deepseek-v4-flash` and the trace says so. |

Cheaper than the spec assumed: Haiku 5.5 and DeepSeek V4 Flash cost a fraction of the spec's estimates, so the §5.3 total will land well under $10 if the Sonnet author runs stay at 3 or fewer.

## Still to verify with a real key (not possible offline)

- [ ] OpenRouter returns usage cost per response (the code asks for it with `openrouter_usage.include`; if absent the YAML prices are used and the trace shows `cost_source: estimate`).
- [ ] Free-model daily limits on this account.
- [ ] §5.2 side-by-side check for the cheap roles (digest, prior work, student critic, analyst): paid fallback vs. cheap model on 3 fixed inputs. Record the verdicts here, one line per role.
- [ ] The F1 check of the vision critic (`python -m papertrail.compare.critic_eval --prepare && --run`); put the winner into `vision_critic.model`.

## Other §17 facts checked

- **SlideAudit**: github.com/zhuohaouw/SlideAudit, **CC BY 4.0** (attribution required). 2,400 slides; `data/images/slide_XXXX.png`, `data/annotations/slide_XXXX.json` (one record per category with `response` and `has_strong_agreement`), `data/descriptions/slide_XXXX.json` (element boxes and text). Category names differ slightly from the paper ("Unbalanced Space Distribution", "Content Alignment Issues"); mapped in `src/papertrail/compare/slideaudit_data.py`. Assumption to verify: positive label = `response: true`.
- **lost_in_conversation**: MIT. `data/sharded_instructions_600.json` (627 instructions, 6 tasks) downloads fine. **It contains instructions and shards only, no per-run scores.** The aptitude/unreliability explanatory graph therefore cannot be built from released per-run data. Options: use the paper's tables where they have the numbers, or the Experiment A runs (SPEC §11). The analyst is told not to invent data and reports `ok=false` when the data does not exist.
- **WSL**: only the `docker-desktop` distro is installed, so `unshare -rn` is not available; the Windows fallback sandbox is used (stated in the README).
- **Semantic Scholar**: reachable without a key; cached, max 20 calls per run.
