// Entity resolution (component 2 — the spine). Server-rendered, no client JS.
// One canonical entity, its links across pillars, and the 1–9 rail lit on the pillars it spans —
// the cross-pillar trace that lets the constraint be followed frontier → graph → pricing.
import type { EntityRow, EntityEdgeRow } from "@/lib/db";

// Short pillar labels (causal order) — the rail shows which layers an entity touches.
const PILLAR_ABBR: Record<number, string> = {
  1: "Frontier",
  2: "Curves",
  3: "Graph",
  4: "Supply",
  5: "Demand",
  6: "Capital",
  7: "Pricing",
  8: "Policy",
  9: "Outcomes",
};

const KIND_CLS: Record<string, string> = {
  technology: "bg-sky-500/15 text-sky-300",
  company: "bg-amber-500/15 text-amber-300",
  material: "bg-emerald-500/15 text-emerald-300",
  component: "bg-teal-500/15 text-teal-300",
  infrastructure: "bg-cyan-500/15 text-cyan-300",
  policy: "bg-rose-500/15 text-rose-300",
  field: "bg-violet-500/15 text-violet-300",
};

function PillarRail({ spanned }: { spanned: number[] }) {
  const set = new Set(spanned);
  return (
    <div className="flex flex-wrap gap-1">
      {Array.from({ length: 9 }, (_, i) => i + 1).map((p) => (
        <span
          key={p}
          title={PILLAR_ABBR[p]}
          className={`rounded px-1.5 py-0.5 font-mono text-[10px] ${
            set.has(p)
              ? "bg-violet-500/25 text-violet-200 ring-1 ring-violet-400/40"
              : "bg-muted/40 text-muted-foreground/40"
          }`}
        >
          {p}
        </span>
      ))}
    </div>
  );
}

export function EntitySpine({ entities, edges = [] }: { entities: EntityRow[]; edges?: EntityEdgeRow[] }) {
  if (entities.length === 0)
    return (
      <div className="flex min-h-24 items-center justify-center rounded-md border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
        No entities resolved yet. Run: python -m engine.cli entity-seed
      </div>
    );

  const totalLinks = entities.reduce((s, e) => s + e.links.length, 0);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
        <span>
          <span className="font-mono text-foreground">{entities.length}</span> entities
        </span>
        <span>
          <span className="font-mono text-foreground">{totalLinks}</span> resolved links
        </span>
        <span>
          <span className="font-mono text-foreground">{edges.length}</span> supplier edges
        </span>
        <span>
          each link carries a <span className="text-foreground">confidence + rationale</span> (GIGO)
        </span>
      </div>

      {/* #4 dependency half: the supply structure between entities — trace a constraint one hop up/down */}
      {edges.length > 0 && (
        <div className="rounded-md border border-border/60 bg-muted/30 p-3">
          <div className="mb-2 text-xs font-semibold text-foreground">
            Supply structure — who supplies whom (the dependency half of #4)
          </div>
          <div className="flex flex-wrap gap-2">
            {edges.map((e) => (
              <span
                key={`${e.src}->${e.dst}`}
                title={`${e.rationale} (confidence ${e.confidence})`}
                className="rounded bg-background/60 px-2 py-1 font-mono text-[10px] text-muted-foreground ring-1 ring-border/50"
              >
                <span className="text-emerald-300">{e.src}</span>
                <span className="text-muted-foreground/60"> →supplies→ </span>
                <span className="text-sky-300">{e.dst}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="grid gap-3 lg:grid-cols-2">
        {entities.map((e) => {
          const aliases = (() => {
            try {
              return JSON.parse(e.aliases) as string[];
            } catch {
              return [];
            }
          })();
          return (
            <div key={e.id} className="rounded-md border p-4">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="font-medium text-foreground">{e.canonical_name}</span>
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] ${
                    KIND_CLS[e.kind] ?? "bg-muted text-muted-foreground"
                  }`}
                >
                  {e.kind}
                </span>
                {aliases.map((a) => (
                  <span key={a} className="font-mono text-[10px] text-muted-foreground">
                    ={a}
                  </span>
                ))}
              </div>

              <div className="mb-3 flex items-center gap-2">
                <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                  spans
                </span>
                <PillarRail spanned={e.pillars} />
              </div>

              <ul className="space-y-1">
                {e.links.map((l, i) => (
                  <li key={i} className="flex items-baseline gap-2 text-xs">
                    <span className="w-7 shrink-0 font-mono text-[10px] text-violet-300">
                      P{l.pillar_id}
                    </span>
                    <span className="w-20 shrink-0 text-[10px] text-muted-foreground">
                      {l.ref_table}
                    </span>
                    <span className="flex-1 text-foreground">{l.ref_label}</span>
                    <span
                      className={`shrink-0 font-mono text-[10px] ${
                        l.confidence >= 0.9 ? "text-emerald-400" : "text-amber-400"
                      }`}
                      title={l.rationale}
                    >
                      {l.confidence.toFixed(2)}
                    </span>
                  </li>
                ))}
              </ul>

              {e.note && (
                <p className="mt-3 border-t pt-2 text-[11px] leading-relaxed text-muted-foreground">
                  {e.note}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
