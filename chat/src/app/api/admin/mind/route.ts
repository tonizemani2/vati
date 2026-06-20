import { requireAdminAccess } from "@/lib/adminAccess";
import { badOrigin } from "@/lib/auth";
import {
  addMessage,
  conversationOwnedBy,
  createConversation,
  dbConfigured,
  deleteAdminMindMap,
  getForwardCalls,
  listAdminMindMaps,
  upsertAdminMindMap,
} from "@/lib/db";
import { askDataLayer, groundDeep, type DataRead } from "@/lib/dataLayer";
import { resolveProvider, type ChatMessage } from "@/lib/model";
import { runCapture, type CapturePlan } from "@/lib/capture";
import { edgeRateLimit } from "@/lib/security";
import { formatWebsetsForPlanner, searchWebsets, websetsEnabled, type WebsetsSearchResult } from "@/lib/websets";

export const dynamic = "force-dynamic";

type MindNode = {
  id?: unknown;
  position?: unknown;
  data?: {
    label?: unknown;
    summary?: unknown;
    kind?: unknown;
    source?: unknown;
  };
};

type MindEdge = {
  id?: unknown;
  source?: unknown;
  target?: unknown;
  label?: unknown;
};

type PlannerOperation =
  | {
      type: "addNode";
      id?: string;
      label: string;
      summary?: string;
      kind?: string;
      source?: string;
      x?: number;
      y?: number;
      connectTo?: string;
      edgeLabel?: string;
    }
  | {
      type: "updateNode";
      id: string;
      label?: string;
      summary?: string;
      kind?: string;
      source?: string;
    }
  | { type: "deleteNode"; id: string }
  | { type: "addEdge"; id?: string; source: string; target: string; label?: string }
  | { type: "deleteEdge"; id: string };

type PlannerResult = {
  reply: string;
  mapTitle?: string;
  operations: PlannerOperation[];
};

type PeopleToolRead = {
  summary: string;
  result: WebsetsSearchResult | null;
  error?: string;
} | null;

export async function GET(request: Request) {
  if (badOrigin(request)) return json({ ok: false, error: "bad origin" }, 403);

  const { caller, allowed } = await requireAdminAccess(request);
  if (!allowed) return json({ ok: false, error: "pin required" }, 403, caller.setCookie);

  if (!dbConfigured()) {
    return json({ ok: true, maps: [], db: false }, 200, caller.setCookie);
  }

  try {
    const maps = await listAdminMindMaps(caller.id);
    return json({ ok: true, maps, db: true }, 200, caller.setCookie);
  } catch (e) {
    console.error("admin mind list failed", e);
    return json({ ok: false, maps: [], db: true, error: "map store unavailable" }, 200, caller.setCookie);
  }
}

