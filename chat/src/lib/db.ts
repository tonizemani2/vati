// Neon Postgres access. Uses the serverless HTTP driver so it runs identically on
// Cloudflare Workers, Vercel, and local Node. DATABASE_URL comes from the platform
// env (Worker secret / Vercel env / local .env).
import { neon } from "@neondatabase/serverless";

let cached: ReturnType<typeof neon> | null = null;

export function db() {
  if (cached) return cached;
  const url = process.env.DATABASE_URL;
  if (!url) throw new Error("DATABASE_URL not set");
  cached = neon(url);
  return cached;
}

export function dbConfigured(): boolean {
  return Boolean(process.env.DATABASE_URL);
}

// --- forward record (read-only at runtime) ---------------------------------
export type ForwardCall = {
  question: string;
  probability: number | null;
  ci_low: number | null;
  ci_high: number | null;
  ci_unit: string | null;
  threshold: number | null;
  threshold_dir: string | null;
  resolution_date: string | null;
  thesis_kind: string | null;
  kill_criteria: string[] | null;
  rationale: string | null;
  implications: {
    exposed?: string;
    action_now?: string;
    decision_changed?: string;
    roi_logic?: string;
    rent_path?: string;
    winners?: { who: string; why: string }[];
    losers?: { who: string; why: string }[];
    reprices?: string;
    next_constraint?: string;
    watch?: string;
  } | null;
};

export async function getForwardCalls(limit = 60): Promise<ForwardCall[]> {
  const sql = db();
  try {
    return (await sql`
      select question, probability, ci_low, ci_high, ci_unit, threshold, threshold_dir,
             resolution_date, thesis_kind, kill_criteria, rationale, implications
      from forward_calls
      where outcome is null
      order by resolution_date asc nulls last
      limit ${limit}
    `) as unknown as ForwardCall[];
  } catch (err) {
    if (!isMissingColumnError(err)) throw err;
    return (await sql`
      select question, probability, ci_low, ci_high, ci_unit, threshold, threshold_dir,
             resolution_date, thesis_kind, kill_criteria, rationale, null::jsonb as implications
      from forward_calls
      where outcome is null
      order by resolution_date asc nulls last
      limit ${limit}
    `) as unknown as ForwardCall[];
  }
}

function isMissingColumnError(err: unknown): boolean {
  return typeof err === "object" && err !== null && "code" in err && err.code === "42703";
}

// --- conversations + messages ----------------------------------------------
export async function createConversation(userId: string, title: string | null) {
  const sql = db();
  const rows = (await sql`
    insert into conversations (user_id, title) values (${userId}, ${title})
    returning id
  `) as unknown as { id: string }[];
  return rows[0].id;
}

export async function listConversations(userId: string, limit = 40) {
  const sql = db();
  return (await sql`
    select id, title, updated_at from conversations
    where user_id = ${userId}
    order by updated_at desc
    limit ${limit}
  `) as unknown as { id: string; title: string | null; updated_at: string }[];
}

export async function getMessages(conversationId: string, userId: string) {
  const sql = db();
  return (await sql`
    select m.role, m.content, m.reasoning
    from messages m
    join conversations c on c.id = m.conversation_id
    where m.conversation_id::text = ${conversationId} and c.user_id = ${userId}
    order by m.id asc
  `) as unknown as { role: string; content: string; reasoning: string | null }[];
}

// Does this conversation belong to this caller? Used to stop cross-tenant writes: the
// client supplies conversation_id, so any persist into someone else's conversation must
// be rejected (write-IDOR).
export async function conversationOwnedBy(conversationId: string, userId: string): Promise<boolean> {
  const sql = db();
  const rows = (await sql`
    select 1 from conversations where id::text = ${conversationId} and user_id = ${userId} limit 1
  `) as unknown as unknown[];
  return rows.length > 0;
}

export async function addMessage(
  conversationId: string,
  role: "user" | "assistant",
  content: string,
  reasoning?: string | null,
) {
  const sql = db();
  await sql`
    insert into messages (conversation_id, role, content, reasoning)
    values (${conversationId}, ${role}, ${content}, ${reasoning ?? null})
  `;
  await sql`update conversations set updated_at = now() where id = ${conversationId}`;
}

