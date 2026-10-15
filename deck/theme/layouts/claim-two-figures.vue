<template>
  <div class="slidev-layout claim-two-figures">
    <slot />
    <div class="cols">
      <div class="col"><slot name="left" /></div>
      <div class="col"><slot name="right" /></div>
    </div>
  </div>
</template>
<style>
.slidev-layout.claim-two-figures .col { display: flex; flex-direction: column; gap: 8px; align-items: flex-start; }
.slidev-layout.claim-two-figures .col img { max-height: 380px; }
</style>