export async function POST(request: Request) {
  if (badOrigin(request)) return json({ ok: false, error: "bad origin" }, 403);
  const limited = await edgeRateLimit(request, {
    bucket: "api-admin-mind",
    limit: 40,
    windowSeconds: 600,
  });
  if (limited) return limited;

  const { caller, allowed } = await requireAdminAccess(request);
  if (!allowed) return json({ ok: false, error: "pin required" }, 403, caller.setCookie);

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return json({ ok: false, error: "bad request" }, 400, caller.setCookie);
  }

  const action = typeof body.action === "string" ? body.action : "chat";

  try {
    if (action === "save_map") {
      if (!dbConfigured()) return json({ ok: true, saved: false, db: false }, 200, caller.setCookie);
      const requestedMapId = stringOr(body.map_id, "");
      const map = await upsertAdminMindMap(caller.id, {
        id: isUuid(requestedMapId) ? requestedMapId : crypto.randomUUID(),
        title: stringOr(body.title, "Untitled map").slice(0, 120),
        nodes: safeArray(body.nodes).slice(0, 120),
        edges: safeArray(body.edges).slice(0, 180),
      });
      const maps = await listAdminMindMaps(caller.id);
      return json({ ok: true, saved: true, map, maps, db: true }, 200, caller.setCookie);
    }

    if (action === "delete_map") {
      if (!dbConfigured()) return json({ ok: true, deleted: false, db: false }, 200, caller.setCookie);
      const mapId = stringOr(body.map_id, "");
      const deleted = isUuid(mapId) ? await deleteAdminMindMap(caller.id, mapId) : false;
      const maps = await listAdminMindMaps(caller.id);
      return json({ ok: true, deleted, maps, db: true }, 200, caller.setCookie);
    }

    if (action !== "chat") {
      return json({ ok: false, error: "unknown action" }, 400, caller.setCookie);
    }

    const prompt = stringOr(body.prompt, "").trim();
    if (!prompt) return json({ ok: false, error: "empty prompt" }, 400, caller.setCookie);

    const nodes = compactNodes(safeArray(body.nodes));
    const edges = compactEdges(safeArray(body.edges));
    const history = compactHistory(safeArray(body.messages));
    const deepData = body.deep_data === true;

    // The agent decides for itself which tools to fire and can chain them
    // (ground a thesis, score it against the record, source the exposed people,
    // design the capture play). No regex pre-routing: the model drives.
    const agent = await runAgentLoop({
      prompt,
      history,
      nodes,
      edges,
      deepData,
    }).catch((e) => {
      console.error("mind agent loop failed", e);
      return { plan: fallbackPlan(prompt, nodes), toolsUsed: [] as string[], ground: null, people: null };
    });

    const plan = ensurePlannerCompletes(prompt, nodes, agent.plan);
    const dataRead = agent.ground;
    const peopleTool = agent.people;

    let conversationId = stringOr(body.conversation_id, "");
    if (dbConfigured()) {
      try {
        if (conversationId && !(await conversationOwnedBy(conversationId, caller.id))) {
          conversationId = "";
        }
        if (!conversationId) {
          conversationId = await createConversation(caller.id, `Mind map: ${prompt.slice(0, 68)}`);
        }
        await addMessage(conversationId, "user", prompt);
        await addMessage(
          conversationId,
          "assistant",
          `${plan.reply}\n\n[mind-map-ops]\n${JSON.stringify(plan.operations)}`,
        );
      } catch (e) {
        console.error("admin mind conversation persist failed", e);
      }
    }

    return json(
      {
        ok: true,
        plan,
        conversation_id: conversationId || null,
        tools_used: agent.toolsUsed,
        data_layer: dataRead ? { answer: dataRead.answer, evidence: dataRead.evidence } : null,
        people_tool: peopleTool
          ? {
              summary: peopleTool.summary,
              result: peopleTool.result,
              error: peopleTool.error,
            }
          : null,
      },
      200,
      caller.setCookie,
    );
  } catch (e) {
    console.error("admin mind action failed", e);
    return json({ ok: false, error: "admin mind failed" }, 500, caller.setCookie);
  }
}

type Provider = ReturnType<typeof resolveProvider>;

// --- agentic tool loop -------------------------------------------------------
// Hermes is a real tool-using agent: the model chooses which tools to fire and can chain them
// (ground a thesis on OUR graph, score it against the scored record, source the exposed
// decision-makers, then design the capture play). When it is done gathering it stops calling
// tools and emits the final mind-map plan. No regex pre-routing: the model drives.

type RawToolCall = {
  id?: string;
  type?: string;
  function?: { name?: string; arguments?: string };
};

// The loop carries tool turns the base ChatMessage union does not model (assistant turns that
// hold tool_calls, and tool-result turns). The provider is OpenAI-compatible, so these serialize
// straight through.
type AgentMessage =
  | ChatMessage
  | { role: "assistant"; content: string; tool_calls: RawToolCall[] }
  | { role: "tool"; content: string; tool_call_id: string };

type AgentResult = {
  plan: PlannerResult;
  toolsUsed: string[];
  ground: DataRead | null;
  people: PeopleToolRead;
};

