// "Find who to call": Rung 3 of the ladder. Takes a PURSUE value-capture play and resolves its
// named targets into REAL, verified, scored contacts (people or companies). The orchestration,
// not the tool, is the point:
//
//   Stage 1  craft the search   the model turns the play's targets + thesis into one search query
//                                and picks the entity (person vs company) and how many
//   Stage 2  discover           ROUTED by count, matching how each tool is actually good:
//                                  - few, precise (the default for "who to call") -> keyless Exa
//                                    search: fast, free, no account, a handful of real profiles
//                                  - many, criteria-based, select-from -> Exa Websets (when wired)
//   Stage 3  verify + score     the model checks each candidate against the intended target and the
//                                thesis, keeps only genuine matches grounded in the results, and
//                                attaches a confidence + a one-line why-relevant. THIS is the quality
//                                gate: search returns noise, and we never surface a contact we cannot
//                                tie back to a target or ground in a real result.
//
// Same streaming contract as capture/council (tagged NDJSON {t,...}): phase heartbeats while it
// works, then a single {t:"contacts"}. Never fabricates.

import { resolveProvider } from "./model";
import { exaSearch, isLinkedInProfile } from "./exa";
import { searchWebsets, websetsEnabled, type WebsetsContact, type WebsetsEntity } from "./websets";
import type { CapturePlan } from "./capture";

export type Contact = {
  name: string;
  title: string;
  org: string;
  location: string;
  linkedin: string;
  email: string;
  phone: string;
  source: string; // the web result the contact was found in (Exa path)
  confidence: number; // 0-1 from the verify step
  why_relevant: string;
  matched_target: string;
};

export type ContactsEvent =
  | { t: "phase"; v: string }
  | { t: "contacts"; contacts: Contact[]; entity: WebsetsEntity; provider: "exa" | "websets"; note?: string }
  | { t: "error"; v: string };

type Emit = (ev: ContactsEvent) => void;

const CONTACTS_MODEL =
  process.env.VATI_CONTACTS_MODEL || process.env.VATI_COUNCIL_PRO || "deepseek-v4-pro";

// Confidence floor: anything the auditor is less than this sure genuinely matches is dropped.
const MIN_CONFIDENCE = Number(process.env.VATI_CONTACTS_MIN_CONFIDENCE || 0.4);
// At or below this count we want a few precise names -> keyless Exa. Above it, a broad
// criteria-based list to select from -> Websets (if configured).
const EXA_FEW_MAX = Number(process.env.VATI_CONTACTS_EXA_MAX || 6);

// Always enabled: keyless Exa needs no account, so the rung can always at least attempt discovery.
export function contactsEnabled(): boolean {
  return true;
}

export async function runFindContacts(question: string, plan: CapturePlan, emit: Emit): Promise<void> {
  const targets = (plan.targets ?? []).filter((t) => t.org || t.person);
  if (!targets.length) {
    emit({ t: "error", v: "this play has no named targets to source contacts for" });
    return;
  }

  // Stage 1 — craft the search. Heuristic query as a floor; the model refines it and picks entity.
  emit({ t: "phase", v: "Working out who to look for" });
  const targetLines = targets
    .map((t) => [t.org, t.role, t.person, t.why].filter(Boolean).join(" - "))
    .join("\n");
  let query = targets.map((t) => [t.role, t.org].filter(Boolean).join(" at ")).filter(Boolean).join("; ");
  let entity: WebsetsEntity = "person";
  let count = Math.min(8, Math.max(4, targets.length * 2));
  try {
    const crafted = await completeJSON(
      [
        { role: "system", content: QUERY_SYSTEM },
        {
          role: "user",
          content: `THESIS: ${question}\n\nINTENDED TARGETS:\n${targetLines}\n\nReturn ONLY the JSON object.`,
        },
      ],
      600,
    );
    const obj = extractJson(crafted) as Record<string, unknown> | null;
    if (obj) {
      if (typeof obj.query === "string" && obj.query.trim()) query = obj.query.trim();
      if (obj.entity === "company") entity = "company";
      if (typeof obj.count === "number" && Number.isFinite(obj.count)) {
        count = Math.min(12, Math.max(3, Math.trunc(obj.count)));
      }
    }
  } catch {
    /* heuristic query stands */
  }

  // Stage 2 — route to the right discovery tool by count.
  const provider: "exa" | "websets" = count <= EXA_FEW_MAX || !websetsEnabled() ? "exa" : "websets";

  let contacts: Contact[] | null = null;
  let note: string | undefined;
  try {
    if (provider === "exa") {
      emit({ t: "phase", v: entity === "company" ? "Searching for the real companies" : "Searching for the real people" });
      const results = await exaSearch(query, Math.min(15, count * 2));
      if (!results.length) {
        emit({ t: "contacts", contacts: [], entity, provider, note: "Search returned nothing for these criteria. Try widening the play's targets." });
        return;
      }
      emit({ t: "phase", v: "Verifying each match against the thesis" });
      contacts = await extractAndVerifyExa(question, targetLines, results, entity);
    } else {
      emit({ t: "phase", v: "Sourcing a criteria-based shortlist" });
      const result = await searchWebsets({ query, entity, count, waitMs: 90000 });
      const raw = result.contacts ?? [];
      if (!raw.length) {
        emit({ t: "contacts", contacts: [], entity, provider, note: "The shortlist search did not return contacts for these criteria." });
        return;
      }
      emit({ t: "phase", v: "Verifying each match against the thesis" });
      contacts = await verifyWebsets(question, targetLines, raw, entity);
    }
  } catch (e) {
    emit({ t: "error", v: `contact search failed: ${e instanceof Error ? e.message : "error"}` });
    return;
  }

  if (!contacts) {
    emit({ t: "contacts", contacts: [], entity, provider, note: "Match verification was unavailable, so nothing was surfaced rather than guess." });
    return;
  }

  const kept = contacts
    .filter((c) => c.confidence >= MIN_CONFIDENCE && (c.name || c.org))
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 10);
  emit({
    t: "contacts",
    contacts: kept,
    entity,
    provider,
    note: kept.length ? note : "Found candidates, but none could be confidently tied to a target. Nothing surfaced rather than guess.",
  });
}

