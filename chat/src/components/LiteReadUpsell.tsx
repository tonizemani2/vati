"use client";

import { ArrowUpRight, Layers } from "lucide-react";
import type { Tier } from "@/components/Composer";

// The honest tier signal. The public chat is the LITE read: fewer analysts, a shallow
// data pull, a faster model. This strip says so plainly and points to the full board, so
// the ceiling is visible and a first-time visitor understands what they are not seeing yet.
export function LiteReadUpsell({
  tier,
  onUpgrade,
}: {
  tier: Tier;
  onUpgrade: () => void;
}) {
  if (tier === "deep") {
    return (
      <div className="mt-3 flex items-center gap-2 rounded-xl border border-[var(--border-faint)] bg-[var(--sidebar-bg)] px-3.5 py-2.5">
        <Layers size={15} strokeWidth={1.9} className="shrink-0 text-[var(--brand-600)]" />
        <p className="text-[12.5px] leading-snug text-[var(--ink-muted)]">
          <span className="font-semibold text-[var(--ink)]">Full board.</span> Seven lenses,
          deeper models, the whole data layer. This is the deep read.
        </p>
      </div>
    );
  }

  return (
    <div className="mt-3 rounded-xl border border-[var(--border-faint)] bg-white px-3.5 py-3">
      <div className="flex items-start gap-2.5">
        <Layers size={16} strokeWidth={1.9} className="mt-0.5 shrink-0 text-[var(--brand-600)]" />
        <div className="min-w-0">
          <p className="text-[13px] font-semibold text-[var(--ink)]">This is the lite read.</p>
          <p className="mt-0.5 text-[12.5px] leading-snug text-[var(--ink-muted)]">
            Five analysts, a shallow data pull, a fast model. The full board runs deeper
            models and more lenses across the whole corpus, and commits to a scored,
            immutable call.
          </p>
          <button
            onClick={onUpgrade}
            className="mt-2 inline-flex items-center gap-1 rounded-full border border-[var(--brand)] px-3 py-1 text-[12px] font-medium text-[var(--brand-600)] transition-colors hover:bg-[rgba(109,106,252,0.08)]"
          >
            Run the full board
            <ArrowUpRight size={13} strokeWidth={2} />
          </button>
        </div>
      </div>
    </div>
  );
}
