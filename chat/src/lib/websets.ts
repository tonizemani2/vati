export type WebsetsEntity = "person" | "company";

type WebsetsCookie = {
  name?: unknown;
  value?: unknown;
  domain?: unknown;
  path?: unknown;
};

type WebsetsAccount = {
  email?: unknown;
  api_token?: unknown;
  exa_token?: unknown;
  team_id?: unknown;
  credits?: unknown;
  status?: unknown;
  created_at?: unknown;
  cookies?: WebsetsCookie[];
};

type WebsetsSession = {
  token: string;
  cookie: string;
};

export type WebsetsContact = {
  full_name: string;
  first_name: string;
  last_name: string;
  title: string;
  company: string;
  location: string;
  linkedin: string;
  email: string;
  phone: string;
  raw?: unknown;
};

export type WebsetsSearchResult = {
  webset_id: string;
  status: string;
  completed: boolean;
  contacts: WebsetsContact[];
  account_email: string;
  credits: number | null;
  item_count: number;
};

const EXA_BASE = "https://websets.exa.ai";
const EXA_TRPC = `${EXA_BASE}/websets/api/trpc`;
const EXA_TOKEN_URL = `${EXA_BASE}/websets/api/token/issue`;
const MIN_CREDITS = 30;

const PERSON_ENRICHMENTS = [
  { description: "Find the work email address", format: "email" },
  { description: "Find the personal mobile phone number", format: "phone" },
  { description: "Find the LinkedIn profile URL", format: "url" },
];

const COMPANY_ENRICHMENTS = [
  { description: "Find the company website URL", format: "url" },
  { description: "Find the CEO or founder name", format: "text" },
  { description: "Find the company LinkedIn page URL", format: "url" },
];

export function websetsEnabled(): boolean {
  return (
    Boolean(websetsToolUrl() || process.env.EXA_WEBSETS_ACCOUNT_JSON || process.env.EXA_WEBSETS_API_TOKEN) ||
    localWebsetsFallbackEnabled()
  );
}

export async function searchWebsets(input: {
  query: string;
  count?: number;
  entity?: WebsetsEntity;
  waitMs?: number;
}): Promise<WebsetsSearchResult> {
  const sidecar = websetsToolUrl();
  if (sidecar) return searchWebsetsViaSidecar(sidecar, input);

  const account = await resolveWebsetsAccount();
  if (!account) throw new Error("websets account is not configured");

  const query = input.query.trim();
  if (!query) throw new Error("empty websets query");
  const entity = input.entity ?? "person";
  const count = clampInt(input.count ?? 5, 1, 25);
  const waitMs = clampInt(input.waitMs ?? 90000, 0, 180000);

  const session = await freshSession(account);
  const websetId = await createWebset(session, {
    query,
    count,
    entity,
    enrichments: entity === "person" ? PERSON_ENRICHMENTS : COMPANY_ENRICHMENTS,
  });
  const status = await waitForWebset(session, websetId, waitMs);
  const contacts = status.completed ? parseItems(await getWebsetItems(session, websetId), entity) : [];
  const credits = await getCredits(session, account);

  return {
    webset_id: websetId,
    status: status.status,
    completed: status.completed,
    contacts,
    account_email: stringOr(account.email, ""),
    credits,
    item_count: contacts.length,
  };
}

export async function getWebsetsStatus(websetId: string): Promise<Omit<WebsetsSearchResult, "account_email" | "credits">> {
  const sidecar = websetsToolUrl();
  if (sidecar) return getWebsetsStatusViaSidecar(sidecar, websetId);

  const account = await resolveWebsetsAccount();
  if (!account) throw new Error("websets account is not configured");
  const session = await freshSession(account);
  const status = await getWebset(session, websetId);
  const completed = status?.status === "idle";
  const contacts = completed ? parseItems(await getWebsetItems(session, websetId), "person") : [];
  return {
    webset_id: websetId,
    status: stringOr(status?.status, "unknown"),
    completed,
    contacts,
    item_count: contacts.length,
  };
}