// --- Exa path: extract + verify + score in one grounded model call -----------
async function extractAndVerifyExa(
  question: string,
  targetLines: string,
  results: Array<{ title: string; url: string; snippet: string }>,
  entity: WebsetsEntity,
): Promise<Contact[] | null> {
  const numbered = results.slice(0, 15).map((r, i) => ({ index: i, title: r.title, url: r.url, snippet: r.snippet }));
  const out = await completeJSON(
    [
      { role: "system", content: EXA_EXTRACT_SYSTEM },
      {
        role: "user",
        content:
          `THESIS: ${question}\n\nINTENDED TARGETS:\n${targetLines}\n\n` +
          `SEARCH RESULTS (${entity}):\n${JSON.stringify(numbered, null, 2)}\n\nReturn ONLY the JSON object.`,
      },
    ],
    2000,
  ).catch(() => "");
  const obj = extractJson(out) as Record<string, unknown> | null;
  const items = obj && Array.isArray(obj.contacts) ? (obj.contacts as Record<string, unknown>[]) : null;
  if (!items) return null;

  return items.map((d) => {
    const sourceIdx = typeof d.index === "number" ? d.index : Number(d.index);
    const source = stringField(d.source) || (results[sourceIdx]?.url ?? "");
    const linkedinField = stringField(d.linkedin);
    const linkedin = linkedinField || (isLinkedInProfile(source) ? source : "");
    return {
      name: stringField(d.name),
      title: stringField(d.title),
      org: stringField(d.org),
      location: stringField(d.location),
      linkedin,
      email: "",
      phone: "",
      source,
      confidence: clamp01(typeof d.confidence === "number" ? d.confidence : Number(d.confidence)),
      why_relevant: stringField(d.why_relevant),
      matched_target: stringField(d.matched_target),
    };
  });
}

// --- Websets path: results are already structured contacts; just verify + score ----------
async function verifyWebsets(
  question: string,
  targetLines: string,
  raw: WebsetsContact[],
  entity: WebsetsEntity,
): Promise<Contact[] | null> {
  const candidates = raw.slice(0, 12).map((c, i) => ({
    index: i,
    name: c.full_name,
    title: c.title,
    company: c.company,
    location: c.location,
    linkedin: c.linkedin,
  }));
  const out = await completeJSON(
    [
      { role: "system", content: VERIFY_SYSTEM },
      {
        role: "user",
        content:
          `THESIS: ${question}\n\nINTENDED TARGETS:\n${targetLines}\n\n` +
          `CANDIDATES (${entity}):\n${JSON.stringify(candidates, null, 2)}\n\nReturn ONLY the JSON object.`,
      },
    ],
    1600,
  ).catch(() => "");
  const obj = extractJson(out) as Record<string, unknown> | null;
  const decisions = obj && Array.isArray(obj.contacts) ? (obj.contacts as Record<string, unknown>[]) : null;
  if (!decisions) return null;

  const merged: Contact[] = [];
  for (const d of decisions) {
    const index = typeof d.index === "number" ? d.index : Number(d.index);
    const base = raw[index];
    if (!base) continue;
    merged.push({
      name: base.full_name || "",
      title: base.title || "",
      org: base.company || "",
      location: base.location || "",
      linkedin: base.linkedin || "",
      email: base.email || "",
      phone: base.phone || "",
      source: base.linkedin || "",
      confidence: clamp01(typeof d.confidence === "number" ? d.confidence : Number(d.confidence)),
      why_relevant: stringField(d.why_relevant),
      matched_target: stringField(d.matched_target),
    });
  }
  return merged;
}

