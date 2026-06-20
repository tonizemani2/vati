"use client";

export type ForecastCardData = {
  question: string;
  quantity_label?: string;
  ci_unit?: string;
  resolution_date?: string;
  dated_metric?: string;
  kill_criteria?: string[];
  already_priced?: string;
  clause_note?: string;
  scenarios?: { outcome: string; p: number; note?: string }[];
  // provenance of the run (set by the chat flow): what actually fed this call.
  provenance?: {
    analysts?: number;
    sources?: number;
    crowd?: string; // "UNPRICED" | "42%" | "unchecked"
    draws?: number; // Monte-Carlo sample count
  };
  implications?: {
    exposed?: string;
    action_now?: string;
    decision_changed?: string;
    roi_logic?: string;
    rent_path?: string;
    winners?: { who: string; why: string }[];
    losers?: { who: string; why: string }[];
    reprices?: string;
    next_constraint?: string;
    watch?: string;
  };
  // engine-computed (from /api/forecast → engine.chat_bridge)
  probability?: number;
  median?: number;
  ci_low?: number;
  ci_high?: number;
  threshold?: number;
  threshold_dir?: string;
  histogram?: { lo: number; hi: number; counts: number[]; peak: number };
  n_samples?: number;
  pending?: boolean;
  error?: string;
};

function fmt(n?: number): string {
  if (n == null || !isFinite(n)) return "—";
  const abs = Math.abs(n);
  if (abs >= 1000) return Math.round(n).toLocaleString("en-US");
  if (abs >= 10) return n.toFixed(0);
  if (abs >= 1) return n.toFixed(2);
  return n.toFixed(3);
}

const clamp = (x: number) => Math.max(0, Math.min(1, x));

