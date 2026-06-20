from engine.metaculus import api

print('=== Summer FutureEval open binary (close TODAY) ===')
for p in api.list_open_questions('summer-futureeval-2026'):
    if not api.binary_question(p):
        continue
    q = api.question_text(p)
    print(f"qid={q['question_id']} close={q['close_time']}")
    print(f"  {q['title']}")
    print(f"  RC: {(q['resolution_criteria'] or '').replace(chr(10),' ')[:240]}")

print('\n=== open BINARY counts across key tournaments ===')
slugs = ['ai-safety', 'ai-technical-benchmarks', 'ai-2027', 'taiwan', 'iran-israel-conflict',
         'current-events', 'POTUS-predictions', 'midterms-2026', 'us-democracy-threat',
         'nuclear-horizons', 'chinese-ai-chips', 'ai-industry-milestones', 'market-pulse-26q2',
         'future-of-ai', 'quantum-computing', 'ai-demonstrations', 'labor-hub']
tot = 0
for s in slugs:
    try:
        b = [p for p in api.list_open_questions(s) if api.binary_question(p)]
        if b:
            print(f'  {s:26} {len(b)} open binary')
            tot += len(b)
    except Exception as e:
        print(f'  {s:26} ERR {str(e)[:40]}')
print(f'  TOTAL across these: {tot} open binary')
