import json
import unittest
from datetime import date
from index_rebalance import ROOT, validate, quarter_dates, events_for, render, utc

class TestCalendar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.years=validate(json.loads((ROOT/'holidays_snapshot.json').read_text()))
        cls.cfg=json.loads((ROOT/'config.json').read_text())
        cls.events=events_for(cls.years,cls.cfg)
    def test_dec_2026(self):
        self.assertEqual(quarter_dates(2026,12,self.years),(date(2026,12,18),date(2026,12,21),date(2026,12,11)))
    def test_juneteenth(self):
        self.assertEqual(quarter_dates(2027,6,self.years),(date(2027,6,17),date(2027,6,21),date(2027,6,10)))
    def test_month_end(self):
        e=next(x for x in self.events if x['uid']=='mend-2026-11')
        self.assertEqual(utc(e['start']),'20261130T203000Z')
        self.assertEqual(utc(e['end']),'20261130T210000Z')
    def test_dst(self):
        e=next(x for x in self.events if x['uid']=='ndx-eff-2027-06')
        self.assertEqual(utc(e['start']),'20270621T133000Z')
    def test_unique_and_ics(self):
        self.assertEqual(len(self.events),len({x['uid'] for x in self.events}))
        raw=render(self.events,'20261115T000000Z')
        self.assertEqual(raw.count(b'BEGIN:VEVENT'),len(self.events))
        self.assertEqual(raw.count(b'END:VEVENT'),len(self.events))
        self.assertTrue(all(len(line)<=75 for line in raw.split(b'\r\n')))
    def test_switches(self):
        e=events_for(self.years,dict(self.cfg,include_month_end=False,include_quarter_end=False))
        self.assertFalse(any(x['uid'].startswith('mend') for x in e))
