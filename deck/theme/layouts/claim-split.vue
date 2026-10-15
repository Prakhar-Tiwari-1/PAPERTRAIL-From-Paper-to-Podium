<template>
  <div class="slidev-layout claim-split">
    <slot />
    <div class="split">
      <div class="split-visual"><slot name="left" /></div>
      <div class="split-text"><slot name="right" /></div>
    </div>
  </div>
</template>
<style>
.slidev-layout.claim-split .split { flex: 1 1 auto; min-height: 0; display: grid; grid-template-columns: 1.15fr 1fr; gap: 32px; align-items: stretch; }
.slidev-layout.claim-split .split-visual { display: flex; flex-direction: column; gap: 8px; justify-content: center; align-items: center; min-width: 0; min-height: 0; }
.slidev-layout.claim-split .split-visual img { max-height: 400px; background: #FFFFFF; border: 1px solid var(--rule); border-radius: 6px; padding: 10px; }
.slidev-layout.claim-split .split-visual .slidev-mermaid, .slidev-layout.claim-split .split-visual .mermaid { width: 100%; background: #FFFFFF; border: 1px solid var(--rule); border-radius: 6px; display: flex; justify-content: center; }
.slidev-layout.claim-split .split-visual .slidev-mermaid svg, .slidev-layout.claim-split .split-visual .mermaid svg { width: 100% !important; height: auto; max-height: 380px; }
.slidev-layout.claim-split .split-text { background: var(--tint); border-left: 8px solid var(--accent); border-radius: 4px; padding: 22px 26px; display: flex; flex-direction: column; justify-content: center; gap: 14px; font-size: 24px; }
.slidev-layout.claim-split .split-text ul { padding-left: 24px; }
.slidev-layout.claim-split .caption { align-self: flex-start; }
</style>
