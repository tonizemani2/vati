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
    {"slug": "catalyst", "spec": "research/pope/any-short-2026-06-15.json",
     "pdf_src": "research/pope/any-short-2026-06-15.pdf", "pdf": "catalyst.pdf"},
    {"slug": "structural", "spec": "research/pope/any-long-2026-06-15.json",
     "pdf_src": "research/pope/any-long-2026-06-15.pdf", "pdf": "structural.pdf"},
    {"slug": "inelastic-needles", "spec": "research/pope/inelastic-needles-2026-06-15.json",
     "pdf_src": "research/pope/inelastic-needles-2026-06-15.pdf", "pdf": "inelastic-needles.pdf"},
    {"slug": "space", "spec": "research/pope/space-2026-06-14.json",
     "pdf_src": "research/pope/space-2026-06-14.pdf", "pdf": "space.pdf"},
    {"slug": "chips", "spec": "research/pope/chips-2026-06-14.json",
     "pdf_src": "research/pope/chips-2026-06-14.pdf", "pdf": "chips.pdf"},
    {"slug": "biotech", "spec": "research/pope/biotech-2026-06-14.json",
     "pdf_src": "research/pope/biotech-2026-06-14.pdf", "pdf": "biotech.pdf"},
]

# Constellation mark lifted verbatim from the site nav (fragments/nav.html) so the
# wordmark on this page is pixel-identical to the homepage; currentColor renders it
# in dark ink on the paper bar (the homepage uses it in white on the dark hero).
LOGO_SVG = (
    '<svg width="34" height="28" viewBox="0 0 34 28" fill="none" aria-hidden="true" '
    'style="flex:none;overflow:visible">'
    '<path d="M3 23 Q17 26 31 17" stroke="currentColor" stroke-opacity="0.18" stroke-width="0.7" fill="none"/>'
    '<path d="M10 5.5 L4.5 9 M10 5.5 L15.5 11.5 M15.5 11.5 L21.5 6.5 M21.5 6.5 L27 12.5 '
    'M15.5 11.5 L18.5 18 M18.5 18 L10.5 16.5 M10.5 16.5 L4.5 9 M18.5 18 L27 12.5" '
    'stroke="currentColor" stroke-opacity="0.42" stroke-width="0.6" stroke-linecap="round"/>'
    '<circle cx="4.5" cy="9" r="0.9" fill="currentColor" fill-opacity="0.85"/>'
    '<circle cx="10" cy="5.5" r="1.1" fill="currentColor" fill-opacity="0.9"/>'
    '<circle cx="15.5" cy="11.5" r="1" fill="currentColor" fill-opacity="0.85"/>'
    '<circle cx="27" cy="12.5" r="1.2" fill="currentColor" fill-opacity="0.9"/>'
    '<circle cx="18.5" cy="18" r="1" fill="currentColor" fill-opacity="0.85"/>'
    '<circle cx="10.5" cy="16.5" r="0.9" fill="currentColor" fill-opacity="0.8"/>'
    '<circle cx="7" cy="21" r="0.5" fill="currentColor" fill-opacity="0.4"/>'
    '<circle cx="24" cy="19.5" r="0.5" fill="currentColor" fill-opacity="0.4"/>'
    '<circle cx="13" cy="3" r="0.5" fill="currentColor" fill-opacity="0.4"/>'
    '<path d="M21.5 3.9 L22.4 5.6 L24.1 6.5 L22.4 7.4 L21.5 9.1 L20.6 7.4 L18.9 6.5 L20.6 5.6 Z" fill="#6d6afc"/>'
    '</svg>'
)

FONT_CSS = """
@font-face{font-family:'Gt Standard';font-weight:400;font-style:normal;font-display:swap;src:url('https://cdn.prod.website-files.com/68907168d294618a86ec6518/689b297557d89256a5697b72_GT-Standard-L-Standard-Regular.woff2') format('woff2');}
@font-face{font-family:'Gt Standard';font-weight:500;font-style:normal;font-display:swap;src:url('https://cdn.prod.website-files.com/68907168d294618a86ec6518/689b2975a12fc701f9f074a9_GT-Standard-L-Standard-Medium.woff2') format('woff2');}
@font-face{font-family:'Gt Standard Mono';font-weight:500;font-style:normal;font-display:swap;src:url('https://cdn.prod.website-files.com/68907168d294618a86ec6518/689b29750af0e8f994b5a45e_GT-Standard-Mono-Narrow-Medium.woff2') format('woff2');}
"""

