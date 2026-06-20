import Header from "@/components/Header";
import ExamplePredictions from "@/components/ExamplePredictions";
import HeroVisual from "@/components/HeroVisual";
import StageBand from "@/components/StageBand";
import { Reveal } from "@/components/Reveal";
import Counter from "@/components/Counter";

/* ── Small inline icon ─────────────────────────────────────────────────────── */
function Icon({ path }: { path: string }) {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor"
      strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d={path} />
    </svg>
  );
}

const SUGGESTIONS = [
  { icon: "M3 12h4l3 8 4-16 3 8h4", label: "Where does the next binding constraint land?" },
  { icon: "M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7l8-4z", label: "Is this shift already priced in?" },
  { icon: "M4 7h16M4 12h10M4 17h7M16 15l2 2 4-4", label: "Show me the leak-free scored record" },
];

const PILLARS = [
  {
    title: "Read the signal early",
    icon: "M3 12h4l3 8 4-16 3 8h4",
    body: "Vati watches the places a shift shows up first: a capability curve bending, a dependency graph turning over, an input that quietly stops being elastic. It reads the fine grain, not the headline number, because by the time the aggregate moves the price already has.",
  },
  {
    title: "Kill the weak calls",
    icon: "M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7l8-4z",
    body: "A call the market has already priced is worth nothing to you. Every one has to clear a dated metric, a clean way to be proven wrong, and a check that the crowd has not caught up yet. Most ideas die at this step. That is the step working.",
  },
  {
    title: "Grade in public",
    icon: "M4 7h16M4 12h10M4 17h7M16 15l2 2 4-4",
    body: "When Vati makes a call we lock it. The resolution date goes down first and the Brier score comes back at close, with nothing edited in between. What you get is a running scoreboard of how the lab actually does, win or lose.",
  },
];

const BENCH = [
  { label: "Vati (dataset split, leak-free)", score: 0.124, pct: 100, accent: true },
  { label: "Crowd / market baseline", score: 0.142, pct: 86 },
  { label: "Naive base rate", score: 0.248, pct: 50 },
];

const MODELS = [
  {
    name: "Vati 8B",
    tags: ["8B parameters", "24 domains", "29,445 traces"],
    lead: "An 8B model fine-tuned to find the binding constraint and call where it moves next.",
    body: "Trained on leak-free reasoning traces so its read does not lean on outcomes it could have memorised. Live on the Metaculus Cup; built to lead the bot field on ForecastBench.",
  },
  {
    name: "The gate",
    tags: ["dated metric", "kill-criterion", "pre-consensus"],
    lead: "The discipline that turns a wide field of ideas into a small set of tracked calls.",
    body: "Generate wide, graduate strict. An idea only becomes a call once it clears a dated constraint metric, a falsifiable kill-criterion, and a check that the crowd has not already priced it.",
  },
];

const USE_CASES = [
  { role: "Investors", line: "Structural calls on where scarcity lands next, each carrying a score you can check." },
  { role: "Operators", line: "Where the rent in your supply chain moves, before a competitor reprices it for you." },
  { role: "Strategists", line: "The dependency graph read one layer below the shortage everyone is already talking about." },
  { role: "Policy teams", line: "Where export controls and decreed scarcity bend the supply graph, ahead of the headline." },
  { role: "Risk & procurement", line: "Lead-time and chokepoint warnings out of a clean, leak-free pipeline." },
  { role: "Researchers", line: "A calibrated model you can audit. Every claim is dated, every method open to inspection." },
];

