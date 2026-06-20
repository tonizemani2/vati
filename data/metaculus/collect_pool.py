"""Paced collector — pull every OPEN, NOT-yet-done question across the target tournaments into
pool.json with the full payload the forecaster needs. Cloudflare 1015-aware (backoff + retry)."""
import json, glob, time, sys
from engine.metaculus import api

DONE=set()
for f in glob.glob('data/metaculus/*.jsonl'):
    for l in open(f):
        try: DONE.add(json.loads(l).get('question_id'))
        except: pass
for f in ['cup_submitted','nearterm_submitted','futureeval_submitted','nmc_batch_results','nmc_test_results']:
    try:
        for r in json.load(open(f'data/metaculus/{f}.json')):
            if isinstance(r,dict): DONE.add(r.get('question_id') or r.get('qid'))
    except: pass
DONE.discard(None)

SLUGS=['metaculus-cup-summer-2026','current-events','POTUS-predictions','midterms-2026',
       'taiwan','nuclear-horizons','synbio','space-tech-climate','quantum-computing',
       'superconductors','market-pulse-26q2','rand','ai-industry-milestones','chinese-ai-chips',
       'ukraine-conflict','red-lines','research-outlook','us-democracy-threat','sagan-tournament']
FT='binary,multiple_choice,numeric,date,discrete'

def fetch(slug, tries=4):
    for t in range(tries):
        try:
            return api.list_open_questions(slug, forecast_type=FT)
        except Exception as e:
            if '429' in str(e) or '1015' in str(e):
                time.sleep(35); continue
            return None
    return None

pool=[]; seen=set()
for i,s in enumerate(SLUGS):
    posts=fetch(s)
    if posts is None:
        print(f"  {s:28} SKIP (rate/err)", flush=True); time.sleep(11); continue
    nd=0
    for p in posts:
        q=p.get('question') or {}
        qid=q.get('id')
        if qid is None or qid in seen or qid in DONE: continue
        seen.add(qid)
        crowd=api.community_prob(p)
        sc=q.get('scaling') or {}
        pool.append({
            'tournament':s,'post_id':p.get('id'),'question_id':qid,'type':q.get('type'),
            'title':p.get('title') or q.get('title'),'short_title':q.get('short_title'),
            'description':(q.get('description') or '')[:2500],
            'resolution_criteria':(q.get('resolution_criteria') or '')[:2000],
            'fine_print':(q.get('fine_print') or '')[:1200],
            'options':q.get('options'),'unit':q.get('unit'),
            'scaling':{'range_min':sc.get('range_min'),'range_max':sc.get('range_max'),
                       'zero_point':sc.get('zero_point'),
                       'open_upper_bound':q.get('open_upper_bound'),
                       'open_lower_bound':q.get('open_lower_bound'),
                       'inbound_outcome_count':sc.get('inbound_outcome_count'),
                       'continuous_range':sc.get('continuous_range')},
            'close':q.get('scheduled_close_time'),'resolve':q.get('scheduled_resolve_time'),
            'cp_reveal':q.get('cp_reveal_time'),'crowd':crowd,
        })
        nd+=1
    print(f"  {s:28} {len(posts):3} open, +{nd} undone (pool={len(pool)})", flush=True)
    time.sleep(11)

json.dump(pool, open('data/metaculus/pool.json','w'), indent=1)
from collections import Counter
print("\nPOOL:", len(pool), "by type:", dict(Counter(x['type'] for x in pool)))
print("by tournament:", dict(Counter(x['tournament'] for x in pool)))
