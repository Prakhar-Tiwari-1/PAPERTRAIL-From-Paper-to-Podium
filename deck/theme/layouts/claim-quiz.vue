<template>
  <div class="slidev-layout claim-quiz">
    <slot />
  </div>
</template>
<style>
.slidev-layout.claim-quiz { gap: 10px; padding-top: 64px; padding-bottom: 76px; }
.slidev-layout.claim-quiz h1 { font-size: 32px; padding-bottom: 14px; }
.slidev-layout.claim-quiz .qa-board { display: flex; flex-direction: column; gap: 12px; flex: 1 1 auto; min-height: 0; }
.slidev-layout.claim-quiz .qa-block { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 28px; align-content: start; }
.slidev-layout.claim-quiz .qa-questions { background: var(--tint); border-left: 8px solid var(--accent); border-radius: 4px; padding: 14px 20px; }
.slidev-layout.claim-quiz .qa-answers { background: var(--tint-warm); border-left: 8px solid var(--warm); border-radius: 4px; padding: 14px 20px; }
.slidev-layout.claim-quiz .qa-q, .slidev-layout.claim-quiz .qa-a { display: flex; gap: 10px; align-items: flex-start; line-height: 1.25; }
.slidev-layout.claim-quiz .qa-q { font-size: 20px; font-weight: 600; color: var(--primary); }
.slidev-layout.claim-quiz .qa-a { font-size: 18px; color: var(--fg); }
.slidev-layout.claim-quiz .qa-n { flex: 0 0 auto; min-width: 26px; height: 26px; border-radius: 13px; background: var(--primary); color: #FFFFFF; font-size: 15px; font-weight: 700; display: inline-flex; align-items: center; justify-content: center; }
.slidev-layout.claim-quiz .qa-answers .qa-n { background: var(--warm); color: var(--fg); }
</style>
