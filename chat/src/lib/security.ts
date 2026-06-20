export type RateLimitOptions = {
  bucket: string;
  limit: number;
  windowSeconds: number;
};

function clientKey(request: Request) {
  const ip =
    request.headers.get("CF-Connecting-IP") ||
    request.headers.get("x-real-ip") ||
    (request.headers.get("x-forwarded-for") || "").split(",")[0].trim() ||
    "anon";
  const ua = (request.headers.get("user-agent") || "ua").slice(0, 80);
  return `${ip}|${ua}`.replace(/[^a-zA-Z0-9:._|-]/g, "_");
}

export async function edgeRateLimit(
  request: Request,
  { bucket, limit, windowSeconds }: RateLimitOptions,
): Promise<Response | null> {
  try {
    const key = new Request(
      `https://ratelimit.local/${encodeURIComponent(bucket)}/${clientKey(request)}`,
    );
    const cache = (caches as unknown as { default: Cache }).default;
    const hit = await cache.match(key);
    const count = hit ? parseInt(await hit.text(), 10) || 0 : 0;
    if (count >= limit) {
      return new Response("rate limit", {
        status: 429,
        headers: {
          "Cache-Control": "no-store",
          "Retry-After": String(windowSeconds),
          "X-Content-Type-Options": "nosniff",
        },
      });
    }
    await cache.put(
      key,
      new Response(String(count + 1), {
        headers: { "Cache-Control": `max-age=${windowSeconds}` },
      }),
    );
  } catch {
    // Edge-cache rate limiting is a protective layer. If Cloudflare cache is
    // temporarily unavailable, do not turn that into a product outage.
  }
  return null;
}
