#!/usr/bin/env python3
"""Publish Pope boards to the vaticinus site as a self-contained /forecasts/ page.

Reads board spec JSONs, emits site/public/forecasts/index.html styled to the
brand (Gt Standard, paper #f3f2f0, ink #343434, brand #3f66fe), and copies the
PDFs alongside for download. Self-contained: does not depend on the Webflow CSS
bundle or the (non-standard) Next routing, so it survives `next build` static
export untouched (public/ is copied verbatim to out/).

Honesty rails (doctrine): these are dated, falsifiable, pre-consensus FORWARD
calls, not a resolved track record. Two probabilities per call. Scored at
resolution. The page says so plainly.

Usage:  python3 -m engine.pope.publish_site
"""
from __future__ import annotations

import html
import json
import os
import shutil

from engine.pope.render import _inline, _pct

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(REPO, "site", "public", "forecasts")

# Publishing config: which boards go live, in order, each with its download PDF.
BOARDS = [
    {"slug": "long-horizon", "spec": "research/pope/long-horizon-2026-06-14.json",
     "pdf_src": "research/long-horizon-theses.pdf", "pdf": "long-horizon.pdf"},
    {"slug": "space", "spec": "research/pope/space-2026-06-14.json",
     "pdf_src": "research/pope/space-2026-06-14.pdf", "pdf": "space.pdf"},
    {"slug": "chips", "spec": "research/pope/chips-2026-06-14.json",
     "pdf_src": "research/pope/chips-2026-06-14.pdf", "pdf": "chips.pdf"},
]

FONT_CSS = """
@font-face{font-family:'Gt Standard';font-weight:400;font-style:normal;font-display:swap;src:url('https://cdn.prod.website-files.com/68907168d294618a86ec6518/689b297557d89256a5697b72_GT-Standard-L-Standard-Regular.woff2') format('woff2');}
@font-face{font-family:'Gt Standard';font-weight:500;font-style:normal;font-display:swap;src:url('https://cdn.prod.website-files.com/68907168d294618a86ec6518/689b2975a12fc701f9f074a9_GT-Standard-L-Standard-Medium.woff2') format('woff2');}
@font-face{font-family:'Gt Standard Mono';font-weight:500;font-style:normal;font-display:swap;src:url('https://cdn.prod.website-files.com/68907168d294618a86ec6518/689b29750af0e8f994b5a45e_GT-Standard-Mono-Narrow-Medium.woff2') format('woff2');}
"""

