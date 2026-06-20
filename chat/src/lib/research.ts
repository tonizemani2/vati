// Live web research for the council. The single biggest quality lever: without it,
// every analyst reasons from frozen training memory and goes thin on anything recent
// or niche (this is why "space" produced a near-empty answer). With it, the council's
// final synthesis is grounded in current, dated facts and cites its sources.
//
// Runs on plain fetch() (Cloudflare Worker / Node), no Python. Uses OpenRouter's
// Perplexity Sonar (native web search, returns citations). Best-effort: if there is no
// OPENROUTER_API_KEY, or the call times out / fails, it returns null and the council
// silently falls back to pure reasoning. NEVER throws.

import { resolveProvider } from "./model";

export type Citation = { title: string; url: string };
export type Research = { summary: string; citations: Citation[] };

const RESEARCH_MODEL = process.env.VATI_RESEARCH_MODEL || "perplexity/sonar";
const RESEARCH_TIMEOUT_MS = Number(process.env.VATI_RESEARCH_TIMEOUT_MS || 16000);

function openrouterKey(): string | null {
  // resolveProvider() loads the repo .env in local dev; in prod the platform env is
  // already populated. We only need the OpenRouter key here regardless of which chat
  // backend (deepseek/minimax) is wired for the council itself.
  try {
    resolveProvider();
  } catch {
    /* provider resolution is only for its .env side-effect; ignore */
  }
  return process.env.OPENROUTER_API_KEY || null;
}

const RESEARCH_SYSTEM =
  "You are the research desk for a forecasting council. Search the live web and return ONLY " +
  "the most decision-relevant, CURRENT, dated facts a forecaster needs. No preamble, no hedging, " +
  "no advice. Format: 5 to 8 tight bullet points, each a hard fact with a number or date or named " +
  "actor where possible (capacities, prices, lead times, recent announcements, who is moving and how " +
  "fast). Include at least one fact that helps settle whether the view is already priced or still " +
  "pre-consensus. Then one final line beginning 'RECENT SHIFT:' naming the single most important " +
  "thing that changed in the last 6 to 12 months. Never use em dashes.";

/** Parse OpenRouter / Perplexity citation shapes into a flat list, de-duped by URL. */
function extractCitations(data: unknown): Citation[] {
  const out: Citation[] = [];
  const seen = new Set<string>();
  const push = (url?: unknown, title?: unknown) => {
    if (typeof url !== "string" || !url.startsWith("http")) return;
    if (seen.has(url)) return;
    seen.add(url);
    let host = url;
    try {
      host = new URL(url).hostname.replace(/^www\./, "");
    } catch {
      /* keep raw */
    }
    out.push({ title: (typeof title === "string" && title.trim()) || host, url });
  };
  const root = data as {
    citations?: unknown[];
    choices?: Array<{ message?: { annotations?: Array<{ url_citation?: { url?: string; title?: string } }> } }>;
  };
  // Perplexity-style top-level array of URL strings.
  for (const c of root.citations ?? []) push(c);
  // OpenRouter-normalized annotations.
  for (const a of root.choices?.[0]?.message?.annotations ?? [])
    push(a?.url_citation?.url, a?.url_citation?.title);
  return out.slice(0, 8);
}

/** Best-effort live research brief for a question. Returns null on any failure. */
export async function research(question: string): Promise<Research | null> {
  const key = openrouterKey();
  if (!key) return null;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), RESEARCH_TIMEOUT_MS);
  try {
    const res = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      signal: controller.signal,
      headers: {
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
        "HTTP-Referer": "https://vaticinus.com",
        "X-Title": "Vaticinus",
      },
      body: JSON.stringify({
        model: RESEARCH_MODEL,
        max_tokens: 900,
        messages: [
          { role: "system", content: RESEARCH_SYSTEM },
          { role: "user", content: question },
        ],
      }),
    });
    if (!res.ok) return null;
    const data = (await res.json()) as {
      choices?: Array<{ message?: { content?: string } }>;
    };
    const summary = data.choices?.[0]?.message?.content?.trim();
    if (!summary) return null;
    return { summary, citations: extractCitations(data) };
  } catch {
    return null; // timeout, abort, network, or bad JSON: fall back to pure reasoning
  } finally {
    clearTimeout(timer);
  }
}
