"""Council-config bake-off: which forecaster config actually wins?

Honest test bed = qbank Manifold questions RESOLVED IN 2026 (postdate model cutoffs → leak-light,
forward-ish), filtered to genuinely-uncertain ones (crowd_final in [0.15,0.85]) so there is signal
to discriminate. Standalone LLM forecasts (NO web research) to isolate the reasoning leg and the
decorrelation structure — the thing that differs between configs.

Models: Opus 4.8 (bedrock), Sonnet 4.6 (bedrock), DeepSeek V3.2 (openrouter). Measures per-model
Brier + calibration + edge vs crowd, pairwise correlation (leak-free), and ensemble Brier for each
candidate config. Caveat: absolute Brier is leak-optimistic; the RELATIVE config ranking + the
correlation matrix are the trustworthy reads.

  uv run python data/metaculus/config_bakeoff.py --n 40
"""
import json, sys, re, statistics as st
from concurrent.futures import ThreadPoolExecutor

from engine import db
from engine.adapters import llm

MODELS = [  # (label, provider, model)
    ("opus48",   "bedrock",    "us.anthropic.claude-opus-4-8"),
    ("sonnet46", "bedrock",    "us.anthropic.claude-sonnet-4-6"),
    ("deepseek", "deepseek",   "deepseek-chat"),
]
SYSTEM = ("You are a calibrated superforecaster. Give a probability the question resolves YES. "
          "Reason in 1-2 sentences, then end with a final line exactly: PROB: <0..1>. "
          "Avoid overconfidence; reserve <0.05 or >0.95 for near-certainties.")


def n_arg(flag, default):
    if flag in sys.argv:
        try: return int(sys.argv[sys.argv.index(flag) + 1])
        except (ValueError, IndexError): pass
    return default


def load_panel(n):
    rows = []
    for l in open("data/metaculus/qbank.jsonl"):
        d = json.loads(l)
        if d.get("resolved_year") != 2026:
            continue
        oc = str(d.get("outcome"))
        if oc not in ("True", "False", "YES", "NO"):
            continue
        try: crowd = float(d["crowd_final"])
        except (KeyError, ValueError, TypeError): continue
        if not (0.15 <= crowd <= 0.85):  # uncertain → discriminative
            continue
        d["_y"] = 1.0 if oc in ("True", "YES") else 0.0
        d["_crowd"] = crowd
        rows.append(d)
    rows.sort(key=lambda r: r["id"])  # deterministic
    step = max(1, len(rows) // n)
    return rows[::step][:n]


def parse_prob(txt):
    m = re.findall(r"PROB:\s*([01]?\.\d+|[01](?:\.0+)?)", txt)
    if m:
        try: return min(0.99, max(0.01, float(m[-1])))
        except ValueError: pass
    m2 = re.findall(r"\b(0?\.\d+)\b", txt)
    if m2:
        try: return min(0.99, max(0.01, float(m2[-1])))
        except ValueError: pass
    return None


def elicit(conn, q, provider, model):
    prompt = (f"Question (resolves YES/NO): {q['title']}\n"
              f"Context: created {q.get('created_date')}, this is a real prediction-market question.\n"
              f"Give your probability it resolved YES.")
    try:
        out = llm.complete(conn, prompt, provider=provider, model=model, system=SYSTEM,
                           max_tokens=220, est_cost_cents=2)
        return parse_prob(out)
    except Exception as e:
        return None


def brier(p, y):
    return (p - y) ** 2


def main():
    n = n_arg("--n", 40)
    conn = db.connect()
    panel = load_panel(n)
    print(f"panel: {len(panel)} uncertain 2026-resolved questions | models: {[m[0] for m in MODELS]}\n",
          file=sys.stderr)
    recs = []
    for i, q in enumerate(panel, 1):
        row = {"id": q["id"], "title": q["title"][:70], "y": q["_y"], "crowd": q["_crowd"]}
        # parallel across the 3 models (separate conn per thread for sqlite safety)
        def run(m):
            c = db.connect()
            return m[0], elicit(c, q, m[1], m[2])
        with ThreadPoolExecutor(max_workers=3) as ex:
            for lbl, p in ex.map(run, MODELS):
                row[lbl] = p
        recs.append(row)
        got = {m[0]: row.get(m[0]) for m in MODELS}
        print(f"[{i:2}/{len(panel)}] y={q['_y']:.0f} crowd={q['_crowd']:.2f} "
              f"{ {k:(round(v,2) if v is not None else None) for k,v in got.items()} }  {q['title'][:40]}",
              file=sys.stderr)
    with open("data/metaculus/config_bakeoff_raw.jsonl", "w") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")

    # ---- metrics ----
    labels = [m[0] for m in MODELS]
    def col(lbl): return [(r[lbl], r["y"], r["crowd"]) for r in recs if r.get(lbl) is not None]

    print("\n=== per-model (n, Brier, vs-crowd Brier, calibration |mean p - base rate|) ===")
    base = st.mean(r["y"] for r in recs)
    for lbl in labels + ["crowd"]:
        if lbl == "crowd":
            data = [(r["crowd"], r["y"]) for r in recs]
        else:
            data = [(p, y) for p, y, _ in col(lbl)]
        if not data: print(f"{lbl:9} no data"); continue
        b = st.mean(brier(p, y) for p, y in data)
        meanp = st.mean(p for p, _ in data)
        print(f"{lbl:9} n={len(data):2}  Brier={b:.4f}  mean_p={meanp:.2f} (base={base:.2f})")

    # ensemble configs (median of member probs), scored on questions all members answered
    def ens_brier(members):
        vals = []
        for r in recs:
            ps = [r[m] for m in members if r.get(m) is not None]
            if len(ps) == len(members):
                vals.append(brier(st.median(ps), r["y"]))
        return (st.mean(vals), len(vals)) if vals else (None, 0)

    print("\n=== ensemble configs (median aggregation) ===")
    configs = {
        "opus-only": ["opus48"],
        "sonnet+opus (current)": ["sonnet46", "opus48"],
        "opus+deepseek": ["opus48", "deepseek"],
        "sonnet+opus+deepseek": ["sonnet46", "opus48", "deepseek"],
        "deepseek-only": ["deepseek"],
    }
    for name, members in configs.items():
        b, k = ens_brier(members)
        print(f"{name:24} Brier={b:.4f} (n={k})" if b is not None else f"{name:24} no data")

    # pairwise correlation (LEAK-FREE signal: low corr = real decorrelation = ensemble adds value)
    print("\n=== pairwise prob correlation (lower = more decorrelated = better ensemble) ===")
    import itertools
    for a, c in itertools.combinations(labels, 2):
        pairs = [(r[a], r[c]) for r in recs if r.get(a) is not None and r.get(c) is not None]
        if len(pairs) > 3:
            xa = [x for x, _ in pairs]; xc = [y for _, y in pairs]
            try: corr = st.correlation(xa, xc)
            except Exception: corr = float("nan")
            mad = st.mean(abs(x - y) for x, y in pairs)
            print(f"{a:9} vs {c:9}  corr={corr:+.2f}  mean|Δp|={mad:.3f}  (n={len(pairs)})")


if __name__ == "__main__":
    main()
