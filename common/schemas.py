"""Pydantic models for every stage output (SPEC §7). These are the contracts between stages."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------- 7.0 ingest


class FigureRef(BaseModel):
    id: str
    path: str
    caption: str = ""
    page: Optional[int] = None


class Ingested(BaseModel):
    paper_id: str
    title: str
    source: Literal["arxiv-latex", "pdf"]
    n_pages: int = 0
    figures: list[FigureRef] = []
    n_tables: int = 0
    n_refs: int = 0
    authors: list[str] = []
    year: Optional[int] = None
    venue: str = ""


class RefEntry(BaseModel):
    key: str = ""
    title: str
    authors: str = ""
    year: Optional[int] = None


# ---------------------------------------------------------------- 7.1 digest


class Claim(BaseModel):
    text: str
    anchor: str = Field(description='"p.X", "Table Y" or "Fig. Z"')
    numbers: list[str] = []


class Term(BaseModel):
    term: str
    definition: str
    anchor: str


class Digest(BaseModel):
    problem: str
    contributions: list[str]
    method_summary: str
    claims: list[Claim]
    terms: list[Term]
    results: list[str]
    limitations: list[str]

    def drop_unanchored(self) -> "Digest":
        """Rule §7.1: anything the model can't anchor is dropped, not guessed."""
        self.claims = [c for c in self.claims if c.anchor.strip()]
        self.terms = [t for t in self.terms if t.anchor.strip()]
        return self


# ---------------------------------------------------------------- 7.2 difficulty map

Device = Literal["worked_example", "analogy", "diagram", "graph", "prior_work_contrast"]
WhyHard = Literal[
    "jargon", "counter-intuitive", "multi-step", "metric definition", "needs prior knowledge"
]


class HardConcept(BaseModel):
    concept: str
    why_hard: WhyHard
    prerequisites: list[str] = []
    misconception_to_avoid: str
    device: Device
    device_material: str = Field(
        description="Concrete: dataset instruction ID + shards / analogy mapping + where it breaks / "
        "node-edge sketch / data source and what the reader should see."
    )
    anchor: str


class AudienceModel(BaseModel):
    already_knows: list[str]
    must_be_taught: list[str]


class DifficultyMap(BaseModel):
    concepts: list[HardConcept]
    audience_model: AudienceModel


# ---------------------------------------------------------------- 7.3 prior work


class PriorWork(BaseModel):
    title: str
    year: Optional[int] = None
    relation: Literal["builds-on", "contrasts", "follow-up"]
    point: str
    used_for: Literal["motivation", "contrast slide", "Q&A backup"]
    semantic_scholar_id: Optional[str] = None
    in_paper_refs: bool = False


class PriorWorkList(BaseModel):
    works: list[PriorWork]


# ---------------------------------------------------------------- 7.4 plan

SlideDevice = Literal[
    "worked_example", "analogy", "diagram", "graph", "prior_work_contrast", "none"
]


class PlanSlide(BaseModel):
    id: str
    title: str = Field(description="Full-sentence claim, not a topic label.")
    purpose: str
    key_points: list[str] = Field(max_length=4)
    device: SlideDevice = "none"
    concept: Optional[str] = Field(default=None, description="difficulty_map concept this slide explains")
    figure_ref: Optional[str] = None
    table_ref: Optional[str] = None
    plot_request: Optional[str] = None
    diagram_request: Optional[str] = None
    layout: str = "claim-bullets"
    anchors: list[str] = []
    minutes: float

    @field_validator("minutes")
    @classmethod
    def _max_minutes(cls, v: float) -> float:
        if v > 3.5:  # only the quiz slide may exceed 2 minutes (checked in validate_plan)
            raise ValueError("no slide over 3.5 minutes")
        return v


class BackupSlide(BaseModel):
    id: str
    title: str
    purpose: str
    key_points: list[str] = []
    anchors: list[str] = []


class AnalysisRequest(BaseModel):
    id: str
    kind: Literal["replot", "explanatory_graph", "our_result"]
    description: str
    data_source: str


class DeferredConcept(BaseModel):
    concept: str
    reason: str


