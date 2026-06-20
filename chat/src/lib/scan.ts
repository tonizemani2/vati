// "Run it yourself": the user names an area and Vaticinus mints fresh pre-consensus structural
// calls for it. This is the generative cousin of the offline Pope engine, compressed to a server
// route and GROUNDED in our data layer so it references real signals, not just model memory:
//
//   Stage 1  ground    pull a read from the foresight.db graph for the area (best-effort, shown live)
//   Stage 2  mint       the model produces 2-3 disruptive, falsifiable, pre-consensus calls, each as
//                       a forecast spec (so the client runs the same Monte-Carlo engine for the
//                       probability) plus the implications layer
//
// Same streaming contract as council/capture (tagged NDJSON {t,...}): phase + ground heartbeats,
// then a single {t:"cards"} carrying the specs. The client turns each spec into a real card with
// cardFromSpecComputed (client-side MC), so the numbers come from the engine, never the model.

import { resolveProvider } from "./model";
import { groundDeep, dataLayerEnabled } from "./dataLayer";

export type ScanEvent =
  | { t: "phase"; v: string }
  | { t: "ground"; v: string }
  | { t: "cards"; specs: Record<string, unknown>[]; grounded: boolean }
  | { t: "error"; v: string };

type Emit = (ev: ScanEvent) => void;

const SCAN_MODEL = process.env.VATI_SCAN_MODEL || process.env.VATI_COUNCIL_PRO || "deepseek-v4-pro";

export async function runScan(area: string, emit: Emit): Promise<void> {
  const a = area.trim();
  if (!a) {
    emit({ t: "error", v: "name an area or industry to scan" });
    return;
  }

  // Stage 1 — ground in the data layer (best-effort; the scan still runs web/memory-only if down).
  emit({ t: "phase", v: `Scanning the frontier of ${a.slice(0, 80)}` });
  let groundText: string | null = null;
  if (dataLayerEnabled()) {
    const read = await groundDeep(a, (tool, n) =>
      emit({ t: "ground", v: `Reading the Vaticinus data layer — ${n} step${n === 1 ? "" : "s"} (latest: ${tool})…` }),
    ).catch(() => null);
    groundText = read?.answer ?? null;
    if (groundText) emit({ t: "ground", v: "Grounded in the concept and dependency graph." });
  }

  // Stage 2 — mint the calls.
  emit({ t: "phase", v: "Minting the pre-consensus calls" });
  const groundBlock = groundText
    ? `\n\nVATICINUS DATA LAYER (our own concept/actor/dependency graph and signal series; prefer these real, dated signals over memory):\n"""\n${groundText.slice(0, 4000)}\n"""`
    : "";
  let raw = "";
  try {
    raw = await completeJSON(
      [
        { role: "system", content: SCAN_SYSTEM },
        {
          role: "user",
          content: `AREA: ${a}${groundBlock}\n\nMint the pre-consensus calls. Output ONLY the JSON object.`,
        },
      ],
      4000,
    );
  } catch (e) {
    emit({ t: "error", v: `the scan could not complete: ${e instanceof Error ? e.message : "error"}` });
    return;
  }

  const obj = extractJson(raw) as Record<string, unknown> | null;
  const calls = obj && Array.isArray(obj.calls) ? (obj.calls as Record<string, unknown>[]) : [];
  const specs = calls
    .filter((c) => c && typeof c === "object" && typeof c.question === "string" && c.base_value != null && c.threshold != null)
    .slice(0, 4);

  if (!specs.length) {
    emit({ t: "error", v: "the scan did not produce usable calls, please try a more specific area" });
    return;
  }
  emit({ t: "cards", specs, grounded: Boolean(groundText) });
}

const SCAN_SYSTEM =
  `You are Vaticinus minting pre-consensus structural calls. Given an AREA, surface 2 to 3 disruptive, ` +
  `falsifiable, PRE-CONSENSUS calls where a binding constraint is MOVING and the shift is not yet priced ` +
  `in. Walk the spine (frontier, capability, dependency graph, supply elasticity, demand, capital, pricing, ` +
  `policy) and stop at the layer where the constraint actually binds. Name the specific inelastic input, ` +
  `never a theme.\n\n` +
  `Each call is a measurable forecast plus its implications. For the measurable part, pick one quantity ` +
  `whose threshold defines the call, estimate its current value and a plausible annual growth multiplier, ` +
  `so a Monte-Carlo engine (not you) computes the probability. Do NOT state a probability yourself.\n\n` +
  `Use the data-layer read as ground truth where given. Never fabricate numbers, dates, or entities. ` +
  `No em dashes.\n\n` +
  `Output ONLY this JSON:\n` +
  `{"calls": [{\n` +
  `  "question": "falsifiable question with an explicit threshold and date",\n` +
  `  "quantity_label": "what is measured",\n` +
  `  "ci_unit": "unit",\n` +
  `  "base_value": 1000,\n` +
  `  "horizon_years": 3,\n` +
  `  "g_mean": 1.15,\n` +
  `  "g_sd": 0.1,\n` +
  `  "decel": 0.02,\n` +
  `  "threshold": 1800,\n` +
  `  "threshold_dir": ">=",\n` +
  `  "resolution_date": "YYYY-MM-DD",\n` +
  `  "dated_metric": "the exact public series that settles it",\n` +
  `  "kill_criteria": ["what would prove this wrong", "a second one"],\n` +
  `  "already_priced": "your honest read on consensus vs pre-consensus, labelled an estimate",\n` +
  `  "implications": {"exposed": "who most needs to know", "action_now": "the next decision this changes", "rent_path": "where value capture migrates", "watch": "earliest public signal"}\n` +
  `}]}`;

// --- one OpenAI-compatible completion (DeepSeek by default) ------------------
async function completeJSON(messages: { role: string; content: string }[], maxTokens: number): Promise<string> {
  const namespaced = SCAN_MODEL.includes("/");
  let url: string;
  let key: string | undefined;
  let model: string;
  let extraHeaders: Record<string, string> | undefined;

  if (namespaced) {
    key = process.env.OPENROUTER_API_KEY;
    if (!key) throw new Error("scan model is OpenRouter-namespaced but OPENROUTER_API_KEY is unset");
    url = "https://openrouter.ai/api/v1/chat/completions";
    model = SCAN_MODEL;
    extraHeaders = { "HTTP-Referer": "https://vaticinus.com", "X-Title": "Vaticinus" };
  } else {
    const p = resolveProvider();
    url = p.url;
    key = p.key;
    extraHeaders = p.extraHeaders;
    model = p.url.includes("deepseek.com") ? SCAN_MODEL : p.model;
  }

  const res = await fetch(url, {
    method: "POST",
    headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json", ...(extraHeaders || {}) },
    body: JSON.stringify({ model, max_tokens: maxTokens, temperature: 0.3, messages }),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`scan model ${res.status}: ${detail.slice(0, 160)}`);
  }
  const data = (await res.json()) as { choices?: Array<{ message?: { content?: string } }> };
  return data.choices?.[0]?.message?.content ?? "";
}

function extractJson(text: string): unknown | null {
  const start = text.indexOf("{");
  if (start === -1) return null;
  let depth = 0;
  let inStr = false;
  let esc = false;
  for (let i = start; i < text.length; i++) {
    const ch = text[i];
    if (inStr) {
      if (esc) esc = false;
      else if (ch === "\\") esc = true;
      else if (ch === '"') inStr = false;
    } else if (ch === '"') inStr = true;
    else if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) {
        try {
          return JSON.parse(text.slice(start, i + 1));
        } catch {
          return null;
        }
      }
    }
  }
  return null;
}
