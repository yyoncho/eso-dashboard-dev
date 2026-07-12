#!/usr/bin/env python3
"""Generate en.html (English dashboard) from index.html (Bulgarian).

Pure string translation — no logic changes. Data keys coming from the
JSONL/records feeds (АЕЦ, ФЕЦ, Товар на РБ, ССЕЕ_mw, …) are kept intact;
only display labels are translated. records.json labels arrive in Bulgarian
from the data branch, so an English remap is injected into loadRecords().

Run after editing index.html:  python3 build_en.py
The script fails loudly if an expected Bulgarian string is missing, so
translations never silently rot.
"""
import re
import sys
from pathlib import Path

SRC = Path(__file__).parent / 'index.html'
DST = Path(__file__).parent / 'en.html'

text = SRC.read_text(encoding='utf-8')

# (bulgarian, english) — applied in order; each must occur at least once.
# Longer/more specific strings must come before shorter substrings.
PAIRS = [
    # ── head / header ──
    ('<html lang="bg">', '<html lang="en">'),
    ('<title>БГ Мрежов Монитор — неофициален</title>',
     '<title>BG Grid Monitor — unofficial</title>'),
    ('<div class="logo-circle">БГ</div>', '<div class="logo-circle">BG</div>'),
    ('<h1>Мрежов монитор — България</h1>', '<h1>Grid Monitor — Bulgaria</h1>'),
    ('<p>Неофициален ресурс &bull; данни от ЕСО ЕАД и IBEX &bull; не представлява ЕСО ЕАД</p>',
     '<p>Unofficial resource &bull; data from ESO EAD and IBEX &bull; not affiliated with ESO EAD</p>'),
    ('Зареждане…', 'Loading…'),
    ('>Днес</button>', '>Today</button>'),
    ('>Анализи</div>', '>Analyses</div>'),
    ('⚛ АЕЦ Козлодуй — LCOE калкулатор', '⚛ Kozloduy NPP — LCOE calculator'),
    ('📈 Дългосрочни тенденции', '📈 Long-term trends'),
    ('🏆 Рекорди</button>', '🏆 Records</button>'),
    ('Рекорди — ВЕИ и ССЕЕ', 'Records — RES &amp; BESS'),
    ('Пълна история на рекордите →', 'Full record history →'),
    ('📅 Исторически данни — показват се архивни записи, не актуална информация',
     '📅 Historical data — showing archived records, not live information'),
    ('>Снимка:</span>', '>Snapshot:</span>'),

    # ── stat cards ──
    ('<div class="stat-label">Товар на РБ</div>', '<div class="stat-label">System load</div>'),
    ('<div class="stat-label">Производство</div>', '<div class="stat-label">Generation</div>'),
    ('<div class="stat-label">IBEX цена</div>', '<div class="stat-label">IBEX price</div>'),
    ('>Внос/Износ</div>', '>Imports/Exports</div>'),

    # ── pie panel ──
    ('Структура на производство — живо', 'Generation mix — live'),
    ('>МВт</button>', '>MW</button>'),
    ('title="Информация"', 'title="Info"'),
    ('Данните за производство по източници са в реално време от ЕСО ЕАД. Вносът и износът се показват директно от ЕСО без допълнителна обработка. ССЕЕ (батерия) се връща от API-то на ЕСО, но не е включено в процентното разпределение на диаграмата — това обяснява „липсващите" проценти до 100%. Зареждането се изчислява като разлика между общото потребление и сумата от всички останали източници; разреждането се отчита директно от API-то. Верификация: производство + внос − износ ≈ потребление.',
     'Generation-by-source data is real-time from ESO EAD. Imports and exports are shown directly from ESO without further processing. BESS (battery) values come from the ESO API but are not included in the chart\'s percentage breakdown — this explains the &ldquo;missing&rdquo; percentages up to 100%. Charging is computed as the difference between total consumption and the sum of all other sources; discharging is reported directly by the API. Verification: generation + imports − exports ≈ consumption.'),

    # ── flows table ──
    ('Трансгранични потоци — дневен профил (+ внос / &minus; износ)',
     'Cross-border flows — daily profile (+ imports / &minus; exports)'),
    ('>Трансгранични потоци</a>', '>Cross-border flows</a>'),
    ('<th>Страна</th>', '<th>Country</th>'),
    ('<th>Баланс</th>', '<th>Balance</th>'),
    ('>Поток</th>', '>Flow</th>'),
    ('>Конг. €/h</th>', '>Cong. €/h</th>'),

    # ── congestion card ──
    ('Congestion рента — живо', 'Congestion rent — live'),
    ('Congestion рента е приходът, който операторът на преносната система (ЕСО) получава при пренос на електроенергия между два пазара с различна цена. При износ от БГ към РО или ГР (по-висока цена), ЕСО инкасира разликата в цените, умножена по преносната мощност. Формула: рента = −поток_МВт × (цена_съсед − цена_БГ) × часове. Отрицателен поток означава износ от БГ. Положителна рента = приход за ЕСО.',
     'Congestion rent is the revenue the transmission system operator (ESO) collects when transmitting electricity between two markets with different prices. When exporting from BG to RO or GR (higher price), ESO pockets the price difference multiplied by the transferred power. Formula: rent = −flow_MW × (price_neighbour − price_BG) × hours. Negative flow means export from BG. Positive rent = revenue for ESO.'),
    ('>IBEX (БГ)</div>', '>IBEX (BG)</div>'),
    ('>DA Румъния</div>', '>DA Romania</div>'),
    ('>DA Гърция</div>', '>DA Greece</div>'),
    ('>Граница</th>', '>Border</th>'),
    ('>Поток МВт</th>', '>Flow MW</th>'),
    ('>Спред €/МВтч</th>', '>Spread €/MWh</th>'),
    ('>Рента €/ч</th>', '>Rent €/h</th>'),
    ('>🇷🇴 Румъния</td>', '>🇷🇴 Romania</td>'),
    ('>🇬🇷 Гърция</td>', '>🇬🇷 Greece</td>'),
    ('>Общо congestion</td>', '>Total congestion</td>'),
    ('>Congestion — дневен приход</div>', '>Congestion — daily revenue</div>'),
    ('<div class="balance-label">Румъния</div>', '<div class="balance-label">Romania</div>'),
    ('<div class="balance-label">Гърция</div>', '<div class="balance-label">Greece</div>'),
    ('>Общо congestion (РО + ГР)</div>', '>Total congestion (RO + GR)</div>'),

    # ── balance panel ──
    ('>Дневен баланс</a>', '>Daily balance</a>'),
    ('Стойностите са изчислени по IBEX дневна цена (борсова цена Day-Ahead). Те са само илюстративни — не отразяват реални договорни цени, такси за достъп до мрежата или крайни финансови стойности. Печалбата от арбитраж на ССЕЕ (Δ) е изчислена като разлика между приход от разреждане и разход за зареждане по борсова цена — реалният финансов резултат зависи от договорните условия на оператора.',
     'Values are computed at the IBEX day-ahead price. They are illustrative only — they do not reflect actual contract prices, grid-access fees or final financial figures. The BESS arbitrage profit (Δ) is discharge revenue minus charging cost at the spot price — the real financial result depends on the operator\'s contractual terms.'),
    ('<div class="balance-label">Внос</div>', '<div class="balance-label">Imports</div>'),
    ('<div class="balance-label">Износ</div>', '<div class="balance-label">Exports</div>'),
    ('>Нетен баланс (+ износ / &minus; внос)</div>', '>Net balance (+ exports / &minus; imports)</div>'),
    ('>IBEX DA (текуща)</div>', '>IBEX DA (current)</div>'),
    ('>Средна за деня</div>', '>Daily average</div>'),
    ('>Мин / Макс</div>', '>Min / Max</div>'),
    ('>ССЕЕ — дневен баланс</div>', '>BESS — daily balance</div>'),
    ('<div class="balance-label">Зареждане</div>', '<div class="balance-label">Charging</div>'),
    ('<div class="balance-label">Разреждане</div>', '<div class="balance-label">Discharging</div>'),
    ('<div class="balance-label">Зареждане помпи</div>', '<div class="balance-label">Pump charging</div>'),
    ('<div class="balance-label">Разр./Зар.</div>', '<div class="balance-label">Dis./Chg.</div>'),
    ('<div class="balance-label">Δ Арбитраж</div>', '<div class="balance-label">Δ Arbitrage</div>'),

    # ── gen table ──
    ('Производство по източници — живо', 'Generation by source — live'),
    ('<th>Източник</th>', '<th>Source</th>'),
    ('>МВт</th>', '>MW</th>'),
    ('<th style="width:100px;">Дял</th>', '<th style="width:100px;">Share</th>'),

    # ── day profile panel ──
    ('>Дневен профил</a>', '>Daily profile</a>'),
    ('>ВЕИ</button>', '>RES</button>'),
    ('>€/ч</button>', '>€/h</button>'),
    ('>Колони</button>', '>Columns</button>'),
    ('title="Цял екран"', 'title="Fullscreen"'),
    ('Данните са изчислени на база живи данни от ЕСО ЕАД, получавани на интервали от 5 минути. Поради вариации при заснемането на интервала е възможна грешка, типично в рамките на 1–2%.',
     'Values are computed from live ESO EAD data received at 5-minute intervals. Due to sampling-interval variations a small error is possible, typically within 1–2%.'),
    ('title="Предишен час"', 'title="Previous hour"'),
    ('title="Следващ час"', 'title="Next hour"'),

    # ── tariff panel (static) ──
    ('Борсова цена — Свободен пазар vs Регулирана тарифа', 'Spot price — Free market vs Regulated tariff'),
    ('Сравнение на регулираната тарифа (КЕВР) с текущата борсова цена (IBEX). Мрежовите такси (пренос, разпределение, ОЗЕ, акциз) са еднакви и на двата пазара. Стойностите са ориентировъчни — реалните договорни условия на свободния пазар може да се различават.',
     'Comparison of the regulated tariff (EWRC) with the current spot price (IBEX). Network charges (transmission, distribution, RES, excise) are identical on both markets. Values are indicative — actual free-market contract terms may differ.'),

    # ── JS: GEN_SERIES / FLOW_CFG display labels (keys stay Bulgarian) ──
    ("label: 'АЕЦ'", "label: 'Nuclear'"),
    ("label: 'Конд. ТЕЦ'", "label: 'Coal TPP'"),
    ("label: 'Топло. ТЕЦ'", "label: 'CHP (heating)'"),
    ("label: 'Зав. ТЕЦ'", "label: 'CHP (industrial)'"),
    ("label: 'Малки ВЕЦ'", "label: 'Small hydro'"),
    ("label: 'М.ВЕЦ'", "label: 'S. hydro'"),
    ("label: 'ВяЕЦ'", "label: 'Wind'"),
    ("label: 'ВЕЦ'", "label: 'Hydro'"),
    ("label: 'ФЕЦ'", "label: 'Solar'"),
    ("label: 'Биомаса'", "label: 'Biomass'"),
    ("label: 'ССЕЕ',", "label: 'BESS',"),
    ("label: 'Румъния'", "label: 'Romania'"),
    ("label: 'Сърбия'", "label: 'Serbia'"),
    ("label: 'С.Македония'", "label: 'N. Macedonia'"),
    ("label: 'Гърция'", "label: 'Greece'"),
    ("label: 'Турция'", "label: 'Turkey'"),

    # ── JS: battery / stats labels ──
    (' MWh зар.', ' MWh chg.'),
    (' MWh разр.', ' MWh dis.'),
    ('`разр. ${avgDis.toFixed(0)} vs зар. ${avgChg.toFixed(0)} €/MWh`',
     '`dis. ${avgDis.toFixed(0)} vs chg. ${avgChg.toFixed(0)} €/MWh`'),
    ("'ССЕЕ разреждане'", "'BESS discharge'"),
    ("'ССЕЕ зареждане'", "'BESS charging'"),
    ("'ССЕЕ разр.'", "'BESS dis.'"),
    ("'ССЕЕ зар.'", "'BESS chg.'"),
    ("'Помпи (товар)'", "'Pumps (load)'"),
    ("'Помпи зар.'", "'Pumps chg.'"),
    ("'Помпи'", "'Pumps'"),
    ('>ВЕИ покритие</div>', '>RES coverage</div>'),
    ("'ВЕИ енергия'", "'RES energy'"),
    ("'Непокрито'", "'Uncovered'"),
    ("'Излишък'", "'Surplus'"),
    ("'100% покр.'", "'100% cov.'"),
    ("'ч:мин'", "'h:min'"),
    ("isImp?'Внос':'Износ'", "isImp?'Imports':'Exports'"),
    ("'MW — зар.'", "'MW — chg.'"),
    ("'MW — разр.'", "'MW — dis.'"),
    ('title="Оценка на база IBEX DA цена"', 'title="Estimate at IBEX DA price"'),
    ('>Нетна позиция</td>', '>Net position</td>'),
    ("'Нетна позиция'", "'Net position'"),
    ("'▼ износ'", "'▼ export'"),
    ("'▲ внос'", "'▲ import'"),
    ('} МВт ${dir}`', '} MW ${dir}`'),
    ("label: 'Внос'", "label: 'Imports'"),
    ("label: 'Износ'", "label: 'Exports'"),
    ("'Внос']", "'Imports']"),
    (" MWh внос'", " MWh imported'"),
    (" MWh износ'", " MWh exported'"),
    (" MWh нет'", " MWh net'"),
    ('>Трансгранична енергия за деня</div>', '>Cross-border energy for the day</div>'),
    ("isImp ? 'внос' : 'износ'", "isImp ? 'import' : 'export'"),
    ('>Няма борсови данни за избрания ден.</div>', '>No market data for the selected day.</div>'),

    # ── JS: tariff calculator ──
    ('label: `Снабдяване<br>', 'label: `Supply<br>'),
    ('>борса: ${', '>spot: ${'),
    ("'Пренос НЕК'", "'Transmission (NEK)'"),
    ("'Разпределение'", "'Distribution'"),
    ("'ОЗЕ надбавка'", "'RES surcharge'"),
    ("'Акциз'", "'Excise duty'"),
    ('`последните ${loadProfile.days} дни (${loadProfile.computed})`',
     '`last ${loadProfile.days} days (${loadProfile.computed})`'),
    ("'типичен профил'", "'typical profile'"),
    ("? 'ден' : 'нощ'", "? 'day' : 'night'"),
    ('<td>Без ДДС &nbsp;', '<td>Excl. VAT &nbsp;'),
    ('<td>ОБЩО с ДДС &nbsp;', '<td>TOTAL incl. VAT &nbsp;'),
    ("return 'никои';", "return 'none';"),
    ('>Цена за краен потребител (свободен пазар)</div>', '>End-consumer price (free market)</div>'),
    ('борса&nbsp;', 'spot&nbsp;'),
    ('мрежа&nbsp;', 'grid&nbsp;'),
    ('ДДС&nbsp;', 'VAT&nbsp;'),
    ('борсова цена (IBEX)&nbsp;', 'spot price (IBEX)&nbsp;'),
    ("'по-евтин от регулирана':'по-скъп от регулирана'",
     "'cheaper than regulated':'more expensive than regulated'"),
    ('vs рег. <span', 'vs reg. <span'),
    ('Референтни стойности по решение <strong style="color:#5a7090;">Ц-25 КЕВР, юли 2025</strong> (Енерго-Про / Електросевер).',
     'Reference values per decision <strong style="color:#5a7090;">C-25 of EWRC, July 2025</strong> (Energo-Pro / Electrosever).'),
    ('Мрежовите компоненти (пренос, разпределение, ОЗЕ, акциз) са еднакви и на двата пазара.',
     'Network components (transmission, distribution, RES, excise) are identical on both markets.'),
    ('Дневна тарифа: 07:00–23:00 ч. &nbsp;|&nbsp; Нощна: 23:00–07:00 ч.',
     'Day tariff: 07:00–23:00 &nbsp;|&nbsp; Night: 23:00–07:00'),
    ('<th>Компонент</th>', '<th>Component</th>'),
    ('>Регулирана<br>', '>Regulated<br>'),
    ('>Свободен пазар<br>', '>Free market<br>'),
    ('Консуматор с ${dailyKwh} кВтч/ден', 'Consumer using ${dailyKwh} kWh/day'),
    ('<div class="balance-label">Регулирана</div>', '<div class="balance-label">Regulated</div>'),
    ('<div class="balance-label">Свободен пазар</div>', '<div class="balance-label">Free market</div>'),
    ('<div class="balance-label">Разлика</div>', '<div class="balance-label">Difference</div>'),
    ('По-евтини часове на свободния пазар', 'Hours when the free market is cheaper'),
    ('>Дневна тарифа (07–23ч)</div>', '>Day tariff (07–23h)</div>'),
    ('>Нощна тарифа (23–07ч)</div>', '>Night tariff (23–07h)</div>'),
    ('</strong> от 16 часа', '</strong> of 16 hours'),
    ('</strong> от 8 часа', '</strong> of 8 hours'),
    ("'всички часове — пазарът е по-скъп'", "'no hours — the market is more expensive'"),
    ('✓ <strong>${allCheap.length} часа</strong> (${hoursToRanges(allCheap.map(a=>a.h))}) свободният пазар е по-евтин от регулираната тарифа.',
     '✓ In <strong>${allCheap.length} hours</strong> (${hoursToRanges(allCheap.map(a=>a.h))}) the free market is cheaper than the regulated tariff.'),
    ('✗ Днес борсовите цени надвишават регулираната тарифа <strong>във всички часове</strong> — регулираната тарифа е по-изгодна.',
     '✗ Today spot prices exceed the regulated tariff <strong>in all hours</strong> — the regulated tariff is the better deal.'),
    ('<span>Свободен пазар: <strong>', '<span>Free market: <strong>'),
    ('<span>Регулиран: <strong>', '<span>Regulated: <strong>'),
    ('✓ Свободният пазар е по-изгоден — спестявате <strong>', '✓ The free market is the better deal — you save <strong>'),
    ('✗ Няма евтини часове — регулираната тарифа е по-изгодна.', '✗ No cheap hours — the regulated tariff is the better deal.'),
    ('Трябва да спестите <strong>${diff} EUR/ден</strong> — преместете ~<strong>${breakEven.shiftPct.toFixed(0)}%</strong> (${breakEven.shiftKwh.toFixed(1)} кВтч) от потреблението към евтините часове (${breakEven.cheapHours}).',
     'You need to save <strong>${diff} EUR/day</strong> — shift ~<strong>${breakEven.shiftPct.toFixed(0)}%</strong> (${breakEven.shiftKwh.toFixed(1)} kWh) of consumption to the cheap hours (${breakEven.cheapHours}).'),
    ('>профил: ${loadProfileLabel}</div>', '>profile: ${loadProfileLabel}</div>'),

    # ── JS: pie chart ──
    ('`${fmt0(loadMw)} т`', '`${fmt0(loadMw)} load`'),
    ('`${fmt0(exportMw)} износ`', '`${fmt0(exportMw)} export`'),
    ('`${fmt0(chgMw)} зар.`', '`${fmt0(chgMw)} chg.`'),
    ('`${fmt0(pumpsNowPie)} помпи`', '`${fmt0(pumpsNowPie)} pumps`'),

    # ── JS: timeline / flows charts ──
    ("name: 'Товар'", "name: 'Load'"),
    ("htFmt('Товар')", "htFmt('Load')"),
    ("name: 'IBEX цена'", "name: 'IBEX price'"),
    ("title: 'Час'", "title: 'Hour'"),
    ('`${unit} (+ внос / − износ)`', '`${unit} (+ imports / − exports)`'),

    # ── JS: timestamps / errors ──
    ("'Няма данни'", "'No data'"),
    ("'Обновено току-що'", "'Updated just now'"),
    ('`Обновено преди ${mins} мин.`', '`Updated ${mins} min ago`'),
    ("'Грешка: '", "'Error: '"),
    (" + ' ч. (местно)'", " + ' (local time)'"),

    # ── JS: records ──
    ("['%', 'ч', 'GWh']", "['%', 'h', 'GWh']"),
    ("['%','ч']", "['%','h']"),
    ("? 'днес' : 'на този ден'", "? 'today' : 'on this day'"),
    ('`<span id="rec-alerts-label">🏆 Рекорди ${dayLabel}:</span>`',
     '`<span id="rec-alerts-label">🏆 Records ${dayLabel}:</span>`'),

    # ── footer ──
    ('Неофициален ресурс &bull; данни от <a href="https://www.eso.bg"',
     'Unofficial resource &bull; data from <a href="https://www.eso.bg"'),
    (';">ЕСО ЕАД</a> и <a', ';">ESO EAD</a> and <a'),
    ('>Документация (README)</a>', '>Documentation (README)</a>'),
    ('>Промени (Changelog)</a>', '>Changelog</a>'),

    # ── catch-all unit/locale tokens (keep last) ──
    ('€/МВтч', '€/MWh'),
    ('EUR/МВтч', 'EUR/MWh'),
    ('МВтч', 'MWh'),
    ('МВт', 'MW'),
    ('EUR/кВтч', 'EUR/kWh'),
    ('кВтч', 'kWh'),
    ('EUR/ден', 'EUR/day'),
    ('/ч</span>', '/h</span>'),
    ("'млн.€'", "'M€'"),
    ("' млн.€'", "' M€'"),
    ("'хил.€'", "'k€'"),
    ("' хил.€'", "' k€'"),
    ("'хил.€/h'", "'k€/h'"),
    ('хил.€/h', 'k€/h'),
    ("'bg-BG'", "'en-GB'"),
]

