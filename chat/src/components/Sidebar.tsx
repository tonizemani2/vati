"use client";

import { SquarePen, ScrollText, CalendarClock, X, MessageSquare } from "lucide-react";
import { cn } from "@/lib/cn";
import { CreditsPanel } from "@/components/CreditsPanel";
import { Account } from "@/components/Account";

export type ConversationSummary = {
  id: string;
  title: string | null;
  updated_at: string;
};

function NavItem({
  icon: Icon,
  label,
  active,
  onClick,
}: {
  icon: React.ComponentType<{ size?: number; strokeWidth?: number }>;
  label: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-2.5 rounded-[10px] px-[10px] py-[7px] text-left text-[14px] leading-5 transition-colors",
        active
          ? "bg-[rgba(109,106,252,0.12)] font-medium text-[var(--brand-600)]"
          : "text-[var(--ink)] hover:bg-[var(--surface-hover)]",
      )}
    >
      <span className="flex h-5 w-5 items-center justify-center">
        <Icon size={18} strokeWidth={1.8} />
      </span>
      <span className="truncate">{label}</span>
    </button>
  );
}

export function Sidebar({
  onNewChat,
  onRecord,
  conversations = [],
  activeConversationId,
  onOpenConversation,
  open = false,
  onClose,
}: {
  onNewChat: () => void;
  onRecord: () => void;
  conversations?: ConversationSummary[];
  activeConversationId?: string | null;
  onOpenConversation?: (id: string) => void;
  open?: boolean;
  onClose?: () => void;
}) {
  // On mobile the sidebar is an off-canvas drawer (slides over the chat, backdrop dims it).
  // On md+ it is a static 260px column that is always visible. `open` only matters on mobile.
  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/40 md:hidden"
          onClick={onClose}
          aria-hidden
        />
      )}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex h-full w-[260px] shrink-0 flex-col bg-[var(--sidebar-bg)] px-2 py-2 transition-transform duration-200 md:static md:z-auto md:translate-x-0",
          open ? "translate-x-0 shadow-xl md:shadow-none" : "-translate-x-full",
        )}
      >
        {/* Brand + close (close only shows on mobile) */}
        <div className="flex items-center justify-between px-1 py-1.5">
          <span className="flex items-center gap-2 px-1">
            <span className="text-[var(--brand)]">
              <VatiMark />
            </span>
            <span className="text-[15px] font-semibold tracking-tight text-[var(--ink)]">
              Vaticinus
            </span>
          </span>
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-md text-[var(--ink-muted)] hover:bg-[var(--surface-hover)] md:hidden"
            aria-label="Close menu"
          >
            <X size={20} strokeWidth={1.8} />
          </button>
        </div>

        {/* Primary nav */}
        <nav className="mt-3 flex flex-col gap-0.5">
          <NavItem icon={SquarePen} label="New forecast" active={!activeConversationId} onClick={onNewChat} />
          <NavItem icon={ScrollText} label="Live record" onClick={onRecord} />
        </nav>

        {conversations.length > 0 && (
          <div className="mt-5 min-h-0 flex-1 overflow-hidden">
            <div className="mb-1 px-[10px] text-[11px] font-semibold uppercase tracking-wide text-[var(--ink-muted)]">
              History
            </div>
            <div className="thin-scroll flex max-h-full flex-col gap-0.5 overflow-y-auto pr-1">
              {conversations.map((c) => (
                <button
                  key={c.id}
                  onClick={() => onOpenConversation?.(c.id)}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-[10px] px-[10px] py-[7px] text-left text-[13px] leading-5 transition-colors",
                    activeConversationId === c.id
                      ? "bg-white font-medium text-[var(--brand-600)] shadow-[0_1px_2px_rgba(12,11,16,0.05)]"
                      : "text-[var(--ink)] hover:bg-[var(--surface-hover)]",
                  )}
                  title={c.title ?? "Untitled forecast"}
                >
                  <MessageSquare size={15} strokeWidth={1.8} className="shrink-0 text-current/70" />
                  <span className="truncate">{c.title || "Untitled forecast"}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {conversations.length === 0 && <div className="flex-1" />}

        {/* Credits + buy */}
        <CreditsPanel />

        {/* Account (sign in / user button) */}
        <Account />

        {/* Public chat is the surface read. The private engagement is framed as a
            board with a mandate, horizon, evidence stack, and kill criteria. */}
        <div className="mt-2 rounded-[12px] border border-[var(--border-faint)] bg-white px-3 py-3 shadow-[0_1px_2px_rgba(12,11,16,0.04)]">
          <p className="flex items-center gap-1.5 text-[13px] font-semibold leading-tight text-[var(--ink)]">
            <CalendarClock size={15} strokeWidth={1.8} className="text-[var(--brand-600)]" />
            Private board
          </p>
          <p className="mt-1.5 text-[12px] leading-snug text-[var(--ink-muted)]">
            The chat is a surface read. For a mandate, we scope the market,
            horizon, evidence stack, and kill criteria.
          </p>
          <a
            href="https://cal.com/vaticinus/30min"
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 flex h-9 items-center justify-center rounded-full bg-[var(--brand)] px-3 text-[13px] font-semibold text-white transition-opacity hover:opacity-90"
          >
            Scope the board
          </a>
        </div>

        <div className="mt-3 flex items-center gap-3 px-2 text-[11px] text-[var(--ink-muted)]">
          <a
            href="https://vaticinus.com/privacy-policy/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-[var(--ink)]"
          >
            Privacy
          </a>
          <a
            href="https://vaticinus.com/terms-of-service/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-[var(--ink)]"
          >
            Terms
          </a>
        </div>
      </aside>
    </>
  );
}

function VatiMark() {
  return (
    <img src="/brand-mark.svg" alt="" className="h-7 w-7 rounded-[7px]" />
  );
}