const AGENT_TOOLS = [
  {
    type: "function",
    function: {
      name: "ground_graph",
      description:
        "Ask the Vaticinus data layer (our concept/actor/dependency graph + minted series + the leak-free record) about a topic. This is OUR data, not the open web: use it to ground a thesis, walk the dependency graph, and find which inputs actually bind. Returns null when the sidecar has nothing or is offline. Set deep=true for the slow agentic graph reasoning, false (default) for a fast keyword slice.",
      parameters: {
        type: "object",
        properties: {
          question: { type: "string", description: "the specific grounding question" },
          deep: { type: "boolean", description: "true for the deep agentic graph loop, default false" },
        },
        required: ["question"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "query_record",
      description:
        "Pull our own open forward calls (the dated, Brier-scored, leak-free record): question, probability, resolution date. Use to check whether a thesis is already a tracked call and how confident we are.",
      parameters: {
        type: "object",
        properties: { limit: { type: "number", description: "how many calls, default 16, max 40" } },
      },
    },
  },
  {
    type: "function",
    function: {
      name: "find_people",
      description:
        "Source the real decision-makers / buyers exposed to a thesis (Exa Websets). Returns names, titles, companies, and contact handles where available. Use only once a thesis is grounded and worth acting on.",
      parameters: {
        type: "object",
        properties: {
          query: { type: "string", description: "who to find, in plain language" },
          count: { type: "number", description: "how many people, default 5, max 10" },
        },
        required: ["query"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "design_capture",
      description:
        "Turn a thesis we have strong, early, grounded confidence in into a concrete value-capture play: named target orgs and people, the exact first ask, the value mechanism, who pays, and an adversarial money-path check. ONLY call this AFTER the thesis is grounded (via ground_graph or the record) and you can state why it is early and likely. This is how we capitalise on being right before the market prices it.",
      parameters: {
        type: "object",
        properties: {
          thesis: { type: "string", description: "the grounded thesis, stated as a falsifiable future" },
          context: { type: "string", description: "the grounding/evidence behind why it is early and likely" },
        },
        required: ["thesis"],
      },
    },
  },
] as const;

async function runAgentLoop(input: {
  prompt: string;
  history: ChatMessage[];
  nodes: Array<Record<string, unknown>>;
  edges: Array<Record<string, unknown>>;
  deepData: boolean;
}): Promise<AgentResult> {
  const provider = resolveProvider();
  const toolsUsed: string[] = [];
  let ground: DataRead | null = null;
  let people: PeopleToolRead = null;

  const messages: AgentMessage[] = [
    { role: "system", content: AGENT_SYSTEM_PROMPT },
    ...input.history,
    {
      role: "user",
      content: JSON.stringify(
        {
          request: input.prompt,
          current_map: { nodes: input.nodes, edges: input.edges },
          deep_data_preferred: input.deepData,
        },
        null,
        2,
      ),
    },
  ];

  // Bounded loop. Each step is one model turn; tool calls feed results back. A wall-clock
  // deadline forces a final answer so a slow tool (capture runs live web research) never
  // hangs the request past the edge timeout. Streaming the steps is the follow-up hardening.
  const MAX_STEPS = 5;
  const deadline = Date.now() + 80_000;

  for (let step = 0; step < MAX_STEPS; step += 1) {
    const forceFinal = step === MAX_STEPS - 1 || Date.now() > deadline;
    if (forceFinal) {
      messages.push({
        role: "user",
        content: "Stop calling tools now. Output ONLY the final mind-map plan as a JSON object (reply, optional mapTitle, operations).",
      });
    }

    const msg = await callModelRaw(provider, messages, forceFinal ? null : AGENT_TOOLS, 2400);
    const toolCalls = forceFinal ? [] : msg.tool_calls ?? [];

    if (toolCalls.length) {
      // echo the assistant's tool-call turn back so the tool results attach to it
      messages.push({ role: "assistant", content: msg.content ?? "", tool_calls: toolCalls });
      for (const call of toolCalls) {
        const exec = await execTool(call, { deepData: input.deepData, prompt: input.prompt });
        if (exec.tool) toolsUsed.push(exec.tool);
        if (exec.ground) ground = exec.ground;
        if (exec.people) people = exec.people;
        messages.push({
          role: "tool",
          tool_call_id: call.id ?? "",
          content: exec.output.slice(0, 6000),
        });
      }
      continue;
    }

    // No tool calls: this turn is the final plan.
    const plan = await finalizePlan(provider, msg.content ?? "", input.prompt, input.nodes);
    return { plan, toolsUsed, ground, people };
  }

  return {
    plan: ensurePlannerCompletes(input.prompt, input.nodes, {
      reply: "I gathered context but did not converge on a final plan within the step budget.",
      operations: [],
    }),
    toolsUsed,
    ground,
    people,
  };
}

async function execTool(
  call: RawToolCall,
  ctx: { deepData: boolean; prompt: string },
): Promise<{ output: string; tool?: string; ground?: DataRead | null; people?: PeopleToolRead }> {
  const name = call.function?.name ?? "";
  let args: Record<string, unknown> = {};
  try {
    args = JSON.parse(call.function?.arguments || "{}") as Record<string, unknown>;
  } catch {
    args = {};
  }

  try {
    if (name === "ground_graph") {
      const question = stringOr(args.question, ctx.prompt).slice(0, 600);
      const deep = args.deep === true || (args.deep == null && ctx.deepData);
      const read = deep ? await groundDeep(question) : await askDataLayer(question);
      if (!read) {
        return { tool: name, output: "No data-layer result (nothing in the graph for that query, or the sidecar is offline). Do not invent facts; say what is missing." };
      }
      return { tool: name, ground: read, output: read.answer };
    }

    if (name === "query_record") {
      const limit = clampInt(args.limit, 16, 1, 40);
      return { tool: name, output: await forwardRecordSummary(limit) };
    }

    if (name === "find_people") {
      const query = stringOr(args.query, ctx.prompt).slice(0, 600);
      const count = clampInt(args.count, 5, 1, 10);
      const result = await runPeopleTool(`${query} (find ${count} people)`);
      return { tool: name, people: result, output: result?.summary ?? "people search returned nothing" };
    }

    if (name === "design_capture") {
      const thesis = stringOr(args.thesis, ctx.prompt).slice(0, 800);
      const context = stringOr(args.context, "").slice(0, 4000);
      return { tool: name, output: await runCaptureTool(thesis, context) };
    }

    return { output: `Unknown tool "${name}". Output the final JSON plan instead of calling more tools.` };
  } catch (e) {
    return { tool: name, output: `Tool "${name}" failed: ${e instanceof Error ? e.message : "error"}. Proceed without it; do not fabricate.` };
  }
}

// Run the value-capture engine (research exposed orgs -> design the play -> adversarial
// money-path refute) and hand the structured plan back to the agent as a tool result, so the
// agent renders it as capture nodes on the canvas.
async function runCaptureTool(thesis: string, context: string): Promise<string> {
  let plan: CapturePlan | null = null;
  let error = "";
  try {
    await runCapture(thesis, context, (ev) => {
      if (ev.t === "plan") plan = ev.plan;
      else if (ev.t === "error") error = ev.v;
    });
  } catch (e) {
    error = e instanceof Error ? e.message : "capture failed";
  }
  if (!plan) return `Capture engine produced no play: ${error || "unknown reason"}. Do not invent targets.`;
  return JSON.stringify(plan);
}

async function finalizePlan(
  provider: Provider,
  content: string,
  prompt: string,
  nodes: Array<Record<string, unknown>>,
): Promise<PlannerResult> {
  try {
    return normalizePlannerResult(parseJsonObject(content));
  } catch (parseError) {
    const repaired = await repairPlannerJson(provider, content);
    try {
      return normalizePlannerResult(parseJsonObject(repaired));
    } catch (repairError) {
      console.error("mind planner JSON repair failed", { parseError, repairError });
      return malformedJsonPlan(prompt, nodes, content);
    }
  }
}

function clampInt(value: unknown, fallback: number, min: number, max: number): number {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(min, Math.min(max, Math.trunc(n)));
}

async function completePlanner(provider: Provider, messages: ChatMessage[], maxTokens: number): Promise<string> {
  const res = await fetch(provider.url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${provider.key}`,
      "Content-Type": "application/json",
      ...(provider.extraHeaders || {}),
    },
    body: JSON.stringify({
      model: provider.model,
      stream: false,
      max_tokens: maxTokens,
      temperature: 0.2,
      response_format: { type: "json_object" },
      messages,
    }),
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`model ${res.status}: ${detail.slice(0, 160)}`);
  }

  const data = (await res.json()) as {
    choices?: Array<{ message?: { content?: string; reasoning_content?: string } }>;
  };
  return data.choices?.[0]?.message?.content ?? "";
}

// One OpenAI-compatible turn that may carry tools. Returns the raw assistant message so the loop
// can read tool_calls. When tools is null the turn is forced to a final answer and we ask for a
// JSON object (the planner schema), which finalizePlan parses. response_format json_object cannot
// be combined with tool calling, so it is only set on the forced-final turn.
async function callModelRaw(
  provider: Provider,
  messages: AgentMessage[],
  tools: typeof AGENT_TOOLS | null,
  maxTokens: number,
): Promise<{ content?: string; tool_calls?: RawToolCall[] }> {
  const res = await fetch(provider.url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${provider.key}`,
      "Content-Type": "application/json",
      ...(provider.extraHeaders || {}),
    },
    body: JSON.stringify({
      model: provider.model,
      stream: false,
      max_tokens: maxTokens,
      temperature: 0.2,
      ...(tools ? { tools, tool_choice: "auto" } : { response_format: { type: "json_object" } }),
      messages,
    }),
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`model ${res.status}: ${detail.slice(0, 160)}`);
  }

  const data = (await res.json()) as {
    choices?: Array<{ message?: { content?: string; tool_calls?: RawToolCall[] } }>;
  };
  const msg = data.choices?.[0]?.message ?? {};
  return { content: msg.content, tool_calls: msg.tool_calls };
}

async function repairPlannerJson(provider: Provider, malformed: string): Promise<string> {
  return completePlanner(
    provider,
    [
      {
        role: "system",
        content:
          "Repair malformed JSON into valid JSON only. Keep the exact admin mind-map schema: reply string, optional mapTitle string, operations array. Do not add markdown or commentary.",
      },
      {
        role: "user",
        content: malformed.slice(0, 12000),
      },
    ],
    2400,
  );
}

const AGENT_SYSTEM_PROMPT = `You are Hermes, the private Vaticinus mind-map agent. You help the owner find where scarcity and value migrate before the market prices it in, and then capitalise on it. The governing idea: rent accrues to the binding constraint, and the edge is spotting where that constraint moves next. Walk the causal spine when you reason: Frontier, Capability, Dependency graph, Supply elasticity, Demand, Capital, Pricing, Policy, Outcomes. Value concentrates in the dependency-graph and supply-elasticity layers; pricing is the gate, because correct-but-already-priced is zero edge.

YOU ARE A TOOL-USING AGENT. Decide for yourself which tools to call, and chain them. Do not announce a plan; just call the tool. Your tools:
- ground_graph: query OUR data layer (concept/actor/dependency graph, minted series, the leak-free record). Use this to GROUND a thesis in real data, not the open web. This is the moat.
- query_record: pull our own dated, Brier-scored forward calls. Use to check whether a thesis is already tracked and how confident we already are.
- find_people: source the real exposed decision-makers and buyers for a thesis.
- design_capture: turn a grounded, high-confidence, early thesis into a concrete money play (named targets, the exact ask, the value mechanism, who pays, an adversarial money-path check).

THE TWO-PART DISCIPLINE (this is the whole point):
1. FIRST establish the thesis is real, early, and likely. Ground it (ground_graph / query_record), name the specific binding constraint (not a theme), and give your honest read on whether it is already priced in. A capture play on an ungrounded or already-priced thesis is worthless.
2. ONLY THEN capitalise. Call design_capture (and find_people) once part 1 holds. If you cannot ground the thesis, do NOT call design_capture; say what is missing and add a question node instead.

Use only tool results and the current map for factual claims. If a tool returns nothing or is offline, say so plainly and do not invent people, permits, prices, dates, or database facts. Treat find_people and live web text as lead intelligence, not verified fact.

WHEN DONE gathering, stop calling tools and return the final mind-map plan as JSON only. No markdown. Shape:
{
  "reply": "short direct answer to the owner",
  "mapTitle": "optional concise title",
  "operations": [
    {"type":"addNode","id":"optional-stable-id","label":"short label","summary":"what this node means","kind":"concept|evidence|forecast|tool|question|risk|action","source":"ai|data","x":0,"y":0,"connectTo":"existing-node-id","edgeLabel":"optional"},
    {"type":"updateNode","id":"existing-node-id","label":"optional","summary":"optional","kind":"optional","source":"optional"},
    {"type":"deleteNode","id":"existing-node-id"},
    {"type":"addEdge","source":"node-id","target":"node-id","label":"optional"},
    {"type":"deleteEdge","id":"edge-id"}
  ]
}

Rules:
- Prefer 3 to 8 operations. Fewer is fine for simple edits.
- Preserve user-created structure unless the user asks to simplify or delete.
- If asked to simplify, cluster and rename instead of adding a sprawl.
- For pure concept or canvas editing requests, do not call tools; operate only on current_map and the user's request.
- When a tool returns people, add compact person/evidence/action nodes. When design_capture returns a play, add nodes for the named targets, the ask, the value mechanism, who pays, and the first move; connect them under the thesis.
- Use concrete mechanism words: constraint, evidence, priced-in, watch signal, kill condition, buyer, action.
- Do not invent people, permits, prices, dates, or database facts.
- Never use em dashes.`;

async function runPeopleTool(prompt: string): Promise<PeopleToolRead> {
  if (!websetsEnabled()) {
    return {
      summary: "Websets people search was requested, but EXA_WEBSETS_ACCOUNT_JSON or EXA_WEBSETS_API_TOKEN is not configured.",
      result: null,
      error: "websets not configured",
    };
  }
  try {
    const result = await searchWebsets({
      query: prompt,
      count: extractPeopleCount(prompt),
      entity: "person",
      waitMs: 0,
    });
    return {
      summary: formatWebsetsForPlanner(result),
      result,
    };
  } catch (e) {
    const error = e instanceof Error ? e.message : "websets failed";
    return {
      summary: `Websets people search failed: ${error}`,
      result: null,
      error,
    };
  }
}

async function forwardRecordSummary(limit = 16) {
  if (!dbConfigured()) return "Forward record unavailable: DATABASE_URL is not configured.";
  try {
    const calls = await getForwardCalls(limit);
    if (!calls.length) return "Forward record is configured but returned no open calls.";
    return calls
      .map((c, i) => {
        const p = c.probability == null ? "no P" : `${Math.round(c.probability * 100)}%`;
        return `${i + 1}. ${c.question} | ${p} | resolves ${c.resolution_date ?? "unknown"}`;
      })
      .join("\n");
  } catch {
    return "Forward record query failed for this request.";
  }
}

function parseJsonObject(text: string): unknown {
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const raw = fenced?.[1] ?? text.match(/\{[\s\S]*\}/)?.[0] ?? text;
  const candidates = [
    raw,
    raw.replace(/,\s*([}\]])/g, "$1"),
    escapeBareControlCharsInJsonStrings(raw),
    escapeBareControlCharsInJsonStrings(raw).replace(/,\s*([}\]])/g, "$1"),
  ];
  let lastError: unknown;
  for (const candidate of candidates) {
    try {
      return JSON.parse(candidate);
    } catch (e) {
      lastError = e;
    }
  }
  throw lastError;
}

