#!/usr/bin/env python3
"""
Fetch ESO Bulgaria real-time data + IBEX/DA prices and write to data/.

Writes every run:
  data/YYYY-MM-DD.jsonl    per-day snapshot log
  data/latest.json         most recent snapshot
  data/today.jsonl         today's snapshots (copy)
  data/index.json          list of available dates

Written once per day:
  data/prices-YYYY-MM.json IBEX 15-min day-ahead prices from energy-charts
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

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

# Sofia is UTC+3 in summer (EEST), UTC+2 in winter (EET).
# We use UTC+2 as conservative offset for date boundary; DST handled by display.
BG_TZ = timezone(timedelta(hours=2))

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

    # Battery discharge via percentage cross-check:
    # ESO computes each source's % against total_supply_including_hidden_discharge.
    # implied_total = source_mw / (source_pct / 100) → average across all sources.
    # batt_discharge_mw = max(0, implied_total - gen_sum)
    implied_totals = []
    for item in gen_data:
        if item is None:
            continue
        label, value = item[0], item[1]
        m = re.search(r'(\d+[.,]\d+)%', label)
        if not m:
            continue
        pct = float(m.group(1).replace(',', '.'))
        try:
            val = float(str(value).replace(',', '.'))
        except (ValueError, TypeError):
            continue
        if pct > 0 and val > 0 and "ССЕЕ" not in label:
            implied_totals.append(val / (pct / 100))

    if implied_totals:
        api_implied_total = round(sum(implied_totals) / len(implied_totals), 1)
        row["api_implied_total_mw"] = api_implied_total
        row["batt_discharge_mw"]    = round(max(0.0, api_implied_total - gen_sum), 1)
    else:
        row["api_implied_total_mw"] = None
        row["batt_discharge_mw"]    = None

    now_utc = datetime.now(timezone.utc)
    row["timestamp_utc"] = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    row["date_bg"]       = now_utc.astimezone(BG_TZ).strftime("%Y-%m-%d")

    return row


def update_prices(year: int, month: int):
    """Download IBEX/DA prices from energy-charts if not yet done today."""
    if not HAS_EC:
        return

    ym       = f"{year:04d}-{month:02d}"
    path     = DATA_DIR / f"prices-{ym}.json"
    today_s  = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if path.exists():
        try:
            cached = json.loads(path.read_text())
            if cached.get("fetched_date") == today_s:
                return   # already fresh
        except Exception:
            pass

    print(f"Fetching IBEX prices for {ym} …", flush=True)
    try:
        data = ec_fetch("price", "bg", ym, ym)
        data["fetched_date"] = today_s
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
