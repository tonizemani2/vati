// Cross-domain world map (the chains are ONE connected world). We flow the same 10× shock across
// the chain boundary (ai_power → metals) and rank every node by constraint pressure — the central
// estimate, mirroring the engine's Monte-Carlo (whose P(bottleneck) + interval live in the CLI /
// forecast card). The point this view makes visible: connecting the next domain MIGRATES the
// binding constraint deeper — power's GOES gives way to metals' copper-mine supply across the line.
// Server-rendered, no client JS. Purpose-built (not a generic graph framework — execution §9).
import { SHOCK, type GraphEdgeRow, type WorldNodeRow } from "@/lib/db";

type Lane = {
  node: WorldNodeRow;
  supply: number;
  substitutability: number;
  pressure: number;
};

const DOMAIN: Record<string, { label: string; chip: string }> = {
  ai_power: { label: "power / grid", chip: "border-amber-500/40 text-amber-300 bg-amber-500/10" },
  metals: { label: "metals / mining", chip: "border-sky-500/40 text-sky-300 bg-sky-500/10" },
};

export function CrossDomainMap({
  nodes,
  edges,
}: {
  nodes: WorldNodeRow[];
  edges: (GraphEdgeRow & { src_chain?: string })[];
}) {
  if (nodes.length === 0)
    return (
      <div className="flex min-h-24 items-center justify-center rounded-md border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
        No connected world yet. Run: python -m engine.cli graph-seed --chain metals
      </div>
    );

  // central pressure per supply node = (shock / supply) · (1 − substitutability), same as the engine
  const subWeight = new Map<string, number>();
  for (const e of edges)
    if (e.rel === "substitutes")
      subWeight.set(e.src, Math.min(0.95, (subWeight.get(e.src) ?? 0) + e.weight));

  const lanes: Lane[] = nodes
    .filter((n) => n.kind !== "substitute" && n.supply_multiple_3y != null)
    .map((n) => {
      const supply = n.supply_multiple_3y as number;
      const substitutability = subWeight.get(n.id) ?? 0;
      return { node: n, supply, substitutability, pressure: (SHOCK / supply) * (1 - substitutability) };
    })
    .sort((a, b) => b.pressure - a.pressure);

  const maxP = lanes[0]?.pressure ?? 1;
  const bottleneck = lanes[0]?.node.id;

  // the cross-domain edges: depends_on edges whose endpoints sit in different domains
  const chainOf = new Map(nodes.map((n) => [n.id, n.domain_chain]));
  const crossEdges = edges.filter(
    (e) => e.rel === "depends_on" && chainOf.get(e.src) && chainOf.get(e.dst) &&
      chainOf.get(e.src) !== chainOf.get(e.dst)
  );

  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        {lanes.map((l) => {
          const isBn = l.node.id === bottleneck;
          const isElastic = l.pressure < 0.5;
          const dom = DOMAIN[l.node.domain_chain] ?? { label: l.node.domain_chain, chip: "border-slate-600 text-slate-300" };
          const barColor = isBn ? "bg-rose-500/70" : isElastic ? "bg-emerald-500/60" : "bg-slate-500/50";
          return (
            <div key={l.node.id} className="flex items-center gap-2 text-xs">
              <div className="w-56 shrink-0 truncate font-medium text-slate-200" title={l.node.name}>
                {l.node.name}
              </div>
              <span className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] ${dom.chip}`}>
                {dom.label}
              </span>
              <div className="relative h-4 flex-1 overflow-hidden rounded bg-slate-800/60">
                <div className={`h-full ${barColor}`} style={{ width: `${Math.max(3, (l.pressure / maxP) * 100)}%` }} />
              </div>
              <div className="w-32 shrink-0 text-right font-mono text-[11px] text-slate-300">
                {l.pressure.toFixed(2)}
                {isBn ? " ⛏ drill" : isElastic ? " ✓ elastic" : ""}
              </div>
            </div>
          );
        })}
      </div>

      {crossEdges.length > 0 && (
        <p className="text-xs leading-relaxed text-muted-foreground">
          <span className="text-sky-300">{crossEdges.length} cross-domain edges</span> connect the
          power chain to metals. Flowing the {SHOCK}× shock across that boundary, the binding
          constraint migrates <span className="text-foreground">deeper</span> — past the
          within-power bottleneck (GOES) to{" "}
          <span className="font-medium text-rose-300">copper-mine supply</span>, where new mines take
          10–16 years and the 3-year horizon barely moves. The drill flag marks where{" "}
          <span className="text-foreground">data, not reasoning</span>, is now binding.
        </p>
      )}
    </div>
  );
}
