#!/usr/bin/env python3
"""Pope CAPTURE renderer: a value-capture board (JSON) -> styled HTML -> PDF.

The forecast→revenue counterpart to engine/pope/render.py. Same deterministic, no-LLM, no-dep,
headless-Chrome pipeline and the same house style, but in the canonical indigo brand and laid out for
the capture board: a cover + the ranked do-this-week shortlist, then one hardened page per call (named
targets, the ask, the money path, and the adversarial money-path refute).

Usage:
    python -m engine.pope.capture_render <board.json> <out_basepath>
    # writes <out_basepath>.html and <out_basepath>.pdf

Board JSON shape (the pope-capture workflow output, plus optional title/domain/date):
    {
      "title": "...", "domain": "...", "date": "2026-06-19",
      "synthesis": "the single best, most reachable opportunity and why",
      "shortlist": [ {rank, headline, target_org, first_move, value_mechanism, expected_value, effort} ],
      "this_week": [ "action 1", ... ],
      "plans": [ {headline, verdict, why, targets[], the_ask, value_mechanism, who_pays, our_angle,
                  proof_to_show, instrument, first_move, checkpoints[], disqualifier, confidence,
                  refute: {money_path_holds, refutation, fixes, hardened_ask, realistic_ticket,
                           revised_verdict, revised_confidence} } ]
    }
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
def _inline(text) -> str:
    if text is None:
        return ""
    raw = (
        str(text)
        .replace("—", " - ").replace("–", "-").replace("‑", "-")
        .replace("−", "-").replace("…", "...")
    )
    out = html.escape(raw)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", out)
    return out


def _field(label: str, text, kind: str = "field") -> str:
    if not text:
        return ""
    klass = {"why": "why", "ask": "ask"}.get(kind, "field")
    return f'<div class="{klass}"><span class="k">{html.escape(label)}</span>\n{_inline(text)}</div>'


# Self-hosted Gt Standard from the live site CDN so the PDF matches the site exactly.
FONT_CSS = """
  @font-face{font-family:'Gt Standard';font-weight:400;font-style:normal;font-display:swap;src:url('https://cdn.prod.website-files.com/68907168d294618a86ec6518/689b297557d89256a5697b72_GT-Standard-L-Standard-Regular.woff2') format('woff2');}
  @font-face{font-family:'Gt Standard';font-weight:500;font-style:normal;font-display:swap;src:url('https://cdn.prod.website-files.com/68907168d294618a86ec6518/689b2975a12fc701f9f074a9_GT-Standard-L-Standard-Medium.woff2') format('woff2');}
  @font-face{font-family:'Gt Standard Mono';font-weight:500;font-style:normal;font-display:swap;src:url('https://cdn.prod.website-files.com/68907168d294618a86ec6518/689b29750af0e8f994b5a45e_GT-Standard-Mono-Narrow-Medium.woff2') format('woff2');}
