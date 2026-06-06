"use client";

import { motion, useReducedMotion } from "motion/react";

/**
 * The nine causal layers, drawn as a single gold vein from frontier to price.
 * The two layers where value concentrates are lit; the pricing gate is marked.
 * Horizontal rail on desktop, vertical rail on mobile. The vein "draws" once on
 * entry (scaleX / scaleY, GPU-only), nodes rise in sequence behind it.
 */

const EASE = [0.16, 1, 0.3, 1] as const;

type Layer = { n: number; name: string; lit?: boolean; gate?: boolean };

const LAYERS: Layer[] = [
  { n: 1, name: "Frontier" },
  { n: 2, name: "Capability" },
  { n: 3, name: "Dependency", lit: true },
  { n: 4, name: "Supply", lit: true },
  { n: 5, name: "Demand" },
  { n: 6, name: "Capital" },
  { n: 7, name: "Pricing", gate: true },
  { n: 8, name: "Policy" },
  { n: 9, name: "Outcomes" },
];

function Node({ layer }: { layer: Layer }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      variants={{
        hidden: { opacity: 0, y: reduce ? 0 : 10 },
        show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: EASE } },
      }}
      className="relative flex flex-row items-center gap-4 md:flex-col md:gap-3"
    >
      {/* dot on the rail */}
      <span className="relative flex h-3.5 w-3.5 shrink-0 items-center justify-center">
        {layer.lit && (
          <span className="absolute h-6 w-6 rounded-full border border-gold/35" />
        )}
        <span
          className={
            layer.gate
              ? "h-3.5 w-3.5 rotate-45 border border-gold bg-marble"
              : layer.lit
                ? "h-3 w-3 rounded-full bg-gold"
                : "h-2.5 w-2.5 rounded-full bg-marble-deep ring-1 ring-line"
          }
        />
      </span>
      <div className="flex items-baseline gap-2 md:mt-1 md:flex-col md:items-center md:gap-1">
        <span className="tnum font-display text-[0.8rem] text-gold">
          {String(layer.n).padStart(2, "0")}
        </span>
        <span
          className={`font-sans text-[0.66rem] uppercase tracking-[0.18em] ${
            layer.lit ? "text-ink" : "text-ink-soft"
          }`}
        >
          {layer.name}
        </span>
      </div>
    </motion.div>
  );
}

export default function LayerVein() {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, amount: 0.4 }}
      variants={{ show: { transition: { staggerChildren: 0.09, delayChildren: 0.15 } } }}
      className="relative"
    >
      {/* horizontal rail (md+) */}
      <div className="pointer-events-none absolute inset-x-[5%] top-[6px] hidden md:block">
        <div className="h-px w-full bg-line" />
        <motion.div
          className="absolute inset-0 h-px origin-left bg-gradient-to-r from-gold/0 via-gold to-gold/40"
          initial={reduce ? false : { scaleX: 0 }}
          whileInView={{ scaleX: 1 }}
          viewport={{ once: true, amount: 0.4 }}
          transition={{ duration: 1.5, ease: EASE, delay: 0.1 }}
        />
      </div>

      {/* vertical rail (mobile) */}
      <div className="pointer-events-none absolute bottom-3 left-[6px] top-3 w-px md:hidden">
        <div className="h-full w-px bg-line" />
        <motion.div
          className="absolute inset-0 w-px origin-top bg-gradient-to-b from-gold via-gold to-gold/30"
          initial={reduce ? false : { scaleY: 0 }}
          whileInView={{ scaleY: 1 }}
          viewport={{ once: true, amount: 0.4 }}
          transition={{ duration: 1.5, ease: EASE, delay: 0.1 }}
        />
      </div>

      <div className="relative flex flex-col gap-6 md:flex-row md:justify-between md:gap-0">
        {LAYERS.map((l) => (
          <Node key={l.n} layer={l} />
        ))}
      </div>
    </motion.div>
  );
}