CSS = FONT_CSS + """
:root{--paper:#f3f2f0;--ink:#343434;--dark:#202020;--brand:#3f66fe;--brand-100:#eaeffdf2;--line:rgba(32,32,32,.12);--mut:#6c6c6c;}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;}
body{background:var(--paper);color:var(--ink);font-family:'Gt Standard',Arial,sans-serif;font-weight:400;line-height:1.55;-webkit-font-smoothing:antialiased;}
.mono{font-family:'Gt Standard Mono','Gt Standard',monospace;}
a{color:var(--brand);text-decoration:none;}
a:hover{text-decoration:underline;}
.wrap{max-width:1080px;margin:0 auto;padding:0 24px;}

/* masthead */
.mast{background:#000;color:var(--paper);padding:38px 0 44px;}
.mast .kick{font-family:'Gt Standard Mono',monospace;font-weight:500;text-transform:uppercase;letter-spacing:.18em;font-size:12px;color:#9b9b9b;}
.mast h1{font-weight:500;font-size:clamp(30px,5vw,52px);line-height:1.04;letter-spacing:-.01em;margin:14px 0 10px;}
.mast p{font-size:18px;color:#d6d5d2;max-width:40em;margin:0;}
.mast .top{display:flex;justify-content:space-between;align-items:center;margin-bottom:26px;}
.mast .top a{color:var(--paper);font-weight:500;}
.mast .brandmark{font-weight:500;letter-spacing:.02em;}

/* method note */
.method{background:#fff;border-bottom:1px solid var(--line);padding:30px 0;}
.method h2{font-weight:500;font-size:15px;text-transform:uppercase;letter-spacing:.1em;color:var(--brand);margin:0 0 12px;}
.method .grid{display:grid;grid-template-columns:1.4fr 1fr;gap:28px;}
.method p{margin:0 0 10px;font-size:15px;}
.legend{border:1px solid var(--line);border-radius:10px;padding:16px 18px;background:var(--paper);}
.legend .row{display:flex;gap:10px;align-items:baseline;margin:8px 0;font-size:14px;}
.legend .pill{flex:0 0 auto;}

/* prob pills */
.pill{display:inline-block;font-family:'Gt Standard Mono',monospace;font-weight:500;font-size:13px;padding:3px 9px;border-radius:999px;border:1px solid var(--line);}
.pill.v{background:#edf3ec;border-color:#cfe0c8;color:#2f5a2a;}
.pill.c{background:#eaeffd;border-color:#cdd9fb;color:#2b3f9b;}
.pill.d{background:#faf6ee;border-color:#e7dcc4;color:#7a611f;}

/* board */
.board{padding:46px 0;border-bottom:1px solid var(--line);}
.board .eyebrow{font-family:'Gt Standard Mono',monospace;font-weight:500;text-transform:uppercase;letter-spacing:.16em;font-size:12px;color:var(--brand);}
.board h2{font-weight:500;font-size:clamp(22px,3vw,30px);line-height:1.12;margin:8px 0 6px;letter-spacing:-.01em;}
.board .sub{font-style:italic;color:var(--mut);font-size:16px;margin:0 0 14px;max-width:52em;}
.board .syn{font-size:15px;max-width:58em;margin:0 0 8px;}
.board .dl{font-family:'Gt Standard Mono',monospace;font-size:13px;margin:10px 0 26px;}
.cards{display:grid;grid-template-columns:repeat(2,1fr);gap:18px;}
@media(max-width:760px){.cards{grid-template-columns:1fr;}.method .grid{grid-template-columns:1fr;}}

.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px 20px;}
.card .chead{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;}
.card .id{font-family:'Gt Standard Mono',monospace;font-weight:500;font-size:12px;color:#fff;background:var(--brand);padding:2px 8px;border-radius:5px;letter-spacing:.08em;}
.card h3{font-weight:500;font-size:16px;line-height:1.3;margin:6px 0 8px;}
.card .boom{font-size:14px;color:var(--mut);margin:0 0 12px;}
.card .pills{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;}
.card .f{margin:9px 0;font-size:13.5px;}
.card .f .k{display:block;font-family:'Gt Standard Mono',monospace;text-transform:uppercase;letter-spacing:.08em;font-size:10.5px;color:var(--brand);margin-bottom:1px;}
.card details{margin-top:12px;border-top:1px solid var(--line);padding-top:10px;}
.card summary{cursor:pointer;font-family:'Gt Standard Mono',monospace;font-size:12px;color:var(--mut);}
.card details .f .k{color:var(--mut);}

footer{padding:40px 0 60px;color:var(--mut);font-size:13px;}
footer .disc{max-width:60em;margin:0 0 14px;}
"""


def _field(label, text, mono=False):
    if not text:
        return ""
    return f'<div class="f"><span class="k">{html.escape(label)}</span>{_inline(text)}</div>'


def _card(t):
    fields = "".join([
        _field("Binding constraint (the needle)", t.get("needle", "")),
        _field("Leading metric", t.get("metric", "")),
        _field("Kill-criterion", t.get("kill", "")),
    ])
    deep = "".join([
        _field("Structural mechanism", t.get("structural", "")),
        _field("Why pre-consensus", t.get("pre_consensus", "")),
        _field("Price channel", t.get("price_channel", "")),
        _field("Refute check (survived)", t.get("refute", "")),
        _field("Why this call", t.get("why", "")),
    ])
    details = (f'<details><summary>Full argument</summary>{deep}</details>' if deep else "")
    return f"""<article class="card">
  <div class="chead"><span class="id">{_inline(t.get('id',''))}</span>
    <span class="pill d mono">resolves {_inline(t.get('resolves',''))}</span></div>
  <h3>{_inline(t.get('headline',''))}</h3>
  <p class="boom">{_inline(t.get('boom',''))}</p>
  <div class="pills">
    <span class="pill v">vision {_pct(t.get('vision_p'))}</span>
    <span class="pill c">clause {_pct(t.get('clause_p'))}</span>
  </div>
  {fields}{details}
</article>"""