CSS = FONT_CSS + """
/* Design tokens mirror the live site (site.webflow.css): brand indigo #6d6afc,
   paper #f3f2f0, ink #343434, near-black #0c0b10. This page is self-contained
   but reads as the same family as the homepage. */
:root{--paper:#f3f2f0;--card:#fff;--ink:#343434;--dark:#0c0b10;--brand:#6d6afc;--brand-deep:#4a47c4;--line:rgba(12,11,16,.12);--mut:#6c6c6c;}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;}
body{background:var(--paper);color:var(--ink);font-family:'Gt Standard',Arial,sans-serif;font-weight:400;line-height:1.55;-webkit-font-smoothing:antialiased;}
.mono{font-family:'Gt Standard Mono','Gt Standard',monospace;}
a{color:var(--brand-deep);text-decoration:none;}
a:hover{text-decoration:underline;}
.wrap{max-width:1120px;margin:0 auto;padding:0 24px;}

/* announcement bar + nav, echoes the site chrome */
.banner{background:var(--dark);color:var(--paper);text-align:center;padding:9px 16px;}
.banner a{color:var(--paper);font-family:'Gt Standard Mono',monospace;font-weight:500;text-transform:uppercase;letter-spacing:.16em;font-size:11px;}
.banner a:hover{text-decoration:none;color:#fff;}
.banner .dot{color:var(--brand);margin:0 .5em;}
.nav{position:sticky;top:0;z-index:20;background:rgba(243,242,240,.86);backdrop-filter:saturate(140%) blur(10px);border-bottom:1px solid var(--line);}
.nav .row{display:flex;align-items:center;justify-content:space-between;height:64px;}
.nav .brand{display:inline-flex;align-items:center;gap:.55rem;color:var(--dark);font-weight:600;font-size:1.4rem;letter-spacing:-.01em;line-height:1;white-space:nowrap;}
.nav .brand:hover{text-decoration:none;}
.nav .links{display:flex;gap:26px;align-items:center;}
.nav .links a{color:var(--ink);font-weight:500;font-size:15px;}
.nav .links a.cur{color:var(--dark);}
@media(max-width:680px){.nav .links a:not(.cur){display:none;}}

/* hero — dark full-bleed band, echoing the homepage hero (paper nav over dark hero) */
.hero{background:var(--dark);color:var(--paper);padding:clamp(54px,7vw,104px) 0 clamp(46px,6vw,76px);}
.hero .eyebrow{font-family:'Gt Standard Mono',monospace;font-weight:500;text-transform:uppercase;letter-spacing:.18em;font-size:12px;color:#a9a6ff;}
.hero h1{font-weight:500;font-size:clamp(34px,6vw,64px);line-height:1.02;letter-spacing:-.02em;color:#fff;margin:18px 0 16px;max-width:16ch;}
.hero p{font-size:clamp(17px,1.5vw,20px);color:rgba(255,255,255,.72);max-width:46em;margin:0;}
.hero .tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:clamp(30px,3.2vw,42px);}
@media(max-width:760px){.hero .tiles{grid-template-columns:1fr 1fr;}}
.hero .tile{border:1px solid rgba(255,255,255,.12);border-radius:14px;padding:16px 18px;background:rgba(255,255,255,.03);}
.hero .tile .n{font-size:clamp(21px,2.1vw,28px);font-weight:700;color:#fff;font-variant-numeric:tabular-nums;line-height:1;letter-spacing:-.01em;}
.hero .tile .l{margin-top:9px;font-size:12.5px;line-height:1.4;color:rgba(255,255,255,.55);}

/* method note */
.method{padding:8px 0 40px;}
.method .box{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:clamp(22px,2.4vw,34px);display:grid;grid-template-columns:1.5fr 1fr;gap:clamp(24px,3vw,44px);}
.method h2{font-family:'Gt Standard Mono',monospace;font-weight:500;font-size:12px;text-transform:uppercase;letter-spacing:.14em;color:var(--brand-deep);margin:0 0 14px;}
.method p{margin:0 0 12px;font-size:15px;color:var(--ink);}
.legend{align-self:start;border-left:1px solid var(--line);padding-left:clamp(24px,3vw,44px);}
.legend .row{display:flex;gap:11px;align-items:baseline;margin:0 0 14px;font-size:14px;color:var(--ink);}
.legend .pill{flex:0 0 auto;}

/* prob pills */
.pill{display:inline-block;font-family:'Gt Standard Mono',monospace;font-weight:500;font-size:12.5px;padding:3px 10px;border-radius:999px;border:1px solid var(--line);white-space:nowrap;}
.pill.v{background:#edf3ec;border-color:#cfe0c8;color:#2f5a2a;}
.pill.c{background:#ecebff;border-color:#cbc9fb;color:#4a47c4;}
.pill.d{background:#faf6ee;border-color:#e7dcc4;color:#7a611f;}

/* board */
.board{padding:clamp(36px,4vw,58px) 0;border-top:1px solid var(--line);}
.board .eyebrow{font-family:'Gt Standard Mono',monospace;font-weight:500;text-transform:uppercase;letter-spacing:.16em;font-size:12px;color:var(--brand-deep);}
.board h2{font-weight:500;font-size:clamp(24px,3.2vw,34px);line-height:1.1;margin:10px 0 8px;letter-spacing:-.015em;color:var(--dark);max-width:24ch;}
.board .sub{font-style:italic;color:var(--mut);font-size:17px;margin:0 0 16px;max-width:56em;}
.board .syn{font-size:15px;color:var(--ink);max-width:62em;margin:0 0 18px;}
.board .dl{display:inline-flex;align-items:center;gap:8px;font-weight:500;font-size:14px;color:var(--brand-deep);border:1px solid var(--line);border-radius:999px;padding:8px 16px;margin:0 0 28px;background:var(--card);}
.board .dl:hover{text-decoration:none;border-color:var(--brand);}
.cards{display:grid;grid-template-columns:repeat(2,1fr);gap:clamp(16px,1.6vw,22px);}
@media(max-width:820px){.cards{grid-template-columns:1fr;}.method .box{grid-template-columns:1fr;}.legend{border-left:0;border-top:1px solid var(--line);padding-left:0;padding-top:22px;}}

/* dark "ticket" cards — the homepage signature: dark cards on the light paper board */
.card{background:linear-gradient(165deg,#17141f,#0c0b10);border:1px solid rgba(255,255,255,.10);border-radius:16px;padding:clamp(20px,2vw,26px);display:flex;flex-direction:column;color:#fff;transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease;}
.card:hover{transform:translateY(-4px);border-color:var(--brand);box-shadow:0 18px 50px rgba(12,11,16,.28);}
.card .chead{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:12px;}
.card .id{font-family:'Gt Standard Mono',monospace;font-weight:500;font-size:12px;color:#fff;background:var(--brand);padding:3px 9px;border-radius:6px;letter-spacing:.08em;}
.card h3{font-weight:500;font-size:17px;line-height:1.32;margin:0 0 12px;color:#fff;}
.card .pills{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;}
.card .f{margin:0 0 12px;font-size:14px;line-height:1.55;color:rgba(255,255,255,.72);}
.card .f .k{display:block;font-family:'Gt Standard Mono',monospace;text-transform:uppercase;letter-spacing:.08em;font-size:10.5px;color:#a9a6ff;margin-bottom:3px;}
.card details{margin-top:6px;border-top:1px solid rgba(255,255,255,.10);padding-top:12px;}
.card details[open]{margin-bottom:2px;}
.card summary{cursor:pointer;list-style:none;font-family:'Gt Standard Mono',monospace;font-weight:500;text-transform:uppercase;letter-spacing:.08em;font-size:11px;color:#a9a6ff;}
.card summary::-webkit-details-marker{display:none;}
.card summary::after{content:" +";}
.card details[open] summary::after{content:" \\2212";}
.card details .f{margin-top:12px;}
.card details .f .k{color:rgba(255,255,255,.5);}

footer{padding:48px 0 64px;color:var(--mut);font-size:13px;border-top:1px solid var(--line);}
footer .disc{max-width:64em;margin:0 0 16px;line-height:1.6;}
"""


