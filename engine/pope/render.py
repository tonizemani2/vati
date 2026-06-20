#!/usr/bin/env python3
"""Pope System renderer: a thesis spec (JSON) -> styled HTML -> PDF.

Deterministic, no LLM, no third-party deps. The PDF is produced by headless
Chrome so the look matches the research-note house style exactly.

Usage:
    python -m engine.pope.render <spec.json> <out_basepath>
    # writes <out_basepath>.html and <out_basepath>.pdf

    Spec JSON shape (see engine/pope/README.md for the full contract):
    {
      "title": "Where Scarcity Migrates Next",
      "subtitle": "...",
      "domain": "robotics",
      "date": "2026-06-14",
      "horizon": "2030 to 2035",
      "synthesis": "one cross-cutting paragraph",
      "theses": [ { ...fields... } ],
      "runner_ups": [ {"seed": "", "case": "", "why_not": ""} ]
    }
Each thesis: id, headline, boom, domain, vision_p, clause_p, resolves,
	structural, pre_consensus, price_channel(optional), needle, metric, kill,
	why, refute(optional), implications(optional).
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import sys

from engine.pope import charts


# ---------------------------------------------------------------- text helpers
def _inline(text: str) -> str:
    """Escape, then re-enable a tiny markdown subset (**bold**, *italic*)."""
    if text is None:
        return ""
    raw = (
        str(text)
        .replace("\u2014", " - ")
        .replace("\u2013", "-")
        .replace("\u2011", "-")
        .replace("\u2212", "-")
        .replace("\u2026", "...")
    )
    out = html.escape(raw)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", out)
    return out


def _field(label: str, text: str, kind: str = "field") -> str:
    if not text:
        return ""
    klass = "why" if kind == "why" else "field"
    return (
        f'<div class="{klass}"><span class="k">{html.escape(label)}</span>\n'
        f"{_inline(text)}</div>"
    )


def _pct(v) -> str:
    if v is None:
        return "-"
    v = float(v)
    if v <= 1.0:  # workflow returns 0-1 fractions (0.82); authored specs use 0-100
        v *= 100
    return f"{int(round(v))}%"


def _clip(text, n=110) -> str:
    """Truncate at a word boundary with an ellipsis (no mid-word cuts)."""
    if not text:
        return ""
    text = str(text).strip()
    if len(text) <= n:
        return text
    return text[:n].rsplit(" ", 1)[0].rstrip(",;:.") + "..."


# ------------------------------------------------------------------- templates
# Self-hosted Gt Standard from the live site CDN so the PDF matches the homepage
# and the /forecasts/ web page exactly. Headless Chrome fetches these over the
# network at render time (file:// pages still have network access).
FONT_CSS = """
  @font-face{font-family:'Gt Standard';font-weight:400;font-style:normal;font-display:swap;src:url('https://cdn.prod.website-files.com/68907168d294618a86ec6518/689b297557d89256a5697b72_GT-Standard-L-Standard-Regular.woff2') format('woff2');}
  @font-face{font-family:'Gt Standard';font-weight:500;font-style:normal;font-display:swap;src:url('https://cdn.prod.website-files.com/68907168d294618a86ec6518/689b2975a12fc701f9f074a9_GT-Standard-L-Standard-Medium.woff2') format('woff2');}
  @font-face{font-family:'Gt Standard Mono';font-weight:500;font-style:normal;font-display:swap;src:url('https://cdn.prod.website-files.com/68907168d294618a86ec6518/689b29750af0e8f994b5a45e_GT-Standard-Mono-Narrow-Medium.woff2') format('woff2');}
