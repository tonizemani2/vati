"use client";

import React from "react";

// A tiny, safe markdown renderer for the council's research note. We deliberately do NOT
// pull in react-markdown: the council emits a known, narrow subset (## headings, **bold**,
// - / 1. bullets, [text](url) links, paragraphs) and shipping ~40 lines beats adding a
// parser dep to the edge bundle. No raw HTML is ever injected; everything is React nodes.

// Only ever render links to these schemes. The note now contains untrusted live web
// research, so a model-emitted [x](javascript:...) or data: URL must never reach an href.
function safeHref(url: string): string | null {
  const u = url.trim();
  if (/^(https?:|mailto:)/i.test(u)) return u;
  if (u.startsWith("/") || u.startsWith("#")) return u;
  return null;
}

// Inline: **bold** and [text](url). Returns an array of React nodes.
function inline(text: string, keyBase: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  // Split on bold or link tokens, keeping the delimiters.
  const re = /(\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) {
      nodes.push(
        <strong key={`${keyBase}-b${i}`} className="font-semibold text-[var(--ink)]">
          {tok.slice(2, -2)}
        </strong>,
      );
    } else {
      const lm = tok.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      const href = lm ? safeHref(lm[2]) : null;
      if (lm && href) {
        nodes.push(
          <a
            key={`${keyBase}-l${i}`}
            href={href}
            target="_blank"
            rel="noreferrer nofollow"
            className="text-[var(--brand-600)] underline decoration-[var(--border-faint)] underline-offset-2 hover:decoration-[var(--brand-600)]"
          >
            {lm[1]}
          </a>,
        );
      } else if (lm) {
        nodes.push(lm[1]); // unsafe scheme: render the link text only, drop the href
      } else {
        nodes.push(tok);
      }
    }
    last = re.lastIndex;
    i++;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

export function Markdown({ text }: { text: string }) {
  const lines = text.replace(/\r/g, "").split("\n");
  const blocks: React.ReactNode[] = [];
  let para: string[] = [];
  let list: string[] = [];
  let key = 0;

  const flushPara = () => {
    if (!para.length) return;
    blocks.push(
      <p key={`p${key++}`} className="leading-7 text-[var(--ink)]">
        {inline(para.join(" "), `p${key}`)}
      </p>,
    );
    para = [];
  };
  const flushList = () => {
    if (!list.length) return;
    blocks.push(
      <ul key={`u${key++}`} className="my-1 ml-1 flex flex-col gap-1">
        {list.map((it, j) => (
          <li key={j} className="flex gap-2 leading-7 text-[var(--ink)]">
            <span className="mt-[10px] h-1 w-1 shrink-0 rounded-full bg-[var(--brand-600)]" />
            <span>{inline(it, `u${key}-${j}`)}</span>
          </li>
        ))}
      </ul>,
    );
    list = [];
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    const heading = line.match(/^#{1,4}\s+(.*)$/);
    const bullet = line.match(/^\s*(?:[-*]|\d+\.)\s+(.*)$/);
    if (heading) {
      flushPara();
      flushList();
      blocks.push(
        <h3
          key={`h${key++}`}
          className="mt-3 text-[12px] font-semibold uppercase tracking-wide text-[var(--ink-muted)]"
        >
          {inline(heading[1], `h${key}`)}
        </h3>,
      );
    } else if (bullet) {
      flushPara();
      list.push(bullet[1]);
    } else if (!line.trim()) {
      flushPara();
      flushList();
    } else {
      flushList();
      para.push(line);
    }
  }
  flushPara();
  flushList();

  return <div className="flex flex-col gap-2 text-[16px]">{blocks}</div>;
}
