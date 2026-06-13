import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await (await b.newContext({viewport:{width:1440,height:900}})).newPage();
await p.goto('http://localhost:4317',{waitUntil:'networkidle',timeout:90000});
await p.waitForTimeout(1500);
const r = {};
// 1. sampleqs swiper next arrow
const before = await p.locator('.sampleqs-swiper .swiper-slide-active').first().getAttribute('aria-label').catch(()=>null);
await p.locator('.sampleqs-swiper-arrows .arrow-next').click({force:true}).catch(()=>{});
await p.waitForTimeout(700);
const after = await p.locator('.sampleqs-swiper .swiper-slide-active').first().getAttribute('aria-label').catch(()=>null);
r.swiperAdvanced = before !== after;
// 2. usecase filter tab -> click Finance
await p.locator('.usecase-filter-tab').nth(2).click({force:true}).catch(()=>{});
await p.waitForTimeout(400);
r.usecaseTabActive = await p.locator('.usecase-filter-tab.is-active').nth(0).innerText().catch(()=>null);
// 3. open sample question modal via first card plus button
await p.locator('[data-samplemodal]').first().click({force:true}).catch(()=>{});
await p.waitForTimeout(700);
r.sampleModalVisible = await p.locator('#sampleqs-modal.visible').count();
await p.screenshot({ path:'docs/design-references/final-modal-open.png' });
// close it
await p.locator('.sampleqs-modal-close').first().click({force:true}).catch(()=>{});
await p.waitForTimeout(400);
r.sampleModalClosed = (await p.locator('#sampleqs-modal.visible').count())===0;
// 4. contact modal
await p.locator('[data-contact]').first().click({force:true}).catch(()=>{});
await p.waitForTimeout(500);
r.contactModalVisible = await p.locator('#contact-modal.visible').count();
console.log(JSON.stringify(r,null,1));
await b.close();