function escapeBareControlCharsInJsonStrings(text: string) {
  let escaped = "";
  let inString = false;
  let slashCount = 0;

  for (const char of text) {
    const isEscaped = slashCount % 2 === 1;
    if (char === '"' && !isEscaped) inString = !inString;

    if (inString && char === "\n") escaped += "\\n";
    else if (inString && char === "\r") escaped += "\\r";
    else if (inString && char === "\t") escaped += "\\t";
    else escaped += char;

    if (char === "\\") slashCount += 1;
    else slashCount = 0;
  }

  return escaped;
}

function normalizePlannerResult(value: unknown): PlannerResult {
  const obj = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  const operations = collectPlannerOperationInputs(obj)
    .map(normalizeOperation)
    .filter((op): op is PlannerOperation => Boolean(op))
    .slice(0, 20);
  const reply = stringOr(obj.reply, "").trim() || "No map edits were needed for that request.";
  return {
    reply: reply.slice(0, 1400),
    mapTitle: stringOr(obj.mapTitle, "").slice(0, 120) || undefined,
    operations,
  };
}

function collectPlannerOperationInputs(obj: Record<string, unknown>): unknown[] {
  const candidates: unknown[] = [];
  for (const key of ["operations", "ops", "actions", "changes", "edits", "mapOperations", "map_edits"]) {
    const value = obj[key];
    if (Array.isArray(value)) candidates.push(...value);
    else if (value && typeof value === "object") candidates.push(...flattenOperationGroups(value));
  }
  if (candidates.length) return candidates;

  const nodeOps = safeArray(obj.nodes).map(nodeLikeToAddNode).filter(Boolean);
  const edgeOps = safeArray(obj.edges).map(edgeLikeToAddEdge).filter(Boolean);
  return [...nodeOps, ...edgeOps];
}

