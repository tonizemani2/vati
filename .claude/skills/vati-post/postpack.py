#!/usr/bin/env python3
"""postpack.py — the deterministic, no-LLM fact + sort layer for /vati-post.

It reads the Pope spec JSONs in research/pope/ (the hardened pre-consensus calls)
and emits clean, post-ready material plus a transparent post-worthiness ranking.
SKILL.md does the judgment and the writing; this file only extracts and sorts, so
the writer never types a claim from memory.

Modes:
  list                       list every available Pope spec (title, #calls, horizon, date)
  rank [FILE|all] [--opps]   rank every call by post-worthiness; --opps weights soonest-resolving
                             (the calls that build a public track record fastest)
  card FILE THESIS_ID        dump the full post-ready card for one call (every field cleaned)

Notes:
- vision_p / clause_p come in two encodings across files (0.82 vs 85). We normalise to %.
- Nothing here is "true" because it parsed cleanly. These calls are hardened candidates,
  NOT forward-tracked results. The ranking is about how postable a call is, not whether it
  will resolve yes. The integrity rules live in SKILL.md.
"""
import json, os, sys, glob, datetime, textwrap

POPE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "research", "pope")
POPE_DIR = os.path.normpath(POPE_DIR)
TODAY = datetime.date(2026, 6, 16)  # pinned; pass a date in if you re-run later

# Files that are exploratory "wide boards" or superseded dupes — skip from the default rank.
SKIP_SUBSTR = ("wide-A", "wide-B", "_runs")


def _pct(v):
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v * 100 if v <= 1.0 else v


def _load(path):
    with open(path) as f:
        return json.load(f)


def _spec_files():
    out = []
    for p in sorted(glob.glob(os.path.join(POPE_DIR, "*.json"))):
        base = os.path.basename(p)
        if any(s in base for s in SKIP_SUBSTR):
            continue
        out.append(p)
    return out


def _days_to(resolves):
    """Days from today to the resolution date; None if unparseable."""
    if not resolves:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            d = datetime.datetime.strptime(str(resolves)[:10], fmt).date()
            return (d - TODAY).days
        except ValueError:
            continue
    return None


def _horizon_bucket(days):
    if days is None:
        return "?"
    if days <= 550:        # ~18 months
        return "NEAR"      # resolves soon -> fastest track-record proof
    if days <= 1500:       # ~4 years
        return "MID"
    return "LONG"


def _has_named(impl, key):
    v = (impl or {}).get(key)
    if isinstance(v, list):
        return any((isinstance(x, dict) and x.get("who")) for x in v)
    return bool(v)


def score_thesis(t, opps=False):
    """Transparent composite in [0,1] with printable subscores. Higher = more postable."""
    vision = _pct(t.get("vision_p")) or 0
    clause = _pct(t.get("clause_p")) or 0
    days = _days_to(t.get("resolves"))
    impl = t.get("implications") or {}

    sub = {}
    # proximity: soonest-resolving calls earn a public scoreboard fastest
    if days is None:
        sub["proximity"] = 0.3
    elif days <= 550:
        sub["proximity"] = 1.0
    elif days <= 1100:
        sub["proximity"] = 0.7
    elif days <= 1800:
        sub["proximity"] = 0.45
    else:
        sub["proximity"] = 0.25
    # specificity: named winners/losers = concrete, screenshot-worthy
    sub["named"] = 1.0 if (_has_named(impl, "winners") or _has_named(impl, "losers")) else 0.0
    # priced-gap: a real "what the market hasn't priced" angle exists
    sub["gap"] = 1.0 if (t.get("pre_consensus") and t.get("price_channel")) else (0.5 if t.get("pre_consensus") else 0.0)
    # tension: a strict clause that is a genuine call (not a lock, not a longshot) reads honest
    sub["tension"] = 1.0 if 40 <= clause <= 72 else (0.5 if 30 <= clause < 40 else 0.2)
    # conviction on direction
    sub["conviction"] = min(vision, 100) / 100.0
    # mechanism: a plain-English explainer (boom) is ready-made post copy
    sub["mechanism"] = 1.0 if t.get("boom") else 0.0
    # monitorable: a dated thing-to-watch makes it an actionable post
    sub["watch"] = 1.0 if impl.get("watch") else 0.0

    if opps:
        w = {"proximity": .34, "named": .14, "gap": .16, "tension": .10,
             "conviction": .06, "mechanism": .10, "watch": .10}
    else:
        w = {"proximity": .14, "named": .16, "gap": .18, "tension": .12,
             "conviction": .10, "mechanism": .15, "watch": .15}
    total = sum(sub[k] * w[k] for k in w)
    return total, sub, dict(vision=vision, clause=clause, days=days)


def cmd_list():
    files = _spec_files()
    if not files:
        print("No Pope specs found in", POPE_DIR)
        return
    print(f"{'FILE':<34} {'#':>3}  {'HORIZON':<14} TITLE")
    print("-" * 100)
    for p in files:
        d = _load(p)
        th = d.get("theses", [])
        print(f"{os.path.basename(p):<34} {len(th):>3}  {str(d.get('horizon',''))[:13]:<14} {str(d.get('title',''))[:50]}")