export default function Page() {
  return (
    <div id="top" className="relative overflow-x-hidden bg-dark">
      <Header />

      {/* ── Hero (dark) ─────────────────────────────────────────────────────── */}
      <section className="relative bg-dark-2 grid-tex">
        <div className="glow left-[60%] top-[2rem] h-[40rem] w-[40rem]" />
        <div className="absolute inset-y-0 right-0 hidden w-1/2 md:block">
          <HeroVisual />
        </div>
        <div className="relative mx-auto max-w-[1280px] px-6 pb-28 pt-40 lg:px-14">
          <div className="max-w-xl">
            <Reveal>
              <span className="eyebrow">A forecasting research lab · Berlin</span>
            </Reveal>
            <Reveal delay={0.06}>
              <h1 className="display mt-6 max-w-[12ch] text-[2.55rem] text-fg sm:max-w-xl sm:text-[3.5rem] lg:text-[4rem]">
                Find the <span className="hl inline-block">hidden bottleneck</span> before it reprices your plan.
              </h1>
            </Reveal>
            <Reveal delay={0.14}>
              <p className="mt-6 max-w-lg text-base leading-relaxed text-fg-soft">
                Vaticinus builds Vati, an 8B model fine-tuned to find the binding constraint in an
                industry and call where it moves next, before the market prices it in. Every call is
                dated, locked, and scored in public.
              </p>
            </Reveal>

            <Reveal delay={0.22}>
              <div className="mt-9 w-full max-w-full">
                <div className="rounded-2xl border border-line bg-white/[0.03] p-2 backdrop-blur-sm">
                  <div className="flex items-center gap-3 rounded-xl px-4 py-3">
                    <span className="min-w-0 flex-1 text-sm text-fg-dim">Ask where value goes next...</span>
                    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-accent text-[#062020]">
                      <Icon path="M5 12h14M13 6l6 6-6 6" />
                    </span>
                  </div>
                </div>

                <div className="mt-3 space-y-px overflow-hidden rounded-xl border border-line">
                  {SUGGESTIONS.map((s) => (
                    <div key={s.label} className="flex w-full items-center gap-3 bg-white/[0.02] px-4 py-3 text-left text-sm text-fg-soft">
                      <span className="shrink-0 text-accent">
                        <Icon path={s.icon} />
                      </span>
                      <span className="min-w-0 flex-1">{s.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            </Reveal>

            <Reveal delay={0.3}>
              <div className="mt-9 flex flex-wrap items-center gap-3">
                <a href="#record" className="pill-primary">Read the record</a>
                <a href="mailto:research@vaticinus.com?subject=Vaticinus%20research" className="pill-soft on-dark">
                  Get in touch
                </a>
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ── Method spine (dark) ─────────────────────────────────────────────── */}
      <section id="method" className="border-t border-line bg-dark">
        <div className="mx-auto max-w-[1280px] px-6 py-32 lg:px-14">
          <div className="grid gap-12 md:grid-cols-[1fr_1.1fr] md:items-end">
            <Reveal>
              <span className="eyebrow">The method</span>
              <h2 className="display mt-4 text-[clamp(2rem,3.6vw,3rem)] text-fg">
                From hindsight to foresight. Read the constraint, not the headline.
              </h2>
            </Reveal>
            <Reveal delay={0.1}>
              <p className="text-base leading-relaxed text-fg-soft">
                Rent accrues to the binding constraint. Vati follows the causal spine of an industry
                from the frontier through to outcomes. The money is usually in the middle, where one
                input stops being elastic while everyone is still watching the shortage above it. Price
                is the last layer and it is also the test.
              </p>
            </Reveal>
          </div>
          <div className="mt-14">
            <StageBand />
          </div>
        </div>
      </section>

      {/* ── Performance / Brier (dark) ──────────────────────────────────────── */}
      <section className="border-t border-line bg-dark">
        <div className="mx-auto max-w-[1280px] px-6 py-32 lg:px-14">
          <Reveal>
            <span className="eyebrow">Scored where it can be checked</span>
            <h2 className="display mt-4 max-w-2xl text-[clamp(2rem,3.6vw,3rem)] text-fg">
              A 0.124 Brier on the ForecastBench dataset split.
            </h2>
            <p className="mt-5 max-w-2xl text-base leading-relaxed text-fg-soft">
              On the benchmark the field runs, where the strongest bots already out-forecast human
              superforecasters, Vati scores ahead of the crowd in our own leak-free testing. Lower is
              better.
            </p>
          </Reveal>
          <div className="mt-14 space-y-6">
            {BENCH.map((b, i) => (
              <Reveal key={b.label} delay={i * 0.08}>
                <div className="flex items-center gap-5">
                  <span className="w-64 shrink-0 text-sm text-fg-soft">{b.label}</span>
                  <div className="h-9 flex-1 overflow-hidden rounded-md bg-white/[0.04]">
                    <div
                      className={`flex h-full items-center justify-end rounded-md px-3 ${
                        b.accent ? "bg-accent text-[#062020]" : "bg-white/10 text-fg"
                      }`}
                      style={{ width: `${b.pct}%` }}
                    >
                      <span className="mono text-sm tnum">{b.score.toFixed(3)}</span>
                    </div>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── Calls on the record (dark) ──────────────────────────────────────── */}
      <section id="record" className="border-t border-line bg-dark">
        <div className="mx-auto max-w-[1280px] px-6 py-32 lg:px-14">
          <Reveal>
            <span className="eyebrow">On the record</span>
            <h2 className="display mt-4 max-w-2xl text-[clamp(2rem,3.6vw,3rem)] text-fg">
              Calls we are making now, each with a number that can prove us wrong.
            </h2>
            <p className="mt-5 max-w-2xl text-base leading-relaxed text-fg-soft">
              These are our positions, on the record. Not stock tips. Each one says where the binding
              constraint lands and ties that to a dated metric you can check. Filter by domain.
            </p>
          </Reveal>
          <div className="mt-12">
            <ExamplePredictions />
          </div>
        </div>
      </section>

      {/* ── Feature grid / pillars (cream) ──────────────────────────────────── */}
      <section className="bg-cream text-ink">
        <div className="mx-auto max-w-[1280px] px-6 py-32 lg:px-14">
          <Reveal>
            <span className="eyebrow">How we work</span>
            <h2 className="display mt-4 max-w-xl text-[clamp(2rem,3.6vw,3rem)] text-ink">
              From a faint early signal to a call you can hold us to.
            </h2>
          </Reveal>
          <div className="mt-14 grid gap-5 md:grid-cols-3">
            {PILLARS.map((p, i) => (
              <Reveal key={p.title} delay={i * 0.08}>
                <div className="card-cream h-full p-7">
                  <div className="grid h-11 w-11 place-items-center rounded-xl border border-ink-line text-accent-deep">
                    <Icon path={p.icon} />
                  </div>
                  <h3 className="display mt-6 text-xl text-ink">{p.title}</h3>
                  <p className="mt-3 text-sm leading-relaxed text-ink-soft">{p.body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── Meet Vati — model rows (cream) ──────────────────────────────────── */}
      <section id="vati" className="bg-cream text-ink">
        <div className="mx-auto max-w-[1280px] px-6 pb-32 lg:px-14">
          <Reveal>
            <span className="eyebrow">The instrument</span>
            <h2 className="display mt-4 max-w-xl text-[clamp(2rem,3.6vw,3rem)] text-ink">
              Meet Vati and the gate that keeps it honest.
            </h2>
          </Reveal>
          <div className="mt-12">
            {MODELS.map((m, i) => (
              <Reveal key={m.name} delay={i * 0.08}>
                <div className={`grid gap-8 py-10 md:grid-cols-[0.8fr_1.2fr] ${i > 0 ? "rule-cream" : ""}`}>
                  <div>
                    <div className="flex items-center gap-3">
                      <span className="grid h-10 w-10 place-items-center rounded-xl bg-accent-tint text-accent-deep">
                        <Icon path="M12 2l2.4 7.2H22l-6 4.4 2.3 7.4L12 16.8 5.7 21l2.3-7.4-6-4.4h7.6L12 2z" />
                      </span>
                      <h3 className="display text-2xl text-ink">{m.name}</h3>
                    </div>
                    <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2">
                      {m.tags.map((t) => (
                        <span key={t} className="tag">{t}</span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-lg leading-snug text-ink">
                      <span className="font-medium">{m.lead}</span>
                    </p>
                    <p className="mt-3 text-sm leading-relaxed text-ink-soft">{m.body}</p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── Who we work with (cream) ────────────────────────────────────────── */}
      <section className="bg-cream text-ink">
        <div className="mx-auto max-w-[1280px] px-6 pb-32 lg:px-14">
          <div className="grid gap-12 md:grid-cols-[0.85fr_1.15fr]">
            <Reveal>
              <span className="eyebrow">Who we work with</span>
              <h2 className="display mt-4 text-[clamp(2rem,3.4vw,2.7rem)] text-ink">
                For the people who have to call it before the crowd does.
              </h2>
              <a href="mailto:research@vaticinus.com?subject=Working%20with%20Vaticinus"
                className="pill-primary mt-7">
                Talk to the lab
              </a>
            </Reveal>
            <div>
              {USE_CASES.map((u, i) => (
                <Reveal key={u.role} delay={i * 0.05}>
                  <div className={`flex items-start justify-between gap-8 py-5 ${i > 0 ? "rule-cream" : ""}`}>
                    <h3 className="w-44 shrink-0 text-base font-medium text-ink">{u.role}</h3>
                    <p className="flex-1 text-sm leading-relaxed text-ink-soft">{u.line}</p>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Graded in public (dark) — replaces testimonials, no fabricated proof ─ */}
      <section className="border-t border-line bg-dark">
        <div className="mx-auto max-w-[1280px] px-6 py-32 lg:px-14">
          <Reveal>
            <span className="eyebrow">Graded in public</span>
            <h2 className="display mt-4 max-w-2xl text-[clamp(2rem,3.6vw,3rem)] text-fg">
              We would rather show the score than the pitch.
            </h2>
          </Reveal>
          <div className="mt-14 grid gap-5 sm:grid-cols-3">
            {[
              { n: 8, suffix: "B", label: "Parameters in Vati, fine-tuned on 29,445 leak-free reasoning traces across 24 domains." },
              { n: 12, label: "Forecasts live on the Metaculus Cup under the handle vaticinus, scored as questions resolve." },
              { n: 53, label: "Calls in our sealed record, each dated before the fact and Brier-scored at resolution." },
            ].map((m) => (
              <Reveal key={m.label}>
                <div className="card-dark h-full p-8">
                  <div className="display tnum text-5xl text-fg">
                    <Counter value={m.n} suffix={m.suffix ?? ""} />
                  </div>
                  <p className="mt-4 text-sm leading-relaxed text-fg-soft">{m.label}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── Leak-free by discipline (dark) ──────────────────────────────────── */}
      <section id="about" className="border-t border-line bg-dark">
        <div className="mx-auto max-w-[1280px] px-6 py-32 lg:px-14">
          <div className="grid gap-12 md:grid-cols-2 md:items-center">
            <Reveal>
              <span className="eyebrow">The lab</span>
              <h2 className="display mt-4 text-[clamp(2rem,3.6vw,3rem)] text-fg">
                Leak-free by discipline. The honesty is the credential.
              </h2>
            </Reveal>
            <Reveal delay={0.1}>
              <p className="text-base leading-relaxed text-fg-soft">
                We do not deal in vision decks. We commit to a number, lock it, and let the score
                settle the argument. The one rule we never bend is leak control: a forecast is only
                worth something if the model could not already know the answer, so everything is dated
                and nothing is graded on what it could have read after the fact. It is the only
                credential worth having in this work, and it is how we intend to win.
              </p>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ── Closing CTA (cream) ─────────────────────────────────────────────── */}
      <section className="bg-cream text-ink">
        <div className="mx-auto max-w-[1280px] px-6 py-36 text-center lg:px-14">
          <Reveal>
            <h2 className="display mx-auto max-w-3xl text-[clamp(2.4rem,5vw,3.8rem)] text-ink">
              The future, called early — and scored when it arrives.
            </h2>
            <p className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-ink-soft">
              Point us at your domain and we will tell you where the binding constraint moves next, and
              the exact number that would tell you we got it wrong.
            </p>
            <div className="mt-9 flex justify-center">
              <a href="mailto:research@vaticinus.com?subject=Working%20with%20Vaticinus" className="pill-primary">
                Talk to the lab
              </a>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ── Footer (dark) ───────────────────────────────────────────────────── */}
      <footer className="border-t border-line bg-dark">
        <div className="mx-auto max-w-[1280px] px-6 py-14 lg:px-14">
          <div className="flex flex-col items-start justify-between gap-6 md:flex-row md:items-center">
            <a href="#top" className="flex items-center gap-2 text-fg">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path d="M12 2.2 20.5 7v10L12 21.8 3.5 17V7L12 2.2Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
                <path d="M12 7.5 16.4 10v4L12 16.5 7.6 14v-4L12 7.5Z" fill="currentColor" />
              </svg>
              <span className="display text-base">vaticinus</span>
            </a>
            <nav className="flex flex-wrap gap-6 text-sm text-fg-soft">
              <a href="#method" className="transition-colors hover:text-fg">Method</a>
              <a href="#record" className="transition-colors hover:text-fg">Record</a>
              <a href="#about" className="transition-colors hover:text-fg">The lab</a>
              <a href="mailto:research@vaticinus.com" className="transition-colors hover:text-fg">
                research@vaticinus.com
              </a>
            </nav>
          </div>
          <div className="mt-8 border-t border-line pt-6 text-xs text-fg-dim">
            © 2026 Vaticinus. A forecasting research lab in Berlin. Vati is our model, graded in public.
          </div>
        </div>
      </footer>
    </div>
  );
}
