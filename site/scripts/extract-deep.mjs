// Deep extraction: rendered HTML, @font-face URLs, resolved CSS custom props (swatches)
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';

const URL = 'https://www.mantic.com';
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
const page = await ctx.newPage();
await page.goto(URL, { waitUntil: 'networkidle', timeout: 60000 });
await page.waitForTimeout(2000);

// 1. Full rendered HTML
const html = await page.content();
writeFileSync('docs/research/page.html', html);

// 2. @font-face rules + resolved root custom properties
const out = await page.evaluate(() => {
  const fontFaces = [];
  for (const sheet of document.styleSheets) {
    let rules;
    try { rules = sheet.cssRules; } catch { continue; }
    if (!rules) continue;
    for (const r of rules) {
      if (r.constructor.name === 'CSSFontFaceRule' || r.type === 5) {
        fontFaces.push({
          family: r.style.getPropertyValue('font-family'),
          weight: r.style.getPropertyValue('font-weight'),
          style: r.style.getPropertyValue('font-style'),
          src: r.style.getPropertyValue('src'),
        });
      }
    }
  }
  // resolve all --swatch / --color / theme custom props on :root
  const rootCS = getComputedStyle(document.documentElement);
  const vars = {};
  for (let i = 0; i < rootCS.length; i++) {
    const p = rootCS[i];
    if (p.startsWith('--')) {
      const v = rootCS.getPropertyValue(p).trim();
      if (/swatch|color|theme|brand|dark|light/i.test(p) && /rgb|#|hsl/.test(v)) vars[p] = v;
    }
  }
  // also grab resolved theme values on a few key sections
  const probe = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const cs = getComputedStyle(el);
    return { bg: cs.backgroundColor, color: cs.color, font: cs.fontFamily };
  };
  return {
    fontFaces,
    swatches: vars,
    themes: {
      body: probe('body'),
      hero: probe('.hero_wrap'),
      sampleqs: probe('.sampleqs_wrap'),
      research: probe('.research_wrap'),
      solutions: probe('.solutions_wrap'),
      usecases: probe('.use_cases_wrap'),
      product: probe('.product_wrap'),
      about: probe('.about_header_wrap'),
      team: probe('.team_wrap'),
      footer: probe('.footer_wrap'),
      nav: probe('.nav_component'),
    },
  };
});
writeFileSync('docs/research/fonts-and-tokens.json', JSON.stringify(out, null, 2));
await browser.close();
console.log('FONT FACES:', out.fontFaces.length);
out.fontFaces.forEach(f => console.log(' -', f.family, f.weight, f.style, '|', f.src.slice(0, 90)));
console.log('\nSWATCHES:', JSON.stringify(out.swatches, null, 1));
console.log('\nTHEMES:', JSON.stringify(out.themes, null, 1));
console.log('\nSaved page.html (', html.length, 'chars ) + fonts-and-tokens.json');
