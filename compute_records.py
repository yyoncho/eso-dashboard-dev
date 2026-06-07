#!/usr/bin/env python3
"""Compute renewable/battery/export records from all daily JSONL files."""

import json
import re as re_mod
from pathlib import Path

import os
DATA_DIR = Path(os.environ.get('DATA_DIR', Path(__file__).parent / 'data'))
non_RE = ['АЕЦ', 'Кондензационни ТЕЦ', 'Топлофикационни ТЕЦ', 'Заводски ТЕЦ']
RE     = ['ВЕЦ', 'Малки ВЕЦ', 'ВяЕЦ', 'ФЕЦ', 'Био ЕЦ']


def batt_discharge(r):
    return max(0.0, r.get('batt_discharge_mw') or 0)


def main():
    rec = {
        'solar':    {'val': 0.0, 'label': 'Соларно производство', 'unit': 'MW', 'date': None, 'snap_ts': None},
        'batt_chg': {'val': 0.0, 'label': 'Зареждане на ССЕЕ',    'unit': 'MW', 'date': None, 'snap_ts': None},
        'batt_dis': {'val': 0.0, 'label': 'Разреждане на ССЕЕ',   'unit': 'MW', 'date': None, 'snap_ts': None},
        'export':   {'val': 0.0, 'label': 'Пикова мощност износ',  'unit': 'MW', 'date': None, 'snap_ts': None},
        'daily_re': {'val': 0.0, 'label': 'Дневен дял ВЕИ',        'unit': '%',  'date': None, 'snap_ts': None},
        're_hours': {'val': 0.0, 'label': 'Най-дълго 100% ВЕИ',    'unit': 'ч',  'date': None, 'snap_ts': None},
    }

    for f in sorted(DATA_DIR.glob('2026-*.jsonl')):
        day = f.stem
        records = [json.loads(l) for l in f.read_text().strip().split('\n') if l.strip()]
        n = len(records)
        if n == 0:
            continue
        ih = 24 / n
        load_gwh = re_gwh = re_hours = 0

        for r in records:
            ts    = r.get('timestamp_utc') or r.get('timestamp') or ''
            solar = r.get('ФЕЦ') or 0
            chg   = abs(r.get('ССЕЕ_mw') or 0) if r.get('ССЕЕ_state') == 'charging' else 0
            dis   = batt_discharge(r)
            exp   = max(0.0, -(r.get('net_import_mw') or 0))
            load  = r.get('Товар на РБ') or 0
            re_av = sum(r.get(k) or 0 for k in RE) + dis
            load_gwh += load  * ih / 1000
            re_gwh   += min(re_av, load) * ih / 1000
            if load > 0 and re_av >= load:
                re_hours += ih

            if solar > rec['solar']['val']:
                rec['solar'].update(val=round(solar, 1), date=day, snap_ts=ts)
            if chg > rec['batt_chg']['val']:
                rec['batt_chg'].update(val=round(chg, 1), date=day, snap_ts=ts)
            if dis > rec['batt_dis']['val']:
                rec['batt_dis'].update(val=round(dis, 1), date=day, snap_ts=ts)
            if exp > rec['export']['val']:
                rec['export'].update(val=round(exp, 1), date=day, snap_ts=ts)

        daily_re = re_gwh / load_gwh * 100 if load_gwh else 0
        if daily_re > rec['daily_re']['val']:
            rec['daily_re'].update(val=round(daily_re, 1), date=day, snap_ts=None)
        if re_hours > rec['re_hours']['val']:
            rec['re_hours'].update(val=round(re_hours, 2), date=day, snap_ts=None)

    out = DATA_DIR / 'records.json'
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=2))
    print(f'Written {out}')


if __name__ == '__main__':
    main()
