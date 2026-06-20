import { getCloudflareContext } from "@opennextjs/cloudflare";

// Keep a background task alive past client disconnect. On Cloudflare, when the browser closes
// mid-stream the request is cancelled and the isolate can be torn down; registering the work with
// the execution context's waitUntil lets it run to completion (and persist its result) anyway, so
// a play or contact search the user kicked off is finished and saved when they come back. Routes
// that persist their result server-side on completion (capture, contacts) get durable runs from
// this. Best-effort: in dev / non-Cloudflare runtimes there is no context, so it is a no-op and
// the work still runs inline.
export function keepAlive(work: Promise<unknown>): void {
  try {
    getCloudflareContext().ctx.waitUntil(work);
  } catch {
    // No Cloudflare execution context (local dev, other runtimes): the caller still awaits the
    // work inline, so nothing is lost; it just is not protected against mid-stream disconnect.
  }
}
