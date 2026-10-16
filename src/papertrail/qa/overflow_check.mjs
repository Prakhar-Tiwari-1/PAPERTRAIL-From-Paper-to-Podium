// overflow_check: automatic checks of SPEC §7.7 step 2, measured at the 1280x720 canvas.
// Runs INSIDE the page (self-contained). cfg = {slideNo, banned: {phrases, titles, emoji_regex}, safe: 64}.
// Returns [{rule, severity, detail}]. These are computed facts; they go to the author, NOT to the vision critic.
export function runChecks(cfg) {
  const issues = []
  const add = (rule, severity, detail) => issues.push({ rule, severity, detail })
  const page = document.querySelector(`.slidev-page[data-slidev-no="${cfg.slideNo}"]`) || document
  const root = page.querySelector('.slidev-layout')
  if (!root) return [{ rule: 'render', severity: 'high', detail: 'slide did not render' }]
  const rr = root.getBoundingClientRect()
  const W = rr.width, H = rr.height, S = cfg.safe
  const TOL = 2

  const lum = (r, g, b) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) }
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
  }
  const rgb = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(',').map(parseFloat); return p.slice(0, 3) }
  const bgOf = (el) => {
    for (let e = el; e; e = e.parentElement) {
      const m = getComputedStyle(e).backgroundColor.match(/rgba?\(([^)]+)\)/)
      if (m) { const p = m[1].split(',').map(parseFloat); if (p.length < 4 || p[3] > 0.5) return p.slice(0, 3) }
    }
    return [250, 250, 247]
  }

  // overflow: content taller/wider than the slide, or any element clipped by its own box
  if (root.scrollHeight > root.clientHeight + TOL) add('overflow', 'high', `slide content is ${root.scrollHeight}px tall in a ${root.clientHeight}px slide`)
  if (root.scrollWidth > root.clientWidth + TOL) add('overflow', 'high', `slide content is ${root.scrollWidth}px wide in a ${root.clientWidth}px slide`)
  for (const el of root.querySelectorAll('*')) {
    const cs = getComputedStyle(el)
    if ((cs.overflow === 'hidden' || cs.overflowY === 'hidden') && el.scrollHeight > el.clientHeight + TOL && el.clientHeight > 0) {
      add('overflow', 'high', `<${el.tagName.toLowerCase()}> clips its content (${el.scrollHeight}px in ${el.clientHeight}px)`)
    }
  }

  const textEls = Array.from(root.querySelectorAll('h1,h2,h3,p,li,.turn,.caption,pre,td,th')).filter((e) => (e.innerText || '').trim())
  // font below 16 px
  for (const el of textEls) {
    const fs = parseFloat(getComputedStyle(el).fontSize)
    if (fs < 16 - 0.01) add('font_below_16px', 'high', `"${el.innerText.trim().slice(0, 40)}" is ${fs}px`)
  }
  // outside the 64 px safe area (visible elements only)
  for (const el of root.querySelectorAll('h1,h2,p,li,img,svg,pre,table,.mermaid,.turn,.caption')) {
    if (el.closest('[data-chrome]')) continue   // branding, not slide content
    const r = el.getBoundingClientRect()
    if (r.width < 2 || r.height < 2) continue
    const x0 = r.left - rr.left, y0 = r.top - rr.top, x1 = r.right - rr.left, y1 = r.bottom - rr.top
    if (x0 < S - TOL || y0 < S - TOL || x1 > W - S + TOL || y1 > H - S + TOL) {
      add('outside_safe_area', 'high', `<${el.tagName.toLowerCase()}> "${(el.innerText || el.getAttribute('src') || '').trim().slice(0, 30)}" spans ${Math.round(x0)},${Math.round(y0)}-${Math.round(x1)},${Math.round(y1)}`)
    }
  }
  // words / bullets
  const caption = Array.from(root.querySelectorAll('.caption')).map((e) => e.innerText).join(' ')
  const words = (root.innerText.replace(caption, '').match(/\S+/g) || []).length
  const limit = root.classList.contains('claim-quiz') ? 300 : root.classList.contains('workflow') ? 90 : 70   // quiz: 7-8 questions plus answers
  if (words > limit) add('too_many_words', 'high', `${words} words (limit ${limit}${limit === 70 ? ', aim for 50-70' : ''})`)
  const bullets = root.querySelectorAll('li').length
  if (bullets > 4) add('too_many_bullets', 'high', `${bullets} bullets (limit 4)`)
  for (const li of root.querySelectorAll('li')) {
    const n = (li.innerText.match(/\S+/g) || []).length
    if (n > 12) add('long_bullet', 'low', `bullet has ${n} words (limit 12): "${li.innerText.trim().slice(0, 40)}"`)
  }
  // image scaled above 1.5x its native size (raster only)
  for (const img of root.querySelectorAll('img')) {
    if (/\.svg(\?|$)/i.test(img.getAttribute('src') || '')) continue
    if (img.naturalWidth > 0 && img.getBoundingClientRect().width / img.naturalWidth > 1.5) {
      add('image_upscaled', 'low', `image shown at ${(img.getBoundingClientRect().width / img.naturalWidth).toFixed(2)}x native size`)
    }
  }
  // figure without a source caption
  const hasFigure = root.querySelector('img:not([data-chrome]), .mermaid, .slidev-mermaid, svg.figure')
  if (hasFigure && !root.querySelector('.caption')) add('figure_without_source_caption', 'high', 'figure or diagram has no <SourceCaption>')
  // WCAG 2.1 contrast: 4.5:1 body, 3:1 for text >= 24 px
  for (const el of textEls) {
    const cs = getComputedStyle(el)
    const fg = rgb(cs.color); if (!fg) continue
    const bg = bgOf(el)
    const L1 = lum(...fg), L2 = lum(...bg)
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05)
    const need = parseFloat(cs.fontSize) >= 24 ? 3 : 4.5
    if (ratio < need) add('contrast', 'high', `"${el.innerText.trim().slice(0, 30)}" has ${ratio.toFixed(2)}:1 (needs ${need}:1)`)
  }
  // banned patterns (regex list shared with the slide-design skill)
  const allText = root.innerText.toLowerCase()
  for (const ph of cfg.banned.phrases) if (allText.includes(ph.toLowerCase())) add('banned_phrase', 'high', `contains "${ph}"`)
  const h1 = root.querySelector('h1')
  if (h1) {
    const t = h1.innerText.trim().toLowerCase().replace(/[.:]$/, '')
    if (cfg.banned.titles.includes(t) && !root.classList.contains('title')) add('banned_title', 'high', `title "${h1.innerText.trim()}"`)
    if (h1.innerText.trim().endsWith('?')) add('rhetorical_question_title', 'high', `title "${h1.innerText.trim()}"`)
  }
  if (new RegExp(cfg.banned.emoji_regex, 'u').test(root.innerText)) add('emoji', 'high', 'slide contains an emoji')
  for (const el of root.querySelectorAll('*')) {
    const cs = getComputedStyle(el)
    if (cs.backgroundImage.includes('gradient')) { add('gradient', 'high', `<${el.tagName.toLowerCase()}> uses a gradient`); break }
  }
  for (const el of root.querySelectorAll('*')) {
    const cs = getComputedStyle(el)
    if ((cs.boxShadow && cs.boxShadow !== 'none') || (cs.textShadow && cs.textShadow !== 'none')) { add('shadow', 'high', `<${el.tagName.toLowerCase()}> has a shadow`); break }
  }
  // bold scattered through sentences
  const inlineBold = Array.from(root.querySelectorAll('p strong, li strong, p b, li b')).length
  if (inlineBold > 2) add('scattered_bold', 'low', `${inlineBold} bold spans inside sentences`)
  return issues
}
