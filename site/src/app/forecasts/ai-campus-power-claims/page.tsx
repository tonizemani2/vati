import type { Metadata } from "next";
import { RawSection } from "@/sections/raw";
import { SiteRuntime } from "@/sections/SiteRuntime";

type DocketRow = {
  docket: string;
  status: string;
  issue: string;
  next: string;
};

type ProjectRow = {
  project: string;
  market: string;
  status: string;
  capacity: string;
  why: string;
  next: string;
};

type TargetRow = {
  org: string;
  category: string;
  angle: string;
};

const DOCKETS: DocketRow[] = [
  {
    docket: "RM26-4-000",
    status: "primary verified",
    issue:
      "FERC large-load interconnection ANOPR, including data centers and co-located/flexible load.",
    next: "Watch for Commission action by end-June 2026.",
  },
  {
    docket: "EL25-49 / AD24-11 / EL25-20",
    status: "primary verified",
    issue:
      "PJM co-located load rules, behind-the-meter netting, transmission service, and rate design.",
    next: "Track compliance and paper-hearing replacement-rate issues.",
  },
  {
    docket: "ER24-2172",
    status: "contested",
    issue:
      "PJM/Susquehanna/Talen/Amazon ISA amendment; FERC rejected amendments on 2024-11-01.",
    next: "Watch appellate review and generic PJM co-location dockets.",
  },
  {
    docket: "ER26-1088",
    status: "primary verified",
    issue:
      "PJM 30-day compliance filing from EL25-49; FERC accepted in part and rejected in part.",
    next: "Track further compliance after the 2026-04-16 order.",
  },
  {
    docket: "ER26-1479",
    status: "pending",
    issue:
      "PJM 60-day co-located load tariff revisions filed 2026-02-23.",
    next: "Await FERC merits order.",
  },
];

const PROJECTS: ProjectRow[] = [
  {
    project: "AWS / Talen Susquehanna data campus",
    market: "PJM, Pennsylvania",
    status: "contested",
    capacity:
      "Large co-located load tied to Susquehanna nuclear; larger multi-phase claims stay live but not clean.",
    why:
      "Core refutation case: commercial story exists, but FERC rejected the ISA amendment.",
    next:
      "Pull ER24-2172, related appeals, and later PJM/FERC filings before using any MW claim.",
  },
  {
    project: "Constellation / Microsoft Crane Clean Energy Center",
    market: "PJM, Pennsylvania",
    status: "restart case",
    capacity: "835 MW company/DOE restart figure.",
    why:
      "Nuclear restart and PPA case tied to Microsoft data-center power matching in PJM.",
    next: "Track NRC restart/license approvals and PJM deliverability materials.",
  },
  {
    project: "Google / Brookfield Holtwood + Safe Harbor hydro",
    market: "PJM, Pennsylvania",
    status: "framework",
    capacity: "670 MW initial; up to 3,000 MW framework.",
    why: "Dispatchable hydro procurement for Google PJM operations.",
    next: "Pull FERC hydro relicensing dockets, especially Safe Harbor No. 1025.",
  },
  {
    project: "Homer City Energy Campus",
    market: "PJM, Pennsylvania",
    status: "official lead",
    capacity: "4.4-4.5 GW project claim.",
    why: "Retired coal site converted into gas-powered AI/HPC campus.",
    next:
      "Verify PA DEP permits, PJM interconnection, and tenant energy service agreements.",
  },
  {
    project: "Amazon / AES Ohio data center",
    market: "PJM, Ohio",
    status: "RTO planning",
    capacity: "65 MW at COD; 480 MW by end of Phase I.",
    why: "Named 345 kV service request with dated ramp schedule.",
    next:
      "Pull AES/PUCO electric service agreement and network upgrade costs.",
  },
  {
    project: "Dominion Culpeper Tech Zone campuses",
    market: "PJM, Virginia",
    status: "utility filing",
    capacity: "188 MW by 2028; 1,164 MW by 2034 aggregate.",
    why:
      "Three named campuses driving 230 kV buildout and useful public load evidence.",
    next: "Track SCC case status, per-campus MW split, and county approvals.",
  },
];

