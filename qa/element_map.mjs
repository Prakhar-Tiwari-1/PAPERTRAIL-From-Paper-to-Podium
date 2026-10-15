// element_map: runs INSIDE the page (self-contained function; serialised by Playwright).
// Emits one record per visible element of the slide: {id, type, bbox (0-1 normalised), font_px, color, bg_color, text_excerpt, tag}.
// `source_line` is added later in Python by matching text_excerpt/src against slides.md (qa/source_map.py).
export function collectElements(slideNo) {
  const page = document.querySelector(`.slidev-page[data-slidev-no="${slideNo}"]`) || document
  const root = page.querySelector('.slidev-layout')
  if (!root) return { error: 'no layout found', elements: [] }
  const rr = root.getBoundingClientRect()
  const SEL = 'h1,h2,h3,p,li,img,svg,pre,table,.mermaid,.slidev-mermaid,.caption,.turn,.big-number'
  const typeOf = (el) => {
    const t = el.tagName.toLowerCase()
    if (el.classList.contains('caption')) return 'caption'
    if (el.classList.contains('mermaid') || el.classList.contains('slidev-mermaid')) return 'diagram'
    if (t === 'svg') return 'diagram'
    if (t === 'img') return 'figure'
    if (t === 'pre') return 'code'
    if (t === 'table') return 'table'
    if (t === 'li') return 'list'
    if (t === 'h1') return 'title'
    return 'text'
  }
  const parse = (c) => {
    const m = c.match(/rgba?\(([^)]+)\)/)
    if (!m) return null
    const p = m[1].split(',').map((x) => parseFloat(x))
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }
  }
  const bgOf = (el) => {
    for (let e = el; e; e = e.parentElement) {
      const c = parse(getComputedStyle(e).backgroundColor)
      if (c && c.a > 0.5) return `rgb(${c.r}, ${c.g}, ${c.b})`
    }
    return 'rgb(250, 250, 247)'
  }
  const all = Array.from(root.querySelectorAll(SEL))
  const taken = []
  const out = []
  for (const el of all) {
    // skip descendants of an already collected container (turn, mermaid, pre, table, svg)
    if (el.closest('[data-chrome]')) continue   // branding (logo chip), not slide content
    if (taken.some((t) => t !== el && t.contains(el))) continue
    const r = el.getBoundingClientRect()
    if (r.width < 2 || r.height < 2) continue
    const cs = getComputedStyle(el)
    if (cs.visibility === 'hidden' || cs.display === 'none') continue
    const type = typeOf(el)
    if (['diagram', 'code', 'table'].includes(type) || el.classList.contains('turn')) taken.push(el)
    const text = (el.innerText || el.textContent || '').trim().replace(/\s+/g, ' ')
    out.push({
      id: out.length + 1,
      type,
      tag: el.tagName.toLowerCase(),
      bbox: [
        +((r.left - rr.left) / rr.width).toFixed(4),
        +((r.top - rr.top) / rr.height).toFixed(4),
        +(r.width / rr.width).toFixed(4),
        +(r.height / rr.height).toFixed(4),
      ],
      font_px: parseFloat(cs.fontSize),
      color: cs.color,
      bg_color: bgOf(el),
      text_excerpt: text.slice(0, 80),
      src: el.getAttribute('src') || '',
    })
  }
  return { error: null, slide_px: [rr.width, rr.height], elements: out }
}
