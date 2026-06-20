// Recon: extract Inception's design system (tokens, layout, type, color, motion).
// Run from site/ so it picks up the installed playwright. Output -> landing/docs/research.
import { chromium } from '/Users/emizemani/Desktop/predictthefuture/site/node_modules/playwright/index.mjs';
import { writeFileSync } from 'node:fs';

const URL = 'https://www.inceptionlabs.ai';
const OUT = '/Users/emizemani/Desktop/predictthefuture/landing/docs';

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
const page = await ctx.newPage();
await page.goto(URL, { waitUntil: 'networkidle', timeout: 60000 });
await page.waitForTimeout(2500);

// 1. Full-page desktop screenshot
await page.screenshot({ path: `${OUT}/design-references/orig-desktop-full.png`, fullPage: true });

// 2. Global design tokens
const tokens = await page.evaluate(() => {
  const root = getComputedStyle(document.documentElement);
  const bodyCS = getComputedStyle(document.body);
  // Collect all CSS custom properties declared on :root
  const vars = {};
  for (const sheet of document.styleSheets) {
    let rules;
    try { rules = sheet.cssRules; } catch { continue; }
    if (!rules) continue;
    for (const rule of rules) {
      if (rule.selectorText && (rule.selectorText === ':root' || rule.selectorText.includes('html'))) {
        for (const prop of rule.style) {
          if (prop.startsWith('--')) vars[prop] = rule.style.getPropertyValue(prop).trim();
        }
      }
    }
  }
  // Sample fonts + colors across many elements
  const fontSet = new Set();
  const colorSet = new Set();
  const bgSet = new Set();
  document.querySelectorAll('h1,h2,h3,h4,p,span,a,button,div,li,code').forEach(el => {
    const cs = getComputedStyle(el);
    fontSet.add(cs.fontFamily);
    if (el.textContent && el.textContent.trim()) colorSet.add(cs.color);
    const bg = cs.backgroundColor;
    if (bg && bg !== 'rgba(0, 0, 0, 0)') bgSet.add(bg);
  });
  // Heading/body type scale
  const sample = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const cs = getComputedStyle(el);
    return { fontFamily: cs.fontFamily, fontSize: cs.fontSize, fontWeight: cs.fontWeight,
      lineHeight: cs.lineHeight, letterSpacing: cs.letterSpacing, color: cs.color, textTransform: cs.textTransform };
  };
  return {
    cssVars: vars,
    bodyBg: bodyCS.backgroundColor,
    bodyColor: bodyCS.color,
    bodyFont: bodyCS.fontFamily,
    fonts: [...fontSet],
    textColors: [...colorSet],
    bgColors: [...bgSet],
    typeScale: { h1: sample('h1'), h2: sample('h2'), h3: sample('h3'), p: sample('p'),
      button: sample('button'), nav: sample('nav a') },
    links: [...document.querySelectorAll('link[rel],style')].slice(0,40).map(l => l.href || '(inline style)'),
  };
});
writeFileSync(`${OUT}/research/tokens.json`, JSON.stringify(tokens, null, 2));

// 3. Section topology: top-level sections with bounding boxes + a label heuristic
const topology = await page.evaluate(() => {
  const main = document.querySelector('main') || document.body;
  const blocks = [...main.children].length > 1 ? [...main.children] : [...document.body.children];
  return blocks.map((el, i) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const heading = el.querySelector('h1,h2,h3');
    return {
      index: i, tag: el.tagName.toLowerCase(),
      classes: el.className?.toString().slice(0, 120),
      top: Math.round(r.top + window.scrollY), height: Math.round(r.height),
      bg: cs.backgroundColor, color: cs.color,
      heading: heading?.textContent?.trim().slice(0, 80) || null,
      childCount: el.children.length,
    };
  }).filter(b => b.height > 40);
});
writeFileSync(`${OUT}/research/topology.json`, JSON.stringify(topology, null, 2));

// 4. Asset inventory
const assets = await page.evaluate(() => ({
  images: [...document.querySelectorAll('img')].map(img => ({
    src: img.currentSrc || img.src, alt: img.alt,
    w: img.naturalWidth, h: img.naturalHeight,
    cls: img.className?.toString().slice(0,60),
  })),
  videos: [...document.querySelectorAll('video')].map(v => ({
    src: v.src || v.querySelector('source')?.src, poster: v.poster,
    autoplay: v.autoplay, loop: v.loop,
  })),
  svgCount: document.querySelectorAll('svg').length,
}));
writeFileSync(`${OUT}/research/assets.json`, JSON.stringify(assets, null, 2));

await browser.close();
console.log('RECON DONE. sections=' + topology.length + ' imgs=' + assets.images.length + ' vars=' + Object.keys(tokens.cssVars).length);
