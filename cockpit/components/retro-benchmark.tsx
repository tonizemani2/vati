// Retrodiction benchmark (Phase 6 — the "are we real" gate). Server-rendered, no client JS.
// The §8 corpus run point-in-time with the method FROZEN: does it rediscover winners AND reject
// fizzles? The fizzle denominator is the test — a method that only retrodicts winners has learned
// nothing about its false-positive rate. Per-case fire/silent + the precision/recall scoreboard.
import type { RetroRow, RetroScore } from "@/lib/db";

function pct(x: number) {
  return `${Math.round(x * 100)}%`;
}

function fmtSigma(s: number | null): string {
  if (s === null) return "—";
  if (Math.abs(s) >= 1e4) return "≫k";
  return `${s.toFixed(1)}σ`;
}

const VERDICT: Record<string, { label: string; cls: string }> = {
  fired: { label: "⚡ fired", cls: "text-emerald-400" },
  silent: { label: "silent", cls: "text-slate-400" },
  not_capturable: { label: "reject · not capturable", cls: "text-slate-400" },
  insufficient_data: { label: "reject · thin data", cls: "text-slate-400" },
};

export function RetroBenchmark({
  cases,
  score,
}: {
  cases: RetroRow[];
  score: RetroScore | null;
}) {
  if (!score || cases.length === 0)
    return (
      <div className="flex min-h-24 items-center justify-center rounded-md border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
        No benchmark run yet. Run: python -m engine.cli retro-run
      </div>
    );

  const winners = cases.filter((c) => c.outcome === 1);
  const fizzles = cases.filter((c) => c.outcome === 0);
  const beats =
    score.brier_model !== null &&
    score.brier_base !== null &&
    score.brier_model < score.brier_base;

  // 2×2 confusion: fired/silent × winner/fizzle. The off-diagonals are the honest failures.
  const fired = (cs: RetroRow[]) => cs.filter((c) => c.verdict === "fired").length;
  const tp = fired(winners);
  const fn = winners.length - tp;
  const fp = fired(fizzles);
  const tn = fizzles.length - fp;

  const Cell = ({
    n,
    label,
    good,
  }: {
    n: number;
    label: string;
    good: boolean;
  }) => (
    <div
      className={`rounded-md border p-3 text-center ${
        good ? "border-emerald-500/30 bg-emerald-500/5" : "border-amber-500/30 bg-amber-500/5"
      }`}
    >
      <div className={`font-mono text-2xl ${good ? "text-emerald-400" : "text-amber-400"}`}>
        {n}
      </div>
      <div className="text-[11px] leading-tight text-muted-foreground">{label}</div>
    </div>
  );

  return (
    <div className="space-y-5">
      {/* headline scoreboard */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          ["Precision", pct(score.precision), "winner | fired", score.lift > 1],
          ["Recall", pct(score.recall), "fired | winner", score.recall >= 0.6],
          ["Specificity", pct(score.specificity), "reject | fizzle", score.specificity >= 0.6],
          [
            "Lead time",
            score.median_lead_months !== null ? `${score.median_lead_months}mo` : "—",
            "before consensus",
            (score.median_lead_months ?? 0) > 0,
          ],
        ].map(([k, v, sub, good]) => (
          <div key={k as string} className="rounded-md border p-3">
            <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
              {k as string}
            </div>
            <div
              className={`font-mono text-2xl ${good ? "text-emerald-400" : "text-foreground"}`}
            >
              {v as string}
            </div>
            <div className="text-[11px] text-muted-foreground">{sub as string}</div>
          </div>
        ))}
      </div>

      {/* the two honest numbers: lift over base rate, Brier vs baseline */}
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
        <span>
          base rate (winners){" "}
          <span className="font-mono text-foreground">{pct(score.base_rate)}</span> ({score.winners}/
          {score.n})
        </span>
        <span>
          lift{" "}
          <span className={`font-mono ${score.lift > 1 ? "text-emerald-400" : "text-foreground"}`}>
            {score.lift.toFixed(2)}×
          </span>
        </span>
        <span>
          Brier{" "}
          <span className={`font-mono ${beats ? "text-emerald-400" : "text-foreground"}`}>
            {score.brier_model?.toFixed(3)}
          </span>{" "}
          vs {score.brier_base?.toFixed(3)} baseline {beats ? "✅" : ""}
        </span>
      </div>

      {/* confusion 2×2 — the fizzle denominator made visible */}
      <div>
        <div className="mb-2 grid grid-cols-[5rem_1fr_1fr] gap-2 text-[11px] text-muted-foreground">
          <span />
          <span className="text-center">truth: winner</span>
          <span className="text-center">truth: fizzle</span>
        </div>
        <div className="grid grid-cols-[5rem_1fr_1fr] gap-2">
          <span className="flex items-center text-[11px] text-muted-foreground">⚡ fired</span>
          <Cell n={tp} label="rediscovered winners" good={tp > 0} />
          <Cell n={fp} label="false positives" good={fp === 0} />
          <span className="flex items-center text-[11px] text-muted-foreground">silent / reject</span>
          <Cell n={fn} label="missed winners" good={fn === 0} />
          <Cell n={tn} label="rejected fizzles" good={tn > 0} />
        </div>
      </div>

      {/* per-case detail */}
      <div className="overflow-x-auto rounded-md border">
        <table className="w-full text-sm">
          <thead className="bg-card text-xs text-muted-foreground">
            <tr className="border-b">
              <th className="px-3 py-2 text-left font-medium">case</th>
              <th className="px-3 py-2 text-left font-medium">as-of</th>
              <th className="px-3 py-2 text-left font-medium">method verdict</th>
              <th className="px-3 py-2 text-right font-medium">capability</th>
              <th className="px-3 py-2 text-right font-medium">attention (decoy)</th>
            </tr>
          </thead>
          <tbody>
            {[...winners, ...fizzles].map((c) => {
              const v = VERDICT[c.verdict] ?? VERDICT.silent;
              return (
                <tr key={c.key} className="border-b last:border-0">
                  <td className="px-3 py-2">
                    <span className="mr-2">{c.correct ? "✅" : "❌"}</span>
                    <span className="text-foreground">{c.label}</span>
                    <span
                      className={`ml-2 rounded px-1.5 py-0.5 text-[10px] ${
                        c.category === "winner"
                          ? "bg-sky-500/15 text-sky-300"
                          : "bg-rose-500/15 text-rose-300"
                      }`}
                    >
                      {c.category}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                    {c.signal_date.slice(0, 4)}
                  </td>
                  <td className={`px-3 py-2 ${v.cls}`}>
                    {v.label}
                    {c.lead_months !== null && (
                      <span className="ml-2 text-[11px] text-muted-foreground">
                        +{c.lead_months}mo lead
                      </span>
                    )}
                  </td>
                  <td
                    className={`px-3 py-2 text-right font-mono text-xs ${
                      c.cap_fired === 1 ? "text-emerald-400" : "text-muted-foreground"
                    }`}
                  >
                    {fmtSigma(c.cap_surprise_sigma)}
                  </td>
                  <td
                    className={`px-3 py-2 text-right font-mono text-xs ${
                      c.att_fired === 1 ? "text-amber-400" : "text-muted-foreground"
                    }`}
                  >
                    {fmtSigma(c.att_surprise_sigma)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="text-xs leading-relaxed text-muted-foreground">
        The method judges the <span className="text-foreground">capability</span> curve
        (mechanism-backed: compute, cost-affordability, throughput, production) on data ≤ the as-of
        date — never the <span className="text-foreground">attention</span> decoy (publications /
        search). Honest results are kept, not tuned away:{" "}
        <span className="text-foreground">AI compute</span> is a real miss (by its 2017 cutoff the
        2012 acceleration was already in-trend — the edge was ~2013, a lead-time lesson);{" "}
        <span className="text-foreground">metaverse</span> attention fires 12.5σ yet is correctly
        rejected (no capability curve). GLP-1, FSD-timeline and EUV/ASML are logged as gaps the
        annual acceleration detector can&apos;t adjudicate — not faked into the score.
      </p>
    </div>
  );
}
