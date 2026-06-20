import json, time
from engine.metaculus import numeric as N

qmap = {}
d = json.load(open('data/metaculus/numeric_mc_questions.json'))
for cat in d:
    for m in d[cat]:
        qmap[m['question_id']] = m

# chair-calibrated proving forecasts
numeric_fc = {
    36339: {0.05: -30, 0.25: -24, 0.5: -20, 0.75: -16, 0.95: -9},   # Trump net approval
    43929: {0.05: 2.55, 0.25: 2.71, 0.5: 2.79, 0.75: 2.88, 0.95: 3.15},  # HY OAS spread
}
mc_fc = {
    35786: {'Democrats': 0.40, 'Republicans': 0.60, 'Other': 0.00},   # Senate
    35785: {'Democrats': 0.68, 'Republicans': 0.31, 'Other': 0.01},   # House
}

results = []
for qid, pcts in numeric_fc.items():
    m = qmap[qid]
    cdf = N.percentiles_to_cdf(pcts, m['continuous_range'], m['open_lower_bound'], m['open_upper_bound'])
    ok, msg = N.validate_cdf(cdf)
    print(f"numeric {qid}: cdf len={len(cdf)} valid={ok}({msg}) range={m['range_min']}..{m['range_max']} "
          f"cdf0={cdf[0]:.4f} cdf-1={cdf[-1]:.4f}", flush=True)
    try:
        N.submit_cdf(qid, cdf)
        print(f"   OK submitted numeric {qid}  ({m['title'][:45]})", flush=True)
        results.append({'qid': qid, 'type': 'numeric', 'ok': True})
    except Exception as e:
        print(f"   FAIL numeric {qid} :: {str(e)[:260]}", flush=True)
        results.append({'qid': qid, 'type': 'numeric', 'ok': False, 'err': str(e)[:300]})
    time.sleep(8)

for qid, probs in mc_fc.items():
    m = qmap[qid]
    vec = N.options_to_vector(probs, m['options'])
    print(f"mc {qid}: vec={[round(x,3) for x in vec]} sum={sum(vec):.3f} opts={len(m['options'])}", flush=True)
    try:
        N.submit_multiple_choice(qid, vec)
        print(f"   OK submitted mc {qid}  ({m['title'][:45]})", flush=True)
        results.append({'qid': qid, 'type': 'mc', 'ok': True})
    except Exception as e:
        print(f"   FAIL mc {qid} :: {str(e)[:260]}", flush=True)
        results.append({'qid': qid, 'type': 'mc', 'ok': False, 'err': str(e)[:300]})
    time.sleep(8)

json.dump(results, open('data/metaculus/nmc_test_results.json', 'w'), indent=1)
print(f"\n=== {sum(1 for r in results if r['ok'])}/{len(results)} accepted ===", flush=True)