function flattenOperationGroups(value: unknown): unknown[] {
  if (!value || typeof value !== "object") return [];
  const grouped = value as Record<string, unknown>;
  const output: unknown[] = [];
  for (const [key, maybeItems] of Object.entries(grouped)) {
    const type = canonicalOperationType(key);
    if (!Array.isArray(maybeItems)) continue;
    output.push(
      ...maybeItems.map((item) =>
        item && typeof item === "object" ? { ...(item as Record<string, unknown>), type } : item,
      ),
    );
  }
  return output;
}

function ensurePlannerCompletes(
  prompt: string,
  nodes: Array<Record<string, unknown>>,
  plan: PlannerResult,
): PlannerResult {
  if (plan.operations.length > 0) return plan;
  if (!expectsMapEdit(prompt)) return plan;
  const rootId = stringOr(nodes[0]?.id, "root");
  const needsGrounding = expectsExternalContext(prompt);
  return {
    ...plan,
    reply: needsGrounding
      ? "I could not find enough grounded context to edit the map confidently, so I added a review node instead of pretending."
      : "DeepSeek did not return any safe canvas operations, so I added a review node instead of pretending the map changed.",
    operations: [
      {
        type: "addNode",
        id: `review-${Date.now()}`,
        label: needsGrounding ? "Needs grounded review" : "Needs canvas review",
        summary: `No safe map edits were produced for: ${prompt.slice(0, 220)}`,
        kind: "question",
        source: "local",
        connectTo: rootId,
        edgeLabel: "review",
      },
    ],
  };
}