class Plan(BaseModel):
    story_arc: str
    slides: list[PlanSlide]
    backup_slides: list[BackupSlide]
    analysis_requests: list[AnalysisRequest] = []
    deferred_concepts: list[DeferredConcept] = []


REQUIRED_SLIDE_KEYWORDS = [
    # (name, keywords matched against lowercase title+purpose)
    # generic for any paper; a paper profile can add more (papers/<id>.yaml: extra_required_slides)
    ("motivation", ["motivation", "problem", "why", "challenge", "gap"]),
    ("method or setup", ["setup", "method", "approach", "design", "condition", "experiment", "architecture", "how it works"]),
    ("headline result", ["headline", "result", "finding", "performance", "improve", "outperform", "evaluation"]),
    ("prior-work positioning", ["prior", "related", "positioning", "background", "earlier work"]),
    ("limitations", ["limitation", "caveat", "weakness", "threat", "caution", "future work"]),
    ("our analysis", ["our analysis", "our own", "our reading", "we re", "replot", "re-plot", "replicat", "our look"]),
    ("takeaway", ["takeaway", "implication", "lesson", "so what", "bottom line"]),
]

QUIZ_LAYOUT = "claim-quiz"   # the one "check your understanding" slide: the questions, then their answers
QUIZ_QUESTIONS = 6            # 3 concept + 3 what-if: six fit above the footer at a readable size (eight did not)
QUIZ_MINUTES = 3.0
MAIN_MIN, MAIN_MAX = 13, 16


def normalize_minutes(plan: Plan, target: float = 19.5, cap: float = 2.0) -> None:
    """Models are poor at arithmetic: rescale the planned minutes proportionally to `target` total, never above `cap` per slide.
    The quiz slide gets a fixed QUIZ_MINUTES (questions, a pause for the audience, then the answers)."""
    if not plan.slides:
        return
    pinned = {i: QUIZ_MINUTES for i, s in enumerate(plan.slides) if s.layout == QUIZ_LAYOUT}
    total = sum(s.minutes for s in plan.slides)
    if 19.0 <= total <= 20.0 and all(s.minutes <= (QUIZ_MINUTES if i in pinned else cap) for i, s in enumerate(plan.slides)) \
            and all(abs(plan.slides[i].minutes - m) < 0.01 for i, m in pinned.items()):
        return
    weights = [max(s.minutes, 0.3) for s in plan.slides]
    fixed: dict[int, float] = dict(pinned)
    for _ in range(len(weights)):
        free = [i for i in range(len(weights)) if i not in fixed]
        left = target - sum(fixed.values())
        scale = left / sum(weights[i] for i in free) if free else 0
        over = [i for i in free if weights[i] * scale > cap]
        if not over:
            for i in free:
                fixed[i] = weights[i] * scale
            break
        for i in over:
            fixed[i] = cap
    for i, sl in enumerate(plan.slides):
        sl.minutes = round(min(fixed.get(i, cap), QUIZ_MINUTES if i in pinned else cap), 2)


