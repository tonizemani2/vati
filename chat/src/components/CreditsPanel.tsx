"use client";

import { useCallback, useEffect, useState } from "react";
import { Coins, Zap, X, Repeat, Settings2 } from "lucide-react";

type Plan = { tier: string | null; creditsPerMonth: number } | null;
type Account = {
  signedIn: boolean;
  credits: number;
  freeCouncilRemaining: number;
  plan?: Plan;
  unlimited?: boolean;
  owner?: boolean;
  viewAsUser?: boolean;
};
type Pack = { id: string; label: string; credits: number; amountCents: number };
type SubPlan = { id: string; label: string; creditsPerMonth: number; amountCents: number };

// Page dispatches this with the fresh account after each council run so the badge updates
// without a refetch. Anyone can also fire it to force a refresh.
export const CREDITS_EVENT = "vati-credits";
// Fire this (e.g. on a 402 from the council) to pop the buy-credits modal open.
export const OPEN_CREDITS_EVENT = "vati-open-credits";

export function CreditsPanel() {
  const [acct, setAcct] = useState<Account | null>(null);
  const [packs, setPacks] = useState<Pack[]>([]);
  const [plans, setPlans] = useState<SubPlan[]>([]);
  const [billingOn, setBillingOn] = useState(false);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(() => {
    fetch("/api/credits")
      .then((r) => r.json())
      .then((d) => setAcct(d))
      .catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
    fetch("/api/checkout")
      .then((r) => r.json())
      .then((d) => {
        setBillingOn(Boolean(d?.configured));
        if (Array.isArray(d?.packs)) setPacks(d.packs);
        if (Array.isArray(d?.plans)) setPlans(d.plans);
      })
      .catch(() => {});
    const onEvt = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.account) setAcct((a) => ({ ...(a ?? { signedIn: true }), ...detail.account }));
      else refresh();
    };
    const onOpen = () => {
      setOpen(true);
      refresh();
    };
    window.addEventListener(CREDITS_EVENT, onEvt);
    window.addEventListener(OPEN_CREDITS_EVENT, onOpen);
    return () => {
      window.removeEventListener(CREDITS_EVENT, onEvt);
      window.removeEventListener(OPEN_CREDITS_EVENT, onOpen);
    };
  }, [refresh]);

  // Owner-only QA: flip between unlimited owner view and the real normal-user paywall.
  // The cookie can only downgrade the owner, so setting it from the client is safe.
  function toggleViewAsUser() {
    const next = !acct?.viewAsUser;
    document.cookie = next
      ? "vati_as_user=1; Path=/; Max-Age=2592000; SameSite=Lax"
      : "vati_as_user=; Path=/; Max-Age=0; SameSite=Lax";
    setTimeout(refresh, 0);
    window.dispatchEvent(new Event(CREDITS_EVENT));
  }

  async function go(path: string, body: Record<string, unknown>, key: string) {
    setBusy(key);
    try {
      const res = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const d = await res.json();
      if (d?.url) window.location.href = d.url;
      else alert(d?.error || "could not start checkout");
    } finally {
      setBusy(null);
    }
  }

  if (!acct?.signedIn) return null;
  const planLabel = acct.plan?.tier;

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="mt-2 flex w-full items-center gap-2.5 rounded-[10px] px-[10px] py-[7px] text-left text-[14px] text-[var(--ink)] transition-colors hover:bg-[var(--surface-hover)]"
      >
        <span className="flex h-5 w-5 items-center justify-center text-[var(--brand-600)]">
          <Coins size={18} strokeWidth={1.8} />
        </span>
        <span className="truncate">
          {acct.unlimited ? (
            "Unlimited"
          ) : (
            <>
              {acct.credits} credits
              <span className="text-[var(--ink-muted)]"> · {acct.freeCouncilRemaining} free</span>
            </>
          )}
        </span>
        <span className="ml-auto text-[12px] font-medium capitalize text-[var(--brand-600)]">
          {planLabel ?? "Upgrade"}
        </span>
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"
          onClick={() => setOpen(false)}
        >
          <div
            className="max-h-[88vh] w-full max-w-[460px] overflow-y-auto rounded-2xl bg-white p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h3 className="text-[16px] font-semibold text-[var(--ink)]">Convene the council</h3>
              <button onClick={() => setOpen(false)} className="text-[var(--ink-muted)] hover:text-[var(--ink)]">
                <X size={18} />
              </button>
            </div>
            <p className="mt-1 text-[13px] text-[var(--ink-muted)]">
              Quick forecasts are free. Each council run convenes five analysts and a gate to put a
              number on a question the market has not.{" "}
              {acct.unlimited
                ? "Your account has unlimited council and deep runs."
                : `You have ${acct.credits} credits and ${acct.freeCouncilRemaining} free council runs left this month.`}
            </p>

            {acct.owner && (
              <button
                onClick={toggleViewAsUser}
                className="mt-3 flex w-full items-center justify-between rounded-xl border border-dashed border-[var(--border-faint)] px-3 py-2 text-[12px] text-[var(--ink-muted)] transition-colors hover:border-[var(--brand)]"
              >
                <span>
                  {acct.viewAsUser
                    ? "Viewing as a normal user — paywall + credits are live for QA"
                    : "Owner account (unlimited). Test the real paywall as a user would see it."}
                </span>
                <span className="ml-2 shrink-0 font-medium text-[var(--brand-600)]">
                  {acct.viewAsUser ? "Back to owner" : "View as user"}
                </span>
              </button>
            )}

            {!billingOn ? (
              <div className="mt-4 rounded-xl bg-[var(--sidebar-bg)] p-3 text-[13px] text-[var(--ink-muted)]">
                Billing is not switched on yet. Add your Stripe keys to enable purchases.
              </div>
            ) : (
              <>
                {/* Memberships */}
                <div className="mt-4 flex items-center justify-between">
                  <span className="text-[12px] font-semibold uppercase tracking-wide text-[var(--ink-muted)]">
                    Monthly membership
                  </span>
                  {planLabel && (
                    <button
                      onClick={() => go("/api/portal", {}, "portal")}
                      disabled={busy !== null}
                      className="flex items-center gap-1 text-[12px] font-medium text-[var(--brand-600)] hover:underline disabled:opacity-50"
                    >
                      <Settings2 size={12} /> Manage {planLabel}
                    </button>
                  )}
                </div>
                <div className="mt-2 flex flex-col gap-2">
                  {plans.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => go("/api/checkout", { type: "sub", id: p.id }, "sub-" + p.id)}
                      disabled={busy !== null || acct.plan?.tier === p.id}
                      className="flex items-center justify-between rounded-xl border border-[var(--border-faint)] px-4 py-3 text-left transition-colors hover:border-[var(--brand)] disabled:opacity-50"
                    >
                      <span className="flex items-center gap-2">
                        <Repeat size={16} className="text-[var(--brand-600)]" />
                        <span className="text-[14px] font-medium text-[var(--ink)]">{p.label}</span>
                        <span className="text-[13px] text-[var(--ink-muted)]">
                          {p.creditsPerMonth} credits / mo
                        </span>
                      </span>
                      <span className="text-[14px] font-semibold text-[var(--ink)]">
                        ${(p.amountCents / 100).toFixed(0)}
                        <span className="text-[12px] font-normal text-[var(--ink-muted)]">/mo</span>
                      </span>
                    </button>
                  ))}
                </div>

                {/* One-time top-ups */}
                <div className="mt-4 text-[12px] font-semibold uppercase tracking-wide text-[var(--ink-muted)]">
                  One-time top-up
                </div>
                <div className="mt-2 flex flex-col gap-2">
                  {packs.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => go("/api/checkout", { type: "pack", id: p.id }, "pack-" + p.id)}
                      disabled={busy !== null}
                      className="flex items-center justify-between rounded-xl border border-[var(--border-faint)] px-4 py-3 text-left transition-colors hover:border-[var(--brand)] disabled:opacity-50"
                    >
                      <span className="flex items-center gap-2">
                        <Zap size={16} className="text-[var(--brand-600)]" />
                        <span className="text-[14px] font-medium text-[var(--ink)]">{p.label}</span>
                        <span className="text-[13px] text-[var(--ink-muted)]">{p.credits} credits</span>
                      </span>
                      <span className="text-[14px] font-semibold text-[var(--ink)]">
                        ${(p.amountCents / 100).toFixed(0)}
                      </span>
                    </button>
                  ))}
                </div>

                {/* Route fund/desk-scale demand to a booked conversation, not a bigger pack. */}
                <a
                  href="https://cal.com/vaticinus/30min"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-4 block rounded-xl bg-[var(--sidebar-bg)] px-4 py-3 text-[13px] text-[var(--ink-muted)] transition-colors hover:text-[var(--ink)]"
                >
                  Running this for a fund or a desk?{" "}
                  <span className="font-medium text-[var(--brand-600)]">Book a call →</span>
                </a>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
