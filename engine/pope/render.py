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
why, refute(optional).
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import sys


# ---------------------------------------------------------------- text helpers
def _inline(text: str) -> str:
    """Escape, then re-enable a tiny markdown subset (**bold**, *italic*)."""
    if text is None:
        return ""
    out = html.escape(str(text))
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
        return "&mdash;"
    v = float(v)
    if v <= 1.0:  # workflow returns 0-1 fractions (0.82); authored specs use 0-100
        v *= 100
    return f"{int(round(v))}%"


# ------------------------------------------------------------------- templates
CSS = """
  @page { size: Letter; margin: 22mm 20mm 20mm 20mm;
    @bottom-center { content: counter(page); font-family: Georgia, serif; font-size: 9pt; color: #8a8f99; } }
  html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  body { font-family: Georgia, "Times New Roman", serif; color: #1c2129; line-height: 1.5; font-size: 10.5pt; margin: 0; }
  h1, h2, h3, h4 { font-family: "Helvetica Neue", Arial, sans-serif; color: #11203a; line-height: 1.2; }
  h1 { font-size: 23pt; letter-spacing: -0.3px; margin: 0 0 6px; }
  h2 { font-size: 14.5pt; margin: 26px 0 8px; border-bottom: 1.5px solid #11203a; padding-bottom: 5px; }
  h3 { font-size: 12.5pt; margin: 20px 0 4px; color: #1a3a6b; }
  h4 { font-size: 10.5pt; margin: 14px 0 3px; text-transform: uppercase; letter-spacing: 0.6px; color: #5a6472; }
  p { margin: 0 0 9px; }
  .accent { color: #1a3a6b; } .muted { color: #5a6472; } .small { font-size: 9pt; } strong { color: #11203a; }
  .cover { padding-top: 30mm; border-top: 6px solid #11203a; }
  .cover .kicker { font-family: "Helvetica Neue", Arial, sans-serif; text-transform: uppercase; letter-spacing: 2px; font-size: 9.5pt; color: #1a3a6b; margin-bottom: 14px; }
  .cover .sub { font-size: 13pt; color: #3a424e; margin-top: 10px; font-style: italic; }
  .cover .meta { margin-top: 30mm; font-family: "Helvetica Neue", Arial, sans-serif; font-size: 9.5pt; color: #5a6472; line-height: 1.7; }
  .cover .spine { margin-top: 16px; padding: 12px 14px; background: #f3f5f8; border-left: 4px solid #1a3a6b; font-size: 9.5pt; }
  .page-break { page-break-before: always; }
  table { border-collapse: collapse; width: 100%; font-size: 9.2pt; margin: 10px 0 14px; }
  th, td { text-align: left; padding: 6px 8px; vertical-align: top; }
  thead th { background: #11203a; color: #fff; font-family: "Helvetica Neue", Arial, sans-serif; font-weight: 600; font-size: 8.6pt; }
  tbody tr:nth-child(even) { background: #f3f5f8; }
  td.num { font-variant-numeric: tabular-nums; white-space: nowrap; }
  .thesis { page-break-before: always; }
  .thesis-head { display: flex; justify-content: space-between; align-items: baseline; border-bottom: 1.5px solid #11203a; padding-bottom: 6px; margin-bottom: 4px; }
  .thesis-head h2 { border: 0; margin: 0; padding: 0; }
  .thesis-head .id { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 9pt; color: #fff; background: #1a3a6b; padding: 3px 8px; border-radius: 3px; letter-spacing: 1px; }
  .prob-band { display: flex; gap: 10px; margin: 10px 0 14px; }
  .prob-card { flex: 1; border: 1px solid #d4d9e0; border-radius: 5px; padding: 9px 11px; }
  .prob-card .label { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 7.6pt; text-transform: uppercase; letter-spacing: 0.8px; color: #5a6472; }
  .prob-card .val { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 19pt; font-weight: 700; color: #11203a; line-height: 1.1; }
  .prob-card.vision { background: #eef4ec; border-color: #cfe0c8; }
  .prob-card.clause { background: #eef1f6; border-color: #cdd6e4; }
  .prob-card.date { background: #faf6ee; border-color: #e7dcc4; }
  .prob-card .val.sm { font-size: 12.5pt; padding-top: 5px; }
  .field { margin: 7px 0; }
  .field .k { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 8.4pt; text-transform: uppercase; letter-spacing: 0.7px; color: #1a3a6b; display: block; margin-bottom: 1px; }
  .why { background: #f7f4ec; border-left: 4px solid #b8923a; padding: 9px 12px; margin: 10px 0; }
  .why .k { color: #8a6d24; }
  .footer-note { margin-top: 6px; font-size: 8.6pt; color: #8a8f99; }
"""


