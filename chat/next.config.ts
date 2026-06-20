import type { NextConfig } from "next";
import { initOpenNextCloudflareForDev } from "@opennextjs/cloudflare";

const globalSecurityHeaders = [
  { key: "X-Robots-Tag", value: "noindex, nofollow" },
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin-allow-popups" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
];

// NOTE: deliberately NOT a static export (unlike ../site). This app has a streaming
// Route Handler (app/api/chat) and live server routes, so it deploys as a Cloudflare
// Worker via the OpenNext adapter (`pnpm ship`), not as Pages static assets.
const nextConfig: NextConfig = {
  // Disable reverse-proxy / compression buffering so token streaming flushes promptly.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: globalSecurityHeaders,
      },
      {
        source: "/api/:path*",
        headers: [
          { key: "X-Accel-Buffering", value: "no" },
          { key: "Cache-Control", value: "no-store" },
        ],
      },
    ];
  },
};

export default nextConfig;

// Lets `next dev` talk to the Cloudflare bindings (env, etc.) during local development.
initOpenNextCloudflareForDev();
