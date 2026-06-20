"""Inline-SVG chart primitives for the Pope renderers - charts as evidence, not decoration.

VOICE.md asks every research note for real visuals (trendlines, bottleneck stacks, supply/demand gaps,
dependency graphs). render.py shipped with none. This is the shared, dependency-free toolkit: pure
functions that return self-contained SVG strings (inline styles + attributes, no external CSS), sized
for the print column, in the canonical indigo brand. Both render.py and capture_render.py import these.

All functions degrade to "" on empty/insufficient data so a spec without chart data renders cleanly.
$0, stdlib only.
"""
from __future__ import annotations

import html

INK = "#151515"
TEXT = "#33312d"
MUT = "#706c65"
LINE = "#d9d4cc"
ACCENT = "#6d6afc"
ACCENT_SOFT = "#eeedff"
LOSS = "#c2604f"  # the gap / shortfall / loser side


def _esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def _fnum(v) -> str:
    """Compact human number for axis/value labels."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return _esc(v)
    a = abs(v)
    if a >= 1_000_000_000:
        return f"{v/1e9:.1f}B"
    if a >= 1_000_000:
        return f"{v/1e6:.1f}M"
    if a >= 1_000:
        return f"{v/1e3:.1f}K"
    if a == int(a):
        return str(int(v))
    return f"{v:.2f}"


def _caption(text: str, w: int) -> str:
    if not text:
        return ""
    return (f'<text x="0" y="0" font-family="Gt Standard Mono, monospace" font-size="9" '
            f'fill="{MUT}">{_esc(text)}</text>')


def _frame(inner: str, w: int, h: int, caption: str = "") -> str:
    cap_h = 16 if caption else 0
    cap = (f'<g transform="translate(0,{h+12})">{_caption(caption, w)}</g>') if caption else ""
    return (
        f'<svg class="vf-chart" viewBox="0 0 {w} {h+cap_h}" width="100%" '
        f'preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg" '
        f'font-family="Gt Standard, Arial, sans-serif">{inner}{cap}</svg>'
    )


def trendline(values, *, width: int = 520, height: int = 96, caption: str = "",
              labels: list | None = None) -> str:
    """An area + line sparkline-style trendline over an ordered series (the dated base rate)."""
    vals = [float(v) for v in (values or []) if v is not None]
    if len(vals) < 2:
        return ""
    pad = 6
    w, h = width, height
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    n = len(vals)
    def x(i): return pad + (w - 2 * pad) * i / (n - 1)
    def y(v): return pad + (h - 2 * pad) * (1 - (v - lo) / span)
    pts = [(x(i), y(v)) for i, v in enumerate(vals)]
    line = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
    area = (f"M{pts[0][0]:.1f},{h-pad:.1f} L" + line.replace(" ", " L")
            + f" L{pts[-1][0]:.1f},{h-pad:.1f} Z")
    last = pts[-1]
    end_lbl = ""
    if labels and len(labels) == n:
        end_lbl = (f'<text x="{x(0):.1f}" y="{h-1:.1f}" font-size="8.5" fill="{MUT}" '
                   f'font-family="Gt Standard Mono, monospace">{_esc(labels[0])}</text>'
                   f'<text x="{w-pad:.1f}" y="{h-1:.1f}" font-size="8.5" fill="{MUT}" '
                   f'text-anchor="end" font-family="Gt Standard Mono, monospace">{_esc(labels[-1])}</text>')
    inner = (
        f'<path d="{area}" fill="{ACCENT_SOFT}" stroke="none"/>'
        f'<polyline points="{line}" fill="none" stroke="{ACCENT}" stroke-width="2" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{last[0]:.1f}" cy="{last[1]:.1f}" r="3" fill="{ACCENT}"/>'
        f'<text x="{last[0]-4:.1f}" y="{last[1]-6:.1f}" text-anchor="end" font-size="9" '
        f'fill="{INK}" font-family="Gt Standard Mono, monospace">{_fnum(vals[-1])}</text>'
        + end_lbl
    )
    return _frame(inner, w, h, caption)


def bar_chart(items, *, width: int = 520, bar_h: int = 22, gap: int = 8, caption: str = "",
              highlight: str | None = None) -> str:
    """Horizontal bars - the bottleneck stack / concentration view. items = [(label, value), ...].
    `highlight` names the label to paint in the loss colour (the binding node)."""
    rows = [(str(l), float(v)) for l, v in (items or []) if v is not None]
    if not rows:
        return ""
    label_w = 150
    track_w = width - label_w - 46
    hi = max(v for _, v in rows) or 1.0
    h = len(rows) * (bar_h + gap)
    parts = []
    for i, (lab, val) in enumerate(rows):
        y = i * (bar_h + gap)
        bw = max(track_w * val / hi, 1)
        col = LOSS if (highlight and lab == highlight) else ACCENT
        parts.append(
            f'<text x="0" y="{y+bar_h*0.7:.0f}" font-size="9.5" fill="{TEXT}">{_esc(lab[:26])}</text>'
            f'<rect x="{label_w}" y="{y}" width="{track_w}" height="{bar_h}" rx="2" fill="#f2f0ea"/>'
            f'<rect x="{label_w}" y="{y}" width="{bw:.1f}" height="{bar_h}" rx="2" fill="{col}"/>'
            f'<text x="{label_w+track_w+6}" y="{y+bar_h*0.7:.0f}" font-size="9" fill="{MUT}" '
            f'font-family="Gt Standard Mono, monospace">{_fnum(val)}</text>'
        )
    return _frame("".join(parts), width, h, caption)


def gap_chart(supply_label: str, supply: float, demand_label: str, demand: float, *,
              width: int = 520, caption: str = "") -> str:
    """Supply-vs-demand gap: two bars on a shared scale with the shortfall shaded."""
    try:
        supply, demand = float(supply), float(demand)
    except (TypeError, ValueError):
        return ""
    label_w = 150
    track_w = width - label_w - 46
    hi = max(supply, demand) or 1.0
    bar_h, gap = 26, 14
    h = 2 * bar_h + gap
    def row(y, lab, val, col):
        bw = max(track_w * val / hi, 1)
        return (
            f'<text x="0" y="{y+bar_h*0.68:.0f}" font-size="9.5" fill="{TEXT}">{_esc(lab[:26])}</text>'
            f'<rect x="{label_w}" y="{y}" width="{track_w}" height="{bar_h}" rx="2" fill="#f2f0ea"/>'
            f'<rect x="{label_w}" y="{y}" width="{bw:.1f}" height="{bar_h}" rx="2" fill="{col}"/>'
            f'<text x="{label_w+track_w+6}" y="{y+bar_h*0.68:.0f}" font-size="9" fill="{MUT}" '
            f'font-family="Gt Standard Mono, monospace">{_fnum(val)}</text>'
        )
    inner = row(0, supply_label, supply, ACCENT) + row(bar_h + gap, demand_label, demand, LOSS)
    return _frame(inner, width, h, caption)


def dependency_chain(nodes, *, width: int = 520, caption: str = "",
                     needle: str | None = None) -> str:
    """A left-to-right chain of boxes joined by arrows - the walk to the inelastic input.
    `needle` names the box to mark as the binding constraint (loss colour, bold)."""
    labels = [str(n) for n in (nodes or []) if n]
    if len(labels) < 2:
        return ""
    n = len(labels)
    arrow = 16
    box_h = 34
    box_w = (width - arrow * (n - 1)) / n
    parts = [
        '<defs><marker id="vfar" markerWidth="7" markerHeight="7" refX="5" refY="3" orient="auto">'
        f'<path d="M0,0 L6,3 L0,6 Z" fill="{MUT}"/></marker></defs>'
    ]
    for i, lab in enumerate(labels):
        x = i * (box_w + arrow)
        is_needle = needle and lab == needle
        fill = ACCENT_SOFT if is_needle else "#fff"
        stroke = LOSS if is_needle else LINE
        sw = 2 if is_needle else 1
        tcol = LOSS if is_needle else INK
        parts.append(
            f'<rect x="{x:.1f}" y="0" width="{box_w:.1f}" height="{box_h}" rx="4" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
            f'<text x="{x+box_w/2:.1f}" y="{box_h/2+3:.0f}" text-anchor="middle" font-size="8.5" '
            f'fill="{tcol}" font-weight="{"600" if is_needle else "400"}">'
            f'{_esc(lab[:16])}</text>'
        )
        if i < n - 1:
            ax = x + box_w
            parts.append(
                f'<line x1="{ax+2:.1f}" y1="{box_h/2:.0f}" x2="{ax+arrow-2:.1f}" y2="{box_h/2:.0f}" '
                f'stroke="{MUT}" stroke-width="1.3" marker-end="url(#vfar)"/>'
            )
    return _frame("".join(parts), width, box_h, caption)