export function ForecastCard({ data }: { data: ForecastCardData }) {
  const {
    question,
    ci_unit,
    resolution_date,
    dated_metric,
    kill_criteria,
    already_priced,
    clause_note,
    scenarios,
    provenance,
    implications,
    probability,
    median,
    ci_low,
    ci_high,
    threshold,
    threshold_dir,
    histogram,
    pending,
    error,
  } = data;

  const dir = threshold_dir === "<=" ? "<=" : ">=";
  // Which histogram bars fall in the YES region (threshold side). Used to color the
  // distribution so the single probability reads as "this slice of the whole spread".
  const isYesBar = (i: number): boolean => {
    if (!histogram || threshold == null) return false;
    const width = (histogram.hi - histogram.lo) / histogram.counts.length;
    const center = histogram.lo + (i + 0.5) * width;
    return dir === "<=" ? center <= threshold : center >= threshold;
  };
  const thresholdPos =
    histogram && threshold != null
      ? clamp((threshold - histogram.lo) / (histogram.hi - histogram.lo || 1))
      : null;
  // Normalize scenarios for display: keep the model's order (first = committed call),
  // clamp probabilities, and scale bar widths to the largest so the field is readable
  // even when the top scenario is only ~40%.
  const scen = (scenarios ?? []).filter((s) => s && s.outcome);
  const scenMax = scen.reduce((m, s) => Math.max(m, clamp(s.p)), 0) || 1;

  const pctDisplay =
    probability == null
      ? "—"
      : probability >= 0.995
        ? ">99%"
        : probability <= 0.005
          ? "<1%"
          : `${Math.round(probability * 100)}%`;

  // Map the 80% CI + median onto the histogram range for the bar.
  let fillLeft = 0,
    fillWidth = 1,
    medianPos = 0.5;
  if (histogram && ci_low != null && ci_high != null) {
    const span = histogram.hi - histogram.lo || 1;
    fillLeft = clamp((ci_low - histogram.lo) / span);
    fillWidth = clamp((ci_high - ci_low) / span);
    if (median != null) medianPos = clamp((median - histogram.lo) / span);
  }

  return (
    <div className="vati-card mt-4 w-full max-w-[640px] min-w-0 p-4 sm:p-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 sm:gap-3">
        <span className="vati-tag">Vaticinus forecast</span>
        {resolution_date && (
          <span className="text-[12px] tabular-nums text-white/45">
            resolves {resolution_date}
          </span>
        )}
      </div>

      {/* Question */}
      <p className="mt-3 break-words text-[15px] font-medium leading-snug text-white">{question}</p>

      {error ? (
        <p className="mt-4 text-[13px] text-white/55">
          The engine could not run this decomposition ({error}). The read above still stands.
        </p>
      ) : (
        <>
          {/* Probability + CI */}
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:gap-5">
            <div className="min-w-0">
              <div className="vati-pct">{pending ? "··" : pctDisplay}</div>
              <div className="vati-card-label mt-1">probability</div>
            </div>
            <div className="min-w-0 flex-1 pb-1">
              <div className="vati-card-label mb-1.5">
                80% interval{ci_unit ? ` · ${ci_unit}` : ""}
              </div>
              {pending ? (
                <div className="vati-ci-track">
                  <div className="vati-ci-fill animate-pulse" style={{ left: "20%", width: "60%" }} />
                </div>
              ) : histogram ? (
                <>
                  <div className="vati-ci-track">
                    <div
                      className="vati-ci-fill"
                      style={{ left: `${fillLeft * 100}%`, width: `${fillWidth * 100}%` }}
                    />
                    <div className="vati-ci-median" style={{ left: `${medianPos * 100}%` }} />
                  </div>
                  <div className="mt-1.5 flex justify-between text-[11px] tabular-nums text-white/50">
                    <span>{fmt(ci_low)}</span>
                    <span className="text-white/70">median {fmt(median)}</span>
                    <span>{fmt(ci_high)}</span>
                  </div>
                </>
              ) : ci_low != null || ci_high != null ? (
                <div className="text-[14px] tabular-nums text-white/80">
                  {fmt(ci_low)} <span className="text-white/40">to</span> {fmt(ci_high)}
                </div>
              ) : (
                <div className="text-[13px] text-white/45">judgmental call (no decomposed interval)</div>
              )}
            </div>
          </div>

          {/* Dual probability: what the single number actually scores vs. the conviction */}
          {clause_note && !pending && (
            <p className="mt-3 text-[12.5px] leading-snug text-white/60">
              <span className="font-medium text-white/80">What the number scores: </span>
              {clause_note}
            </p>
          )}

          {/* Distribution, with the threshold drawn through it so the probability reads as
              a slice of the whole spread, not an arbitrary figure. */}
          {histogram && !pending && (
            <div className="mt-4">
              <div className="relative">
                <div className="vati-hist">
                  {histogram.counts.map((c, i) => (
                    <div
                      key={i}
                      className={isYesBar(i) ? "vati-hist-bar vati-hist-yes" : "vati-hist-bar vati-hist-no"}
                      style={{ height: `${Math.max(4, (c / histogram.peak) * 100)}%` }}
                    />
                  ))}
                </div>
                {thresholdPos != null && (
                  <div className="vati-hist-threshold" style={{ left: `${thresholdPos * 100}%` }} />
                )}
              </div>
              <div className="mt-1.5 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <span className="vati-card-label">Monte-Carlo outcome distribution</span>
                {probability != null && (
                  <span className="text-[11.5px] tabular-nums text-white/60">
                    <span className="font-semibold text-[var(--brand-light)]">{pctDisplay}</span> land{" "}
                    {dir} {fmt(threshold)}
                    {median != null ? ` · median ${fmt(median)}` : ""}
                  </span>
                )}
              </div>
            </div>
          )}

          {/* The field: mutually exclusive futures. Answers "what else could happen?" */}
          {scen.length >= 2 && !pending && (
            <div className="mt-5">
              <div className="vati-card-label">The field · what else could happen</div>
              <ul className="mt-2 flex flex-col gap-2">
                {scen.map((s, i) => (
                  <li
                    key={i}
                    className={`rounded-lg border p-2.5 ${
                      i === 0
                        ? "border-[var(--brand)]/50 bg-[rgba(109,106,252,0.10)]"
                        : "border-white/10 bg-white/[0.02]"
                    }`}
                  >
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="min-w-0 text-[13px] font-medium leading-snug text-white/90">
                        {i === 0 && (
                          <span className="mr-1.5 align-middle text-[9.5px] font-semibold uppercase tracking-wider text-[var(--brand-light)]">
                            our call
                          </span>
                        )}
                        {s.outcome}
                      </span>
                      <span className="shrink-0 text-[13px] font-semibold tabular-nums text-white/80">
                        {Math.round(clamp(s.p) * 100)}%
                      </span>
                    </div>
                    <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-white/8">
                      <div
                        className={i === 0 ? "h-full rounded-full bg-[var(--brand)]" : "h-full rounded-full bg-white/30"}
                        style={{ width: `${(clamp(s.p) / scenMax) * 100}%` }}
                      />
                    </div>
                    {s.note && (
                      <p className="mt-1.5 text-[12px] leading-snug text-white/55">{s.note}</p>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      {/* Metric */}
      {dated_metric && (
        <div className="mt-4 border-t border-white/10 pt-3">
          <div className="vati-card-label">settles on</div>
          <p className="mt-1 text-[13px] leading-snug text-white/75">{dated_metric}</p>
        </div>
      )}

      {/* Kill criteria */}
      {kill_criteria && kill_criteria.length > 0 && (
        <div className="mt-3">
          <div className="vati-card-label">kill-criteria</div>
          <ul className="mt-1.5 flex flex-col gap-1.5">
            {kill_criteria.map((k, i) => (
              <li key={i} className="flex gap-2 text-[13px] leading-snug text-white/70">
                <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-[var(--brand-light)]" />
                {k}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Priced-in note */}
      {already_priced && (
        <p className="mt-3 text-[12px] italic leading-snug text-white/50">{already_priced}</p>
      )}

      {/* Real-world implications: what moves if the call is right */}
      {implications && (
        <div className="mt-4 rounded-xl border border-white/12 bg-white/[0.03] p-3.5">
          <div className="vati-card-label text-[var(--brand-light)]">
            decision layer
          </div>
          {(implications.exposed ||
            implications.action_now ||
            implications.decision_changed ||
            implications.roi_logic) && (
            <div className="mt-2 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
              {implications.exposed && (
                <div>
                  <div className="vati-card-label">exposed buyer</div>
                  <p className="mt-1 text-[12.5px] leading-snug text-white/75">
                    {implications.exposed}
                  </p>
                </div>
              )}
              {implications.action_now && (
                <div>
                  <div className="vati-card-label">action now</div>
                  <p className="mt-1 text-[12.5px] leading-snug text-white/75">
                    {implications.action_now}
                  </p>
                </div>
              )}
              {implications.decision_changed && (
                <div>
                  <div className="vati-card-label">decision changed</div>
                  <p className="mt-1 text-[12.5px] leading-snug text-white/75">
                    {implications.decision_changed}
                  </p>
                </div>
              )}
              {implications.roi_logic && (
                <div>
                  <div className="vati-card-label">roi logic</div>
                  <p className="mt-1 text-[12.5px] leading-snug text-white/75">
                    {implications.roi_logic}
                  </p>
                </div>
              )}
            </div>
          )}
          {implications.rent_path && (
            <div className="mt-3">
              <div className="vati-card-label">rent path</div>
              <p className="mt-1 text-[13px] leading-snug text-white/80">
                {implications.rent_path}
              </p>
            </div>
          )}
          {(implications.winners?.length || implications.losers?.length) ? (
            <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
              {implications.winners?.length ? (
                <div className="rounded-lg border border-white/10 p-2.5">
                  <div className="vati-card-label text-emerald-300/90">who gains</div>
                  <ul className="mt-1.5 flex flex-col gap-1">
                    {implications.winners.map((w, i) => (
                      <li key={i} className="text-[12.5px] leading-snug text-white/70">
                        <span className="font-medium text-white">{w.who}</span>
                        {w.why ? `: ${w.why}` : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {implications.losers?.length ? (
                <div className="rounded-lg border border-white/10 p-2.5">
                  <div className="vati-card-label text-rose-300/90">who loses</div>
                  <ul className="mt-1.5 flex flex-col gap-1">
                    {implications.losers.map((w, i) => (
                      <li key={i} className="text-[12.5px] leading-snug text-white/70">
                        <span className="font-medium text-white">{w.who}</span>
                        {w.why ? `: ${w.why}` : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : null}
          {implications.reprices && (
            <div className="mt-3">
              <div className="vati-card-label">what reprices</div>
              <p className="mt-1 text-[12.5px] leading-snug text-white/70">{implications.reprices}</p>
            </div>
          )}
          {implications.next_constraint && (
            <div className="mt-2.5">
              <div className="vati-card-label">the next constraint it creates</div>
              <p className="mt-1 text-[12.5px] leading-snug text-white/70">
                {implications.next_constraint}
              </p>
            </div>
          )}
          {implications.watch && (
            <div className="mt-2.5">
              <div className="vati-card-label">earliest sign it has begun</div>
              <p className="mt-1 text-[12.5px] leading-snug text-white/70">{implications.watch}</p>
            </div>
          )}
        </div>
      )}

      {/* Provenance: the real inputs behind this call, not a single prompt. */}
      {provenance &&
        (provenance.analysts || provenance.sources || provenance.crowd || provenance.draws) && (
          <div className="mt-4 flex flex-wrap gap-1.5 border-t border-white/10 pt-3">
            {provenance.analysts ? (
              <span className="vati-prov-chip">{provenance.analysts} analysts</span>
            ) : null}
            {provenance.sources ? (
              <span className="vati-prov-chip">{provenance.sources} live web sources</span>
            ) : null}
            {provenance.crowd ? (
              <span className="vati-prov-chip">crowd-check: {provenance.crowd}</span>
            ) : null}
            {provenance.draws ? (
              <span className="vati-prov-chip">
                {provenance.draws >= 1000
                  ? `${Math.round(provenance.draws / 1000)}k Monte-Carlo draws`
                  : `${provenance.draws} draws`}
              </span>
            ) : null}
          </div>
        )}

      <p className="mt-3 text-[11px] text-white/35">
        Computed by the Vaticinus Monte-Carlo engine. Immutable and Brier-scored at resolution.
      </p>
    </div>
  );
}
