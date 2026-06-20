import type { Metadata } from "next";
import { readFileSync } from "fs";
import { join } from "path";
import { RawSection } from "@/sections/raw";
import { SiteRuntime } from "@/sections/SiteRuntime";

type Thesis = {
  id?: string;
  headline?: string;
  clause_p?: number;
  resolves?: string;
};

type BoardSpec = {
  title?: string;
  domain?: string;
  synthesis?: string;
  subtitle?: string;
  theses?: Thesis[];
};

type Board = {
  slug: string;
  specPath: string;
  pdf: string;
  preview: string;
};

const BOARDS: Board[] = [
  {
    slug: "critical-minerals",
    specPath: "research/pope/critical-minerals-2026-06-20.json",
    pdf: "/forecasts/critical-minerals.pdf",
    preview: "/forecasts/previews/critical-minerals-memo.png",
  },
  {
    slug: "inelastic-needles",
    specPath: "research/pope/inelastic-needles-2026-06-15.json",
    pdf: "/forecasts/inelastic-needles.pdf",
    preview: "/forecasts/previews/inelastic-needles-memo.png",
  },
  {
    slug: "long-horizon",
    specPath: "research/pope/long-horizon-2026-06-14.json",
    pdf: "/forecasts/long-horizon.pdf",
    preview: "/forecasts/previews/long-horizon-memo.png",
  },
  {
    slug: "chips",
    specPath: "research/pope/chips-2026-06-14.json",
    pdf: "/forecasts/chips.pdf",
    preview: "/forecasts/previews/chips-memo.png",
  },
  {
    slug: "biotech",
    specPath: "research/pope/biotech-2026-06-14.json",
    pdf: "/forecasts/biotech.pdf",
    preview: "/forecasts/previews/biotech-memo.png",
  },
  {
    slug: "space",
    specPath: "research/pope/space-2026-06-14.json",
    pdf: "/forecasts/space.pdf",
    preview: "/forecasts/previews/space-memo.png",
  },
  {
    slug: "post-ai-world",
    specPath: "research/pope/post-ai-world-2026-06-17.json",
    pdf: "/forecasts/post-ai-world.pdf",
    preview: "/forecasts/previews/post-ai-world-memo.png",
  },
  {
    slug: "structural",
    specPath: "research/pope/any-long-2026-06-15.json",
    pdf: "/forecasts/structural.pdf",
    preview: "/forecasts/previews/structural-memo.png",
  },
  {
    slug: "after-ai",
    specPath: "research/pope/after-ai-2026-06-17.json",
    pdf: "/forecasts/after-ai.pdf",
    preview: "/forecasts/previews/after-ai-memo.png",
  },
  {
    slug: "catalyst",
    specPath: "research/pope/any-short-2026-06-15.json",
    pdf: "/forecasts/catalyst.pdf",
    preview: "/forecasts/previews/catalyst-memo.png",
  },
];

export const metadata: Metadata = {
  title: "Forecasts - Vaticinus",
  description:
    "Dated Vaticinus forecast boards on where scarce inputs and value migrate next.",
  openGraph: {
    title: "Forecasts - Vaticinus",
    description:
      "Dated Vaticinus forecast boards on where scarce inputs and value migrate next.",
  },
  twitter: {
    title: "Forecasts - Vaticinus",
    description:
      "Dated Vaticinus forecast boards on where scarce inputs and value migrate next.",
  },
};

function repoPath(...parts: string[]) {
  return join(process.cwd(), "..", ...parts);
}

function loadBoards() {
  return BOARDS.map((board) => {
    const spec = JSON.parse(
      readFileSync(repoPath(board.specPath), "utf8"),
    ) as BoardSpec;
    return { ...board, spec, theses: spec.theses ?? [] };
  });
}

function pct(value?: number) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return `${Math.round(value <= 1 ? value * 100 : value)}%`;
}

