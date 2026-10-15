<template>
  <div class="slidev-layout claim-quiz">
    <slot />
  </div>
</template>
<style>
.slidev-layout.claim-quiz { gap: 14px; padding-top: 56px; padding-bottom: 76px; }
.slidev-layout.claim-quiz h1 { font-size: 34px; }
.slidev-layout.claim-quiz .qa-board { display: flex; flex-direction: column; gap: 14px; flex: 1 1 auto; min-height: 0; }
/* six items: three in the left column, three in the right (concept questions left, what-ifs right) */
.slidev-layout.claim-quiz .qa-block { display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: repeat(3, auto); grid-auto-flow: column; gap: 12px 36px; align-content: start; }
.slidev-layout.claim-quiz .qa-questions { background: var(--tint); border-left: 8px solid var(--accent); border-radius: 4px; padding: 16px 24px; }
.slidev-layout.claim-quiz .qa-answers { background: var(--tint-warm); border-left: 8px solid var(--warm); border-radius: 4px; padding: 16px 24px; }
.slidev-layout.claim-quiz .qa-q, .slidev-layout.claim-quiz .qa-a { display: flex; gap: 8px; align-items: baseline; line-height: 1.28; }
.slidev-layout.claim-quiz .qa-q { font-size: 22px; font-weight: 600; color: var(--primary); }
.slidev-layout.claim-quiz .qa-a { font-size: 19px; color: var(--fg); }
/* plain bold numbers ("1."), no circle */
.slidev-layout.claim-quiz .qa-n { flex: 0 0 auto; min-width: 26px; font-weight: 700; color: var(--primary); }
.slidev-layout.claim-quiz .qa-n::after { content: "."; }
.slidev-layout.claim-quiz .qa-answers .qa-n { color: var(--warm); }
</style>
