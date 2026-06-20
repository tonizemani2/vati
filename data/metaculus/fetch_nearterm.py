import json, time
from engine.metaculus import api

CUTOFF = '2027-01-01'  # resolves in 2026
slugs = ['current-events', 'POTUS-predictions', 'taiwan', 'iran-israel-conflict',
         'us-democracy-threat', 'market-pulse-26q2', 'midterms-2026']
out, seen = [], set()
for slug in slugs:
    posts = []
    for attempt in range(4):
        try:
            posts = api.list_open_questions(slug); break
        except Exception as e:
            if '429' in str(e):
                print(f'  429 on {slug}, backoff…', flush=True); time.sleep(20)
            else:
                break
    kept = 0
    for p in posts:
        if not api.binary_question(p):
            continue
        q = api.question_text(p)
        close = q['close_time'] or ''
        if close[:10] >= CUTOFF:      # skip long-horizon
            continue
        if q['question_id'] in seen:
            continue
        seen.add(q['question_id'])
        out.append({'slug': slug, 'qid': q['question_id'], 'post_id': q['post_id'],
                    'title': q['title'], 'close': close,
                    'rc': q['resolution_criteria'], 'bg': (q['description'] or '')[:350]})
        kept += 1
    print(f'  {slug}: {kept} near-term binary kept (total {len(out)})', flush=True)
    time.sleep(8)

out.sort(key=lambda o: o['close'])
json.dump(out, open('data/metaculus/nearterm_questions.json', 'w'), indent=1)
print(f'\nsaved {len(out)} near-term binary questions (close < {CUTOFF})')
for o in out:
    print(f"  [{o['slug'][:16]:16}] close {o['close'][:10]} | {o['title'][:60]}")