function expectsMapEdit(prompt: string): boolean {
  return /\b(map|canvas|node|edge|connect|relate|simplify|delete|pull|record|database|db|add|build|show how|make)\b/i.test(
    prompt,
  );
}

function expectsExternalContext(prompt: string): boolean {
  return /\b(record|database|db|data|forward|evidence|corpus|permit|people|person|enrich|enrichment|xr|pulp|tool|company|customer)\b/i.test(
    prompt,
  );
}

function extractPeopleCount(prompt: string) {
  const explicit = prompt.match(/\b(?:count|top|find|return|show)\s+(\d{1,2})\b/i)?.[1];
  const loose = prompt.match(/\b(\d{1,2})\s+(?:people|contacts|leads|prospects)\b/i)?.[1];
  const parsed = Number(explicit ?? loose ?? 5);
  return Number.isFinite(parsed) ? Math.max(1, Math.min(10, Math.trunc(parsed))) : 5;
}

function normalizeOperation(value: unknown): PlannerOperation | null {
  if (!value || typeof value !== "object") return null;
  const op = value as Record<string, unknown>;
  const type = canonicalOperationType(stringOr(op.type, ""));
  if (type === "addNode") {
    const label = stringOr(op.label, "").trim();
    if (!label) return null;
    return {
      type,
      id: stringOr(op.id, "") || undefined,
      label: label.slice(0, 80),
      summary: stringOr(op.summary, "").slice(0, 360) || undefined,
      kind: stringOr(op.kind, "concept").slice(0, 24),
      source: stringOr(op.source, "ai").slice(0, 24),
      x: numberOr(op.x),
      y: numberOr(op.y),
      connectTo: stringOr(op.connectTo, "") || undefined,
      edgeLabel: stringOr(op.edgeLabel, "").slice(0, 60) || undefined,
    };
  }
  if (type === "updateNode") {
    const id = stringOr(op.id, "");
    if (!id) return null;
    return {
      type,
      id,
      label: stringOr(op.label, "").slice(0, 80) || undefined,
      summary: stringOr(op.summary, "").slice(0, 360) || undefined,
      kind: stringOr(op.kind, "").slice(0, 24) || undefined,
      source: stringOr(op.source, "").slice(0, 24) || undefined,
    };
  }
  if (type === "deleteNode") {
    const id = stringOr(op.id, "");
    return id ? { type, id } : null;
  }
  if (type === "addEdge") {
    const source = stringOr(op.source, "");
    const target = stringOr(op.target, "");
    if (!source || !target || source === target) return null;
    return {
      type,
      id: stringOr(op.id, "") || undefined,
      source,
      target,
      label: stringOr(op.label, "").slice(0, 60) || undefined,
    };
  }
  if (type === "deleteEdge") {
    const id = stringOr(op.id, "");
    return id ? { type, id } : null;
  }
  return null;
}

