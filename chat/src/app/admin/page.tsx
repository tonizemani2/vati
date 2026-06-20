"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  Controls,
  Handle,
  MiniMap,
  Panel,
  Position,
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  useEdgesState,
  useNodesState,
  MarkerType,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import {
  Brain,
  Database,
  Eraser,
  GitBranch,
  Loader2,
  LockKeyhole,
  MessageSquare,
  MousePointer2,
  Plus,
  Save,
  Search,
  Sparkles,
  Trash2,
  Users,
  X,
} from "lucide-react";
import { cn } from "@/lib/cn";

type NodeKind = "concept" | "evidence" | "forecast" | "tool" | "question" | "risk" | "action";
type NodeSource = "manual" | "ai" | "data" | "local" | "websets" | "deepseek";

type MindNodeData = {
  label: string;
  summary: string;
  kind: NodeKind;
  source: NodeSource;
  [key: string]: unknown;
};

type MindNode = Node<MindNodeData, "mind">;
type MindEdge = Edge<{ label?: string }>;

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  pending?: boolean;
  error?: boolean;
  tools?: string[];
};

const TOOL_LABELS: Record<string, string> = {
  ground_graph: "data layer",
  query_record: "scored record",
  find_people: "people finder",
  design_capture: "capture play",
};

type SavedMap = {
  id: string;
  title: string;
  nodes: MindNode[];
  edges: MindEdge[];
  updated_at?: string;
};

type WebsetsContact = {
  full_name: string;
  title: string;
  company: string;
  location: string;
  linkedin: string;
  email: string;
  phone: string;
};

type WebsetsResult = {
  webset_id: string;
  status: string;
  completed: boolean;
  contacts: WebsetsContact[];
  account_email?: string;
  credits?: number | null;
  item_count: number;
};

type PlannerOperation =
  | {
      type: "addNode";
      id?: string;
      label: string;
      summary?: string;
      kind?: NodeKind;
      source?: NodeSource;
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
      kind?: NodeKind;
      source?: NodeSource;
    }
  | { type: "deleteNode"; id: string }
  | { type: "addEdge"; id?: string; source: string; target: string; label?: string }
  | { type: "deleteEdge"; id: string };

const STORAGE_KEY = "vati-admin-mind-v1";

const KIND_STYLES: Record<NodeKind, { bg: string; border: string; ink: string }> = {
  concept: { bg: "#ffffff", border: "#d8d5cc", ink: "#1a1206" },
  evidence: { bg: "#f0f7f3", border: "#8cc5a5", ink: "#123025" },
  forecast: { bg: "#f2f1ff", border: "#a9a6ff", ink: "#24206f" },
  tool: { bg: "#eef6ff", border: "#8bbde8", ink: "#113047" },
  question: { bg: "#fff7ed", border: "#e8b46d", ink: "#40270d" },
  risk: { bg: "#fff0f0", border: "#e89a9a", ink: "#4a1111" },
  action: { bg: "#f6f6f6", border: "#a9a39b", ink: "#211b14" },
};

const STARTER_NODES: MindNode[] = [
  {
    id: "root",
    type: "mind",
    position: { x: 0, y: 0 },
    data: {
      label: "Vaticinus mind map",
      summary: "A private canvas for concepts, evidence, forecasts, tools, and actions.",
      kind: "concept",
      source: "manual",
    },
  },
  {
    id: "record",
    type: "mind",
    position: { x: 320, y: -140 },
    data: {
      label: "Forward record",
      summary: "Pull dated calls, probabilities, horizons, watch signals, and kill criteria.",
      kind: "forecast",
      source: "data",
    },
  },
  {
    id: "data-layer",
    type: "mind",
    position: { x: 320, y: 90 },
    data: {
      label: "Data layer",
      summary: "Ask the graph for entities, world-state facts, series, papers, patents, permits, and sources.",
      kind: "tool",
      source: "data",
    },
  },
];

const STARTER_EDGES: MindEdge[] = [
  makeEdge("root", "record", "queries"),
  makeEdge("root", "data-layer", "grounds"),
];

const PROMPTS = [
  "Map Time-to-Energize Truth into buyer, ledger, evidence, demotion, and next action.",
  "Make this map simpler. Keep only the load-bearing mechanism and the next action.",
  "Pull relevant forward calls from the record and connect them to this map.",
  "Find 5 quantitative researchers and forecasters at prediction markets, trading firms, or hedge funds.",
  "Show how this concept relates to pricing, policy, and supply elasticity.",
];

function MindNodeCard({ data, selected }: NodeProps<MindNode>) {
  const style = KIND_STYLES[data.kind] ?? KIND_STYLES.concept;
  return (
    <div
      className={cn(
        "w-[240px] rounded-[8px] border bg-white px-3 py-2 shadow-[0_8px_22px_rgba(12,11,16,0.08)] transition-transform",
        selected && "translate-y-[-1px] ring-2 ring-[var(--brand)]",
      )}
      style={{ background: style.bg, borderColor: style.border, color: style.ink }}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!h-2.5 !w-2.5 !border-2 !border-white !bg-[var(--brand)]"
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!h-2.5 !w-2.5 !border-2 !border-white !bg-[var(--brand)]"
      />
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 text-[13px] font-semibold leading-snug">{data.label}</div>
        <span className="shrink-0 rounded-[6px] border border-current/20 px-1.5 py-0.5 text-[10px] uppercase leading-none tracking-[0.08em] text-current/65">
          {data.kind}
        </span>
      </div>
      {data.summary ? (
        <p className="mt-1.5 line-clamp-4 text-[11.5px] leading-snug text-current/70">{data.summary}</p>
      ) : null}
      <div className="mt-2 text-[10px] uppercase tracking-[0.08em] text-current/45">{data.source}</div>
    </div>
  );
}

