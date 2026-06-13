import { chromium } from 'playwright';
const PORT = process.env.PORT || '3001';
const label = process.env.LABEL || 'clone';
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
const page = await ctx.newPage();
const errors = [];
page.on('console', m => { if (m.type() === 'error') errors.push(m.text().slice(0, 160)); });
page.on('pageerror', e => errors.push('PAGEERR: ' + e.message.slice(0, 160)));
await page.goto(`http://localhost:${PORT}`, { waitUntil: 'networkidle', timeout: 90000 });
await page.waitForTimeout(2500);
await page.evaluate(async () => { await new Promise(r => { let y=0; const t=setInterval(()=>{ window.scrollBy(0,900); y+=900; if(y>document.body.scrollHeight){clearInterval(t);r();} }, 60); }); window.scrollTo(0,0); });
await page.waitForTimeout(1500);
await page.screenshot({ path: `docs/design-references/${label}-full.png`, fullPage: true });
// section shots
const SECS = [['hero','.hero_wrap'],['sampleqs','.sampleqs_wrap'],['research','.research_wrap'],['solutions','.solutions_wrap'],['usecases','.use_cases_wrap'],['product','.product_wrap'],['about','.about_header_wrap'],['mission','.about_2col_wrap'],['team','.team_wrap'],['footer','.footer_wrap']];
for (const [n,s] of SECS) { try { const l=page.locator(s).first(); await l.scrollIntoViewIfNeeded(); await page.waitForTimeout(300); await l.screenshot({ path:`docs/design-references/${label}-${n}.png` }); } catch(e){ console.error('miss',n,e.message.slice(0,60)); } }
await browser.close();
console.log('CONSOLE ERRORS:', errors.length);
errors.slice(0, 20).forEach(e => console.log('  ', e));
console.log('shots saved with label', label);
