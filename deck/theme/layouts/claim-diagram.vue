<template>
  <div class="slidev-layout claim-diagram">
    <slot />
  </div>
</template>
<style>
.slidev-layout.claim-diagram .slidev-mermaid, .slidev-layout.claim-diagram .mermaid { flex: 1 1 auto; width: 100%; align-self: stretch; display: flex; justify-content: center; align-items: center; min-height: 0; background: #FFFFFF; border: 1px solid var(--rule); border-radius: 6px; }
.slidev-layout.claim-diagram .slidev-mermaid svg, .slidev-layout.claim-diagram .mermaid svg { width: 100% !important; height: auto; max-height: 400px; }
</style>