const TARGETS: TargetRow[] = [
  {
    org: "Infrastructure investors and lenders",
    category: "First buyer",
    angle:
      "Use the sprint before underwriting a campus, loan, power JV, or land transaction.",
  },
  {
    org: "Municipalities and landowners",
    category: "High pain",
    angle:
      "Separate a credible powered-campus proposal from a press-release-deep promise.",
  },
  {
    org: "Smaller developers",
    category: "Credibility wedge",
    angle:
      "Use a primary-source dossier to prove a site is more real than larger announced competitors.",
  },
  {
    org: "Power developers",
    category: "Partner screen",
    angle:
      "Find which AI-campus counterparties have a real path through interconnection and permits.",
  },
];

export const metadata: Metadata = {
  title: "AI Campus Power-Claim Diligence - Vaticinus",
  description:
    "A 31-page Vaticinus analyst-team dossier that verifies or refutes AI campus power claims with primary-source evidence.",
  openGraph: {
    title: "AI Campus Power-Claim Diligence - Vaticinus",
    description:
      "A 31-page Vaticinus analyst-team dossier that verifies or refutes AI campus power claims with primary-source evidence.",
  },
  twitter: {
    title: "AI Campus Power-Claim Diligence - Vaticinus",
    description:
      "A 31-page Vaticinus analyst-team dossier that verifies or refutes AI campus power claims with primary-source evidence.",
  },
};

function StatusPill({ children }: { children: React.ReactNode }) {
  return <span className="vfu-pill">{children}</span>;
}

