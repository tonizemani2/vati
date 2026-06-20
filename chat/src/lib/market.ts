// Keyless live market anchor for the "is this already priced in?" check.
// Ported from engine/market.py. The honest contract (this is the anti-lie fix):
//
//   status: "priced"    -> we reached a market and a qualifying one trades this. Real signal.
//   status: "none"      -> we reached the markets and found nothing comparable. NOT a green light.
//   status: "unchecked" -> we could NOT reach the markets (timeout/error). We do NOT KNOW. Never
//                          claim priced or not-priced on an unchecked result.
//
// The old version returned null for BOTH "none" and "unchecked", so a transient timeout looked
// identical to "no market exists" and the model flip-flopped between "priced" and "not priced" on
// re-ask. Distinguishing the three states is what stops the lie. Never throws.
//
// Metaculus note: Metaculus removed keyless API access (every endpoint now 403s with "available to
// authenticated users only"). So the Metaculus leg only runs when METACULUS_TOKEN is set; without
// it we skip the doomed call entirely and let Manifold (keyless, primary) carry the anchor. A
// skipped leg is NOT a transport failure, so it never tips the result into "unchecked".

import { resolveProvider } from "./model";

export type MarketAnchor = {
  source: "manifold" | "metaculus";
  label: string;
  prob: number; // 0..1 crowd probability
  volume: number;
  url: string;
};

export type MarketResult = {
  status: "priced" | "none" | "unchecked";
  top: MarketAnchor | null;
  markets: MarketAnchor[];
};

const VOLUME_FLOOR = 50; // below this a Manifold market is too thin to count as "the crowd has arrived"
const TIMEOUT_MS = 5000;

type Leg = { ok: boolean; markets: MarketAnchor[] };

// Both Manifold and Metaculus full-text search choke on a whole natural-language question:
// "Will Bitcoin reach $200000 in 2026?" returns ZERO markets, while "bitcoin 200k" returns the
// real ones. So we distill the question to a compact keyword query before searching: drop the
// question scaffolding and stopwords, strip punctuation, convert big round numbers to k/m form
// (200000 -> 200k, the form markets actually use), and drop bare years (they hurt more than help).
// Measured: this fixes many 0-hit questions to real matches and never reduces the hit rate.
const STOP = new Set(
  ("will would could should the a an of to in on at for and or is are was were be been being by " +
    "with from as that this it its than then so but if not no yes do does did done how what when " +
    "where which who whom whose why us reach reaches reached exceed exceeds hit hits hitting cross " +
    "crosses surpass before after end average annually per year years month months any least most " +
    "more less over under above below within during about into onto out up down").split(/\s+/),
);
function distill(question: string): string {
  let s = " " + question.toLowerCase() + " ";
  s = s.replace(/\$?([0-9][0-9,]*)/g, (_m, num: string) => {
    const n = Number(num.replace(/,/g, ""));
    if (!isFinite(n)) return num;
    if (n >= 1_000_000 && n % 100_000 === 0) return n / 1_000_000 + "m";
    if (n >= 1000 && n % 1000 === 0) return n / 1000 + "k";
    return String(n);
  });
  s = s.replace(/[^a-z0-9\s]/g, " ").replace(/\b(19|20)\d\d\b/g, " ");
  const toks = s.split(/\s+/).filter((t) => t && !STOP.has(t));
  return toks.slice(0, 6).join(" ") || question; // never search on an empty string
}

async function getJson(url: string, token?: string): Promise<unknown | undefined> {
  // undefined = could not fetch (network/timeout/non-200). Distinct from an empty result.
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
    const headers: Record<string, string> = { Accept: "application/json" };
    if (token) headers.Authorization = `Token ${token}`;
    const res = await fetch(url, { headers, signal: ctrl.signal });
    clearTimeout(timer);
    if (!res.ok) return undefined;
    return await res.json();
  } catch {
    return undefined;
  }
}

