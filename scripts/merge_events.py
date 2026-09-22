#!/usr/bin/env python3
"""
새로 조사한 행사를 공원별 월 데이터 파일(data/<park>/YYYY-MM.json)에 병합한다.

사용법
  python3 scripts/merge_events.py --park cheongna new_events.json
  python3 scripts/merge_events.py --park songdo  new_events.json --dry-run
  cat new.json | python3 scripts/merge_events.py --park songdo -

입력 형식 (둘 중 하나)
  [ {행사}, {행사}, ... ]
  { "events": [ {행사}, ... ], "monthNotes": { "2026-11": "..." } }

병합 규칙
  - 같은 id 가 있으면 기존 행사를 갱신(값이 있는 필드만 덮어씀)
  - id 가 없거나 다른데 title+start 가 같으면 같은 행사로 보고 갱신
  - 그 외는 신규 추가
  - id 가 없으면 start + title 로 자동 생성
  - start 가 공원의 range 밖이면 range 를 자동으로 넓힌다
  - config.updatedAt 을 오늘 날짜로 갱신
종료 코드: 0. 변경 여부는 마지막 줄 "CHANGED=0|1" 로 판단.
"""
import json, os, re, sys, datetime, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
CONFIG = os.path.join(DATA, 'config.json')
REQUIRED = ('title', 'category', 'start')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
MONTH_RE = re.compile(r'^\d{4}-\d{2}$')


def load(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write('\n')


def slug(text):
    text = unicodedata.normalize('NFKC', text).lower()
    text = re.sub(r'[^0-9a-z가-힣]+', '-', text).strip('-')
    return text[:40] or 'event'


def norm_title(t):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', t or '')).lower()


def widen(rng, month):
    """행사 월이 범위 밖이면 범위를 넓히고 True 를 돌려준다."""
    changed = False
    if month < rng['start']:
        rng['start'] = month; changed = True
    if month > rng['end']:
        rng['end'] = month; changed = True
    return changed


def main():
    args, park_id, dry = [], None, False
    it = iter(sys.argv[1:])
    for a in it:
        if a == '--park':
            park_id = next(it, None)
        elif a == '--dry-run':
            dry = True
        elif not a.startswith('--'):
            args.append(a)
    if not args or not park_id:
        print(__doc__); sys.exit(2)

    config = load(CONFIG)
    if config is None:
        print('ERROR: data/config.json 이 없습니다.'); sys.exit(1)
    park = next((p for p in config.get('parks', []) if p['id'] == park_id), None)
    if park is None:
        ids = ', '.join(p['id'] for p in config.get('parks', []))
        print(f'ERROR: 알 수 없는 공원 "{park_id}". 등록된 공원: {ids}'); sys.exit(1)

    raw = sys.stdin.read() if args[0] == '-' else open(args[0], encoding='utf-8').read()
    payload = json.loads(raw)
    new_events = payload if isinstance(payload, list) else payload.get('events', [])
    new_notes = {} if isinstance(payload, list) else (payload.get('monthNotes') or {})

    cats = set(config.get('categories', {}).keys())
    park_dir = os.path.join(DATA, park_id)
    added, updated, skipped, notes_msg = [], [], [], []
    touched = {}

    for e in new_events:
        missing = [k for k in REQUIRED if not e.get(k)]
        if missing:
            skipped.append((e.get('title', '?'), '필수 필드 누락: ' + ','.join(missing))); continue
        if not DATE_RE.match(e['start']) or (e.get('end') and not DATE_RE.match(e['end'])):
            skipped.append((e['title'], '날짜 형식 오류(YYYY-MM-DD)')); continue
        if e.get('end') and e['end'] < e['start']:
            skipped.append((e['title'], 'end 가 start 보다 이릅니다')); continue
        if e['category'] not in cats:
            skipped.append((e['title'], f"알 수 없는 category: {e['category']} (가능: {','.join(sorted(cats))})")); continue

        month = e['start'][:7]
        if widen(park['range'], month):
            notes_msg.append(f"표시 범위를 {park['range']['start']}~{park['range']['end']} 로 넓힘")
        if not e.get('id'):
            e['id'] = e['start'] + '-' + slug(e['title'])

        path = os.path.join(park_dir, month + '.json')
        if month not in touched:
            touched[month] = load(path, {'month': month, 'events': []})
        events = touched[month]['events']

        match = next((x for x in events if x.get('id') == e['id']), None) or \
                next((x for x in events if norm_title(x.get('title')) == norm_title(e['title'])
                      and x.get('start') == e['start']), None)
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
        if not MONTH_RE.match(k):
            skipped.append((k, 'monthNotes 키는 YYYY-MM 형식이어야 합니다')); continue
        park.setdefault('monthNotes', {})
        if park['monthNotes'].get(k) != v:
            park['monthNotes'][k] = v; updated.append(f'monthNotes[{k}]')

    changed = bool(added or updated or notes_msg)
    if changed and not dry:
        for month, data in touched.items():
            save(os.path.join(park_dir, month + '.json'), data)
        # 범위 안의 빈 달 파일도 만들어 둔다 (404 를 줄이기 위함)
        for mm in month_range(park['range']):
            p = os.path.join(park_dir, mm + '.json')
            if not os.path.exists(p):
                save(p, {'month': mm, 'events': []})
        config['updatedAt'] = datetime.date.today().isoformat()
        save(CONFIG, config)

    print(f"[{park['name']}] 추가 {len(added)}건: " + (', '.join(added) or '-'))
    print(f"[{park['name']}] 갱신 {len(updated)}건: " + (', '.join(updated) or '-'))
    for m in notes_msg: print('안내: ' + m)
    for t, why in skipped: print(f"건너뜀: {t} — {why}")
    if dry: print('(dry-run: 파일을 쓰지 않았습니다)')
    print('CHANGED=' + ('1' if changed else '0'))


def month_range(rng):
    out = []
    y, m = map(int, rng['start'].split('-'))
    ey, em = map(int, rng['end'].split('-'))
    while (y, m) <= (ey, em):
        out.append(f'{y}-{m:02d}')
        m += 1
        if m > 12: m = 1; y += 1
    return out


if __name__ == '__main__':
    main()