def _board(spec, pdf):
    cards = "".join(_card(t) for t in spec["theses"])
    dl = f'<p class="dl">Full board (with sources and the adversarial refute notes): <a href="{pdf}">download PDF &darr;</a></p>'
    return f"""<section class="board"><div class="wrap">
  <div class="eyebrow">{_inline(spec.get('domain','')[:60])}</div>
  <h2>{_inline(spec.get('title',''))}</h2>
  <p class="sub">{_inline(spec.get('subtitle',''))}</p>
  <p class="syn">{_inline(spec.get('synthesis',''))}</p>
  {dl}
  <div class="cards">{cards}</div>
</div></section>"""


def build_page(specs_pdfs, date):
    boards = "".join(_board(s, p) for s, p in specs_pdfs)
    n_calls = sum(len(s["theses"]) for s, _ in specs_pdfs)
    method = f"""<section class="method"><div class="wrap">
  <h2>How to read these</h2>
  <div class="grid">
    <div>
      <p>These are dated, falsifiable, pre-consensus forward calls: bets on which inelastic constraint captures the rent before the market prices it. They are not a resolved track record. None has paid out yet. Each one carries a resolution date and a kill-criterion fixed at creation, and is scored with the Brier rule when it resolves.</p>
      <p>Every call shows <strong>two</strong> probabilities, never one. The <strong>vision</strong> figure is how strong the structural case is. The <strong>clause</strong> figure is the calibrated odds that the exact dated, mechanically checkable clause resolves true, after the timing and measurement tax. The clause number is the one that gets scored. A call reading near 50 on the clause is honest uncertainty on a tight criterion, not a weak thesis.</p>
    </div>
    <div class="legend">
      <div class="row"><span class="pill v mono">vision</span><span>strength of the structural case</span></div>
      <div class="row"><span class="pill c mono">clause</span><span>calibrated odds the dated clause resolves; Brier-scored</span></div>
      <div class="row"><span class="pill d mono">resolves</span><span>fixed at creation; superseded, never edited</span></div>
    </div>
  </div>
</div></section>"""
    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Forward calls — Vaticinus</title>
<meta name="description" content="Dated, falsifiable, pre-consensus forward structural calls: where scarcity and value migrate next, given physical and demographic constraints.">
<style>{CSS}</style></head><body>
<header class="mast"><div class="wrap">
  <div class="top"><span class="brandmark mono">VATICINUS</span><a href="/">&larr; home</a></div>
  <div class="kick">Forward calls &middot; pre-consensus &middot; calibrated &middot; falsifiable</div>
  <h1>Where scarcity migrates next</h1>
  <p>{n_calls} dated forward structural calls across {len(specs_pdfs)} boards. Each names the inelastic input that captures the rent before pricing catches up, with the date and the test that would prove it wrong.</p>
</div></header>
{method}
{boards}
<footer><div class="wrap">
  <p class="disc">These calls are generated by an internal foresight system and hardened through an adversarial gate that tries to prove each one is already priced. Survivors are published here as forward instruments. They are not investment advice and not a resolved record. The point is calibration over time: dated claims, scored honestly when they come due.</p>
  <p class="mono">Generated {html.escape(date)} &middot; <a href="/">vaticinus</a></p>
</div></footer>
</body></html>"""


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    specs_pdfs = []
    for b in BOARDS:
        spec_path = os.path.join(REPO, b["spec"])
        if not os.path.exists(spec_path):
            print(f"skip {b['slug']}: missing {b['spec']}")
            continue
        with open(spec_path, encoding="utf-8") as fh:
            spec = json.load(fh)
        pdf_src = os.path.join(REPO, b["pdf_src"])
        if os.path.exists(pdf_src):
            shutil.copy(pdf_src, os.path.join(OUT_DIR, b["pdf"]))
        specs_pdfs.append((spec, b["pdf"]))
    if not specs_pdfs:
        raise SystemExit("no boards to publish")
    page = build_page(specs_pdfs, "2026-06-14")
    out = os.path.join(OUT_DIR, "index.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"wrote {out}  ({sum(len(s['theses']) for s,_ in specs_pdfs)} calls, {len(specs_pdfs)} boards)")
    print("pdfs:", ", ".join(b["pdf"] for b in BOARDS if os.path.exists(os.path.join(OUT_DIR, b['pdf']))))


if __name__ == "__main__":
    main()