"""

# Print system: memo-like, mostly monochrome, with one signal accent. The live
# site can stay more branded; the PDFs need to read as research artifacts.
CSS = FONT_CSS + """
  :root { --page:#fbfaf7; --paper:#f2f0ea; --ink:#151515; --text:#33312d; --mut:#706c65; --quiet:#9b958d; --line:#d9d4cc; --line-strong:#151515; --accent:#6d6afc; --accent-soft:#eeedff; }
  @page { size: Letter; margin: 18mm 17mm 18mm 17mm;
    @bottom-left { content: "Vaticinus"; font-family: 'Gt Standard Mono', monospace; font-size: 7.5pt; color: #a7a19a; }
    @bottom-center { content: counter(page); font-family: 'Gt Standard Mono', monospace; font-size: 8pt; color: #a7a19a; } }
  html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  body { font-family: 'Gt Standard', Arial, sans-serif; font-weight: 400; color: var(--text); line-height: 1.48; font-size: 10pt; margin: 0; background: var(--page); }
  h1, h2, h3, h4 { font-family: 'Gt Standard', Arial, sans-serif; font-weight: 500; color: var(--ink); line-height: 1.08; letter-spacing: 0; }
  h1 { font-size: 34pt; margin: 0; max-width: 650px; }
  h2 { font-size: 17pt; margin: 0; }
  h3 { font-size: 11.8pt; margin: 18px 0 5px; color: var(--ink); }
  h4 { font-family: 'Gt Standard Mono', monospace; font-size: 8.2pt; margin: 12px 0 3px; color: var(--mut); }
  p { margin: 0 0 8px; }
  .accent { color: var(--accent); } .muted { color: var(--mut); } .small { font-size: 8.7pt; } strong { color: var(--ink); font-weight: 500; }
  .cover { min-height: 238mm; display: flex; flex-direction: column; }
  .cover .mast { display: flex; justify-content: space-between; align-items: baseline; border-top: 2px solid var(--ink); border-bottom: 1px solid var(--line); padding: 8px 0 10px; font-family: 'Gt Standard Mono', monospace; font-weight: 500; font-size: 8pt; color: var(--mut); }
  .cover .mast span:last-child { color: var(--accent); }
  .cover .title-block { padding-top: 33mm; }
  .cover .sub { font-size: 13.5pt; color: var(--mut); margin-top: 10px; max-width: 610px; line-height: 1.38; }
  .cover .frame { margin-top: auto; display: grid; grid-template-columns: 1.15fr .85fr; gap: 18px; border-top: 2px solid var(--ink); border-bottom: 1px solid var(--line); padding: 15px 0 14px; }
  .cover .frame-copy { font-size: 10pt; max-width: 420px; }
  .cover .frame-copy .label { display: block; font-family: 'Gt Standard Mono', monospace; font-weight: 500; font-size: 7.7pt; color: var(--accent); margin-bottom: 4px; }
  .cover .meta { display: grid; grid-template-columns: 1fr; gap: 7px; font-size: 9pt; }
  .cover .meta div { border-top: 1px solid var(--line); padding-top: 6px; }
  .cover .meta span { display: block; font-family: 'Gt Standard Mono', monospace; font-size: 7.3pt; color: var(--quiet); margin-bottom: 1px; }
  .page-break { page-break-before: always; }
  .section-rule { border-top: 2px solid var(--ink); padding-top: 10px; margin-bottom: 14px; }
  table { border-collapse: collapse; table-layout: fixed; width: 100%; font-size: 8.1pt; line-height: 1.28; margin: 10px 0 11px; border-top: 1.5px solid var(--ink); border-bottom: 1px solid var(--line); }
  th, td { text-align: left; padding: 4.5px 6px; vertical-align: top; overflow-wrap: anywhere; }
  thead th { border-bottom: 1px solid var(--ink); color: var(--mut); font-family: 'Gt Standard Mono', monospace; font-weight: 500; font-size: 7.3pt; }
  tbody tr + tr { border-top: 1px solid var(--line); }
  tbody tr:nth-child(even) { background: rgba(242,240,234,.58); }
  tr { break-inside: avoid; }
  td.num { font-family: 'Gt Standard Mono', monospace; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .thesis { page-break-before: always; }
  .thesis-head { display: grid; grid-template-columns: 42px 1fr; gap: 13px; border-top: 2px solid var(--ink); padding-top: 10px; margin-bottom: 8px; }
  .thesis-head .id { font-family: 'Gt Standard Mono', monospace; font-weight: 500; font-size: 9pt; color: var(--accent); padding-top: 2px; }
  .thesis-head h2 { font-size: 16.2pt; }
  .thesis-meta { display: grid; grid-template-columns: 1fr 108px; gap: 16px; margin: 6px 0 12px 55px; color: var(--mut); font-size: 8.7pt; }
  .thesis-meta .date { font-family: 'Gt Standard Mono', monospace; color: var(--ink); text-align: right; }
  .prob-band { display: grid; grid-template-columns: 1fr 1fr 1.18fr; margin: 11px 0 14px 55px; border-top: 1.5px solid var(--ink); border-bottom: 1px solid var(--line); }
  .prob-card { padding: 8px 10px 9px; border-right: 1px solid var(--line); }
  .prob-card:last-child { border-right: 0; }
  .prob-card .label { font-family: 'Gt Standard Mono', monospace; font-weight: 500; font-size: 7.2pt; color: var(--quiet); }
  .prob-card .val { font-family: 'Gt Standard', Arial, sans-serif; font-weight: 500; font-size: 20pt; color: var(--ink); line-height: 1.05; }
  .prob-card.clause .val { color: var(--accent); }
  .prob-card .val.sm { font-size: 11.6pt; padding-top: 5px; font-family: 'Gt Standard Mono', monospace; }
  .thesis-body { margin-left: 55px; }
  .lead { font-size: 10.5pt; color: var(--ink); margin-bottom: 10px; }
  .charts { margin: 12px 0; break-inside: avoid; }
  .chartbox { margin: 8px 0 14px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 4px; background: #fff; break-inside: avoid; }
  .chartbox .vf-chart { display: block; }
  .field, .why { display: grid; grid-template-columns: 138px 1fr; gap: 14px; border-top: 1px solid var(--line); padding-top: 7px; margin: 0 0 8px; break-inside: avoid; }
  .field .k, .why .k { font-family: 'Gt Standard Mono', monospace; font-weight: 500; font-size: 7.4pt; color: var(--mut); }
  .why { background: var(--accent-soft); border-top: 0; border-left: 3px solid var(--accent); padding: 9px 11px; margin: 11px 0; }
  .impl { margin: 13px 0 4px; padding: 11px 12px; background: #f6f7fb; border: 1px solid var(--line); border-left: 3px solid var(--accent); break-inside: avoid; }
  .impl .k { font-family: 'Gt Standard Mono', monospace; font-weight: 500; font-size: 7.4pt; color: var(--accent); display: block; margin-bottom: 4px; }
  .impl p { margin: 0 0 7px; }
  .decision { display: grid; grid-template-columns: 1fr 1fr; gap: 9px 12px; margin: 8px 0 10px; }
  .decision .ditem { border-top: 1px solid var(--line); padding-top: 5px; }
  .decision .dk { display: block; font-family: 'Gt Standard Mono', monospace; font-weight: 500; font-size: 7.1pt; color: var(--mut); margin-bottom: 2px; }
  .wl { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 8px 0 10px; }
  .wl .col { border-top: 1px solid var(--line); padding-top: 5px; }
  .wl h5 { font-family: 'Gt Standard Mono', monospace; font-weight: 500; font-size: 7.2pt; color: var(--mut); margin: 0 0 5px; }
  .wl .row { margin: 0 0 5px; font-size: 8.8pt; line-height: 1.38; }
  .wl .who { font-weight: 500; color: var(--ink); }
  .impl .sub { margin-top: 7px; }
  .footer-note { margin-top: 8px; font-family: 'Gt Standard Mono', monospace; font-size: 7.8pt; color: var(--quiet); }
"""


def _cover(spec: dict) -> str:
    return f"""<section class="cover">
  <div class="mast"><span>Vaticinus forecast board</span><span>Dated / falsifiable</span></div>
  <div class="title-block">
    <h1>{_inline(spec.get('title', 'Where Scarcity Migrates Next'))}</h1>
    <div class="sub">{_inline(spec.get('subtitle', ''))}</div>
  </div>
  <div class="frame">
    <div class="frame-copy"><span class="label">Frame</span>When a system scales, the money moves to the input that cannot scale with it. This board names that input, the date it starts to bite, and the line that would break the call.</div>
    <div class="meta">
      <div><span>Area</span>{_inline(spec.get('domain', 'any'))}</div>
      <div><span>Horizon</span>{_inline(spec.get('horizon', ''))}</div>
      <div><span>Issued</span>{_inline(spec.get('date', ''))}</div>
      <div><span>Method</span>Wide cast, adversarial gate, public resolution criteria.</div>
    </div>
  </div>
</section>"""


def _summary_table(spec: dict) -> str:
    rows = []
    for t in spec["theses"]:
        rows.append(
            f'<tr><td>{_inline(t.get("id",""))}</td>'
            f'<td>{_inline(_clip(t.get("boom",""), 120))}</td>'
            f'<td>{_inline(_clip(t.get("needle_short", t.get("needle","")), 110))}</td>'
            f'<td class="num">{_pct(t.get("vision_p"))}</td>'
            f'<td class="num">{_pct(t.get("clause_p"))}</td>'
            f'<td class="num">{_inline(t.get("resolves",""))}</td></tr>'
        )
    syn = (
        f'<h3>The cross-cutting read</h3><p>{_inline(spec["synthesis"])}</p>'
        if spec.get("synthesis")
        else ""
    )
    return f"""<section class="page-break">
  <div class="section-rule"><h2>Board summary</h2></div>
  {syn}
  <h3>At a glance</h3>
  <table><thead><tr>
    <th style="width:6%">#</th><th style="width:36%">Claim</th><th style="width:31%">Binding constraint</th>
    <th class="num" style="width:8%">Case</th><th class="num" style="width:9%">Call</th><th class="num" style="width:10%">Resolves</th>
  </tr></thead><tbody>{''.join(rows)}</tbody></table>
  <p class="small muted">Case is the strength of the structural thesis. Call is the probability on the exact dated clause.</p>
</section>"""


def _wl_col(label: str, items, klass: str) -> str:
    rows = []
    for it in items or []:
        who = _inline(it.get("who", "")) if isinstance(it, dict) else _inline(str(it))
        why = _inline(it.get("why", "")) if isinstance(it, dict) else ""
        sep = ": " if who and why else ""
        rows.append(f'<div class="row"><span class="who">{who}</span>{sep}{why}</div>')
    if not rows:
        return ""
    return f'<div class="col {klass}"><h5>{html.escape(label)}</h5>{"".join(rows)}</div>'


def _implications(t: dict) -> str:
    im = t.get("implications")
    if not im or not isinstance(im, dict):
        return ""
    win = _wl_col("Who gains", im.get("winners"), "gain")
    los = _wl_col("Who loses", im.get("losers"), "lose")
    parts = ['<div class="k">If the call is right</div>']
    decision_rows = []
    for label, key in (
        ("Who is exposed", "exposed"),
        ("Action now", "action_now"),
        ("Decision it changes", "decision_changed"),
        ("ROI / risk logic", "roi_logic"),
    ):
        if im.get(key):
            decision_rows.append(
                f'<div class="ditem"><span class="dk">{html.escape(label)}</span>'
                f'{_inline(im[key])}</div>'
            )
    if decision_rows:
        parts.append(f'<div class="decision">{"".join(decision_rows)}</div>')
    if im.get("rent_path"):
        parts.append(f'<p>{_inline(im["rent_path"])}</p>')
    if win or los:
        parts.append(f'<div class="wl">{win}{los}</div>')
    for label, key in (
        ("What reprices", "reprices"),
        ("The next constraint it creates", "next_constraint"),
        ("Earliest sign it has begun", "watch"),
    ):
        if im.get(key):
            parts.append(
                f'<span class="sub k">{html.escape(label)}</span>'
                f'<p>{_inline(im[key])}</p>'
            )
    return f'<div class="impl">{"".join(parts)}</div>'


def _one_chart(c: dict) -> str:
    """Dispatch a single chart spec to the charts toolkit. Unknown/empty -> ''. """
    if not isinstance(c, dict):
        return ""
    kind = (c.get("type") or "").lower()
    cap = c.get("caption", "")
    if kind in ("trendline", "line", "spark"):
        return charts.trendline(c.get("values"), caption=cap, labels=c.get("labels"))
    if kind in ("bars", "bar"):
        items = []
        for i in (c.get("items") or []):
            if isinstance(i, dict) and "label" in i and "value" in i:
                items.append((i["label"], i["value"]))
            elif isinstance(i, (list, tuple)) and len(i) >= 2:
                items.append((i[0], i[1]))
        return charts.bar_chart(items, caption=cap, highlight=c.get("highlight"))
    if kind == "gap":
        return charts.gap_chart(c.get("supply_label", "Supply"), c.get("supply"),
                                c.get("demand_label", "Demand"), c.get("demand"), caption=cap)
    if kind in ("dependency", "chain", "depend"):
        return charts.dependency_chain(c.get("nodes"), caption=cap, needle=c.get("needle"))
    return ""


def _chart(t: dict) -> str:
    """Render a thesis chart (single `chart` dict or a `charts` list). Evidence, not decoration."""
    specs = t.get("charts") if isinstance(t.get("charts"), list) else (
        [t["chart"]] if isinstance(t.get("chart"), dict) else [])
    svgs = [s for s in (_one_chart(c) for c in specs) if s]
    if not svgs:
        return ""
    return '<div class="charts">' + "".join(f'<div class="chartbox">{s}</div>' for s in svgs) + "</div>"


def _thesis(t: dict) -> str:
    cards = f"""<div class="prob-band">
    <div class="prob-card vision"><div class="label">Structural case</div><div class="val">{_pct(t.get('vision_p'))}</div></div>
    <div class="prob-card clause"><div class="label">Our call, dated</div><div class="val">{_pct(t.get('clause_p'))}</div></div>
    <div class="prob-card date"><div class="label">Resolves</div><div class="val sm">{_inline(t.get('resolves',''))}</div></div>
  </div>"""
    body = "\n".join(
        [
            f'<p class="lead">{_inline(t.get("structural",""))}</p>',
            _field("The boom", t.get("boom", "")),
            _field("Why it is not priced yet", t.get("pre_consensus", "")),
            _field("Where the price sits today", t.get("price_channel", "")),
            _field("The binding constraint", t.get("needle", "")),
            _field("What we are watching", t.get("metric", "")),
            _chart(t),
            _field("What would prove us wrong", t.get("kill", "")),
            _field("How we tried to break it", t.get("refute", "")),
            _field("Why we are making the call", t.get("why", ""), kind="why"),
            _implications(t),
        ]
    )
    if t.get("subtitle"):
        sub_html = _inline(t["subtitle"])
    else:
        sub_html = f'Domain: {_inline(t.get("domain",""))}'
    title = _clip(t.get("headline", ""), 190)
    return f"""<section class="thesis">
  <div class="thesis-head"><span class="id">{_inline(t.get('id',''))}</span><h2>{_inline(title)}</h2></div>
  <div class="thesis-meta"><div>{sub_html}</div><div class="date">{_inline(t.get('resolves',''))}</div></div>
  {cards}
  <div class="thesis-body">{body}</div>
</section>"""


def _runner_ups(spec: dict) -> str:
    rus = spec.get("runner_ups") or []
    if not rus:
        return ""
    rows = "".join(
        f'<tr><td>{_inline(r.get("seed",""))}</td><td>{_inline(r.get("case",""))}</td>'
        f'<td>{_inline(r.get("why_not",""))}</td></tr>'
        for r in rus
    )
    return f"""<section class="page-break">
  <div class="section-rule"><h2>Seeds considered</h2></div>
  <p>These cleared the supply-side test but did not make the final board, usually because the trade was not clean or the move was already priced.</p>
  <table><thead><tr><th style="width:24%">Seed</th><th style="width:40%">Physical case</th><th style="width:36%">Why not promoted</th></tr></thead>
  <tbody>{rows}</tbody></table>
  <p class="footer-note">Each call is dated. The line that would prove it wrong is fixed when the board is issued.</p>
</section>"""


def build_html(spec: dict) -> str:
    parts = [
        _cover(spec),
        _summary_table(spec),
        *[_thesis(t) for t in spec["theses"]],
        _runner_ups(spec),
    ]
    title = html.escape(spec.get("title", "Pope System"))
    return (
        f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{title}</title><style>{CSS}</style></head><body>"
        + "\n".join(parts)
        + "</body></html>"
    )


# ----------------------------------------------------------------- chrome -> pdf
def _find_chrome() -> str | None:
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]
    return next((c for c in candidates if c and os.path.exists(c)), None)


def render(spec_path: str, out_base: str) -> None:
    with open(spec_path, "r", encoding="utf-8") as fh:
        spec = json.load(fh)
    if not spec.get("theses"):
        raise SystemExit("spec has no theses")

    html_path = f"{out_base}.html"
    pdf_path = f"{out_base}.pdf"
    os.makedirs(os.path.dirname(os.path.abspath(out_base)) or ".", exist_ok=True)
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(build_html(spec))
    print(f"wrote {html_path}")

    chrome = _find_chrome()
    if not chrome:
        print("WARNING: no Chrome/Chromium found; HTML written, PDF skipped.")
        return
    subprocess.run(
        [chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={os.path.abspath(pdf_path)}",
         f"file://{os.path.abspath(html_path)}"],
        check=True, capture_output=True,
    )
    print(f"wrote {pdf_path}  ({os.path.getsize(pdf_path)//1024} KB, {len(spec['theses'])} theses)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: python -m engine.pope.render <spec.json> <out_basepath>")
    render(sys.argv[1], sys.argv[2])
