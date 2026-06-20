import type { MetadataRoute } from "next";

const SITE_URL = "https://vaticinus.com";
const updatedWeekly = new Date("2026-06-19T00:00:00.000Z");
const forecastDetailUpdated = new Date("2026-06-17T00:00:00.000Z");
const legalUpdated = new Date("2026-06-18T00:00:00.000Z");

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: `${SITE_URL}/`,
      lastModified: updatedWeekly,
      changeFrequency: "weekly",
      priority: 1,
    },
    {
      url: `${SITE_URL}/forecasts/`,
      lastModified: updatedWeekly,
      changeFrequency: "weekly",
      priority: 0.9,
    },
    {
      url: `${SITE_URL}/forecasts/ai-campus-power-claims/`,
      lastModified: forecastDetailUpdated,
      changeFrequency: "monthly",
      priority: 0.8,
    },
    {
      url: `${SITE_URL}/privacy-policy/`,
      lastModified: legalUpdated,
      changeFrequency: "yearly",
      priority: 0.2,
    },
    {
      url: `${SITE_URL}/terms-of-service/`,
      lastModified: legalUpdated,
      changeFrequency: "yearly",
      priority: 0.2,
    },
  ];
}
