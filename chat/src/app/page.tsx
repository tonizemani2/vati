"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowDown, ClipboardList, Menu, Radar, Route, RotateCcw, Scale, ScrollText } from "lucide-react";
import { Sidebar, type ConversationSummary } from "@/components/Sidebar";
import { Composer, type Tier } from "@/components/Composer";
import { Reasoning } from "@/components/Reasoning";
import { Council, type CouncilData } from "@/components/Council";
import { Markdown } from "@/components/Markdown";
import { CopyButton } from "@/components/CopyButton";
import { CREDITS_EVENT, OPEN_CREDITS_EVENT } from "@/components/CreditsPanel";
import { ForecastCard, type ForecastCardData } from "@/components/ForecastCard";
import { CapturePlanCard } from "@/components/CapturePlan";
import type { CapturePlan } from "@/lib/capture";
import type { Contact } from "@/lib/contacts";
import { LiteReadUpsell } from "@/components/LiteReadUpsell";
import {
  stripSpecForDisplay,
  extractSpec,
  cardFromSpec,
  cardFromSpecComputed,
  withSpecForPersist,
  parsePersistedSpec,
  parseMarkerJson,
  CAPTURE_MARKER,
  CONTACTS_MARKER,
} from "@/lib/forecast";

type Msg = {
  id: number;
  role: "user" | "assistant";
  content: string;
  reasoning?: string;
  council?: CouncilData;
  card?: ForecastCardData;
  cards?: ForecastCardData[];
  heading?: string;
  // The value-capture play built from this message's forecast (on-demand, paid).
  capture?: CapturePlan;
  captureLoading?: boolean;
  capturePhase?: string;
  captureError?: string;
  // Rung 3: the real contacts sourced from the play's targets (on-demand, paid).
  contacts?: Contact[];
  contactsNote?: string;
  contactsLoading?: boolean;
  contactsPhase?: string;
  contactsError?: string;
};

const FALLBACK_CHIPS = [
  "Where does the binding constraint in AI move next: chips, power, or data?",
  "Will US grid interconnection queue waits exceed 4 years by end of 2027?",
  "Is HVDC cable-lay vessel capacity the pace-setter for offshore grid buildout?",
];

const STARTER_CARDS = [
  {
    title: "Constraint map",
    prompt: "Where does the binding constraint move next in AI data center power by 2027?",
    icon: Route,
  },
  {
    title: "Priced-in gap",
    prompt: "What is the most mispriced bottleneck in humanoid robotics over the next 18 months?",
    icon: Scale,
  },
  {
    title: "Watchlist",
    prompt: "Build a watchlist for whether extrahepatic in-vivo gene editing is crossing into humans.",
    icon: Radar,
  },
  {
    title: "Action memo",
    prompt: "If transformer scarcity migrates upstream, what should a data center operator do now?",
    icon: ClipboardList,
  },
];

