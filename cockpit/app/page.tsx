import {
  Activity,
  CircleDollarSign,
  Compass,
  GitBranch,
  Lightbulb,
  ListChecks,
  ShieldQuestion,
  Target,
  Zap,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { BetCard } from "@/components/bet-card";
import { CalibrationChart } from "@/components/calibration-chart";
import { ConsensusGate } from "@/components/consensus-gate";
import { DataHealthPanel } from "@/components/data-health";
import { EntitySpine } from "@/components/entity-spine";
import { HypothesisEngine } from "@/components/hypothesis-engine";
import { RetroBenchmark } from "@/components/retro-benchmark";
import { UniverseBenchmark } from "@/components/universe-benchmark";
import { SupplyGraph } from "@/components/supply-graph";
import { CrossDomainMap } from "@/components/cross-domain-map";
import {
  getBet,
  getCalibration,
  getConsensus,
  getCostLedger,
  getDataHealth,
  getDiscovery,
  getEntities,
  getEntityEdges,
  getForecasts,
  getGraphEdges,
  getGraphNodes,
  getWorldNodes,
  getWorldEdges,
  getHypotheses,
  getOpenDecisions,
  getPillars,
  getRetroCases,
  getRetroScore,
  getRecallProbe,
  getSlowConstraints,
  getUniverseScore,
  getSeries,
  getSources,
  getSpendCents,
  getLadder,
  getLadderScore,
  getDriverHealth,
  consensusEcho,
  CONSENSUS_ECHO_AT,
  type SeriesRow,
} from "@/lib/db";

// Always read fresh from the DB on each request (no static caching of dynamic state).
export const dynamic = "force-dynamic";

const PROVIDERS = [
  { name: "Claude (in-session)", role: "reasoning", on: true },
  { name: "MiniMax", role: "scale", on: false },
  { name: "DeepInfra", role: "scale", on: false },
  { name: "OpenRouter", role: "OCR/scale", on: false },
];

function statusBadge(status: string) {
  if (status === "exhausted")
    return <Badge variant="secondary">exhausted</Badge>;
  if (status === "in_progress")
    return <Badge className="bg-amber-500/20 text-amber-300">in progress</Badge>;
  return <Badge variant="outline">untapped</Badge>;
}

function trustClass(score: number) {
  if (score >= 80) return "text-emerald-400";
  if (score >= 50) return "text-amber-400";
  return "text-red-400";
}

// Tiny server-rendered SVG sparkline — no client JS, "visual-first" even for 60 rows.
function Sparkline({ values, fired }: { values: number[]; fired: boolean }) {
  const w = 88;
  const h = 22;
  if (values.length < 2) return <span className="text-muted-foreground">—</span>;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pts = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * (w - 2) + 1;
      const y = h - 1 - ((v - min) / span) * (h - 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const stroke = fired ? "#34d399" : "#64748b";
  return (
    <svg width={w} height={h} className="overflow-visible" aria-hidden>
      <polyline points={pts} fill="none" stroke={stroke} strokeWidth={1.5} />
    </svg>
  );
}

function fmtSigma(s: number | null): string {
  if (s === null) return "—";
  if (s >= 100) return `${Math.round(s)}σ`;
  return `${s.toFixed(1)}σ`;
}

// Empirical p-value (significance.py): a raw σ overstates — this is the honest, bounded number.
// At the MC resolution floor (1/(M+1)) we say "<floor" rather than fake more precision.
function fmtP(p: number | null, m: number | null): string {
  if (p === null) return "—";
  const floor = m ? 1 / (m + 1) : 0;
  if (p <= floor + 1e-12) return `p<${floor.toPrecision(1)}`;
  return `p=${p < 0.1 ? p.toFixed(3) : p.toFixed(2)}`;
}

function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-24 items-center justify-center rounded-md border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
      {children}
    </div>
  );
}

