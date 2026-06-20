import json, time
from engine.metaculus import api

# Pull non-binary open questions from the bot tournaments and dump their structure.
found = {'multiple_choice': None, 'numeric': None, 'date': None, 'discrete': None}
counts = {}
for slug in ['summer-futureeval-2026', 'spring-aib-2026', 'market-pulse-26q2', 'POTUS-predictions']:
    for ftype in ['multiple_choice', 'numeric', 'date', 'discrete']:
        for attempt in range(3):
            try:
                posts = api.list_open_questions(slug, forecast_type=ftype)
                break
            except Exception as e:
                if '429' in str(e):
                    time.sleep(15); posts = []
                else:
                    posts = []; break
        if posts:
            counts[(slug, ftype)] = len(posts)
            if found[ftype] is None:
                found[ftype] = posts[0]
        time.sleep(4)

print('=== counts (slug, type) -> n open ===')
for k, v in counts.items():
    print(' ', k, v)

for ftype, post in found.items():
    if not post:
        continue
    q = post.get('question') or {}
    print(f"\n===== EXAMPLE {ftype} =====")
    print('title:', (post.get('title') or '')[:80])
    print('q.type:', q.get('type'))
    print('options:', q.get('options'))
    print('scaling:', json.dumps(q.get('scaling')))
    print('open_lower_bound:', q.get('open_lower_bound'), '| open_upper_bound:', q.get('open_upper_bound'))
    print('range_min:', q.get('range_min'), '| range_max:', q.get('range_max'), '| zero_point:', q.get('zero_point'))
    print('unit:', q.get('unit'))
    print('possibilities:', json.dumps(q.get('possibilities'))[:200])
    # save full for building
    json.dump(post, open(f'data/metaculus/example_{ftype}.json', 'w'), indent=1)
