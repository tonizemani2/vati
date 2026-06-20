import type { Metadata } from "next";
import { RawSection } from "@/sections/raw";
import { SiteRuntime } from "@/sections/SiteRuntime";

export const metadata: Metadata = {
  title: "Terms of Service - Vaticinus",
  description:
    "Terms for using Vaticinus public research, forecast boards, contact forms, and chat surfaces.",
  alternates: {
    canonical: "/terms-of-service/",
  },
};

export default function TermsOfServicePage() {
  return (
    <div className="page_wrap">
      <RawSection name="nav" />
      <main className="page_main legal-page" id="main">
        <section className="legal-hero u-section u-theme-dark">
          <div className="u-container-small">
            <a className="legal-back" href="/">
              Home
            </a>
            <h1>Terms of Service</h1>
            <p>
              Vaticinus publishes research and probabilistic forecasts. The
              output is information and analysis, not a promise of outcome or a
              substitute for professional advice.
            </p>
          </div>
        </section>

        <section className="legal-body u-section">
          <div className="u-container-small">
            <div className="legal-copy">
              <h2>Use of the site</h2>
              <p>
                You may read public pages, download public forecast boards, and
                submit legitimate enquiries. Do not attack the service, scrape
                private endpoints, impersonate others, submit spam, or use the
                site to distribute malicious, deceptive, or unlawful material.
              </p>

              <h2>Research and forecasts</h2>
              <p>
                Forecasts are dated analytical views with uncertainty attached.
                They may be wrong. Nothing on the site is investment, legal,
                tax, medical, or engineering advice. You are responsible for
                your own decisions and diligence.
              </p>

              <h2>Public records</h2>
              <p>
                The value of Vaticinus is the dated record. We may preserve
                public forecast boards, timestamps, kill criteria, and scoring
                notes to keep that record auditable.
              </p>

              <h2>External services</h2>
              <p>
                Links to the chat app, scheduling, official sources, and PDFs
                are provided for convenience. External services have their own
                terms and privacy practices.
              </p>

              <h2>Contact</h2>
              <p>
                Questions about these terms can be sent to toni@vaticinus.com.
              </p>
            </div>
          </div>
        </section>
        <RawSection name="footer" />
      </main>
      <RawSection name="contactModal" />
      <SiteRuntime />
    </div>
  );
}
