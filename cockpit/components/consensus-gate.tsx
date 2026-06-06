// Consensus gate (Phase 5, component 7 — THE GATE). Server-rendered SVG, no client JS.
// Shows the one number the thesis hinges on: modeled fair premium vs market-implied premium for
// the inelastic consumable layer over the elastic sequencer. The gap between them IS the edge.
import type { ConsensusRow } from "@/lib/db";

const VERDICT: Record<string, { label: string; cls: string; blurb: string }> = {
  edge: {
    label: "EDGE — not priced in",
    cls: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
    blurb: "The model sees more consumable-scarcity rent than the market prices.",
  },
  edge_low_conf: {
    label: "EDGE (LOW-CONFIDENCE)",
    cls: "bg-amber-500/20 text-amber-200 border-amber-500/40",
    blurb:
      "The band clears the bar, but on a P/S LEVEL alone — not an expectation. A high multiple already " +
      "prices growth/margin, so this can read 'cheap' exactly when the market correctly prices the moat " +
      "eroding. Low-confidence by construction (redteam #5): never alone enough to flip a bet — a " +
      "forward-estimates or short-interest leg is the next rung.",
  },
  priced_in: {
    label: "NO EDGE — priced in",
    cls: "bg-amber-500/20 text-amber-300 border-amber-500/40",
    blurb: "The market already prices the constraint migration (or more). No pre-consensus edge.",
  },
  inconclusive: {
    label: "INCONCLUSIVE",
    cls: "bg-slate-500/20 text-slate-300 border-slate-500/40",
    blurb: "The delta band straddles the threshold. Collect more signal before betting.",
  },
};

export function ConsensusGate({ c }: { c: ConsensusRow | null }) {
  if (!c)
    return (
      <div className="flex min-h-24 items-center justify-center rounded-md border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
        No consensus read yet. Run: python -m engine.cli consensus-score
      </div>
    );

  const v = VERDICT[c.verdict] ?? VERDICT.inconclusive;

  // Axis: relative P/S premium of consumable over sequencer. 1.0 = parity.
  const W = 940;
  const H = 132;
  const padL = 56;
  const padR = 24;
  const axisY = 64;
  const lo = 0.8;
  const hi = Math.max(3.0, c.r_fair + 0.4, c.delta_ci_high + c.r_market + 0.2);
  const xOf = (val: number) =>
    padL + ((val - lo) / (hi - lo)) * (W - padL - padR);

  const xParity = xOf(1.0);
  const xMarket = xOf(c.r_market);
  const xFair = xOf(c.r_fair);
  // The delta gap lives between market and fair; shade the 80% CI around the fair anchor.
  const xCiLo = xOf(c.r_market + c.delta_ci_low);
  const xCiHi = xOf(c.r_market + c.delta_ci_high);

  const edge = c.verdict === "edge";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <span className="text-xs text-muted-foreground">Consensus delta</span>
          <span
            className={`font-mono text-2xl font-semibold ${
              edge ? "text-emerald-400" : "text-foreground"
            }`}
          >
            {c.delta_median > 0 ? "+" : ""}
            {c.delta_median.toFixed(2)}×
          </span>
          <span className="text-xs text-muted-foreground">
            80% CI [{c.delta_ci_low.toFixed(2)}, {c.delta_ci_high.toFixed(2)}] {c.delta_unit} ·
            P(&gt;0) {Math.round(c.p_positive * 100)}%
          </span>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-medium ${v.cls}`}>
          {v.label}
        </span>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
           aria-label="modeled vs priced-in relative premium for the consumable layer">
        {/* axis */}
        <line x1={padL} y1={axisY} x2={W - padR} y2={axisY} stroke="#334155" strokeWidth={1.5} />
        {[1.0, 1.5, 2.0, 2.5, 3.0].filter((t) => t >= lo && t <= hi).map((t) => (
          <g key={t}>
            <line x1={xOf(t)} y1={axisY - 4} x2={xOf(t)} y2={axisY + 4} stroke="#475569" strokeWidth={1} />
            <text x={xOf(t)} y={axisY + 20} fill="#64748b" fontSize={10} textAnchor="middle"
                  fontFamily="monospace">
              {t.toFixed(1)}×
            </text>
          </g>
        ))}
        <text x={padL} y={axisY - 44} fill="#64748b" fontSize={10}>
          consumable P/S ÷ sequencer P/S  (1.0× = parity; higher = market pays up for the consumable)
        </text>

        {/* parity reference */}
        <line x1={xParity} y1={axisY - 28} x2={xParity} y2={axisY + 8} stroke="#475569"
              strokeWidth={1} strokeDasharray="3 3" />

        {/* the delta gap = the edge, shaded with its 80% CI */}
        <rect x={Math.min(xCiLo, xCiHi)} y={axisY - 14} width={Math.abs(xCiHi - xCiLo)} height={28}
              fill={edge ? "#34d39922" : "#64748b22"} rx={3} />
        <line x1={xMarket} y1={axisY} x2={xFair} y2={axisY}
              stroke={edge ? "#34d399" : "#94a3b8"} strokeWidth={3} />

        {/* market marker (priced in) */}
        <g>
          <circle cx={xMarket} cy={axisY} r={6} fill="#fbbf24" stroke="#0f172a" strokeWidth={1.5} />
          <text x={xMarket} y={axisY - 16} fill="#fbbf24" fontSize={11} textAnchor="middle"
                fontWeight={700}>
            priced in {c.r_market.toFixed(2)}×
          </text>
        </g>

        {/* fair marker (modeled) */}
        <g>
          <circle cx={xFair} cy={axisY} r={6} fill="#34d399" stroke="#0f172a" strokeWidth={1.5} />
          <text x={xFair} y={axisY + 38} fill="#34d399" fontSize={11} textAnchor="middle"
                fontWeight={700}>
            modeled fair ~{c.r_fair.toFixed(1)}×
          </text>
        </g>
      </svg>

      <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
        <span>
          {c.consumable_sym} (consumable) P/S{" "}
          <span className="font-mono text-foreground">{c.ps_consumable.toFixed(1)}</span>
        </span>
        <span>
          {c.sequencer_sym} (sequencer) P/S{" "}
          <span className="font-mono text-foreground">{c.ps_sequencer.toFixed(1)}</span>
        </span>
        <span>as-of {c.as_of}</span>
        <span>edge threshold {c.threshold.toFixed(1)}×</span>
      </div>

      <p className="text-xs leading-relaxed text-muted-foreground">
        {v.blurb}{" "}
        {edge && (
          <span className="text-foreground">
            But the market&apos;s discount aligns with this thesis&apos; own kill-criterion (rising
            substitutability) — so the open Decision asks: real mispricing, or is the market right that
            the moat is dissolving?
          </span>
        )}
      </p>
    </div>
  );
}
