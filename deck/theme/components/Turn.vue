<script setup lang="ts">
defineProps<{ who: 'user' | 'assistant' }>()
</script>
<template>
  <div class="turn" :class="who"
       style="max-width:78%;padding:12px 20px;border-radius:8px;font-size:22px;line-height:1.3"
       :style="who === 'user' ? 'align-self:flex-start;background:#FCF1D6;border:1px solid #E69F00' : 'align-self:flex-end;background:#E8F0F6;border:1px solid #0072B2'">
    <div style="font-size:16px;font-weight:600;color:#063A59;margin-bottom:4px">{{ who === 'user' ? 'User' : 'Assistant' }}</div>
    <slot />
  </div>
</template>
