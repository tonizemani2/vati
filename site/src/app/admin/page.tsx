"use client";

import { useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { ArrowRight, BookOpenText, Layers, ListTree, LockKeyhole } from "lucide-react";
import data from "@/content/posts.json";

const CODE = "258036";
type VersionKey = "full" | "analyst" | "arrow";

type Post = {
  n: number;
  title: string;
  domain: string;
  resolves: string;
  odds: string;
  view: string;
  note: string;
  kill: string;
  watch: string;
};

const VERSION_OPTIONS = [
  {
    key: "full",
    label: "Full memo",
    note: "Source text",
    icon: BookOpenText,
  },
  {
    key: "analyst",
    label: "Analyst brief",
    note: "Middle version",
    icon: Layers,
  },
  {
    key: "arrow",
    label: "Arrow brief",
    note: "Shortest read",
    icon: ListTree,
  },
] as const;

const wrap: CSSProperties = {
  maxWidth: 1120,
  margin: "0 auto",
  padding: "28px 18px 88px",
  color: "#e8e8ea",
  background: "#0b0b0c",
  minHeight: "100vh",
  fontFamily:
    'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
  lineHeight: 1.55,
};

const muted: CSSProperties = { color: "rgba(232, 232, 234, 0.62)" };

const card: CSSProperties = {
  border: "1px solid #242428",
  borderRadius: 8,
  background: "#111113",
  boxShadow: "0 18px 60px rgba(0, 0, 0, 0.22)",
};

function paragraphs(text: string) {
  return text
    .split(/\n\s*\n/g)
    .map((para) => para.replace(/\s+/g, " ").trim())
    .filter(Boolean);
}

function sentences(text: string) {
  return (
    text
      .replace(/\s+/g, " ")
      .match(/[^.!?]+[.!?]+|[^.!?]+$/g)
      ?.map((sentence) => sentence.trim())
      .filter(Boolean) ?? []
  );
}

function trimText(text: string, limit = 170) {
  const clean = text.replace(/\s+/g, " ").trim();
  if (clean.length <= limit) return clean;
  return `${clean.slice(0, limit).replace(/\s+\S*$/, "")}...`;
}

function firstSentences(text: string, count: number) {
  return sentences(text).slice(0, count);
}

function evidenceLines(post: Post) {
  const parts = paragraphs(post.note);
  const lines = [
    ...firstSentences(parts[0] ?? "", 2),
    ...firstSentences(parts[1] ?? "", 1),
  ];

  return lines.filter(Boolean).slice(0, 3).map((line) => trimText(line, 190));
}

function positioning(post: Post, kind: "best" | "exposed") {
  const source =
    paragraphs(post.note).find((para) => para.includes("Best positioned:")) ?? "";
  const match =
    kind === "best"
      ? source.match(/Best positioned:\s*([\s\S]*?)(?:\.\s*Most exposed:| Most exposed:|$)/i)
      : source.match(/Most exposed:\s*([\s\S]*?)$/i);

  return trimText((match?.[1] ?? "Not called out separately.").replace(/\.$/, ""), 190);
}

function exampleLine(post: Post) {
  return trimText(firstSentences(paragraphs(post.note)[0] ?? "", 1)[0] ?? post.view, 170);
}

function Meta({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        fontSize: 12,
        letterSpacing: 0.5,
        color: "#9aa0a6",
        textTransform: "uppercase",
      }}
    >
      {children}
    </div>
  );
}

function Label({ children, tone = "blue" }: { children: ReactNode; tone?: "blue" | "green" | "red" | "amber" }) {
  const color =
    tone === "green" ? "#34d399" : tone === "red" ? "#f87171" : tone === "amber" ? "#fbbf24" : "#93c5fd";

  return (
    <span style={{ color, fontWeight: 700, fontSize: 13, letterSpacing: 0.2 }}>
      {children}
    </span>
  );
}

