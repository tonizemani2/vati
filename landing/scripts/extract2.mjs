import { chromium } from '/Users/emizemani/Desktop/predictthefuture/site/node_modules/playwright/index.mjs';
import { writeFileSync } from 'node:fs';

const URL = 'https://www.inceptionlabs.ai';
const OUT = '/Users/emizemani/Desktop/predictthefuture/landing/docs';
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
const page = await ctx.newPage();
await page.goto(URL, { waitUntil: 'networkidle', timeout: 60000 });
await page.waitForTimeout(2500);

const total = await page.evaluate(() => document.body.scrollHeight);
// Viewport segment screenshots top->bottom
let y = 0, i = 0;
while (y < total) {
  await page.evaluate((sy) => window.scrollTo(0, sy), y);
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/design-references/orig-seg-${String(i).padStart(2,'0')}.png` });
  y += 900; i++;
  if (i > 16) break;
}
await page.evaluate(() => window.scrollTo(0, 0));
await page.waitForTimeout(400);

// For each section heading, walk up to find the section wrapper and extract its box + the heading style
const probe = (texts) => {
  const grab = (el) => { const cs = getComputedStyle(el); const r = el.getBoundingClientRect(); return {
    tag: el.tagName.toLowerCase(), cls: (el.className?.toString()||'').slice(0,80),
    w: Math.round(r.width), bg: cs.backgroundColor, color: cs.color,
    padT: cs.paddingTop, padB: cs.paddingBottom, padL: cs.paddingLeft, padR: cs.paddingRight,
    fontFamily: cs.fontFamily, fontSize: cs.fontSize, fontWeight: cs.fontWeight,
    lineHeight: cs.lineHeight, letterSpacing: cs.letterSpacing, borderRadius: cs.borderRadius,
    maxWidth: cs.maxWidth, display: cs.display, gap: cs.gap, border: cs.border,
  }; };
  const out = {};
  for (const t of texts) {
    const h = [...document.querySelectorAll('h1,h2,h3')].find(e => e.textContent.trim().toLowerCase().includes(t.toLowerCase()));
    if (!h) { out[t] = null; continue; }
    // climb to a wrapper that spans most of the width (the section)
    let sec = h; for (let k=0;k<8;k++){ if(sec.parentElement){ const pr=sec.parentElement.getBoundingClientRect(); sec=sec.parentElement; if(pr.width>1200) break; } }
    out[t] = { heading: grab(h), section: grab(sec) };
  }
  return out;
};
const sections = await page.evaluate(probe, [
  'new frontier', 'diffusion difference', 'Blazing', 'Build the future',
  'family of diffusion', 'visionary', 'Loved by', 'Enterprise', 'future of LLMs',
]);
writeFileSync(`${OUT}/research/sections.json`, JSON.stringify(sections, null, 2));

// Button + eyebrow + chip styles
const ui = await page.evaluate(() => {
  const grab = (el) => { if(!el) return null; const cs=getComputedStyle(el); return {
    text: el.textContent.trim().slice(0,30), bg: cs.backgroundColor, color: cs.color,
    border: cs.border, borderRadius: cs.borderRadius, padding: cs.padding,
    fontSize: cs.fontSize, fontWeight: cs.fontWeight, fontFamily: cs.fontFamily,
    letterSpacing: cs.letterSpacing, textTransform: cs.textTransform, boxShadow: cs.boxShadow }; };
  const btns = [...document.querySelectorAll('a,button')].filter(b=>b.textContent.trim().length>2 && b.textContent.trim().length<24).slice(0,8);
  return { buttons: btns.map(grab) };
});
writeFileSync(`${OUT}/research/ui.json`, JSON.stringify(ui, null, 2));

await browser.close();
console.log('EXTRACT2 DONE segs='+i);