// --- immutable forecast cards ----------------------------------------------
export type CardRow = {
  conversation_id: string | null;
  user_id: string | null;
  question: string;
  quantity_label?: string | null;
  ci_unit?: string | null;
  base_value?: number | null;
  horizon_years?: number | null;
  g_mean?: number | null;
  g_sd?: number | null;
  decel?: number | null;
  threshold?: number | null;
  threshold_dir?: string | null;
  probability?: number | null;
  median?: number | null;
  ci_low?: number | null;
  ci_high?: number | null;
  resolution_date?: string | null;
  dated_metric?: string | null;
  kill_criteria?: string[] | null;
  already_priced?: string | null;
};

export async function insertForecastCard(c: CardRow) {
  const sql = db();
  await sql`
    insert into forecast_cards
      (conversation_id, user_id, question, quantity_label, ci_unit, base_value, horizon_years,
       g_mean, g_sd, decel, threshold, threshold_dir, probability, median, ci_low, ci_high,
       resolution_date, dated_metric, kill_criteria, already_priced)
    values
      (${c.conversation_id}, ${c.user_id}, ${c.question}, ${c.quantity_label ?? null},
       ${c.ci_unit ?? null}, ${c.base_value ?? null}, ${c.horizon_years ?? null},
       ${c.g_mean ?? null}, ${c.g_sd ?? null}, ${c.decel ?? null}, ${c.threshold ?? null},
       ${c.threshold_dir ?? null}, ${c.probability ?? null}, ${c.median ?? null},
       ${c.ci_low ?? null}, ${c.ci_high ?? null}, ${c.resolution_date ?? null},
       ${c.dated_metric ?? null}, ${JSON.stringify(c.kill_criteria ?? [])}, ${c.already_priced ?? null})
  `;
}

// --- owner admin mind maps ---------------------------------------------------
// Internal operator surface: store editable XYFlow canvases per verified owner
// account. The schema is created lazily from the owner-only admin route so local
// and preview deployments do not need a separate migration just to try the UI.
export type AdminMindMapRow = {
  id: string;
  title: string;
  nodes: unknown[];
  edges: unknown[];
  updated_at: string;
};

let adminMindSchemaReady = false;

async function ensureAdminMindSchema() {
  if (adminMindSchemaReady) return;
  const sql = db();
  await sql`
    create table if not exists admin_mind_maps (
      id uuid primary key,
      user_id text not null,
      title text not null,
      nodes jsonb not null default '[]'::jsonb,
      edges jsonb not null default '[]'::jsonb,
      created_at timestamptz not null default now(),
      updated_at timestamptz not null default now()
    )
  `;
  await sql`
    create index if not exists admin_mind_maps_user_updated_idx
      on admin_mind_maps (user_id, updated_at desc)
  `;
  adminMindSchemaReady = true;
}

export async function listAdminMindMaps(userId: string, limit = 24): Promise<AdminMindMapRow[]> {
  await ensureAdminMindSchema();
  const sql = db();
  return (await sql`
    select id::text, title, nodes, edges, updated_at
    from admin_mind_maps
    where user_id = ${userId}
    order by updated_at desc
    limit ${limit}
  `) as unknown as AdminMindMapRow[];
}

export async function upsertAdminMindMap(
  userId: string,
  map: { id: string; title: string; nodes: unknown[]; edges: unknown[] },
): Promise<AdminMindMapRow> {
  await ensureAdminMindSchema();
  const sql = db();
  const rows = (await sql`
    insert into admin_mind_maps (id, user_id, title, nodes, edges, updated_at)
    values (
      ${map.id}::uuid,
      ${userId},
      ${map.title || "Untitled map"},
      ${JSON.stringify(map.nodes)}::jsonb,
      ${JSON.stringify(map.edges)}::jsonb,
      now()
    )
    on conflict (id) do update
      set title = excluded.title,
          nodes = excluded.nodes,
          edges = excluded.edges,
          updated_at = now()
      where admin_mind_maps.user_id = ${userId}
    returning id::text, title, nodes, edges, updated_at
  `) as unknown as AdminMindMapRow[];
  if (!rows[0]) throw new Error("map not owned by caller");
  return rows[0];
}

export async function deleteAdminMindMap(userId: string, id: string): Promise<boolean> {
  await ensureAdminMindSchema();
  const sql = db();
  const rows = (await sql`
    delete from admin_mind_maps
    where id = ${id}::uuid and user_id = ${userId}
    returning id
  `) as unknown as unknown[];
  return rows.length > 0;
}

export async function deleteConversation(userId: string, conversationId: string): Promise<boolean> {
  const sql = db();
  const rows = (await sql`
    delete from conversations
    where id::text = ${conversationId} and user_id = ${userId}
    returning id
  `) as unknown as unknown[];
  return rows.length > 0;
}