export async function getWebsetsCredits(): Promise<{ account_email: string; credits: number | null }> {
  const sidecar = websetsToolUrl();
  if (sidecar) return getWebsetsCreditsViaSidecar(sidecar);

  const account = await resolveWebsetsAccount();
  if (!account) throw new Error("websets account is not configured");
  const session = await freshSession(account);
  return {
    account_email: stringOr(account.email, ""),
    credits: await getCredits(session, account),
  };
}

async function searchWebsetsViaSidecar(
  base: string,
  input: { query: string; count?: number; entity?: WebsetsEntity; waitMs?: number },
): Promise<WebsetsSearchResult> {
  const res = await fetch(`${base}/search`, {
    method: "POST",
    headers: sidecarHeaders(),
    body: JSON.stringify({
      query: input.query,
      count: input.count ?? 5,
      entity: input.entity ?? "person",
      wait_ms: input.waitMs ?? 90000,
      proxy: process.env.VATI_WEBSETS_PROXY || "none",
    }),
  });
  const data = (await res.json().catch(() => null)) as Record<string, unknown> | null;
  if (!res.ok || !data?.ok) throw new Error(stringOr(data?.detail, "") || stringOr(data?.error, "") || `sidecar search ${res.status}`);
  return normalizeSidecarSearchResult(data);
}

async function getWebsetsStatusViaSidecar(
  base: string,
  websetId: string,
): Promise<Omit<WebsetsSearchResult, "account_email" | "credits">> {
  const res = await fetch(`${base}/status`, {
    method: "POST",
    headers: sidecarHeaders(),
    body: JSON.stringify({ webset_id: websetId, proxy: process.env.VATI_WEBSETS_PROXY || "none" }),
  });
  const data = (await res.json().catch(() => null)) as Record<string, unknown> | null;
  if (!res.ok || !data?.ok) throw new Error(stringOr(data?.detail, "") || `sidecar status ${res.status}`);
  const result = normalizeSidecarSearchResult(data);
  return {
    webset_id: result.webset_id,
    status: result.status,
    completed: result.completed,
    contacts: result.contacts,
    item_count: result.item_count,
  };
}

async function getWebsetsCreditsViaSidecar(base: string) {
  const res = await fetch(`${base}/credits`, { headers: sidecarHeaders() });
  const data = (await res.json().catch(() => null)) as Record<string, unknown> | null;
  if (!res.ok || !data?.ok) throw new Error(stringOr(data?.detail, "") || `sidecar credits ${res.status}`);
  return {
    account_email: stringOr(data.account_email, ""),
    credits: numberOr(data.credits, 0),
  };
}

function normalizeSidecarSearchResult(data: Record<string, unknown>): WebsetsSearchResult {
  return {
    webset_id: stringOr(data.webset_id, ""),
    status: stringOr(data.status, "unknown"),
    completed: data.completed === true,
    contacts: Array.isArray(data.contacts)
      ? data.contacts.map(normalizeSidecarContact).filter((item): item is WebsetsContact => Boolean(item))
      : [],
    account_email: stringOr(data.account_email, ""),
    credits: typeof data.credits === "number" ? data.credits : null,
    item_count: numberOr(data.item_count, Array.isArray(data.contacts) ? data.contacts.length : 0),
  };
}

function normalizeSidecarContact(value: unknown): WebsetsContact | null {
  if (!isObject(value)) return null;
  return {
    full_name: stringOr(value.full_name, ""),
    first_name: stringOr(value.first_name, ""),
    last_name: stringOr(value.last_name, ""),
    title: stringOr(value.title, ""),
    company: stringOr(value.company, ""),
    location: stringOr(value.location, ""),
    linkedin: stringOr(value.linkedin, ""),
    email: stringOr(value.email, ""),
    phone: stringOr(value.phone, ""),
  };
}

function websetsToolUrl() {
  return (process.env.VATI_WEBSETS_TOOL_URL || "").replace(/\/$/, "");
}

