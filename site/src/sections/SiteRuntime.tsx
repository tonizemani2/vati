"use client";

import { useEffect } from "react";
import Swiper from "swiper";
import { Navigation, Pagination } from "swiper/modules";
import "swiper/css";
import "swiper/css/navigation";
import "swiper/css/pagination";

// The Rive runtime is loaded as a self-hosted UMD script (public/rive/rive.js)
// rather than the ESM package: under Turbopack the bundled ESM build never
// initiates its wasm load, leaving the canvas blank. The UMD build works.
type RiveGlobal = {
  Rive: new (opts: Record<string, unknown>) => RiveInstance;
  Layout: new (opts: Record<string, unknown>) => unknown;
  Fit: Record<string, unknown>;
  Alignment: Record<string, unknown>;
  RuntimeLoader: { setWasmUrl: (u: string) => void };
};
type RiveInstance = {
  resizeDrawingSurfaceToCanvas: () => void;
  stateMachineInputs: (sm: string) => Array<{ name: string; fire?: () => void }>;
  cleanup: () => void;
};

let riveLoader: Promise<RiveGlobal> | null = null;
function loadRive(): Promise<RiveGlobal> {
  if (typeof window === "undefined") return Promise.reject();
  const w = window as unknown as { rive?: RiveGlobal };
  if (w.rive) return Promise.resolve(w.rive);
  if (riveLoader) return riveLoader;
  riveLoader = new Promise<RiveGlobal>((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "/rive/rive.js";
    s.async = true;
    s.onload = () => (w.rive ? resolve(w.rive) : reject());
    s.onerror = reject;
    document.head.appendChild(s);
  });
  return riveLoader;
}

