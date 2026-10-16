// slideMetrics: how much of the content area a slide really uses. Runs INSIDE the page (self-contained function).
// Content area = inside the 64 px margins, above the footer (x 64-1216, y 64-640). The area is cut into 16 px cells; a cell counts as used when
// a visible element (text, figure, diagram, table, panel) covers it. `coverage` is used cells / all cells, `bottom` the lowest used y.
export function slideMetrics(slideNo) {
  const page = document.querySelector(`.slidev-page[data-slidev-no="${slideNo}"]`) || document
  const root = page.querySelector('.slidev-layout')
  if (!root) return { error: 'no layout' }
  const rr = root.getBoundingClientRect()
  const X0 = 64, Y0 = 64, X1 = 1216, Y1 = 640, C = 16
  const cols = (X1 - X0) / C, rows = (Y1 - Y0) / C
  const grid = new Uint8Array(cols * rows)
  const SEL = 'h1,h2,p,li,img,svg,pre,table,.mermaid,.slidev-mermaid,.turn,.caption,.big-number,.qa-block,ul,.split-text,.card'
  let bottom = 0, right = 0
  for (const el of root.querySelectorAll(SEL)) {
    if (el.closest('[data-chrome]')) continue
    const r = el.getBoundingClientRect()
    if (r.width < 2 || r.height < 2) continue
    const x0 = Math.max(r.left - rr.left, X0), y0 = Math.max(r.top - rr.top, Y0)
    const x1 = Math.min(r.right - rr.left, X1), y1 = Math.min(r.bottom - rr.top, Y1)
    if (x1 <= x0 || y1 <= y0) continue
    bottom = Math.max(bottom, y1); right = Math.max(right, x1)
    for (let cy = Math.floor((y0 - Y0) / C); cy < Math.ceil((y1 - Y0) / C); cy++)
      for (let cx = Math.floor((x0 - X0) / C); cx < Math.ceil((x1 - X0) / C); cx++) grid[cy * cols + cx] = 1
  }
  let used = 0
  for (const v of grid) used += v
  // empty band: the tallest run of completely unused rows (a big hole below short content shows up here)
  let run = 0, maxRun = 0
  for (let cy = 0; cy < rows; cy++) {
    let any = false
    for (let cx = 0; cx < cols; cx++) if (grid[cy * cols + cx]) { any = true; break }
    run = any ? 0 : run + 1; maxRun = Math.max(maxRun, run)
  }
  return { coverage: +(used / grid.length).toFixed(3), bottom: Math.round(bottom), right: Math.round(right), empty_band_px: maxRun * C }
}
