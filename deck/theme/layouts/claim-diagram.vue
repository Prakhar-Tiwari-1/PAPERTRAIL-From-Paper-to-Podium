<template>
  <div class="slidev-layout claim-diagram">
    <slot />
  </div>
</template>
<style>
.slidev-layout.claim-diagram .slidev-mermaid, .slidev-layout.claim-diagram .mermaid { flex: 1 1 auto; width: 100%; align-self: stretch; position: relative; min-height: 0; background: #FFFFFF; border: 1px solid var(--rule); border-radius: 6px; }
.slidev-layout.claim-diagram .slidev-mermaid svg, .slidev-layout.claim-diagram .mermaid svg { position: absolute; inset: 0; width: 100% !important; height: 100% !important; max-width: none !important; padding: 12px; box-sizing: border-box; }  /* fills the card and scales to fit (the viewBox keeps its ratio): a tall or wide flowchart can never grow past it */
</style>