function nodeLikeToAddNode(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object") return null;
  const node = value as Record<string, unknown>;
  const data = node.data && typeof node.data === "object" ? (node.data as Record<string, unknown>) : {};
  const label = stringOr(node.label, "") || stringOr(data.label, "");
  if (!label) return null;
  return {
    type: "addNode",
    id: stringOr(node.id, ""),
    label,
    summary: stringOr(node.summary, "") || stringOr(data.summary, ""),
    kind: stringOr(node.kind, "") || stringOr(data.kind, "concept"),
    source: stringOr(node.source, "") || stringOr(data.source, "ai"),
    x: numberOr(node.x),
    y: numberOr(node.y),
    connectTo: stringOr(node.connectTo, ""),
    edgeLabel: stringOr(node.edgeLabel, ""),
  };
}

function edgeLikeToAddEdge(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object") return null;
  const edge = value as Record<string, unknown>;
  const source = stringOr(edge.source, "");
  const target = stringOr(edge.target, "");
  if (!source || !target || source === target) return null;
  return {
    type: "addEdge",
    id: stringOr(edge.id, ""),
    source,
    target,
    label: stringOr(edge.label, ""),
  };
}

function canonicalOperationType(type: string) {
  const key = type.trim().toLowerCase().replace(/[-_\s]/g, "");
  if (key === "addnode" || key === "createnode" || key === "insertnode") return "addNode";
  if (key === "updatenode" || key === "editnode" || key === "renamenode") return "updateNode";
  if (key === "deletenode" || key === "removenode") return "deleteNode";
  if (key === "addedge" || key === "createedge" || key === "connectnodes") return "addEdge";
  if (key === "deleteedge" || key === "removeedge") return "deleteEdge";
  return type;
}