function VersionToggle({
  value,
  onChange,
}: {
  value: VersionKey;
  onChange: (value: VersionKey) => void;
}) {
  return (
    <div
      role="tablist"
      aria-label="Forecast display version"
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
        gap: 8,
        marginTop: 18,
      }}
    >
      {VERSION_OPTIONS.map((option) => {
        const Icon = option.icon;
        const active = value === option.key;

        return (
          <button
            key={option.key}
            type="button"
            role="tab"
            aria-selected={active}
            title={`Switch to ${option.label}`}
            onClick={() => onChange(option.key)}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 10,
              minHeight: 56,
              padding: "10px 12px",
              borderRadius: 8,
              border: active ? "1px solid #93c5fd" : "1px solid #25252a",
              background: active ? "#182033" : "#121214",
              color: active ? "#ffffff" : "#d0d0d4",
              cursor: "pointer",
              textAlign: "left",
            }}
          >
            <span style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
              <span style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 700 }}>
                <Icon size={15} aria-hidden="true" />
                {option.label}
              </span>
              <span style={{ fontSize: 12, color: active ? "#b9d5ff" : "rgba(232,232,234,.52)" }}>
                {option.note}
              </span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

function MiniTable({ rows }: { rows: Array<[string, string]> }) {
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {rows.map(([label, value]) => (
        <div
          key={label}
          style={{
            display: "grid",
            gridTemplateColumns: "112px minmax(0, 1fr)",
            gap: 12,
            alignItems: "start",
            borderTop: "1px solid #222226",
            paddingTop: 8,
            fontSize: 14,
          }}
        >
          <span style={{ ...muted, fontSize: 12, textTransform: "uppercase", letterSpacing: 0.5 }}>
            {label}
          </span>
          <span>{value}</span>
        </div>
      ))}
    </div>
  );
}

function ArrowPath({ post }: { post: Post }) {
  const items = [post.domain, trimText(post.title, 58), trimText(post.watch, 86)];

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        flexWrap: "wrap",
        padding: 12,
        border: "1px solid #263238",
        borderRadius: 8,
        background: "#0d1719",
        fontSize: 14,
      }}
    >
      {items.map((item, index) => (
        <span key={`${item}-${index}`} style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span>{item}</span>
          {index < items.length - 1 ? (
            <ArrowRight size={15} aria-hidden="true" color="#34d399" />
          ) : null}
        </span>
      ))}
    </div>
  );
}

function FullMemo({ post }: { post: Post }) {
  return (
    <>
      <p style={{ margin: "0 0 14px", fontWeight: 700 }}>{post.view}</p>
      {paragraphs(post.note).map((para, i) => (
        <p key={i} style={{ margin: "0 0 12px", opacity: 0.92 }}>
          {para}
        </p>
      ))}
      <MiniTable
        rows={[
          ["Kill", post.kill],
          ["Watch", post.watch],
        ]}
      />
    </>
  );
}

function AnalystBrief({ post }: { post: Post }) {
  return (
    <div style={{ display: "grid", gap: 16 }}>
      <MiniTable
        rows={[
          ["Thesis", post.view],
          ["Odds", post.odds],
          ["Resolves", post.resolves],
        ]}
      />

      <div>
        <Label>Mechanism</Label>
        <div style={{ marginTop: 8 }}>
          <ArrowPath post={post} />
        </div>
      </div>

      <div>
        <Label tone="amber">Evidence</Label>
        <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
          {evidenceLines(post).map((line) => (
            <li key={line} style={{ marginBottom: 6 }}>
              {line}
            </li>
          ))}
        </ul>
      </div>

      <MiniTable
        rows={[
          ["Winners", positioning(post, "best")],
          ["Exposed", positioning(post, "exposed")],
          ["Confirms", post.watch],
          ["Breaks", post.kill],
        ]}
      />
    </div>
  );
}

function ArrowBrief({ post }: { post: Post }) {
  return (
    <div style={{ display: "grid", gap: 14 }}>
      <div style={{ padding: 14, borderRadius: 8, background: "#171719", border: "1px solid #28282d" }}>
        <Label>Bottom line</Label>
        <p style={{ margin: "6px 0 0", fontSize: 16, fontWeight: 700 }}>{post.view}</p>
      </div>

      <div>
        <Label tone="green">Map</Label>
        <div style={{ marginTop: 8 }}>
          <ArrowPath post={post} />
        </div>
      </div>

      <MiniTable
        rows={[
          ["Example", exampleLine(post)],
          ["Trigger", post.watch],
          ["Kill", post.kill],
        ]}
      />
    </div>
  );
}

