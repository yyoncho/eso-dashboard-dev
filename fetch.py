#!/usr/bin/env python3
"""
Fetch ESO Bulgaria real-time data and write to data/ directory.

Writes:
  data/YYYY-MM-DD.jsonl   — per-day log (one JSON per line, appended)
  data/latest.json        — most recent snapshot
  data/today.jsonl        — alias: same as today's JSONL (symlink or copy)
  data/index.json         — list of available dates
"""

import json
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.eso.bg/"}
BG_TZ = timezone(timedelta(hours=3))  # Sofia = UTC+3 in summer (approx)

GEN_COLS = [
    "АЕЦ", "Кондензационни ТЕЦ", "Топлофикационни ТЕЦ", "Заводски ТЕЦ",
    "ВЕЦ", "Малки ВЕЦ", "ВяЕЦ", "ФЕЦ", "Био ЕЦ",
]

# English labels for the frontend
GEN_LABELS_EN = {
    "АЕЦ": "Nuclear",
    "Кондензационни ТЕЦ": "Coal (condensing)",
    "Топлофикационни ТЕЦ": "CHP thermal",
    "Заводски ТЕЦ": "Industrial CHP",
    "ВЕЦ": "Hydro",
    "Малки ВЕЦ": "Small hydro",
    "ВяЕЦ": "Wind",
    "ФЕЦ": "Solar",
    "Био ЕЦ": "Biomass",
}

FLOW_COUNTRIES = ["RO", "SR", "MK", "GR", "TR"]
FLOW_LABELS_EN = {"RO": "Romania", "SR": "Serbia", "MK": "N.Macedonia", "GR": "Greece", "TR": "Turkey"}


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

    row["RO_mw"] = flows.get("RO_data", 0)
    row["SR_mw"] = flows.get("SR_data", 0)
    row["MK_mw"] = flows.get("MK_data", 0)
    row["GR_mw"] = flows.get("GR_data", 0)
    row["TR_mw"] = flows.get("TR_data", 0)

    gen_sum    = sum(row.get(c, 0) for c in GEN_COLS)
    net_import = sum(row.get(f"{c}_mw", 0) for c in FLOW_COUNTRIES)
    load       = row.get("Товар на РБ", 0)

    row["gen_total_mw"]  = round(gen_sum, 1)
    row["net_import_mw"] = round(net_import, 1)
    row["load_mw"]       = round(load, 1)

    now_utc = datetime.now(timezone.utc)
    row["timestamp_utc"] = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    row["date_bg"]       = now_utc.astimezone(BG_TZ).strftime("%Y-%m-%d")

    return row


def append_day_file(record):
    date_str = record["date_bg"]
    path = DATA_DIR / f"{date_str}.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_today_file(date_str):
    src = DATA_DIR / f"{date_str}.jsonl"
    dst = DATA_DIR / "today.jsonl"
    if src.exists():
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def write_index():
    dates = sorted(
        p.stem for p in DATA_DIR.glob("????-??-??.jsonl")
    )
    (DATA_DIR / "index.json").write_text(
        json.dumps({"dates": dates}, ensure_ascii=False),
        encoding="utf-8",
    )


def main():
    record = build_record()
    append_day_file(record)
    (DATA_DIR / "latest.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_today_file(record["date_bg"])
    write_index()
    print(f"[{record['timestamp_utc']}] written — load {record['load_mw']} MW, gen {record['gen_total_mw']} MW")


if __name__ == "__main__":
    main()