// Faithful re-implementation of the original inline init scripts (Swiper carousels,
// filter tabs, contact/sample/video modals, nav banner) as a single client runtime.
// Mirrors docs/research/scripts-extracted/inline-{1,2,4,5,6,7,8}.js.
export function SiteRuntime() {
  useEffect(() => {
    const cleanups: Array<() => void> = [];

    // ---- Rive animations (the research-section "boxes" illustration) ----
    const riveHosts = document.querySelectorAll<HTMLElement>(
      '[data-animation-type="rive"]',
    );
    if (riveHosts.length) {
      loadRive()
        .then((R) => {
          R.RuntimeLoader.setWasmUrl("/rive/rive.wasm");
          riveHosts.forEach((host) => {
           try {
            const src = host.dataset.riveUrl;
            if (!src) return;
            // The captured fragment embeds the original (now-empty) Rive canvas;
            // remove it before mounting a fresh, runtime-driven one.
            host.querySelectorAll("canvas").forEach((c) => c.remove());
            const canvas = document.createElement("canvas");
            canvas.style.width = "100%";
            canvas.style.height = "100%";
            canvas.style.display = "block";
            host.appendChild(canvas);
            const stateMachine = host.dataset.riveStateMachine || undefined;
            // The "main" state machine starts on an empty state: fire "start"
            // to play the build, then the viewport trigger ("desktop"/"mobile")
            // to pick the layout (matches the live Webflow Rive integration).
            const playDiagram = () => {
              if (!stateMachine) return;
              const inputs = rive.stateMachineInputs(stateMachine) || [];
              const fire = (n: string) => {
                const i = inputs.find((x) => x.name === n);
                if (i && typeof i.fire === "function") i.fire();
              };
              fire("start");
              const want = window.innerWidth >= 992 ? "desktop" : "mobile";
              const t = setTimeout(() => fire(want), 150);
              cleanups.push(() => clearTimeout(t));
            };
            const rive = new R.Rive({
              src,
              canvas,
              autoplay: host.dataset.riveAutoplay !== "false",
              stateMachines: stateMachine,
              artboard: host.dataset.riveArtboard || undefined,
              layout: new R.Layout({
                fit: R.Fit.Contain,
                alignment: R.Alignment.Center,
              }),
              onLoad: () => {
                rive.resizeDrawingSurfaceToCanvas();
                playDiagram();
              },
            });
            const onResize = () => rive.resizeDrawingSurfaceToCanvas();
            window.addEventListener("resize", onResize);
            cleanups.push(() => {
              window.removeEventListener("resize", onResize);
              try {
                rive.cleanup();
              } catch {
                /* noop */
              }
              canvas.remove();
            });
           } catch {
             /* a single illustration failing must not break the rest of the runtime */
           }
          });
        })
        .catch(() => {
          /* runtime failed to load — illustration falls back to the static grid */
        });
    }

    // The captured fragments contain Swiper's POST-init DOM (stale inline transforms
    // + generated bullets). Reset each carousel to pristine markup before re-init.
    const resetSwiper = (root: HTMLElement | null, paginationSel: string) => {
      if (!root) return;
      const wrapper = root.querySelector<HTMLElement>(".swiper-wrapper");
      if (wrapper) wrapper.removeAttribute("style");
      root
        .querySelectorAll<HTMLElement>(".swiper-slide")
        .forEach((s) => s.removeAttribute("style"));
      const pag = document.querySelector(paginationSel);
      if (pag) pag.innerHTML = "";
    };

    const makeSwiper = (
      sel: string,
      paginationSel: string,
      arrowsSel: string,
      spaceBetween: number,
      breakpoints?: Record<number, { spaceBetween: number }>,
    ): Swiper | null => {
      const root = document.querySelector<HTMLElement>(sel);
      if (!root) return null;
      resetSwiper(root, paginationSel);
      return new Swiper(sel, {
        modules: [Navigation, Pagination],
        slidesPerView: "auto",
        spaceBetween,
        pagination: { el: paginationSel, clickable: true },
        navigation: {
          prevEl: `${arrowsSel} .arrow-prev`,
          nextEl: `${arrowsSel} .arrow-next`,
        },
        breakpoints,
      });
    };

    const sampleSwiper = makeSwiper(
      ".sampleqs-swiper",
      ".sampleqs-swiper-pagination",
      ".sampleqs-swiper-arrows",
      16,
    );
    const solutionSwiper = makeSwiper(
      ".solutions-swiper",
      ".solutions-swiper-pagination",
      ".solutions-swiper-arrows",
      20,
      { 991: { spaceBetween: 0 } },
    );
    const usecaseSwiper = makeSwiper(
      ".usecase-swiper",
      ".usecase-swiper-pagination",
      ".usecase-swiper-arrows",
      16,
    );
    [sampleSwiper, solutionSwiper, usecaseSwiper].forEach((s) =>
      cleanups.push(() => s?.destroy(true, true)),
    );

    // ---- Scroll-reveal: carousel cards fade in on scroll-into-view ----
    // The live site's only IX2 scroll animation: collection-list cards in these
    // three carousels fade (opacity 0→1) when the section enters the viewport.
    // Hidden state is applied in JS only, so with JS disabled cards stay visible;
    // these carousels are below the fold, so applying it on mount causes no flash.
    const setupReveal = (sectionSel: string, cardSel: string) => {
      const section = document.querySelector<HTMLElement>(sectionSel);
      if (!section) return;
      const cards = Array.from(
        section.querySelectorAll<HTMLElement>(cardSel),
      );
      if (!cards.length) return;
      cards.forEach((c) => {
        c.style.opacity = "0";
        c.style.transition = "opacity 0.5s ease";
        c.style.willChange = "opacity";
      });
      let done = false;
      const reveal = () => {
        if (done) return;
        done = true;
        cards.forEach((c, i) => {
          const t = setTimeout(() => {
            c.style.opacity = "1";
          }, i * 90);
          cleanups.push(() => clearTimeout(t));
        });
        io?.disconnect();
        clearTimeout(fallback);
      };
      const io =
        typeof IntersectionObserver !== "undefined"
          ? new IntersectionObserver(
              (entries) => {
                if (entries.some((e) => e.isIntersecting)) reveal();
              },
              { threshold: 0.15 },
            )
          : null;
      if (io) io.observe(section);
      else reveal();
      // belt-and-suspenders: never leave a card stuck hidden
      const fallback = setTimeout(reveal, 6000);
      cleanups.push(() => {
        io?.disconnect();
        clearTimeout(fallback);
      });
    };
    setupReveal(".sampleqs_wrap", ".sampleqs-card");
    setupReveal(".solutions_wrap", ".solutions-card");
    setupReveal(".use_cases_wrap", ".usecase-card");

    // ---- Filter tabs (sampleqs + usecases) ----
    const wireFilter = (
      tabSel: string,
      cardSel: string,
      cardTagSel: string,
      viewAllId: string,
      swiper: Swiper | null,
    ) => {
      const tabs = document.querySelectorAll<HTMLElement>(tabSel);
      const cards = document.querySelectorAll<HTMLElement>(cardSel);
      tabs.forEach((tab) => {
        const onClick = (e: Event) => {
          const current = e.currentTarget as HTMLElement;
          const selected = current.dataset.filter;
          tabs.forEach((x) => x.classList.remove("is-active"));
          current.classList.add("is-active");
          if (tab.id === viewAllId) {
            cards.forEach((c) => (c.style.display = "block"));
          } else {
            cards.forEach((c) => {
              const tags = c.querySelectorAll<HTMLElement>(cardTagSel);
              const match = Array.from(tags).some(
                (t) => t.dataset.filter === selected,
              );
              c.style.display = match ? "block" : "none";
            });
          }
          swiper?.update();
        };
        tab.addEventListener("click", onClick);
        cleanups.push(() => tab.removeEventListener("click", onClick));
      });
    };
    wireFilter(
      ".sampleqs-filter-tab",
      ".sampleqs-card",
      ".sampleqs-card-tag",
      "view-all-tab",
      sampleSwiper,
    );
    wireFilter(
      ".usecase-filter-tab",
      ".usecase-card",
      ".usecase-card-tag",
      "view-all-usecase",
      usecaseSwiper,
    );

    // ---- Contact modal ----
    const contactModal = document.querySelector("#contact-modal");
    const openContact = () => {
      contactModal?.classList.add("visible");
      document.body.classList.add("no-scroll");
    };
    const closeContact = () => {
      contactModal?.classList.remove("visible");
      document.body.classList.remove("no-scroll");
    };
    document.querySelectorAll<HTMLElement>("[data-contact]").forEach((b) => {
      b.addEventListener("click", openContact);
      cleanups.push(() => b.removeEventListener("click", openContact));
    });
    document
      .querySelectorAll<HTMLElement>(".contact-modal-close, .contact-modal-bg")
      .forEach((b) => {
        b.addEventListener("click", closeContact);
        cleanups.push(() => b.removeEventListener("click", closeContact));
      });

    // ---- Sample-question detail modal + accordions ----
    const sampleqsModal = document.querySelector("#sampleqs-modal");
    if (sampleqsModal) {
      const items = sampleqsModal.querySelectorAll<HTMLElement>(
        ".sampleqs-modal-item",
      );
      const resetItems = () =>
        items.forEach((i) => (i.style.display = "none"));
      resetItems();
      document
        .querySelectorAll<HTMLElement>("[data-samplemodal]")
        .forEach((btn) => {
          const onOpen = (e: Event) => {
            const key = (e.currentTarget as HTMLElement).dataset.samplemodal;
            items.forEach((i) => {
              if (i.dataset.samplemodal === key) i.style.display = "block";
            });
            sampleqsModal.classList.add("visible");
            document.body.classList.add("no-scroll");
          };
          btn.addEventListener("click", onOpen);
          cleanups.push(() => btn.removeEventListener("click", onOpen));
        });
      document
        .querySelectorAll<HTMLElement>(
          ".sampleqs-modal-close, .sampleqs-modal-bg, .sampleqs-modal-footer",
        )
        .forEach((btn) => {
          const onClose = (e: Event) => {
            e.stopPropagation();
            sampleqsModal.classList.remove("visible");
            resetItems();
            document.body.classList.remove("no-scroll");
          };
          btn.addEventListener("click", onClose);
          cleanups.push(() => btn.removeEventListener("click", onClose));
        });

      // rationale accordions
      sampleqsModal
        .querySelectorAll<HTMLElement>(".sampleqs-modal-accordion")
        .forEach((acc) => {
          const content = acc.querySelector<HTMLElement>(
            ".sampleqs-modal-acc-ans",
          );
          const setMax = (open: boolean) => {
            if (content)
              content.style.maxHeight = open ? `${content.scrollHeight}px` : "0px";
          };
          if (content) content.style.maxHeight = "0px";
          if (acc.classList.contains("active")) setMax(true);
          const tab = acc.querySelector<HTMLElement>(".sampleqs-modal-acc-que");
          if (!tab) return;
          const onToggle = () => {
            acc.classList.toggle("active");
            setMax(acc.classList.contains("active"));
          };
          tab.addEventListener("click", onToggle);
          cleanups.push(() => tab.removeEventListener("click", onToggle));
        });
    }

    // ---- Video modal ----
    const vidModal = document.querySelector<HTMLElement>(".video-modal");
    const videoElem = vidModal?.querySelector<HTMLVideoElement>("video");
    if (vidModal && videoElem) {
      document.querySelectorAll<HTMLElement>("[data-video]").forEach((slide) => {
        const onPlay = (e: Event) => {
          const src = (e.currentTarget as HTMLElement).dataset.video;
          if (src) videoElem.src = src;
          vidModal.classList.add("show");
          void videoElem.play().catch(() => {});
        };
        slide.addEventListener("click", onPlay);
        cleanups.push(() => slide.removeEventListener("click", onPlay));
      });
      const close = vidModal.querySelector<HTMLElement>(".vid-modal-close");
      const onCloseVid = () => {
        vidModal.classList.remove("show");
        videoElem.src = "";
      };
      close?.addEventListener("click", onCloseVid);
      cleanups.push(() => close?.removeEventListener("click", onCloseVid));
    }

    // ---- Nav banner dismiss ----
    if (sessionStorage.getItem("hide-nav-banner") === "true") {
      document.documentElement.classList.add("hide-nav-banner");
    }
    document
      .querySelectorAll<HTMLElement>(".nav_banner_close_wrap")
      .forEach((button) => {
        const onClose = () => {
          sessionStorage.setItem("hide-nav-banner", "true");
          document.documentElement.classList.add("hide-nav-banner");
        };
        button.addEventListener("click", onClose);
        cleanups.push(() => button.removeEventListener("click", onClose));
      });

    // ---- Mobile nav menu toggle (Webflow's collapse JS isn't bundled) ----
    document
      .querySelectorAll<HTMLElement>(".nav_wrap.is-mobile .nav_btn_wrap")
      .forEach((btn) => {
        const nav = btn.closest<HTMLElement>(".nav_wrap.is-mobile");
        if (!nav) return;
        const menu = nav.querySelector<HTMLElement>(".nav_menu_wrap");
        const setOpen = (open: boolean) => {
          if (open && menu) {
            // anchor the panel just under the bar so the logo + button stay tappable
            menu.style.top = `${Math.round(nav.getBoundingClientRect().bottom)}px`;
          }
          nav.classList.toggle("is-open", open);
          btn.classList.toggle("w--open", open);
          btn.setAttribute("aria-expanded", String(open));
          document.documentElement.classList.toggle("nav-locked", open);
        };
        const onToggle = () => setOpen(!nav.classList.contains("is-open"));
        btn.addEventListener("click", onToggle);
        cleanups.push(() => btn.removeEventListener("click", onToggle));
        // close when a link or the backdrop is tapped
        nav
          .querySelectorAll<HTMLElement>(
            ".nav_links_link, .nav_links_link-2, .nav_menu_backdrop",
          )
          .forEach((c) => {
            const onClose = () => setOpen(false);
            c.addEventListener("click", onClose);
            cleanups.push(() => c.removeEventListener("click", onClose));
          });
      });

    return () => cleanups.forEach((fn) => fn());
  }, []);

  return null;
}