function VersionBody({ post, version }: { post: Post; version: VersionKey }) {
  if (version === "analyst") return <AnalystBrief post={post} />;
  if (version === "arrow") return <ArrowBrief post={post} />;
  return <FullMemo post={post} />;
}

export default function AdminPage() {
  const [entry, setEntry] = useState("");
  const [ok, setOk] = useState(false);
  const [version, setVersion] = useState<VersionKey>("analyst");

  if (!ok) {
    return (
      <main style={{ ...wrap, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setOk(entry.trim() === CODE);
          }}
          style={{ width: "100%", maxWidth: 320, textAlign: "center" }}
        >
          <div style={{ fontSize: 13, letterSpacing: 1, opacity: 0.5, marginBottom: 14 }}>
            VATI · FORECAST ADMIN
          </div>
          <LockKeyhole size={28} aria-hidden="true" style={{ marginBottom: 14, opacity: 0.64 }} />
          <input
            value={entry}
            onChange={(e) => setEntry(e.target.value)}
            inputMode="numeric"
            placeholder="access code"
            autoFocus
            style={{
              width: "100%",
              padding: "12px 14px",
              fontSize: 16,
              borderRadius: 8,
              border: "1px solid #333",
              background: "#151517",
              color: "#fff",
              textAlign: "center",
            }}
          />
          <button
            type="submit"
            style={{
              marginTop: 12,
              width: "100%",
              padding: "12px 14px",
              fontSize: 15,
              borderRadius: 8,
              border: "none",
              background: "#3b82f6",
              color: "#fff",
              cursor: "pointer",
            }}
          >
            Open
          </button>
        </form>
      </main>
    );
  }

  const posts = (data.posts as Post[]) ?? [];
  const activeVersion = VERSION_OPTIONS.find((option) => option.key === version);

  return (
    <main style={wrap}>
      <header style={{ borderBottom: "1px solid #222", paddingBottom: 20, marginBottom: 24 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 18, flexWrap: "wrap" }}>
          <div>
            <h1 style={{ fontSize: 24, margin: "0 0 6px" }}>Forecast admin</h1>
            <div style={{ fontSize: 13, opacity: 0.58 }}>{data.note}</div>
            <div style={{ fontSize: 12, opacity: 0.42, marginTop: 6 }}>
              Generated {data.generated} · {posts.length} forecasts · display layer only
            </div>
          </div>
          <div
            style={{
              ...card,
              minWidth: 190,
              padding: 14,
              display: "grid",
              gap: 4,
              alignSelf: "start",
            }}
          >
            <Meta>Active version</Meta>
            <strong style={{ fontSize: 18 }}>{activeVersion?.label}</strong>
            <span style={{ ...muted, fontSize: 12 }}>{activeVersion?.note}</span>
          </div>
        </div>

        <VersionToggle value={version} onChange={setVersion} />
      </header>

      {posts.map((p) => (
        <article key={p.n} style={{ ...card, marginBottom: 18, padding: 18 }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "start" }}>
            <Meta>
              {p.domain} · resolves {p.resolves} · {p.odds}
            </Meta>
            <span
              style={{
                flex: "0 0 auto",
                fontSize: 12,
                color: "#0b0b0c",
                background: "#e8e8ea",
                borderRadius: 999,
                padding: "2px 8px",
                fontWeight: 700,
              }}
            >
              #{p.n}
            </span>
          </div>
          <h2 style={{ fontSize: 20, margin: "8px 0 14px", lineHeight: 1.25 }}>
            {p.title}
          </h2>
          <VersionBody post={p} version={version} />
        </article>
      ))}

      <footer style={{ fontSize: 12, opacity: 0.4 }}>
        Dated, falsifiable calls. Versions here change the reading surface, not the sealed call.
      </footer>
    </main>
  );
}
