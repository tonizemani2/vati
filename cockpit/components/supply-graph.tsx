// Supply-graph node-link view (Phase 4, components 5+6). Server-rendered SVG, no client JS.
// Purpose-built for the scRNA-seq chain — NOT a generic graph framework (execution §9 anti-pattern).
// The bottleneck is re-derived here under flow (central estimate) from the stored node/edge params,
// mirroring the engine's Monte-Carlo; the interval + P(bottleneck) live in the forecast card.
import { SHOCK, type GraphEdgeRow, type GraphNodeRow } from "@/lib/db";

type Lane = {
  node: GraphNodeRow;
  short: string;
  sub: string;
  required: number;
  supply: number | null;
  substitutability: number;
  pressure: number | null;
};

const SHORT: Record<string, [string, string]> = {
  assay: ["scRNA-seq assay", `${SHOCK}× demand shock`],
  consumable: ["Partitioning consumable", "chip + barcoded gel beads"],
  prep: ["Library prep", "NGS kits"],
  equipment: ["Short-read sequencer", "capacity"],
  reagent: ["Reagents", "flow cells"],
};

function derive(nodes: GraphNodeRow[], edges: GraphEdgeRow[]) {
  const subWeight = new Map<string, number>();
  for (const e of edges)
    if (e.rel === "substitutes")
      subWeight.set(e.src, Math.min(0.95, (subWeight.get(e.src) ?? 0) + e.weight));

  const lanes: Lane[] = nodes
    .filter((n) => n.kind !== "substitute")
    .map((n) => {
      const supply = n.supply_multiple_3y;
      const substitutability = subWeight.get(n.id) ?? 0;
      const required = SHOCK;
      const pressure =
        supply != null ? (required / supply) * (1 - substitutability) : null;
      const [short, sub] = SHORT[n.kind] ?? [n.name.slice(0, 22), n.kind];
      return { node: n, short, sub, required, supply, substitutability, pressure };
    });

  const supplyLanes = lanes.filter((l) => l.pressure != null);
  const bottleneck = supplyLanes.reduce(
    (a, b) => ((b.pressure ?? 0) > (a?.pressure ?? -1) ? b : a),
    null as Lane | null
  );
  return { lanes, bottleneck };
}

// Display labels for the AI-power chain's kinds too (scRNA-seq kinds above). Unknown kinds fall
// back to the node's own name, so a new chain always renders — no kind is silently dropped.
const SHORT_POWER: Record<string, [string, string]> = {
  transformer: ["Large-power transformer", "≥100 MVA, 2–4yr lead"],
  material: ["GOES electrical steel", "transformer core input"],
  // 'grid' is intentionally absent — two grid nodes (switchgear, interconnection) fall back to
  // their own distinct names rather than colliding on one label.
};
Object.assign(SHORT, SHORT_POWER);

