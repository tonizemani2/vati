import type { Metadata } from "next";
import { RawSection } from "@/sections/raw";
import { SiteRuntime } from "@/sections/SiteRuntime";

const evidenceChecks = [
  {
    label: "Research frontier",
    title: "What is becoming technically possible",
    body: "Papers, preprints, clinical trials, patents, citations, and lab-to-market signals.",
  },
  {
    label: "Supply chain",
    title: "What cannot scale on demand",
    body: "Trade flows, mineral data, component capacity, shipping routes, and supplier concentration.",
  },
  {
    label: "Buildout",
    title: "What is actually getting built",
    body: "Permits, interconnection queues, project filings, land records, and construction evidence.",
  },
  {
    label: "Capital",
    title: "Where the market has already priced it",
    body: "Public filings, prices, funding rounds, procurement language, and capex commitments.",
  },
  {
    label: "Policy",
    title: "Where rules move the constraint",
    body: "Export controls, sanctions, subsidies, procurement rules, and licensing bottlenecks.",
  },
  {
    label: "Outcomes",
    title: "Whether the thesis is becoming true",
    body: "Resolved events, price anchors, production data, disclosure changes, and kill signals.",
  },
];

const walk = [
  {
    title: "Name the constraint",
    body: "The system starts with a concrete bottleneck, not a sector narrative.",
  },
  {
    title: "Pull the evidence",
    body: "It checks the sources that should move first if the constraint is real.",
  },
  {
    title: "Test the price",
    body: "A call dies if the market has already absorbed the thesis.",
  },
  {
    title: "Lock the watchlist",
    body: "The forecast carries the signal that would confirm it and the evidence that would kill it.",
  },
];

const sourceGroups = [
  "papers and preprints",
  "patents and assignees",
  "permits and dockets",
  "filings and disclosures",
  "trade and customs",
  "market prices",
  "policy and sanctions",
  "climate and earth systems",
  "clinical and health data",
  "public forecast boards",
  "entity and ownership graphs",
  "resolved outcomes",
];

export const metadata: Metadata = {
  title: "The data layer - Vaticinus",
  description:
    "The evidence substrate Vaticinus checks before making a call: research, patents, permits, filings, trade, market prices and policy.",
  openGraph: {
    title: "The data layer - Vaticinus",
    description:
      "The evidence substrate behind each Vaticinus call. Not a prompt.",
  },
};

export default function DataPage() {
  return (
    <div className="page_wrap">
      <RawSection name="nav" />
      <main className="page_main vf-page vf-data-page" id="main">
        <section className="vf-hero vf-data-hero u-section u-theme-dark">
          <div className="vf-hero-inner vf-data-hero-inner u-container">
            <div className="vf-hero-copy">
              <div className="c-heading h1 w-richtext u-mb-7">
                <h1>The data layer behind the calls</h1>
              </div>
              <div className="c-paragraph w-richtext u-mb-text u-rich-text u-text-style-large u-color-faded u-max-width-50ch">
                <p>
                  Vaticinus maps the evidence behind a forecast before the model
                  takes a side. The point is not a big corpus number. It is
                  checking the right parts of the world.
                </p>
              </div>
              <div className="u-button-group">
                <a href="#checks" className="button_main_wrap w-inline-block">
                  <div aria-hidden="true" className="button_main_text u-text-style-main">
                    See the checks
                  </div>
                </a>
                <a
                  href="https://chat.vaticinus.com"
                  className="button_main_wrap secondary-white w-inline-block"
                >
                  <div aria-hidden="true" className="button_main_text u-text-style-main secondary-8">
                    Open the model
                  </div>
                </a>
              </div>
            </div>

            <aside className="vf-data-walk-panel" aria-label="Evidence walk">
              <div className="vf-panel-head">
                <strong>Evidence walk</strong>
                <span>live substrate</span>
              </div>
              <div className="vf-data-walk-list">
                {walk.map((item) => (
                  <div className="vf-data-walk-row" key={item.title}>
                    <strong>{item.title}</strong>
                    <p>{item.body}</p>
                  </div>
                ))}
              </div>
            </aside>
          </div>
        </section>

        <section id="checks" className="vf-boards vf-data-checks u-section">
          <div className="u-container">
            <div className="vf-section-head">
              <div className="c-heading w-richtext u-mb-7">
                <h2>What the system checks</h2>
              </div>
              <div className="c-paragraph w-richtext u-rich-text u-color-faded">
                <p>
                  Every forecast is routed through the evidence that should move
                  first if the thesis is true. These are the checks, not a vanity
                  count.
                </p>
              </div>
            </div>
            <div className="vf-data-check-grid">
              {evidenceChecks.map((check) => (
                <article className="vf-data-check-card" key={check.label}>
                  <span>{check.label}</span>
                  <h3>{check.title}</h3>
                  <p>{check.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="vf-boards vf-data-method u-section">
          <div className="u-container">
            <div className="vf-data-method-card">
              <div>
                <div className="c-heading w-richtext u-mb-7">
                  <h2>How the data changes the call</h2>
                </div>
                <div className="c-paragraph w-richtext u-rich-text u-color-faded">
                  <p>
                    The substrate is a constraint map. It tells the forecaster
                    where the bottleneck lives, who owns it, whether supply can
                    answer price, and what observation would make the claim fail.
                  </p>
                </div>
              </div>
              <div className="vf-data-rule-stack">
                <div>
                  <strong>No prompt-only answers</strong>
                  <p>The answer has to touch source data before it becomes a forecast.</p>
                </div>
                <div>
                  <strong>No stale evidence</strong>
                  <p>Dates matter because forecasts are only real before the outcome.</p>
                </div>
                <div>
                  <strong>No unpriced edge</strong>
                  <p>If the market already sees the constraint, the call is not useful.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="vf-boards vf-data-sources u-section">
          <div className="u-container">
            <div className="vf-section-head">
              <div className="c-heading w-richtext u-mb-7">
                <h2>The source families</h2>
              </div>
              <div className="c-paragraph w-richtext u-rich-text u-color-faded">
                <p>
                  The same call may need scientific evidence, supply-chain
                  evidence, market evidence, and policy evidence on one page.
                </p>
              </div>
            </div>
            <div className="vf-chip-wrap vf-data-source-wrap">
              {sourceGroups.map((source) => (
                <span key={source} className="vf-chip">
                  {source}
                </span>
              ))}
            </div>
          </div>
        </section>

        <section className="vf-note u-section">
          <div className="u-container">
            <div className="vf-ultra-link">
              <div>
                <span>Research tier</span>
                <h2>Bring your own mandate</h2>
                <p>
                  Ask a question about a sector, supply chain, or policy shock.
                  We point the data layer at the sources that should move first,
                  then turn the evidence into a forecast you can monitor.
                </p>
              </div>
              <a href="#contact-modal" data-contact="">
                Work with us
              </a>
            </div>
            <p className="vf-disclaimer">
              Data checks are evidence inputs, not investment advice.
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
