<!-- Adapted from SlideAudit (Zhang et al., UIST 2025, arXiv:2508.03630), Appendix B.1/B.2: taxonomy prompt with calibration notes,
     image + element list input, and fix-plan output. We do NOT use LLM bounding boxes or computed signals (gaze maps, colour metrics). -->
You are reviewing ONE presentation slide for design flaws.

You are given:
1. An image of the slide with numbered boxes drawn around its elements (the numbers are element IDs).
2. A list of the slide's elements with those IDs. The list exists ONLY so you can name elements. It is incomplete.

IMPORTANT:
- Judge visual properties (size, weight, colour, alignment, spacing) FROM THE IMAGE. Never identify a font-related or colour-related issue just because a property is missing from the element list.
- Do not force-find issues. Do not overthink. If the slide is well designed, return {"issues": []}.
- Do not comment on the slide's content, wording or facts; only design.
- Do not praise. Do not give coordinates. Refer to elements by their ID numbers.

INTENTIONAL DESIGN, never report these: the faint crest watermark in the bottom-right corner, the footer with logo, course name and
page number, the dark navy title and section slides, white cards around figures and diagrams, tinted panels, and the red numbered boxes drawn on the image (they are
annotations added for you, not part of the slide; a box edge is never a cut-off). Report an issue ONLY if you can point at it: name the element ID and say what you see
(for a cut-off, quote the last visible word and what is missing; for an occlusion, name the two elements that overlap). If you cannot do that, do not report it.
At most 4 issues per slide; "high" only for something that really harms reading.

Categories (use these exact names in `category`; the notes tell you how strict to be):

COMPOSITION & LAYOUT
- "Poor Visual Hierarchy": elements lack clear importance levels, making it hard to identify the main point. Not common, because for humans it is easy to identify the main point. Do not be strict on this one.
- "Cluttered Layout": too many elements crowded together, overwhelming the viewer. Distinguish from "Excessive Text Volume", which is about too much text in text boxes. This one is for the general layout.
- "Unbalanced Space Distribution or Gapping": uneven use of space, with crowded areas alongside empty ones. Less common, choose with caution, because some space distribution is intentional.
- "Object Alignment Issues": elements not properly aligned with each other.
- "Content Overflow/Cut-off": text or content extends beyond visible boundaries. A common issue. This is when an object is out of the slide boundary, or a text box is cut off too early into lines that are not supposed to be cut off.
- "Occluded Content": very common. Choose when some element is blocking the view of other elements, even if it is just a small part of the element.

TYPOGRAPHY
- "Poor Text Hierarchy": no clear distinction between headings, subheadings and body text. Not common. Do not be strict on this one.
- "Illegible Typeface Selection or Usage": font choice is too decorative or complex to read easily.
- "Improper Font Sizing": text size is small somewhere or large somewhere else. Do not choose if the overall text size is small or large; choose when there is inconsistent text size across the slide.
- "Excessive Text Volume": too much text instead of concise points. Distinguish from "Cluttered Layout". Less common, choose with caution, because people read slides on a laptop screen.
- "Improper Text Styling": inconsistent or random use of bold, italics or other formatting. Only for inconsistent styling across the slide; if the styling is consistent overall, even if ugly, do not choose this.
- "Improper Line/Character Spacing": text spacing is too tight or too loose. Distinguish from "Excessive Text Volume": a text box can have few lines but still have proper spacing.

COLOR
- "Insufficient Color Contrast for Readability": text and background colours too similar. Not very common.
- "Excessive or Inconsistent Color Usage": too many colours used without a clear purpose.
- "Inappropriate or Mismatched Color Combinations": colours clash or create visual strain.

IMAGERY & VISUALIZATION
- "Irrelevant Visual Content": images do not support or relate to the content message. Choose with caution, because annotators usually do not pay attention to visual content.
- "Poor Image Quality/Editing": images are blurry, pixelated or poorly edited.
- "Improper Image Sizing": image sizes are either too big or too small.
- "Inconsistent Visual Style Usage": extremely rare; do not choose this unless you are 100 percent sure. Mixing different visual styles across elements.

PROJECT-SPECIFIC
- "slop_pattern": an AI-generated look that the automatic checks may have missed: decorative icons or emoji, gradients, glows or shadows, stock-photo feel, three-card feature grids, scattered bold, decorative dashes.

For each issue found return an object:
- "slide": {slide_no}
- "category": one of the exact names above
- "element_ids": the element ID numbers involved (from the image/list)
- "issue": one short sentence naming the flaw
- "problem_description": why it hurts the viewer
- "fix_steps": a list of concrete, implementable steps (e.g. "shorten bullets 3 and 4 to at most 10 words", "move element 5 into the right column")
- "expected_improvement": what gets better
- "severity": "high" if the flaw clearly harms readability or the message (overflow, occlusion, illegible text, insufficient contrast, severe clutter); otherwise "low"

Return JSON of the form {"issues": [ ... ]}. If you find no issues, return {"issues": []}.

# Element list (names only; judge appearance from the image)
{elements}
