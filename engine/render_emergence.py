"""Render the emergence layer as a self-contained static HTML page (fork C — "make it land").

A public-facing visual of what the data layer SEES moving right now: across all ~46k OpenAlex concepts,
which research constraints are accelerating (and still early), which are dissolving (rent leaving), and
which dependency EDGES are tightening (the binding constraint migrating onto a specific input). Reads
concept_emergence + concept_edge_shift + the paper→patent reliance overlay. Deterministic, $0, no deps
(one HTML file, unicode sparklines straight from the tables). Writes to research/ — NOT site/ — so it
never touches a deploy or the chat product.

USAGE
  uv run python -m engine.render_emergence                      # -> research/emergence_layer.html
  uv run python -m engine.render_emergence --out path.html
"""
from __future__ import annotations

import argparse
import html
from pathlib import Path

from engine import db, signals

OUT = Path(__file__).resolve().parents[1] / "research" / "emergence_layer.html"

_CSS = """
:root{--bg:#0b0d10;--card:#14181d;--ink:#e9edf2;--mut:#8b97a6;--up:#5ad1a0;--dn:#e06b6b;--line:#242b33}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:56px 28px 96px}
h1{font-size:30px;letter-spacing:-.02em;margin:0 0 6px}
.sub{color:var(--mut);max-width:680px;margin:0 0 8px}
.asof{color:var(--mut);font-size:13px;margin:0 0 40px}
h2{font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:var(--mut);
margin:44px 0 14px;border-bottom:1px solid var(--line);padding-bottom:8px}
table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;color:var(--mut);font-weight:500;padding:8px 10px;font-size:12px}
td{padding:10px;border-top:1px solid var(--line);vertical-align:top}
.name{font-weight:600}.spark{font-size:17px;letter-spacing:1px;color:var(--ink)}
.sig{font-variant-numeric:tabular-nums;font-weight:600}.up{color:var(--up)}.dn{color:var(--dn)}
.mut{color:var(--mut)}.r{text-align:right;font-variant-numeric:tabular-nums}
.arrow{color:var(--mut);padding:0 6px}.foot{color:var(--mut);font-size:12px;margin-top:56px;
border-top:1px solid var(--line);padding-top:16px}
"""


def _esc(s) -> str:
    return html.escape(str(s))


_BARS = "▁▂▃▄▅▆▇█"


def _clean_ramp(spark: str) -> bool:
    """True if the rise is SUSTAINED, not a single final-year spike — for the public visual's credibility.

    A genuine constraint migration shows the last several years elevated; a small-N blip shows only the
    final bar high. Require ≥2 of the last 4 bars in the top third AND the penultimate bar not at floor."""
    levels = [_BARS.index(c) for c in spark if c in _BARS]
    if len(levels) < 5:
        return False
    last4 = levels[-4:]
    return sum(1 for v in last4 if v >= 5) >= 2 and levels[-2] >= 2


def _patent_label(rel: dict | None) -> str:
    if not rel:
        return '<span class="mut">—</span>'
    return f"{rel['n_patents']:,}"


