import json, time
from engine.metaculus import api

# qid -> (prob, short title) — chair-calibrated near-term slate. Hondius (43465) already live via the Cup.
slate = {
    38099: (0.03, "Musk denaturalization suit by Jul 1"),
    38280: (0.02, "2/3 EU recognize Palestine by Jul"),
    43524: (0.52, "Fed courts block USPS ballot restriction"),
    43606: (0.12, "Trump election-integrity natl emergency"),
    37460: (0.12, "Impoundment authority expanded by Nov 3"),
    39090: (0.08, "Lisa Cook off Fed before Nov 3"),
    43497: (0.42, "Missouri Amendment 3 repeal passes"),
    37484: (0.60, "DOJ removes PIN consult requirement"),
    35765: (0.08, "Federal judge partisan-impeached"),
    38065: (0.09, "US ground invasion of Iran"),
    38067: (0.03, "Iranian govt loses power by 2027"),
    43133: (0.30, "US-China new trade agreement 2026"),
    42686: (0.18, "US attacks Cuba before 2027"),
    43938: (0.22, "CJP protest >=20k before 2027"),
    38265: (0.02, "Obama arrested before Jul 2026"),
}
results = []
for qid, (p, name) in slate.items():
    for attempt in range(4):
        try:
            api.submit_binary(qid, p)
            print(f"  OK {p:.2f}  {name}", flush=True)
            results.append({"qid": qid, "prob": p, "name": name, "submitted": True})
            break
        except Exception as e:
            if '429' in str(e) and attempt < 3:
                w = 30 * (attempt + 1)
                print(f"  ...429 backoff {w}s ({name})", flush=True); time.sleep(w)
            else:
                print(f"  FAIL {name} :: {str(e)[:90]}", flush=True)
                results.append({"qid": qid, "prob": p, "name": name, "submitted": False, "err": str(e)[:150]})
                break
    time.sleep(8)
json.dump(results, open('data/metaculus/nearterm_submitted.json', 'w'), indent=1)
ok = sum(1 for r in results if r.get('submitted'))
print(f"\n=== {ok}/{len(slate)} near-term forecasts submitted ===", flush=True)
