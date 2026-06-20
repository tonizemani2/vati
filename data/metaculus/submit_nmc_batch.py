import json, time
from engine.metaculus import numeric as N

qmap = {}
for cat, v in json.load(open('data/metaculus/numeric_mc_questions.json')).items():
    for m in v:
        qmap[m['question_id']] = m

# numeric/discrete percentiles {quantile: value}
numeric_fc = {
    43930: {0.05: 18, 0.25: 20, 0.5: 23, 0.75: 27, 0.95: 38},          # VIX biweekly max
    43931: {0.05: 4.22, 0.25: 4.39, 0.5: 4.48, 0.75: 4.57, 0.95: 4.74},  # UST 10Y
    35726: {0.05: 24, 0.25: 28, 0.5: 33, 0.75: 41, 0.95: 58},          # VIX max after Jun30
    35759: {0.05: 2620, 0.25: 2730, 0.5: 2800, 0.75: 2870, 0.95: 2960},  # federal employees
    36712: {0.05: 399000, 0.25: 402000, 0.5: 405000, 0.75: 408000, 0.95: 411000},  # crude prod
    35734: {0.05: 4.5, 0.25: 7.0, 0.5: 9.0, 0.75: 10.5, 0.95: 13.5},   # effective tariff rate
    35775: {0.05: 6650000, 0.25: 6950000, 0.5: 7150000, 0.75: 7350000, 0.95: 7650000},  # net outlays
    35758: {0.05: 52, 0.25: 63, 0.5: 76, 0.75: 94, 0.95: 128},         # journalists charged
    37442: {0.05: 7.20, 0.25: 7.55, 0.5: 7.70, 0.75: 7.82, 0.95: 7.95},  # democracy index
    43132: {0.05: 1, 0.25: 2, 0.5: 3, 0.75: 5, 0.95: 7},               # discrete: emergencies
    38115: {0.05: 4, 0.25: 5, 0.5: 6, 0.75: 7, 0.95: 9},               # discrete: military metros
    37836: {0.05: 8, 0.25: 10, 0.5: 11, 0.75: 12, 0.95: 12},           # discrete: cabinet retention
    43928: {0.05: -9, 0.25: -3, 0.5: 0, 0.75: 3, 0.95: 9},             # Nvidia-MSFT spread (0-centered)
    43927: {0.05: -12, 0.25: -4, 0.5: 0, 0.75: 4, 0.95: 12},           # Crude-S&P spread (0-centered)
}
mc_fc = {
    42099: {'2': 0.57, '3': 0.34, '4': 0.08, '5 or more': 0.01},       # Trump impeachment count
}

results = []
for qid, pcts in numeric_fc.items():
    m = qmap[qid]
    try:
        cdf = N.percentiles_to_cdf(pcts, m['continuous_range'], m['open_lower_bound'], m['open_upper_bound'])
        ok, msg = N.validate_cdf(cdf)
        if not ok:
            print(f"  SKIP {qid} invalid cdf: {msg}", flush=True)
            results.append({'qid': qid, 'ok': False, 'err': 'invalid:' + msg}); continue
        N.submit_cdf(qid, cdf)
        print(f"  OK num {qid} (cdf0={cdf[0]:.3f} cdf-1={cdf[-1]:.3f})  {m['title'][:46]}", flush=True)
        results.append({'qid': qid, 'ok': True})
    except Exception as e:
        print(f"  FAIL num {qid} :: {str(e)[:120]}", flush=True)
        results.append({'qid': qid, 'ok': False, 'err': str(e)[:150]})
    time.sleep(8)

for qid, probs in mc_fc.items():
    m = qmap[qid]
    try:
        vec = N.options_to_vector(probs, m['options'])
        N.submit_multiple_choice(qid, vec)
        print(f"  OK mc  {qid}  {m['title'][:46]}", flush=True)
        results.append({'qid': qid, 'ok': True})
    except Exception as e:
        print(f"  FAIL mc {qid} :: {str(e)[:120]}", flush=True)
        results.append({'qid': qid, 'ok': False, 'err': str(e)[:150]})
    time.sleep(8)

json.dump(results, open('data/metaculus/nmc_batch_results.json', 'w'), indent=1)
print(f"\n=== {sum(1 for r in results if r['ok'])}/{len(results)} submitted ===", flush=True)
