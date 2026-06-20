"use client";

import { Users, Scale, Loader2, Check, ExternalLink, Globe, Database } from "lucide-react";

export type CouncilMember = {
  id: string;
  lens: string;
  stance?: string;
  brief?: string;
  done: boolean;
};

export type MarketAnchor = { source: string; label: string; prob: number; volume: number; url: string };
export type CouncilGate = {
  verdict: string;
  priced: string;
  lean: string;
  anchor: { status: "priced" | "none" | "unchecked"; top: MarketAnchor | null; markets: MarketAnchor[] };
};

export type CouncilResearch = {
  summary: string;
  citations: { title: string; url: string }[];
};

export type CouncilData = {
  members: CouncilMember[];
  research?: CouncilResearch;
  gate?: CouncilGate;
  // Deep tier only: a read from the Vaticinus data layer (our concept/actor/dependency graph).
  ground?: string;
};

function lensTitle(lens: string) {
  return lens.split(" — ")[0];
}

function verdictColor(v: string) {
  if (/PRE-CONSENSUS/i.test(v)) return "text-emerald-700 bg-emerald-50 ring-emerald-200";
  if (/PARTIALLY/i.test(v)) return "text-amber-700 bg-amber-50 ring-amber-200";
  return "text-rose-700 bg-rose-50 ring-rose-200"; // PRICED = no edge
}

type PhaseState = "done" | "active" | "pending" | "muted";

function phaseClass(state: PhaseState) {
  if (state === "done") return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (state === "active") return "border-[var(--brand)] bg-[rgba(109,106,252,0.08)] text-[var(--brand-600)]";
  if (state === "muted") return "border-[var(--border-faint)] bg-[var(--sidebar-bg)] text-[var(--ink-muted)]";
  return "border-[var(--border-faint)] bg-white text-[var(--ink-muted)]";
}

function Phase({ label, state, meta }: { label: string; state: PhaseState; meta?: string }) {
  return (
    <div
      className={`flex min-w-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${phaseClass(
        state,
      )}`}
    >
      {state === "active" ? (
        <Loader2 size={11} className="shrink-0 animate-spin" />
      ) : state === "done" ? (
        <Check size={11} className="shrink-0" />
      ) : (
        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-current opacity-35" />
      )}
      <span className="truncate">{label}</span>
      {meta && <span className="text-current/60">{meta}</span>}
    </div>
  );
}

