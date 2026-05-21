#!/usr/bin/env python3
"""
Fetch ESO Bulgaria real-time data + IBEX/DA prices and write to data/.

Writes every run:
  data/YYYY-MM-DD.jsonl    per-day snapshot log
  data/latest.json         most recent snapshot
  data/today.jsonl         today's snapshots (copy)
  data/index.json          list of available dates

Refreshed every 4 hours (energy-charts updates prices throughout the day):
  data/prices-YYYY-MM.json IBEX 15-min prices from energy-charts
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT     = Path(__file__).parent
DATA_DIR = Path(os.environ.get("DATA_DIR", str(ROOT / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# energy_charts module lives alongside us once deployed; also try local source
sys.path.insert(0, str(ROOT))
try:
    from energy_charts import fetch as ec_fetch
    HAS_EC = True
except ImportError:
    HAS_EC = False

HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.eso.bg/"}

BG_TZ = ZoneInfo('Europe/Sofia')

GEN_COLS = [
    "АЕЦ", "Кондензационни ТЕЦ", "Топлофикационни ТЕЦ", "Заводски ТЕЦ",
    "ВЕЦ", "Малки ВЕЦ", "ВяЕЦ", "ФЕЦ", "Био ЕЦ",
]
FLOW_COUNTRIES = ["RO", "SR", "MK", "GR", "TR"]


def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def build_record():
    gen_data = fetch_json("https://www.eso.bg/api/rabota_na_EEC_json.php?tovar")
    flows    = fetch_json("https://www.eso.bg/api/scada_live_json_pure.php")

    row = {}
    for item in gen_data:
        if item is None:
            continue
        label, value = item[0], item[1]
        name = re.sub(r"\s+\d+[.,]\d+%$", "", label).strip()
        if "ССЕЕ" in name:
            row["ССЕЕ_mw"]    = -float(value) if "зареждане" in label else float(value)
            row["ССЕЕ_state"] = "charging" if "зареждане" in label else "discharging"
        else:
            try:
                row[name] = float(str(value).replace(",", "."))
            except (ValueError, TypeError):
                pass

    for c in FLOW_COUNTRIES:
        row[f"{c}_mw"] = flows.get(f"{c}_data", 0) or 0

    gen_sum    = sum(row.get(c, 0) for c in GEN_COLS)
    net_import = sum(row.get(f"{c}_mw", 0) for c in FLOW_COUNTRIES)
    load       = row.get("Товар на РБ", 0)

    row["gen_total_mw"]  = round(gen_sum, 1)
    row["net_import_mw"] = round(net_import, 1)
    row["load_mw"]       = round(load, 1)

    ssee  = abs(row.get("ССЕЕ_mw", 0) or 0)
    state = row.get("ССЕЕ_state", "")
    row["batt_charge_mw"] = round(ssee if state == "charging" else 0.0, 1)

    # Discharge: ESO bakes it into the % denominator — back-calculate implied total
    implied = []
    for item in gen_data:
        if item is None: continue
        label, value = item[0], item[1]
        if "ССЕЕ" in label: continue
        m = re.search(r'(\d+[.,]\d+)%', label)
        if not m: continue
        pct = float(m.group(1).replace(',', '.'))
        try: val = float(str(value).replace(',', '.'))
        except: continue
        if pct > 0 and val > 0:
            implied.append(val / (pct / 100))
    # Percentage precision is 0.01% → ~50 MW noise at typical load; suppress below that
    if implied:
        api_total = sum(implied) / len(implied)
        raw = max(0.0, api_total - gen_sum)
    else:
        raw = max(0.0, load - gen_sum - net_import)
    row["batt_discharge_mw"] = round(raw if raw >= 50.0 else 0.0, 1)

    now_utc = datetime.now(timezone.utc)
    row["timestamp_utc"] = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    row["date_bg"]       = now_utc.astimezone(BG_TZ).strftime("%Y-%m-%d")

    return row


def _fetch_prices_direct(year: int, month: int) -> dict:
    """Fetch BG prices directly using bzn=BG (not country=bg).

    The energy_charts module uses ?country=bg for all endpoints, but the price
    endpoint requires ?bzn=BG — these return different data. Calling directly
    ensures we get the correct IBEX bidding-zone prices.
    """
    from calendar import monthrange
    import urllib.parse
    _, last_day = monthrange(year, month)
    start = f"{year}-{month:02d}-01T00:00+00:00"
    end   = f"{year}-{month:02d}-{last_day:02d}T23:59+00:00"
    url = (
        "https://api.energy-charts.info/price"
        f"?bzn=BG"
        f"&start={urllib.parse.quote(start)}"
        f"&end={urllib.parse.quote(end)}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "eso-dashboard/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def update_prices(year: int, month: int):
    """Download IBEX/DA prices from energy-charts, refreshing every 4 hours.

    energy-charts blends DA and real-time prices and updates throughout the day,
    so a once-per-day fetch produces stale values for past hours.
    """
    ym   = f"{year:04d}-{month:02d}"
    path = DATA_DIR / f"prices-{ym}.json"
    now  = datetime.now(timezone.utc)

    if path.exists():
        try:
            cached = json.loads(path.read_text())
            fetched_at = cached.get("fetched_at")
            if fetched_at:
                age_h = (now - datetime.fromisoformat(fetched_at)).total_seconds() / 3600
                if age_h < 4:
                    return   # still fresh
        except Exception:
            pass

    print(f"Fetching IBEX prices for {ym} …", flush=True)
    try:
        data = _fetch_prices_direct(year, month)
        data["fetched_at"] = now.isoformat()
        path.write_text(json.dumps(data))
        print(f"  → {len(data.get('unix_seconds', []))} price points", flush=True)
    except Exception as e:
        print(f"  WARN: price fetch failed: {e}", flush=True)


def append_day_file(record):
    path = DATA_DIR / f"{record['date_bg']}.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_today_alias(date_str):
    src = DATA_DIR / f"{date_str}.jsonl"
    dst = DATA_DIR / "today.jsonl"
    if src.exists():
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def write_index():
    dates = sorted(p.stem for p in DATA_DIR.glob("????-??-??.jsonl"))
    (DATA_DIR / "index.json").write_text(json.dumps({"dates": dates}))


def main():
    record = build_record()
    append_day_file(record)
    (DATA_DIR / "latest.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2)
    )
    write_today_alias(record["date_bg"])
    write_index()

    # refresh prices for current month (once per day)
    now_utc = datetime.now(timezone.utc)
    update_prices(now_utc.year, now_utc.month)

    print(f"[{record['timestamp_utc']}] load {record['load_mw']} MW  "
          f"gen {record['gen_total_mw']} MW  "
          f"net_import {record['net_import_mw']} MW")


if __name__ == "__main__":
    main()