def _cover(spec: dict) -> str:
    return f"""<section class="cover">
  <div class="kicker">The Pope System &middot; Pre-Consensus, Calibrated, Falsifiable</div>
  <h1>{_inline(spec.get('title', 'Where Scarcity Migrates Next'))}</h1>
  <div class="sub">{_inline(spec.get('subtitle', ''))}</div>
  <div class="spine"><strong>Thesis spine:</strong> Frontier &rarr; Capability &rarr; Dependency graph &rarr; Supply elasticity &rarr; Demand &rarr; Capital &rarr; Pricing &rarr; Policy &rarr; Outcomes. Rent accrues to the inelastic input. The edge is naming where the constraint moves before pricing catches up.</div>
  <div class="meta">
    Area: {_inline(spec.get('domain', 'any'))} &nbsp;&bull;&nbsp; Horizon: {_inline(spec.get('horizon', ''))}<br>
    Method: generate wide and disruptive, then gate strict. Each call names the needle, not the theme.<br>
    Two probabilities per call: directional vision, and the strict dated clause scored at resolution.<br>
    Status: hardened candidates (survived the adversarial refute pass). Drafted {_inline(spec.get('date', ''))}.
  </div>
</section>"""


def _summary_table(spec: dict) -> str:
    rows = []
    for t in spec["theses"]:
        rows.append(
            f'<tr><td>{_inline(t.get("id",""))}</td>'
            f'<td>{_inline(t.get("boom",""))}</td>'
            f'<td>{_inline(t.get("needle_short", t.get("needle","")[:120]))}</td>'
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
  <h2>The board: {len(spec['theses'])} hardened calls</h2>
  {syn}
  <h3>At a glance</h3>
  <table><thead><tr>
    <th style="width:5%">#</th><th style="width:28%">The boom</th><th style="width:37%">Binding constraint (the needle)</th>
    <th class="num" style="width:10%">Vision&nbsp;P</th><th class="num" style="width:10%">Clause&nbsp;P</th><th class="num" style="width:10%">Resolves</th>
  </tr></thead><tbody>{''.join(rows)}</tbody></table>
  <p class="small muted">Vision P = strength of the structural case. Clause P = calibrated odds the exact dated clause resolves true, scored with Brier. The gap is the honest timing and measurement tax, not timidity.</p>
</section>"""


def _thesis(t: dict) -> str:
    cards = f"""<div class="prob-band">
    <div class="prob-card vision"><div class="label">Directional vision</div><div class="val">{_pct(t.get('vision_p'))}</div></div>
    <div class="prob-card clause"><div class="label">Strict clause</div><div class="val">{_pct(t.get('clause_p'))}</div></div>
    <div class="prob-card date"><div class="label">Resolves</div><div class="val sm">{_inline(t.get('resolves',''))}</div></div>
  </div>"""
    body = "\n".join(
        [
            f'<p>{_inline(t.get("structural",""))}</p>',
            _field("Why it is pre-consensus", t.get("pre_consensus", "")),
            _field("Honest price channel", t.get("price_channel", "")),
            _field("The needle", t.get("needle", "")),
            _field("Leading metric", t.get("metric", "")),
            _field("Kill-criterion", t.get("kill", "")),
            _field("Refute check (survived)", t.get("refute", "")),
            _field("Why this call earned a place", t.get("why", ""), kind="why"),
        ]
    )
    if t.get("subtitle"):
        sub_html = _inline(t["subtitle"])
    else:
        sub_html = (
            f'The boom: {_inline(t.get("boom",""))} &middot; '
            f'Domain: {_inline(t.get("domain",""))}'
        )
    return f"""<section class="thesis">
  <div class="thesis-head"><h2>{_inline(t.get('id',''))} &middot; {_inline(t.get('headline',''))}</h2><span class="id">{_inline(t.get('id',''))}</span></div>
  <p class="muted small">{sub_html}</p>
  {cards}
  {body}
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
  <h2>Seeds considered and not promoted</h2>
  <p>Cleared the physical-constraint test but failed on investability or on the price channel. Logged because the discipline is to surface what was cut.</p>
  <table><thead><tr><th style="width:24%">Seed</th><th style="width:40%">Physical case</th><th style="width:36%">Why not promoted</th></tr></thead>
  <tbody>{rows}</tbody></table>
  <p class="footer-note">Generated by the Pope System. Each call is a forward instrument: resolution date and kill-criterion fixed at creation, superseded never edited, clause probability scored with Brier at resolution.</p>
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