export default function CampusPowerClaimsPage() {
  return (
    <div className="page_wrap">
      <RawSection name="nav" />
      <main className="page_main vfu-page" id="main">
        <section className="vfu-hero">
          <div className="u-container vfu-hero-inner">
            <div className="vfu-hero-copy">
              <a className="vfu-back" href="/forecasts/">
                Forecasts
              </a>
              <h1>AI campus power claims need a docket check.</h1>
              <p>
                Our analyst team turned the forecast into a 31-page diligence
                dossier: verify or refute whether announced AI campuses can
                actually energize.
              </p>
              <div className="vfu-actions">
                <a href="#sample" className="vfu-button">
                  Read sample rows
                </a>
                <a
                  href="/forecasts/ai-campus-power-claims.pdf"
                  className="vfu-button vfu-button-secondary"
                >
                  Open full PDF
                </a>
              </div>
            </div>

            <aside className="vfu-side" aria-label="Dossier summary">
              <a
                className="vfu-cover-card"
                href="/forecasts/ai-campus-power-claims.pdf"
              >
                <img
                  src="/forecasts/previews/ai-campus-power-claims-memo.png"
                  alt="AI Campus Power-Claim Diligence full dossier cover"
                />
              </a>
              <div className="vfu-brief">
                <div>
                  <span>Prepared by</span>
                  <strong>Our analyst team</strong>
                </div>
                <div>
                  <span>Format</span>
                  <strong>31-page dossier</strong>
                </div>
                <div>
                  <span>Result</span>
                  <strong>Wedge narrowed</strong>
                </div>
                <div>
                  <span>First market</span>
                  <strong>PJM / Mid-Atlantic</strong>
                </div>
              </div>
            </aside>
          </div>
        </section>

        <section className="vfu-section">
          <div className="u-container">
            <div className="vfu-lede">
              <p>
                The broad insight, data-center power is scarce, is now public.
                The sharper product is more useful: test the exact power story
                attached to a site before capital treats it as real.
              </p>
            </div>
            <div className="vfu-rule-grid">
              <div className="vfu-rule-card vfu-rule-card-plain">
                <h2>Bad pitch</h2>
                <p>Power-secured AI campuses win.</p>
              </div>
              <div className="vfu-rule-card">
                <h2>Better pitch</h2>
                <p>
                  Prove whether a claimed power-secured campus survives
                  primary-source diligence.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="vfu-section vfu-section-tight">
          <div className="u-container">
            <div className="vfu-label-rule">
              <h2>Hard label rule</h2>
              <p>
                No row can be called <code>power secured</code> unless primary
                or official sources verify MW, counterparty/offtake,
                interconnection or behind-the-meter path, and permit/regulatory
                status.
              </p>
              <div className="vfu-pills">
                <StatusPill>lead</StatusPill>
                <StatusPill>source verified</StatusPill>
                <StatusPill>contested</StatusPill>
                <StatusPill>demoted</StatusPill>
                <StatusPill>interconnection risk</StatusPill>
              </div>
            </div>
          </div>
        </section>

        <section className="vfu-section" id="dockets">
          <div className="u-container">
            <div className="vfu-section-head">
              <h2>Docket spine</h2>
              <p>
                These are the public record surfaces that make the product
                concrete. The work starts where the press release stops.
              </p>
            </div>
            <div className="vfu-table">
              {DOCKETS.map((row) => (
                <article className="vfu-table-row" key={row.docket}>
                  <div>
                    <span className="vfu-row-label">{row.status}</span>
                    <h3>{row.docket}</h3>
                  </div>
                  <p>{row.issue}</p>
                  <p>{row.next}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="vfu-section" id="sample">
          <div className="u-container">
            <div className="vfu-section-head">
              <h2>Sample rows</h2>
              <p>
                The sample set already has one crucial correction: Talen/Amazon
                is not clean proof. It is the flagship contested row in a
                12-row project ledger.
              </p>
            </div>
            <div className="vfu-project-stack">
              {PROJECTS.map((row) => (
                <article className="vfu-project" key={row.project}>
                  <div className="vfu-project-top">
                    <div>
                      <span>{row.market}</span>
                      <h3>{row.project}</h3>
                    </div>
                    <StatusPill>{row.status}</StatusPill>
                  </div>
                  <dl>
                    <div>
                      <dt>Verified capacity</dt>
                      <dd>{row.capacity}</dd>
                    </div>
                    <div>
                      <dt>Why it matters</dt>
                      <dd>{row.why}</dd>
                    </div>
                    <div>
                      <dt>Next check</dt>
                      <dd>{row.next}</dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="vfu-section" id="offer">
          <div className="u-container">
            <div className="vfu-offer">
              <div>
                <h2>10-business-day AI Campus Power-Claim Diligence sprint</h2>
                <p>
                  For a buyer-provided asset list, docket, site, or LOI. The
                  output is a memo-ready call on what to reserve, diligence,
                  monitor, or kill.
                </p>
              </div>
              <div className="vfu-offer-list">
                <p>Deliverables</p>
                <ul>
                  <li>Five to twelve verified or demoted site rows.</li>
                  <li>One refuted lead, included by design.</li>
                  <li>Time-to-energize risk table and watchlist.</li>
                  <li>Action memo: reserve, avoid, diligence, monitor, or kill.</li>
                </ul>
              </div>
            </div>
            <div className="vfu-targets">
              {TARGETS.map((target) => (
                <article key={target.org}>
                  <span>{target.category}</span>
                  <h3>{target.org}</h3>
                  <p>{target.angle}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="vfu-section vfu-section-tight">
          <div className="u-container">
            <div className="vfu-source-links">
              <h2>Primary anchors</h2>
              <a href="https://www.ferc.gov/rm26-4">FERC RM26-4</a>
              <a href="https://www.ferc.gov/news-events/news/fact-sheet-ferc-directs-nations-largest-grid-operator-create-new-rules-embrace">
                FERC PJM co-location order
              </a>
              <a href="https://www.ferc.gov/sites/default/files/2024-11/20241101-3061_ER24-2172-000.pdf">
                ER24-2172 order
              </a>
              <a href="https://www.energy.gov/articles/doe-releases-new-report-evaluating-increase-electricity-demand-data-centers">
                DOE/LBNL data-center load report
              </a>
            </div>
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
