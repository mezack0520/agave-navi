#!/usr/bin/env python3
"""
.ics(iCalendar) ファイル生成 — Googleカレンダー/Apple カレンダーで購読可能。
- /events.ics: 全イベント
- /this-month.ics: 今月のイベント
- /upcoming.ics: 今後のイベント(直近)
"""
import os, json
from datetime import datetime, timedelta, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_JSON = os.path.join(REPO_ROOT, 'events.json')
DOMAIN = 'agave-navi.com'
JST = timezone(timedelta(hours=9))


def fold(line):
    """RFC5545: 75オクテット超えは継続行に折りたたむ。"""
    if len(line.encode('utf-8')) <= 75:
        return line
    out = []
    s = line
    while len(s.encode('utf-8')) > 75:
        # find safe split
        for i in range(75, 1, -1):
            if len(s[:i].encode('utf-8')) <= 75:
                out.append(s[:i])
                s = s[i:]
                break
        else:
            out.append(s); s=''; break
    if s: out.append(s)
    return out[0] + ''.join('\r\n ' + p for p in out[1:])


def esc(s):
    """ICS text-encode: \\, ; , newline。"""
    return (s or '').replace('\\','\\\\').replace(';','\\;').replace(',','\\,').replace('\n','\\n')


def event_to_ics(e):
    slug = e.get('slug','')
    name = e.get('name','')
    d = e.get('date','')
    de = e.get('dateEnd') or d
    if not d: return None
    try:
        dt_start = datetime.strptime(d, '%Y-%m-%d')
        dt_end = datetime.strptime(de, '%Y-%m-%d') + timedelta(days=1)  # ICS DTEND is exclusive
    except ValueError:
        return None
    loc = e.get('location') or ''
    pref = e.get('prefecture') or ''
    desc = e.get('description') or ''
    url = f'https://{DOMAIN}/events/{slug}.html'
    location = ', '.join(x for x in [loc, pref] if x)
    uid = f'{slug}@{DOMAIN}'
    now = datetime.now(JST).strftime('%Y%m%dT%H%M%SZ')
    lines = [
        'BEGIN:VEVENT',
        fold(f'UID:{uid}'),
        fold(f'DTSTAMP:{now}'),
        fold(f'DTSTART;VALUE=DATE:{dt_start.strftime("%Y%m%d")}'),
        fold(f'DTEND;VALUE=DATE:{dt_end.strftime("%Y%m%d")}'),
        fold(f'SUMMARY:{esc(name)}'),
        fold(f'DESCRIPTION:{esc(desc)}\\n\\n詳細: {url}'),
        fold(f'LOCATION:{esc(location)}'),
        fold(f'URL:{url}'),
        'END:VEVENT',
    ]
    return '\r\n'.join(lines)


def make_calendar(name, events):
    head = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        f'PRODID:-//agave-navi.com//{name}//JP',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        f'X-WR-CALNAME:{esc(name)}',
        'X-WR-TIMEZONE:Asia/Tokyo',
        'X-WR-CALDESC:アガベ・多肉・塊根植物のイベント情報を配信',
    ]
    body = []
    for e in events:
        ics = event_to_ics(e)
        if ics: body.append(ics)
    body.append('END:VCALENDAR')
    return '\r\n'.join(head + body) + '\r\n'


def main():
    with open(EVENTS_JSON, encoding='utf-8') as f:
        events = json.load(f)
    today = datetime.now(JST).strftime('%Y-%m-%d')
    cur_ym = datetime.now(JST).strftime('%Y-%m')

    # 全イベント
    with open(os.path.join(REPO_ROOT, 'events.ics'), 'w', encoding='utf-8') as f:
        f.write(make_calendar('アガベイベントナビ - 全イベント', events))
    # 今月
    with open(os.path.join(REPO_ROOT, 'this-month.ics'), 'w', encoding='utf-8') as f:
        f.write(make_calendar('アガベイベントナビ - 今月', [e for e in events if e.get('date','') and e.get('date','')[:7] <= cur_ym <= (e.get('dateEnd') or e.get('date',''))[:7]]))
    # 開催予定
    with open(os.path.join(REPO_ROOT, 'upcoming.ics'), 'w', encoding='utf-8') as f:
        f.write(make_calendar('アガベイベントナビ - 開催予定', [e for e in events if (e.get('dateEnd') or e.get('date','')) >= today]))

    print(f'Generated: events.ics ({len(events)} events), this-month.ics, upcoming.ics')


if __name__ == '__main__':
    main()
