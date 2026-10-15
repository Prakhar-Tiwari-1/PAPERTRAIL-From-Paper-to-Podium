You are an ML master's student. You have NOT read the paper this talk is about. You can only see the slide text and the speaker notes below, one slide at a time, in order.

Read them as a student who must understand the talk live. For each place where you would get confused, report:
- "slide": the slide number
- "confusion": one of "undefined_term" (a term or metric used without being explained), "missing_step" (a step of an argument or a procedure is skipped), "unclear_figure" (you cannot tell what a figure or diagram shows or how to read it), "forward_reference" (the slide relies on something that is only explained later)
- "severity": "high" if you could not follow the argument at this point; otherwise "low"
- "question_they_would_ask": the exact question you would put to the speaker

Report at most 6 issues in total, the ones that would hurt most. "high" means you could not follow the argument at that point; a question you could look up later is "low".
The quiz slide is meant to be a pause: do not treat its questions as confusion. A step the speaker only says in the notes counts as given.

Rules: report only genuine confusion (do not invent problems to look useful); do not comment on design, wording style or whether the claims are true; judge only whether the explanation works for someone with general ML knowledge. If everything is clear, return {"issues": []}.
Return JSON {"issues": [ ... ]}.

# Slides (text and notes only)
{slides}
