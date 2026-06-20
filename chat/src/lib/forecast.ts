import type { ForecastCardData } from "@/components/ForecastCard";
import { runForecast, type ForecastSpec } from "@/lib/mc";

const MARKER = "```vaticinus-forecast";

// Persistence markers. A forecast turn is saved as prose + a hidden spec block so the card can be
// rebuilt on reload; capture plays and contact lists are saved as their own marker-led messages by
// their routes. Kept as plain bracket tags (matching the existing [capture plan] / [contacts]
// convention) so old rows stay readable.
export const FORECAST_SPEC_MARKER = "[forecast-spec]";
export const CAPTURE_MARKER = "[capture plan]";
export const CONTACTS_MARKER = "[contacts]";

/** Save the visible prose plus a hidden spec block, so reopening a chat can rebuild the card. */
export function withSpecForPersist(prose: string, spec: Record<string, unknown> | null): string {
  if (!spec) return prose;
  return `${prose}\n\n${FORECAST_SPEC_MARKER}\n${JSON.stringify(spec)}`;
}

/** Split a persisted assistant turn back into clean prose + the forecast spec (if any). */
export function parsePersistedSpec(content: string): {
  prose: string;
  spec: Record<string, unknown> | null;
} {
  const idx = content.indexOf(FORECAST_SPEC_MARKER);
  if (idx === -1) return { prose: content, spec: null };
  const prose = content.slice(0, idx).trimEnd();
  const json = content.slice(idx + FORECAST_SPEC_MARKER.length).trim();
  try {
    return { prose, spec: JSON.parse(json) as Record<string, unknown> };
  } catch {
    return { prose, spec: null };
  }
}

/** Parse a marker-led message ("[capture plan]\n{...}" / "[contacts]\n[...]") back to JSON. */
export function parseMarkerJson(content: string, marker: string): unknown | null {
  const trimmed = content.trimStart();
  if (!trimmed.startsWith(marker)) return null;
  try {
    return JSON.parse(trimmed.slice(trimmed.indexOf(marker) + marker.length).trim());
  } catch {
    return null;
  }
}

/** Rebuild a finished forecast card from its spec, running the Monte-Carlo engine client-side
 *  (deterministic, no network, no credit charge) so a reopened chat shows the real card, not text. */
export function cardFromSpecComputed(spec: Record<string, unknown>): ForecastCardData {
  const base = cardFromSpec(spec);
  if (spec.base_value == null || spec.threshold == null) return { ...base, pending: false };
  try {
    const r = runForecast(engineSpec(spec) as unknown as ForecastSpec);
    return {
      ...base,
      pending: false,
      probability: r.probability,
      median: r.median,
      ci_low: r.ci_low,
      ci_high: r.ci_high,
      threshold: r.threshold,
      threshold_dir: r.threshold_dir,
      histogram: r.histogram,
      n_samples: r.n_samples,
    };
  } catch {
    return { ...base, pending: false };
  }
}

/** Hide the forecast spec fence from the visible prose, including a partial fence
 *  still mid-stream, so the user never sees raw JSON flash by. */
export function stripSpecForDisplay(text: string): string {
  const idx = text.indexOf(MARKER);
  if (idx !== -1) return text.slice(0, idx).trimEnd();
  // Tail could be a partial fence as it streams in ("`", "```vat", ...).
  const lastFence = text.lastIndexOf("```");
  if (lastFence !== -1) {
    const tail = text.slice(lastFence);
    if (MARKER.startsWith(tail)) return text.slice(0, lastFence).trimEnd();
  }
  return text;
}

/** Parse the completed forecast spec out of an assistant message. */
export function extractSpec(text: string): {
  prose: string;
  spec: Record<string, unknown> | null;
} {
  const start = text.indexOf(MARKER);
  if (start === -1) return { prose: text, spec: null };
  const after = start + MARKER.length;
  const end = text.indexOf("```", after);
  const inner = text.slice(after, end === -1 ? undefined : end);
  const prose = text.slice(0, start).trimEnd();
  try {
    return { prose, spec: JSON.parse(inner) };
  } catch {
    return { prose, spec: null };
  }
}

/** Build the card's display fields from the model spec (engine numbers added later). */
export function cardFromSpec(spec: Record<string, unknown>): ForecastCardData {
  const implications =
    spec.implications && typeof spec.implications === "object" && !Array.isArray(spec.implications)
      ? (spec.implications as ForecastCardData["implications"])
      : undefined;
  return {
    question: String(spec.question ?? ""),
    quantity_label: spec.quantity_label as string | undefined,
    ci_unit: spec.ci_unit as string | undefined,
    resolution_date: spec.resolution_date as string | undefined,
    dated_metric: spec.dated_metric as string | undefined,
    kill_criteria: Array.isArray(spec.kill_criteria)
      ? (spec.kill_criteria as string[])
      : undefined,
    already_priced: spec.already_priced as string | undefined,
    clause_note: spec.clause_note as string | undefined,
    scenarios:
      Array.isArray(spec.scenarios) && spec.scenarios.length >= 2
        ? (spec.scenarios as ForecastCardData["scenarios"])
        : undefined,
    threshold: typeof spec.threshold === "number" ? spec.threshold : undefined,
    threshold_dir: spec.threshold_dir as string | undefined,
    implications,
    pending: true,
  };
}

/** The subset of the spec the engine needs to run the Monte-Carlo forecast. */
export function engineSpec(spec: Record<string, unknown>) {
  return {
    question: spec.question,
    base_value: spec.base_value,
    horizon_years: spec.horizon_years,
    g_mean: spec.g_mean,
    g_sd: spec.g_sd,
    decel: spec.decel,
    threshold: spec.threshold,
    threshold_dir: spec.threshold_dir,
  };
}
