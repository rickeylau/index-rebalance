#!/usr/bin/env python3
"""Build rule-based US index rebalance reminders (not a live index announcement feed)."""
import argparse
import calendar
import json
import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
HOLIDAYS = 'https://raw.githubusercontent.com/rickeylau/market-holidays/main/holidays.json'
SP = 'https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-us-indices.pdf'
SP_POLICY = 'https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-equity-indices-policies-practices.pdf'
NDX = 'https://indexes.nasdaq.com/docs/Methodology_NDX.pdf'
ET = ZoneInfo('America/New_York')
SNAPSHOT = ROOT / 'holidays_snapshot.json'
OUTPUT = ROOT / 'index-rebalance.ics'
CONFIG = ROOT / 'config.json'
QUARTERS = (3, 6, 9, 12)


def validate(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('events'), list):
        raise ValueError('Invalid holiday source')
    if payload.get('source') != 'https://www.cboe.com/about/hours/us-options/':
        raise ValueError('Unexpected holiday data source')
    by_year = {}
    seen = set()
    for item in payload['events']:
        d = date.fromisoformat(item['date']); close = item['close']
        if d in seen or not item['holiday'] or d.weekday() >= 5:
            raise ValueError(f'Invalid/duplicate holiday: {item}')
        seen.add(d)
        if close is not None:
            t = time.fromisoformat(close)
            if not time(9,30) < t < time(16):
                raise ValueError(f'Invalid early close: {item}')
        by_year.setdefault(d.year, {})[d] = close
    for y, holidays in by_year.items():
        if not 9 <= sum(v is None for v in holidays.values()) <= 15:
            raise ValueError(f'Incomplete holiday year: {y}')
    if not by_year:
        raise ValueError('No holiday years')
    return by_year


def trading(d, by_year):
    if d.year not in by_year:
        raise ValueError(f'No published holiday schedule for {d.year}')
    return d.weekday() < 5 and not (d in by_year[d.year] and by_year[d.year][d] is None)


def move(d, direction, by_year, inclusive=False):
    if not inclusive:
        d += timedelta(days=direction)
    while not trading(d, by_year):
        d += timedelta(days=direction)
    return d


def close_at(d, by_year):
    return datetime.combine(d, time.fromisoformat(by_year[d.year].get(d, '16:00')), ET)


def third_friday(y, m):
    d = date(y, m, 15)
    return d + timedelta(days=(4 - d.weekday()) % 7)


def quarter_dates(y, m, by_year):
    f = third_friday(y, m)
    closing = move(f, -1, by_year, inclusive=True)
    effective = move(f, 1, by_year)
    announce = effective
    for _ in range(6):
        announce = move(announce, -1, by_year)
    return closing, effective, announce


def events_for(by_year, cfg):
    minutes = cfg.get('close_reminder_minutes', 30)
    if not isinstance(minutes, int) or not 5 <= minutes <= 120:
        raise ValueError('close_reminder_minutes must be 5–120')
    result = []
    def add(uid, title, start, end, description, url):
        result.append(dict(uid=uid, title=title, start=start, end=end, description=description, url=url))
    for y in sorted(by_year):
        for m in range(1,13):
            key = f'{y}-{m:02}'
            if m in QUARTERS:
                close_day, effective, announce = quarter_dates(y, m, by_year)
                end = close_at(close_day, by_year)
                label = 'Annual Reconstitution' if m == 12 else 'Quarterly Rebalance'
                if cfg.get('include_quarterly_close', True):
                    add(f'qclose-{key}', 'SPX / NDX Rebalance Close (Expected)', end-timedelta(minutes=minutes), end,
                        'Rule-based reminder for the closing session before scheduled index adjustments; not a confirmed announcement or a forecast of trading flows. If third Friday is closed, previous session is a planning assumption. Check official notices. S&P 500 share updates are quarterly; membership changes may occur at any time. Sources: '+SP+' ; '+SP_POLICY+' ; '+NDX, SP)
                if cfg.get('include_ndx_announcement', True):
                    t = close_at(announce, by_year)
                    add(f'ndx-ann-{key}', f'NDX {label} Announcement (Expected)', t, t+timedelta(minutes=15),
                        'Nasdaq methodology schedules the announcement after the close of the sixth trading day before effectiveness. Event starts at the close as a reminder; actual release time can differ. Verify Nasdaq notices.', NDX)
                if cfg.get('include_ndx_effective', True):
                    t = datetime.combine(effective, time(9,30), ET)
                    add(f'ndx-eff-{key}', f'NDX {label} Effective (Expected)', t, t+timedelta(minutes=15),
                        'Rule-based expected effective time at the opening of the first trading day following the third Friday. Not a confirmation of constituent changes. Verify Nasdaq notices.', NDX)
            quarter = m in QUARTERS
            if (quarter and cfg.get('include_quarter_end', True)) or (not quarter and cfg.get('include_month_end', True)):
                d = move(date(y, m, calendar.monthrange(y,m)[1]), -1, by_year, inclusive=True)
                end = close_at(d, by_year)
                label = 'Quarter-End' if quarter else 'Month-End'
                add(f'mend-{key}', f'{label} Rebalance Reminder', end-timedelta(minutes=minutes), end,
                    'Custom reminder for final regular trading session of the month. Actual institutional flows are not known or guaranteed; this is not an official index event. Holiday-adjusted using Cboe regular-session calendar.', 'https://www.cboe.com/about/hours/us-options/')
    return sorted(result, key=lambda e:(e['start'],e['uid']))