export default function Page() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [tier, setTier] = useState<Tier>("council");
  const [chips, setChips] = useState<string[]>(FALLBACK_CHIPS);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [navOpen, setNavOpen] = useState(false);
  const [showJump, setShowJump] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  // Whether the view is "stuck" to the bottom. We only auto-scroll while streaming if the
  // reader is already at the bottom — so scrolling up to re-read no longer yanks you back.
  const stickRef = useRef(true);
  const idRef = useRef(0);
  const convIdRef = useRef<string | null>(null);
  const autoStartedRef = useRef(false);

  const empty = messages.length === 0;

  const refreshConversations = useCallback(async () => {
    const data = await fetch("/api/conversations").then((r) => r.json()).catch(() => null);
    if (data?.ok && Array.isArray(data.conversations)) {
      setConversations(data.conversations);
    }
  }, []);

  // Seed the starter chips from our real sealed forward calls.
  useEffect(() => {
    fetch("/api/record")
      .then((r) => r.json())
      .then((d) => {
        if (d?.ok && Array.isArray(d.calls) && d.calls.length) {
          const qs = d.calls
            .map((c: { question?: string }) => c.question)
            .filter(Boolean)
            .slice(0, 3);
          if (qs.length) setChips(qs);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    refreshConversations();
  }, [refreshConversations]);

  useEffect(() => {
    if (autoStartedRef.current) return;
    const params = new URLSearchParams(window.location.search);
    const q = (params.get("q") || "").trim();
    const auto = params.get("auto") === "1";
    const requestedTier = params.get("tier");
    if (requestedTier === "quick" || requestedTier === "council" || requestedTier === "deep") {
      setTier(requestedTier);
    }
    if (!q) return;
    autoStartedRef.current = true;
    setInput(q);
    if (auto) {
      window.history.replaceState(null, "", window.location.pathname);
      send(q);
    }
  }, []);

  function scrollToBottom() {
    requestAnimationFrame(() => {
      const el = scrollRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    });
  }

  // Auto-scroll only when the reader is already near the bottom. While a reply streams,
  // scrolling up sets stick=false so new tokens stop yanking the view down.
  function autoScroll() {
    if (stickRef.current) scrollToBottom();
  }

  // Track the reader's position; the "jump to latest" button shows when scrolled up.
  function onScroll() {
    const el = scrollRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    const atBottom = distance < 120;
    stickRef.current = atBottom;
    setShowJump(!atBottom);
  }

  function jumpToLatest() {
    stickRef.current = true;
    setShowJump(false);
    scrollToBottom();
  }

  function scrollToTop() {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const el = scrollRef.current;
        if (el) el.scrollTop = 0;
      });
    });
  }

  function patch(id: number, fn: (m: Msg) => Msg) {
    setMessages((prev) => prev.map((m) => (m.id === id ? fn(m) : m)));
  }

  // Turn the council's real inputs into card provenance ("the receipts"): how many
  // analysts deliberated, how many live sources grounded it, and what the crowd-price
  // check found. This is what makes a call visibly more than a single prompt.
  function councilProvenance(c: CouncilData): ForecastCardData["provenance"] {
    const anchor = c.gate?.anchor;
    const crowd =
      anchor?.status === "priced" && anchor.top
        ? `${Math.round(anchor.top.prob * 100)}%`
        : anchor?.status === "none"
          ? "UNPRICED"
          : anchor?.status === "unchecked"
            ? "unchecked"
            : undefined;
    return {
      analysts: c.members.filter((m) => m.done).length || undefined,
      sources: c.research?.citations.length || undefined,
      crowd,
    };
  }

  async function runEngineForCard(msgId: number, spec: Record<string, unknown>) {
    try {
      const res = await fetch("/api/forecast", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...spec, conversation_id: convIdRef.current }),
      });
      const data = await res.json();
      patch(msgId, (m) => {
        if (!m.card) return m;
        if (data?.ok) {
          return {
            ...m,
            card: {
              ...m.card,
              pending: false,
              probability: data.probability,
              median: data.median,
              ci_low: data.ci_low,
              ci_high: data.ci_high,
              threshold: data.threshold ?? m.card.threshold,
              threshold_dir: data.threshold_dir ?? m.card.threshold_dir,
              histogram: data.histogram,
              n_samples: data.n_samples,
              provenance: m.card.provenance
                ? { ...m.card.provenance, draws: data.n_samples }
                : { draws: data.n_samples },
            },
          };
        }
        return { ...m, card: { ...m.card, pending: false, error: String(data?.error || "engine error") } };
      });
      autoScroll();
    } catch {
      patch(msgId, (m) =>
        m.card ? { ...m, card: { ...m.card, pending: false, error: "engine unreachable" } } : m,
      );
    }
  }

  // Turn a forecast into a value-capture play: who to call, the exact ask, the value
  // mechanism, who pays. Streams phase events then the structured plan. Paid; an anon caller
  // hits the 402 gate and is nudged to sign in (the conversion funnel).
  async function runCapturePlay(msgId: number, question: string, context: string) {
    if (streaming) return;
    patch(msgId, (m) => ({
      ...m,
      captureLoading: true,
      capturePhase: "Starting",
      capture: undefined,
      captureError: undefined,
    }));
    autoScroll();
    try {
      const res = await fetch("/api/capture", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, context, conversation_id: convIdRef.current }),
      });
      if (res.status === 402) {
        const body = await res.json().catch(() => ({}) as { anon?: boolean });
        patch(msgId, (m) => ({
          ...m,
          captureLoading: false,
          capturePhase: undefined,
          captureError: body?.anon
            ? "Sign in to build the value-capture play."
            : "Out of credits. Top up to build the value-capture play.",
        }));
        if (!body?.anon) window.dispatchEvent(new Event(OPEN_CREDITS_EVENT));
        return;
      }
      if (!res.ok || !res.body) {
        patch(msgId, (m) => ({
          ...m,
          captureLoading: false,
          capturePhase: undefined,
          captureError: "Could not build the play, please try again.",
        }));
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const ev = JSON.parse(line);
            if (ev.t === "account") {
              window.dispatchEvent(new CustomEvent(CREDITS_EVENT, { detail: { account: ev.account } }));
            } else if (ev.t === "phase") {
              patch(msgId, (m) => ({ ...m, capturePhase: ev.v }));
            } else if (ev.t === "plan") {
              patch(msgId, (m) => ({
                ...m,
                capture: ev.plan,
                captureLoading: false,
                capturePhase: undefined,
              }));
            } else if (ev.t === "error") {
              patch(msgId, (m) => ({
                ...m,
                captureLoading: false,
                capturePhase: undefined,
                captureError: String(ev.v || "could not build the play"),
              }));
            }
          } catch {
            // tolerate a stray non-JSON line
          }
        }
        autoScroll();
      }
    } catch {
      patch(msgId, (m) => ({
        ...m,
        captureLoading: false,
        capturePhase: undefined,
        captureError: "Could not reach the capture engine.",
      }));
    }
  }

  // Rung 3: resolve a PURSUE play's named targets into real, verified contacts. Streams phase
  // events then the contact list. Paid; an anon caller hits the 402 gate (conversion funnel).
  async function runFindContacts(msgId: number, question: string, plan: CapturePlan) {
    if (streaming) return;
    patch(msgId, (m) => ({
      ...m,
      contactsLoading: true,
      contactsPhase: "Starting",
      contacts: undefined,
      contactsNote: undefined,
      contactsError: undefined,
    }));
    autoScroll();
    try {
      const res = await fetch("/api/contacts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, plan, conversation_id: convIdRef.current }),
      });
      if (res.status === 402) {
        const body = await res.json().catch(() => ({}) as { anon?: boolean });
        patch(msgId, (m) => ({
          ...m,
          contactsLoading: false,
          contactsPhase: undefined,
          contactsError: body?.anon
            ? "Sign in to find who to call."
            : "Out of credits. Top up to find who to call.",
        }));
        if (!body?.anon) window.dispatchEvent(new Event(OPEN_CREDITS_EVENT));
        return;
      }
      if (res.status === 503) {
        patch(msgId, (m) => ({
          ...m,
          contactsLoading: false,
          contactsPhase: undefined,
          contactsError: "The people finder is not available right now.",
        }));
        return;
      }
      if (!res.ok || !res.body) {
        patch(msgId, (m) => ({
          ...m,
          contactsLoading: false,
          contactsPhase: undefined,
          contactsError: "Could not find contacts, please try again.",
        }));
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const ev = JSON.parse(line);
            if (ev.t === "account") {
              window.dispatchEvent(new CustomEvent(CREDITS_EVENT, { detail: { account: ev.account } }));
            } else if (ev.t === "phase") {
              patch(msgId, (m) => ({ ...m, contactsPhase: ev.v }));
            } else if (ev.t === "contacts") {
              patch(msgId, (m) => ({
                ...m,
                contacts: Array.isArray(ev.contacts) ? ev.contacts : [],
                contactsNote: typeof ev.note === "string" ? ev.note : undefined,
                contactsLoading: false,
                contactsPhase: undefined,
              }));
            } else if (ev.t === "error") {
              patch(msgId, (m) => ({
                ...m,
                contactsLoading: false,
                contactsPhase: undefined,
                contactsError: String(ev.v || "could not find contacts"),
              }));
            }
          } catch {
            // tolerate a stray non-JSON line
          }
        }
        autoScroll();
      }
    } catch {
      patch(msgId, (m) => ({
        ...m,
        contactsLoading: false,
        contactsPhase: undefined,
        contactsError: "Could not reach the people finder.",
      }));
    }
  }

  async function showRecord() {
    stop();
    convIdRef.current = null;
    setActiveConversationId(null);
    const res = await fetch("/api/record").then((r) => r.json()).catch(() => null);
    const calls: Record<string, unknown>[] = res?.ok ? res.calls : [];
    const cards: ForecastCardData[] = calls.slice(0, 12).map((c) => ({
      question: String(c.question ?? ""),
      ci_unit: c.ci_unit as string | undefined,
      resolution_date: c.resolution_date as string | undefined,
      kill_criteria: Array.isArray(c.kill_criteria) ? (c.kill_criteria as string[]) : undefined,
      probability: typeof c.probability === "number" ? c.probability : undefined,
      ci_low: typeof c.ci_low === "number" ? c.ci_low : undefined,
      ci_high: typeof c.ci_high === "number" ? c.ci_high : undefined,
      threshold: typeof c.threshold === "number" ? c.threshold : undefined,
      threshold_dir: c.threshold_dir as string | undefined,
      implications:
        c.implications && typeof c.implications === "object"
          ? (c.implications as ForecastCardData["implications"])
          : undefined,
      pending: false,
    }));
    setMessages([
      {
        id: ++idRef.current,
        role: "assistant",
        content: cards.length
          ? `Here is the live forward record: ${cards.length} dated, leak-free calls, sealed and Brier-scored at resolution. Nearest resolutions first.`
          : "No sealed forward calls are available right now.",
        cards,
        heading: "Live forward record",
      },
    ]);
    scrollToTop();
  }

  async function send(text?: string, tierOverride?: Tier) {
    const content = (text ?? input).trim();
    if (!content || streaming) return;
    const runTier = tierOverride ?? tier;

    const userMsg: Msg = { id: ++idRef.current, role: "user", content };
    const asstMsg: Msg = { id: ++idRef.current, role: "assistant", content: "" };
    const history = [...messages.filter((m) => !m.cards), userMsg];
    setMessages((prev) => [...prev, userMsg, asstMsg]);
    setInput("");
    setStreaming(true);
    stickRef.current = true; // a fresh send always sticks to the new turn
    setShowJump(false);
    scrollToBottom();

    const controller = new AbortController();
    abortRef.current = controller;

    // Frontier scan: mint pre-consensus calls for an area, grounded in the data layer. Distinct
    // output (a set of cards), so it has its own request + stream handling.
    if (runTier === "scan") {
      try {
        const res = await fetch("/api/scan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ area: content, conversation_id: convIdRef.current }),
          signal: controller.signal,
        });
        const cid = res.headers.get("X-Conversation-Id");
        if (cid) {
          convIdRef.current = cid;
          setActiveConversationId(cid);
        }
        if (res.status === 402) {
          const body = await res.json().catch(() => ({}) as { anon?: boolean });
          patch(asstMsg.id, (m) => ({
            ...m,
            content: body?.anon
              ? "Sign in to run a frontier scan."
              : "Out of credits. Top up to run a frontier scan.",
          }));
          if (!body?.anon) window.dispatchEvent(new Event(OPEN_CREDITS_EVENT));
          return;
        }
        if (!res.ok || !res.body) {
          patch(asstMsg.id, (m) => ({ ...m, content: "Could not run the scan, please try again." }));
          return;
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split("\n");
          buf = lines.pop() ?? "";
          for (const ln of lines) {
            if (!ln.trim()) continue;
            try {
              const ev = JSON.parse(ln);
              if (ev.t === "account") {
                window.dispatchEvent(new CustomEvent(CREDITS_EVENT, { detail: { account: ev.account } }));
              } else if (ev.t === "phase" || ev.t === "ground") {
                patch(asstMsg.id, (m) => ({ ...m, content: `${ev.v}…` }));
              } else if (ev.t === "cards") {
                const specs = Array.isArray(ev.specs) ? ev.specs : [];
                const cards = specs.map((s: Record<string, unknown>) => cardFromSpecComputed(s));
                patch(asstMsg.id, (m) => ({
                  ...m,
                  heading: `Frontier scan: ${content.slice(0, 60)}`,
                  content: cards.length
                    ? `${cards.length} pre-consensus call${cards.length === 1 ? "" : "s"}${ev.grounded ? ", grounded in the data layer" : ""}. Each is dated, falsifiable, with a kill criterion.`
                    : "No usable calls came back. Try a more specific area.",
                  cards,
                }));
              } else if (ev.t === "error") {
                patch(asstMsg.id, (m) => ({ ...m, content: String(ev.v || "the scan failed") }));
              }
            } catch {
              // tolerate a stray non-JSON line
            }
          }
          autoScroll();
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          patch(asstMsg.id, (m) => (m.content ? m : { ...m, content: "Could not reach the scan engine." }));
        }
      } finally {
        setStreaming(false);
        abortRef.current = null;
      }
      return;
    }

    const useCouncil = runTier !== "quick";

    try {
      const res = useCouncil
        ? await fetch("/api/council", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question: content, tier: runTier, conversation_id: convIdRef.current }),
            signal: controller.signal,
          })
        : await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              messages: history.map((m) => ({ role: m.role, content: m.content })),
              conversation_id: convIdRef.current,
            }),
            signal: controller.signal,
          });

      const cid = res.headers.get("X-Conversation-Id");
      if (cid) {
        convIdRef.current = cid;
        setActiveConversationId(cid);
      }

      // Out of free/paid council runs. Signed-out visitors get a sign-in nudge (they have no
      // credits panel to top up); signed-in users get the buy-credits flow.
      if (res.status === 402) {
        const body = await res.json().catch(() => ({}) as { anon?: boolean });
        if (body?.anon) {
          patch(asstMsg.id, (m) => ({
            ...m,
            content:
              "You have used your free council runs. Quick forecasts stay free, or sign in to keep running the council and unlock Deep research.",
          }));
        } else {
          patch(asstMsg.id, (m) => ({
            ...m,
            content:
              "You are out of council credits for this month. Quick forecasts stay free, or top up to keep running the council.",
          }));
          window.dispatchEvent(new Event(OPEN_CREDITS_EVENT));
        }
        return;
      }
      if (!res.ok || !res.body) {
        const errText = (await res.text().catch(() => "")) || `error ${res.status}`;
        patch(asstMsg.id, (m) => ({ ...m, content: errText }));
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      let reasoningAcc = "";
      let acc = "";
      const council: CouncilData = { members: [] };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const ev = JSON.parse(line);
            switch (ev.t) {
              case "r":
                reasoningAcc += ev.v;
                break;
              case "c":
                acc += ev.v;
                break;
              case "account":
                window.dispatchEvent(
                  new CustomEvent(CREDITS_EVENT, { detail: { account: ev.account } }),
                );
                break;
              case "member_start":
                if (!council.members.find((mm) => mm.id === ev.id))
                  council.members.push({ id: ev.id, lens: ev.lens, done: false });
                break;
              case "member_done": {
                const mm = council.members.find((x) => x.id === ev.id);
                if (mm) {
                  mm.stance = ev.stance;
                  mm.brief = ev.brief;
                  mm.done = true;
                } else {
                  council.members.push({
                    id: ev.id,
                    lens: ev.lens,
                    stance: ev.stance,
                    brief: ev.brief,
                    done: true,
                  });
                }
                break;
              }
              case "research":
                council.research = { summary: ev.summary, citations: ev.citations ?? [] };
                break;
              case "ground":
                council.ground = ev.summary;
                break;
              case "gate":
                council.gate = {
                  verdict: ev.verdict,
                  priced: ev.priced,
                  lean: ev.lean,
                  anchor: ev.anchor,
                };
                break;
              case "error":
                acc += `\n\n(${ev.v})`;
                break;
            }
          } catch {
            // tolerate a stray non-JSON line
          }
        }
        const visible = stripSpecForDisplay(acc);
        patch(asstMsg.id, (m) => ({
          ...m,
          reasoning: reasoningAcc,
          content: visible,
          council: useCouncil
            ? {
                members: [...council.members],
                research: council.research,
                gate: council.gate,
                ground: council.ground,
              }
            : undefined,
        }));
        autoScroll();
      }

      // Stream done: pull out the forecast spec and run the real engine.
      const { prose, spec } = extractSpec(acc);
      patch(asstMsg.id, (m) => ({ ...m, content: prose }));

      // Persist the assistant turn (best-effort; the server saved the user turn).
      if (convIdRef.current && prose) {
        fetch("/api/messages", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            conversation_id: convIdRef.current,
            // Persist prose + a hidden spec block so reopening the chat rebuilds the card.
            content: withSpecForPersist(prose, spec),
            reasoning: reasoningAcc || null,
          }),
        }).catch(() => {});
      }
      if (spec && spec.base_value != null && spec.threshold != null) {
        const provenance = useCouncil ? councilProvenance(council) : undefined;
        patch(asstMsg.id, (m) => ({ ...m, card: { ...cardFromSpec(spec), provenance } }));
        autoScroll();
        await runEngineForCard(asstMsg.id, spec);
      }
      refreshConversations();
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        patch(asstMsg.id, (m) =>
          m.content ? m : { ...m, content: "Something went wrong reaching the model." },
        );
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }

  function stop() {
    abortRef.current?.abort();
    setStreaming(false);
  }

  // Re-run the last question: drop the current answer (and its user turn, which send re-adds)
  // and ask again. Standard chat affordance for a weak or interrupted reply.
  function regenerate() {
    if (streaming) return;
    let lastUser: Msg | undefined;
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "user") {
        lastUser = messages[i];
        break;
      }
    }
    if (!lastUser) return;
    const content = lastUser.content;
    setMessages((prev) => {
      const idx = prev.findIndex((m) => m.id === lastUser!.id);
      return idx === -1 ? prev : prev.slice(0, idx);
    });
    send(content, tier);
  }

  function newChat() {
    stop();
    setMessages([]);
    setInput("");
    convIdRef.current = null;
    setActiveConversationId(null);
  }

  async function openConversation(id: string) {
    stop();
    const data = await fetch(`/api/conversations?id=${encodeURIComponent(id)}`)
      .then((r) => r.json())
      .catch(() => null);
    if (!data?.ok || !Array.isArray(data.messages)) return;

    // Rebuild rich state from the saved markers so a reopened chat looks like it did live:
    // forecast turns carry a hidden spec (rebuild the card client-side), and capture plays /
    // contact lists were saved as their own marker-led messages (fold them back into the
    // forecast turn they belong to rather than showing raw JSON).
    const raw = (data.messages as Array<{ role?: string; content?: unknown; reasoning?: string | null }>).filter(
      (m) => (m.role === "user" || m.role === "assistant") && typeof m.content === "string",
    );
    const loaded: Msg[] = [];
    let lastCardMsg: Msg | null = null;
    for (const m of raw) {
      const role = m.role as "user" | "assistant";
      const content = m.content as string;

      if (role === "assistant") {
        const capturePlan = parseMarkerJson(content, CAPTURE_MARKER) as CapturePlan | null;
        if (capturePlan) {
          if (lastCardMsg) lastCardMsg.capture = capturePlan;
          continue; // folded in, not a standalone bubble
        }
        const contacts = parseMarkerJson(content, CONTACTS_MARKER) as Contact[] | null;
        if (Array.isArray(contacts)) {
          if (lastCardMsg) lastCardMsg.contacts = contacts;
          continue;
        }
      }

      const { prose, spec } = role === "assistant" ? parsePersistedSpec(content) : { prose: content, spec: null };
      const msg: Msg = {
        id: ++idRef.current,
        role,
        content: prose,
        reasoning: m.reasoning ?? undefined,
      };
      if (spec) msg.card = cardFromSpecComputed(spec);
      loaded.push(msg);
      if (role === "assistant") lastCardMsg = msg;
    }
    convIdRef.current = id;
    setActiveConversationId(id);
    setMessages(loaded);
    setInput("");
    setNavOpen(false);
    scrollToBottom();
  }

  const lastId = messages.length ? messages[messages.length - 1].id : -1;

  return (
    <div className="flex h-dvh w-full overflow-hidden bg-[var(--bg)]">
      <Sidebar
        open={navOpen}
        onClose={() => setNavOpen(false)}
        onNewChat={() => {
          newChat();
          setNavOpen(false);
        }}
        onRecord={() => {
          showRecord();
          setNavOpen(false);
        }}
        conversations={conversations}
        activeConversationId={activeConversationId}
        onOpenConversation={openConversation}
      />

      <main className="relative flex min-w-0 flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex h-[52px] min-w-0 shrink-0 items-center justify-between gap-2 px-4">
          <div className="flex min-w-0 items-center gap-1">
            <button
              onClick={() => setNavOpen(true)}
              className="-ml-1 flex h-9 w-9 items-center justify-center rounded-lg text-[var(--ink)] hover:bg-[var(--surface-hover)] md:hidden"
              aria-label="Open menu"
            >
              <Menu size={22} strokeWidth={2} />
            </button>
            <button
              onClick={newChat}
              className="flex min-w-0 items-center gap-2 truncate rounded-lg px-2 py-1 text-[18px] font-semibold tracking-tight text-[var(--ink)] hover:bg-[var(--surface-hover)] md:hidden"
            >
              <img src="/brand-mark.svg" alt="" className="h-6 w-6 shrink-0 rounded-md" />
              Vaticinus
            </button>
          </div>
          <button
            onClick={showRecord}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[var(--brand)] text-[14px] font-medium text-[var(--brand-600)] transition-colors hover:bg-[rgba(109,106,252,0.08)] sm:w-auto sm:gap-1.5 sm:px-3.5"
            title="Live record"
          >
            <ScrollText size={16} strokeWidth={1.9} />
            <span className="hidden sm:inline">Live record</span>
          </button>
        </header>

        {empty ? (
          <div className="thin-scroll flex min-w-0 flex-1 flex-col items-center overflow-y-auto overflow-x-hidden px-4 py-8 sm:justify-center">
            <h1 className="mb-2 w-full max-w-[720px] text-center text-[28px] font-semibold leading-tight tracking-tight text-[var(--ink)] sm:text-[34px]">
              What changes next?
            </h1>
            <p className="mb-7 w-full max-w-[560px] text-center text-[14px] leading-relaxed text-[var(--ink-muted)]">
              Name a market, technology, policy fight, or bottleneck. Ask for a dated call,
              watchlist, priced-in gap, or kill condition.
            </p>
            <div className="relative w-full max-w-[720px] min-w-0">
              <div className="composer-glow pointer-events-none absolute -inset-y-10 inset-x-0 -z-10 rounded-full" />
              <Composer
                value={input}
                onChange={setInput}
                onSubmit={() => send()}
                onStop={stop}
                streaming={streaming}
                tier={tier}
                onTierChange={setTier}
              />
            </div>
            <div className="mt-5 grid w-full max-w-[720px] min-w-0 grid-cols-1 gap-2 sm:grid-cols-2">
              {STARTER_CARDS.map((s) => {
                const Icon = s.icon;
                return (
                  <button
                    key={s.title}
                    onClick={() => send(s.prompt)}
                    className="group flex min-h-[78px] min-w-0 items-start gap-3 rounded-lg border border-[var(--border-faint)] bg-white px-3.5 py-3 text-left shadow-[0_1px_2px_rgba(12,11,16,0.04)] transition-colors hover:border-[var(--brand)]"
                  >
                    <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[rgba(109,106,252,0.09)] text-[var(--brand-600)]">
                      <Icon size={17} strokeWidth={1.9} />
                    </span>
                    <span className="min-w-0">
                      <span className="block text-[13px] font-semibold text-[var(--ink)]">
                        {s.title}
                      </span>
                      <span className="mt-0.5 block max-h-[40px] overflow-hidden break-words text-[12px] leading-5 text-[var(--ink-muted)] group-hover:text-[var(--ink)]">
                        {s.prompt}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
            <div className="mt-5 flex w-full max-w-[720px] min-w-0 flex-wrap justify-center gap-2 overflow-hidden">
              {chips.map((c, i) => (
                <button
                  key={i}
                  onClick={() => send(c)}
                  className="max-w-full truncate rounded-full border border-[var(--border-faint)] bg-white px-3.5 py-1.5 text-left text-[13px] text-[var(--ink-muted)] transition-colors hover:border-[var(--brand)] hover:text-[var(--ink)] sm:max-w-[330px]"
                  title={c}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            <div ref={scrollRef} onScroll={onScroll} className="thin-scroll flex-1 overflow-y-auto">
              <div className="mx-auto flex w-full max-w-[720px] min-w-0 flex-col gap-6 px-4 py-6">
                {messages.map((m) =>
                  m.role === "user" ? (
                    <div key={m.id} className="flex justify-end">
                      <div className="max-w-[85%] whitespace-pre-wrap rounded-3xl bg-white px-4 py-2.5 text-[16px] leading-6 text-[var(--ink)] shadow-[0_1px_2px_rgba(12,11,16,0.06)] ring-1 ring-[var(--border-faint)]">
                        {m.content}
                      </div>
                    </div>
                  ) : (
                    <div key={m.id} className="flex flex-col">
                      {m.heading && (
                        <h2 className="mb-1 text-[20px] font-semibold tracking-tight text-[var(--ink)]">
                          {m.heading}
                        </h2>
                      )}
                      {m.council && m.council.members.length > 0 && (
                        <Council
                          data={m.council}
                          live={streaming && m.id === lastId}
                          hasAnswer={Boolean(m.content)}
                        />
                      )}
                      {m.reasoning && (
                        <Reasoning
                          text={m.reasoning}
                          live={streaming && m.id === lastId && !m.content}
                        />
                      )}
                      {m.content && (
                        <div className="text-[16px] leading-7 text-[var(--ink)]">
                          <Markdown text={m.content} />
                          {streaming && m.id === lastId && <span className="caret" />}
                        </div>
                      )}
                      {m.content && !m.cards && !(streaming && m.id === lastId) && (
                        <div className="mt-1.5 flex items-center gap-1">
                          <CopyButton text={m.content} />
                          {m.id === lastId && (
                            <button
                              type="button"
                              onClick={regenerate}
                              className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[12px] text-[var(--ink-muted)] transition-colors hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]"
                              aria-label="Regenerate"
                            >
                              <RotateCcw size={14} strokeWidth={1.9} /> Regenerate
                            </button>
                          )}
                        </div>
                      )}
                      {streaming && !m.content && !m.reasoning && !m.council && m.id === lastId && (
                        <span className="caret" />
                      )}
                      {m.card && <ForecastCard data={m.card} />}
                      {m.card && m.council && !m.card.pending && !m.capture && !m.captureLoading && (
                        <LiteReadUpsell
                          tier={tier}
                          onUpgrade={() => {
                            const q = messages.find(
                              (x) => x.id === m.id - 1 && x.role === "user",
                            )?.content;
                            setTier("deep");
                            if (q && !streaming) send(q, "deep");
                          }}
                        />
                      )}

                      {/* Value capture: turn the forecast into a concrete play. The bridge from
                          "we were right" to "here is who to call and how it makes money". */}
                      {m.capture ? (
                        <CapturePlanCard
                          plan={m.capture}
                          question={m.card?.question ?? ""}
                          contacts={m.contacts}
                          contactsNote={m.contactsNote}
                          contactsLoading={m.contactsLoading}
                          contactsPhase={m.contactsPhase}
                          contactsError={m.contactsError}
                          streaming={streaming}
                          onFindContacts={() => runFindContacts(m.id, m.card?.question ?? m.capture!.headline, m.capture!)}
                        />
                      ) : m.captureLoading ? (
                        <div className="vati-card mt-4 flex w-full max-w-[640px] items-center gap-3 p-4 text-[13px] text-white/70">
                          <span className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-white/20 border-t-[var(--brand-light)]" />
                          {m.capturePhase || "Building the play"}…
                        </div>
                      ) : m.card && !m.card.pending && !(streaming && m.id === lastId) ? (
                        <div className="mt-3 flex flex-col gap-1.5">
                          <button
                            type="button"
                            onClick={() => runCapturePlay(m.id, m.card!.question, m.content)}
                            disabled={streaming}
                            className="inline-flex w-fit items-center gap-2 rounded-full border border-[var(--brand)] px-3.5 py-1.5 text-[13px] font-medium text-[var(--brand-600)] transition-colors hover:bg-[rgba(109,106,252,0.08)] disabled:opacity-40"
                          >
                            <Route size={15} strokeWidth={1.9} /> Turn this into a play
                          </button>
                          {m.captureError && (
                            <p className="text-[12px] text-[var(--ink-muted)]">{m.captureError}</p>
                          )}
                        </div>
                      ) : null}
                      {m.cards && (
                        <div className="mt-3 flex flex-col gap-4">
                          {m.cards.map((c, i) => (
                            <ForecastCard key={i} data={c} />
                          ))}
                        </div>
                      )}
                    </div>
                  ),
                )}
              </div>
            </div>

            {showJump && (
              <button
                type="button"
                onClick={jumpToLatest}
                className="absolute bottom-[104px] left-1/2 z-10 flex h-9 w-9 -translate-x-1/2 items-center justify-center rounded-full border border-[var(--border-faint)] bg-white text-[var(--ink)] shadow-md transition-colors hover:bg-[var(--surface-hover)]"
                aria-label="Jump to latest"
              >
                <ArrowDown size={18} strokeWidth={2} />
              </button>
            )}

            <div className="min-w-0 shrink-0 px-4 pb-4">
              <div className="mx-auto w-full max-w-[720px] min-w-0">
                <Composer
                  value={input}
                  onChange={setInput}
                  onSubmit={() => send()}
                  onStop={stop}
                  streaming={streaming}
                  tier={tier}
                  onTierChange={setTier}
                />
                <p className="mt-2 text-center text-[12px] text-[var(--ink-muted)]">
                  Probabilities are computed by the Vaticinus Monte-Carlo engine. Every call is
                  falsifiable, dated, and Brier-scored at resolution.
                </p>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