"""

# Indigo brand (the canonical content palette), memo discipline.
CSS = FONT_CSS + """
  :root { --page:#fbfaf7; --paper:#f2f0ea; --ink:#151515; --text:#33312d; --mut:#706c65; --quiet:#9b958d; --line:#d9d4cc; --line-strong:#151515; --accent:#6d6afc; --accent-soft:#eeedff; --pass:#9b958d; }
  @page { size: Letter; margin: 18mm 17mm 18mm 17mm;
    @bottom-left { content: "Vaticinus - Capture"; font-family: 'Gt Standard Mono', monospace; font-size: 7.5pt; color: #a7a19a; }
    @bottom-center { content: counter(page); font-family: 'Gt Standard Mono', monospace; font-size: 8pt; color: #a7a19a; } }
  html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  body { font-family: 'Gt Standard', Arial, sans-serif; font-weight: 400; color: var(--text); line-height: 1.48; font-size: 10pt; margin: 0; background: var(--page); }
  h1, h2, h3, h4 { font-family: 'Gt Standard', Arial, sans-serif; font-weight: 500; color: var(--ink); line-height: 1.1; letter-spacing: 0; }
  h1 { font-size: 32pt; margin: 0; max-width: 650px; }
  .mono { font-family: 'Gt Standard Mono', monospace; }
  .eyebrow { font-family: 'Gt Standard Mono', monospace; font-size: 8pt; letter-spacing: 0.14em; text-transform: uppercase; color: var(--accent); }
  .cover { border-bottom: 2px solid var(--line-strong); padding-bottom: 14px; margin-bottom: 22px; }
  .cover .masthead { display: flex; justify-content: space-between; font-family: 'Gt Standard Mono', monospace; font-size: 8pt; color: var(--mut); letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 26px; }
  .cover .frame { margin-top: 14px; color: var(--text); max-width: 640px; font-size: 11pt; }
  .meta { display: flex; gap: 26px; margin-top: 16px; font-family: 'Gt Standard Mono', monospace; font-size: 8pt; color: var(--mut); }
  .meta b { color: var(--ink); font-weight: 500; }
  h2.sec { font-size: 13pt; margin: 26px 0 10px; padding-bottom: 5px; border-bottom: 1px solid var(--line); }
  table { width: 100%; border-collapse: collapse; font-size: 8.6pt; margin-top: 6px; }
  th { text-align: left; font-family: 'Gt Standard Mono', monospace; font-size: 7pt; text-transform: uppercase; letter-spacing: 0.08em; color: var(--mut); border-bottom: 1px solid var(--line-strong); padding: 4px 8px 4px 0; }
  td { padding: 6px 8px 6px 0; border-bottom: 1px solid var(--line); vertical-align: top; }
  td .rank { font-family: 'Gt Standard Mono', monospace; color: var(--accent); }
  .pill { display: inline-block; font-family: 'Gt Standard Mono', monospace; font-size: 7pt; text-transform: uppercase; letter-spacing: 0.08em; padding: 2px 7px; border-radius: 999px; }
  .pill.pursue { background: var(--accent); color: #fff; }
  .pill.pass { background: var(--paper); color: var(--pass); border: 1px solid var(--line); }
  .pill.eff { background: var(--paper); color: var(--mut); }
  .this-week { margin: 8px 0 0; padding: 0; list-style: none; counter-reset: tw; }
  .this-week li { counter-increment: tw; padding: 7px 0 7px 30px; position: relative; border-bottom: 1px solid var(--line); }
  .this-week li::before { content: counter(tw); position: absolute; left: 0; top: 6px; font-family: 'Gt Standard Mono', monospace; font-size: 8pt; color: #fff; background: var(--accent); width: 18px; height: 18px; border-radius: 50%; text-align: center; line-height: 18px; }
  .plan { page-break-before: always; }
  .plan .head { display: flex; justify-content: space-between; align-items: baseline; gap: 16px; border-bottom: 1px solid var(--line); padding-bottom: 8px; }
  .plan h3 { font-size: 16pt; max-width: 560px; }
  .field, .why, .ask { margin: 11px 0; }
  .field .k, .why .k, .ask .k { display: block; font-family: 'Gt Standard Mono', monospace; font-size: 7pt; text-transform: uppercase; letter-spacing: 0.09em; color: var(--mut); margin-bottom: 3px; }
  .ask { background: var(--accent-soft); border-left: 3px solid var(--accent); padding: 10px 12px; }
  .targets { margin: 10px 0; }
  .target { border: 1px solid var(--line); border-left: 3px solid var(--accent); border-radius: 4px; padding: 9px 11px; margin-bottom: 8px; }
  .target .org { font-weight: 500; color: var(--ink); }
  .target .role { font-family: 'Gt Standard Mono', monospace; font-size: 8pt; color: var(--mut); }
  .target .det { margin-top: 4px; font-size: 9pt; }
  .target .det b { font-weight: 500; color: var(--ink); }
  .refute { margin-top: 14px; border: 1px solid var(--line-strong); border-radius: 4px; padding: 11px 13px; background: var(--paper); }
  .refute .rk { font-family: 'Gt Standard Mono', monospace; font-size: 7.5pt; text-transform: uppercase; letter-spacing: 0.09em; color: var(--ink); margin-bottom: 6px; }
  .grid2 { display: flex; gap: 22px; }
  .grid2 > div { flex: 1; }
"""


def _meta_row(spec: dict) -> str:
    bits = []
    if spec.get("domain"):
        bits.append(f"<span>Domain<br><b>{_inline(spec['domain'])}</b></span>")
    bits.append(f"<span>Calls<br><b>{len(spec.get('plans') or [])}</b></span>")
    pursue = sum(1 for p in (spec.get("plans") or []) if _verdict(p) == "PURSUE")
    bits.append(f"<span>Pursue<br><b>{pursue}</b></span>")
    if spec.get("date"):
        bits.append(f"<span>Dated<br><b>{_inline(spec['date'])}</b></span>")
    return '<div class="meta">' + "".join(bits) + "</div>"


def _cover(spec: dict) -> str:
    title = spec.get("title") or "Value-capture board"
    return (
        '<section class="cover">'
        '<div class="masthead"><span>Vaticinus</span><span>Forecast to revenue</span></div>'
        '<div class="eyebrow">Capture board</div>'
        f"<h1>{_inline(title)}</h1>"
        + (f'<div class="frame">{_inline(spec["synthesis"])}</div>' if spec.get("synthesis") else "")
        + _meta_row(spec)
        + "</section>"
    )


def _shortlist(spec: dict) -> str:
    rows = spec.get("shortlist") or []
    if not rows:
        return ""
    body = []
    for r in rows:
        eff = (r.get("effort") or "").lower()
        body.append(
            "<tr>"
            f'<td><span class="rank">{html.escape(str(r.get("rank", "")))}</span></td>'
            f"<td><b>{_inline(r.get('headline'))}</b></td>"
            f"<td>{_inline(r.get('target_org'))}</td>"
            f"<td>{_inline(r.get('first_move'))}</td>"
            f"<td>{_inline(r.get('expected_value'))}</td>"
            f'<td><span class="pill eff">{html.escape(eff)}</span></td>'
            "</tr>"
        )
    return (
        '<h2 class="sec">Do-this-week shortlist</h2>'
        "<table><thead><tr><th>#</th><th>Call</th><th>Target</th><th>First move</th>"
        "<th>Expected value</th><th>Effort</th></tr></thead><tbody>"
        + "".join(body) + "</tbody></table>"
    )


def _this_week(spec: dict) -> str:
    acts = spec.get("this_week") or []
    if not acts:
        return ""
    items = "".join(f"<li>{_inline(a)}</li>" for a in acts)
    return f'<h2 class="sec">Next 7 days</h2><ol class="this-week">{items}</ol>'


def _verdict(plan: dict) -> str:
    ref = plan.get("refute") or {}
    return (ref.get("revised_verdict") or plan.get("verdict") or "").upper()


def _targets(plan: dict) -> str:
    rows = plan.get("targets") or []
    if not rows:
        return ""
    cards = []
    for t in rows:
        person = f" - {_inline(t['person'])}" if t.get("person") else ""
        cards.append(
            '<div class="target">'
            f'<div class="org">{_inline(t.get("org"))}<span class="role"> &nbsp;{_inline(t.get("role"))}{person}</span></div>'
            f'<div class="det"><b>Why them:</b> {_inline(t.get("care_about"))}</div>'
            f'<div class="det"><b>Reach:</b> {_inline(t.get("reach"))}</div>'
            "</div>"
        )
    return '<div class="targets"><span class="k mono" style="font-size:7pt;color:#706c65;text-transform:uppercase;letter-spacing:.09em;">Targets</span>' + "".join(cards) + "</div>"


def _refute(plan: dict) -> str:
    r = plan.get("refute") or {}
    if not r:
        return ""
    holds = r.get("money_path_holds")
    verdict = "holds" if holds else "does not hold as stated"
    parts = [f'<div class="rk">Adversarial money-path test - {verdict}</div>']
    parts.append(_field("Strongest refutation", r.get("refutation")))
    parts.append(_field("Fix or kill", r.get("fixes")))
    parts.append(_field("Hardened ask", r.get("hardened_ask"), kind="ask") if r.get("hardened_ask") else "")
    parts.append(_field("Realistic ticket", r.get("realistic_ticket")))
    return '<div class="refute">' + "".join(p for p in parts if p) + "</div>"


def _plan(plan: dict) -> str:
    verdict = _verdict(plan)
    pill_cls = "pursue" if verdict == "PURSUE" else "pass"
    conf = (plan.get("refute") or {}).get("revised_confidence") or plan.get("confidence") or ""
    head = (
        '<div class="head">'
        f"<h3>{_inline(plan.get('headline'))}</h3>"
        f'<span class="pill {pill_cls}">{html.escape(verdict or "?")}</span>'
        "</div>"
    )
    left = [
        _field("Why capturable", plan.get("why"), kind="why"),
        _targets(plan),
        _field("The ask", plan.get("the_ask"), kind="ask"),
    ]
    right = [
        _field("Value mechanism", plan.get("value_mechanism")),
        _field("Who pays", plan.get("who_pays")),
        _field("Our angle", plan.get("our_angle")),
        _field("Proof to show", plan.get("proof_to_show")),
        _field("Instrument", plan.get("instrument")),
    ]
    tail = [
        _field("First move (this week)", plan.get("first_move")),
        _field("Checkpoints", " | ".join(plan.get("checkpoints") or [])),
        _field("Disqualifier", plan.get("disqualifier")),
        _field("Confidence", conf),
    ]
    body = (
        '<div class="grid2">'
        f'<div>{"".join(x for x in left if x)}</div>'
        f'<div>{"".join(x for x in right if x)}</div>'
        "</div>"
        + "".join(x for x in tail if x)
        + _refute(plan)
    )
    return f'<section class="plan">{head}{body}</section>'


def build_html(spec: dict) -> str:
    plans = spec.get("plans") or []
    parts = [_cover(spec), _shortlist(spec), _this_week(spec)]
    parts += [_plan(p) for p in plans]
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<style>{CSS}</style></head><body>" + "".join(parts) + "</body></html>"
    )


def _find_chrome() -> str | None:
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chromium-browser"),
    ]
    return next((c for c in candidates if c and os.path.exists(c)), None)


def render(spec_path: str, out_base: str) -> None:
    with open(spec_path, "r", encoding="utf-8") as fh:
        spec = json.load(fh)
    if not spec.get("plans"):
        raise SystemExit("capture board has no plans")

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
         f"--print-to-pdf={os.path.abspath(pdf_path)}", f"file://{os.path.abspath(html_path)}"],
        check=True, capture_output=True,
    )
    print(f"wrote {pdf_path}  ({os.path.getsize(pdf_path)//1024} KB, {len(spec['plans'])} plans)")


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("usage: python -m engine.pope.capture_render <board.json> <out_basepath>", file=sys.stderr)
        return 1
    render(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