def esc(s):
    return s.replace('\\','\\\\').replace('\n','\\n').replace(';','\\;').replace(',','\\,')


def fold(s):
    lines=[]; part=''
    for ch in s:
        if len((part+ch).encode('utf-8'))>75:
            lines.append(part); part=' '+ch
        else: part+=ch
    return '\r\n'.join(lines+[part])


def utc(dt):
    return dt.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def render(events, stamp):
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Index Rebalance Calendar//EN','CALSCALE:GREGORIAN','X-WR-CALNAME:Index Rebalance','X-WR-TIMEZONE:America/New_York','X-WR-CALDESC:Rule-based SPX and NDX schedule reminders. Verify official announcements.']
    for e in events:
        lines.extend(['BEGIN:VEVENT',f'UID:{e["uid"]}@index-rebalance',f'DTSTAMP:{stamp}',f'DTSTART:{utc(e["start"])}',f'DTEND:{utc(e["end"])}',f'SUMMARY:{esc(e["title"])}',f'DESCRIPTION:{esc(e["description"])}',f'URL:{e["url"]}','TRANSP:TRANSPARENT','END:VEVENT'])
    lines.append('END:VCALENDAR')
    return ('\r\n'.join(fold(x) for x in lines)+'\r\n').encode('utf-8')


def atomic(path, data):
    if path.exists() and path.read_bytes() == data: return
    temp = path.with_suffix(path.suffix+'.tmp'); temp.write_bytes(data); temp.replace(path)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--offline', action='store_true'); args=parser.parse_args()
    old=json.loads(SNAPSHOT.read_text(encoding='utf-8')); old_years=validate(old)
    payload=old
    if not args.offline:
        req=Request(HOLIDAYS,headers={'User-Agent':'IndexRebalanceCalendar/1.0','Accept':'application/json'})
        with urlopen(req,timeout=30) as response:
            raw=response.read(1024*1024+1)
        if len(raw)>1024*1024: raise ValueError('Holiday payload too large')
        payload=json.loads(raw); years=validate(payload)
        current=datetime.now(ET).year
        if current not in years or not set(old_years).issubset(years):
            raise ValueError('Holiday coverage regressed; refusing to replace calendar')
    cfg=json.loads(CONFIG.read_text(encoding='utf-8'))
    events=events_for(validate(payload),cfg)
    if not events: raise ValueError('No events; refusing to overwrite')
    stamp=payload.get('stamp','')
    if not re.fullmatch(r'\d{8}T\d{6}Z',stamp): raise ValueError('Invalid snapshot timestamp')
    # Keep stable DTSTAMP on unchanged inputs; no hourly commit noise.
    data=render(events,stamp)
    atomic(OUTPUT,data)
    atomic(SNAPSHOT,(json.dumps(payload,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(f'{len(events)} events in {OUTPUT.name}')

if __name__=='__main__': main()
