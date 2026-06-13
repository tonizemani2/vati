// Download all Mantic assets to public/, preserving readable basenames.
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { pipeline } from 'stream/promises';
import { Readable } from 'stream';
import { createWriteStream } from 'fs';

const html = readFileSync('docs/research/page.html', 'utf8');
const tokens = JSON.parse(readFileSync('docs/research/fonts-and-tokens.json', 'utf8'));

mkdirSync('public/images', { recursive: true });
mkdirSync('public/videos', { recursive: true });
mkdirSync('public/fonts', { recursive: true });
mkdirSync('public/seo', { recursive: true });

// 1. Regex every asset-like URL out of the HTML
const urlRe = /https?:\/\/[^\s"'()]+?\.(?:avif|webp|png|jpe?g|svg|gif|mp4|webm|woff2?)/gi;
const found = new Set();
let m;
while ((m = urlRe.exec(html))) found.add(m[0].replace(/\\/g, ''));

// 2. add font + favicon URLs from tokens
tokens.fontFaces.forEach(f => { const u = (f.src.match(/https?:\/\/[^"')]+/) || [])[0]; if (u) found.add(u); });

const ALL = [...found];

function classify(u) {
  const ext = u.split('?')[0].split('.').pop().toLowerCase();
  if (['mp4', 'webm'].includes(ext)) return 'videos';
  if (['woff', 'woff2'].includes(ext)) return 'fonts';
  return 'images';
}
function basename(u) {
  let n = decodeURIComponent(u.split('?')[0].split('/').pop());
  n = n.replace(/[^a-zA-Z0-9._-]/g, '_');
  return n;
}

const manifest = {};
let ok = 0, fail = 0, skip = 0;

async function dl(u) {
  const dir = classify(u);
  const name = basename(u);
  const path = `public/${dir}/${name}`;
  manifest[u] = `/${dir}/${name}`;
  if (existsSync(path)) { skip++; return; }
  try {
    const res = await fetch(u, { headers: { 'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.mantic.com/' } });
    if (!res.ok) { fail++; console.error('FAIL', res.status, u.slice(-50)); return; }
    await pipeline(Readable.fromWeb(res.body), createWriteStream(path));
    ok++;
  } catch (e) { fail++; console.error('ERR', e.message, u.slice(-50)); }
}

// batched concurrency = 5
const batch = 5;
for (let i = 0; i < ALL.length; i += batch) {
  await Promise.all(ALL.slice(i, i + batch).map(dl));
  process.stdout.write(`\r${i + batch}/${ALL.length}`);
}

writeFileSync('docs/research/asset-manifest.json', JSON.stringify(manifest, null, 2));
console.log(`\nDONE. ok=${ok} skip=${skip} fail=${fail} total=${ALL.length}`);
console.log('manifest -> docs/research/asset-manifest.json');
