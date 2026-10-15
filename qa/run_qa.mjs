// run_qa.mjs: serve a built Slidev SPA, visit every slide at 1280x720, write per-slide
//   slide-N.png, slide-N.elements.json (element_map) and slide-N.checks.json (overflow_check).
// Usage: node qa/run_qa.mjs --dist <dist> --deck <dir with node_modules> --out <outdir> --n <slides>
import { createRequire } from 'module'
import http from 'http'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'
import { collectElements } from './element_map.mjs'
import { runChecks } from './overflow_check.mjs'
import { slideMetrics } from './metrics.mjs'

const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? [...a, [v.slice(2), arr[i + 1]]] : a), []))
const here = path.dirname(fileURLToPath(import.meta.url))
const require = createRequire(path.join(path.resolve(args.deck), 'package.json'))
const { chromium } = require('playwright-chromium')
const banned = JSON.parse(fs.readFileSync(path.join(here, 'banned.json'), 'utf8'))
const dist = path.resolve(args.dist)
const out = path.resolve(args.out)
const n = parseInt(args.n, 10)
fs.mkdirSync(out, { recursive: true })

const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.json': 'application/json', '.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf' }
const srv = http.createServer((req, res) => {
  const p = decodeURIComponent(req.url.split('?')[0])
  let f = path.join(dist, p === '/' ? 'index.html' : p)
  if (!f.startsWith(dist) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) f = path.join(dist, 'index.html')
  res.setHeader('content-type', types[path.extname(f)] || 'application/octet-stream')
  fs.createReadStream(f).pipe(res)
}).listen(0, '127.0.0.1')
await new Promise((r) => srv.on('listening', r))
const port = srv.address().port

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } })
const summary = []
for (let i = 1; i <= n; i++) {
  await page.goto(`http://127.0.0.1:${port}/#/${i}`)
  await page.waitForSelector(`.slidev-page[data-slidev-no="${i}"] .slidev-layout`, { timeout: 20000 })
  // let diagrams and images settle
  await page.waitForFunction(() => Array.from(document.images).every((im) => im.complete), null, { timeout: 10000 }).catch(() => {})
  if (await page.$(`.slidev-page[data-slidev-no="${i}"] .mermaid`)) {
    await page.waitForSelector(`.slidev-page[data-slidev-no="${i}"] .mermaid svg`, { timeout: 8000 }).catch(() => {})
  }
  // reveal every click-by-click element (the quiz answers): the checks and the critics must see the slide as the PDF shows it
  await page.addStyleTag({ content: '.slidev-vclick-hidden{opacity:1 !important;visibility:visible !important}.slidev-vclick-prior{opacity:1 !important}' })
  await page.waitForTimeout(250)
  const map = await page.evaluate(collectElements, i)
  const checks = await page.evaluate(runChecks, { slideNo: i, banned, safe: 64 })
  const metrics = await page.evaluate(slideMetrics, i)
  fs.writeFileSync(path.join(out, `slide-${i}.metrics.json`), JSON.stringify(metrics))
  await page.screenshot({ path: path.join(out, `slide-${i}.png`) })
  fs.writeFileSync(path.join(out, `slide-${i}.elements.json`), JSON.stringify(map, null, 1))
  fs.writeFileSync(path.join(out, `slide-${i}.checks.json`), JSON.stringify(checks, null, 1))
  summary.push({ slide: i, n_elements: map.elements.length, n_issues: checks.length })
}
await browser.close()
srv.close()
fs.writeFileSync(path.join(out, 'summary.json'), JSON.stringify(summary, null, 1))
console.log(JSON.stringify(summary))