def _field(label, text, mono=False):
    if not text:
        return ""
    return f'<div class="f"><span class="k">{html.escape(label)}</span>{_inline(text)}</div>'


def _card(t):
    # Always-visible: the three core, scoreable fields. The longer prose (the
    # "boom" setup + the structural/pre-consensus/price/refute/why argument) goes
    # into a collapsed disclosure so the card reads clean instead of as a wall.
    fields = "".join([
        _field("Binding constraint (the needle)", t.get("needle", "")),
        _field("Leading metric", t.get("metric", "")),
        _field("Kill-criterion", t.get("kill", "")),
    ])
    deep = "".join([
        _field("The setup", t.get("boom", "")),
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
  <div class="pills">
    <span class="pill v">vision {_pct(t.get('vision_p'))}</span>
    <span class="pill c">clause {_pct(t.get('clause_p'))}</span>
  </div>
  {fields}{details}
</article>"""


def _board(spec, pdf):
    cards = "".join(_card(t) for t in spec["theses"])
    dl = f'<a class="dl" href="{pdf}">Download the full board PDF, with sources and refute notes &darr;</a>'
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
  <div class="box">
    <div>
      <h2>How to read these</h2>
      <p>These are dated, falsifiable, pre-consensus forward calls: bets on which inelastic constraint captures the rent before the market prices it. They are not a resolved track record. None has paid out yet. Each one carries a resolution date and a kill-criterion fixed at creation, and is scored with the Brier rule when it resolves.</p>
      <p>Every call shows <strong>two</strong> probabilities, never one. The <strong>vision</strong> figure is how strong the structural case is. The <strong>clause</strong> figure is the calibrated odds that the exact dated, mechanically checkable clause resolves true, after the timing and measurement tax. The clause number is the one that gets scored. A call reading near 50 on the clause is honest uncertainty on a tight criterion, not a weak thesis.</p>
    </div>
    <div class="legend">
      <div class="row"><span class="pill v">vision</span><span>strength of the structural case</span></div>
      <div class="row"><span class="pill c">clause</span><span>calibrated odds the dated clause resolves; Brier-scored</span></div>
      <div class="row"><span class="pill d">resolves</span><span>fixed at creation; superseded, never edited</span></div>
    </div>
  </div>
</div></section>"""
    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Forward calls · Vaticinus</title>
<meta name="description" content="Dated, falsifiable, pre-consensus forward structural calls: where scarcity and value migrate next, given physical and demographic constraints.">
<style>{CSS}</style></head><body>
<div class="banner"><a href="/#research">The sealed forecast record <span class="dot">&middot;</span> see the calls</a></div>
<header class="nav"><div class="wrap"><div class="row">
  <a class="brand" href="/" aria-label="Vaticinus home">{LOGO_SVG}Vaticinus</a>
  <nav class="links">
    <a class="cur" href="/forecasts/">Forecasts</a>
    <a href="/#research">Research</a>
    <a href="/#product">Product</a>
    <a href="/#about">Company</a>
  </nav>
</div></div></header>
<section class="hero"><div class="wrap">
  <div class="eyebrow">Forward calls &middot; pre-consensus &middot; calibrated &middot; falsifiable</div>
  <h1>Where scarcity moves next</h1>
  <p>{n_calls} dated forward structural calls across {len(specs_pdfs)} boards. Each names the inelastic input that captures the rent before pricing catches up, with the date and the test that would prove it wrong.</p>
  <div class="tiles">
    <div class="tile"><div class="n">{n_calls}</div><div class="l">dated forward calls</div></div>
    <div class="tile"><div class="n">{len(specs_pdfs)}</div><div class="l">constraint boards</div></div>
    <div class="tile"><div class="n">2</div><div class="l">probabilities per call: the vision and the scored clause</div></div>
    <div class="tile"><div class="n">Brier</div><div class="l">scored in public when each call comes due</div></div>
  </div>
</div></section>
{method}
{boards}
<footer><div class="wrap">
  <p class="disc">These calls are generated by an internal foresight system and hardened through an adversarial gate that tries to prove each one is already priced. Survivors are published here as forward instruments. They are not investment advice and not a resolved record. The point is calibration over time: dated claims, scored honestly when they come due.</p>
  <p class="mono">Generated {html.escape(date)} &middot; <a href="/">vaticinus.com</a></p>
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
    page = build_page(specs_pdfs, "2026-06-15")
    out = os.path.join(OUT_DIR, "index.html")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"wrote {out}  ({sum(len(s['theses']) for s,_ in specs_pdfs)} calls, {len(specs_pdfs)} boards)")
    print("pdfs:", ", ".join(b["pdf"] for b in BOARDS if os.path.exists(os.path.join(OUT_DIR, b['pdf']))))


if __name__ == "__main__":
    main()
