"use client";

import { motion, useScroll, useTransform, useReducedMotion } from "motion/react";

/**
 * Slim header that stays out of the way over the hero (the large wordmark
 * carries the brand there) and fades in once you scroll past it.
 */
export default function Header() {
  const { scrollY } = useScroll();
  const reduce = useReducedMotion();
  const opacity = useTransform(scrollY, [0, 480, 640], [0, 0, 1]);
  const y = useTransform(scrollY, [480, 640], [-10, 0]);

  return (
    <motion.header
      style={reduce ? undefined : { opacity, y }}
      className="fixed inset-x-0 top-0 z-40 border-b border-line bg-marble/75 backdrop-blur-md"
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between px-8 py-4">
        <span className="font-display text-[0.82rem] tracking-monument text-ink">
          VATICINUS
        </span>
        <a
          href="mailto:access@vaticinus.com?subject=Introduction"
          className="font-sans text-[0.7rem] uppercase tracking-[0.2em] text-ink-soft transition-colors hover:text-gold"
        >
          <span className="cta-rule">Access by introduction</span>
        </a>
      </div>
    </motion.header>
  );
}
