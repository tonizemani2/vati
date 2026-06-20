import type { Metadata } from "next";
import { RawSection } from "@/sections/raw";
import { SiteRuntime } from "@/sections/SiteRuntime";

export const metadata: Metadata = {
  title: "Privacy Policy - Vaticinus",
  description:
    "How Vaticinus handles contact enquiries, forecasting questions, analytics data, and public research material.",
  alternates: {
    canonical: "/privacy-policy/",
  },
};

export default function PrivacyPolicyPage() {
  return (
    <div className="page_wrap">
      <RawSection name="nav" />
      <main className="page_main legal-page" id="main">
        <section className="legal-hero u-section u-theme-dark">
          <div className="u-container-small">
            <a className="legal-back" href="/">
              Home
            </a>
            <h1>Privacy Policy</h1>
            <p>
              Vaticinus is a research and forecasting site. We collect the
              minimum information needed to answer enquiries, run the product,
              and protect the service.
            </p>
          </div>
        </section>

        <section className="legal-body u-section">
          <div className="u-container-small">
            <div className="legal-copy">
              <h2>What we collect</h2>
              <p>
                If you submit the work-with-us form, we receive the name, work
                email, organisation, role, timeline, and message you provide.
                If you use the chat app, the chat service may process your
                questions, account state, usage limits, and billing state where
                relevant.
              </p>

              <h2>How we use it</h2>
              <p>
                We use enquiry data to reply, scope research work, prevent spam,
                and maintain a dated record of buyer requests. We use product
                usage data to operate the chat, enforce rate limits, debug
                failures, and understand which public research surfaces are
                useful.
              </p>

              <h2>Processors</h2>
              <p>
                The site may use Cloudflare for hosting and security, Resend for
                contact email delivery, Cal.com for optional scheduling, Clerk
                for chat account management, and Stripe for billing inside the
                chat app. These services process data only to provide their
                respective functions.
              </p>

              <h2>Analytics</h2>
              <p>
                We do not sell visitor data. If analytics are enabled, they are
                used to understand aggregate site usage, search traffic, and
                broken paths. We keep the marketing site focused on public
                research and do not add hidden credential-collection pages.
              </p>

              <h2>Your choices</h2>
              <p>
                To ask about your data or request deletion of an enquiry, email
                toni@vaticinus.com. We may retain records required for security,
                accounting, dispute handling, or the integrity of public dated
                forecasts.
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
