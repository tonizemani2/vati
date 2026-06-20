import json, time
from engine.metaculus import api

out = []
for slug in ['ai-2027', 'ai-safety', 'ai-technical-benchmarks']:
    for attempt in range(4):
        try:
            posts = api.list_open_questions(slug)
            break
        except Exception as e:
            if '429' in str(e):
                print(f'  429 on {slug}, backoff…', flush=True); time.sleep(20)
            else:
                posts = []; break
    for p in posts:
        if not api.binary_question(p):
            continue
        q = api.question_text(p)
        out.append({'slug': slug, 'qid': q['question_id'], 'post_id': q['post_id'],
                    'title': q['title'], 'close': q['close_time'],
                    'rc': q['resolution_criteria'], 'bg': (q['description'] or '')[:400]})
    print(f'  {slug}: collected, running total {len(out)}', flush=True)
    time.sleep(8)

json.dump(out, open('data/metaculus/ai_cluster_questions.json', 'w'), indent=1)
print(f'\nsaved {len(out)} AI-cluster binary questions')
for o in out:
    print(f"  [{o['slug']}] close {o['close'][:10]} | {o['title'][:66]}")