function short(text?: string, limit = 210) {
  const clean = (text ?? "").replace(/\s+/g, " ").trim();
  if (clean.length <= limit) return clean;
  return `${clean.slice(0, limit).replace(/\s+\S*$/, "")}...`;
}

function CallRow({ thesis }: { thesis: Thesis }) {
  return (
    <div className="vf-call-row">
      <span className="vf-call-id">{thesis.id}</span>
      <span className="vf-call-title">{thesis.headline}</span>
      <span className="vf-call-read">
        {pct(thesis.clause_p)}
        <small>{thesis.resolves}</small>
      </span>
    </div>
  );
}

export default function ForecastsPage() {
  const boards = loadBoards();
  const callCount = boards.reduce((n, board) => n + board.theses.length, 0);
  const leadCalls = boards[0]?.theses.slice(0, 3) ?? [];

  return (
    <div className="page_wrap">
      <RawSection name="nav" />
      <main className="page_main vf-page" id="main">
        <section className="vf-hero u-section u-theme-dark">
          <div className="vf-hero-inner u-container">
            <div className="vf-hero-copy">
              <div className="c-heading h1 w-richtext u-mb-7">
                <h1>Forecast boards</h1>
              </div>
              <div className="c-paragraph w-richtext u-mb-text u-rich-text u-text-style-large u-color-faded u-max-width-50ch">
                <p>
                  Dated calls, scored when they resolve. Open a board for the
                  sources, refute notes, and full argument.
                </p>
              </div>
              <div className="u-button-group">
                <div className="button_main_wrap">
                  <div className="clickable_wrap u-cover-absolute">
                    <a className="clickable_link w-inline-block" href="#boards">
                      <span className="clickable_text u-sr-only">
                        Browse boards
                      </span>
                    </a>
                  </div>
                  <div className="button_main_text u-text-style-main">
                    Browse boards
                  </div>
                </div>
                <div className="button_main_wrap secondary-white">
                  <div className="clickable_wrap u-cover-absolute">
                    <a
                      className="clickable_link w-inline-block"
                      href="/forecasts/inelastic-needles.pdf"
                    >
                      <span className="clickable_text u-sr-only">
                        Lead PDF
                      </span>
                    </a>
                  </div>
                  <div className="button_main_text u-text-style-main secondary-8">
                    Lead PDF
                  </div>
                </div>
              </div>
            </div>

            <aside className="vf-live-panel" aria-label="Lead forecast calls">
              <div className="vf-panel-head">
                <strong>Lead board</strong>
                <span>Live record</span>
              </div>
              {leadCalls.map((thesis) => (
                <CallRow key={thesis.id ?? thesis.headline} thesis={thesis} />
              ))}
            </aside>
          </div>
        </section>

        <section id="boards" className="vf-boards u-section">
          <div className="u-container">
            <div className="vf-section-head">
              <div>
                <div className="c-heading w-richtext u-mb-7">
                  <h2>Current boards</h2>
                </div>
              </div>
              <div className="c-paragraph w-richtext u-rich-text u-color-faded">
                <p>
                  {callCount} calls across {boards.length} boards. Each row
                  gives the claim, resolution date, and probability we put on
                  the dated version.
                </p>
              </div>
            </div>

            <div className="vf-board-stack">
              <article className="vf-board-card vf-dossier-card">
                <a
                  className="vf-cover"
                  href="/forecasts/ai-campus-power-claims.pdf"
                  aria-label="Open AI Campus Power-Claim Diligence PDF"
                >
                  <img
                    src="/forecasts/previews/ai-campus-power-claims-memo.png"
                    alt="AI Campus Power-Claim Diligence PDF"
                  />
                </a>
                <div className="vf-board-copy">
                  <div className="vf-board-kicker">31-page analyst dossier</div>
                  <h3>AI campus power-claim diligence</h3>
                  <p className="vf-board-summary">
                    Our analyst team turns announced AI campus power claims into
                    a full primary-source dossier: verify, contest, or demote
                    the energization story before capital treats it as real.
                  </p>
                  <div className="vf-board-meta">
                    <span>31-page dossier</span>
                    <span>12 project rows</span>
                  </div>
                  <div className="vf-call-list">
                    <div className="vf-call-row">
                      <span className="vf-call-id">Lead</span>
                      <span className="vf-call-title">
                        Talen/Amazon Susquehanna is the flagship contested row,
                        not clean proof.
                      </span>
                      <span className="vf-call-read">
                        Docket
                        <small>ER24-2172</small>
                      </span>
                    </div>
                    <div className="vf-call-row">
                      <span className="vf-call-id">Check</span>
                      <span className="vf-call-title">
                        A claimed power-secured campus needs MW, counterparty,
                        interconnection path, and permit status.
                      </span>
                      <span className="vf-call-read">
                        Source
                        <small>Primary</small>
                      </span>
                    </div>
                  </div>
                  <div className="vf-board-actions">
                    <a
                      className="vf-pill vf-pill-primary"
                      href="/forecasts/ai-campus-power-claims/"
                    >
                      Read dossier
                    </a>
                    <a
                      className="vf-pill"
                      href="/forecasts/ai-campus-power-claims.pdf"
                    >
                      Open PDF
                    </a>
                  </div>
                </div>
              </article>
              {boards.map((board) => {
                const visible = board.theses.slice(0, 2);
                const rest = board.theses.slice(2);
                return (
                  <article
                    className="vf-board-card"
                    id={board.slug}
                    key={board.slug}
                  >
                    <a className="vf-cover" href={board.pdf} aria-label={`Open ${board.spec.title ?? "forecast board"} PDF`}>
                      <img
                        src={board.preview}
                        alt={`${board.spec.title ?? "Forecast board"} PDF`}
                      />
                    </a>
                    <div className="vf-board-copy">
                      <div className="vf-board-kicker">
                        {short(board.spec.domain, 70)}
                      </div>
                      <h3>{board.spec.title}</h3>
                      <p className="vf-board-summary">
                        {short(board.spec.synthesis || board.spec.subtitle)}
                      </p>
                      <div className="vf-board-meta">
                        <span>{board.theses.length} calls</span>
                        <span>PDF board</span>
                      </div>
                      <div className="vf-call-list">
                        {visible.map((thesis) => (
                          <CallRow
                            key={thesis.id ?? thesis.headline}
                            thesis={thesis}
                          />
                        ))}
                        {rest.length > 0 && (
                          <details className="vf-more-calls">
                            <summary>
                              Show {rest.length} more{" "}
                              {rest.length === 1 ? "call" : "calls"}
                            </summary>
                            {rest.map((thesis) => (
                              <CallRow
                                key={thesis.id ?? thesis.headline}
                                thesis={thesis}
                              />
                            ))}
                          </details>
                        )}
                      </div>
                      <div className="vf-board-actions">
                        <a className="vf-pill vf-pill-primary" href={board.pdf}>
                          Open board PDF
                        </a>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        </section>

        <section className="vf-note u-section">
          <div className="u-container">
            <div className="vf-ultra-link">
              <div>
                <span>Analyst-team dossier</span>
                <h2>AI campus power-claim diligence</h2>
                <p>
                  Built from public dockets and official records as a 31-page
                  buyer-facing report on what counts as power secured.
                </p>
              </div>
              <a href="/forecasts/ai-campus-power-claims">Read the dossier</a>
            </div>
            <p className="vf-disclaimer">
              Not investment advice. These are dated forward calls; they get
              graded when the resolution date arrives.
            </p>
          </div>
        </section>
        <RawSection name="engage" />
        <RawSection name="footer" />
      </main>
      <RawSection name="contactModal" />
      <RawSection name="sampleqsModal" />
      <RawSection name="videoModal" />
      <SiteRuntime />
    </div>
  );
}
