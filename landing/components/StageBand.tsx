"use client";

import { motion } from "motion/react";

const STAGES = [
  "Frontier",
  "Capability",
  "Dependency graph",
  "Supply elasticity",
  "Demand",
  "Capital",
  "Pricing",
  "Policy",
  "Outcomes",
];
// the two layers where rent concentrates
const HOT = new Set(["Dependency graph", "Supply elasticity"]);

/**
 * Horizontal causal-spine band. Cells settle in left→right; the two layers
 * where value concentrates glow teal. Mirrors the original's token-stream band.
 */
export default function StageBand() {
  return (
    <div className="flex flex-wrap items-stretch gap-2">
      {STAGES.map((s, i) => {
        const hot = HOT.has(s);
        return (
          <motion.div
            key={s}
            initial={{ opacity: 0, y: 6 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: i * 0.07 }}
            className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
              hot
                ? "border-accent/40 bg-accent-tint text-fg"
                : "border-line bg-card/60 text-fg-soft"
            }`}
          >
            <span
              className={`mono text-xs ${hot ? "text-accent" : "text-fg-dim"}`}
            >
              {String(i + 1).padStart(2, "0")}
            </span>
            <span>{s}</span>
            {i < STAGES.length - 1 && (
              <span className="text-fg-dim" aria-hidden>
                →
              </span>
            )}
          </motion.div>
        );
      })}
    </div>
  );
}