const NODE_TYPES = { mind: MindNodeCard };

export default function AdminMindPage() {
  return (
    <ReactFlowProvider>
      <AdminMindSurface nodeTypes={NODE_TYPES} />
    </ReactFlowProvider>
  );
}

function AdminMindSurface({ nodeTypes }: { nodeTypes: { mind: typeof MindNodeCard } }) {
  const [nodes, setNodes, onNodesChange] = useNodesState<MindNode>(STARTER_NODES);
  const [edges, setEdges, onEdgesChange] = useEdgesState<MindEdge>(STARTER_EDGES);
  const [title, setTitle] = useState("Private thinking canvas");
  const [mapId, setMapId] = useState(() => crypto.randomUUID());
  const [maps, setMaps] = useState<SavedMap[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "hello",
      role: "assistant",
      content:
        "Give me a topic, a database request, or an edit instruction. I will answer and change the map.",
    },
  ]);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState<"loading" | "ready" | "locked" | "error">("loading");
  const [pin, setPin] = useState("");
  const [pinError, setPinError] = useState("");
  const [pinSubmitting, setPinSubmitting] = useState(false);
  const [dbReady, setDbReady] = useState(false);
  const [saving, setSaving] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [deepData, setDeepData] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [sideTab, setSideTab] = useState<"chat" | "inspect" | "tools" | "maps">("chat");
  const [lastDataLayer, setLastDataLayer] = useState<string | null>(null);
  const [websetsQuery, setWebsetsQuery] = useState(
    "Quantitative researchers and forecasters working at prediction market companies, trading firms, or hedge funds in the US or Europe",
  );
  const [websetsCount, setWebsetsCount] = useState(5);
  const [websetsResult, setWebsetsResult] = useState<WebsetsResult | null>(null);
  const [websetsStatus, setWebsetsStatus] = useState<"idle" | "running" | "done" | "error">("idle");
  const [websetsError, setWebsetsError] = useState("");
  const [hydrated, setHydrated] = useState(false);

  const nodesRef = useRef(nodes);
  const edgesRef = useRef(edges);
  const messagesRef = useRef(messages);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    nodesRef.current = nodes;
  }, [nodes]);

  useEffect(() => {
    edgesRef.current = edges;
  }, [edges]);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    const saved = readLocalState();
    if (saved) {
      setTitle(saved.title);
      setMapId(saved.mapId);
      setNodes(saved.nodes);
      setEdges(saved.edges);
      setMessages(saved.messages);
      setConversationId(saved.conversationId);
      setDeepData(saved.deepData);
    }
    setHydrated(true);

    loadAdminState();
  }, [setEdges, setNodes]);

  function loadAdminState() {
    setStatus("loading");
    fetch("/api/admin/mind")
      .then(async (res) => {
        if (res.status === 403 || res.status === 401) {
          setStatus("locked");
          return null;
        }
        const data = await res.json();
        if (data?.ok) {
          setMaps(normalizeMaps(data.maps));
          setDbReady(Boolean(data.db));
          setStatus("ready");
        } else {
          setStatus("error");
        }
        return null;
      })
      .catch(() => setStatus("error"));
  }

  async function submitPin(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setPinSubmitting(true);
    setPinError("");
    try {
      const res = await fetch("/api/admin/pin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.ok) {
        throw new Error(typeof data?.error === "string" ? data.error : "wrong pin");
      }
      setPin("");
      loadAdminState();
    } catch (err) {
      setPinError(err instanceof Error ? err.message : "wrong pin");
    } finally {
      setPinSubmitting(false);
    }
  }

  useEffect(() => {
    if (!hydrated) return;
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        title,
        mapId,
        nodes,
        edges,
        messages,
        conversationId,
        deepData,
      }),
    );
  }, [conversationId, deepData, edges, hydrated, mapId, messages, nodes, title]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  const selectedNode = nodes.find((node) => node.selected);
  const selectedIds = useMemo(() => new Set(nodes.filter((node) => node.selected).map((node) => node.id)), [nodes]);
  const selectedEdges = useMemo(() => edges.filter((edge) => edge.selected), [edges]);

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((current) =>
        addEdge(
          {
            ...connection,
            id: `edge-${connection.source}-${connection.target}-${Date.now()}`,
            markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18 },
            style: { strokeWidth: 1.8, stroke: "#6d6afc" },
          },
          current,
        ),
      );
    },
    [setEdges],
  );

  function addManualNode() {
    const anchor = selectedNode ?? nodes[0];
    const id = `manual-${Date.now()}`;
    const next: MindNode = {
      id,
      type: "mind",
      position: {
        x: (anchor?.position.x ?? 0) + 320,
        y: (anchor?.position.y ?? 0) + 220,
      },
      data: {
        label: "New thought",
        summary: "Edit this node in the inspector.",
        kind: "concept",
        source: "manual",
      },
      selected: true,
    };
    setNodes((current) => [
      ...current.map((node): MindNode => ({ ...node, selected: false })),
      next,
    ]);
    if (anchor) setEdges((current) => current.concat(makeEdge(anchor.id, id, "relates")));
    setSideTab("inspect");
  }

  function deleteSelection() {
    if (!selectedIds.size && !selectedEdges.length) return;
    setNodes((current) => current.filter((node) => !selectedIds.has(node.id)));
    setEdges((current) =>
      current.filter(
        (edge) =>
          !edge.selected &&
          !selectedIds.has(edge.source) &&
          !selectedIds.has(edge.target),
      ),
    );
  }

  function updateSelected(patch: Partial<MindNodeData>) {
    if (!selectedNode) return;
    setNodes((current) =>
      current.map((node) =>
        node.id === selectedNode.id
          ? { ...node, data: { ...node.data, ...patch } }
          : node,
      ),
    );
  }

  function newSlate() {
    if (!window.confirm("Clear the current canvas and local chat?")) return;
    const nextId = crypto.randomUUID();
    setTitle("Private thinking canvas");
    setMapId(nextId);
    setNodes(STARTER_NODES);
    setEdges(STARTER_EDGES);
    setMessages([
      {
        id: `msg-${Date.now()}`,
        role: "assistant",
        content: "Fresh canvas. Give me a topic or tell me what to build.",
      },
    ]);
    setConversationId(null);
    setLastDataLayer(null);
  }

  async function saveMap() {
    setSaving(true);
    try {
      const res = await fetch("/api/admin/mind", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "save_map",
          map_id: mapId,
          title,
          nodes: nodesRef.current,
          edges: edgesRef.current,
        }),
      });
      const data = await res.json();
      if (data?.maps) setMaps(normalizeMaps(data.maps));
      setDbReady(Boolean(data?.db));
      pushAssistant(data?.saved ? "Saved to the account map store." : "Saved locally. Database storage is not configured.");
    } catch {
      pushAssistant("Save failed. Your browser still has the local copy.");
    } finally {
      setSaving(false);
    }
  }

  async function deleteCurrentMap() {
    if (!window.confirm("Delete this saved map? The local canvas will stay open.")) return;
    try {
      const res = await fetch("/api/admin/mind", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "delete_map", map_id: mapId }),
      });
      const data = await res.json();
      if (data?.maps) setMaps(normalizeMaps(data.maps));
      pushAssistant(data?.deleted ? "Deleted the saved copy." : "No saved copy was deleted.");
    } catch {
      pushAssistant("Delete failed.");
    }
  }

  function loadMap(map: SavedMap) {
    setMapId(map.id);
    setTitle(map.title);
    setNodes(normalizeNodes(map.nodes));
    setEdges(normalizeEdges(map.edges));
    setSideTab("chat");
    pushAssistant(`Loaded "${map.title}".`);
  }

  async function deleteChat() {
    if (!window.confirm("Clear this admin chat?")) return;
    if (conversationId) {
      fetch(`/api/conversations?id=${encodeURIComponent(conversationId)}`, { method: "DELETE" }).catch(() => {});
    }
    setConversationId(null);
    setMessages([
      {
        id: `msg-${Date.now()}`,
        role: "assistant",
        content: "Chat cleared. The canvas is unchanged.",
      },
    ]);
  }

  function pushAssistant(content: string) {
    setMessages((current) =>
      current.concat({ id: `assistant-${Date.now()}`, role: "assistant", content }),
    );
  }

  async function sendPrompt(prompt = input.trim()) {
    if (!prompt || streaming) return;
    const userMsg: ChatMessage = { id: `user-${Date.now()}`, role: "user", content: prompt };
    const pendingId = `assistant-${Date.now() + 1}`;
    const outgoing = messagesRef.current.concat(userMsg).map(({ role, content }) => ({ role, content }));
    setMessages((current) =>
      current.concat(userMsg, {
        id: pendingId,
        role: "assistant",
        content: "Thinking through the map...",
        pending: true,
      }),
    );
    setInput("");
    setStreaming(true);
    try {
      const res = await fetch("/api/admin/mind", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "chat",
          prompt,
          messages: outgoing,
          nodes: nodesRef.current,
          edges: edgesRef.current,
          conversation_id: conversationId,
          map_id: mapId,
          deep_data: deepData,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.ok) {
        const err = typeof data?.error === "string" ? data.error : "admin agent failed";
        throw new Error(err);
      }

      const plan = data.plan ?? {};
      if (typeof plan.mapTitle === "string" && plan.mapTitle.trim()) {
        setTitle(plan.mapTitle.trim());
      }
      if (Array.isArray(plan.operations)) {
        const next = applyOperations(nodesRef.current, edgesRef.current, plan.operations);
        setNodes(next.nodes);
        setEdges(next.edges);
      }
      if (typeof data.conversation_id === "string") setConversationId(data.conversation_id);
      if (data.data_layer?.answer) setLastDataLayer(data.data_layer.answer);
      if (data.people_tool?.summary) {
        const summary = String(data.people_tool.summary);
        setWebsetsResult(data.people_tool.result ?? null);
        if (data.people_tool.result?.contacts?.length) {
          addWebsetsResultToMap(data.people_tool.result, prompt);
        }
        if (summary) setLastDataLayer(summary);
      }
      const toolsUsed = Array.isArray(data.tools_used)
        ? (data.tools_used as unknown[]).filter((t): t is string => typeof t === "string")
        : [];
      setMessages((current) =>
        current.map((msg) =>
          msg.id === pendingId
            ? {
                ...msg,
                pending: false,
                content: typeof plan.reply === "string" ? plan.reply : "Map updated.",
                tools: toolsUsed,
              }
            : msg,
        ),
      );
    } catch (e) {
      setMessages((current) =>
        current.map((msg) =>
          msg.id === pendingId
            ? {
                ...msg,
                pending: false,
                error: true,
                content: e instanceof Error ? e.message : "admin agent failed",
              }
            : msg,
        ),
      );
    } finally {
      setStreaming(false);
    }
  }

  async function runWebsetsSearch() {
    if (!websetsQuery.trim() || websetsStatus === "running") return;
    setWebsetsStatus("running");
    setWebsetsError("");
    setWebsetsResult(null);
    try {
      const res = await fetch("/api/admin/websets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "search",
          query: websetsQuery.trim(),
          entity: "person",
          count: websetsCount,
          wait_ms: 0,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.ok) throw new Error(typeof data?.error === "string" ? data.error : "websets failed");
      const started = normalizeWebsetsResult(data.result);
      setWebsetsResult(started);
      if (started?.contacts?.length) {
        setWebsetsStatus("done");
        addWebsetsResultToMap(started, websetsQuery.trim());
        pushAssistant(`Websets returned ${started.contacts.length} people and added them to the canvas.`);
      } else {
        pushAssistant(`Websets search started as ${started?.webset_id ?? "a webset"}. I will poll for completed contacts.`);
        if (started?.webset_id) await pollWebsetsResult(started.webset_id, websetsQuery.trim());
      }
    } catch (e) {
      setWebsetsStatus("error");
      setWebsetsError(e instanceof Error ? e.message : "websets failed");
    }
  }

  async function pollWebsetsResult(websetId: string, query: string) {
    for (let attempt = 0; attempt < 42; attempt += 1) {
      await sleep(10000);
      const res = await fetch("/api/admin/websets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "status", webset_id: websetId }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.ok) continue;
      const result = normalizeWebsetsResult(data.result);
      if (!result) continue;
      setWebsetsResult((current) => ({ ...(current ?? result), ...result }));
      if (result.contacts.length || result.completed) {
        setWebsetsStatus("done");
        if (result.contacts.length) {
          addWebsetsResultToMap(result, query);
          pushAssistant(`Websets returned ${result.contacts.length} people and added them to the canvas.`);
        } else {
          pushAssistant("Websets finished but did not return contacts for that criteria.");
        }
        return;
      }
    }
    setWebsetsStatus("idle");
    pushAssistant("Websets is still running. Open Tools and poll again later with the webset id.");
  }

  function addWebsetsResultToMap(result: WebsetsResult, query: string) {
    const root = nodesRef.current.find((node) => node.id === "root") ?? nodesRef.current[0];
    const searchId = uniqueNodeId(`websets-${result.webset_id || Date.now()}`, nodesRef.current);
    const searchNode: MindNode = {
      id: searchId,
      type: "mind",
      position: { x: (root?.position.x ?? 0) + 360, y: (root?.position.y ?? 0) + 260 },
      data: {
        label: "Websets people search",
        summary: query,
        kind: "tool",
        source: "websets",
      },
    };
    const personNodes = result.contacts.slice(0, 8).map((contact, index): MindNode => ({
      id: uniqueNodeId(`${contact.full_name || "person"}-${index}`, nodesRef.current.concat(searchNode)),
      type: "mind",
      position: {
        x: searchNode.position.x + 320,
        y: searchNode.position.y + (index - Math.min(result.contacts.length, 8) / 2) * 116,
      },
      data: {
        label: contact.full_name || "Unnamed person",
        summary: [contact.title, contact.company, contact.location, contact.email, contact.linkedin]
          .filter(Boolean)
          .join(" | "),
        kind: contact.email || contact.linkedin ? "evidence" : "question",
        source: "websets",
      },
    }));
    const nextEdges = [
      ...(root ? [makeEdge(root.id, searchId, "searched")] : []),
      ...personNodes.map((node) => makeEdge(searchId, node.id, "found")),
    ];
    setNodes((current) => current.concat(searchNode, personNodes));
    setEdges((current) => dedupeEdges(current.concat(nextEdges)));
  }

  if (status === "loading") {
    return (
      <main className="flex min-h-[100dvh] items-center justify-center bg-[#f5f4f0] text-[var(--ink)]">
        <div className="flex items-center gap-3 rounded-[8px] border border-[var(--border-faint)] bg-white px-4 py-3 text-sm shadow-sm">
          <Loader2 className="animate-spin text-[var(--brand)]" size={18} />
          Opening private canvas
        </div>
      </main>
    );
  }

  if (status === "locked") {
    return (
      <main className="flex min-h-[100dvh] items-center justify-center bg-[#f5f4f0] px-4 text-[var(--ink)]">
        <form
          onSubmit={submitPin}
          className="w-full max-w-[380px] rounded-[8px] border border-[var(--border-faint)] bg-white p-5 text-center shadow-sm"
        >
          <LockKeyhole className="mx-auto text-[var(--brand)]" size={26} />
          <h1 className="mt-3 text-xl font-semibold">Admin PIN required</h1>
          <p className="mt-2 text-sm leading-6 text-[var(--ink-muted)]">
            This canvas can read private tools and model state, so it opens behind the private PIN.
          </p>
          <input
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            inputMode="numeric"
            autoComplete="one-time-code"
            className="mt-4 h-11 w-full rounded-[8px] border border-[var(--border-faint)] bg-white px-3 text-center text-lg font-semibold tracking-[0.18em] outline-none focus:border-[var(--brand)]"
            placeholder="PIN"
            aria-label="Admin PIN"
          />
          {pinError ? <div className="mt-2 text-sm text-[#8b1d1d]">{pinError}</div> : null}
          <button
            type="submit"
            disabled={pinSubmitting || !pin.trim()}
            className="mt-4 inline-flex h-10 w-full items-center justify-center gap-2 rounded-[8px] bg-[var(--brand)] px-4 text-sm font-semibold text-white disabled:opacity-45"
          >
            {pinSubmitting ? <Loader2 size={16} className="animate-spin" /> : <LockKeyhole size={16} />}
            Unlock canvas
          </button>
        </form>
      </main>
    );
  }

  return (
    <main className="min-h-[100dvh] bg-[#f5f4f0] text-[var(--ink)]">
      <header className="border-b border-[var(--border-faint)] bg-[#faf9f7]/95 px-3 py-3 backdrop-blur md:px-5">
        <div className="mx-auto flex max-w-[1680px] flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-[0.12em] text-[var(--ink-muted)]">
              <Brain size={15} strokeWidth={1.8} />
              Admin mind map
            </div>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="mt-1 w-full bg-transparent text-[22px] font-semibold leading-tight outline-none md:text-[26px]"
              aria-label="Map title"
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <ToolbarButton icon={Plus} label="Add node" onClick={addManualNode} />
            <ToolbarButton
              icon={Trash2}
              label="Delete"
              onClick={deleteSelection}
              disabled={!selectedIds.size && !selectedEdges.length}
            />
            <ToolbarButton icon={Eraser} label="New slate" onClick={newSlate} />
            <ToolbarButton icon={Save} label={saving ? "Saving" : "Save"} onClick={saveMap} disabled={saving} />
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1680px] grid-cols-1 gap-3 px-3 py-3 lg:grid-cols-[minmax(0,1fr)_390px] md:px-5">
        <section className="h-[62dvh] min-h-[460px] overflow-hidden rounded-[8px] border border-[var(--border-faint)] bg-[#fbfaf8] shadow-sm lg:h-[calc(100dvh-118px)]">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            fitView
            fitViewOptions={{ padding: 0.28 }}
            minZoom={0.18}
            maxZoom={1.7}
            nodesDraggable
            nodesConnectable
            deleteKeyCode={["Backspace", "Delete"]}
            proOptions={{ hideAttribution: true }}
          >
            <Background color="#d8d5cc" gap={22} size={1} />
            <Controls showInteractive={false} />
            <MiniMap
              pannable
              zoomable
              className="!bg-white/90"
              nodeColor={(node) => KIND_STYLES[(node.data as MindNodeData).kind]?.border ?? "#d8d5cc"}
            />
            <Panel position="top-left">
              <div className="flex flex-wrap items-center gap-2 rounded-[8px] border border-[var(--border-faint)] bg-white/95 px-2 py-2 text-[12px] shadow-sm">
                <span className="flex items-center gap-1.5 text-[var(--ink-muted)]">
                  <MousePointer2 size={14} />
                  Drag nodes
                </span>
                <span className="flex items-center gap-1.5 text-[var(--ink-muted)]">
                  <GitBranch size={14} />
                  Connect handles
                </span>
                <span className="flex items-center gap-1.5 text-[var(--ink-muted)]">
                  <Database size={14} />
                  {dbReady ? "Account save on" : "Local save on"}
                </span>
              </div>
            </Panel>
          </ReactFlow>
        </section>

        <aside className="flex min-h-[520px] flex-col overflow-hidden rounded-[8px] border border-[var(--border-faint)] bg-white shadow-sm lg:h-[calc(100dvh-118px)]">
          <div className="grid grid-cols-4 border-b border-[var(--border-faint)] p-1">
            <TabButton label="Chat" active={sideTab === "chat"} onClick={() => setSideTab("chat")} />
            <TabButton label="Inspect" active={sideTab === "inspect"} onClick={() => setSideTab("inspect")} />
            <TabButton label="Tools" active={sideTab === "tools"} onClick={() => setSideTab("tools")} />
            <TabButton label="Maps" active={sideTab === "maps"} onClick={() => setSideTab("maps")} />
          </div>

          {sideTab === "chat" ? (
            <div className="flex min-h-0 flex-1 flex-col">
              <div className="thin-scroll min-h-0 flex-1 overflow-y-auto px-3 py-3">
                <div className="mb-3 grid gap-2">
                  {PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      onClick={() => sendPrompt(prompt)}
                      className="rounded-[8px] border border-[var(--border-faint)] bg-[#faf9f7] px-3 py-2 text-left text-[12.5px] leading-5 text-[var(--ink)] transition-colors hover:bg-[#f2f1ff]"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>

                <div className="space-y-3">
                  {messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={cn(
                        "rounded-[8px] px-3 py-2 text-[13px] leading-5",
                        msg.role === "user"
                          ? "ml-7 bg-[var(--brand)] text-white"
                          : "mr-7 border border-[var(--border-faint)] bg-[#faf9f7] text-[var(--ink)]",
                        msg.error && "border-[#e89a9a] bg-[#fff0f0] text-[#4a1111]",
                      )}
                    >
                      <div className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] opacity-60">
                        {msg.pending ? <Loader2 size={12} className="animate-spin" /> : <MessageSquare size={12} />}
                        {msg.role === "user" ? "You" : "Hermes"}
                      </div>
                      {msg.content}
                      {msg.tools && msg.tools.length ? (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {msg.tools.map((tool, i) => (
                            <span
                              key={`${msg.id}-tool-${i}`}
                              className="inline-flex items-center rounded-[6px] border border-[#8bbde8] bg-[#eef6ff] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.06em] text-[#113047]"
                            >
                              {TOOL_LABELS[tool] ?? tool}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ))}
                  <div ref={chatEndRef} />
                </div>
              </div>

              {lastDataLayer ? (
                <div className="border-t border-[var(--border-faint)] bg-[#f7fbff] px-3 py-2 text-[12px] leading-5 text-[#113047]">
                  <div className="mb-1 font-semibold">Latest tool pack</div>
                  <div className="line-clamp-3">{lastDataLayer}</div>
                </div>
              ) : null}

              <form
                className="border-t border-[var(--border-faint)] p-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  sendPrompt();
                }}
              >
                <label className="mb-2 flex items-center justify-between gap-2 text-[12px] font-medium text-[var(--ink-muted)]">
                  <span>Ask or edit the canvas</span>
                  <button
                    type="button"
                    onClick={() => setDeepData((value) => !value)}
                    className={cn(
                      "rounded-[999px] border px-2 py-1 text-[11px]",
                      deepData
                        ? "border-[var(--brand)] bg-[#f2f1ff] text-[var(--brand-600)]"
                        : "border-[var(--border-faint)] text-[var(--ink-muted)]",
                    )}
                  >
                    {deepData ? "Deep data on" : "Fast data"}
                  </button>
                </label>
                <div className="flex gap-2">
                  <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Ask for a concept map, simplify, connect ideas, or pull from the record."
                    rows={3}
                    className="min-h-[72px] flex-1 resize-none rounded-[8px] border border-[var(--border-faint)] bg-white px-3 py-2 text-[14px] leading-5 outline-none focus:border-[var(--brand)]"
                  />
                  <button
                    type="submit"
                    disabled={streaming || !input.trim()}
                    className="flex w-11 shrink-0 items-center justify-center rounded-[8px] bg-[var(--brand)] text-white transition-opacity disabled:opacity-45"
                    aria-label="Send"
                    title="Send"
                  >
                    {streaming ? <Loader2 size={18} className="animate-spin" /> : <Sparkles size={18} />}
                  </button>
                </div>
                <button
                  type="button"
                  onClick={deleteChat}
                  className="mt-2 inline-flex items-center gap-1.5 text-[12px] text-[var(--ink-muted)] hover:text-[var(--ink)]"
                >
                  <X size={13} />
                  Clear chat
                </button>
              </form>
            </div>
          ) : null}

          {sideTab === "inspect" ? (
            <div className="thin-scroll min-h-0 flex-1 overflow-y-auto p-3">
              {selectedNode ? (
                <div className="grid gap-3">
                  <Field label="Label">
                    <input
                      value={selectedNode.data.label}
                      onChange={(e) => updateSelected({ label: e.target.value })}
                      className="input"
                    />
                  </Field>
                  <Field label="Summary">
                    <textarea
                      value={selectedNode.data.summary}
                      onChange={(e) => updateSelected({ summary: e.target.value })}
                      rows={5}
                      className="input resize-none"
                    />
                  </Field>
                  <Field label="Kind">
                    <select
                      value={selectedNode.data.kind}
                      onChange={(e) => updateSelected({ kind: e.target.value as NodeKind })}
                      className="input"
                    >
                      {Object.keys(KIND_STYLES).map((kind) => (
                        <option key={kind} value={kind}>
                          {kind}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <div className="rounded-[8px] border border-[var(--border-faint)] bg-[#faf9f7] p-3 text-[12px] leading-5 text-[var(--ink-muted)]">
                    Node id: <span className="font-mono text-[var(--ink)]">{selectedNode.id}</span>
                  </div>
                </div>
              ) : (
                <div className="rounded-[8px] border border-dashed border-[var(--border-faint)] p-4 text-sm leading-6 text-[var(--ink-muted)]">
                  Select a node to edit its label, summary, and type.
                </div>
              )}
            </div>
          ) : null}

          {sideTab === "tools" ? (
            <div className="thin-scroll min-h-0 flex-1 overflow-y-auto p-3">
              <div className="mb-3 rounded-[8px] border border-[var(--border-faint)] bg-[#faf9f7] p-3 text-[12px] leading-5 text-[var(--ink-muted)]">
                <div className="flex items-center gap-2 font-semibold text-[var(--ink)]">
                  <Users size={15} />
                  Websets people finder
                </div>
                <div className="mt-1">Runs Exa Websets and drops completed contacts onto the canvas.</div>
              </div>
              <div className="grid gap-3">
                <Field label="Criteria">
                  <textarea
                    value={websetsQuery}
                    onChange={(e) => setWebsetsQuery(e.target.value)}
                    rows={5}
                    className="input resize-none"
                  />
                </Field>
                <Field label="Count">
                  <input
                    type="number"
                    min={1}
                    max={10}
                    value={websetsCount}
                    onChange={(e) => setWebsetsCount(Math.max(1, Math.min(10, Number(e.target.value) || 1)))}
                    className="input"
                  />
                </Field>
                <button
                  type="button"
                  onClick={runWebsetsSearch}
                  disabled={websetsStatus === "running" || !websetsQuery.trim()}
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-[8px] bg-[var(--brand)] px-3 text-sm font-semibold text-white disabled:opacity-45"
                >
                  {websetsStatus === "running" ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
                  Run search
                </button>
                {websetsError ? (
                  <div className="rounded-[8px] border border-[#e89a9a] bg-[#fff0f0] p-3 text-[12px] leading-5 text-[#4a1111]">
                    {websetsError}
                  </div>
                ) : null}
                {websetsResult ? (
                  <div className="rounded-[8px] border border-[var(--border-faint)] bg-white p-3">
                    <div className="text-[12px] font-semibold text-[var(--ink)]">
                      {websetsResult.completed ? `${websetsResult.contacts.length} people found` : `Webset ${websetsResult.status}`}
                    </div>
                    <div className="mt-1 text-[11px] text-[var(--ink-muted)]">
                      {websetsResult.webset_id}
                      {typeof websetsResult.credits === "number" ? ` | ${websetsResult.credits} credits` : ""}
                    </div>
                    <div className="mt-3 grid gap-2">
                      {websetsResult.contacts.slice(0, 8).map((contact) => (
                        <div
                          key={`${contact.full_name}-${contact.company}-${contact.email}`}
                          className="rounded-[8px] border border-[var(--border-faint)] bg-[#faf9f7] p-2 text-[12px] leading-5"
                        >
                          <div className="font-semibold text-[var(--ink)]">{contact.full_name || "Unnamed person"}</div>
                          <div className="text-[var(--ink-muted)]">
                            {[contact.title, contact.company, contact.location].filter(Boolean).join(" | ")}
                          </div>
                          {contact.email || contact.linkedin ? (
                            <div className="mt-1 break-words text-[11px] text-[var(--ink-muted)]">
                              {[contact.email, contact.linkedin].filter(Boolean).join(" | ")}
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          ) : null}

          {sideTab === "maps" ? (
            <div className="thin-scroll min-h-0 flex-1 overflow-y-auto p-3">
              <div className="mb-3 rounded-[8px] border border-[var(--border-faint)] bg-[#faf9f7] p-3 text-[12px] leading-5 text-[var(--ink-muted)]">
                {dbReady
                  ? "Saved maps are tied to the verified owner account."
                  : "No database store is configured. Your browser local copy is still active."}
              </div>
              <div className="grid gap-2">
                {maps.length ? (
                  maps.map((map) => (
                    <button
                      key={map.id}
                      onClick={() => loadMap(map)}
                      className={cn(
                        "rounded-[8px] border px-3 py-2 text-left text-sm transition-colors",
                        map.id === mapId
                          ? "border-[var(--brand)] bg-[#f2f1ff]"
                          : "border-[var(--border-faint)] bg-white hover:bg-[#faf9f7]",
                      )}
                    >
                      <div className="font-semibold">{map.title}</div>
                      <div className="mt-1 text-[12px] text-[var(--ink-muted)]">
                        {map.nodes.length} nodes, {map.edges.length} edges
                      </div>
                    </button>
                  ))
                ) : (
                  <div className="rounded-[8px] border border-dashed border-[var(--border-faint)] p-4 text-sm text-[var(--ink-muted)]">
                    No saved account maps yet.
                  </div>
                )}
              </div>
              <button
                type="button"
                onClick={deleteCurrentMap}
                className="mt-3 inline-flex items-center gap-1.5 text-[12px] text-[#8b1d1d] hover:text-[#4a1111]"
              >
                <Trash2 size={13} />
                Delete saved copy
              </button>
            </div>
          ) : null}
        </aside>
      </div>
    </main>
  );
}

function ToolbarButton({
  icon: Icon,
  label,
  onClick,
  disabled,
}: {
  icon: React.ComponentType<{ size?: number; strokeWidth?: number; className?: string }>;
  label: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex h-9 items-center gap-2 rounded-[8px] border border-[var(--border-faint)] bg-white px-3 text-[13px] font-medium text-[var(--ink)] shadow-sm transition-colors hover:bg-[#faf9f7] disabled:cursor-not-allowed disabled:opacity-45"
    >
      <Icon size={16} strokeWidth={1.8} />
      {label}
    </button>
  );
}

function TabButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "h-8 rounded-[7px] text-[13px] font-medium transition-colors",
        active ? "bg-[var(--ink)] text-white" : "text-[var(--ink-muted)] hover:bg-[#faf9f7]",
      )}
    >
      {label}
    </button>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="grid gap-1.5 text-[12px] font-medium text-[var(--ink-muted)]">
      {label}
      {children}
    </label>
  );
}

function makeEdge(source: string, target: string, label?: string): MindEdge {
  return {
    id: `edge-${source}-${target}-${label ?? "link"}`.replace(/[^a-zA-Z0-9_-]/g, "-"),
    source,
    target,
    label,
    markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18 },
    style: { strokeWidth: 1.8, stroke: "#6d6afc" },
    labelStyle: { fill: "#6f6a63", fontSize: 11, fontWeight: 600 },
    labelBgStyle: { fill: "#faf9f7", fillOpacity: 0.92 },
  };
}

function applyOperations(nodes: MindNode[], edges: MindEdge[], operations: PlannerOperation[]) {
  let nextNodes: MindNode[] = nodes.map((node): MindNode => ({ ...node, selected: false }));
  let nextEdges: MindEdge[] = edges.map((edge): MindEdge => ({ ...edge, selected: false }));

  for (const op of operations) {
    if (op.type === "addNode") {
      const id = uniqueNodeId(op.id || slug(op.label), nextNodes);
      const anchor = nextNodes.find((node) => node.id === op.connectTo) ?? nextNodes[0];
      const index = nextNodes.length;
      const node: MindNode = {
        id,
        type: "mind",
        position: {
          x: typeof op.x === "number" ? op.x : (anchor?.position.x ?? 0) + 280 + (index % 3) * 34,
          y: typeof op.y === "number" ? op.y : (anchor?.position.y ?? 0) + ((index % 5) - 2) * 96,
        },
        data: {
          label: op.label,
          summary: op.summary ?? "",
          kind: normalizeKind(op.kind),
          source: normalizeSource(op.source),
        },
        selected: true,
      };
      nextNodes = nextNodes.concat(node);
      if (op.connectTo && nextNodes.some((existing) => existing.id === op.connectTo)) {
        nextEdges = nextEdges.concat(makeEdge(op.connectTo, id, op.edgeLabel || "relates"));
      }
      continue;
    }

    if (op.type === "updateNode") {
      nextNodes = nextNodes.map((node) =>
        node.id === op.id
          ? {
              ...node,
              data: {
                ...node.data,
                ...(op.label ? { label: op.label } : {}),
                ...(op.summary ? { summary: op.summary } : {}),
                ...(op.kind ? { kind: normalizeKind(op.kind) } : {}),
                ...(op.source ? { source: normalizeSource(op.source) } : {}),
              },
            }
          : node,
      );
      continue;
    }

    if (op.type === "deleteNode") {
      nextNodes = nextNodes.filter((node) => node.id !== op.id);
      nextEdges = nextEdges.filter((edge) => edge.source !== op.id && edge.target !== op.id);
      continue;
    }

    if (op.type === "addEdge") {
      const exists =
        nextNodes.some((node) => node.id === op.source) &&
        nextNodes.some((node) => node.id === op.target);
      if (exists) nextEdges = nextEdges.concat({ ...makeEdge(op.source, op.target, op.label), id: op.id || makeEdge(op.source, op.target, op.label).id });
      continue;
    }

    if (op.type === "deleteEdge") {
      nextEdges = nextEdges.filter((edge) => edge.id !== op.id);
    }
  }

  return { nodes: nextNodes, edges: dedupeEdges(nextEdges) };
}

function normalizeKind(kind: unknown): NodeKind {
  return typeof kind === "string" && kind in KIND_STYLES ? (kind as NodeKind) : "concept";
}

function normalizeSource(source: unknown): NodeSource {
  return source === "ai" || source === "data" || source === "local" || source === "websets" || source === "deepseek"
    ? source
    : "manual";
}

function normalizeWebsetsResult(value: unknown): WebsetsResult | null {
  if (!value || typeof value !== "object") return null;
  const result = value as Partial<WebsetsResult>;
  return {
    webset_id: typeof result.webset_id === "string" ? result.webset_id : "",
    status: typeof result.status === "string" ? result.status : "unknown",
    completed: result.completed === true,
    contacts: Array.isArray(result.contacts) ? result.contacts : [],
    account_email: typeof result.account_email === "string" ? result.account_email : undefined,
    credits: typeof result.credits === "number" ? result.credits : null,
    item_count: typeof result.item_count === "number" ? result.item_count : Array.isArray(result.contacts) ? result.contacts.length : 0,
  };
}

function uniqueNodeId(base: string, nodes: MindNode[]) {
  const taken = new Set(nodes.map((node) => node.id));
  let candidate = slug(base) || `node-${Date.now()}`;
  let i = 2;
  while (taken.has(candidate)) candidate = `${slug(base)}-${i++}`;
  return candidate;
}

function slug(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 54);
}

function dedupeEdges(edges: MindEdge[]) {
  const seen = new Set<string>();
  return edges.filter((edge) => {
    const key = `${edge.source}->${edge.target}:${edge.label ?? ""}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function normalizeNodes(raw: unknown): MindNode[] {
  if (!Array.isArray(raw)) return STARTER_NODES;
  return raw
    .map((node) => {
      if (!node || typeof node !== "object") return null;
      const n = node as Partial<MindNode>;
      const data = n.data ?? ({} as Partial<MindNodeData>);
      if (!n.id || typeof n.id !== "string") return null;
      return {
        ...n,
        id: n.id,
        type: "mind",
        position: n.position ?? { x: 0, y: 0 },
        data: {
          label: typeof data.label === "string" ? data.label : "Untitled",
          summary: typeof data.summary === "string" ? data.summary : "",
          kind: normalizeKind(data.kind),
          source: normalizeSource(data.source),
        },
      } as MindNode;
    })
    .filter((node): node is MindNode => Boolean(node));
}

function normalizeEdges(raw: unknown): MindEdge[] {
  if (!Array.isArray(raw)) return STARTER_EDGES;
  return raw
    .map((edge) => {
      if (!edge || typeof edge !== "object") return null;
      const e = edge as Partial<MindEdge>;
      if (!e.source || !e.target) return null;
      return {
        ...makeEdge(String(e.source), String(e.target), typeof e.label === "string" ? e.label : undefined),
        id: typeof e.id === "string" ? e.id : `edge-${e.source}-${e.target}`,
      };
    })
    .filter((edge): edge is MindEdge => Boolean(edge));
}

function normalizeMaps(raw: unknown): SavedMap[] {
  if (!Array.isArray(raw)) return [];
  const maps: SavedMap[] = [];
  for (const map of raw) {
    if (!map || typeof map !== "object") continue;
    const m = map as Partial<SavedMap>;
    if (!m.id || !m.title) continue;
    const saved: SavedMap = {
      id: String(m.id),
      title: String(m.title),
      nodes: normalizeNodes(m.nodes),
      edges: normalizeEdges(m.edges),
    };
    if (typeof m.updated_at === "string") saved.updated_at = m.updated_at;
    maps.push(saved);
  }
  return maps;
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function readLocalState():
  | {
      title: string;
      mapId: string;
      nodes: MindNode[];
      edges: MindEdge[];
      messages: ChatMessage[];
      conversationId: string | null;
      deepData: boolean;
    }
  | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    return {
      title: typeof parsed.title === "string" ? parsed.title : "Private thinking canvas",
      mapId: typeof parsed.mapId === "string" ? parsed.mapId : crypto.randomUUID(),
      nodes: normalizeNodes(parsed.nodes),
      edges: normalizeEdges(parsed.edges),
      messages: Array.isArray(parsed.messages)
        ? (parsed.messages as ChatMessage[]).filter(
            (msg) => msg && (msg.role === "user" || msg.role === "assistant") && typeof msg.content === "string",
          )
        : [],
      conversationId: typeof parsed.conversationId === "string" ? parsed.conversationId : null,
      deepData: parsed.deepData === true,
    };
  } catch {
    return null;
  }
}
