"use client";

import { useRef, useEffect, useState } from "react";
import { ArrowUp, Square, Zap, Users, Telescope, Compass, ChevronDown, Check } from "lucide-react";

export type Tier = "quick" | "council" | "deep" | "scan";

export const TIERS: { id: Tier; label: string; desc: string; cost: string; icon: typeof Zap }[] = [
  { id: "quick", label: "Quick", desc: "Single pass with an engine card", cost: "free", icon: Zap },
  { id: "council", label: "Council", desc: "5 lenses, live research, priced-in gate", cost: "1 credit", icon: Users },
  { id: "deep", label: "Deep", desc: "7 lenses for diligence-grade calls", cost: "5 credits", icon: Telescope },
  { id: "scan", label: "Frontier", desc: "Mint pre-consensus calls for an area, grounded in the data layer", cost: "5 credits", icon: Compass },
];

export function Composer({
  value,
  onChange,
  onSubmit,
  onStop,
  streaming,
  tier,
  onTierChange,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  onStop: () => void;
  streaming: boolean;
  tier: Tier;
  onTierChange: (t: Tier) => void;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }, [value]);

  const canSend = value.trim().length > 0;
  const current = TIERS.find((t) => t.id === tier) ?? TIERS[0];
  const CurIcon = current.icon;

  return (
    <div className="composer-pill flex w-full min-w-0 items-end gap-1 px-[10px] py-2">
      {/* depth selector */}
      <div className="relative mb-0.5 shrink-0">
        <button
          type="button"
          onClick={() => setMenuOpen((v) => !v)}
          className="flex h-9 max-w-[128px] items-center gap-1.5 rounded-full border border-[var(--border-faint)] px-2.5 text-[13px] font-medium text-[var(--ink)] hover:bg-[var(--surface-hover)] sm:px-3"
        >
          <CurIcon size={15} strokeWidth={1.9} className="text-[var(--brand-600)]" />
          <span className="truncate">{current.label}</span>
          <ChevronDown size={14} className="text-[var(--ink-muted)]" />
        </button>
        {menuOpen && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
            <div className="absolute bottom-11 left-0 z-20 w-[min(286px,calc(100vw-32px))] overflow-hidden rounded-xl border border-[var(--border-faint)] bg-white shadow-lg">
              {TIERS.map((t) => {
                const Icon = t.icon;
                return (
                  <button
                    key={t.id}
                    onClick={() => {
                      onTierChange(t.id);
                      setMenuOpen(false);
                    }}
                    className="flex w-full items-start gap-2.5 px-3 py-2.5 text-left hover:bg-[var(--surface-hover)]"
                  >
                    <Icon size={16} strokeWidth={1.8} className="mt-0.5 text-[var(--brand-600)]" />
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-1.5">
                        <span className="text-[13px] font-medium text-[var(--ink)]">{t.label}</span>
                        <span className="text-[11px] text-[var(--ink-muted)]">· {t.cost}</span>
                        {t.id === tier && <Check size={13} className="ml-auto text-[var(--brand-600)]" />}
                      </span>
                      <span className="block text-[12px] leading-snug text-[var(--ink-muted)]">
                        {t.desc}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          </>
        )}
      </div>

      <textarea
        ref={ref}
        rows={1}
        value={value}
        placeholder={
          tier === "scan"
            ? "Name an area or industry to scan for pre-consensus calls"
            : tier === "quick"
              ? "Ask for a quick forecast"
              : "Ask for a dated call"
        }
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            if (canSend && !streaming) onSubmit();
          }
        }}
        className="thin-scroll max-h-[200px] min-w-0 flex-1 resize-none bg-transparent py-2 text-[16px] leading-6 text-[var(--ink)] outline-none placeholder:text-[var(--ink-muted)]"
      />

      <div className="mb-0.5 flex shrink-0 items-center gap-1">
        {streaming ? (
          <button
            type="button"
            onClick={onStop}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--ink)] text-white"
            aria-label="Stop"
          >
            <Square size={15} strokeWidth={2} fill="white" />
          </button>
        ) : (
          <button
            type="button"
            onClick={onSubmit}
            disabled={!canSend}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--brand)] text-white transition-opacity hover:opacity-90 disabled:opacity-30"
            aria-label="Send"
          >
            <ArrowUp size={20} strokeWidth={2.2} />
          </button>
        )}
      </div>
    </div>
  );
}