export function SupplyGraph({
  nodes,
  edges,
}: {
  nodes: GraphNodeRow[];
  edges: GraphEdgeRow[];
}) {
  if (nodes.length === 0)
    return (
      <div className="flex min-h-24 items-center justify-center rounded-md border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
        No supply graph yet. Run: python -m engine.cli graph-seed
      </div>
    );

  const { lanes, bottleneck } = derive(nodes, edges);
  // Order chain-agnostically: the shock origin (assay) first, then the rest in chain order,
  // left→right. Works for any seeded chain — no kind is dropped (was a fixed scRNA-seq list).
  const ordered: Lane[] = [
    ...lanes.filter((l) => l.node.kind === "assay"),
    ...lanes.filter((l) => l.node.kind !== "assay"),
  ];

  // Substitute chips, attached to their parent (the substitutes-edge src) by id.
  const subs = nodes.filter((n) => n.kind === "substitute");
  const subParent = new Map<string, string>(); // substitute id -> parent node id
  for (const e of edges)
    if (e.rel === "substitutes") subParent.set(e.dst, e.src);

  const W = 940;
  const H = 320;
  const BW = 150;
  const BH = 78;
  const rowY = 46;
  const subY = 196;
  const gap = (W - BW) / (ordered.length - 1);
  const xOf = (i: number) => i * gap;
  const xById = new Map<string, number>();
  ordered.forEach((l, i) => xById.set(l.node.id, xOf(i)));

  function color(l: Lane): { stroke: string; fill: string; text: string } {
    if (l.node.kind === "assay")
      return { stroke: "#60a5fa", fill: "#1e3a5f33", text: "#93c5fd" };
    if (bottleneck && l.node.id === bottleneck.node.id)
      return { stroke: "#fb7185", fill: "#7f1d1d44", text: "#fda4af" };
    if (l.pressure != null && l.pressure < 0.5)
      return { stroke: "#34d399", fill: "#064e3b44", text: "#6ee7b7" };
    return { stroke: "#64748b", fill: "#1e293b66", text: "#cbd5e1" };
  }

  return (
    <div className="space-y-3">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
           aria-label="single-cell RNA-seq supply graph with derived bottleneck">
        <defs>
          <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3"
                  orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L6,3 L0,6 Z" fill="#64748b" />
          </marker>
        </defs>

        {/* flow arrows along the pipeline */}
        {ordered.slice(0, -1).map((l, i) => {
          const x1 = xOf(i) + BW;
          const x2 = xOf(i + 1);
          const y = rowY + BH / 2;
          return (
            <line key={`f${i}`} x1={x1} y1={y} x2={x2 - 2} y2={y}
                  stroke="#64748b" strokeWidth={1.5} markerEnd="url(#arrow)" />
          );
        })}

        {/* substitutes: dashed connectors down to substitute chips */}
        {subs.map((s, i) => {
          const px = xById.get(subParent.get(s.id) ?? "");
          if (px == null) return null;
          const cx = px + BW / 2;
          return (
            <g key={`s${i}`}>
              <line x1={cx} y1={rowY + BH} x2={cx} y2={subY}
                    stroke="#475569" strokeWidth={1.2} strokeDasharray="4 3" />
              <text x={cx + 4} y={(rowY + BH + subY) / 2} fill="#64748b" fontSize={10}>
                substitutes
              </text>
              <rect x={px} y={subY} width={BW} height={52} rx={7}
                    fill="#0f172a" stroke="#475569" strokeWidth={1} strokeDasharray="4 3" />
              <text x={px + 8} y={subY + 19} fill="#94a3b8" fontSize={10.5} fontWeight={600}>
                {s.name.length > 24 ? s.name.slice(0, 23) + "…" : s.name}
              </text>
              <text x={px + 8} y={subY + 38} fill="#64748b" fontSize={9.5}>
                {(() => {
                  const w = edges.find((e) => e.dst === s.id && e.rel === "substitutes")?.weight ?? 0;
                  return `routes ~${Math.round(w * 100)}% around`;
                })()}
              </text>
            </g>
          );
        })}

        {/* nodes */}
        {ordered.map((l, i) => {
          const x = xOf(i);
          const c = color(l);
          const isBn = bottleneck && l.node.id === bottleneck.node.id;
          const isElastic = l.pressure != null && l.pressure < 0.5;
          return (
            <g key={l.node.id}>
              <rect x={x} y={rowY} width={BW} height={BH} rx={8}
                    fill={c.fill} stroke={c.stroke} strokeWidth={isBn ? 2.4 : 1.4} />
              <text x={x + 10} y={rowY + 19} fill={c.text} fontSize={12} fontWeight={700}>
                {l.short}
              </text>
              <text x={x + 10} y={rowY + 34} fill="#94a3b8" fontSize={9.5}>
                {l.sub}
              </text>
              {l.pressure != null ? (
                <>
                  <text x={x + 10} y={rowY + 54} fill="#cbd5e1" fontSize={9.5} fontFamily="monospace">
                    {l.supply}× supply · {Math.round(l.substitutability * 100)}% sub
                  </text>
                  <text x={x + 10} y={rowY + 69} fill={c.text} fontSize={10.5} fontFamily="monospace"
                        fontWeight={700}>
                    pressure {l.pressure.toFixed(2)}
                    {isBn ? "  ⛔ rent lands here" : isElastic ? "  ✓ elastic" : ""}
                  </text>
                </>
              ) : (
                <text x={x + 10} y={rowY + 60} fill="#93c5fd" fontSize={10} fontFamily="monospace">
                  shock origin
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {bottleneck && (
        <p className="text-xs leading-relaxed text-muted-foreground">
          Flowing a {SHOCK}× demand shock through the chain, the first-saturating,
          least-substitutable node is the{" "}
          <span className="font-medium text-rose-300">{bottleneck.short.toLowerCase()}</span>{" "}
          (pressure {bottleneck.pressure?.toFixed(2)}) — <span className="text-foreground">A</span>, not
          the obvious end-product, which is elastic (capital can scale it), so rent does not land there.
          This is <span className="text-foreground">derived</span>{" "}
          under flow, not asserted; the supply-gap interval and P(bottleneck) are on the forecast card.
        </p>
      )}
    </div>
  );
}