def validate_plan(plan: Plan, concept_names: list[str], extra_required: list[dict] | tuple = ()) -> list[str]:
    """Return a list of human-readable rule violations (empty = valid). Rules from SPEC §7.4."""
    errs: list[str] = []
    if plan.slides and plan.slides[0].layout != "title":
        errs.append("the first slide must be the title slide (layout `title`)")
    n = len(plan.slides)
    if not MAIN_MIN <= n <= MAIN_MAX:
        errs.append(f"{n} main slides; need {MAIN_MIN}-{MAIN_MAX}")
    quiz = [i for i, s in enumerate(plan.slides) if s.layout == QUIZ_LAYOUT]
    if len(quiz) != 1:
        errs.append(f"need exactly one quiz slide (layout `{QUIZ_LAYOUT}`: {QUIZ_QUESTIONS} questions about the talk, answers below); found {len(quiz)}")
    elif quiz[0] in (0, n - 1):
        errs.append("the quiz slide goes after the results and limitations, before the takeaway and the final Tools & Workflow slide")
    for s in plan.slides:
        if s.minutes > 2.0 and s.layout != QUIZ_LAYOUT:
            errs.append(f"slide {s.id} has {s.minutes} minutes; only the quiz slide may exceed 2")
    total = sum(s.minutes for s in plan.slides)
    if not 19.0 <= total <= 20.0:
        errs.append(f"minutes total {total:.1f}; need 19-20")
    if len(plan.backup_slides) != 3:
        errs.append(f"{len(plan.backup_slides)} backup slides; need exactly 3")
    if plan.slides:
        last = plan.slides[-1]
        text = (last.title + " " + last.purpose).lower()
        if "tools" not in text or "workflow" not in text:
            errs.append("last main slide must be Tools & Workflow")
    assigned = {s.concept for s in plan.slides if s.concept} | {d.concept for d in plan.deferred_concepts}
    for c in concept_names:
        if c not in assigned:
            errs.append(f"hard concept not assigned to a slide or deferred: {c!r}")
    blob = [(s.title + " " + s.purpose).lower() for s in plan.slides]
    for name, kws in list(REQUIRED_SLIDE_KEYWORDS) + [(r["name"], r["keywords"]) for r in extra_required]:
        if not any(any(k in b for k in kws) for b in blob):
            errs.append(f"missing required slide: {name}")
    banned_titles = {"introduction", "overview", "key takeaways", "conclusion"}
    for s in plan.slides:
        if s.title.strip().lower() in banned_titles:
            errs.append(f"banned slide title: {s.title!r}")
    return errs


# ---------------------------------------------------------------- 7.6 author


class DeckClaim(BaseModel):
    slide: int
    text: str
    kind: Literal["number", "claim", "figure"]
    source: str = Field(description='anchor ("p.X", "Table Y") or artifact path ("artifacts/x.csv")')


class AuthorOutput(BaseModel):
    slides_md: str = Field(description="Full Slidev markdown, with speaker notes as HTML comments.")
    deck_claims: list[DeckClaim]


# ---------------------------------------------------------------- 7.7 render loop

IssueSource = Literal["automatic", "vision_slide", "vision_deck", "student"]


class VisionIssue(BaseModel):
    slide: int
    category: str
    element_ids: list[int] = []
    issue: str
    problem_description: str
    fix_steps: list[str]
    expected_improvement: str
    severity: Literal["low", "high"]


class VisionReport(BaseModel):
    """A well-designed slide returns an empty list (SlideAudit: do not force-find issues)."""

    issues: list[VisionIssue] = []


class StudentIssue(BaseModel):
    slide: int
    confusion: Literal["undefined_term", "missing_step", "unclear_figure", "forward_reference"]
    severity: Literal["low", "high"]
    question_they_would_ask: str


class StudentReport(BaseModel):
    issues: list[StudentIssue] = []


class QAIssue(BaseModel):
    """Unified issue record written to qa.json."""

    round: int
    source: IssueSource
    slide: int
    category: str
    severity: Literal["low", "high"]
    detail: str
    source_lines: Optional[str] = None
    fixed: Optional[bool] = None


# ---------------------------------------------------------------- 7.8 fact check


class NumberPair(BaseModel):
    slide: int
    value: str
    claim: str


class NumberPairs(BaseModel):
    pairs: list[NumberPair]


class FactCheck(BaseModel):
    n_extracted: int
    n_matched: int
    unmatched: list[NumberPair] = []
    waived: list[NumberPair] = []


# ---------------------------------------------------------------- 7.9 judge


class ChecklistItem(BaseModel):
    """Paper-specific atomic item. It is a sub-check of the static rubric item `parent` (e.g. E1): the parent passes only if all its children pass."""

    id: str
    parent: str
    text: str


class Checklist(BaseModel):
    items: list[ChecklistItem]


class JudgeItemResult(BaseModel):
    item_id: str
    passed: bool = Field(alias="pass")
    evidence_slide: Optional[int] = None
    evidence_paper_quote: Optional[str] = None
    issue: str = ""
    suggested_fix: str = ""

    model_config = {"populate_by_name": True}


class JudgeDimensionResult(BaseModel):
    results: list[JudgeItemResult]


