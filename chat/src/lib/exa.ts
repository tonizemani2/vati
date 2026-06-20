// Keyless Exa search. The protocol (vendored from the engine's exa_search.py): POST
// exa.ai/api/token/issue with browser headers -> a bearer token with a ~5 min TTL -> POST
// exa.ai/api/search. Free, no API key. This is the fast, small-N discovery path for "find who
// to call": precise, a handful of real people/companies, no account to keep alive. The broad
// criteria-based many-to-select-from path is Websets (see websets.ts); contacts.ts routes
// between them on count.
//
// Best-effort and tightly timed: never throws, returns [] on any failure so the caller degrades.

const EXA_TOKEN_URL = "https://exa.ai/api/token/issue";
const EXA_SEARCH_URL = "https://exa.ai/api/search";

const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";
const BROWSER_HEADERS = {
  "User-Agent": UA,
  Origin: "https://exa.ai",
  Referer: "https://exa.ai/",
};

export type ExaResult = { title: string; url: string; snippet: string };

// Per-isolate token cache (5-min TTL). A cache miss just re-issues; cheap.
let cachedToken: string | null = null;
let tokenExpires = 0;

async function getToken(signal: AbortSignal): Promise<string | null> {
  const now = Date.now();
  if (cachedToken && now < tokenExpires) return cachedToken;
  try {
    const res = await fetch(EXA_TOKEN_URL, {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", ...BROWSER_HEADERS },
      body: "{}",
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { token?: string; expiresIn?: number };
    if (!data.token) return null;
    cachedToken = data.token;
    tokenExpires = now + (Number(data.expiresIn) || 240) * 1000 - 5000; // refresh 5s early
    return cachedToken;
  } catch {
    return null;
  }
}

export async function exaSearch(query: string, numResults = 8, timeoutMs = 12000): Promise<ExaResult[]> {
  const q = query.trim();
  if (!q) return [];
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const token = await getToken(controller.signal);
    if (!token) return [];
    const res = await fetch(EXA_SEARCH_URL, {
      method: "POST",
      signal: controller.signal,
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        ...BROWSER_HEADERS,
      },
      body: JSON.stringify({ query: q, num_results: Math.min(25, Math.max(1, numResults)) }),
    });
    if (!res.ok) {
      if (res.status === 401) cachedToken = null; // stale token: drop so next call re-issues
      return [];
    }
    const data = (await res.json()) as { results?: Array<{ title?: string; url?: string; text?: string }> };
    if (!Array.isArray(data.results)) return [];
    return data.results
      .map((r) => ({
        title: typeof r.title === "string" ? r.title : "",
        url: typeof r.url === "string" ? r.url : "",
        snippet: typeof r.text === "string" ? r.text.slice(0, 400) : "",
      }))
      .filter((r) => r.url);
  } catch {
    return [];
  } finally {
    clearTimeout(timer);
  }
}

export function isLinkedInProfile(url: string): boolean {
  return /linkedin\.com\/(in|company)\//i.test(url);
}