function sidecarHeaders() {
  return {
    "Content-Type": "application/json",
    ...(process.env.VATI_WEBSETS_TOOL_TOKEN
      ? { Authorization: `Bearer ${process.env.VATI_WEBSETS_TOOL_TOKEN}` }
      : {}),
  };
}

export function formatWebsetsForPlanner(result: WebsetsSearchResult): string {
  if (!result.contacts.length) {
    return `Websets search ${result.webset_id} is ${result.status}; no completed contacts are available yet.`;
  }
  return result.contacts
    .slice(0, 8)
    .map((contact, i) => {
      const parts = [
        contact.full_name,
        contact.title,
        contact.company,
        contact.location,
        contact.email ? `email ${contact.email}` : "",
        contact.linkedin ? `linkedin ${contact.linkedin}` : "",
      ].filter(Boolean);
      return `${i + 1}. ${parts.join(" | ")}`;
    })
    .join("\n");
}

async function resolveWebsetsAccount(): Promise<WebsetsAccount | null> {
  const envAccount = parseAccountEnv();
  if (envAccount) return envAccount;
  if (!localWebsetsFallbackEnabled()) return null;
  return readLocalAccountPool();
}

function parseAccountEnv(): WebsetsAccount | null {
  const raw = process.env.EXA_WEBSETS_ACCOUNT_JSON;
  if (raw) {
    try {
      const parsed = JSON.parse(raw) as unknown;
      const accounts = normalizeAccounts(parsed);
      return selectFreshAccount(accounts);
    } catch {
      return null;
    }
  }

  const token = process.env.EXA_WEBSETS_API_TOKEN;
  if (!token) return null;
  return {
    email: process.env.EXA_WEBSETS_EMAIL || "websets-token",
    api_token: token,
    team_id: process.env.EXA_WEBSETS_TEAM_ID || "",
    credits: Number(process.env.EXA_WEBSETS_CREDITS || 0) || MIN_CREDITS,
    cookies: [],
  };
}

async function readLocalAccountPool(): Promise<WebsetsAccount | null> {
  try {
    const fs = await import("node:fs/promises");
    const path = await import("node:path");
    const home = process.env.HOME || "";
    const dataDir = path.join(home, "orca97-v2", "people_intel", "data");
    const files = [
      "exa_accounts.json",
      "exa_dc_accounts.json",
      "exa_outlook_accounts.json",
      "exa_45f_accounts.json",
      "exa_hetzner_accounts.json",
      "exa_scale_accounts.json",
      "exa_temp_accounts.json",
      "exa_temp_accounts_batch.json",
      "exa_temp_accounts_batch2.json",
    ];
    const accounts: WebsetsAccount[] = [];
    const seen = new Set<string>();
    for (const file of files) {
      try {
        const parsed = JSON.parse(await fs.readFile(path.join(dataDir, file), "utf8")) as unknown;
        for (const account of normalizeAccounts(parsed)) {
          const email = stringOr(account.email, "");
          if (!email || seen.has(email)) continue;
          seen.add(email);
          accounts.push(account);
        }
      } catch {
        continue;
      }
    }
    return selectFreshAccount(accounts);
  } catch {
    return null;
  }
}

function normalizeAccounts(parsed: unknown): WebsetsAccount[] {
  if (Array.isArray(parsed)) return parsed.filter(isObject) as WebsetsAccount[];
  if (isObject(parsed) && Array.isArray(parsed.accounts)) {
    return parsed.accounts.filter(isObject) as WebsetsAccount[];
  }
  return [];
}

function selectFreshAccount(accounts: WebsetsAccount[]) {
  const usable = accounts
    .map((account) => {
      const apiToken = stringOr(account.api_token, "") || stringOr(account.exa_token, "");
      return { ...account, api_token: apiToken, credits: numberOr(account.credits, 0) };
    })
    .filter(
      (account) =>
        stringOr(account.status, "active") === "active" &&
        stringOr(account.api_token, "") &&
        numberOr(account.credits, 0) >= MIN_CREDITS,
    );
  usable.sort((a, b) => String(b.created_at ?? "").localeCompare(String(a.created_at ?? "")));
  return usable[0] ?? null;
}

