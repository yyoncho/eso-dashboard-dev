"""
Lazy-caching client for the energy-charts.info API.

Cache layout:
  cache/energy_charts/{endpoint}/{country}/{YYYY-MM}.json

Cache rules:
  - Months before the current month: cached forever (data won't change)
  - Current month: cached for CURRENT_MONTH_TTL_HOURS hours

Supported endpoints (see https://api.energy-charts.info/openapi.json):
  public_power    – hourly generation mix by production type
  cbet            – cross-border electricity trading (scheduled/commercial)
  cbpf            – cross-border physical flows
  price           – day-ahead prices
  total_power     – total generation

All endpoints return:
  {
      'unix_seconds': [...],          # UTC timestamps
      '<series_key>': [...],          # one or more value arrays
  }
  e.g. public_power has a 'production_types' list of {name, data} dicts.

Usage:
  from energy_charts import fetch

  gen  = fetch('public_power',  country='ro', start='2026-03', end='2026-05')
  cbet = fetch('cbet',          country='ro', start='2026-03', end='2026-05')
  cbpf = fetch('cbpf',          country='ro', start='2026-03', end='2026-05')

  # Access data:
  unix = gen['unix_seconds']
  for s in gen['production_types']:
      print(s['name'], s['data'][0])

  # cbet / cbpf return neighbor series:
  for s in cbet['cross_border_flows']:
      print(s['name'], s['data'][0])   # name = neighbor country code
"""

import json
import time
import urllib.request
from datetime import datetime, timezone, date
from pathlib import Path
from calendar import monthrange

BASE_URL              = 'https://api.energy-charts.info'
CACHE_ROOT            = Path(__file__).parent / 'cache' / 'energy_charts'
CURRENT_MONTH_TTL_H   = 4          # re-fetch current month if older than this
REQUEST_DELAY_S       = 0.5        # polite delay between API calls
MAX_RETRIES           = 4          # retries on 429 with exponential backoff
RETRY_BASE_S          = 10        # base wait for first retry


# ── Internal helpers ───────────────────────────────────────────────────────────

def _cache_path(endpoint: str, country: str, ym: str) -> Path:
    p = CACHE_ROOT / endpoint / country / f'{ym}.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _is_stale(path: Path, current_month: bool) -> bool:
    if not path.exists():
        return True
    if not current_month:
        return False
    age_h = (time.time() - path.stat().st_mtime) / 3600
    return age_h > CURRENT_MONTH_TTL_H


def _month_url(endpoint: str, country: str, year: int, month: int) -> str:
    _, last_day = monthrange(year, month)
    start = f'{year}-{month:02d}-01T00:00+00:00'
    end   = f'{year}-{month:02d}-{last_day:02d}T23:59+00:00'
    return (
        f'{BASE_URL}/{endpoint}'
        f'?country={country}'
        f'&start={urllib.parse.quote(start)}'
        f'&end={urllib.parse.quote(end)}'
    )


def _fetch_month(endpoint: str, country: str, year: int, month: int) -> dict:
    import urllib.parse
    _, last_day = monthrange(year, month)
    start = f'{year}-{month:02d}-01T00:00+00:00'
    end   = f'{year}-{month:02d}-{last_day:02d}T23:59+00:00'
    url = (
        f'{BASE_URL}/{endpoint}'
        f'?country={country}'
        f'&start={urllib.parse.quote(start)}'
        f'&end={urllib.parse.quote(end)}'
    )
    req = urllib.request.Request(url, headers={'User-Agent': 'energy-charts-cache/1.0'})
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES - 1:
                wait = RETRY_BASE_S * (2 ** attempt)
                print(f'  [energy_charts] 429 rate-limit on {endpoint}/{country}/{year}-{month:02d}, waiting {wait}s...')
                time.sleep(wait)
            else:
                raise


def _load_month(endpoint: str, country: str, year: int, month: int) -> dict | None:
    ym   = f'{year}-{month:02d}'
    path = _cache_path(endpoint, country, ym)
    today = date.today()
    is_current = (year == today.year and month == today.month)

    if _is_stale(path, is_current):
        try:
            data = _fetch_month(endpoint, country, year, month)
            path.write_text(json.dumps(data))
            time.sleep(REQUEST_DELAY_S)
            return data
        except Exception as e:
            print(f'  [energy_charts] WARN {endpoint}/{country}/{ym}: {e}')
            return json.loads(path.read_text()) if path.exists() else None
    else:
        return json.loads(path.read_text())


# ── Series merging ─────────────────────────────────────────────────────────────

