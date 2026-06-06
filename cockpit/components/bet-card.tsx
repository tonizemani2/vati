// Bet / decision translator (Phase 5 half 2, component 12). The last mile: a consensus EDGE turned
// into a sized, monitorable PAPER bet. Shows instrument(s) + direction, size, horizon, and the
// entry/exit/kill triggers — tied back to the consensus delta. Server-rendered, no client JS.
import type { BetLeg, BetRow } from "@/lib/db";

function parse<T>(json: string, fallback: T): T {
  try {
    return JSON.parse(json) as T;
  } catch {
    return fallback;
  }
}

const pct = (v: number | null, sign = false) =>
  v === null ? "—" : `${sign && v > 0 ? "+" : ""}${Math.round(v * 100)}%`;

export function BetCard({ b }: { b: BetRow | null }) {
  if (!b)
    return (
      <div className="flex min-h-24 items-center justify-center rounded-md border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
        No bet yet. The translator fires only on a consensus EDGE. Run: python -m engine.cli
        bet-translate
      </div>
    );

  const legs = parse<BetLeg[]>(b.legs, []);
  const entry = parse<string[]>(b.entry_triggers, []);
  const exit = parse<string[]>(b.exit_triggers, []);
  const kill = parse<string[]>(b.kill_triggers, []);

  return (
    <div className="space-y-4">
      {/* headline: direction + paper badge */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-base font-semibold text-foreground">{b.direction}</span>
        <span className="rounded-full border border-sky-500/40 bg-sky-500/15 px-3 py-1 text-xs font-medium text-sky-300">
          PAPER · {b.status} · $0
        </span>
      </div>

      {/* the three numbers that matter: size, modeled payoff, horizon */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-md border p-3">
          <div className="text-xs text-muted-foreground">Size (¼-Kelly, capped)</div>
          <div className="font-mono text-2xl font-semibold text-emerald-400">
            {pct(b.size_fraction)}
          </div>
          <div className="mt-1 text-[10px] text-muted-foreground">
            of risk capital · 80% band {pct(b.size_ci_low)}–{pct(b.size_ci_high)}
            {b.kelly_full !== null && (
              <> · full Kelly {b.kelly_full.toFixed(2)}</>
            )}
            {b.size_cap !== null && <> · cap {pct(b.size_cap)}</>}
          </div>
        </div>
        <div className="rounded-md border p-3">
          <div className="text-xs text-muted-foreground">Modeled pair return</div>
          <div className="font-mono text-2xl font-semibold text-foreground">
            {pct(b.exp_return_median, true)}
          </div>
          <div className="mt-1 text-[10px] text-muted-foreground">
            80% CI {pct(b.exp_return_ci_low, true)}–{pct(b.exp_return_ci_high, true)} · P(win){" "}
            {pct(b.p_win)}
          </div>
        </div>
        <div className="rounded-md border p-3">
          <div className="text-xs text-muted-foreground">Horizon</div>
          <div className="font-mono text-2xl font-semibold text-foreground">{b.horizon_date}</div>
          <div className="mt-1 text-[10px] text-muted-foreground">as-of {b.as_of}</div>
        </div>
      </div>

      {/* legs */}
      <div className="space-y-2">
        {legs.map((l) => (
          <div key={l.sym} className="flex items-start gap-3 rounded-md border p-2.5">
            <span
              className={`shrink-0 rounded px-2 py-0.5 text-xs font-semibold ${
                l.side === "long"
                  ? "bg-emerald-500/20 text-emerald-300"
                  : "bg-rose-500/20 text-rose-300"
              }`}
            >
              {l.side.toUpperCase()} {l.sym}
            </span>
            <div className="min-w-0">
              <div className="text-xs text-muted-foreground">
                {l.role} · {Math.round(l.weight * 100)}% of gross
              </div>
              <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{l.rationale}</p>
            </div>
          </div>
        ))}
      </div>

      {/* triggers: entry / exit / kill */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <TriggerList title="Entry" tone="text-sky-300" items={entry} />
        <TriggerList title="Exit" tone="text-amber-300" items={exit} />
        <TriggerList title="Kill" tone="text-rose-300" items={kill} />
      </div>

      {/* thesis (conditional) + full reasoning */}
      <div className="rounded-md border border-rose-500/30 bg-rose-500/5 p-3">
        <div className="text-xs font-medium text-rose-300">
          Central thesis — conditional on the open consensus Decision
        </div>
        <p className="mt-1 text-xs leading-relaxed text-foreground">{b.thesis}</p>
      </div>
      <details>
        <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
          Full sizing &amp; instrument rationale
        </summary>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{b.rationale}</p>
      </details>
    </div>
  );
}

function TriggerList({
  title,
  tone,
  items,
}: {
  title: string;
  tone: string;
  items: string[];
}) {
  return (
    <div className="rounded-md border p-3">
      <div className={`text-xs font-medium ${tone}`}>{title}</div>
      <ul className="mt-1.5 list-disc space-y-1.5 pl-4 text-xs leading-relaxed text-muted-foreground">
        {items.length === 0 ? (
          <li className="list-none text-muted-foreground/60">—</li>
        ) : (
          items.map((t, i) => <li key={i}>{t}</li>)
        )}
      </ul>
    </div>
  );
}
