import { defineCloudflareConfig } from "@opennextjs/cloudflare";

// Default config: caching disabled (the chat is dynamic, nothing to ISR-cache). This is
// all OpenNext needs to package the Next app as a Cloudflare Worker.
export default defineCloudflareConfig({});