export default async function Cockpit() {
  const pillars = getPillars();
  const sources = getSources();
  const decisions = getOpenDecisions();
  const ledger = getCostLedger();
  const forecasts = getForecasts();
  const calibration = getCalibration();
  const ladder = getLadder();
  const ladderScore = getLadderScore();
  const driverHealth = getDriverHealth();
  const spendCents = getSpendCents();
  const series = getSeries();
  const graphNodes = getGraphNodes();
  const graphEdges = getGraphEdges();
  const powerNodes = getGraphNodes("ai_power");
  const powerEdges = getGraphEdges("ai_power");
  const worldNodes = getWorldNodes();
  const worldEdges = getWorldEdges();
  const dataHealth = getDataHealth();
  const entities = getEntities();
  const entityEdges = getEntityEdges();
  const hypotheses = getHypotheses();
  const consensus = getConsensus();
  const powerConsensus = getConsensus("ai_power");
  const betCard = getBet();
  const retroCases = getRetroCases();
  const retroScore = getRetroScore();
  const recallProbe = getRecallProbe();
  const slowConstraints = getSlowConstraints();
  const universeScore = getUniverseScore();
  const discovery = getDiscovery();

  const tracked = series.filter((s) => s.provider !== "synthetic");
  const firing = series.filter((s) => s.last_fired === 1 && s.provider !== "synthetic");
  const control = series.find((s) => s.provider === "synthetic");
  const detectorRun = series.some((s) => s.last_fired !== null);
  // Look-elsewhere correction (significance.py): the false-positive denominator at the detector.
  const sig = series.filter((s) => s.last_p_mc !== null);
  const sigRun = sig.length > 0;
  const sigFired = sig.filter((s) => s.last_fired === 1);
  const sigSurvive = sig.filter((s) => s.last_fdr_survive === 1);
  const sigQ = sig.find((s) => s.last_fdr_q !== null)?.last_fdr_q ?? 0.1;
  const sigExpFalse = sigQ * sigSurvive.length;
  const sparkOf = (s: SeriesRow): number[] =>
    s.spark ? s.spark.split(",").map(Number).filter((n) => !Number.isNaN(n)) : [];

  const sourcesByPillar = new Map<number, number>();
  for (const s of sources)
    sourcesByPillar.set(s.pillar_id, (sourcesByPillar.get(s.pillar_id) ?? 0) + 1);

  // The next actionable layer = first pillar not yet exhausted (enforces layering visually).
  const nextPillarId = pillars.find((p) => p.status !== "exhausted")?.id;

  const resolved = forecasts.filter((f) => f.outcome !== null);

  return (
    <div className="flex min-h-full">
      {/* Left rail */}
      <aside className="hidden w-64 shrink-0 flex-col border-r bg-card/40 p-5 md:flex">
        <div className="flex items-center gap-2">
          <Target className="size-5 text-primary" />
          <span className="font-semibold tracking-tight">Predict The Future</span>
        </div>
        <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
          Calibrated, pre-consensus forecasts of where scarcity migrates. The edge is
          finding the binding constraint before it&apos;s priced in.
        </p>
        <nav className="mt-6 flex flex-col gap-1 text-sm">
          {[
            ["#discovery", "Discovery", Compass],
            ["#slow", "Slow constraints", Compass],
            ["#pillars", "Pillars", Compass],
            ["#frontier", "Frontier signals", Zap],
            ["#hypotheses", "Hypothesis engine", Lightbulb],
            ["#data-health", "Data health", Activity],
            ["#entities", "Entity spine", GitBranch],
            ["#supply-graph", "Supply graph", GitBranch],
            ["#consensus", "Consensus gate", Target],
            ["#retro", "Retrodiction test", Activity],
            ["#universe", "Bias-proof universe", Activity],
            ["#bet", "Bet translation", ListChecks],
            ["#sources", "Sources & trust", GitBranch],
            ["#decisions", "Decisions", ShieldQuestion],
            ["#costs", "Cost ledger", CircleDollarSign],
            ["#forecasts", "Forecasts", ListChecks],
            ["#drivers", "Driver tracker", Activity],
            ["#ladder", "Resolution ladder", Activity],
          ].map(([href, label, Icon]) => {
            const I = Icon as typeof Compass;
            return (
              <a
                key={href as string}
                href={href as string}
                className="flex items-center gap-2 rounded-md px-2 py-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                <I className="size-4" />
                {label as string}
              </a>
            );
          })}
        </nav>
        <div className="mt-auto pt-6">
          <Badge variant="outline" className="text-xs">
            Phase 1: Frontier
          </Badge>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1">
        {/* Top bar */}
        <header className="flex flex-wrap items-center justify-between gap-3 border-b px-6 py-3">
          <div className="flex items-center gap-2 text-sm">
            <Activity className="size-4 text-muted-foreground" />
            <span className="text-muted-foreground">Spend to date</span>
            <span className="font-mono font-semibold">
              ${(spendCents / 100).toFixed(2)}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {PROVIDERS.map((p) => (
              <span
                key={p.name}
                className="flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs text-muted-foreground"
                title={`${p.role} — ${p.on ? "active" : "not configured"}`}
              >
                <span
                  className={`size-1.5 rounded-full ${
                    p.on ? "bg-emerald-400" : "bg-muted-foreground/40"
                  }`}
                />
                {p.name}
              </span>
            ))}
          </div>
        </header>

        <div className="space-y-6 p-6">
          {/* 0. Discovery — the open, self-discovering, gated scan (component 17) */}
          <section id="discovery" className="scroll-mt-4">
            <Card className="border-primary/40 bg-primary/5">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Compass className="size-4 text-primary" />
                  Discovery — where is the future, before it&apos;s priced?
                </CardTitle>
                <CardDescription>
                  The open scan, gated end-to-end. Every signal across {discovery.feeds.length} live
                  feeds passes QC → acceleration → a false-discovery (FDR) correction. Then the{" "}
                  <span className="text-foreground">pre-consensus</span> filter asks the only question
                  that matters: does a <span className="text-foreground">leading</span> channel
                  (capability, science, supply) fire while the <span className="text-foreground">lagging</span>{" "}
                  ones (attention, capital, policy) are still flat? That gap is <span className="text-emerald-300">EARLY</span>.
                  Most days it&apos;s empty — that honest default is the point.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
                  <span><span className="font-mono text-foreground">{discovery.survivors.length}</span> signals survive FDR (q={Math.round(discovery.q * 100)}%, expected false ≤ {discovery.expFalse.toFixed(1)})</span>
                  <span><span className="font-mono text-emerald-400">{discovery.early.length}</span> early</span>
                  <span><span className="font-mono text-foreground">{discovery.priced.length}</span> priced</span>
                  <span><span className="font-mono text-amber-400">{discovery.laggingOnly.length}</span> lagging-only (decoy)</span>
                </div>

                {discovery.early.length > 0 ? (
                  <div className="space-y-2">
                    <div className="text-xs font-medium text-emerald-300">★ EARLY — real & not yet priced (leading fires, consensus still flat)</div>
                    {discovery.early.map((e) => (
                      <div key={e.name} className="rounded-md border border-emerald-500/30 bg-emerald-500/5 p-3">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium">{e.name}</span>
                          <div className="flex items-center gap-2 text-xs">
                            <span className="font-mono text-emerald-400">{fmtSigma(e.lead_sig)} lead</span>
                            <Badge variant="outline" className={e.has_ticker ? "text-emerald-300" : "text-muted-foreground"}>
                              {e.has_ticker ? "priced-in gate ready" : "needs ticker map"}
                            </Badge>
                          </div>
                        </div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          fires: {e.leads.slice(0, 3).map((l) => `${l.label} (${l.provider} ${fmtSigma(l.sig)})`).join(" · ")}
                        </div>
                        <div className="mt-1 text-xs">
                          {e.satTier === "unmeasured" ? (
                            <span className="text-amber-400">saturation UNMEASURED — run `saturation-scan`; not yet confirmed pre-consensus</span>
                          ) : (
                            <span className="text-muted-foreground">saturation {e.saturation?.toFixed(2)} ({e.satTier}) — coverage measured low ✓</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState>
                    Nothing clean today — {discovery.survivors.length} signals survived FDR, but none
                    fire on a leading channel while consensus is still flat. The world is mostly priced;
                    keep scanning / widen feeds. (That this says &quot;no&quot; is the system working.)
                  </EmptyState>
                )}

                {discovery.laggingOnly.length > 0 && (
                  <div className="text-xs text-muted-foreground">
                    <span className="text-amber-400">⚠ Lagging-only (attention without capability — the decoy/hype tell):</span>{" "}
                    {discovery.laggingOnly.map((e) => e.name).join(", ")}
                  </div>
                )}
                {discovery.priced.length > 0 && (
                  <div className="text-xs text-muted-foreground">
                    Priced (real but the crowd is here): {discovery.priced.map((e) => e.name).join(", ")}
                  </div>
                )}
                <div className="text-[11px] text-muted-foreground">
                  feeds scanned: {discovery.feeds.join(" · ")}
                </div>
              </CardContent>
            </Card>
          </section>

          {/* 1a2. Slow-constraint aperture — the constraints the σ-detector is blind to */}
          {slowConstraints.length > 0 && (
            <section id="slow" className="scroll-mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Compass className="size-4 text-amber-400" />
                    Slow constraints — what binds without ever accelerating
                  </CardTitle>
                  <CardDescription>
                    The acceleration detector finds capability <span className="text-foreground">taking off</span>.
                    But scarcity also migrates from slow forces that trip no σ-detector — a workforce
                    peaking, water or arable land per capita falling, aging rising. These bind by slowly
                    crossing a <span className="text-foreground">sourced threshold</span> (Falkenmark water,
                    demographic peaks): the signal is <span className="text-foreground">years-to-bind</span>,
                    not σ. Keyless World Bank WDI.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-1.5">
                    {slowConstraints.map((s) => {
                      const tone =
                        s.status === "binding"
                          ? "text-red-400"
                          : s.status === "crossing_soon"
                            ? "text-amber-400"
                            : s.status === "approaching"
                              ? "text-sky-400"
                              : "text-muted-foreground";
                      const when = s.crossed
                        ? "BINDING now"
                        : s.years_to_cross !== null
                          ? `~${Math.round(s.years_to_cross)}y to bind`
                          : "stable / moving away";
                      return (
                        <div
                          key={s.label}
                          className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 border-b border-border/40 pb-1.5 text-xs"
                        >
                          <span className={`w-28 shrink-0 font-semibold ${tone}`}>
                            {s.status.replace("_", " ")}
                          </span>
                          <span className="text-foreground">{s.label}</span>
                          <Badge variant="outline" className="text-[10px]">
                            {s.constraint_kind}
                          </Badge>
                          <span className="text-muted-foreground">
                            now {s.current_val >= 1e6 ? `${(s.current_val / 1e6).toFixed(0)}M` : s.current_val.toFixed(s.current_val < 1 ? 2 : 0)}
                            {s.threshold !== null ? ` · threshold ${s.threshold}` : " · peak"} · {when}
                          </span>
                          {s.qc_status === "fail" && (
                            <span className="text-[10px] text-amber-500/80">
                              ⚠ data lags (WDI updates slowly — fine for a slow constraint)
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  <p className="mt-2 text-[11px] text-muted-foreground">
                    {slowConstraints.filter((s) => s.crossed).length} binding now ·{" "}
                    {slowConstraints.filter((s) => s.status === "crossing_soon").length} crossing within a
                    decade. The largest honest gap (execution §7), now open — a level/threshold detector,
                    not the 2nd-derivative one.
                  </p>
                </CardContent>
              </Card>
            </section>
          )}

          {/* 1. Pillars */}
          <section id="pillars" className="scroll-mt-4">
            <h2 className="mb-3 text-sm font-medium text-muted-foreground">
              Data-flow layers · exhaust one before the next
            </h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {pillars.map((p) => {
                const isNext = p.id === nextPillarId;
                const dim = p.status === "exhausted";
                return (
                  <Card
                    key={p.id}
                    className={[
                      "gap-2 transition-colors",
                      isNext ? "border-primary/60 bg-primary/5" : "",
                      dim ? "opacity-50" : "",
                    ].join(" ")}
                  >
                    <CardHeader className="gap-1">
                      <div className="flex items-center justify-between">
                        <CardTitle className="flex items-center gap-2 text-base">
                          <span className="font-mono text-xs text-muted-foreground">
                            {String(p.ord).padStart(2, "0")}
                          </span>
                          {p.name}
                        </CardTitle>
                        {statusBadge(p.status)}
                      </div>
                      <CardDescription className="text-xs leading-relaxed">
                        {p.description}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>{sourcesByPillar.get(p.id) ?? 0} sources</span>
                      {isNext && <span className="text-primary">← start here</span>}
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </section>

          {/* 1b. Frontier signals — the detector verdict on each concept's velocity */}
          <section id="frontier" className="scroll-mt-4">
            <Card>
              <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <CardTitle className="flex items-center gap-2 text-base">
                      <Zap className="size-4 text-emerald-400" />
                      Frontier signals
                    </CardTitle>
                    <CardDescription>
                      Frontier velocity vs each series&apos; own noise floor, across four free
                      source families — OpenAlex works/yr, Google Patents filings/yr, NIH grant
                      awards/yr, Epoch AI training-compute. We hunt the second derivative —
                      acceleration, not size. ⚡ = surprised past k·σ. A raw σ is a ranking, not a
                      reliability — each fire carries an empirical p (vs a continued-trend null) and
                      a Benjamini-Hochberg survival flag, the false-positive denominator at the detector.
                      The σ triggers on the single largest surprise (recall — a faint early bend still
                      fires); the <span className="text-emerald-400/70">sustained</span> /{" "}
                      <span className="text-amber-400">spike?</span> tag says whether the whole window
                      stayed above trend or it was one point (a transient can&apos;t pose as a bend).
                    </CardDescription>
                  </div>
                  <div className="flex gap-5 text-xs text-muted-foreground">
                    <span>
                      Tracked:{" "}
                      <span className="font-mono text-foreground">{tracked.length}</span>
                    </span>
                    <span>
                      Firing:{" "}
                      <span className="font-mono text-emerald-400">{firing.length}</span>
                    </span>
                    <span>
                      Control:{" "}
                      <span className="font-mono text-foreground">
                        {control
                          ? control.last_fired
                            ? `FIRED ${fmtSigma(control.last_surprise_sigma)} ⚠`
                            : `silent ${fmtSigma(control.last_surprise_sigma)} ✓`
                          : "—"}
                      </span>
                    </span>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {!detectorRun ? (
                  <EmptyState>
                    {series.length === 0
                      ? "No series yet. Run: python -m engine.cli collect-frontier"
                      : "Series collected, detector not run yet. Run: python -m engine.cli detect"}
                  </EmptyState>
                ) : (
                  <>
                  {sigRun && (
                    <div className="mb-3 rounded-md border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-xs text-muted-foreground">
                      <span className="font-medium text-foreground">Look-elsewhere correction:</span>{" "}
                      scanned <span className="font-mono text-foreground">{sig.length}</span> · fired{" "}
                      <span className="font-mono text-foreground">{sigFired.length}</span> raw ·{" "}
                      <span className="font-mono text-emerald-400">{sigSurvive.length}</span> survive
                      BH-FDR (q={(sigQ * 100).toFixed(0)}%) · expected false discoveries ≤{" "}
                      <span className="font-mono text-foreground">{sigExpFalse.toFixed(1)}</span>.
                      The σ is a ranking; the p + survival flag is the reliability.
                    </div>
                  )}
                  <div className="max-h-[26rem] overflow-y-auto rounded-md border">
                    <Table>
                      <TableHeader className="sticky top-0 bg-card">
                        <TableRow>
                          <TableHead>Concept</TableHead>
                          <TableHead className="hidden sm:table-cell">Span</TableHead>
                          <TableHead>Trend</TableHead>
                          <TableHead className="text-right">Surprise</TableHead>
                          <TableHead className="hidden text-right md:table-cell">Significance</TableHead>
                          <TableHead className="text-right">Signal</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {series.map((s) => {
                          const fired = s.last_fired === 1;
                          const isControl = s.provider === "synthetic";
                          return (
                            <TableRow
                              key={s.id}
                              className={isControl ? "bg-muted/30" : undefined}
                            >
                              <TableCell className="max-w-[16rem]">
                                <span className="truncate">{s.label}</span>
                                <span className="ml-2 text-xs text-muted-foreground">
                                  {s.provider}
                                </span>
                              </TableCell>
                              <TableCell className="hidden whitespace-nowrap text-xs text-muted-foreground sm:table-cell">
                                {s.first_as_of?.slice(0, 4)}–{s.last_as_of?.slice(0, 4)}
                                {s.first_val !== null && s.last_val !== null && (
                                  <span className="ml-1">
                                    ({Math.round(s.first_val)}→{Math.round(s.last_val)})
                                  </span>
                                )}
                              </TableCell>
                              <TableCell>
                                <Sparkline values={sparkOf(s)} fired={fired} />
                              </TableCell>
                              <TableCell
                                className={`text-right font-mono ${
                                  fired ? "text-emerald-400" : "text-muted-foreground"
                                }`}
                              >
                                {fmtSigma(s.last_surprise_sigma)}
                                {fired && s.last_n_consecutive !== null && (() => {
                                  // persistence annotation (redteam #1): sustained bend vs 1-pt spike.
                                  // Replicate detector.py's rule from n_obs (holdout ≈ 30%).
                                  const holdout = Math.max(2, Math.round(0.3 * s.n_obs));
                                  const need = Math.max(2, Math.ceil(holdout / 2));
                                  const sustained = (s.last_n_consecutive ?? 0) >= need;
                                  return (
                                    <div
                                      className={`text-[10px] font-normal ${
                                        sustained ? "text-emerald-400/70" : "text-amber-400"
                                      }`}
                                      title={
                                        sustained
                                          ? `sustained bend: ${s.last_n_consecutive} consecutive points above trend (not a one-point spike)`
                                          : `transient: only ${s.last_n_consecutive} consecutive point(s) above trend — the fire may be a single spike/revision. Annotation only; the verdict still fired (recall).`
                                      }
                                    >
                                      {sustained ? "sustained" : "spike?"}
                                    </div>
                                  );
                                })()}
                                {s.last_dissolving === 1 && (
                                  <div
                                    className="text-[10px] font-normal text-sky-400"
                                    title={`dissolving: a sustained downturn below the established trend (↓${fmtSigma(
                                      s.last_down_surprise_sigma
                                    )}) — the constraint is relaxing. The symmetric kill-signal (redteam #6).`}
                                  >
                                    ↓ dissolving
                                  </div>
                                )}
                              </TableCell>
                              <TableCell className="hidden text-right font-mono text-xs md:table-cell">
                                {s.last_p_mc === null ? (
                                  <span className="text-muted-foreground">—</span>
                                ) : (
                                  <span
                                    className={
                                      s.last_fdr_survive === 1
                                        ? "text-emerald-400"
                                        : "text-muted-foreground line-through"
                                    }
                                    title={
                                      s.last_fdr_survive === 1
                                        ? "survives Benjamini-Hochberg across the scan"
                                        : "FDR-rejected — a likely look-elsewhere false positive"
                                    }
                                  >
                                    {fmtP(s.last_p_mc, s.last_p_mc_m)}
                                  </span>
                                )}
                              </TableCell>
                              <TableCell className="text-right">
                                {fired ? (
                                  s.last_fdr_survive === 0 ? (
                                    <span className="text-muted-foreground" title="fired, but FDR-rejected (look-elsewhere)">
                                      ⚡ fired ✗
                                    </span>
                                  ) : (
                                    <span className="text-emerald-400">⚡ fired</span>
                                  )
                                ) : (
                                  <span className="text-muted-foreground">silent</span>
                                )}
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </div>
                  </>
                )}
              </CardContent>
            </Card>
          </section>

          {/* 1c. Supply graph — pillars 3-4 as a chain; the bottleneck derived under flow */}
          {/* 1b2. Data health — component 16: the QC harness (freshness/completeness/validity/...) */}
          <section id="data-health" className="scroll-mt-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Activity className="size-4 text-emerald-400" />
                  Data health — the quality gate
                </CardTitle>
                <CardDescription>
                  The model is only as good as its data. Every series is audited for{" "}
                  <span className="text-foreground">freshness</span>,{" "}
                  <span className="text-foreground">completeness</span>,{" "}
                  <span className="text-foreground">validity</span>, cross-source{" "}
                  <span className="text-foreground">reconciliation</span>, and{" "}
                  <span className="text-foreground">provenance</span>. A failing series is skipped by
                  the detector and refused as a forecast seed — stale or incomplete data cannot
                  silently reach a bet.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <DataHealthPanel health={dataHealth} />
              </CardContent>
            </Card>
          </section>

          {/* 1b3. Hypothesis engine — component 8: the generative front-end. The oracle, gated. */}
          <section id="hypotheses" className="scroll-mt-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Lightbulb className="size-4 text-amber-300" />
                  Hypothesis engine — the oracle, gated
                </CardTitle>
                <CardDescription>
                  Everything else here <span className="text-foreground">disposes</span> — the detector,
                  the consensus gate and Brier kill bad ideas, but can only judge curves we already chose
                  to look at. This is the missing half: the divergent, cross-domain act of{" "}
                  <span className="text-foreground">where should we even look?</span> Each thesis is
                  proposed in-session through a lens, then forced through the same discipline a forecast
                  obeys — an outside-view base rate, a <span className="text-foreground">disconfirmer
                  sought first</span>, kill-criteria, and a projectibility check. The gate{" "}
                  <span className="text-emerald-300">survives</span> what clears every bar,{" "}
                  <span className="text-amber-300">parks</span> the beautiful-but-untestable (logged, not
                  faked — the anti-astrology valve), and <span className="text-rose-300">kills</span> its
                  own seductive narratives. The seer proposes; the cold machine disposes.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <HypothesisEngine hypotheses={hypotheses} />
              </CardContent>
            </Card>
          </section>

          {/* 1c0. Entity resolution — component 2: the spine that links the same thing across pillars */}
          <section id="entities" className="scroll-mt-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <GitBranch className="size-4 text-violet-400" />
                  Entity resolution — the spine across pillars
                </CardTitle>
                <CardDescription>
                  Every pillar names the same things differently — OpenAlex&apos;s{" "}
                  <span className="text-foreground">deep learning</span>, Epoch&apos;s compute curves
                  and the patent phrase are one technology; 10x Genomics is a graph node{" "}
                  <span className="text-foreground">and</span> the ticker TXG. Resolving them onto one
                  node is what lets the constraint be <span className="text-foreground">traced</span>{" "}
                  frontier → graph → pricing. In-session judgment, every link rationaled (GIGO) — and
                  as much about <span className="text-foreground">not</span> merging distinct things
                  (NLP ≠ deep learning) as merging the same one.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <EntitySpine entities={entities} edges={entityEdges} />
              </CardContent>
            </Card>
          </section>

          <section id="supply-graph" className="scroll-mt-4 space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <GitBranch className="size-4 text-rose-400" />
                  Supply graph — single-cell RNA-seq
                </CardTitle>
                <CardDescription>
                  Where does the rent land? We flow a 10× demand shock through the value chain and
                  let the first-saturating, least-substitutable node fall out. The bottleneck is
                  <span className="text-foreground"> computed under flow</span>, never a stored label —
                  and human-verified before it backs a forecast.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <SupplyGraph nodes={graphNodes} edges={graphEdges} />
              </CardContent>
            </Card>
            {powerNodes.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <GitBranch className="size-4 text-amber-400" />
                    Supply graph — AI-power buildout (2nd domain)
                  </CardTitle>
                  <CardDescription>
                    The same engine, a new domain — the proof it generalizes. Capital floods the{" "}
                    <span className="text-foreground">GPU</span> (elastic — fabs + CoWoS expanding), but
                    cannot fast-forward the electrical layer. Flowing the shock, the bottleneck the
                    market hasn&apos;t named falls out: <span className="text-foreground">grain-oriented
                    electrical steel</span> — the constraint behind the transformer. The GPU is elastic;
                    rent does not land there.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <SupplyGraph nodes={powerNodes} edges={powerEdges} />
                </CardContent>
              </Card>
            )}
            {worldNodes.some((n) => n.domain_chain === "metals") && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <GitBranch className="size-4 text-sky-400" />
                    Cross-domain world — power → metals (the constraint migrates a domain deeper)
                  </CardTitle>
                  <CardDescription>
                    The chains are <span className="text-foreground">one connected world</span>, not
                    silos. We flow the same 10× shock <span className="text-foreground">across the
                    domain boundary</span> — power&apos;s grid gear depends on metals&apos; refined
                    copper, which depends on mine supply. Recomputed over the whole world, the binding
                    constraint moves past GOES to <span className="text-foreground">copper-mine
                    supply</span>. The <span className="text-foreground">⛏ drill</span> flag marks
                    where data, not reasoning, is now binding.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <CrossDomainMap nodes={worldNodes} edges={worldEdges} />
                </CardContent>
              </Card>
            )}
          </section>

          {/* 1d. Consensus gate — pillar 7: is the derived bottleneck already priced in? */}
          <section id="consensus" className="scroll-mt-4 space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Target className="size-4 text-emerald-400" />
                  Consensus gate — is it already priced in? (scRNA-seq)
                </CardTitle>
                <CardDescription>
                  The gate the whole thesis hinges on. We measure what the market pays for the
                  inelastic <span className="text-foreground">consumable</span> layer vs the elastic{" "}
                  <span className="text-foreground">sequencer</span> (relative P/S, from keyless Stooq
                  + SEC filings), and subtract it from what the constraint model says the premium{" "}
                  <span className="text-foreground">should</span> be. The gap is the edge — correct +
                  already priced = zero return.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ConsensusGate c={consensus} />
              </CardContent>
            </Card>
            {powerConsensus && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Target className="size-4 text-amber-400" />
                    Consensus gate — AI-power buildout (GEV vs NVDA)
                  </CardTitle>
                  <CardDescription>
                    The gate keeps the system honest. The graph says the rent migrates to the
                    electrical layer — but the obvious play (GE Vernova) has{" "}
                    <span className="text-foreground">already re-rated</span> on the AI-power narrative,
                    so the liquid edge is largely priced (verdict: inconclusive). The pure pre-consensus
                    edge sits in the deep layer — <span className="text-foreground">GOES steel, the
                    interconnection queue</span> — which has no public pure-play. Named, not faked.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <ConsensusGate c={powerConsensus} />
                </CardContent>
              </Card>
            )}
          </section>

          {/* 1d2. Retrodiction benchmark — the "are we real" gate (plan.md scoreboard #2) */}
          <section id="retro" className="scroll-mt-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Activity className="size-4 text-violet-400" />
                  Retrodiction test — are we real?
                </CardTitle>
                <CardDescription>
                  The acceptance test. The §8 corpus — famous{" "}
                  <span className="text-foreground">winners</span> and famous{" "}
                  <span className="text-foreground">fizzles</span> — replayed point-in-time with the
                  method <span className="text-foreground">frozen before the run</span> (no tuning on
                  the corpus = no hindsight machine). The fizzle denominator is the test: a method
                  that only retrodicts winners has learned nothing about its false positives.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <RetroBenchmark cases={retroCases} score={retroScore} />
                {recallProbe.length > 0 && (
                  <div className="mt-4 rounded-lg border border-border/60 bg-muted/30 p-3">
                    <div className="mb-1 text-xs font-semibold text-foreground">
                      Recall probe #3 — talent-inflow, scored on recall AND precision
                    </div>
                    <div className="mb-2 text-[11px] text-muted-foreground">
                      The first recall channel to pass BOTH halves (changepoint &amp; cross-field diffusion
                      both failed): it fires early on the deep-learning miss the annual curve is silent on
                      (recall), and stays quiet on receding research bubbles (precision). Point-in-time,
                      frozen detector; never touches the §8 scoreboard. Graphene fires because its research
                      genuinely boomed — a commercial fizzle, left for the downstream gate.
                    </div>
                    {(() => {
                      const STYLE: Record<string, [string, string]> = {
                        recall_gain: ["✓ recall gain", "font-semibold text-emerald-400"],
                        no_gain: ["— no gain", "text-muted-foreground"],
                        silent_correct: ["✓ silent (precision)", "font-semibold text-sky-400"],
                        false_positive: ["✗ false positive", "font-semibold text-rose-400"],
                        research_fired: ["◐ research fired (gate-rejected)", "text-amber-400"],
                        silent: ["· silent", "text-muted-foreground"],
                      };
                      return recallProbe.map((p) => {
                        const [lbl, cls] = STYLE[p.verdict] ?? [p.verdict, "text-muted-foreground"];
                        return (
                          <div key={`${p.term}-${p.channel}`} className="flex items-baseline gap-2 text-[11px]">
                            <span className={cls}>{lbl}</span>
                            <span className="text-foreground">
                              {p.term} ({p.channel.replace("_", " ")})
                            </span>
                            {p.verdict === "recall_gain" && (
                              <span className="text-muted-foreground">
                                fires {p.first_fire_year} ({p.first_fire_sigma}σ), {p.lead_years}y before §8
                                signal {p.canonical_signal}
                              </span>
                            )}
                          </div>
                        );
                      });
                    })()}
                  </div>
                )}
              </CardContent>
            </Card>
          </section>

          {/* 1d3. Bias-proof universe — the survivorship-killer: drawn by rule, labelled by rule */}
          <section id="universe" className="scroll-mt-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Activity className="size-4 text-violet-400" />
                  Bias-proof universe — nobody picked the cases
                </CardTitle>
                <CardDescription>
                  The answer to &quot;you only tested famous cases you already knew.&quot; The
                  candidate set is <span className="text-foreground">drawn by a frozen rule</span>{" "}
                  from the whole OpenAlex concept pool (data ≤ each origin) and the win/lose label is a{" "}
                  <span className="text-foreground">frozen gain-of-share rule</span> (data after the
                  origin). The same frozen detector calls each one blind. Lift is measured over a{" "}
                  <span className="text-foreground">true, low base rate</span> — and it holds at every
                  rolling origin.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <UniverseBenchmark score={universeScore} />
              </CardContent>
            </Card>
          </section>

          {/* 1e. Bet translation — pillar 12: the edge → a sized, monitorable paper bet */}
          <section id="bet" className="scroll-mt-4">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <ListChecks className="size-4 text-sky-400" />
                  Bet translation — what to do about the edge
                </CardTitle>
                <CardDescription>
                  Not just <span className="text-foreground">where</span> the constraint is, but{" "}
                  <span className="text-foreground">what to do</span> about it. The edge is expressed in
                  the inelastic layer as a <span className="text-foreground">pair</span> (long the
                  consumable, short the elastic sequencer) to isolate constraint-migration from sector
                  beta, sized small (capped ¼-Kelly) because the edge is contested. Paper only, $0 —
                  translation, not execution.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <BetCard b={betCard} />
              </CardContent>
            </Card>
          </section>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            {/* 2. Sources & trust */}
            <section id="sources" className="scroll-mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Sources &amp; trust</CardTitle>
                  <CardDescription>
                    Every source carries a stated reason to trust it. Rank is not trust.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {sources.length === 0 ? (
                    <EmptyState>
                      No sources yet. Garbage in, garbage out — a source only enters with a
                      trust rationale and score.
                    </EmptyState>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Title</TableHead>
                          <TableHead>Kind</TableHead>
                          <TableHead className="text-right">Trust</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {sources.map((s) => (
                          <TableRow key={s.id}>
                            <TableCell
                              className="max-w-[20rem] truncate"
                              title={s.trust_rationale}
                            >
                              {s.title}
                            </TableCell>
                            <TableCell className="text-muted-foreground">{s.kind}</TableCell>
                            <TableCell
                              className={`text-right font-mono ${trustClass(s.trust_score)}`}
                            >
                              {s.trust_score}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </section>

            {/* 3. Decisions */}
            <section id="decisions" className="scroll-mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Decisions awaiting you</CardTitle>
                  <CardDescription>
                    Pivotal forks the AI won&apos;t take alone — a short prompt and a
                    recommendation.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {decisions.length === 0 ? (
                    <EmptyState>Nothing needs you right now.</EmptyState>
                  ) : (
                    decisions.map((d) => {
                      let opts: string[] = [];
                      try {
                        opts = JSON.parse(d.options) as string[];
                      } catch {
                        opts = [];
                      }
                      return (
                        <div key={d.id} className="rounded-md border p-3">
                          <p className="text-sm">{d.prompt}</p>
                          {d.recommendation && (
                            <p className="mt-1 text-xs text-muted-foreground">
                              Recommendation: {d.recommendation}
                            </p>
                          )}
                          <div className="mt-2 flex flex-wrap gap-2">
                            {opts.map((o) => (
                              <Badge key={o} variant="outline">
                                {o}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      );
                    })
                  )}
                </CardContent>
              </Card>
            </section>

            {/* 4. Cost ledger */}
            <section id="costs" className="scroll-mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Cost ledger</CardTitle>
                  <CardDescription>
                    Strict mode: free/keyless runs automatically; any spend is logged and waits
                    for your approval.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-baseline justify-between">
                    <span className="text-2xl font-semibold tabular-nums">
                      ${(spendCents / 100).toFixed(2)}
                    </span>
                    <span className="text-xs text-muted-foreground">spent to date</span>
                  </div>
                  <Progress value={0} />
                  {ledger.length === 0 ? (
                    <EmptyState>
                      All actions so far were free/keyless. Nothing has cost money.
                    </EmptyState>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Action</TableHead>
                          <TableHead>Provider</TableHead>
                          <TableHead className="text-right">Est.</TableHead>
                          <TableHead className="text-right">Status</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {ledger.map((c) => (
                          <TableRow key={c.id}>
                            <TableCell>{c.action}</TableCell>
                            <TableCell className="text-muted-foreground">{c.provider}</TableCell>
                            <TableCell className="text-right font-mono">
                              ${(c.est_cost_cents / 100).toFixed(2)}
                            </TableCell>
                            <TableCell className="text-right">{c.approval_status}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </section>

            {/* 5. Forecasts */}
            <section id="forecasts" className="scroll-mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Forecasts &amp; calibration</CardTitle>
                  <CardDescription>
                    Each card is a distribution, not a point: a binary probability + an 80%
                    credible interval, with a resolution date and kill-criteria. The diagonal is
                    perfect calibration; we must beat the naive 50% base-rate baseline.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <CalibrationChart points={calibration.points} />
                  <div className="flex flex-wrap gap-6 text-xs text-muted-foreground">
                    <span>
                      Open:{" "}
                      <span className="font-mono text-foreground">
                        {forecasts.filter((f) => f.outcome === null).length}
                      </span>
                    </span>
                    <span>
                      Resolved:{" "}
                      <span className="font-mono text-foreground">{resolved.length}</span>
                    </span>
                    <span>
                      Mean Brier:{" "}
                      <span
                        className={`font-mono ${
                          calibration.brier_model !== null &&
                          calibration.brier_baseline !== null &&
                          calibration.brier_model < calibration.brier_baseline
                            ? "text-emerald-400"
                            : "text-foreground"
                        }`}
                      >
                        {calibration.brier_model !== null
                          ? calibration.brier_model.toFixed(3)
                          : "n/a"}
                      </span>
                      {calibration.brier_baseline !== null && (
                        <span className="text-muted-foreground">
                          {" "}
                          vs {calibration.brier_baseline.toFixed(3)} baseline
                        </span>
                      )}
                    </span>
                  </div>

                  {forecasts.length === 0 ? (
                    <EmptyState>
                      No forecasts yet. A forecast needs a resolution date and at least one
                      kill-criterion — a story without those is not a bet.
                    </EmptyState>
                  ) : (
                    <div className="space-y-3">
                      {forecasts.map((f) => {
                        let kills: string[] = [];
                        try {
                          kills = JSON.parse(f.kill_criteria) as string[];
                        } catch {
                          kills = [];
                        }
                        const resolvedCard = f.outcome !== null;
                        const beat =
                          f.brier_score !== null && f.brier_score < 0.25;
                        return (
                          <div key={f.id} className="rounded-md border p-3">
                            <div className="flex items-start justify-between gap-3">
                              <p className="text-sm leading-snug">{f.question}</p>
                              <div className="shrink-0 text-right">
                                <div className="font-mono text-lg leading-none">
                                  {Math.round(f.probability * 100)}%
                                </div>
                                {f.ci_low !== null && f.ci_high !== null && (
                                  <div className="mt-1 text-[10px] text-muted-foreground">
                                    80% CI {Math.round(f.ci_low)}–{Math.round(f.ci_high)}
                                    {f.ci_unit ? ` ${f.ci_unit}` : ""}
                                  </div>
                                )}
                              </div>
                            </div>
                            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                              <Badge variant="outline">by {f.resolution_date}</Badge>
                              {(() => {
                                const echo = consensusEcho(f.saturation);
                                if (echo === null) return null; // saturation unmeasured → no tag (honest)
                                return echo ? (
                                  <Badge className="bg-amber-500/20 text-amber-300" title={`narrative-saturation ${f.saturation?.toFixed(2)} ≥ ${CONSENSUS_ECHO_AT} — already widely covered`}>
                                    consensus-echo · sat {f.saturation?.toFixed(2)}
                                  </Badge>
                                ) : (
                                  <Badge className="bg-sky-500/20 text-sky-300" title={`narrative-saturation ${f.saturation?.toFixed(2)} < ${CONSENSUS_ECHO_AT} — still ahead of the crowd`}>
                                    pre-consensus · sat {f.saturation?.toFixed(2)}
                                  </Badge>
                                );
                              })()}
                              {resolvedCard ? (
                                <Badge
                                  className={
                                    beat
                                      ? "bg-emerald-500/20 text-emerald-300"
                                      : "bg-amber-500/20 text-amber-300"
                                  }
                                >
                                  resolved {f.outcome} · Brier{" "}
                                  {f.brier_score?.toFixed(3)}
                                </Badge>
                              ) : (
                                <Badge variant="secondary">open</Badge>
                              )}
                            </div>
                            {kills.length > 0 && (
                              <details className="mt-2">
                                <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
                                  Kill-criteria ({kills.length}) · rationale
                                </summary>
                                <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-muted-foreground">
                                  {kills.map((k, i) => (
                                    <li key={i}>{k}</li>
                                  ))}
                                </ul>
                                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                                  {f.rationale}
                                </p>
                              </details>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>
            </section>

            {/* 5a-bis. Leading-indicator / driver tracker — forecast the drivers, not the endpoints */}
            <section id="drivers" className="scroll-mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Driver tracker — leading indicators on a fast clock</CardTitle>
                  <CardDescription>
                    A live call resolves in 2027–28, but its dated kill-criteria are observable{" "}
                    <span className="text-foreground">now</span>. Each driver links one kill-criterion to a
                    series; the <span className="text-foreground">signal</span> is the mean fast-clock
                    partial (1 = comfortably on the confirming side and trending right, 0 = falsified) —{" "}
                    <span className="text-foreground">forecast the drivers, not the endpoint</span>. A
                    threshold is often a target to reach by a future date, so a metric below it but climbing
                    reads <span className="text-amber-300">approaching</span>, not falsified. Observe-only:
                    this never moves a card&apos;s issued probability (rule 7).
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {driverHealth.length === 0 ? (
                    <EmptyState>
                      No drivers linked yet. Run: python -m engine.cli driver-seed (or driver-link --card
                      &lt;id&gt; --series &lt;id&gt; --threshold &lt;x&gt; --direction fails_below --confirm up)
                    </EmptyState>
                  ) : (
                    driverHealth.map((h) => {
                      const sig = h.signal === null ? "—" : `${Math.round(h.signal * 100)}%`;
                      const sigClass =
                        h.signal === null ? "text-foreground"
                          : h.signal >= 0.6 ? "text-emerald-400"
                          : h.signal >= 0.4 ? "text-amber-400" : "text-red-400";
                      return (
                        <div key={h.key} className="rounded-md border p-3">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-sm leading-snug">{h.title}</p>
                              <p className="mt-1 text-[10px] uppercase tracking-wide text-muted-foreground">
                                {h.kind} · {h.n} driver{h.n === 1 ? "" : "s"}
                              </p>
                            </div>
                            <div className="shrink-0 text-right">
                              <div className={`font-mono text-lg leading-none ${sigClass}`}>{sig}</div>
                              <div className="mt-1 text-[10px] text-muted-foreground">driver signal</div>
                            </div>
                          </div>
                          <div className="mt-2 space-y-1.5">
                            {h.drivers.map((d, i) => {
                              const cls =
                                d.status === "on_track" ? "bg-emerald-500/20 text-emerald-300"
                                  : d.status === "approaching" ? "bg-amber-500/20 text-amber-300"
                                  : d.status === "falsified" ? "bg-red-500/20 text-red-300"
                                  : "bg-muted text-muted-foreground";
                              const arrow = d.direction === "fails_below" ? "≥" : "≤";
                              const spark = d.spark ? d.spark.split(",").map(Number).filter((n) => !Number.isNaN(n)) : [];
                              return (
                                <div key={i} className="flex items-center justify-between gap-3 text-xs">
                                  <div className="flex min-w-0 items-center gap-2">
                                    <Badge className={cls}>{d.status}</Badge>
                                    <span className="truncate" title={d.note}>{d.series_label}</span>
                                  </div>
                                  <div className="flex shrink-0 items-center gap-3 text-muted-foreground">
                                    <span className="font-mono">
                                      {d.value === null ? "—" : (+d.value.toPrecision(4)).toString()} {arrow}{" "}
                                      {(+d.threshold.toPrecision(4)).toString()}
                                    </span>
                                    <span className="hidden sm:inline">
                                      {d.margin_sigma === null ? "" : `${d.margin_sigma >= 0 ? "+" : ""}${d.margin_sigma.toFixed(2)}σ · `}
                                      {d.trend}
                                    </span>
                                    <Sparkline values={spark} fired={d.status !== "falsified"} />
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })
                  )}
                </CardContent>
              </Card>
            </section>

            {/* 5b. Fast-resolution ladder (redteam #3) */}
            <section id="ladder" className="scroll-mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Resolution ladder — calibration + discrimination on a fast clock</CardTitle>
                  <CardDescription>
                    The thesis cards resolve in 2027–28, so the track record can&apos;t accumulate for
                    years. This ladder runs short-horizon (1–2yr) constraint-persistence micro-forecasts on
                    <span className="text-foreground"> every QC-passing series across all pillars</span>,
                    resolved from history <span className="text-foreground">now</span> — the same card
                    machinery, a faster clock. Two things must both hold:{" "}
                    <span className="text-foreground">calibration</span> (full-history drift + Student-t
                    tails → Brier beats max-entropy) and{" "}
                    <span className="text-foreground">discrimination</span> — the issued P now comes from a
                    transparent logistic on point-in-time mean-reversion features (sharpen.py), trained{" "}
                    <span className="text-foreground">leak-free by expanding window</span>, lifting AUC from
                    ~0.49 (drift-only ties the base rate) to ~0.68. <span className="text-foreground">Open:</span>{" "}
                    cross-pillar &quot;depth&quot; features add nothing yet — entity-sibling coverage is
                    research 80% / capital 3% / demand 0%, a data gap, not a modelling one.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {ladderScore.n_resolved === 0 ? (
                    <EmptyState>
                      No ladder rungs yet. Run: python -m engine.cli ladder-run
                    </EmptyState>
                  ) : (
                    <>
                      <div className="flex flex-wrap gap-6 text-xs text-muted-foreground">
                        <span>
                          Resolved:{" "}
                          <span className="font-mono text-foreground">{ladderScore.n_resolved}</span>
                        </span>
                        <span>
                          Brier:{" "}
                          <span
                            className={`font-mono ${
                              (ladderScore.brier_model ?? 1) < (ladderScore.brier_baseline ?? 0)
                                ? "text-emerald-400"
                                : "text-amber-400"
                            }`}
                          >
                            {ladderScore.brier_model?.toFixed(3)}
                          </span>{" "}
                          vs {ladderScore.brier_baseline?.toFixed(3)} naive ·{" "}
                          {ladderScore.brier_baserate?.toFixed(3)} base-rate
                        </span>
                        <span>
                          Discrimination (AUC):{" "}
                          <span
                            className={`font-mono ${
                              (ladderScore.auc ?? 0.5) >= 0.6
                                ? "text-emerald-400"
                                : (ladderScore.auc ?? 0.5) > 0.53
                                ? "text-amber-400"
                                : "text-red-400"
                            }`}
                          >
                            {ladderScore.auc?.toFixed(3) ?? "—"}
                          </span>{" "}
                          (0.5 = none)
                        </span>
                        <span>
                          Hit-rate:{" "}
                          <span className="font-mono text-foreground">
                            {Math.round((ladderScore.hit_rate ?? 0) * 100)}%
                          </span>{" "}
                          · mean P {Math.round((ladderScore.mean_p ?? 0) * 100)}%
                        </span>
                      </div>
                      {/* plan.md #4+#5 — engine vs ALL naive baselines, side-by-side, on BOTH proper
                          scores. Log loss (cross-entropy) punishes confident-wrong far harder than
                          Brier, so it can disagree — and that disagreement is the honest finding, shown
                          not hidden. random-walk ≡ the 0.5 column here (a zero-drift 'holds ≥ today'
                          call has its median AT the threshold); consensus has no per-rung analyst
                          series, so it lives at the thesis-card gate, not here. */}
                      <div className="mt-1 overflow-x-auto rounded-md border border-border/60 text-xs">
                        <table className="w-full font-mono">
                          <thead className="text-muted-foreground">
                            <tr className="[&>th]:px-3 [&>th]:py-1.5 [&>th]:text-left [&>th]:font-medium">
                              <th>score</th>
                              <th>model</th>
                              <th>0.5 / random-walk</th>
                              <th>base-rate</th>
                              <th>persistence</th>
                            </tr>
                          </thead>
                          <tbody className="[&>tr>td]:px-3 [&>tr>td]:py-1.5">
                            <tr className="border-t border-border/60">
                              <td className="text-muted-foreground">Brier ↓</td>
                              <td className={(ladderScore.brier_model ?? 1) <= (ladderScore.brier_baserate ?? 0) ? "text-emerald-400" : "text-amber-400"}>{ladderScore.brier_model?.toFixed(3)}</td>
                              <td>{ladderScore.brier_baseline?.toFixed(3)}</td>
                              <td>{ladderScore.brier_baserate?.toFixed(3)}</td>
                              <td>{ladderScore.brier_persist?.toFixed(3)}</td>
                            </tr>
                            <tr className="border-t border-border/60">
                              <td className="text-muted-foreground">LogLoss ↓</td>
                              <td className={(ladderScore.logloss_model ?? 1) <= (ladderScore.logloss_baserate ?? 0) ? "text-emerald-400" : "text-amber-400"}>{ladderScore.logloss_model?.toFixed(3)}</td>
                              <td>{ladderScore.logloss_baseline?.toFixed(3)}</td>
                              <td>{ladderScore.logloss_baserate?.toFixed(3)}</td>
                              <td>{ladderScore.logloss_persist?.toFixed(3)}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                      {(ladderScore.logloss_model ?? 0) > (ladderScore.logloss_baserate ?? 1) && (
                        <p className="text-xs text-amber-400/90">
                          Honest read: the model beats max-entropy on both scores but only{" "}
                          <span className="font-mono">ties</span> the base-rate guesser under log loss
                          — a confident-wrong tail (the documented low-end overconfidence) that Brier&apos;s
                          boundedness masks. Calibrated and discriminating on rank (AUC), not yet sharp at the extremes.
                        </p>
                      )}
                      {/* reliability bins: predicted vs observed (the diagonal is perfect) */}
                      <div className="space-y-1">
                        {ladderScore.bins.map((b, i) => (
                          <div key={i} className="flex items-center gap-2 text-xs">
                            <span className="w-20 shrink-0 font-mono text-muted-foreground">
                              p≈{Math.round(b.pred * 100)}%
                            </span>
                            <div className="relative h-3 flex-1 rounded bg-muted">
                              <div
                                className="absolute inset-y-0 left-0 rounded bg-sky-500/40"
                                style={{ width: `${Math.round(b.obs * 100)}%` }}
                              />
                              <div
                                className="absolute inset-y-0 w-px bg-foreground/60"
                                style={{ left: `${Math.round(b.pred * 100)}%` }}
                                title="predicted (the bar should reach this line)"
                              />
                            </div>
                            <span className="w-24 shrink-0 font-mono text-muted-foreground">
                              obs {Math.round(b.obs * 100)}% · n={b.n}
                            </span>
                          </div>
                        ))}
                      </div>
                      <details>
                        <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
                          {ladder.length < ladderScore.n_resolved
                            ? `${ladder.length} most-recent of ${ladderScore.n_resolved} rungs`
                            : `All ${ladder.length} rungs`}
                        </summary>
                        <div className="mt-2 space-y-1">
                          {ladder.map((r, i) => (
                            <div
                              key={i}
                              className="flex items-center gap-2 text-xs text-muted-foreground"
                            >
                              <span
                                className={`w-12 shrink-0 font-mono ${
                                  r.outcome === null
                                    ? "text-muted-foreground"
                                    : r.outcome === "true"
                                    ? "text-emerald-400"
                                    : "text-amber-400"
                                }`}
                              >
                                {Math.round(r.probability * 100)}%
                              </span>
                              <span className="w-20 shrink-0 font-mono">
                                {r.outcome === null
                                  ? "open"
                                  : `${r.outcome} ${r.brier_score?.toFixed(2)}`}
                              </span>
                              <span className="truncate">
                                {r.ci_unit} · by {r.resolution_date.slice(0, 4)}
                              </span>
                            </div>
                          ))}
                        </div>
                      </details>
                    </>
                  )}
                </CardContent>
              </Card>
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}