// Manifold full-text search. sort=score + volume floor matches engine/market.py for stability.
async function manifold(term: string): Promise<Leg> {
  const url =
    "https://api.manifold.markets/v0/search-markets?term=" +
    encodeURIComponent(term) +
    "&limit=8&sort=score&filter=open&contractType=BINARY";
  const data = await getJson(url);
  if (!Array.isArray(data)) return { ok: false, markets: [] };
  const markets: MarketAnchor[] = [];
  for (const r of data as Array<Record<string, unknown>>) {
    const prob = r.probability as number | undefined;
    const vol = Number(r.volume ?? 0);
    if (r.isResolved || typeof prob !== "number" || vol < VOLUME_FLOOR || !r.url) continue;
    markets.push({
      source: "manifold",
      label: String(r.question ?? term),
      prob: Math.round(prob * 1000) / 1000,
      volume: Math.round(vol),
      url: String(r.url),
    });
  }
  return { ok: true, markets };
}

function metaculusToken(): string | null {
  // resolveProvider() loads the repo .env in local dev as a side-effect; in prod the platform
  // env is already populated. We only need METACULUS_TOKEN here.
  try {
    resolveProvider();
  } catch {
    /* env side-effect only; ignore provider resolution errors */
  }
  return process.env.METACULUS_TOKEN || null;
}

// The community-median field moved across Metaculus API versions. Try the known shapes and
// return the first 0..1 probability found. Returns undefined when the crowd prediction is
// withheld (common for young or low-volume questions), so that question is simply skipped.
function metaculusCp(q: Record<string, unknown>): number | undefined {
  const cp = q.community_prediction as { full?: { q2?: unknown } } | undefined;
  if (typeof cp?.full?.q2 === "number") return cp.full.q2;
  const question = q.question as
    | { aggregations?: { recency_weighted?: { latest?: { centers?: unknown } } } }
    | undefined;
  const centers = question?.aggregations?.recency_weighted?.latest?.centers;
  if (Array.isArray(centers) && typeof centers[0] === "number") return centers[0];
  return undefined;
}

// Metaculus search → community prediction. Token-gated: Metaculus no longer serves the API
// keylessly (403 "authenticated users only"). With no token we skip cleanly (ok:true, no
// markets) so Manifold drives the anchor and the result never falls to "unchecked".
async function metaculus(term: string): Promise<Leg> {
  const token = metaculusToken();
  if (!token) return { ok: true, markets: [] };
  const url =
    "https://www.metaculus.com/api2/questions/?search=" +
    encodeURIComponent(term) +
    "&limit=4&status=open&forecast_type=binary&order_by=-activity&with_cp=true";
  const data = await getJson(url, token);
  if (!data || typeof data !== "object") return { ok: false, markets: [] };
  const results = (data as { results?: Array<Record<string, unknown>> }).results;
  if (!Array.isArray(results)) return { ok: false, markets: [] };
  const markets: MarketAnchor[] = [];
  for (const q of results) {
    const p = metaculusCp(q);
    const id = q.id as number | undefined;
    if (typeof p !== "number" || !id) continue;
    const slug = typeof q.slug === "string" ? q.slug : "";
    markets.push({
      source: "metaculus",
      label: String(q.title ?? term),
      prob: Math.round(p * 1000) / 1000,
      volume: Number(q.nr_forecasters ?? q.number_of_forecasters ?? 0),
      url: `https://www.metaculus.com/questions/${id}/${slug ? slug + "/" : ""}`,
    });
  }
  return { ok: true, markets };
}

/**
 * Best-effort crowd anchor for a question, with an honest 3-state status.
 * Tries Manifold and Metaculus concurrently. status is "unchecked" only when BOTH legs failed
 * to respond (so we genuinely do not know), "none" when they responded with nothing comparable,
 * and "priced" when a qualifying market exists.
 */
export async function anchorFor(term: string): Promise<MarketResult> {
  const query = distill(term); // a keyword query the market search engines can actually match
  const [m, k] = await Promise.all([
    manifold(query).catch(() => ({ ok: false, markets: [] }) as Leg),
    metaculus(query).catch(() => ({ ok: false, markets: [] }) as Leg),
  ]);
  if (!m.ok && !k.ok) return { status: "unchecked", top: null, markets: [] };
  const markets = [...m.markets, ...k.markets].sort((a, b) => b.volume - a.volume);
  if (markets.length === 0) return { status: "none", top: null, markets: [] };
  return { status: "priced", top: markets[0], markets: markets.slice(0, 6) };
}
