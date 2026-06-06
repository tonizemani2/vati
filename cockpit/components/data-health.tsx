// Data quality / QC harness (A5, component 16). Server-rendered, no client JS.
// The health score + the worst series, so "no unupdated/incomplete stuff" is visible at a glance.
// A 'fail' series is skipped by the detector and refused as a forecast seed (the hard gate).
import type { DataHealth } from "@/lib/db";

const STATUS_CLS: Record<string, string> = {
  fail: "text-rose-400",
  warn: "text-amber-400",
  ok: "text-emerald-400",
};

function scoreClass(s: number) {
  if (s >= 90) return "text-emerald-400";
  if (s >= 70) return "text-amber-400";
  return "text-rose-400";
}

function detailLine(detail: string): string {
  try {
    const d = JSON.parse(detail) as Record<string, string>;
    // surface the most actionable non-ok facts
    return [d.fresh, d.complete, d.valid, d.prov, d.recon]
      .filter((x) => x && !/^(no gaps|sourced|in range|frozen|co-moves|sole series|single point|too short|latest \d+ \(≤)/.test(x))
      .slice(0, 2)
      .join(" · ");
  } catch {
    return "";
  }
}

export function DataHealthPanel({ health }: { health: DataHealth }) {
  if (health.n === 0)
    return (
      <div className="flex min-h-24 items-center justify-center rounded-md border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
        No audit yet. Run: python -m engine.cli data-audit
      </div>
    );

  const pct = (x: number) => (health.n ? Math.round((x / health.n) * 100) : 0);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-x-8 gap-y-2">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
            data-health score
          </div>
          <div className={`font-mono text-4xl ${scoreClass(health.score)}`}>
            {health.score.toFixed(1)}
            <span className="text-lg text-muted-foreground"> / 100</span>
          </div>
        </div>
        <div className="flex gap-4 text-sm">
          <span>
            <span className="font-mono text-emerald-400">{health.ok}</span>{" "}
            <span className="text-muted-foreground">ok</span>
          </span>
          <span>
            <span className="font-mono text-amber-400">{health.warn}</span>{" "}
            <span className="text-muted-foreground">warn</span>
          </span>
          <span>
            <span className="font-mono text-rose-400">{health.fail}</span>{" "}
            <span className="text-muted-foreground">fail (gated)</span>
          </span>
        </div>
      </div>

      {/* ok/warn/fail bar */}
      <div className="flex h-2 overflow-hidden rounded">
        <div className="bg-emerald-500/70" style={{ width: `${pct(health.ok)}%` }} />
        <div className="bg-amber-500/70" style={{ width: `${pct(health.warn)}%` }} />
        <div className="bg-rose-500/70" style={{ width: `${pct(health.fail)}%` }} />
      </div>

      {health.worst.length > 0 ? (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-card text-xs text-muted-foreground">
              <tr className="border-b">
                <th className="px-3 py-2 text-left font-medium">series</th>
                <th className="px-3 py-2 text-left font-medium">status</th>
                <th className="px-3 py-2 text-left font-medium">why</th>
                <th className="px-3 py-2 text-right font-medium">score</th>
              </tr>
            </thead>
            <tbody>
              {health.worst.map((r) => (
                <tr key={r.series_id} className="border-b last:border-0">
                  <td className="px-3 py-2">
                    <span className="text-foreground">{r.label}</span>
                    <span className="ml-2 text-[10px] text-muted-foreground">{r.provider}</span>
                  </td>
                  <td className={`px-3 py-2 font-medium ${STATUS_CLS[r.status] ?? ""}`}>{r.status}</td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">{detailLine(r.detail)}</td>
                  <td className="px-3 py-2 text-right font-mono text-xs text-muted-foreground">
                    {r.health_score.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-emerald-400">All series pass QC. ✓</p>
      )}

      <p className="text-xs leading-relaxed text-muted-foreground">
        Six checks per series — <span className="text-foreground">freshness</span> (latest point vs
        expected cadence), <span className="text-foreground">completeness</span> (gaps in the time
        grid), <span className="text-foreground">validity</span> (range + unit consistency),{" "}
        <span className="text-foreground">reconciliation</span> (co-movement across an entity&apos;s
        sources), <span className="text-foreground">provenance</span> (every series has a trusted
        Source), and revision tracking. A <span className="text-rose-400">fail</span> is skipped by
        the detector and refused as a forecast seed — stale/incomplete data cannot reach a bet.
      </p>
    </div>
  );
}
