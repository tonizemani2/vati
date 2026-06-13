// Phase 1 reconnaissance: screenshots + global extraction for www.mantic.com
import { chromium } from 'playwright';
import { writeFileSync, mkdirSync } from 'fs';

const URL = process.env.TARGET_URL || 'https://www.mantic.com';
const REF = 'docs/design-references';
const RES = 'docs/research';
mkdirSync(REF, { recursive: true });
mkdirSync(RES, { recursive: true });

const GLOBAL_EXTRACT = () => JSON.stringify({
  title: document.title,
  images: [...document.querySelectorAll('img')].map(img => ({
    src: img.src || img.currentSrc, alt: img.alt,
    width: img.naturalWidth, height: img.naturalHeight,
    parentClasses: img.parentElement?.className?.toString?.().slice(0,120),
    position: getComputedStyle(img).position, zIndex: getComputedStyle(img).zIndex
  })),
  videos: [...document.querySelectorAll('video')].map(v => ({
    src: v.src || v.querySelector('source')?.src, poster: v.poster,
    autoplay: v.autoplay, loop: v.loop, muted: v.muted
  })),
  backgroundImages: [...new Set([...document.querySelectorAll('*')].filter(el => {
    const bg = getComputedStyle(el).backgroundImage; return bg && bg !== 'none';
  }).map(el => getComputedStyle(el).backgroundImage))].slice(0, 60),
  svgCount: document.querySelectorAll('svg').length,
  fontsUsed: [...new Set([...document.querySelectorAll('h1,h2,h3,h4,p,a,span,button,li,div,code,label')]
    .map(el => getComputedStyle(el).fontFamily))].slice(0, 30),
  favicons: [...document.querySelectorAll('link[rel*="icon"],link[rel*="apple-touch"]')]
    .map(l => ({ href: l.href, rel: l.rel, sizes: l.sizes?.toString() })),
  metaOg: [...document.querySelectorAll('meta[property^="og:"],meta[name^="twitter:"]')]
    .map(m => ({ key: m.getAttribute('property') || m.getAttribute('name'), content: m.content })),
  stylesheets: [...document.querySelectorAll('link[rel="stylesheet"]')].map(l => l.href),
  bodyBg: getComputedStyle(document.body).backgroundColor,
  bodyColor: getComputedStyle(document.body).color,
  // top-level section topology
  sections: [...document.body.querySelectorAll('body > *, main > *, body > div > *')]
    .slice(0, 40).map(el => ({
      tag: el.tagName.toLowerCase(),
      classes: el.className?.toString?.().slice(0,100),
      id: el.id,
      h: Math.round(el.getBoundingClientRect().height),
      text: el.textContent?.trim().slice(0, 80)
    })).filter(s => s.h > 20),
  hasLenis: !!document.querySelector('.lenis, [data-lenis]') ||
            !![...document.scripts].find(s => /lenis|locomotive/i.test(s.src)),
});

const browser = await chromium.launch();

async function shoot(width, height, label) {
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  await page.goto(URL, { waitUntil: 'networkidle', timeout: 60000 }).catch(e => console.error('goto warn', e.message));
  await page.waitForTimeout(2500);
  // scroll to trigger lazy content, then back to top
  await page.evaluate(async () => {
    await new Promise(r => { let y=0; const t=setInterval(()=>{ window.scrollBy(0,600); y+=600; if(y>document.body.scrollHeight){clearInterval(t);r();} }, 80); });
    window.scrollTo(0,0);
  });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${REF}/${label}-full.png`, fullPage: true });
  const data = await page.evaluate(GLOBAL_EXTRACT);
  await ctx.close();
  return data;
}

const desktop = await shoot(1440, 900, 'desktop');
writeFileSync(`${RES}/global-extract.json`, desktop);
await shoot(390, 844, 'mobile');

await browser.close();
const g = JSON.parse(desktop);
console.log('TITLE:', g.title);
console.log('imgs:', g.images.length, '| videos:', g.videos.length, '| svgs:', g.svgCount, '| bgImgs:', g.backgroundImages.length);
console.log('fonts:', JSON.stringify(g.fontsUsed));
console.log('bodyBg:', g.bodyBg, '| bodyColor:', g.bodyColor, '| lenis:', g.hasLenis);
console.log('sections:', g.sections.length);
console.log('Saved screenshots + global-extract.json');