missing = []
for bg, en in PAIRS:
    if bg not in text:
        missing.append(bg)
    else:
        text = text.replace(bg, en)
if missing:
    for m in missing:
        print(f'MISSING: {m[:100]!r}', file=sys.stderr)
    sys.exit(f'{len(missing)} expected strings not found in index.html — update build_en.py')

# ── records.json arrives with Bulgarian labels — inject an English remap ──
REC_REMAP = """    const rec = await getJSON(`${BASE}/records.json`);
    const REC_EN = {
      solar: 'Peak solar generation', solar_gwh: 'Solar energy in a day',
      total_chg: 'BESS + pumps charging', batt_chg: 'Battery charging',
      chg_gwh_day: 'Charging in a day', batt_dis: 'BESS discharging',
      dis_gwh_day: 'Discharging in a day', pumps_gwh: 'Pumps record day',
      export: 'Peak export power', daily_re: 'Daily RES share',
      re_gwh_day: 'RES energy in a day', re_hours: 'Longest 100% RES',
    };
    for (const k of Object.keys(rec)) {
      if (rec[k] && typeof rec[k] === 'object') {
        if (REC_EN[k]) rec[k].label = REC_EN[k];
        if (rec[k].unit === 'ч') rec[k].unit = 'h';
      }
    }"""