class JudgeReport(BaseModel):
    judge_role: str
    judge_model: str = ""
    repeats: int = 2
    scores: dict[str, float]
    total: float
    hard_fail: bool
    items: list[dict]
    disagreements: list[str] = []


# ---------------------------------------------------------------- quiz slide


class QuizItem(BaseModel):
    kind: Literal["concept", "what_if"]
    question: str = Field(description="At most 16 words. Concept: tests understanding. What-if: changes one thing and asks what happens and why.")
    answer: str = Field(description="At most 26 words, answers the question AND says why. Numbers exactly as printed in the source.")
    anchor: str = Field(description="p.N, Table N or Fig. N that supports the answer")
    evidence: Literal["paper", "reasoned"] = Field(
        description="paper = the paper tests or states it; reasoned = the paper does not test it, the answer is our reasoning and must start with 'Not tested:'")


class Quiz(BaseModel):
    items: list[QuizItem]


def validate_quiz(q: Quiz, n_pages: int | None = None) -> list[str]:
    from common.anchors import valid_anchor

    errs: list[str] = []
    n = len(q.items)
    if n != QUIZ_QUESTIONS:
        errs.append(f"{n} questions; need {QUIZ_QUESTIONS}")
    what_if = sum(1 for i in q.items if i.kind == "what_if")
    if what_if < 3:
        errs.append(f"{what_if} what-if questions; need at least 3 (change one thing, ask what happens and why)")
    if sum(1 for i in q.items if i.kind == "concept") < 3:
        errs.append("need at least 3 concept questions (why does it work, what does it mean, how is it computed)")
    for k, i in enumerate(q.items, start=1):
        if len(i.question.split()) > 16:
            errs.append(f"question {k} has {len(i.question.split())} words; limit 16")
        if len(i.answer.split()) > 26:
            errs.append(f"answer {k} has {len(i.answer.split())} words; limit 26")
        if not valid_anchor(i.anchor, n_pages):
            errs.append(f"question {k} lacks a valid anchor")
        if i.evidence == "reasoned" and not i.answer.strip().lower().startswith("not tested"):
            errs.append(f"answer {k} is our own reasoning, so it must start with 'Not tested:'")
        if i.evidence == "paper" and i.answer.strip().lower().startswith("not tested"):
            errs.append(f"answer {k} says 'Not tested' but is marked evidence=paper")
    if len({i.question.strip().lower() for i in q.items}) != n:
        errs.append("duplicate questions")
    return errs


# ---------------------------------------------------------------- per-slide revision (render loop)


class SlideRewrite(BaseModel):
    no: int = Field(description="Number of the slide being replaced (as listed in the issues)")
    markdown: str = Field(description="The COMPLETE replacement for that slide: frontmatter block, content and the speaker-notes comment")
    claims: list[DeckClaim] = Field(default_factory=list, description="deck_claims for this slide only")


class RevisionOutput(BaseModel):
    slides: list[SlideRewrite]


# ---------------------------------------------------------------- style references


class StyleExample(BaseModel):
    file: str
    layout_pattern: str = Field(description="How the slide is laid out, in one sentence")
    visual_device: str = Field(description="What carries the message: chart, diagram, photo, big number, table, icon row, text only ...")
    what_works: list[str] = Field(description="Specific design moves that make it effective (max 3)")
    avoid_copying: str = Field(description="Its own content or branding that must NOT be reproduced")


class StyleBrief(BaseModel):
    examples: list[StyleExample]
    principles: list[str] = Field(description="6 to 10 concrete, transferable design rules distilled from the examples")
    quality_bar: list[str] = Field(description="5 to 8 checkable features our deck must match or beat (e.g. 'every content slide has a visual that fills at least half the area')")


class FeatureScore(BaseModel):
    feature: str
    references: int = Field(ge=1, le=5, description="1 to 5 for the reference slides")
    ours: int = Field(ge=1, le=5, description="1 to 5 for our deck")
    note: str = ""


class StyleComparison(BaseModel):
    features: list[FeatureScore]
    verdict: str = Field(description="Two sentences: where ours is at least as good, where it falls short")
    slides_to_improve: list[int] = []
