import { chromium } from 'playwright';
import { writeFileSync } from 'fs';
const b = await chromium.launch();
const ctx = await b.newContext({ viewport:{width:1440,height:900}, deviceScaleFactor:1 });
const p = await ctx.newPage();
await p.goto('https://www.mantic.com',{waitUntil:'domcontentloaded',timeout:60000});
// give webflow.js time to set INITIAL states, but DO NOT scroll yet
await p.waitForTimeout(2500);

// build a stable unique selector for an element (nth-of-type path, capped depth)
const PATHFN = `function pathOf(el){
  if(!el || el===document.body) return 'body';
  const parts=[];
  let node=el, depth=0;
  while(node && node!==document.body && depth<6){
    const tag=node.tagName.toLowerCase();
    const parent=node.parentElement;
    if(!parent){ parts.unshift(tag); break; }
    const sibs=[...parent.children].filter(c=>c.tagName===node.tagName);
    const idx=sibs.indexOf(node)+1;
    const cls=(node.className&&node.className.toString().trim().split(/\\s+/)[0])||'';
    parts.unshift(tag + (cls?'.'+CSS.escape(cls):'') + ':nth-of-type('+idx+')');
    node=parent; depth++;
  }
  return parts.join(' > ');
}`;

const capture = (label) => p.evaluate(({label, PATHFN})=>{
  eval(PATHFN);
  const out={};
  document.querySelectorAll('main *').forEach(el=>{
    const cs=getComputedStyle(el);
    const op=parseFloat(cs.opacity);
    const tf=cs.transform;
    // candidates: partially/fully transparent OR transformed, and rendered
    if((op<0.99 || (tf && tf!=='none')) && cs.display!=='none' && cs.visibility!=='hidden'){
      const key=pathOf(el);
      out[key]={op:+op.toFixed(2), tf, tag:el.tagName.toLowerCase(),
        cls:(el.className||'').toString().slice(0,50),
        sect:(el.closest('section')?.className||'').toString().split(/\s+/)[0]||'',
        wid: el.getAttribute('data-w-id')||null,
        top: Math.round(el.getBoundingClientRect().top + window.scrollY)};
    }
  });
  return out;
},{label,PATHFN});

const initial = await capture('initial');
// now reveal everything
await p.evaluate(async ()=>{ await new Promise(r=>{let y=0;const t=setInterval(()=>{window.scrollBy(0,500);y+=500;if(y>document.body.scrollHeight){clearInterval(t);r();}},60);}); window.scrollTo(0,0); });
await p.waitForTimeout(1500);
const finalAll = await p.evaluate(({PATHFN})=>{ eval(PATHFN);
  const out={}; document.querySelectorAll('main *').forEach(el=>{ const cs=getComputedStyle(el);
    out[pathOf(el)]={op:+parseFloat(cs.opacity).toFixed(2), tf:cs.transform}; }); return out; },{PATHFN});

// reveals = initial hidden/transformed but final visible+untransformed
const reveals={};
for(const [k,v] of Object.entries(initial)){
  const f=finalAll[k];
  if(!f) continue;
  const becameVisible = v.op<0.99 && f.op>=0.99;
  const untransformed = v.tf!=='none' && (f.tf==='none' || f.tf==='matrix(1, 0, 0, 1, 0, 0)');
  if(becameVisible || untransformed){ reveals[k]={...v, finalOp:f.op, finalTf:f.tf}; }
}
writeFileSync('docs/research/reveals.json', JSON.stringify(reveals,null,1));
console.log('candidates(initial hidden/transformed):', Object.keys(initial).length);
console.log('REVEAL elements (hidden->shown):', Object.keys(reveals).length);
// summarize by section + initial transform variant
const bySect={}, byTf={};
for(const v of Object.values(reveals)){ bySect[v.sect]=(bySect[v.sect]||0)+1; byTf[v.tf]=(byTf[v.tf]||0)+1; }
console.log('by section:', JSON.stringify(bySect));
console.log('initial transform variants:', JSON.stringify(byTf,null,1));
await b.close();
