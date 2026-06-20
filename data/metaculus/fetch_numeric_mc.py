import json, time
from engine.metaculus import api, numeric

out = {'numeric': [], 'multiple_choice': [], 'discrete': []}
plan = [('summer-futureeval-2026', 'numeric'), ('POTUS-predictions', 'multiple_choice'),
        ('POTUS-predictions', 'numeric'), ('POTUS-predictions', 'discrete')]
for slug, ftype in plan:
    posts = []
    for attempt in range(3):
        try:
            posts = api.list_open_questions(slug, forecast_type=ftype); break
        except Exception as e:
            if '429' in str(e):
                time.sleep(15)
            else:
                break
    for p in posts:
        m = numeric.question_meta(p)
        m['slug'] = slug
        out[ftype if ftype in out else 'numeric'].append(m)
    print(f'  {slug}/{ftype}: {len(posts)}', flush=True)
    time.sleep(5)

json.dump(out, open('data/metaculus/numeric_mc_questions.json', 'w'), indent=1)
print(f"\nnumeric={len(out['numeric'])} mc={len(out['multiple_choice'])} discrete={len(out['discrete'])}")
for m in out['numeric']:
    print(f"  [num {m['range_min']}-{m['range_max']} {m['unit']}] {m['title'][:62]}")
for m in out['multiple_choice']:
    print(f"  [mc {len(m['options'])}opt] {m['title'][:62]} :: {m['options']}")
for m in out['discrete']:
    print(f"  [disc {m['range_min']}-{m['range_max']} {m['unit']}] {m['title'][:60]}")
