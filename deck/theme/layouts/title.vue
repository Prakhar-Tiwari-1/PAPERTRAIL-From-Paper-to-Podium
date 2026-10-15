<script setup lang="ts">
import footer from '../footer.json'

const course = [footer.course_code, footer.course_name].filter(Boolean).join(footer.separator ?? ' - ')
const names = (footer.presenters || []).join('   ·   ')
const when = [course, footer.date].filter(Boolean).join('   ·   ')
const photo = footer.title_background ? { backgroundImage: 'url(/title-bg.jpg)' } : {}
const shade = { background: `rgba(0, 0, 0, ${footer.title_shade ?? 0.6})` }
</script>

<template>
  <div class="slidev-layout title" :style="photo">
    <div class="title-shade" :style="shade"></div>
    <div class="title-content">
      <div v-if="footer.title_logo || footer.event_label" class="title-top">
        <span v-if="footer.title_logo && footer.logo" class="title-chip"><img data-chrome src="/footer-logo.png" alt="" /></span>
        <span v-if="footer.event_label" class="title-tag">{{ footer.event_label }}</span>
      </div>
      <div class="title-body"><slot /></div>
      <div v-if="footer.paper_citation" class="title-cite">{{ footer.paper_citation }}</div>
      <div class="title-meta">
        <div v-if="names" class="title-names">{{ names }}</div>
        <div class="title-course">{{ when }}</div>
      </div>
      <div v-if="footer.image_credit" class="title-credit">{{ footer.image_credit }}</div>
    </div>
  </div>
</template>

<style>
.slidev-layout.title { position: relative; background-color: var(--primary); background-size: cover; background-position: center; color: #FFFFFF; padding: 0; }
.slidev-layout.title .title-shade { position: absolute; inset: 0; }
.slidev-layout.title .title-content { position: relative; height: 100%; box-sizing: border-box; padding: 48px 64px 40px 64px; display: flex; flex-direction: column; gap: 22px; }
.slidev-layout.title .title-top { display: flex; align-items: center; gap: 18px; }
.slidev-layout.title .title-chip { background: #FFFFFF; border-radius: 6px; padding: 6px 12px; display: inline-flex; }
.slidev-layout.title .title-chip img { height: 40px; width: auto; }
.slidev-layout.title .title-tag { font-size: 20px; letter-spacing: 0.14em; text-transform: uppercase; color: #F2B8A5; font-weight: 600; }
.slidev-layout.title .title-body { margin-top: auto; }
.slidev-layout.title h1 { font-size: 56px; line-height: 1.12; color: #FFFFFF; }
.slidev-layout.title .title-body p { font-size: 30px; color: #E4EDF3; margin-top: 4px; max-width: 980px; }
.slidev-layout.title .title-cite { font-size: 22px; color: #F2B8A5; }
.slidev-layout.title .title-meta { display: flex; flex-direction: column; gap: 6px; margin-top: 6px; }
.slidev-layout.title .title-names { font-size: 30px; font-weight: 700; color: #FFFFFF; }
.slidev-layout.title .title-course { font-size: 22px; color: #D6E4EE; }
.slidev-layout.title .title-credit { font-size: 14px; color: #B9C7D2; margin-top: 4px; }
</style>
