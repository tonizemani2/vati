const UNDERSTAND_PIN = "258036";

export type PagesEnv = {
  ASSETS: {
    fetch(request: Request): Promise<Response>;
  };
};

export function authorized(request: Request): boolean {
  const url = new URL(request.url);
  return url.searchParams.get("token") === UNDERSTAND_PIN;
}

export function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
      "X-Robots-Tag": "noindex, nofollow",
    },
  });
}

export async function privateAsset(
  request: Request,
  env: PagesEnv,
  assetPath: string,
): Promise<Response> {
  if (!authorized(request)) return json(403, { error: "invalid token" });

  const url = new URL(request.url);
  url.pathname = assetPath;
  url.search = "";

  const res = await env.ASSETS.fetch(new Request(url.toString(), request));
  if (!res.ok) return json(404, { error: "not found" });

  const headers = new Headers(res.headers);
  headers.set("Cache-Control", "private, no-store");
  headers.set("X-Robots-Tag", "noindex, nofollow");
  return new Response(res.body, { status: res.status, headers });
}
