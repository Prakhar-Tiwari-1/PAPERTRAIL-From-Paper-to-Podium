"""A scripted fake model for offline end-to-end runs: returns schema-valid canned outputs for every role, so the whole
pipeline (including real Slidev rendering and Playwright QA) can be exercised without an API key or spending money."""
from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

ROOT = Path(__file__).resolve().parent.parent

LOREM = ("so what this means for you is that the model commits early and then cannot recover when new details arrive in later turns "
         "and we will walk through that slowly with one example before moving on to the next point").split()


def notes(n_words: int, transition: str) -> str:
    words = (LOREM * (n_words // len(LOREM) + 1))[: n_words - len(transition.split())]
    return " ".join(words) + " " + transition


FRONT = ("---\ntheme: ./theme\nrouterMode: hash\ncanvasWidth: 1280\naspectRatio: 16/9\nfonts:\n  provider: none\n  sans: Inter\n"
         "  mono: JetBrains Mono\nlayout: title\n---\n\n")
QUIZ = [("concept", "Why does a model that answers early get stuck on its first guess?", "Its first attempt stays in the conversation and later details are fitted around it.", "paper"),
        ("concept", "What does unreliability measure that average performance hides?", "The gap between best and worst runs of the same instruction, so how much luck decides.", "paper"),
        ("concept", "Why call the loss getting lost and not just worse?", "The same model solves the task when told everything at once, so the ability is there but not used.", "paper"),
        ("what_if", "What if the temperature is set to zero?", "Unreliability drops but a large share stays, so randomness is not the main cause.", "paper"),
        ("what_if", "What if the user repeats everything in a final turn?", "Performance improves but stays below the single-turn level, so a recap helps only part of the way.", "paper"),
        ("what_if", "What if only one shard is revealed per turn instead of several?", "Not tested: with fewer pieces there is less to anchor on early, so we would expect a smaller drop.", "reasoned")]


class FakeScript:
    """State shared across calls: critic rounds decline in issues so the loop visibly converges."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.vision_calls = 0
        self.student_calls = 0
        self.author_calls = 0

    # ---- helpers
    @staticmethod
    def user_text(messages) -> str:
        out = []
        for m in messages:
            if isinstance(m, ModelRequest):
                for p in m.parts:
                    if isinstance(p, UserPromptPart):
                        c = p.content
                        out.append(c if isinstance(c, str) else " ".join(x for x in c if isinstance(x, str)))
        return "\n".join(out)

    def figures(self) -> list[str]:
        info = json.loads((self.run_dir / "ingested.json").read_text(encoding="utf-8"))
        return [Path(f["path"]).name for f in info["figures"]]

    # ---- canned payloads per output schema
    def payload(self, props: set[str], prompt: str):
        from tools import dataset as dataset_tool

        if {"problem", "claims", "terms"} <= props:
            return {"problem": "LLMs lose track in multi-turn chats.", "contributions": ["A simulation of sharded conversations"],
                    "method_summary": "Sharded instructions are revealed turn by turn.",
                    "claims": [{"text": "Performance drops in multi-turn settings", "anchor": "p.1", "numbers": ["35%"]},
                               {"text": "A claim with no anchor", "anchor": "", "numbers": []}],
                    "terms": [{"term": "aptitude", "definition": "best-case performance", "anchor": "p.2"}],
                    "results": ["Average drop of 39%"], "limitations": ["Models tested are limited"]}
        if {"concepts", "audience_model"} <= props:
            ds = dataset_tool.active()
            example = f"{ds.lookup(None, 1)[0]['id']} shown turn by turn" if ds else "the example printed in Table 1 on p.2"
            return {"concepts": [
                {"concept": f"concept {i}", "why_hard": "jargon", "prerequisites": [], "misconception_to_avoid": "none",
                 "device": "worked_example" if i == 0 else "analogy" if i == 1 else "diagram",
                 "device_material": example if i == 0 else "mapping; the analogy breaks when numbers matter" if i == 1 else "A -> B -> C",
                 "anchor": "p.2"} for i in range(6)],
                "audience_model": {"already_knows": ["transformers"], "must_be_taught": ["sharding"]}}
        if props == {"works"}:
            refs = json.loads((self.run_dir / "refs.json").read_text(encoding="utf-8"))
            return {"works": [{"title": r["title"][:120], "year": r.get("year"), "relation": "builds-on", "point": "related work",
                               "used_for": "motivation", "semantic_scholar_id": None, "in_paper_refs": True} for r in refs[:3]]}
        if {"story_arc", "slides", "backup_slides"} <= props:
            dm = json.loads((self.run_dir / "difficulty_map.json").read_text(encoding="utf-8"))
            titles = ["Title", "Motivation: models get lost when details arrive late", "The setup shards one instruction into turns",
                      "Conditions isolate what makes multi-turn hard", "Metrics: aptitude and unreliability explained",
                      "Headline result: a large average drop", "Failure behaviours: models answer too early", "Prior work positions this study",
                      "Our analysis re-plots the main figure", "Limitations include dated models", "Check your understanding",
                      "Takeaway: tell the model everything at once", "Tools & Workflow of this talk"]
            slides = []
            for i, t in enumerate(titles):
                s = {"id": f"s{i+1}", "title": t, "purpose": t.lower(), "key_points": ["one point"], "minutes": 1.4, "anchors": ["p.1"], "layout": "claim-figure"}
                if i == 0:
                    s["layout"] = "title"
                if t.startswith("Check your understanding"):
                    s["layout"] = "claim-quiz"
                if i == len(titles) - 1:
                    s["layout"], s["purpose"] = "workflow", "tools and workflow"
                if i < len(dm["concepts"]):
                    s["concept"] = dm["concepts"][i]["concept"]
                    s["device"] = dm["concepts"][i]["device"]
                slides.append(s)
            return {"story_arc": "problem -> setup -> result -> limits", "slides": slides,
                    "backup_slides": [{"id": f"b{i}", "title": f"Backup {i}", "purpose": "detail"} for i in range(3)],
                    "analysis_requests": [{"id": "replot_fig", "kind": "replot", "description": "re-plot a figure", "data_source": "Table 1"}]}
        if {"ok", "csv_files", "svg_file"} <= props:
            return {"ok": True, "csv_files": ["replot_fig.csv"], "svg_file": "replot_fig.svg",
                    "caption": "Our analysis, artifacts/replot_fig.csv", "notes": "fake analysis"}
        if {"slides_md", "deck_claims"} <= props:
            return self.author_payload()
        if props == {"slides"}:
            return self.revision_payload(prompt)
        if props == {"items"} and "check your understanding" in prompt[:200]:
            return {"items": [{"kind": k, "question": q, "answer": a, "anchor": "p.1", "evidence": ev} for k, q, a, ev in QUIZ]}
        if {"examples", "principles", "quality_bar"} <= props:
            labels = sorted(set(re.findall(r"image (\d+):", prompt)), key=int)
            return {"examples": [{"file": f"image {n}", "layout_pattern": "one large visual with a claim title", "visual_device": "chart",
                                  "what_works": ["the visual fills most of the slide"], "avoid_copying": "its text and logo"} for n in labels],
                    "principles": [f"Principle {k}: let one visual carry the message" for k in range(6)],
                    "quality_bar": [f"feature {k}" for k in range(5)]}
        if {"features", "verdict"} <= props:
            feats = re.findall(r"^- (.+)$", prompt.split("Features:")[1].split("Return JSON")[0], re.M)
            return {"features": [{"feature": f, "references": 4, "ours": 4, "note": "comparable"} for f in feats], "verdict": "Ours is comparable.", "slides_to_improve": []}
        if props == {"issues"}:
            if "student" in prompt.lower()[:200] or "master's student" in prompt:
                self.student_calls += 1
                return {"issues": [{"slide": 3, "confusion": "undefined_term", "severity": "high", "question_they_would_ask": "What is sharding?"}]
                        if self.student_calls == 1 else []}
            self.vision_calls += 1
            if self.vision_calls == 1:   # a false claim the DOM measurements do not support: triage must demote it
                return {"issues": [{"slide": 2, "category": "Content Overflow/Cut-off", "element_ids": [1], "issue": "title cut off", "problem_description": "x",
                                    "fix_steps": ["shorten"], "expected_improvement": "fits", "severity": "high"}]}
            return {"issues": []}
        if props == {"pairs"}:
            return {"pairs": []}
        if props == {"items"}:
            return {"items": [{"id": "E1.1", "parent": "E1", "text": "explains concept 0"}, {"id": "C2.1", "parent": "C2", "text": "states the contribution"}]}
        if props == {"results"}:
            ids = re.findall(r"^- ([A-Z]\d(?:\.\d+)?)\b", prompt, re.M)
            return {"results": [{"item_id": i, "pass": True, "evidence_slide": 2, "evidence_paper_quote": "LLMs get Lost in Conversation", "issue": "", "suggested_fix": ""} for i in ids]}
        if props == {"mapped"}:
            return {"mapped": []}
        raise AssertionError(f"fake has no payload for schema props {props}")

    # ---- the deck
    def author_payload(self):
        self.author_calls += 1
        figs = self.figures()
        parts = [FRONT + "# Paper to podium demo\n\nA fake deck\n\n<!--\n" + notes(190, "Next, the setup.") + "\n-->\n"]
        claims = []
        for i in range(2, 11):   # nine content slides (slides 2 to 10)
            fig, tag = figs[i % len(figs)], chr(64 + i)
            if i == 6:           # a deliberately sparse bullets slide: the empty-space check must send it to the reviser
                layout, body = "claim-bullets", f"# Claim {tag}: three short points\n\n- The first guess anchors the rest\n- Later turns add details\n- Models rarely recover\n"
            elif i == 5:
                layout, body = "claim-table", ("# Claim E: each condition isolates one cause\n\n| Condition | What it isolates |\n|---|---|\n| Full | the task itself |\n"
                                               "| Concat | rephrasing without turns |\n| Sharded | the turn structure |\n\n<SourceCaption>Laban et al., 2025, Table 1</SourceCaption>\n")
            elif i % 4 == 0:
                layout, body = "claim-figure", f"# Claim {tag}: the model loses the thread\n\n<img src=\"/figures/{fig}\" />\n\n<SourceCaption>Laban et al., 2025, Fig. 1</SourceCaption>\n"
            elif i % 4 == 1:
                layout, body = "claim-number", f"# Claim {tag}: the average drop is large\n\n<BigNumber>39%</BigNumber>\n\nAverage performance drop across tasks\n"
                claims.append({"slide": len(parts) + 1, "text": "39% average drop", "kind": "number", "source": "p.1"})
            elif i % 4 == 2:
                layout, body = "claim-diagram", (f"# Claim {tag}: answers stick once given\n\n```mermaid\nflowchart LR\n  A[First guess] --> B[Later details] --> C[Wrong answer]\n```\n\n"
                                                 "<SourceCaption>Our analysis, artifacts/replot_fig.csv</SourceCaption>\n")
            else:
                layout, body = "claim-split", (f"# Claim {tag}: one figure and its reading\n\n::left::\n\n<img src=\"/figures/{fig}\" />\n\n<SourceCaption>Laban et al., 2025, Fig. 1</SourceCaption>\n\n"
                                               "::right::\n\n- The curve falls with every turn\n- Early answers are rarely revised\n")
            if self.author_calls == 1 and i == 3:   # round-1 defect: far too many words on one slide
                body += " ".join(["extra"] * 80) + "\n"
            parts.append(f"---\nlayout: {layout}\n---\n\n{body}\n<!--\n{notes(190, 'Next slide.')}\n-->\n")
        parts.append(f"---\nlayout: claim-quiz\n---\n\n# Check your understanding\n\n<!--\n{notes(190, 'Now the takeaway.')}\n-->\n")
        n_take = len(parts) + 1
        parts.append("---\nlayout: claim-number\n---\n\n# Takeaway: say everything at once\n\n<BigNumber>39%</BigNumber>\n\nAverage drop when details arrive in pieces\n\n"
                     f"<!--\n{notes(190, 'Last, the tools.')}\n-->\n")
        claims.append({"slide": n_take, "text": "39% average drop", "kind": "number", "source": "p.1"})
        parts.append(f"---\nlayout: workflow\n---\n\n# Tools & Workflow\n\n<!--\n{notes(190, 'That is the end.')}\n-->\n")
        parts.append("---\nlayout: section\n---\n\n# Backup\n\n<!--\nbackup\n-->\n")
        for i in range(3):
            parts.append(f"---\nlayout: claim-figure\n---\n\n# Backup detail {chr(97+i)}\n\n<img src=\"/figures/{figs[i % len(figs)]}\" />\n\n"
                         "<SourceCaption>Laban et al., 2025, Fig. 1</SourceCaption>\n\n<!--\nbackup notes\n-->\n")
        claims.append({"slide": 9, "text": "re-plot of Fig. 1", "kind": "figure", "source": "artifacts/replot_fig.csv"})
        return {"slides_md": "\n".join(parts), "deck_claims": claims}

    def revision_payload(self, prompt: str):
        figs = self.figures()
        out = []
        for n in re.findall(r"^### Slide (\d+) \(", prompt, re.M):
            fig = figs[int(n) % len(figs)]
            block = (f"---\nlayout: claim-split\n---\n\n# Claim {chr(64 + int(n))}: repaired with a visual\n\n::left::\n\n<img src=\"/figures/{fig}\" />\n\n"
                     "<SourceCaption>Laban et al., 2025, Fig. 1</SourceCaption>\n\n::right::\n\n- The visual carries the point\n- Two short takeaways\n\n"
                     f"<!--\n{notes(190, 'Next slide.')}\n-->")
            out.append({"no": int(n), "markdown": block, "claims": []})
        return {"slides": out}


def make_factory(run_dir: Path):
    script = FakeScript(run_dir)

    def factory(slug: str):
        def fn(messages, info: AgentInfo):
            prompt = script.user_text(messages)
            # analyst tool loop: first call runs python, second returns the final result
            if info.function_tools and any(t.name == "run_python" for t in info.function_tools):
                last = messages[-1]
                if not any(isinstance(p, ToolReturnPart) for p in getattr(last, "parts", [])):
                    code = ("import csv\nfrom tools.plot_style import apply_style\napply_style()\nimport matplotlib.pyplot as plt\n"
                            "rows=[('a',1),('b',2)]\nw=csv.writer(open('replot_fig.csv','w',newline=''))\nw.writerow(['x','y'])\n"
                            "[w.writerow(r) for r in rows]\nplt.plot([r[1] for r in rows]);plt.savefig('replot_fig.svg')\n")
                    return ModelResponse(parts=[ToolCallPart("run_python", {"code": code})])
            tools = info.output_tools
            if not tools:  # prompted output: the schema is not in the request, so decide by what the prompt asks for
                if "Write a checklist" in prompt:
                    props = {"items"}
                elif "# Items to grade" in prompt:
                    props = {"results"}
                else:
                    props = {"pairs"}
                return ModelResponse(parts=[TextPart(json.dumps(script.payload(props, prompt)))])
            props = set(tools[0].parameters_json_schema.get("properties", {}))
            return ModelResponse(parts=[ToolCallPart(tools[0].name, script.payload(props, prompt))])

        return FunctionModel(fn)

    return factory, script
