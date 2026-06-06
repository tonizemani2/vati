"use client";

import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

const EASE = [0.16, 1, 0.3, 1] as const;

/** Fade + rise a block the first time it enters view. */
export function Reveal({
  children,
  delay = 0,
  y = 22,
  className = "",
}: {
  children: ReactNode;
  delay?: number;
  y?: number;
  className?: string;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? false : { opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.9, delay, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

/**
 * Reveal a statement line by line as a soft staggered fade. No clip masks, so
 * italic descenders stay intact. Pass deliberate line breaks as an array.
 */
export function Lines({
  lines,
  className = "",
  lineClassName = "",
}: {
  lines: string[];
  className?: string;
  lineClassName?: string;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, amount: 0.4 }}
      variants={{ show: { transition: { staggerChildren: 0.11, delayChildren: 0.04 } } }}
    >
      {lines.map((line, i) => (
        <motion.span
          key={i}
          className={`block ${lineClassName}`}
          variants={{
            hidden: { opacity: 0, y: reduce ? 0 : 14 },
            show: { opacity: 1, y: 0, transition: { duration: 0.85, ease: EASE } },
          }}
        >
          {line}
        </motion.span>
      ))}
    </motion.div>
  );
}
