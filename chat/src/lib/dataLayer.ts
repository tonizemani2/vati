// Bridge to the Vaticinus data layer: the 6GB foresight.db (concept/actor/dependency graph,
// minted series, the leak-free record) reachable via the read-only HTTP sidecar
// (vati-data-agent/serve_http.py, POST /ask). This is the moat the Deep tier and the Capture
// play read that a generic chatbot cannot: OUR graph, not a web search.
//
// Best-effort and tightly timed, NEVER throws. If VATI_DATA_URL is unset (the default) or the
// box is slow or down, the caller proceeds without it and the feature degrades to web-only.
// That gating is deliberate: the integration ships dark and lights up the moment the sidecar
// URL + token are set as Worker secrets.

const dataUrl = () => (process.env.VATI_DATA_URL || "").replace(/\/$/, "");
const dataToken = () => process.env.VATI_DATA_TOKEN || "";
// /pack is a deterministic ~2-7s SQL read, so a tight budget is right: if the box is slow we
// fall back rather than stall a run. /ask is the agentic loop (the LLM authors SQL/search over
// the graph and verifies its own answer); it is rich but slow (~60-150s), so it gets its own
// generous budget and is used only by the heavy Deep / Capture tiers via groundDeep().
const DATA_TIMEOUT_MS = Number(process.env.VATI_DATA_TIMEOUT_MS || 9000);
// The agentic loop streams a heartbeat per step, so Cloudflare never 524s on the silence.
// That lets us run it at FULL depth (no step/model trade) and just wait it out; the budget
// is a generous backstop against a genuinely hung box, not a quality lever.
const ASK_TIMEOUT_MS = Number(process.env.VATI_DATA_ASK_TIMEOUT_MS || 240000);

export type DataRead = { answer: string; evidence: string[] };

export function dataLayerEnabled(): boolean {
  return Boolean(dataUrl());
}

// Pull a deterministic grounding pack (real entities, dependency edges, signal series,
// emerging concepts) for a topic from the graph. Hits the fast /pack endpoint (pure SQL, no
// model). Returns null on any failure (unset, timeout, network, bad JSON, nothing found) so
// callers fall back to web-only cleanly.
export async function askDataLayer(topic: string): Promise<DataRead | null> {
  const base = dataUrl();
  if (!base) return null;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), DATA_TIMEOUT_MS);
  try {
    const res = await fetch(`${base}/pack`, {
      method: "POST",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(dataToken() ? { Authorization: `Bearer ${dataToken()}` } : {}),
      },
      body: JSON.stringify({ topic }),
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { summary?: unknown; found?: unknown };
    if (data?.found !== true) return null; // nothing in the graph for this topic
    const answer = typeof data?.summary === "string" ? data.summary.trim() : "";
    if (!answer) return null;
    return { answer, evidence: [] };
  } catch {
    return null; // timeout, abort, network, or bad JSON: caller falls back to web-only
  } finally {
    clearTimeout(timer);
  }
}

// The MOAT read: run the full agentic loop over the graph (the model authors SQL/search across
// foresight.db, walks dependency edges, pulls dated series, and verifies its own answer against
// the evidence ledger). This is what a generic chatbot cannot do: reason over OUR data, not the
// open web. We hit the STREAMING endpoint (/ask_stream): the box emits one NDJSON line per tool
// step, which both keeps the connection alive through Cloudflare (no 524 on a 100-150s run, so
// we never have to shrink the loop to fit) and lets the caller surface a live heartbeat via
// onStep. Best-effort; returns null on any failure so callers fall back. `evidence` carries the
// tool names the agent fired, for provenance.
export async function askDataLayerAgentic(
  question: string,
  onStep?: (tool: string, n: number) => void,
): Promise<DataRead | null> {
  const base = dataUrl();
  if (!base) return null;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ASK_TIMEOUT_MS);
  try {
    const res = await fetch(`${base}/ask_stream`, {
      method: "POST",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(dataToken() ? { Authorization: `Bearer ${dataToken()}` } : {}),
      },
      body: JSON.stringify({ question }),
    });
    if (!res.ok || !res.body) return null;

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    type FinalEv = { answer?: unknown; evidence?: Array<{ tool?: unknown }> };
    let final: FinalEv | null = null;
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let nl: number;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (!line) continue;
        let ev: { t?: string; tool?: unknown; n?: unknown; answer?: unknown; evidence?: unknown };
        try {
          ev = JSON.parse(line);
        } catch {
          continue; // a partial/garbled line never sinks the read
        }
        if (ev.t === "step") {
          if (onStep && typeof ev.tool === "string") onStep(ev.tool, Number(ev.n) || 0);
        } else if (ev.t === "final") {
          final = ev as FinalEv;
        } else if (ev.t === "error") {
          return null;
        }
      }
    }

    const answer = typeof final?.answer === "string" ? final.answer.trim() : "";
    // "[hit max steps ...]" is the agent's no-answer sentinel; treat it as a miss.
    if (!answer || answer.startsWith("[")) return null;
    const tools = Array.isArray(final?.evidence)
      ? final!.evidence.map((e) => e?.tool).filter((t): t is string => typeof t === "string")
      : [];
    return { answer, evidence: tools };
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

// Deep grounding for the heavy tiers: prefer the agentic /ask_stream loop (real reasoning over
// the graph), fall back to the fast deterministic /pack (a keyword SQL slice), then to null. One
// call, graceful degradation: best data when the agent succeeds, still-useful facts when it
// times out, clean web-only when the sidecar is down. onStep forwards the agent's live steps.
export async function groundDeep(
  question: string,
  onStep?: (tool: string, n: number) => void,
): Promise<DataRead | null> {
  const agentic = await askDataLayerAgentic(question, onStep);
  if (agentic) return agentic;
  return askDataLayer(question);
}
