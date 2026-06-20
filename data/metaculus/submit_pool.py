"""Paced submitter — read council_forecasts.json + pool.json, submit each forecast in the right
Metaculus shape (binary / MC / continuous CDF). ~8s pacing with 429 backoff. Idempotent log.
Honors a 2h wall-clock cap via /tmp/mtc_start.txt.  Pass --submit to go live (else DRY-RUN)."""
import json, time, sys, glob
from datetime import datetime, timezone
from engine.metaculus import api, numeric

def _epoch(v):
    """Parse an ISO date/datetime string (or pass through a number) to unix seconds."""
    if isinstance(v, (int, float)): return float(v)
    s = str(v).replace('Z', '+00:00')
    try: return datetime.fromisoformat(s).timestamp()
    except ValueError:
        return datetime.fromisoformat(s[:10]).timestamp()

def _cdf_for(q, percentiles):
    """Build a valid CDF; for date questions convert ISO grid + ISO percentile values to epoch."""
    cr = q['scaling']['continuous_range']
    pcts = {float(k): v for k, v in percentiles.items()}
    if q['type'] == 'date':
        cr = [_epoch(x) for x in cr]
        pcts = {k: _epoch(v) for k, v in pcts.items()}
    else:
        pcts = {k: float(v) for k, v in pcts.items()}
    return numeric.percentiles_to_cdf(pcts, cr,
            q['scaling']['open_lower_bound'], q['scaling']['open_upper_bound'])

LIVE = '--submit' in sys.argv
CAP_S = 2*3600 + 300  # 2h hard cap (small grace already burned on setup)
try: START = int(open('/tmp/mtc_start.txt').read().strip())
except: START = int(time.time())

pool = {x['question_id']: x for x in json.load(open('data/metaculus/pool.json'))}
fcs = json.load(open('data/metaculus/council_forecasts.json'))

# already-submitted this run-set (idempotent)
done = set()
for f in glob.glob('data/metaculus/forecasts_*.jsonl'):
    for l in open(f):
        try:
            r = json.loads(l)
            if r.get('submitted'): done.add(r.get('question_id'))
        except: pass

def backoff_submit(fn, *a):
    for t in range(4):
        try: return fn(*a), None
        except Exception as e:
            s = str(e)
            if '429' in s or '1015' in s:
                time.sleep(40); continue
            return None, s[:300]
    return None, 'rate-limited x4'

def logrec(tour, rec):
    with open(f'data/metaculus/forecasts_{tour}.jsonl', 'a') as f:
        f.write(json.dumps(rec) + '\n')

ok = err = skip = 0
for i, fc in enumerate(fcs, 1):
    qid = fc.get('question_id')
    q = pool.get(qid)
    if not q:
        print(f"[{i}] qid={qid} NOT IN POOL — skip"); skip += 1; continue
    if qid in done:
        print(f"[{i}] qid={qid} already submitted — skip"); skip += 1; continue
    if time.time() - START > CAP_S:
        print(f"\n=== 2h CAP REACHED at {i}/{len(fcs)} — stopping ==="); break

    typ = q['type']; tour = q['tournament']
    rec = {'question_id': qid, 'post_id': q['post_id'], 'title': q['title'][:90],
           'type': typ, 'reasoning': fc.get('reasoning', '')[:400],
           'at': datetime.now(timezone.utc).isoformat()}
    desc = ''
    if not LIVE:
        # dry-run: just validate shapes
        if typ == 'binary': desc = f"p={fc.get('prob')}"
        elif typ == 'multiple_choice':
            vec = numeric.options_to_vector(fc.get('option_probs', {}), q['options'])
            desc = "MC " + ",".join(f"{k[:10]}={v:.2f}" for k,v in list(vec.items())[:4])
        else:
            cr = q['scaling']['continuous_range']
            cdf = _cdf_for(q, fc['percentiles'])
            valid,msg = numeric.validate_cdf(cdf, len(cr))
            desc = f"CDF len={len(cdf)} valid={valid}({msg})"
        print(f"[{i}/{len(fcs)}] DRY {typ:14} {tour[:16]:16} {desc}  {q['title'][:48]}")
        continue

    # LIVE
    if typ == 'binary':
        res, e = backoff_submit(api.submit_binary, qid, float(fc['prob']))
        rec['prob'] = fc.get('prob')
    elif typ == 'multiple_choice':
        vec = numeric.options_to_vector(fc.get('option_probs', {}), q['options'])
        res, e = backoff_submit(numeric.submit_multiple_choice, qid, vec)
        rec['option_probs'] = vec
    else:
        cr = q['scaling']['continuous_range']
        if not cr:
            e = "no continuous_range"; res = None
        else:
            try:
                cdf = _cdf_for(q, fc['percentiles'])
                res, e = backoff_submit(numeric.submit_cdf, qid, cdf)
            except Exception as ex:
                res, e = None, f"cdf-build:{ex}"[:120]
            rec['percentiles'] = fc['percentiles']
    rec['submitted'] = e is None
    if e: rec['error'] = e; err += 1; print(f"[{i}/{len(fcs)}] FAIL {typ:12} {tour[:14]:14} {e[:60]}  {q['title'][:40]}")
    else: ok += 1; print(f"[{i}/{len(fcs)}] OK   {typ:12} {tour[:14]:14} {q['title'][:52]}", flush=True)
    logrec(tour, rec)
    time.sleep(8)

print(f"\n{'SUBMITTED' if LIVE else 'DRY-RAN'}: ok={ok} err={err} skip={skip} / {len(fcs)} total")
