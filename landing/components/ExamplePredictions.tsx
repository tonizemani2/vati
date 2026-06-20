"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";

type Card = {
  category: string;
  question: string;
  context: string;
  probability: number; // 0–100, our forecast
  rationale: string;
  horizon: string;
};

// Representative calls from Vati's tracked record. Each is a pre-consensus
// claim tied to a dated, falsifiable constraint metric.
const CARDS: Card[] = [
  {
    category: "Energy",
    question: "Grain-oriented electrical steel, not transformers, becomes the binding constraint on the US grid build-out.",
    context: "Everyone is pricing the transformer shortage. The deeper bottleneck is GOES, where capacity is concentrated and slow to add.",
    probability: 72,
    rationale: "The rent moves one layer below the shortage you can see. Origin premium and ex-region output share are what would prove it wrong.",
    horizon: "4-year horizon",
  },
  {
    category: "Geopolitics",
    question: "Weaponized export controls make ex-China refining capacity the binding constraint on critical minerals, not the mines.",
    context: "The Oct 2025 rare-earth megacontrol corners refining, not extraction. Mine supply can flex. Separation capacity cannot.",
    probability: 68,
    rationale: "A decree creates scarcity before the price catches up. Proven wrong by ex-China refined-output share and the origin premium.",
    horizon: "4-year horizon",
  },
  {
    category: "Labor",
    question: "Skilled electrical-trades labour, not equipment, is the binding constraint on US electrification.",
    context: "Capital and equipment scale faster than licensed electricians and linemen. The crew is the chokepoint.",
    probability: 64,
    rationale: "Proven wrong if electrician-wage growth lags transformer-PPI growth over the window. A labor force bending the supply graph.",
    horizon: "4-year horizon",
  },
  {
    category: "Technology",
    question: "Antibody-engineering rent lands on Protein-A capture resin, a cornered consumable, not the drugs themselves.",
    context: "As pipelines expand, the part that stays scarce is the purification ligand, and only a handful of suppliers make it.",
    probability: 61,
    rationale: "Classic razor-and-blade rent on a platform-locked consumable. Scored on supplier share and resin pricing, not any single ticker.",
    horizon: "5-year horizon",
  },
  {
    category: "Technology",
    question: "Spatial-transcriptomics value concentrates in platform-locked reagent consumables.",
    context: "The instrument is sold near-cost; the recurring rent is the proprietary reagent each run consumes.",
    probability: 58,
    rationale: "Lock-in at the consumable layer. The narrative is still quiet, so the structure is not yet in the price.",
    horizon: "5-year horizon",
  },
  {
    category: "Geopolitics",
    question: "BIS compute controls make advanced-packaging capacity the named US constraint on AI hardware.",
    context: "The Oct-2022 controls corner advanced computing; the durable bottleneck shifts to packaging and substrate.",
    probability: 66,
    rationale: "A decree is the scarcity-creating act. Tracked via export-control rule deltas, ahead of the price signal.",
    horizon: "3-year horizon",
  },
];

const CATEGORIES = ["All", "Energy", "Geopolitics", "Labor", "Technology"];

export default function ExamplePredictions() {
  const [active, setActive] = useState("All");
  const shown = active === "All" ? CARDS : CARDS.filter((c) => c.category === active);

  return (
    <div>
      <div className="mb-8 flex flex-wrap gap-2">
        {CATEGORIES.map((c) => (
          <button
            key={c}
            onClick={() => setActive(c)}
            className={`rounded-full border px-4 py-1.5 text-sm transition-colors ${
              active === c
                ? "border-accent bg-accent-tint text-accent"
                : "border-line text-fg-soft hover:border-line-strong hover:text-fg"
            }`}
          >
            {c}
          </button>
        ))}
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <AnimatePresence mode="popLayout">
          {shown.map((c) => (
            <motion.article
              key={c.question}
              layout
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
              className="card-dark flex flex-col gap-4 p-6"
            >
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center rounded-full border border-line bg-white/5 px-3 py-1 text-xs text-fg-soft">
                  {c.category}
                </span>
                <span className="text-xs text-fg-dim">{c.horizon}</span>
              </div>

              <h3 className="text-[1.05rem] font-medium leading-snug text-fg">{c.question}</h3>
              <p className="text-sm leading-relaxed text-fg-soft">{c.context}</p>

              <div className="mt-auto">
                <div className="mb-2 flex items-baseline justify-between">
                  <span className="text-xs uppercase tracking-wider text-fg-dim eyebrow">
                    Vati&apos;s read
                  </span>
                  <span className="tnum text-2xl font-semibold text-accent">{c.probability}%</span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/5">
                  <div
                    className="h-full rounded-full bg-accent"
                    style={{ width: `${c.probability}%` }}
                  />
                </div>
                <p className="mt-4 border-t border-line pt-4 text-sm leading-relaxed text-fg-soft">
                  {c.rationale}
                </p>
              </div>
            </motion.article>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