def cmd_rank(target="all", opps=False):
    files = _spec_files() if target in ("all", "", None) else [
        p for p in _spec_files() if target in os.path.basename(p)]
    rows = []
    for p in files:
        d = _load(p)
        for t in d.get("theses", []):
            total, sub, meta = score_thesis(t, opps=opps)
            rows.append((total, sub, meta, os.path.basename(p), t))
    rows.sort(key=lambda r: r[0], reverse=True)

    mode = "OPPORTUNITY (soonest-resolving weighted)" if opps else "POST-WORTHINESS (general)"
    print(f"== RANKED SLATE — {mode} ==")
    print("Hardened candidates, NOT forward-tracked results. Sort = how postable, not how likely.\n")
    for i, (total, sub, meta, fname, t) in enumerate(rows, 1):
        bucket = _horizon_bucket(meta["days"])
        fmt = _suggest_format(bucket, sub)
        head = t.get("headline", "")[:150]
        print(f"#{i:>2} [{total:.2f}] {bucket:<4} vision {meta['vision']:.0f}% / clause {meta['clause']:.0f}% "
              f"| resolves {t.get('resolves','?')} | {fname}  id={t.get('id','?')}")
        print(f"      {head}")
        print(f"      best format: {fmt}  |  subscores: " +
              " ".join(f"{k}={sub[k]:.1f}" for k in ("proximity","named","gap","mechanism","watch")))
        print()


def _suggest_format(bucket, sub):
    if bucket == "NEAR":
        return "X single (opportunity) + add to a dated scoreboard thread"
    if sub["named"] and sub["mechanism"]:
        return "X long article or LinkedIn (named winners + clean mechanism)"
    if sub["mechanism"]:
        return "X thread (walk the mechanism) or Substack section"
    return "LinkedIn take / Substack section"


def _clean(s, width=0):
    if s is None:
        return ""
    s = str(s).strip()
    return s


def cmd_card(fname, tid):
    matches = [p for p in _spec_files() if fname in os.path.basename(p)]
    if not matches:
        print("No spec file matching:", fname); return
    d = _load(matches[0])
    th = d.get("theses", [])
    t = next((x for x in th if str(x.get("id")) == str(tid)), None)
    if t is None:
        print(f"No thesis id={tid} in {os.path.basename(matches[0])}. Available ids:",
              ", ".join(str(x.get("id")) for x in th))
        return
    impl = t.get("implications") or {}
    vision, clause = _pct(t.get("vision_p")), _pct(t.get("clause_p"))
    days = _days_to(t.get("resolves"))

    def names(key):
        v = impl.get(key)
        if isinstance(v, list):
            return "; ".join(f"{x.get('who','?')} — {x.get('why','')}" for x in v if isinstance(x, dict))
        return _clean(v)

    print("=" * 90)
    print("POST CARD —", os.path.basename(matches[0]), "| id", t.get("id"))
    print("=" * 90)
    print("HORIZON BUCKET :", _horizon_bucket(days), f"({days} days to resolve)" if days is not None else "")
    print("DUAL PROB      :", f"vision {vision:.0f}% / strict-clause {clause:.0f}%")
    print("RESOLVES       :", t.get("resolves"))
    print()
    print("HEADLINE       :", _clean(t.get("headline")))
    print()
    print("MECHANISM (boom, plain-English, post-ready):")
    print(textwrap.fill(_clean(t.get("boom")), 88, initial_indent="  ", subsequent_indent="  "))
    print()
    print("WHY INELASTIC (structural):")
    print(textwrap.fill(_clean(t.get("structural")), 88, initial_indent="  ", subsequent_indent="  "))
    print()
    print("THE NEEDLE     :")
    print(textwrap.fill(_clean(t.get("needle")), 88, initial_indent="  ", subsequent_indent="  "))
    print()
    print("WHAT'S NOT PRICED (pre_consensus):")
    print(textwrap.fill(_clean(t.get("pre_consensus")), 88, initial_indent="  ", subsequent_indent="  "))
    print()
    print("LIVE PRICE ANCHOR (price_channel):")
    print(textwrap.fill(_clean(t.get("price_channel")), 88, initial_indent="  ", subsequent_indent="  "))
    print()
    print("WINNERS        :", textwrap.fill(names("winners"), 88, subsequent_indent="                 "))
    print("LOSERS         :", textwrap.fill(names("losers"), 88, subsequent_indent="                 "))
    print("NEXT CONSTRAINT:", textwrap.fill(_clean(impl.get("next_constraint")), 88, subsequent_indent="                 "))
    print()
    print("WATCH (dated monitorable — the actionable hook):")
    print(textwrap.fill(_clean(impl.get("watch")), 88, initial_indent="  ", subsequent_indent="  "))
    print()
    print("KILL (how we will be proven wrong — ALWAYS include in the post):")
    print(textwrap.fill(_clean(t.get("kill")), 88, initial_indent="  ", subsequent_indent="  "))


def main():
    args = sys.argv[1:]
    if not args or args[0] == "list":
        cmd_list(); return
    if args[0] == "rank":
        target = "all"
        opps = "--opps" in args
        rest = [a for a in args[1:] if not a.startswith("--")]
        if rest:
            target = rest[0]
        cmd_rank(target, opps=opps); return
    if args[0] == "card":
        if len(args) < 3:
            print("usage: postpack.py card FILE THESIS_ID"); return
        cmd_card(args[1], args[2]); return
    print(__doc__)


if __name__ == "__main__":
    main()
