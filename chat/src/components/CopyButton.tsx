"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";

// Copy-to-clipboard affordance for an assistant message. Standard chat-UX action:
// shows a brief "Copied" check on success and falls back silently if clipboard is blocked.
export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setDone(true);
      setTimeout(() => setDone(false), 1400);
    } catch {
      // clipboard unavailable (insecure context / denied) — no-op
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[12px] text-[var(--ink-muted)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]"
      aria-label={label}
    >
      {done ? <Check size={14} strokeWidth={2} /> : <Copy size={14} strokeWidth={1.9} />}
      {done ? "Copied" : label}
    </button>
  );
}
