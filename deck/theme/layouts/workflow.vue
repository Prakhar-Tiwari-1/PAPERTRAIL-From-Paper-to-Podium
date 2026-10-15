<template>
  <div class="slidev-layout workflow">
    <slot />
    <div class="cols">
      <div class="col"><slot name="left" /></div>
      <div class="col"><slot name="right" /></div>
    </div>
  </div>
</template>
<style>
.slidev-layout.workflow { gap: 12px; }
.slidev-layout.workflow .col { display: flex; flex-direction: column; gap: 8px; align-items: flex-start; }
.slidev-layout.workflow .slidev-mermaid, .slidev-layout.workflow .mermaid { width: 100%; align-self: stretch; display: flex; justify-content: center; }
.slidev-layout.workflow .slidev-mermaid svg, .slidev-layout.workflow .mermaid svg { width: 100% !important; height: auto; max-height: 230px; }
.slidev-layout.workflow li { font-size: 22px; }
</style>
