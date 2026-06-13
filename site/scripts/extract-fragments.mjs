// Extract per-section outerHTML fragments + modal HTML, and screenshot opened modals.
import { chromium } from 'playwright';
import { writeFileSync, mkdirSync, readFileSync } from 'fs';
mkdirSync('docs/research/fragments', { recursive: true });
const REF = 'docs/design-references';
const manifest = JSON.parse(readFileSync('docs/research/asset-manifest.json', 'utf8'));

const SECTIONS = {
  nav: '.nav_component',
  hero: '.hero_wrap',
  sampleqs: '.sampleqs_wrap',
  research: '.research_wrap',
  solutions: '.solutions_wrap',
  usecases: '.use_cases_wrap',
  product: '.product_wrap',
  about: '.about_header_wrap',
  mission: '.about_2col_wrap',
  team: '.team_wrap',
  footer: '.footer_wrap',
  contactModal: '#contact-modal',
  sampleqsModal: '#sampleqs-modal',
  videoModal: '.video-modal',
};

// rewrite absolute cdn URLs to local paths using the manifest
function localize(html) {
  for (const [remote, local] of Object.entries(manifest)) {
    html = html.split(remote).join(local);
    // also handle url-encoded variants present in srcset
    html = html.split(encodeURI(remote)).join(local);
  }
  return html;
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
const page = await ctx.newPage();
await page.goto('https://www.mantic.com', { waitUntil: 'networkidle', timeout: 60000 });
await page.evaluate(async () => { await new Promise(r => { let y=0; const t=setInterval(()=>{ window.scrollBy(0,800); y+=800; if(y>document.body.scrollHeight){clearInterval(t);r();} }, 50); }); window.scrollTo(0,0); });
await page.waitForTimeout(1000);

for (const [name, sel] of Object.entries(SECTIONS)) {
  const h = await page.locator(sel).first().evaluate(el => el.outerHTML).catch(() => null);
  if (h) { writeFileSync(`docs/research/fragments/${name}.html`, localize(h)); console.log('frag', name, h.length); }
  else console.error('no frag', name);
}

// Open + screenshot modals
async function snap(name, opener) {
  try {
    await opener();
    await page.waitForTimeout(900);
    await page.screenshot({ path: `${REF}/modal-${name}.png` });
    console.log('modal shot', name);
  } catch (e) { console.error('modal fail', name, e.message); }
}
// sample question card -> plus button opens detail modal
await snap('sampleqs', async () => { await page.locator('.sampleqs-card-button').first().click({ force: true }); });
await page.keyboard.press('Escape').catch(()=>{});
await page.waitForTimeout(400);
// contact modal via "Book a demo"/contact trigger
await snap('contact', async () => { await page.locator('[href="#contact-modal"], .nav_contact, a:has-text("Book")').first().click({ force: true }); });

await browser.close();
console.log('done');