export function Council({
  data,
  live = false,
  hasAnswer = false,
}: {
  data: CouncilData;
  live?: boolean;
  hasAnswer?: boolean;
}) {
  const total = data.members.length;
  const done = data.members.filter((m) => m.done).length;
  const running = done < total || !data.gate;
  const analystsDone = total > 0 && done === total;
  const researchDone = Boolean(data.research);
  const researchSkipped = Boolean(data.gate && !data.research);
  const gateDone = Boolean(data.gate);
  const synthesisDone = gateDone && hasAnswer && !live;

  return (
    <div className="my-3 overflow-hidden rounded-2xl border border-[var(--border-faint)] bg-white">
      <div className="flex items-center gap-2 border-b border-[var(--border-faint)] px-4 py-2.5">
        <Users size={16} strokeWidth={1.9} className="text-[var(--brand-600)]" />
        <span className="text-[13px] font-semibold text-[var(--ink)]">The council</span>
        <span className="text-[12px] text-[var(--ink-muted)]">
          {running ? `deliberating ${done}/${total}` : `${total} analysts`}
        </span>
        {running && <Loader2 size={13} className="animate-spin text-[var(--ink-muted)]" />}
      </div>

      <div className="flex flex-wrap gap-1.5 border-b border-[var(--border-faint)] px-4 py-2.5">
        <Phase
          label="Analysts"
          state={analystsDone ? "done" : "active"}
          meta={total ? `${done}/${total}` : undefined}
        />
        <Phase
          label="Research"
          state={researchDone ? "done" : researchSkipped ? "muted" : analystsDone ? "active" : "pending"}
          meta={
            researchDone
              ? `${data.research?.citations.length ?? 0} src`
              : researchSkipped
                ? "best effort"
                : undefined
          }
        />
        {data.ground && <Phase label="Data layer" state="done" />}
        <Phase label="Gate" state={gateDone ? "done" : analystsDone ? "active" : "pending"} />
        <Phase
          label="Synthesis"
          state={synthesisDone ? "done" : gateDone && live ? "active" : "pending"}
        />
      </div>

      <ul className="divide-y divide-[var(--border-faint)]">
        {data.members.map((m) => (
          <li key={m.id} className="px-4 py-2.5">
            <div className="flex items-start gap-2">
              <span className="mt-0.5 shrink-0">
                {m.done ? (
                  <Check size={14} className="text-emerald-600" />
                ) : (
                  <Loader2 size={14} className="animate-spin text-[var(--ink-muted)]" />
                )}
              </span>
              <div className="min-w-0">
                <div className="text-[13px] font-medium text-[var(--ink)]">{lensTitle(m.lens)}</div>
                {m.stance && (
                  <div className="text-[13px] text-[var(--ink)]">{m.stance}</div>
                )}
                {m.brief && (
                  <div className="mt-0.5 text-[12px] leading-snug text-[var(--ink-muted)]">
                    {m.brief}
                  </div>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>

      {data.research && data.research.citations.length > 0 && (
        <div className="border-t border-[var(--border-faint)] px-4 py-3">
          <div className="flex items-center gap-2">
            <Globe size={15} strokeWidth={1.9} className="text-[var(--brand-600)]" />
            <span className="text-[12px] font-semibold uppercase tracking-wide text-[var(--ink-muted)]">
              Live web research
            </span>
            <span className="text-[12px] text-[var(--ink-muted)]">
              {data.research.citations.length} sources
            </span>
          </div>
          <details className="group mt-2">
            <summary className="cursor-pointer list-none text-[12px] font-medium text-[var(--brand-600)] hover:underline">
              Research brief
            </summary>
            <p className="thin-scroll mt-1.5 max-h-[180px] overflow-y-auto whitespace-pre-wrap rounded-lg bg-[var(--sidebar-bg)] px-3 py-2 text-[12px] leading-5 text-[var(--ink-muted)]">
              {data.research.summary}
            </p>
          </details>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {data.research.citations.map((c, i) => (
              <a
                key={i}
                href={c.url}
                target="_blank"
                rel="noreferrer"
                title={c.title}
                className="inline-flex max-w-[220px] items-center gap-1 truncate rounded-full border border-[var(--border-faint)] bg-white px-2.5 py-1 text-[12px] text-[var(--ink-muted)] transition-colors hover:border-[var(--brand)] hover:text-[var(--ink)]"
              >
                <ExternalLink size={10} className="shrink-0" />
                {c.title}
              </a>
            ))}
          </div>
        </div>
      )}

      {data.ground && (
        <div className="border-t border-[var(--border-faint)] px-4 py-3">
          <div className="flex items-center gap-2">
            <Database size={15} strokeWidth={1.9} className="text-[var(--brand-600)]" />
            <span className="text-[12px] font-semibold uppercase tracking-wide text-[var(--ink-muted)]">
              Vaticinus data layer
            </span>
            <span className="text-[12px] text-[var(--ink-muted)]">concept and dependency graph</span>
          </div>
          <details className="group mt-2">
            <summary className="cursor-pointer list-none text-[12px] font-medium text-[var(--brand-600)] hover:underline">
              Graph read
            </summary>
            <p className="thin-scroll mt-1.5 max-h-[180px] overflow-y-auto whitespace-pre-wrap rounded-lg bg-[var(--sidebar-bg)] px-3 py-2 text-[12px] leading-5 text-[var(--ink-muted)]">
              {data.ground}
            </p>
          </details>
        </div>
      )}

      {data.gate && (
        <div className="border-t border-[var(--border-faint)] bg-[var(--sidebar-bg)] px-4 py-3">
          <div className="flex items-center gap-2">
            <Scale size={15} strokeWidth={1.9} className="text-[var(--ink)]" />
            <span className="text-[12px] font-semibold uppercase tracking-wide text-[var(--ink-muted)]">
              Gate
            </span>
            <span
              className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ${verdictColor(
                data.gate.verdict,
              )}`}
            >
              {data.gate.verdict}
            </span>
          </div>
          <p className="mt-1.5 text-[13px] leading-snug text-[var(--ink)]">{data.gate.priced}</p>
          {data.gate.anchor.status === "priced" && data.gate.anchor.top ? (
            <a
              href={data.gate.anchor.top.url}
              target="_blank"
              rel="noreferrer"
              className="mt-1 inline-flex items-center gap-1 text-[12px] text-[var(--brand-600)] hover:underline"
            >
              live {data.gate.anchor.top.source} anchor: {(data.gate.anchor.top.prob * 100).toFixed(0)}%
              <ExternalLink size={11} />
            </a>
          ) : data.gate.anchor.status === "none" ? (
            <p className="mt-1 text-[12px] italic leading-snug text-[var(--ink-muted)]">
              No public prediction market trades this yet. A genuinely early structural call usually is not
              traded anywhere, so the crowd has not arrived. That is where the edge lives, not a defect.
            </p>
          ) : (
            <p className="mt-1 text-[12px] italic leading-snug text-[var(--ink-muted)]">
              The live crowd cross-check was unavailable this run. The call stands on its structural read.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