function fallbackPlan(prompt: string, nodes: Array<Record<string, unknown>>): PlannerResult {
  const rootId = stringOr(nodes[0]?.id, "root");
  return {
    reply:
      "I could not reach the model backend, so I staged a local node. Once DeepSeek is configured, this same request will produce model-authored edits.",
    operations: [
      {
        type: "addNode",
        id: `local-${Date.now()}`,
        label: prompt.slice(0, 72),
        summary: "Local placeholder from the admin canvas while the model backend was unavailable.",
        kind: "question",
        source: "local",
        connectTo: rootId,
        edgeLabel: "asks",
      },
    ],
  };
}

function malformedJsonPlan(
  prompt: string,
  nodes: Array<Record<string, unknown>>,
  rawContent: string,
): PlannerResult {
  const rootId = stringOr(nodes[0]?.id, "root");
  return {
    reply:
      "DeepSeek responded, but its planner JSON was malformed after repair. I added a review node instead of applying unsafe edits.",
    operations: [
      {
        type: "addNode",
        id: `malformed-json-${Date.now()}`,
        label: "Malformed planner JSON",
        summary:
          `Request: ${prompt.slice(0, 180)}. Raw response preview: ${rawContent
            .replace(/\s+/g, " ")
            .slice(0, 160)}`,
        kind: "risk",
        source: "deepseek",
        connectTo: rootId,
        edgeLabel: "needs repair",
      },
    ],
  };
}

function compactNodes(items: unknown[]) {
  return items.slice(0, 80).map((item) => {
    const node = item && typeof item === "object" ? (item as MindNode) : {};
    const data = node.data && typeof node.data === "object" ? node.data : {};
    return {
      id: stringOr(node.id, ""),
      position: node.position,
      label: stringOr(data.label, ""),
      summary: stringOr(data.summary, "").slice(0, 420),
      kind: stringOr(data.kind, "concept"),
      source: stringOr(data.source, "manual"),
    };
  });
}

function compactEdges(items: unknown[]) {
  return items.slice(0, 120).map((item) => {
    const edge = item && typeof item === "object" ? (item as MindEdge) : {};
    return {
      id: stringOr(edge.id, ""),
      source: stringOr(edge.source, ""),
      target: stringOr(edge.target, ""),
      label: stringOr(edge.label, ""),
    };
  });
}

function compactHistory(items: unknown[]): ChatMessage[] {
  return items
    .slice(-8)
    .map((item) => (item && typeof item === "object" ? (item as Record<string, unknown>) : null))
    .filter((item): item is Record<string, unknown> => Boolean(item))
    .map((item): ChatMessage => {
      const role: ChatMessage["role"] =
        stringOr(item.role, "user") === "assistant" ? "assistant" : "user";
      return {
        role,
        content: stringOr(item.content, "").slice(0, 1200),
      };
    })
    .filter((item) => item.content);
}

function safeArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function stringOr(value: unknown, fallback: string) {
  return typeof value === "string" ? value : fallback;
}

function numberOr(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function isUuid(value: string) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
    value,
  );
}

function json(body: unknown, status: number, setCookie?: string) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
      ...(setCookie ? { "Set-Cookie": setCookie } : {}),
    },
  });
}