const QUERY_SYSTEM =
  `You source the real decision-makers (or companies) to contact for a value-capture play. ` +
  `Given the thesis and the intended target organizations and roles, write ONE search query that ` +
  `will surface the right real contacts, and choose the entity type and how many.\n\n` +
  `- Prefer entity "person" when the targets are roles or named individuals; use "company" only when ` +
  `the play needs to source organizations rather than people.\n` +
  `- For people, phrase the query so it surfaces real profiles (role, seniority, sector, geography, ` +
  `and the word linkedin help).\n` +
  `- count is how many real contacts are worth surfacing for this play: a few (3 to 6) for a precise ` +
  `who-to-call, more only if the play genuinely needs a broad shortlist.\n` +
  `- No em dashes.\n\n` +
  `Output ONLY this JSON: {"query": "...", "entity": "person" | "company", "count": 5}`;

const EXA_EXTRACT_SYSTEM =
  `You build an outbound contact shortlist from raw web search results. Given a thesis, the intended ` +
  `targets, and search results (title, url, snippet), extract the real people (or companies) and keep ` +
  `only those that genuinely match an intended target and are plausibly exposed to or able to act on ` +
  `the thesis.\n\n` +
  `Rules:\n` +
  `- Extract name, title, and org ONLY from what the result title and snippet actually support. Never ` +
  `invent a name, title, company, or detail not present in the results.\n` +
  `- Use the result url as "source". If it is a LinkedIn profile url, also put it in "linkedin".\n` +
  `- Skip results that are not a real person or company profile (articles, directories, listings).\n` +
  `- confidence is 0 to 1: how sure you are this is a right, real contact for the play.\n` +
  `- why_relevant is one short concrete sentence tying them to the thesis or target.\n` +
  `- matched_target names which intended target this resolves. OMIT anything you cannot ground or tie ` +
  `back. No padding. No em dashes.\n\n` +
  `Output ONLY this JSON: {"contacts": [{"index": 0, "name": "...", "title": "...", "org": "...", ` +
  `"location": "...", "linkedin": "...", "source": "...", "matched_target": "...", "confidence": 0.8, ` +
  `"why_relevant": "..."}]}`;

const VERIFY_SYSTEM =
  `You are the match auditor for an outbound contact list. Given a thesis, the intended targets, and ` +
  `candidate contacts returned by a search, decide for each candidate whether it GENUINELY matches an ` +
  `intended target and is plausibly exposed to or able to act on the thesis.\n\n` +
  `Rules:\n` +
  `- Keep only genuine matches. OMIT anyone who does not clearly map to an intended target; do not pad.\n` +
  `- confidence is 0 to 1: how sure you are this is a right contact for the play.\n` +
  `- why_relevant is one short, concrete sentence. matched_target names which target this resolves.\n` +
  `- Never invent. Judge only the candidates given. No em dashes.\n\n` +
  `Output ONLY this JSON: {"contacts": [{"index": 0, "matched_target": "...", "confidence": 0.8, "why_relevant": "..."}]}`;

// --- one OpenAI-compatible JSON completion (DeepSeek by default) -------------
async function completeJSON(messages: { role: string; content: string }[], maxTokens: number): Promise<string> {
  const namespaced = CONTACTS_MODEL.includes("/");
  let url: string;
  let key: string | undefined;
  let model: string;
  let extraHeaders: Record<string, string> | undefined;

  if (namespaced) {
    key = process.env.OPENROUTER_API_KEY;
    if (!key) throw new Error("contacts model is OpenRouter-namespaced but OPENROUTER_API_KEY is unset");
    url = "https://openrouter.ai/api/v1/chat/completions";
    model = CONTACTS_MODEL;
    extraHeaders = { "HTTP-Referer": "https://vaticinus.com", "X-Title": "Vaticinus" };
  } else {
    const p = resolveProvider();
    url = p.url;
    key = p.key;
    extraHeaders = p.extraHeaders;
    model = p.url.includes("deepseek.com") ? CONTACTS_MODEL : p.model;
  }

  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${key}`,
      "Content-Type": "application/json",
      ...(extraHeaders || {}),
    },
    body: JSON.stringify({ model, max_tokens: maxTokens, temperature: 0.2, messages }),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`contacts model ${res.status}: ${detail.slice(0, 160)}`);
  }
  const data = (await res.json()) as { choices?: Array<{ message?: { content?: string } }> };
  return data.choices?.[0]?.message?.content ?? "";
}

// Brace-matched, string-aware JSON extraction (handles fences and leading prose).
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

function stringField(v: unknown): string {
  return typeof v === "string" ? v.trim() : "";
}

function clamp01(n: number): number {
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(1, n));
}
