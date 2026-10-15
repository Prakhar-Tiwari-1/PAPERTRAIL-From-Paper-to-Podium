<script setup lang="ts">
import { computed } from 'vue'
import { useNav } from '@slidev/client'
import footer from './footer.json'

const { currentPage, currentLayout } = useNav()

// watermark position is the same on every slide: set once as a CSS variable (see styles/index.css)
const WM = { right: 'right 40px bottom 80px', center: 'center 52%' } as Record<string, string>
if (typeof document !== 'undefined') document.documentElement.style.setProperty('--wm-pos', WM[footer.watermark_position as string] ?? WM.right)
const hidden = computed(() => !footer.enabled || (footer.hide_on_layouts || []).includes(currentLayout.value))
const label = computed(() => [footer.course_code, footer.course_name].filter(Boolean).join(footer.separator ?? ' - '))
</script>

<template>
  <div v-if="!hidden" class="pt-footer">
    <img v-if="footer.logo" class="pt-logo" src="/footer-logo.png" alt="" />
    <span class="pt-course">{{ label }}</span>
    <span v-if="footer.show_page_number" class="pt-page">{{ currentPage }}</span>
  </div>
</template>