def _merge(months: list[dict]) -> dict:
    """Merge a list of monthly API responses into one combined response."""
    if not months:
        return {}

    # Determine the top-level structure from the first non-empty month
    first = months[0]
    result = {'unix_seconds': []}

    # Identify which keys hold lists-of-series vs flat arrays
    series_keys = []   # keys whose value is a list of {name, data} dicts
    array_keys  = []   # keys whose value is a flat array parallel to unix_seconds

    for k, v in first.items():
        if k == 'unix_seconds':
            continue
        if isinstance(v, list) and v and isinstance(v[0], dict) and 'data' in v[0]:
            series_keys.append(k)
        elif isinstance(v, list):
            array_keys.append(k)

    # Initialise series accumulators
    series_acc = {k: {} for k in series_keys}   # key -> {name -> [values]}
    array_acc  = {k: [] for k in array_keys}

    for month_data in months:
        if not month_data:
            continue
        result['unix_seconds'].extend(month_data.get('unix_seconds', []))

        for k in series_keys:
            for s in month_data.get(k, []):
                name = s.get('name', s.get('key', ''))
                if name not in series_acc[k]:
                    series_acc[k][name] = []
                series_acc[k][name].extend(s.get('data', []))

        for k in array_keys:
            array_acc[k].extend(month_data.get(k, []))

    for k in series_keys:
        result[k] = [{'name': n, 'data': d} for n, d in series_acc[k].items()]
    for k in array_keys:
        result[k] = array_acc[k]

    return result


# ── Public API ─────────────────────────────────────────────────────────────────

def fetch(endpoint: str, country: str, start: str, end: str) -> dict:
    """
    Fetch energy-charts data with lazy monthly caching.

    Args:
        endpoint: API endpoint name ('public_power', 'cbet', 'cbpf', 'price', ...)
        country:  Two-letter country code lower-case ('bg', 'ro', 'hu', ...)
        start:    'YYYY-MM' or 'YYYY-MM-DD' — inclusive start
        end:      'YYYY-MM' or 'YYYY-MM-DD' — inclusive end

    Returns:
        Merged dict with 'unix_seconds' and all series arrays.
    """
    # Parse start/end into (year, month) tuples
    def parse_ym(s: str):
        parts = s.split('-')
        return int(parts[0]), int(parts[1])

    start_y, start_m = parse_ym(start)
    end_y,   end_m   = parse_ym(end)

    months = []
    y, m = start_y, start_m
    while (y, m) <= (end_y, end_m):
        data = _load_month(endpoint, country, y, m)
        if data:
            months.append(data)
        m += 1
        if m > 12:
            m = 1
            y += 1

    return _merge(months)


def series_to_dict(data: dict, key: str) -> dict[str, list]:
    """
    Convert a list-of-series structure to {name: [values]} dict.

    Example:
        gen = fetch('public_power', 'bg', '2026-01', '2026-05')
        by_name = series_to_dict(gen, 'production_types')
        solar = by_name['Solar']
    """
    return {s['name']: s['data'] for s in data.get(key, [])}


def as_hourly(data: dict, series_name_or_key: str, series_key: str = None) -> dict:
    """
    Return {datetime_utc: value} for a named series.

    Args:
        data:               Result from fetch()
        series_name_or_key: Name of the series (e.g. 'Solar') or a flat key
        series_key:         Top-level key for list-of-series (e.g. 'production_types')
    """
    unix = data.get('unix_seconds', [])
    values = None

    if series_key:
        for s in data.get(series_key, []):
            if s.get('name') == series_name_or_key:
                values = s['data']
                break
    else:
        values = data.get(series_name_or_key)

    if values is None:
        return {}

    return {
        datetime.fromtimestamp(ts, tz=timezone.utc): v
        for ts, v in zip(unix, values)
        if v is not None
    }


# ── CLI convenience ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    import urllib.parse

    args = sys.argv[1:]
    if len(args) < 4:
        print('Usage: python3 energy_charts.py <endpoint> <country> <start> <end>')
        print('  e.g. python3 energy_charts.py cbet ro 2026-03 2026-05')
        sys.exit(1)

    endpoint, country, start, end = args[:4]
    print(f'Fetching {endpoint} / {country} / {start} → {end} ...')
    result = fetch(endpoint, country, start, end)

    print(f'  unix_seconds: {len(result.get("unix_seconds", []))} points')
    for k, v in result.items():
        if k == 'unix_seconds':
            continue
        if isinstance(v, list) and v and isinstance(v[0], dict):
            print(f'  {k}: {len(v)} series')
            for s in v:
                vals = [x for x in s.get("data", []) if x is not None]
                print(f'    {s["name"]}: {len(vals)} non-null pts, '
                      f'avg={sum(vals)/len(vals):.1f}' if vals else f'    {s["name"]}: no data')
        else:
            non_null = [x for x in v if x is not None]
            print(f'  {k}: {len(non_null)} non-null pts')
