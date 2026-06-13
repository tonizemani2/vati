// Per-section element screenshots for visual reference.
import { chromium } from 'playwright';
const URL = 'https://www.mantic.com';
const REF = 'docs/design-references';

const SECTIONS = [
  ['nav', '.nav_component'],
  ['hero', '.hero_wrap'],
  ['sampleqs', '.sampleqs_wrap'],
  ['research', '.research_wrap'],
  ['solutions', '.solutions_wrap'],
  ['usecases', '.use_cases_wrap'],
  ['product', '.product_wrap'],
  ['about', '.about_header_wrap'],
  ['mission', '.about_2col_wrap'],
  ['team', '.team_wrap'],
  ['footer', '.footer_wrap'],
];

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
const page = await ctx.newPage();
await page.goto(URL, { waitUntil: 'networkidle', timeout: 60000 });
await page.waitForTimeout(1500);
// settle lazy content
await page.evaluate(async () => { await new Promise(r => { let y=0; const t=setInterval(()=>{ window.scrollBy(0,800); y+=800; if(y>document.body.scrollHeight){clearInterval(t);r();} }, 60); }); window.scrollTo(0,0); });
await page.waitForTimeout(1200);

for (const [name, sel] of SECTIONS) {
  const loc = page.locator(sel).first();
  try {
    await loc.scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);
    await loc.screenshot({ path: `${REF}/sec-${name}.png` });
    console.log('shot', name);
  } catch (e) { console.error('skip', name, e.message); }
}

// Mobile full-page slices for key sections
const mctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
const mp = await mctx.newPage();
await mp.goto(URL, { waitUntil: 'networkidle', timeout: 60000 });
await mp.waitForTimeout(1200);
for (const [name, sel] of [['hero','.hero_wrap'],['sampleqs','.sampleqs_wrap'],['solutions','.solutions_wrap'],['team','.team_wrap'],['footer','.footer_wrap']]) {
  const loc = mp.locator(sel).first();
  try { await loc.scrollIntoViewIfNeeded(); await mp.waitForTimeout(400); await loc.screenshot({ path: `${REF}/m-${name}.png` }); console.log('mobile', name); }
  catch (e) { console.error('mskip', name, e.message); }
}

await browser.close();
console.log('done');