async function freshSession(account: WebsetsAccount): Promise<WebsetsSession> {
  const cookie = cookieHeader(account.cookies);
  if (cookie) {
    const res = await fetch(EXA_TOKEN_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Cookie: cookie,
        "User-Agent": chromeUserAgent(),
      },
    });
    if (res.ok) {
      const data = (await res.json().catch(() => null)) as { token?: unknown } | null;
      const token = stringOr(data?.token, "");
      if (token) return { token, cookie };
    }
  }

  const token = stringOr(account.api_token, "") || stringOr(account.exa_token, "");
  if (!token) throw new Error("websets token is unavailable");
  return { token, cookie };
}

async function createWebset(
  session: WebsetsSession,
  input: { query: string; count: number; entity: WebsetsEntity; enrichments: Array<Record<string, string>> },
): Promise<string> {
  const payload = {
    "0": {
      search: { query: input.query, count: input.count, entity: { type: input.entity } },
      enrichments: input.enrichments,
    },
  };
  const res = await fetch(`${EXA_TRPC}/createWebset?batch=1`, {
    method: "POST",
    headers: websetsHeaders(session),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`createWebset failed ${res.status}: ${(await res.text()).slice(0, 160)}`);
  const data = (await res.json()) as unknown;
  const id = Array.isArray(data) ? stringOr(data[0]?.result?.data?.id, "") : "";
  if (!id) throw new Error("createWebset returned no webset id");
  return id;
}

async function waitForWebset(session: WebsetsSession, websetId: string, waitMs: number) {
  const started = Date.now();
  let latest: Record<string, unknown> | null = null;
  do {
    latest = await getWebset(session, websetId);
    if (latest?.status === "idle") return { status: "idle", completed: true };
    if (waitMs <= 0) break;
    await sleep(6000);
  } while (Date.now() - started < waitMs);
  return { status: stringOr(latest?.status, "running"), completed: false };
}

async function getWebset(session: WebsetsSession, websetId: string): Promise<Record<string, unknown> | null> {
  const input = encodeURIComponent(JSON.stringify({ "0": { id: websetId } }));
  const res = await fetch(`${EXA_TRPC}/getWebset?batch=1&input=${input}`, {
    headers: websetsHeaders(session),
  });
  if (!res.ok) return null;
  const data = (await res.json().catch(() => null)) as unknown;
  if (!Array.isArray(data)) return null;
  const result = data[0]?.result?.data;
  return isObject(result) ? result : null;
}

async function getWebsetItems(session: WebsetsSession, websetId: string): Promise<unknown[]> {
  const input = encodeURIComponent(JSON.stringify({ "0": { websetId } }));
  for (const endpoint of ["getWebsetItems", "getItems"]) {
    const res = await fetch(`${EXA_TRPC}/${endpoint}?batch=1&input=${input}`, {
      headers: websetsHeaders(session),
    });
    if (!res.ok) continue;
    const data = (await res.json().catch(() => null)) as unknown;
    if (!Array.isArray(data)) continue;
    const result = data[0]?.result?.data;
    if (Array.isArray(result)) return result;
    if (isObject(result) && Array.isArray(result.results)) return result.results;
    if (isObject(result) && Array.isArray(result.items)) return result.items;
  }
  return [];
}

async function getCredits(session: WebsetsSession, account: WebsetsAccount): Promise<number | null> {
  const teamId = stringOr(account.team_id, "");
  if (!teamId) return numberOr(account.credits, 0);
  const res = await fetch(`${EXA_BASE}/websets/api/billing/${teamId}`, {
    headers: websetsHeaders(session),
  }).catch(() => null);
  if (!res?.ok) return numberOr(account.credits, 0);
  const data = (await res.json().catch(() => null)) as { credits?: { balance?: unknown } } | null;
  return numberOr(data?.credits?.balance, numberOr(account.credits, 0));
}

function parseItems(items: unknown[], entity: WebsetsEntity): WebsetsContact[] {
  return items.map((item) => parseItem(item, entity)).filter((item): item is WebsetsContact => Boolean(item));
}

function parseItem(item: unknown, entity: WebsetsEntity): WebsetsContact | null {
  if (!isObject(item)) return null;
  const props = isObject(item.properties) ? item.properties : item;
  const person = isObject(props.person) ? props.person : {};
  const companyObj = isObject(props.company) ? props.company : {};

  let fullName = stringOr(person.full_name, "") || stringOr(props.name, "");
  let firstName = stringOr(person.first_name, "");
  let lastName = stringOr(person.last_name, "");
  if (!firstName && fullName) {
    const parts = fullName.split(/\s+/, 2);
    firstName = parts[0] ?? "";
    lastName = parts[1] ?? "";
  }

  let title = stringOr(person.position, "") || stringOr(props.title, "");
  let company = "";
  const experience = Array.isArray(person.experience) ? person.experience : [];
  const latest = experience.find(isObject);
  if (latest) {
    company = stringOr(latest.company_name, "");
    title ||= stringOr(latest.position, "");
  }

  let location = stringOr(person.location, "");
  if (entity === "company") {
    fullName = stringOr(companyObj.identity?.name, "") || fullName;
    const hq = isObject(companyObj.locations?.headquarters) ? companyObj.locations.headquarters : {};
    location = [stringOr(hq.city, ""), stringOr(hq.country, "")].filter(Boolean).join(", ");
    company = fullName;
  }

  let email = "";
  let phone = "";
  let linkedin = "";
  const enrichments = Array.isArray(item.enrichments) ? item.enrichments : [];
  for (const enrichment of enrichments.filter(isObject)) {
    if (stringOr(enrichment.status, "") !== "completed") continue;
    const result = Array.isArray(enrichment.result) ? enrichment.result[0] : enrichment.result;
    const value = stringOr(result, "");
    if (!value) continue;
    const format = stringOr(enrichment.format, "");
    if (format === "email" && !email) email = value;
    else if (format === "phone" && !phone) phone = value;
    else if (format === "url" && value.toLowerCase().includes("linkedin")) linkedin = value;
  }

  linkedin ||= stringOr(person.url, "") || stringOr(props.url, "");
  if (!fullName && !company) return null;
  return {
    full_name: fullName,
    first_name: firstName,
    last_name: lastName,
    title,
    company,
    location,
    linkedin,
    email,
    phone,
    raw: item,
  };
}

function websetsHeaders(session: WebsetsSession) {
  return {
    Authorization: `Bearer ${session.token}`,
    "Content-Type": "application/json",
    "User-Agent": chromeUserAgent(),
    ...(session.cookie ? { Cookie: session.cookie } : {}),
  };
}

function cookieHeader(cookies: WebsetsCookie[] | undefined) {
  const parts = (cookies ?? [])
    .map((cookie) => {
      const name = stringOr(cookie.name, "");
      const value = stringOr(cookie.value, "");
      if (!name || !value) return "";
      return `${name}=${value}`;
    })
    .filter(Boolean);
  return parts.join("; ");
}

function localWebsetsFallbackEnabled() {
  return process.env.NODE_ENV !== "production" && process.env.EXA_WEBSETS_LOCAL_FALLBACK !== "0";
}

function chromeUserAgent() {
  return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";
}

function isObject(value: unknown): value is Record<string, any> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function stringOr(value: unknown, fallback: string) {
  return typeof value === "string" ? value : fallback;
}

function numberOr(value: unknown, fallback: number) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function clampInt(value: number, min: number, max: number) {
  if (!Number.isFinite(value)) return min;
  return Math.max(min, Math.min(max, Math.trunc(value)));
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
