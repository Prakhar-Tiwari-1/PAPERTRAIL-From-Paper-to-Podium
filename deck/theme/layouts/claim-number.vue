<template>
  <div class="slidev-layout claim-number">
    <slot />
  </div>
</template>
<style>
.slidev-layout.claim-number { justify-content: flex-start; }
.slidev-layout.claim-number .big-number { background: var(--tint); border-left: 8px solid var(--warm); border-radius: 6px; padding: 18px 40px; align-self: stretch; font-size: 190px !important; }
.slidev-layout.claim-number p { font-size: 30px; color: var(--fg); line-height: 1.35; }
.slidev-layout.claim-number .caption { font-size: 16px; color: var(--muted); }
</style>
