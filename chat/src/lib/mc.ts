// The Monte-Carlo Fermi engine, ported from engine/forecast.py `mc_quantity` so the
// app runs anywhere (Cloudflare Workers, Vercel, Node) with NO Python subprocess.
//
// Same model as the Python card engine: project a compounding count `horizonYears`
// ahead under uncertain annual growth (each year a draw from Normal(gMean - decel*year,
// gSd), floored at 0.85), then add sqrt(n) count noise. The probability and 80% interval
// FALL OUT of the samples (doctrine 2.2) — we never hand-type a number.
//
// The only deliberate difference from Python: the RNG. Python uses Mersenne Twister; here
// we use a seeded mulberry32 + Box-Muller gaussian. The exact sample stream differs, but at
// 80k samples the probability and percentiles are statistically identical. The seed is still
// derived from the question, so a given question reproduces the same distribution.

export type ForecastResult = {
  ok: true;
  engine: "monte_carlo_fermi";
  probability: number;
  median: number;
  ci_low: number;
  ci_high: number;
  threshold: number;
  threshold_dir: string;
  horizon_years: number;
  base_value: number;
  n_samples: number;
  histogram: { lo: number; hi: number; counts: number[]; peak: number };
};

export type ForecastSpec = {
  question?: string;
  base_value: number;
  horizon_years: number;
  g_mean?: number;
  g_sd?: number;
  decel?: number;
  threshold: number;
  threshold_dir?: string;
  seed?: number;
  n?: number;
};

/** Deterministic 32-bit seed from the question (matches the intent of the Python sha256 seed). */
export function seedFromQuestion(s: string): number {
  let h = 2166136261 >>> 0; // FNV-1a
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h >>> 0;
}

function mulberry32(seed: number) {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Standard-normal sampler (Box-Muller) over a uniform RNG. */
function makeGauss(rand: () => number) {
  return (mean: number, sd: number) => {
    let u = 0;
    let v = 0;
    while (u === 0) u = rand();
    while (v === 0) v = rand();
    const z = Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
    return mean + sd * z;
  };
}

function histogram(sorted: number[], bins = 28) {
  const n = sorted.length;
  const lo = sorted[Math.floor(0.02 * n)];
  let hi = sorted[Math.floor(0.98 * n)];
  if (hi <= lo) hi = lo + 1.0;
  const width = (hi - lo) / bins;
  const counts = new Array(bins).fill(0);
  for (const value of sorted) {
    if (value < lo || value > hi) continue;
    const idx = Math.min(bins - 1, Math.floor((value - lo) / width));
    counts[idx] += 1;
  }
  const peak = Math.max(...counts) || 1;
  return { lo, hi, counts, peak };
}

export function runForecast(spec: ForecastSpec): ForecastResult {
  const baseVal = Number(spec.base_value);
  const horizonYears = Math.trunc(Number(spec.horizon_years));
  const gMean = spec.g_mean != null ? Number(spec.g_mean) : 1.0;
  const gSd = spec.g_sd != null ? Number(spec.g_sd) : 0.1;
  const decel = spec.decel != null ? Number(spec.decel) : 0.0;
  const threshold = Number(spec.threshold);
  const direction = (spec.threshold_dir ?? ">=").trim() || ">=";
  const seed = spec.seed ?? seedFromQuestion(spec.question || String(baseVal));
  // 80k samples: P accurate to ~0.2%, histogram smooth, still snappy for an interactive card.
  const n = spec.n ?? 80_000;

  if (!Number.isFinite(baseVal) || !Number.isFinite(threshold) || !Number.isFinite(horizonYears)) {
    throw new Error("base_value, threshold and horizon_years must be finite numbers");
  }

  const rand = mulberry32(seed);
  const gauss = makeGauss(rand);
  const out = new Array<number>(n);
  for (let i = 0; i < n; i++) {
    let v = baseVal;
    for (let h = 0; h < horizonYears; h++) {
      const g = Math.max(gauss(gMean - decel * h, gSd), 0.85);
      v *= g;
    }
    v = gauss(v, Math.sqrt(Math.max(v, 0)));
    out[i] = v;
  }
  out.sort((a, b) => a - b);
  const pct = (p: number) => out[Math.floor(p * out.length)];

  let beyond = 0;
  if (direction === "<=") {
    for (const v of out) if (v <= threshold) beyond++;
  } else {
    for (const v of out) if (v >= threshold) beyond++;
  }

  return {
    ok: true,
    engine: "monte_carlo_fermi",
    probability: Math.round((beyond / out.length) * 1000) / 1000,
    median: pct(0.5),
    ci_low: pct(0.1),
    ci_high: pct(0.9),
    threshold,
    threshold_dir: direction,
    horizon_years: horizonYears,
    base_value: baseVal,
    n_samples: out.length,
    histogram: histogram(out),
  };
}
