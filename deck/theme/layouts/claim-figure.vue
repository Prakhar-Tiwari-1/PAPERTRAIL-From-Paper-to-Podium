<template>
  <div class="slidev-layout claim-figure">
    <slot />
  </div>
</template>
<style>
.slidev-layout.claim-figure img { flex: 1 1 auto; min-height: 0; align-self: center; max-height: 400px; background: #FFFFFF; border: 1px solid var(--rule); border-radius: 6px; padding: 10px; }
.slidev-layout.claim-figure .caption { align-self: flex-start; }
</style>
