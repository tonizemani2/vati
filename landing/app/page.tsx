import Header from "@/components/Header";
import { Reveal, Lines } from "@/components/Reveal";
import Counter from "@/components/Counter";
import LayerVein from "@/components/LayerVein";

const ACCESS = "mailto:access@vaticinus.com?subject=Introduction";

/* One label for one intent, used in the hero, here, and the footer. */
function AccessLink({ className = "" }: { className?: string }) {
  return (
    <a
      href={ACCESS}
      className={`group inline-flex items-center gap-2 font-sans text-[0.74rem] uppercase tracking-[0.22em] text-ink transition-colors hover:text-gold ${className}`}
    >
      <span className="cta-rule">Access by introduction</span>
      <span aria-hidden className="transition-transform duration-500 ease-out group-hover:translate-x-1">
        &rarr;
      </span>
    </a>
  );
}

export default function Page() {
  return (
    <main className="relative">
      <Header />

      {/* ── Hero ──────────────────────────────────────────────────────── */}
      <section className="relative flex min-h-[100dvh] items-center overflow-hidden pt-24">
        <div className="absolute inset-0 -z-[1]">
          <div
            className="absolute inset-0 bg-cover bg-center"
            style={{ backgroundImage: "url('/images/hero.webp')" }}
          />
          <div className="absolute inset-0 bg-gradient-to-r from-marble via-marble/88 to-marble/25" />
          <div className="absolute inset-0 bg-gradient-to-t from-marble/75 via-transparent to-marble/45" />
        </div>

        <div className="mx-auto w-full max-w-6xl px-6 sm:px-8">
          <div className="max-w-2xl">
            {/* dictionary lockup: the brand signature, one unit */}
            <h1 className="font-display text-[clamp(2.8rem,9vw,5.5rem)] font-medium leading-none tracking-monument text-ink">
              VATICINUS
            </h1>
            <Reveal delay={0.2}>
              <p className="mt-5 font-sans text-[0.7rem] uppercase tracking-wide-label text-gold">
                adjective, Latin
              </p>
              <p className="mt-2 font-serif text-xl font-light italic leading-[1.2] text-ink-soft sm:text-2xl">
                Of a seer. Foretelling what is not yet seen.
              </p>
            </Reveal>

            <div className="mt-9 mb-8 h-px w-24 bg-gold/70" />

            <Lines
              lines={["We find where value moves next,", "before it is priced in."]}
              className="font-serif text-[clamp(2rem,5.2vw,3.4rem)] font-light leading-[1.12] text-ink text-balance"
            />
            <Reveal delay={0.6}>
              <p className="mt-7 max-w-xl font-sans text-[1.04rem] leading-relaxed text-ink-soft text-pretty">
                Calibrated, falsifiable forecasts of where scarcity migrates. Each
                one is dated, scored, and built to be proven wrong.
              </p>
              <div className="mt-9">
                <AccessLink />
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ── The thesis + the method (constraint → rent, three moves) ───── */}
      <section className="relative px-6 py-24 sm:px-8 sm:py-28">
        <div className="mx-auto max-w-6xl">
          <div className="grid items-start gap-12 md:grid-cols-12">
            <div className="md:col-span-5">
              <Lines
                lines={["Rent accrues to", "the binding constraint."]}
                className="font-serif text-[clamp(1.9rem,4vw,3rem)] font-light leading-[1.1] text-ink text-balance"
              />
            </div>
            <Reveal delay={0.15} className="md:col-span-6 md:col-start-7">
              <p className="font-sans text-[1.04rem] leading-relaxed text-ink-soft text-pretty">
                Scarcity is never still. It gathers at the constraint the world has
                not yet solved, and it moves the instant that constraint is
                understood. Find the constraint before it binds, and you find where
                value is about to go. The idea is simple. Seeing it early, and being
                willing to be scored, is not.
              </p>
            </Reveal>
          </div>

          {/* three moves, as an open sequence under one gold rule (not cards) */}
          <div className="mt-20 grid gap-px overflow-hidden border-t border-gold/40 sm:grid-cols-3">
            {[
              {
                n: "01",
                h: "Locate the constraint",
                b: "Read the world's record at full scale to find the input everything else will soon depend on.",
              },
              {
                n: "02",
                h: "Test if it is priced",
                b: "A correct call already in the price is worth nothing. We read the narrative, the forecasters, and the tape.",
              },
              {
                n: "03",
                h: "Commit, dated",
                b: "State the claim, the date it resolves, and the condition that would prove it wrong. Then keep the score.",
              },
            ].map((s, i) => (
              <Reveal key={s.n} delay={i * 0.12}>
                <div className="h-full pt-7 sm:pr-8">
                  <span className="tnum font-display text-2xl text-gold">{s.n}</span>
                  <h3 className="mt-4 font-serif text-2xl font-normal leading-snug text-ink">
                    {s.h}
                  </h3>
                  <p className="mt-3 max-w-xs font-sans text-[0.96rem] leading-relaxed text-ink-soft">
                    {s.b}
                  </p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── The nine layers (the vein) ────────────────────────────────── */}
      <section className="relative overflow-hidden px-6 py-24 sm:px-8 sm:py-28">
        <div
          className="absolute inset-y-0 right-0 -z-[1] hidden w-2/5 bg-cover bg-center opacity-[0.5] md:block"
          style={{ backgroundImage: "url('/images/scale.webp')" }}
        />
        <div className="absolute inset-0 -z-[1] bg-gradient-to-r from-marble via-marble to-marble/55" />

        <div className="mx-auto max-w-6xl">
          <div className="max-w-2xl">
            <Reveal>
              <h2 className="font-serif text-[clamp(1.9rem,4vw,3rem)] font-light leading-[1.1] text-ink text-balance">
                From frontier to price, in nine layers.
              </h2>
            </Reveal>
            <Reveal delay={0.15}>
              <p className="mt-6 max-w-xl font-sans text-[1.04rem] leading-relaxed text-ink-soft text-pretty">
                Every forecast is placed on one map. We trace value down the chain
                of dependence, layer by layer, to the point where it concentrates.
              </p>
            </Reveal>
          </div>

          {/* read-at-scale figures, hairline-divided, no boxes */}
          <Reveal delay={0.2}>
            <div className="mt-12 flex flex-wrap divide-line border-y border-line sm:divide-x">
              {[
                { v: <Counter value={1.4} decimals={1} suffix="M" />, l: "Papers, filings, patents read" },
                { v: <Counter value={9} />, l: "Causal layers, frontier to price" },
                { v: <span>100%</span>, l: "Dated and falsifiable" },
              ].map((s, i) => (
                <div key={i} className="flex-1 py-6 pr-8 sm:px-8 sm:first:pl-0">
                  <div className="tnum font-display text-3xl text-gold sm:text-4xl">{s.v}</div>
                  <div className="mt-2 font-sans text-[0.68rem] uppercase tracking-[0.16em] text-ink-soft">
                    {s.l}
                  </div>
                </div>
              ))}
            </div>
          </Reveal>

          <div className="mt-16">
            <LayerVein />
          </div>

          <Reveal delay={0.2}>
            <p className="mt-12 max-w-2xl font-sans text-[0.98rem] leading-relaxed text-ink-soft text-pretty">
              <span className="text-ink">Value concentrates in the dependency and supply layers.</span>{" "}
              Market pricing is the gate: a call that is correct and already priced
              carries no edge. The whole craft is finding the layer the crowd has
              not yet reached.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ── What a call looks like (the specimen) ─────────────────────── */}
      <section className="relative px-6 py-24 sm:px-8 sm:py-28">
        <div className="mx-auto max-w-6xl">
          <div className="grid items-end gap-12 md:grid-cols-12">
            <Reveal className="md:col-span-7">
              <h2 className="font-serif text-[clamp(1.9rem,4vw,3rem)] font-light leading-[1.1] text-ink text-balance">
                What a call looks like.
              </h2>
              <p className="mt-6 max-w-md font-sans text-[1.04rem] leading-relaxed text-ink-soft text-pretty">
                Not a story. A claim with a date attached and a clear way for it to
                die. The financial instrument is optional. The physical constraint
                is the point.
              </p>
            </Reveal>
          </div>

          <Reveal delay={0.15}>
            <article className="mt-12 rounded-sm border border-line bg-marble-bright/70 shadow-[0_40px_90px_-45px_rgba(13,17,48,0.3)]">
              <div className="grid gap-px md:grid-cols-12">
                {/* claim */}
                <div className="border-b border-line p-8 sm:p-10 md:col-span-7 md:border-b-0 md:border-r">
                  <div className="flex items-center justify-between">
                    <span className="font-sans text-[0.66rem] uppercase tracking-[0.22em] text-gold">
                      Specimen
                    </span>
                    <span className="tnum font-sans text-[0.66rem] uppercase tracking-[0.16em] text-ink-soft">
                      Horizon 4 yr
                    </span>
                  </div>
                  <p className="mt-6 font-serif text-[1.45rem] font-light leading-[1.3] text-ink">
                    Over four years, antibody manufacturing reorganizes around one
                    bottleneck: the capture resin that purifies every dose.
                    Consensus prices the drugs. We price the resin.
                  </p>
                  <p className="mt-6 font-sans text-[0.86rem] uppercase tracking-[0.14em] text-ink-soft">
                    Mispricing: the constraint sits one layer down.
                  </p>
                </div>

                {/* ledger */}
                <dl className="divide-y divide-line p-8 sm:p-10 md:col-span-5">
                  {[
                    ["Consensus believes", "Capacity scales with plant build-out."],
                    ["We predict", "Margin migrates to the cornered purification input."],
                    ["Resolves", "2029-12-31, on resin supplier margin and lead time."],
                    ["Kill criteria", "A drop-in substitute reaches commercial scale."],
                    ["Brier at resolution", "Pending"],
                  ].map(([k, v]) => (
                    <div key={k} className="flex flex-col gap-1 py-3 first:pt-0 last:pb-0">
                      <dt className="font-sans text-[0.64rem] uppercase tracking-[0.18em] text-gold">
                        {k}
                      </dt>
                      <dd className="tnum font-sans text-[0.95rem] leading-snug text-ink">
                        {v}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            </article>
          </Reveal>
        </div>
      </section>

      {/* ── The principle (the single dark interlude) ─────────────────── */}
      <section className="relative flex min-h-[70dvh] items-center overflow-hidden bg-indigo px-6 py-32 sm:px-8">
        <div className="absolute inset-x-0 top-0 h-px bg-gold/30" />
        <div className="absolute inset-x-0 bottom-0 h-px bg-gold/30" />
        <div className="mx-auto max-w-3xl text-center">
          <Lines
            lines={["A forecast that cannot fail", "is not a forecast."]}
            className="font-serif text-[clamp(2rem,5vw,3.6rem)] font-light leading-[1.12] text-marble-bright text-balance"
          />
          <Reveal delay={0.4}>
            <p className="mx-auto mt-9 max-w-xl font-sans text-[1.04rem] leading-relaxed text-marble-bright/70 text-pretty">
              Each of ours carries its own undoing in advance, and is scored against
              what happened. We would rather be precisely wrong than vaguely right.
            </p>
          </Reveal>
        </div>
      </section>

      {/* ── The scoreboard (base rate by kind) ────────────────────────── */}
      <section className="relative px-6 py-24 sm:px-8 sm:py-28">
        <div className="mx-auto max-w-6xl">
          <div className="grid items-start gap-12 md:grid-cols-12">
            <div className="md:col-span-5">
              <Reveal>
                <h2 className="font-serif text-[clamp(1.9rem,4vw,3rem)] font-light leading-[1.1] text-ink text-balance">
                  We keep the score.
                </h2>
              </Reveal>
              <Reveal delay={0.15}>
                <p className="mt-6 max-w-sm font-sans text-[1.04rem] leading-relaxed text-ink-soft text-pretty">
                  Every call folds into a base rate: how often a kind of mispricing
                  actually pays. This is measured, not asserted.
                </p>
              </Reveal>
            </div>

            <Reveal delay={0.1} className="md:col-span-6 md:col-start-7">
              <div className="border-t border-line">
                {[
                  ["Constraint one layer down", 100],
                  ["Cost-curve breakout", 100],
                  ["Regime change", 25],
                  ["Horizon mispricing", 0],
                  ["Hot narrative, over-priced", 0],
                ].map(([label, pct]) => (
                  <div
                    key={label as string}
                    className="flex items-baseline justify-between gap-6 border-b border-line py-4"
                  >
                    <span className="font-sans text-[0.98rem] text-ink">{label}</span>
                    <span className="tnum font-display text-xl text-gold">{pct}%</span>
                  </div>
                ))}
              </div>
              <p className="mt-5 font-sans text-[0.82rem] leading-relaxed text-ink-soft">
                Retrodiction on a closed historical set. The live record is being
                built, one dated call at a time.
              </p>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ── Discipline (closing statement over marble) ────────────────── */}
      <section className="relative flex min-h-[78dvh] items-center overflow-hidden px-6 py-32 sm:px-8">
        <div
          className="absolute inset-0 -z-[1] bg-cover bg-center"
          style={{ backgroundImage: "url('/images/discipline.webp')" }}
        />
        <div className="absolute inset-0 -z-[1] bg-gradient-to-r from-marble via-marble/82 to-marble/25" />
        <div className="mx-auto w-full max-w-6xl">
          <div className="max-w-2xl">
            <Lines
              lines={["How we measure is ours.", "That it can be checked is yours."]}
              className="font-serif text-[clamp(1.9rem,4.4vw,3.2rem)] font-light leading-[1.14] text-ink text-balance"
            />
            <Reveal delay={0.3}>
              <p className="mt-7 max-w-lg font-sans text-[1.04rem] leading-relaxed text-ink-soft text-pretty">
                What we publish is a discipline, not a narrative. Every forecast
                names the date it will be judged and the condition that would prove
                it wrong. We do not narrate. We resolve.
              </p>
              <div className="mt-9">
                <AccessLink />
              </div>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ── Footer ────────────────────────────────────────────────────── */}
      <footer className="relative border-t border-line px-6 py-16 sm:px-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-4 text-center">
          <span className="font-display text-lg tracking-monument text-ink">
            VATICINUS
          </span>
          <span className="font-serif text-base italic text-gold">
            We keep the score.
          </span>
          <span className="font-sans text-[0.68rem] uppercase tracking-[0.28em] text-ink-soft">
            vaticinus.com
          </span>
        </div>
      </footer>
    </main>
  );
}
