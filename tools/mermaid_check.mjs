// mermaid_check.mjs: parse Mermaid sources in a headless browser (mermaid from deck/node_modules) and report errors.
// Usage: node tools/mermaid_check.mjs --deck <dir with node_modules> --in <json file: ["src", ...]>  -> prints [{ok, error}]
import { createRequire } from 'module'
import fs from 'fs'
import path from 'path'

const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? [...a, [v.slice(2), arr[i + 1]]] : a), []))
const deck = path.resolve(args.deck)
const require = createRequire(path.join(deck, 'package.json'))
const { chromium } = require('playwright-chromium')
const sources = JSON.parse(fs.readFileSync(args.in, 'utf8'))
const lib = fs.readFileSync(require.resolve('mermaid/dist/mermaid.min.js'), 'utf8')

const browser = await chromium.launch()
const page = await browser.newPage()
await page.setContent('<html><body></body></html>')
await page.addScriptTag({ content: lib })
const results = await page.evaluate(async (srcs) => {
  window.mermaid.initialize({ startOnLoad: false })
  const out = []
  for (const s of srcs) {
    try { await window.mermaid.parse(s); out.push({ ok: true, error: '' }) }
    catch (e) { out.push({ ok: false, error: String(e && e.message ? e.message : e).slice(0, 400) }) }
  }
  return out
}, sources)
await browser.close()
console.log(JSON.stringify(results))