old = "    const rec = await getJSON(`${BASE}/records.json`);"
assert old in text, 'records.json fetch line not found'
text = text.replace(old, REC_REMAP)

# ── language switch: EN page links back to the Bulgarian page ──
CONG_LINK = '<a href="congestion.html" style="margin-left:10px;color:rgba(255,255,255,0.7);font-size:0.72rem;text-decoration:none;white-space:nowrap;">Congestion →</a>'
assert CONG_LINK in text, 'congestion header link not found'
text = text.replace(
    CONG_LINK,
    CONG_LINK + '\n        <a href="index.html" style="margin-left:10px;color:#ffd700;font-size:0.72rem;text-decoration:none;font-weight:700;white-space:nowrap;">БГ</a>')

# ── sanity: remaining Cyrillic must only be data keys / comments ──
ALLOWED = re.compile(
    r"key: '|\['(?:АЕЦ|Кондензационни ТЕЦ|Топлофикационни ТЕЦ|Заводски ТЕЦ|ВЕЦ|Малки ВЕЦ|ВяЕЦ|ФЕЦ|Био ЕЦ|Товар на РБ|ССЕЕ_mw)'\]"
    r"|RE_KEYS|avgOf\(recs, 'Товар на РБ'\)|'ССЕЕ_mw'|//|href=\"index.html\"|>БГ</a>|=== 'ч'")
leftover = [
    (i + 1, ln.strip()[:110])
    for i, ln in enumerate(text.splitlines())
    if re.search('[А-Яа-я]', ln) and not ALLOWED.search(ln)
]
if leftover:
    for n, ln in leftover:
        print(f'CYRILLIC LEFT at {n}: {ln}', file=sys.stderr)
    sys.exit('untranslated strings remain — extend PAIRS')

DST.write_text(text, encoding='utf-8')
print(f'wrote {DST} ({len(text)} bytes)')
