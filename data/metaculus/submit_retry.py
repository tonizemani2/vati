import json, time
from engine.metaculus import api

slate = {o['qid']: o for o in json.load(open('data/metaculus/cup_slate.json'))}
done = {r['qid'] for r in json.load(open('data/metaculus/cup_submitted.json')) if r.get('submitted')}
pending = [(qid, o) for qid, o in slate.items() if qid not in done]
print(f'{len(done)} already live; retrying {len(pending)} pending (submit-only, paced)...', flush=True)
time.sleep(25)  # let Cloudflare cool down

newly = []
for qid, o in pending:
    for attempt in range(4):
        try:
            api.submit_binary(qid, o['prob'])
            print(f"  OK {o['prob']:.2f}  {o['title'][:55]}", flush=True)
            newly.append(qid)
            break
        except Exception as e:
            if '429' in str(e) and attempt < 3:
                wait = 30 * (attempt + 1)
                print(f"  ...429 backoff {wait}s ({o['title'][:32]})", flush=True)
                time.sleep(wait)
            else:
                print(f"  FAIL {o['title'][:45]} :: {str(e)[:90]}", flush=True)
                break
    time.sleep(8)

rec = json.load(open('data/metaculus/cup_submitted.json'))
for r in rec:
    if r['qid'] in newly:
        r['submitted'] = True
        r.pop('error', None)
json.dump(rec, open('data/metaculus/cup_submitted.json', 'w'), indent=1)
print(f"\n=== now {sum(1 for r in rec if r.get('submitted'))}/12 live ===", flush=True)