def render(conn) -> str:
    pat = signals._concept_patents()
    moving = conn.execute(
        "SELECT * FROM concept_emergence WHERE fired=1 AND sustained=1 AND dissolving=0 "
        "ORDER BY sustained_sigma DESC LIMIT 40").fetchall()
    leaving = conn.execute(
        "SELECT * FROM concept_emergence WHERE dissolving=1 ORDER BY sustained_sigma DESC LIMIT 12").fetchall()
    try:
        cand = conn.execute(
            "SELECT * FROM concept_edge_shift WHERE fired=1 AND sustained=1 AND dissolving=0 "
            "AND last_share >= 0.05 ORDER BY sustained_sigma DESC LIMIT 200").fetchall()
    except Exception:  # noqa: BLE001 — table may not be built yet
        cand = []
    # de-spike for the public visual: keep only SUSTAINED ramps, not a single final-year jump. A clean
    # rise has ≥2 of its last 4 years in the top third of the sparkline; a blip has just the last bar high.
    tightening = [r for r in cand if _clean_ramp(r["spark"])][:24]
    as_of = moving[0]["as_of"] if moving else "—"

    def _row(r):
        rel = pat.get(r["concept_name"].lower())
        return (f'<tr><td class="name">{_esc(r["concept_name"])}</td>'
                f'<td class="spark up">{_esc(r["spark"])}</td>'
                f'<td class="r sig up">{r["sustained_sigma"]:.1f}σ̄</td>'
                f'<td class="r mut">{r["last_works"]:,}<span class="mut">/{r["last_year"]}</span></td>'
                f'<td class="r">{_patent_label(rel)}</td></tr>')

    moving_rows = "\n".join(_row(r) for r in moving)
    leaving_rows = "\n".join(
        f'<tr><td class="name">{_esc(r["concept_name"])}</td>'
        f'<td class="spark dn">{_esc(r["spark"])}</td>'
        f'<td class="r sig dn">{r["sustained_sigma"]:.1f}σ̄</td>'
        f'<td class="r mut">{r["last_works"]:,}/{r["last_year"]}</td></tr>' for r in leaving)
    edge_rows = "\n".join(
        f'<tr><td class="name">{_esc(r["src_name"])}<span class="arrow">→</span>'
        f'<span class="up">{_esc(r["dst_name"])}</span></td>'
        f'<td class="spark up">{_esc(r["spark"])}</td>'
        f'<td class="r sig up">{r["sustained_sigma"]:.1f}σ̄</td>'
        f'<td class="r mut">{r["last_share"]*100:.0f}%<span class="mut"> of outbound</span></td></tr>'
        for r in tightening)

    edge_section = ""
    if edge_rows:
        edge_section = f"""
    <h2>Constraints migrating — dependency edges tightening</h2>
    <p class="sub">Not the node moving, the <em>link</em>: a reliance whose share is accelerating means the
    binding constraint is concentrating onto that specific upstream input. This is the earliest tell.</p>
    <table><thead><tr><th>reliance (A draws on B)</th><th>trajectory</th><th class="r">accel</th>
    <th class="r">weight now</th></tr></thead><tbody>{edge_rows}</tbody></table>"""

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>The emergence layer</title><style>{_CSS}</style></head><body><div class="wrap">
<h1>The emergence layer</h1>
<p class="sub">Where attention — and with it, the binding constraint — is moving across science right now.
The detector runs a leak-free share-acceleration test on every one of ~46,000 research concepts: a rising
share of world literature is real reorientation, not just more papers. It fires early and goes quiet once
a winner is priced (deep learning reads 5.9σ in 2016, sub-threshold by 2025).</p>
<p class="asof">As of {_esc(as_of)} (the last complete publication year; the provisional trailing year is dropped).</p>

<h2>Accelerating — and still early</h2>
<table><thead><tr><th>concept</th><th>trajectory (yearly share)</th><th class="r">accel</th>
<th class="r">works</th><th class="r">patents citing</th></tr></thead><tbody>{moving_rows}</tbody></table>
{edge_section}
<h2>Rent leaving — share retreating below trend</h2>
<table><thead><tr><th>concept</th><th>trajectory</th><th class="r">accel</th><th class="r">works</th></tr></thead>
<tbody>{leaving_rows or '<tr><td class="mut" colspan="4">none flagged dissolving</td></tr>'}</tbody></table>

<p class="foot">Signal: per-concept / per-edge log-space share-acceleration (engine/detector.py) over the
frozen OpenAlex corpus. Recall lives at the detector; precision is the priced-in gate + dependency-cross
downstream. Acceleration is a where-to-look signal, not a forecast — the tracked calls carry P + interval
+ kill-criterion and are scored at resolution.</p>
</div></body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Render the emergence layer to a static HTML page.")
    ap.add_argument("--out", default=str(OUT), help="output HTML path")
    args = ap.parse_args()
    conn = db.connect()
    page = render(conn)
    conn.close()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out} ({len(page):,} bytes). cost: $0.00")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
