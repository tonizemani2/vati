"use client";

import { ArrowUpRight, Target, Mail, Coins, Users, Link as LinkIcon } from "lucide-react";
import type { CapturePlan } from "@/lib/capture";
import type { Contact } from "@/lib/contacts";

// Where the contextual mandate handoff routes. This is the monetization motion that falls out
// of the value: the reader has a real named play in front of them, and the next click is "have
// Vaticinus run it". The play context is prefilled into the booking notes.
const CAL_URL = "https://cal.com/vaticinus/30min";

export function CapturePlanCard({
  plan,
  question,
  contacts,
  contactsNote,
  contactsLoading,
  contactsPhase,
  contactsError,
  streaming,
  onFindContacts,
}: {
  plan: CapturePlan;
  question: string;
  contacts?: Contact[];
  contactsNote?: string;
  contactsLoading?: boolean;
  contactsPhase?: string;
  contactsError?: string;
  streaming?: boolean;
  onFindContacts?: () => void;
}) {
  const pass = plan.verdict === "PASS";
  const notes = [
    `Play: ${plan.headline}`,
    `Thesis: ${question}`,
    plan.value_mechanism ? `Mechanism: ${plan.value_mechanism}` : "",
    plan.targets?.[0]?.org ? `First target: ${plan.targets[0].org}` : "",
  ]
    .filter(Boolean)
    .join("\n");
  const calHref = `${CAL_URL}?notes=${encodeURIComponent(notes.slice(0, 900))}`;

  return (
    <div className="vati-card mt-4 w-full max-w-[640px] min-w-0 p-4 sm:p-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="vati-tag">Value-capture play</span>
        <span
          className={`text-[11px] font-semibold uppercase tracking-wider ${
            pass ? "text-rose-300/90" : "text-emerald-300/90"
          }`}
        >
          {pass ? "Pass" : "Pursue"}
        </span>
      </div>

      {plan.headline && (
        <p className="mt-3 break-words text-[15px] font-medium leading-snug text-white">
          {plan.headline}
        </p>
      )}

      {/* The named targets: who to call. The thing nobody gets from a generic chatbot. */}
      {plan.targets.length > 0 && (
        <div className="mt-4">
          <div className="vati-card-label flex items-center gap-1.5">
            <Target size={12} strokeWidth={2} /> who to call
          </div>
          <ul className="mt-2 flex flex-col gap-2">
            {plan.targets.map((t, i) => (
              <li key={i} className="rounded-lg border border-white/10 bg-white/[0.02] p-2.5">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-[13.5px] font-semibold leading-snug text-white">
                    {t.org}
                  </span>
                  {t.role && (
                    <span className="shrink-0 text-[11.5px] text-white/55">{t.role}</span>
                  )}
                </div>
                {t.person && (
                  <p className="mt-0.5 text-[12.5px] text-[var(--brand-light)]">{t.person}</p>
                )}
                {t.why && <p className="mt-1 text-[12.5px] leading-snug text-white/65">{t.why}</p>}
                {t.reach && (
                  <p className="mt-1 text-[12px] leading-snug text-white/45">
                    <span className="text-white/60">reach: </span>
                    {t.reach}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* The exact ask */}
      {plan.the_ask && (
        <div className="mt-4 rounded-lg border border-[var(--brand)]/40 bg-[rgba(109,106,252,0.08)] p-3">
          <div className="vati-card-label flex items-center gap-1.5 text-[var(--brand-light)]">
            <Mail size={12} strokeWidth={2} /> what to say first
          </div>
          <p className="mt-1.5 text-[13px] leading-snug text-white/85">{`"${plan.the_ask}"`}</p>
        </div>
      )}

      {/* How the money is made */}
      <div className="mt-4 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
        {plan.value_mechanism && (
          <Field icon={<Coins size={12} strokeWidth={2} />} label="value mechanism" value={plan.value_mechanism} />
        )}
        {plan.who_pays && <Field label="who pays" value={plan.who_pays} />}
        {plan.instrument && <Field label="instrument" value={plan.instrument} />}
        {plan.our_angle && <Field label="our angle" value={plan.our_angle} />}
      </div>

      {plan.proof_to_show && <Field className="mt-3" label="proof to put in front of them" value={plan.proof_to_show} />}
      {plan.first_move && <Field className="mt-3" label="first move this week" value={plan.first_move} emphasis />}

      {plan.checkpoints.length > 0 && (
        <div className="mt-3">
          <div className="vati-card-label">keep-going signals</div>
          <ul className="mt-1.5 flex flex-col gap-1.5">
            {plan.checkpoints.map((c, i) => (
              <li key={i} className="flex gap-2 text-[12.5px] leading-snug text-white/70">
                <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-[var(--brand-light)]" />
                {c}
              </li>
            ))}
          </ul>
        </div>
      )}

      {plan.disqualifier && (
        <p className="mt-3 text-[12px] italic leading-snug text-white/50">
          <span className="text-white/65">what kills it: </span>
          {plan.disqualifier}
        </p>
      )}

      {plan.citations && plan.citations.length > 0 && (
        <div className="mt-4 border-t border-white/10 pt-3">
          <div className="vati-card-label">sources</div>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {plan.citations.map((c, i) => (
              <a
                key={i}
                href={c.url}
                target="_blank"
                rel="noreferrer nofollow"
                className="vati-prov-chip hover:text-white"
              >
                {c.title}
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Rung 3: find who to call. Resolves the named targets into real, verified contacts. */}
      {!pass && (
        <div className="mt-4 border-t border-white/10 pt-4">
          {contacts ? (
            contacts.length > 0 ? (
              <div>
                <div className="vati-card-label flex items-center gap-1.5">
                  <Users size={12} strokeWidth={2} /> people to contact
                </div>
                <ul className="mt-2 flex flex-col gap-2">
                  {contacts.map((c, i) => (
                    <ContactRow key={i} c={c} />
                  ))}
                </ul>
                {contactsNote && <p className="mt-2 text-[11.5px] italic leading-snug text-white/45">{contactsNote}</p>}
              </div>
            ) : (
              <p className="text-[12.5px] leading-snug text-white/55">
                {contactsNote || "No contact could be confidently tied to a target. Nothing surfaced rather than guess."}
              </p>
            )
          ) : contactsLoading ? (
            <div className="flex items-center gap-3 text-[13px] text-white/70">
              <span className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-white/20 border-t-[var(--brand-light)]" />
              {contactsPhase || "Finding who to call"}…
            </div>
          ) : (
            <div className="flex flex-col gap-1.5">
              <button
                type="button"
                onClick={onFindContacts}
                disabled={streaming || !onFindContacts}
                className="inline-flex w-fit items-center gap-2 rounded-full border border-[var(--brand)]/50 px-3.5 py-1.5 text-[13px] font-medium text-[var(--brand-light)] transition-colors hover:bg-[rgba(109,106,252,0.1)] disabled:opacity-40"
              >
                <Users size={15} strokeWidth={2} /> Find who to call
              </button>
              {contactsError && <p className="text-[12px] text-white/50">{contactsError}</p>}
            </div>
          )}
        </div>
      )}

      {/* The contextual handoff: the monetization motion born from the value, tied to THIS play. */}
      <div className="mt-4 flex flex-col gap-2 border-t border-white/10 pt-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-[12.5px] leading-snug text-white/60">
          {pass
            ? "We would not chase this one. If you see an angle we missed, talk it through with us."
            : "Want us to run this play, make the introductions, and structure the deal?"}
        </p>
        <a
          href={calHref}
          target="_blank"
          rel="noreferrer"
          className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-full bg-[var(--brand)] px-4 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-90"
        >
          Run this as a mandate <ArrowUpRight size={15} strokeWidth={2.2} />
        </a>
      </div>
    </div>
  );
}

function ContactRow({ c }: { c: Contact }) {
  const pct = Math.round((c.confidence ?? 0) * 100);
  const meta = [c.title, c.org, c.location].filter(Boolean).join(" · ");
  return (
    <li className="rounded-lg border border-white/10 bg-white/[0.02] p-2.5">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[13.5px] font-semibold leading-snug text-white">{c.name || "Unnamed"}</span>
        {pct > 0 && (
          <span
            className={`shrink-0 text-[11px] font-semibold ${
              pct >= 70 ? "text-emerald-300/90" : pct >= 50 ? "text-amber-300/90" : "text-white/45"
            }`}
            title="match confidence"
          >
            {pct}% match
          </span>
        )}
      </div>
      {meta && <p className="mt-0.5 text-[12px] text-white/55">{meta}</p>}
      {c.why_relevant && <p className="mt-1 text-[12.5px] leading-snug text-white/65">{c.why_relevant}</p>}
      {(c.email || c.linkedin || c.phone || c.source) && (
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px]">
          {c.email && (
            <a href={`mailto:${c.email}`} className="inline-flex items-center gap-1 text-[var(--brand-light)] hover:text-white">
              <Mail size={11} strokeWidth={2} /> {c.email}
            </a>
          )}
          {c.linkedin && (
            <a
              href={c.linkedin.startsWith("http") ? c.linkedin : `https://${c.linkedin}`}
              target="_blank"
              rel="noreferrer nofollow"
              className="inline-flex items-center gap-1 text-[var(--brand-light)] hover:text-white"
            >
              <LinkIcon size={11} strokeWidth={2} /> LinkedIn
            </a>
          )}
          {!c.linkedin && c.source && (
            <a
              href={c.source.startsWith("http") ? c.source : `https://${c.source}`}
              target="_blank"
              rel="noreferrer nofollow"
              className="inline-flex items-center gap-1 text-[var(--brand-light)] hover:text-white"
            >
              <LinkIcon size={11} strokeWidth={2} /> source
            </a>
          )}
          {c.phone && <span className="text-white/50">{c.phone}</span>}
        </div>
      )}
    </li>
  );
}

function Field({
  label,
  value,
  icon,
  className,
  emphasis,
}: {
  label: string;
  value: string;
  icon?: React.ReactNode;
  className?: string;
  emphasis?: boolean;
}) {
  return (
    <div className={className}>
      <div className="vati-card-label flex items-center gap-1.5">
        {icon}
        {label}
      </div>
      <p
        className={`mt-1 text-[12.5px] leading-snug ${
          emphasis ? "font-medium text-white/90" : "text-white/75"
        }`}
      >
        {value}
      </p>
    </div>
  );
}
