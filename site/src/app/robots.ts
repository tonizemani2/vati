import type { MetadataRoute } from "next";

export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/api/", "/understand/", "/understand-data/"],
      },
      {
        userAgent: [
          "GPTBot",
          "OAI-SearchBot",
          "ChatGPT-User",
          "ClaudeBot",
          "Claude-SearchBot",
          "Claude-User",
          "PerplexityBot",
        ],
        allow: "/",
        disallow: ["/api/", "/understand/", "/understand-data/"],
      },
      {
        userAgent: [
          "Amazonbot",
          "Applebot-Extended",
          "Bytespider",
          "CCBot",
          "anthropic-ai",
          "cohere-ai",
          "Google-Extended",
          "meta-externalagent",
        ],
        disallow: "/",
      },
    ],
    sitemap: "https://vaticinus.com/sitemap.xml",
    host: "https://vaticinus.com",
  };
}
