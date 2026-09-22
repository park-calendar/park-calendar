#!/usr/bin/env python3
"""
새로 조사한 행사를 월별 데이터 파일(data/YYYY-MM.json)에 병합한다.

사용법
  python3 scripts/merge_events.py new_events.json            # 병합
  python3 scripts/merge_events.py new_events.json --dry-run  # 결과만 출력
  cat new_events.json | python3 scripts/merge_events.py -    # stdin

입력 형식 (둘 중 하나)
  [ {행사}, {행사}, ... ]
  { "events": [ {행사}, ... ], "monthNotes": { "2026-11": "..." } }

병합 규칙
  - 같은 id 가 있으면 기존 행사를 갱신(덮어쓰기: 새 값이 있는 필드만)
  - id 가 없거나 다른데 title+start 가 같으면 같은 행사로 보고 갱신
  - 그 외는 신규 추가
  - id 가 없으면 start + title 로 자동 생성
  - start 가 config.range 밖이면 range 를 확장하지 않고 경고만 출력
  - config.updatedAt 을 오늘 날짜로 갱신
종료 코드: 0 (변경 없음 포함). 변경 여부는 마지막 줄 "CHANGED=0|1" 로 판단.
"""
import json, os, re, sys, datetime, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
REQUIRED = ('title', 'category', 'start')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save(path, obj):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write('\n')


def slug(text):
    text = unicodedata.normalize('NFKC', text).lower()
    text = re.sub(r'[^0-9a-z가-힣]+', '-', text).strip('-')
    return text[:40] or 'event'


def norm_title(t):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', t or '')).lower()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dry = '--dry-run' in sys.argv
    if not args:
        print(__doc__); sys.exit(2)
    raw = sys.stdin.read() if args[0] == '-' else open(args[0], encoding='utf-8').read()
    payload = json.loads(raw)
    new_events = payload if isinstance(payload, list) else payload.get('events', [])
    new_notes = {} if isinstance(payload, list) else payload.get('monthNotes', {}) or {}

    config = load(os.path.join(DATA, 'config.json'), None)
    if config is None:
        print('ERROR: data/config.json 이 없습니다.'); sys.exit(1)
    cats = set(config.get('categories', {}).keys())
    rng = config['range']

    added, updated, skipped, warnings = [], [], [], []
    touched = {}  # month -> data

    for e in new_events:
        missing = [k for k in REQUIRED if not e.get(k)]
        if missing:
            skipped.append((e.get('title', '?'), '필수 필드 누락: ' + ','.join(missing))); continue
        if not DATE_RE.match(e['start']) or (e.get('end') and not DATE_RE.match(e['end'])):
            skipped.append((e['title'], '날짜 형식 오류(YYYY-MM-DD)')); continue
        if e['category'] not in cats:
            skipped.append((e['title'], '알 수 없는 category: ' + e['category'] + ' (가능: ' + ','.join(sorted(cats)) + ')')); continue
        month = e['start'][:7]
        if not (rng['start'] <= month <= rng['end']):
            warnings.append(f"{e['title']}: start {e['start']} 가 표시 범위({rng['start']}~{rng['end']}) 밖입니다. config.range 를 넓혀야 달력에 보입니다.")
        if not e.get('id'):
            e['id'] = e['start'] + '-' + slug(e['title'])

        path = os.path.join(DATA, month + '.json')
        if month not in touched:
            touched[month] = load(path, {'month': month, 'events': []})
        events = touched[month]['events']

        match = next((x for x in events if x.get('id') == e['id']), None) or \
                next((x for x in events if norm_title(x.get('title')) == norm_title(e['title']) and x.get('start') == e['start']), None)
        if match:
            before = json.dumps(match, ensure_ascii=False, sort_keys=True)
            for k, v in e.items():
                if v not in (None, '', [], {}):
                    match[k] = v
            if json.dumps(match, ensure_ascii=False, sort_keys=True) != before:
                updated.append(match['title'])
        else:
            events.append(e); added.append(e['title'])
        events.sort(key=lambda x: (x['start'], x.get('time') or ''))

    for k, v in new_notes.items():
        if config.setdefault('monthNotes', {}).get(k) != v:
            config['monthNotes'][k] = v; updated.append(f'monthNotes[{k}]')

    changed = bool(added or updated)
    if changed and not dry:
        for month, data in touched.items():
            save(os.path.join(DATA, month + '.json'), data)
        config['updatedAt'] = datetime.date.today().isoformat()
        save(os.path.join(DATA, 'config.json'), config)

    print(f"추가 {len(added)}건: " + (', '.join(added) or '-'))
    print(f"갱신 {len(updated)}건: " + (', '.join(updated) or '-'))
    for t, why in skipped: print(f"건너뜀: {t} — {why}")
    for w in warnings: print('경고: ' + w)
    if dry: print('(dry-run: 파일을 쓰지 않았습니다)')
    print('CHANGED=' + ('1' if changed else '0'))


if __name__ == '__main__':
    main()
