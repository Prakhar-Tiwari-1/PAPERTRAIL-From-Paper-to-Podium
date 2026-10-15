<template>
  <div class="slidev-layout section" style="background:var(--primary);color:#FFFFFF;justify-content:center">
    <slot />
  </div>
</template>
<style>
.slidev-layout.section h1 { font-size: 52px; color: #FFFFFF; }
.slidev-layout.section h1::after { background: var(--warm); }
</style>
