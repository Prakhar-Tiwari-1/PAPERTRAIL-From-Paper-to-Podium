<template>
  <div class="slidev-layout claim-bullets">
    <slot />
  </div>
</template>
<style>
.slidev-layout.claim-bullets ul { flex: 1 1 auto; justify-content: center; background: var(--tint); border-left: 8px solid var(--accent); border-radius: 4px; padding: 24px 32px 24px 56px; gap: 22px; }
.slidev-layout.claim-bullets li { font-size: 28px; }
</style>
