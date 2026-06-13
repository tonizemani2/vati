import { readFileSync } from "fs";
import { join } from "path";

// Server-only: reads the exact (localized, script-stripped) Webflow fragment at build
// time and injects it under the vendored stylesheet. The display:contents wrapper
// keeps the original <section> as the layout-participating element.
export function loadFragment(name: string): string {
  return readFileSync(
    join(process.cwd(), "src/sections/fragments", `${name}.html`),
    "utf8",
  );
}

export function RawSection({ name }: { name: string }) {
  return (
    <div
      style={{ display: "contents" }}
      dangerouslySetInnerHTML={{ __html: loadFragment(name) }}
    />
  );
}
