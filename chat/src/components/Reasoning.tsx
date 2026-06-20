"use client";

import { useState } from "react";
import { ChevronRight, Brain } from "lucide-react";
import { cn } from "@/lib/cn";

export function Reasoning({ text, live }: { text: string; live: boolean }) {
  // Auto-open while the model is actively thinking; collapsible once the answer starts.
  const [openOverride, setOpenOverride] = useState<boolean | null>(null);
  const open = openOverride ?? live;

  if (!text) return null;

  return (
    <div className="mb-2">
      <button
        onClick={() => setOpenOverride(!open)}
        className="flex items-center gap-1.5 text-[13px] font-medium text-[var(--ink-muted)] transition-colors hover:text-[var(--ink)]"
      >
        <Brain size={14} strokeWidth={1.9} className="text-[var(--brand)]" />
        {live ? "Thinking" : "Reasoning"}
        <ChevronRight
          size={14}
          strokeWidth={2}
          className={cn("transition-transform", open && "rotate-90")}
        />
      </button>
      {open && (
        <div className="thin-scroll mt-2 max-h-[260px] overflow-y-auto border-l-2 border-[var(--border-faint)] pl-3">
          <p className="whitespace-pre-wrap text-[13px] leading-6 text-[var(--ink-muted)]">
            {text}
            {live && <span className="caret" />}
          </p>
        </div>
      )}
    </div>
  );
}
