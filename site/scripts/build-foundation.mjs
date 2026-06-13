// Localize + vendor the Webflow CSS, stage fragments, download remaining assets.
import { readFileSync, writeFileSync, mkdirSync, readdirSync, existsSync, createWriteStream } from 'fs';
import { pipeline } from 'stream/promises';
import { Readable } from 'stream';

mkdirSync('src/styles', { recursive: true });
mkdirSync('src/sections/fragments', { recursive: true });

// 1. download dots.svg (referenced by CSS, not on page)
const dots = 'https://cdn.prod.website-files.com/68907168d294618a86ec6518/68907168d294618a86ec65bf_dots.svg';
if (!existsSync('public/images/68907168d294618a86ec65bf_dots.svg')) {
  const r = await fetch(dots, { headers: { 'User-Agent': 'Mozilla/5.0' } });
  await pipeline(Readable.fromWeb(r.body), createWriteStream('public/images/68907168d294618a86ec65bf_dots.svg'));
  console.log('downloaded dots.svg');
}

// 2. localize the CSS url() refs
let css = readFileSync('docs/research/mantic.webflow.css', 'utf8');
const map = {
  '68907168d294618a86ec65bf_dots.svg': '/images/68907168d294618a86ec65bf_dots.svg',
  '689b29750af0e8f994b5a45e_GT-Standard-Mono-Narrow-Medium.woff2': '/fonts/689b29750af0e8f994b5a45e_GT-Standard-Mono-Narrow-Medium.woff2',
  '689b297557d89256a5697b72_GT-Standard-L-Standard-Regular.woff2': '/fonts/689b297557d89256a5697b72_GT-Standard-L-Standard-Regular.woff2',
  '689b2975a12fc701f9f074a9_GT-Standard-L-Standard-Medium.woff2': '/fonts/689b2975a12fc701f9f074a9_GT-Standard-L-Standard-Medium.woff2',
};
// replace any full cdn url ending in one of these basenames with the local path
css = css.replace(/url\("?https:\/\/cdn\.prod\.website-files\.com\/[^")]*?\/([^"/)]+\.(?:woff2|svg))"?\)/g,
  (full, base) => map[base] ? `url("${map[base]}")` : full);
writeFileSync('src/styles/mantic.webflow.css', css);
console.log('vendored CSS ->', css.length, 'chars; remaining cdn refs:', (css.match(/cdn\.prod\.website-files/g) || []).length);

// 3. stage fragments, stripping <script> tags (keep <style>)
const fragDir = 'docs/research/fragments';
for (const f of readdirSync(fragDir)) {
  if (!f.endsWith('.html')) continue;
  let h = readFileSync(`${fragDir}/${f}`, 'utf8');
  h = h.replace(/<script[\s\S]*?<\/script>/gi, '');
  writeFileSync(`src/sections/fragments/${f}`, h);
}
console.log('staged fragments:', readdirSync('src/sections/fragments').length);
