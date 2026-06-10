#!/usr/bin/env python3
"""Split events.js into current + archive.

Moves real events (not canaries, not ADs) whose (dateEnd or date) is before
today into events-archive.js. Keeps the copyright header in both files.
Adds "archivedCount" to EVENTS_DATA so the hero stats can show the true total
without loading the archive.

Run from repo root: python3 tools/split-archive.py
Safe to re-run any time (monthly maintenance): it merges the existing archive
back in, re-splits by today's date, and rewrites both files.
"""
import json, re, sys, datetime, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS = os.path.join(ROOT, 'events.js')
ARCHIVE = os.path.join(ROOT, 'events-archive.js')

def read_js_object(path, varname):
    src = open(path, encoding='utf-8').read()
    m = re.search(r'const\s+' + varname + r'\s*=\s*', src)
    if not m:
        raise SystemExit(f'{varname} not found in {path}')
    header = src[:m.start()]
    start = src.index('{', m.end() - 1)
    depth = 0
    in_str = False
    esc = False
    for i, c in enumerate(src[start:], start):
        if in_str:
            if esc: esc = False
            elif c == '\\': esc = True
            elif c == '"': in_str = False
            continue
        if c == '"': in_str = True
        elif c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return header, json.loads(src[start:i+1])
    raise SystemExit(f'unbalanced braces in {path}')

def write_js(path, header, varname, obj):
    body = json.dumps(obj, ensure_ascii=False, indent=2)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(header + 'const ' + varname + ' = ' + body + ';\n')

def main():
    today = datetime.date.today().isoformat()
    header, data = read_js_object(EVENTS, 'EVENTS_DATA')
    events = data['events']

    # merge existing archive back in (re-run support)
    if os.path.exists(ARCHIVE):
        _, arch = read_js_object(ARCHIVE, 'EVENTS_ARCHIVE')
        seen = {e['id'] for e in events}
        events += [e for e in arch['events'] if e['id'] not in seen]

    def is_past(e):
        if e.get('_canary') or e.get('_ad'):
            return False
        return (e.get('dateEnd') or e['date']) < today

    past = sorted([e for e in events if is_past(e)], key=lambda e: e['date'])
    current = [e for e in events if not is_past(e)]

    canaries = sum(1 for e in current if e.get('_canary'))
    ads = sum(1 for e in current if e.get('_ad'))
    if canaries != 6:
        raise SystemExit(f'ABORT: expected 6 canaries in current set, got {canaries}')

    out = dict(data)
    out['events'] = current
    out['archivedCount'] = len(past)
    out['archivedMonths'] = sorted({int(e['date'][5:7]) for e in past})
    write_js(EVENTS, header, 'EVENTS_DATA', out)
    write_js(ARCHIVE, header, 'EVENTS_ARCHIVE', {'events': past})
    real_current = len(current) - canaries - ads
    print(f'today: {today}')
    print(f'events.js: {real_current} real events + {canaries} canaries + {ads} _ad cards')
    print(f'events-archive.js: {len(past)} past events')

if __name__ == '__main__':
    main()
