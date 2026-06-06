// Hypothesis engine (component 8 — the generative front-end, "the oracle"). Server-rendered.
// The soul of the system, wired to the gate: divergent, cross-domain constraint-migration theses
// PROPOSED in-session, each forced through the same discipline a forecast obeys and stamped with a
// verdict — survived / parked (un-falsifiable, logged not faked) / killed (refuted). The whole point
// of showing all three is honesty: the engine must kill its own pretty stories and refuse its own
// un-testable ones, or "more soul" is just astrology.
import type { HypothesisRow } from "@/lib/db";

const LENS_LABEL: Record<string, string> = {
  toc: "Theory of Constraints",
  perez: "Techno-economic cycles",
  helmer: "7 Powers",
  arthur: "Increasing returns",
  ricardian: "Ricardian rent",
  inversion: "Inversion",
  analogy: "Cross-domain analogy",
};

const VERDICT: Record<
  string,
  { label: string; ring: string; chip: string; dot: string }
> = {
  promoted: { label: "★ promoted", ring: "border-sky-500/40", chip: "bg-sky-500/15 text-sky-300", dot: "bg-sky-400" },
  survived: { label: "✓ survived", ring: "border-emerald-500/40", chip: "bg-emerald-500/15 text-emerald-300", dot: "bg-emerald-400" },
  parked: { label: "◦ parked", ring: "border-amber-500/40", chip: "bg-amber-500/15 text-amber-300", dot: "bg-amber-400" },
  killed: { label: "✗ killed", ring: "border-rose-500/40 opacity-80", chip: "bg-rose-500/15 text-rose-300", dot: "bg-rose-400" },
};

function count(rows: HypothesisRow[], status: string) {
  return rows.filter((h) => h.status === status).length;
}

export function HypothesisEngine({ hypotheses }: { hypotheses: HypothesisRow[] }) {
  if (hypotheses.length === 0)
    return (
      <div className="flex min-h-24 items-center justify-center rounded-md border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
        No hypotheses yet. Run: python -m engine.cli hypothesis-seed
      </div>
    );

  return (
    <div className="space-y-4">
      {/* the propose → dispose pipe, as a legend */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span className="font-medium text-foreground">propose</span>
        <span>→</span>
        <span>gate</span>
        <span>→</span>
        <span className="flex items-center gap-1.5">
          <span className="size-1.5 rounded-full bg-emerald-400" />
          {count(hypotheses, "survived")} survived
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-1.5 rounded-full bg-amber-400" />
          {count(hypotheses, "parked")} parked
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-1.5 rounded-full bg-rose-400" />
          {count(hypotheses, "killed")} killed
        </span>
        {count(hypotheses, "promoted") > 0 && (
          <span className="flex items-center gap-1.5">
            <span className="size-1.5 rounded-full bg-sky-400" />
            {count(hypotheses, "promoted")} promoted
          </span>
        )}
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        {hypotheses.map((h) => {
          const v = VERDICT[h.status] ?? VERDICT.parked;
          let kills: string[] = [];
          try {
            kills = JSON.parse(h.kill_criteria) as string[];
          } catch {
            kills = [];
          }
          return (
            <div key={h.id} className={`flex flex-col rounded-md border ${v.ring} p-4`}>
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className={`rounded px-1.5 py-0.5 text-[10px] ${v.chip}`}>{v.label}</span>
                <span
                  className="font-mono text-[10px] text-muted-foreground"
                  title={LENS_LABEL[h.lens] ?? h.lens}
                >
                  {LENS_LABEL[h.lens] ?? h.lens}
                </span>
              </div>

              <p className="text-sm font-medium leading-snug text-foreground">{h.title}</p>

              {/* the migration the thesis claims: obvious (priced) → inelastic (where rent lands) */}
              <div className="mt-3 flex items-center gap-2 text-[11px]">
                <span className="rounded bg-muted/50 px-1.5 py-0.5 text-muted-foreground line-through decoration-muted-foreground/40">
                  {h.obvious_layer.split("—")[0].split("(")[0].trim().slice(0, 28)}
                </span>
                <span className="text-muted-foreground">→</span>
                <span className={`rounded px-1.5 py-0.5 ${v.chip}`}>
                  {h.inelastic_layer.split("(")[0].trim().slice(0, 34)}
                </span>
              </div>

              <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-muted-foreground">
                <span title="outside-view base rate (doctrine §2.1)">
                  base rate{" "}
                  <span className="font-mono text-foreground">
                    {h.base_rate !== null ? `${Math.round(h.base_rate * 100)}%` : "—"}
                  </span>
                </span>
                <span title="is there a point-in-time series that could test it? (§0.5 projectibility)">
                  testable{" "}
                  <span className={`font-mono ${h.measurable ? "text-emerald-400" : "text-rose-400"}`}>
                    {h.measurable ? "yes" : "no"}
                  </span>
                </span>
                {h.horizon && <span>by {h.horizon}</span>}
                {h.n_skeptics > 0 && (
                  <span
                    title="component 9: independent multi-skeptic panel — each skeptic blind to the others tries to refute; a majority kills it (§2.6)"
                    className={`rounded px-1.5 py-0.5 font-mono ${
                      h.n_refute * 2 > h.n_skeptics
                        ? "bg-rose-500/15 text-rose-300"
                        : "bg-emerald-500/15 text-emerald-300"
                    }`}
                  >
                    panel {h.n_refute}/{h.n_skeptics} refute
                  </span>
                )}
              </div>

              <details className="mt-3 border-t pt-2">
                <summary className="cursor-pointer text-[11px] text-muted-foreground hover:text-foreground">
                  disconfirmer · gate verdict{kills.length ? ` · ${kills.length} kill-criteria` : ""}
                </summary>
                <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
                  <span className="text-foreground">Sought first: </span>
                  {h.disconfirmer}
                </p>
                <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
                  <span className="text-foreground">Verdict: </span>
                  {h.refutation}
                </p>
                {kills.length > 0 && (
                  <ul className="mt-2 list-disc space-y-1 pl-4 text-[11px] text-muted-foreground">
                    {kills.map((k, i) => (
                      <li key={i}>{k}</li>
                    ))}
                  </ul>
                )}
              </details>
            </div>
          );
        })}
      </div>
    </div>
  );
}
