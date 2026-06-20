"use client";

import { useState } from "react";
import { motion, useScroll, useMotionValueEvent } from "motion/react";

const LINKS = [
  { label: "Method", href: "#method" },
  { label: "Record", href: "#record" },
  { label: "Vati", href: "#vati" },
  { label: "The lab", href: "#about" },
];

/** Hexagonal mark — small geometric logo to the left of the wordmark. */
function Mark() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M12 2.2 20.5 7v10L12 21.8 3.5 17V7L12 2.2Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M12 7.5 16.4 10v4L12 16.5 7.6 14v-4L12 7.5Z" fill="currentColor" />
    </svg>
  );
}

/**
 * Top chrome: a thin announcement bar over a transparent nav that settles into
 * a tinted, blurred fill once you scroll past the hero lead.
 */
export default function Header() {
  const { scrollY } = useScroll();
  const [solid, setSolid] = useState(false);
  useMotionValueEvent(scrollY, "change", (y) => setSolid(y > 24));

  return (
    <div className="fixed inset-x-0 top-0 z-50">
      {/* announcement bar */}
      <a
        href="#record"
        className="flex items-center justify-center gap-2 bg-dark-2 px-4 py-1.5 text-center text-xs text-fg-soft transition-colors hover:text-fg"
      >
        <span className="hidden sm:inline">Vati is live on the Metaculus Cup, scored as questions resolve</span>
        <span className="sm:hidden">Vati is live on the Metaculus Cup</span>
        <span className="text-accent">See the record →</span>
      </a>

      <motion.header
        className={`transition-colors duration-300 ${
          solid ? "border-b border-line bg-dark/80 backdrop-blur-md" : "border-b border-transparent"
        }`}
      >
        <div className="mx-auto flex max-w-[1280px] items-center justify-between px-6 py-4 lg:px-14">
          <a href="#top" className="flex items-center gap-2 text-fg">
            <Mark />
            <span className="display text-[1.18rem] font-normal tracking-tight">vaticinus</span>
          </a>

          <nav className="hidden items-center gap-1 md:flex">
            {LINKS.map((l) => (
              <a
                key={l.href}
                href={l.href}
                className="rounded-full px-4 py-1.5 text-sm text-fg-soft transition-colors hover:text-fg"
              >
                {l.label}
              </a>
            ))}
          </nav>

          <a
            href="mailto:research@vaticinus.com?subject=Vaticinus%20research"
            className="pill-soft on-dark text-sm"
          >
            Get in touch
          </a>
        </div>
      </motion.header>
    </div>
  );
}
