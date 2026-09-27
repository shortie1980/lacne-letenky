#!/usr/bin/env python3
"""Sleduje lacné letenky cez Travelpayouts (Aviasales), posiela upozornenia
(Teams + e-mail cez Power Automate, push cez ntfy) a pripravuje dáta pre webovú aplikáciu.

Použitie:
    python watcher.py               # normálny beh
    python watcher.py --dry-run     # nič neposiela, neukladá stav upozornení; dáta pre web áno
    python watcher.py --test-notify # pošle skúšobné upozornenie všetkými kanálmi
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
from html import escape
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).parent
CONFIG_FILE = ROOT / "config.json"
WEB_SOURCE = ROOT / "docs" / "index.html"
SITE_DIR = Path(os.environ.get("SITE_DIR", ROOT / "site"))
DATA_DIR = SITE_DIR / "data"
STATE_FILE = DATA_DIR / "state.json"
HISTORY_FILE = DATA_DIR / "history.json"

TP_PRICES_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
TP_CITIES_URL = "https://api.travelpayouts.com/data/en/cities.json"
TP_AIRPORTS_URL = "https://api.travelpayouts.com/data/en/airports.json"
TP_COUNTRIES_URL = "https://api.travelpayouts.com/data/en/countries.json"
SERPAPI_URL = "https://serpapi.com/search.json"
NTFY_URL = "https://ntfy.sh"

HISTORY_DAYS = 120
OTHER_REGION = {"label": "Ostatné", "max_price": 0, "min_days": 3, "max_days": 30, "enabled": False}

REGION_COUNTRIES = {
    "europe": """AL AD AT BY BE BA BG HR CY CZ DK EE FI FR DE GR HU IS IE IT XK LV LI LT
        LU MT MD MC ME NL MK NO PL PT RO SM RS SK SI ES SE CH UA GB TR GI FO IM JE GG""",
    "middle_east": "AE QA OM BH KW SA JO IL LB IQ EG GE AM AZ",
    "central_asia": "AF KZ KG TJ TM UZ",
    "asia": """BD BT BN KH CN HK MO IN ID JP LA MY MV MN MM NP KR PK PH SG LK TW
        TH TL VN""",
    "north_america": "US CA MX",
    "latam": """AR BO BR CL CO EC GY PY PE SR UY VE GF BZ CR SV GT HN NI PA CU DO HT JM PR
        BS BB TT AG DM GD KN LC VC AW CW SX BQ KY TC VG VI GP MQ BL MF AI MS BM""",
}
COUNTRY_TO_REGION = {
    code: region for region, codes in REGION_COUNTRIES.items() for code in codes.split()
}


# ─── Súbory ──────────────────────────────────────────────────────────────────

def load_config():
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def read_json(path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


# ─── Travelpayouts ───────────────────────────────────────────────────────────

def load_places():
    """Vráti (places, countries): IATA kód -> (názov, krajina) a kód krajiny -> názov."""
    cities = requests.get(TP_CITIES_URL, timeout=60).json()
    airports = requests.get(TP_AIRPORTS_URL, timeout=60).json()
    countries = requests.get(TP_COUNTRIES_URL, timeout=60).json()
    places = {}
    for a in airports:
        if a.get("code") and a.get("country_code"):
            places[a["code"]] = (a.get("name") or a["code"], a["country_code"])
    for c in cities:
        if c.get("code") and c.get("country_code"):
            places[c["code"]] = (c.get("name") or c["code"], c["country_code"])
    country_names = {c["code"]: c.get("name") or c["code"] for c in countries if c.get("code")}
    return places, country_names


def upcoming_months(count, today):
    months = []
    year, month = today.year, today.month
    for _ in range(count):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return months


def fetch_prices(origin, month, token):
    params = {
        "origin": origin,
        "departure_at": month,
        "one_way": "false",
        "direct": "false",
        "sorting": "price",
        "unique": "false",
        "currency": "eur",
        "limit": 1000,
        "page": 1,
        "token": token,
    }
    r = requests.get(TP_PRICES_URL, params=params, timeout=60)
    r.raise_for_status()
    data = r.json()
    if not data.get("success"):
        raise RuntimeError(f"Travelpayouts chyba pre {origin} {month}: {data.get('error')}")
    return data.get("data", [])


# ─── Pravidlá ────────────────────────────────────────────────────────────────

def region_rule(region, cfg):
    return cfg["regions"].get(region) or OTHER_REGION


def limit_for(dest, country, region, cfg):
    """Cenový limit pre destináciu, alebo None, ak ju nesledujeme."""
    excluded = set(cfg.get("excluded", []))
    if dest in excluded or country in excluded:
        return None
    watch = {w["code"]: w["max_price"] for w in cfg.get("watchlist", [])}
    if dest in watch:
        return watch[dest]
    if country in watch:
        return watch[country]
    rule = region_rule(region, cfg)
    if not rule.get("enabled", True):
        return None
    return rule["max_price"]


def to_offer(it, places, cfg, today):
    """Prevedie záznam z API na ponuku. Vráti None, ak nespĺňa dĺžku pobytu alebo prestupy."""
    dest = it.get("destination")
    if dest not in places or not it.get("return_at") or it.get("price") is None:
        return None
    city, country = places[dest]
    region = COUNTRY_TO_REGION.get(country, "other")
    dep = dt.date.fromisoformat(it["departure_at"][:10])
    ret = dt.date.fromisoformat(it["return_at"][:10])
    days = (ret - dep).days
    transfers = max(it.get("transfers", 0), it.get("return_transfers", 0))
    rule = region_rule(region, cfg)
    if dep <= today or transfers > cfg["max_transfers"]:
        return None
    if not rule["min_days"] <= days <= rule["max_days"]:
        return None
    age = price_age(it.get("link"), today)
    if age is not None and age > cfg.get("max_price_age_days", 4):
        return None
    return {
        "origin": it.get("origin"),
        "origin_airport": it.get("origin_airport") or it.get("origin"),
        "destination": dest,
        "destination_airport": it.get("destination_airport") or dest,
        "city": city,
        "country": country,
        "region": region,
        "price": it["price"],
        "limit": limit_for(dest, country, region, cfg),
        "departure": dep.isoformat(),
        "return": ret.isoformat(),
        "days": days,
        "transfers": transfers,
        "airline": it.get("airline", ""),
        "link": "https://www.aviasales.com" + it["link"] if it.get("link") else None,
        "age": age,
    }


def price_age(link, today):
    """Pred koľkými dňami niekto túto cenu našiel (z parametra search_date v odkaze)."""
    m = re.search(r"search_date=(\d{2})(\d{2})(\d{4})", link or "")
    if not m:
        return None
    try:
        return (today - dt.date(int(m[3]), int(m[2]), int(m[1]))).days
    except ValueError:
        return None


def is_deal(o):
    return bool(o["limit"]) and o["price"] <= o["limit"]


def cheapest_by(offers, key):
    best = {}
    for o in offers:
        k = key(o)
        if k not in best or o["price"] < best[k]["price"]:
            best[k] = o
    return best


def filter_new(deals, state, cfg, now):
    """Ponuky, o ktorých ešte neprišlo upozornenie (alebo odvtedy výrazne zlacneli)."""
    fresh = []
    for d in deals:
        prev = state["notified"].get(f"{d['origin']}-{d['destination']}")
        if prev:
            age_days = (now - dt.datetime.fromisoformat(prev["at"])).days
            dropped = d["price"] <= prev["price"] * (1 - cfg["renotify_drop_pct"] / 100)
            if age_days < cfg["renotify_days"] and not dropped:
                continue
        fresh.append(d)
    fresh.sort(key=lambda d: d["price"] / d["limit"])
    per_region = {}
    balanced = []
    for d in fresh:
        per_region[d["region"]] = per_region.get(d["region"], 0) + 1
        if per_region[d["region"]] <= cfg["max_alerts_per_region"]:
            balanced.append(d)
    return balanced


# ─── Overenie cez Google Flights (voliteľné) ─────────────────────────────────

def verify_price(d, api_key):
    params = {
        "engine": "google_flights",
        "departure_id": d["origin_airport"],
        "arrival_id": d["destination_airport"],
        "outbound_date": d["departure"],
        "return_date": d["return"],
        "currency": "EUR",
        "hl": "en",
        "api_key": api_key,
    }
    try:
        r = requests.get(SERPAPI_URL, params=params, timeout=90)
        r.raise_for_status()
        j = r.json()
    except (requests.RequestException, ValueError) as e:
        print(f"  Overenie zlyhalo ({d['origin']}→{d['destination']}): {e}", file=sys.stderr)
        return None
    prices = [f["price"] for f in j.get("best_flights", []) + j.get("other_flights", [])
              if isinstance(f.get("price"), (int, float))]
    return min(prices) if prices else None


def verify_key(d):
    return f"{d['origin']}-{d['destination']}-{d['departure']}-{d['return']}"


def apply_verified(offers, state, now):
    """Použije overenia z posledných 12 hodín: overenú cenu doplní, neplatné ponuky označí."""
    cache = state.setdefault("verified", {})
    for k in [k for k, v in cache.items() if now - dt.datetime.fromisoformat(v["at"]) > dt.timedelta(hours=12)]:
        del cache[k]
    for o in offers:
        v = cache.get(verify_key(o))
        if v:
            o["verified_price"] = v["price"]


def verification_ok(d, cfg):
    tolerance = 1 + cfg["verify"]["tolerance_pct"] / 100
    return d.get("verified_price") is None or (d["limit"] and d["verified_price"] <= d["limit"] * tolerance)


def verify_deals(fresh, state, cfg, api_key, now):
    """Overí nové ponuky naživo v Google Flights, v rámci limitu na beh aj na mesiac."""
    usage = state.setdefault("verify_usage", {})
    month = now.strftime("%Y-%m")
    if usage.get("month") != month:
        usage.update(month=month, count=0)
    checks_left = cfg["verify"]["max_checks_per_run"]
    cache = state.setdefault("verified", {})
    kept = []
    for d in fresh:
        if "verified_price" not in d and checks_left > 0 and usage["count"] < cfg["verify"]["monthly_budget"]:
            checks_left -= 1
            usage["count"] += 1
            real = verify_price(d, api_key)
            if real is not None:
                d["verified_price"] = real
                cache[verify_key(d)] = {"price": real, "at": now.isoformat()}
        if verification_ok(d, cfg):
            kept.append(d)
        else:
            print(f"  Zahodené: {d['origin']}→{d['city']} {d['price']} € (Google Flights teraz {d['verified_price']} €)")
    return kept


# ─── Formátovanie ────────────────────────────────────────────────────────────

def flag(country):
    if len(country) != 2 or not country.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in country.upper())


def fmt_date(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.day}. {d.month}. {d.year}"


def plural(n, one, few, many):
    if n == 1:
        return one
    return few if 2 <= n <= 4 else many


def transfers_text(n):
    if n == 0:
        return "priamy let"
    return f"{n} {plural(n, 'prestup', 'prestupy', 'prestupov')}"


def google_flights_link(d):
    q = f"Flights from {d['origin']} to {d['destination']} on {d['departure']} through {d['return']}"
    return "https://www.google.com/travel/flights?q=" + quote(q)


def buy_link(d):
    """Overená ponuka → Google Flights (tam cena platí), inak konkrétny let na Aviasales."""
    if d.get("verified_price") is not None:
        return google_flights_link(d)
    return d["link"] or google_flights_link(d)


def freshness_text(d):
    if d.get("verified_price") is not None:
        return "✓ cena overená naživo v Google Flights"
    age = d.get("age")
    if age is None:
        return "cena z cache, neoverená"
    return "cena z cache nájdená dnes" if age == 0 else f"cena z cache spred {age} {plural(age, 'dňa', 'dní', 'dní')}"


def second_link(d):
    """Druhý odkaz popri Kúpiť: pri overenej ponuke Aviasales, inak Google Flights."""
    if d.get("verified_price") is not None and d.get("link"):
        return "pozrieť aj na Aviasales", d["link"]
    return "porovnať na Google Flights", google_flights_link(d)


def other_links_md(d):
    label, url = second_link(d)
    return f"**[🛒 Kúpiť túto letenku]({buy_link(d)})** · [{label}]({url})"


def shown_price(d):
    return d["verified_price"] if d.get("verified_price") is not None else d["price"]


def region_label(region, cfg):
    return region_rule(region, cfg)["label"]


def details_text(d, cfg):
    return (f"{fmt_date(d['departure'])} – {fmt_date(d['return'])} · {d['days']} dní · "
            f"{transfers_text(d['transfers'])} · {d['airline']} · {region_label(d['region'], cfg)}")


# ─── Notifikácie ─────────────────────────────────────────────────────────────

def build_card(deals, cfg, dashboard_url):
    body = [{
        "type": "TextBlock",
        "text": f"✈️ Lacné letenky: {len(deals)} {plural(len(deals), 'nová ponuka', 'nové ponuky', 'nových ponúk')}",
        "weight": "Bolder",
        "size": "Large",
        "wrap": True,
    }]
    for d in deals:
        price = f"{shown_price(d)} €"
        body.append({
            "type": "Container",
            "separator": True,
            "spacing": "Medium",
            "selectAction": {"type": "Action.OpenUrl", "url": buy_link(d)},
            "items": [
                {
                    "type": "TextBlock",
                    "text": f"{flag(d['country'])} **{d['origin']} → {d['city']}** · **{price}**",
                    "wrap": True,
                },
                {"type": "TextBlock", "text": details_text(d, cfg), "isSubtle": True,
                 "spacing": "None", "wrap": True},
                {"type": "TextBlock", "text": freshness_text(d), "size": "Small", "spacing": "None", "wrap": True,
                 "color": "Good" if d.get("verified_price") is not None else "Default"},
                {
                    "type": "TextBlock",
                    "text": other_links_md(d),
                    "spacing": "Small",
                    "wrap": True,
                },
            ],
        })
    footer = "Ceny pochádzajú z cache vyhľadávaní a môžu sa rýchlo zmeniť."
    if dashboard_url:
        footer += f" [Otvoriť aplikáciu]({dashboard_url})"
    body.append({"type": "TextBlock", "text": footer, "isSubtle": True, "size": "Small", "wrap": True})
    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "msteams": {"width": "Full"},
                "body": body,
            },
        }],
    }


def build_email(deals, cfg, dashboard_url):
    cheapest = min(deals, key=shown_price)
    subject = f"✈️ {cheapest['origin']} → {cheapest['city']} za {shown_price(cheapest)} €"
    rest = len(deals) - 1
    if rest == 1:
        subject += " a ďalšia lacná letenka"
    elif rest > 1:
        subject += f" a {rest} {plural(rest, '', 'ďalšie lacné letenky', 'ďalších lacných leteniek')}"

    rows = []
    for d in deals:
        color = "#0f8a4f" if d.get("verified_price") is not None else "#888"
        price = (f"{shown_price(d)} €<br><span style='font-size:12px;font-weight:400;color:{color}'>"
                 f"{escape(freshness_text(d))}</span>")
        rows.append(f"""
<tr>
  <td style="padding:14px 12px;border-bottom:1px solid #e5e7eb">
    <div style="font-size:16px;font-weight:600">{flag(d['country'])} {escape(d['origin'])} → {escape(d['city'])}</div>
    <div style="font-size:13px;color:#555;margin-top:3px">
      {fmt_date(d['departure'])} – {fmt_date(d['return'])} · {d['days']} dní · {transfers_text(d['transfers'])} · {escape(d['airline'])}
    </div>
    <div style="font-size:12px;color:#888;margin-top:2px">
      {escape(region_label(d['region'], cfg))} · tvoj limit {d['limit']} € ·
      <a href="{escape(second_link(d)[1])}" style="color:#888">{escape(second_link(d)[0])}</a>
    </div>
  </td>
  <td style="padding:14px 12px;border-bottom:1px solid #e5e7eb;text-align:right;white-space:nowrap">
    <div style="font-size:20px;font-weight:700;margin-bottom:6px">{price}</div>
    <a href="{escape(buy_link(d))}" style="display:inline-block;background:#2563eb;color:#fff;
       text-decoration:none;padding:8px 16px;border-radius:6px;font-weight:600;font-size:14px">Kúpiť</a>
  </td>
</tr>""")

    app_link = (f' · <a href="{escape(dashboard_url)}" style="color:#2563eb">Otvoriť aplikáciu a nastavenia</a>'
                if dashboard_url else "")
    html = f"""<div style="font-family:Segoe UI,Arial,sans-serif;max-width:640px;color:#111">
<h2 style="margin:0 0 4px">✈️ Lacné letenky</h2>
<p style="margin:0 0 16px;color:#555">Našiel som {len(deals)} {plural(len(deals), 'ponuku', 'ponuky', 'ponúk')} pod tvojím limitom.</p>
<table cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse">{''.join(rows)}</table>
<p style="font-size:12px;color:#888;margin-top:16px">Tlačidlo Kúpiť otvorí presne tento let na Aviasales, kde si vyberieš
predajcu (aerolínia alebo agentúra) a zaplatíš. Ceny pochádzajú z cache vyhľadávaní a môžu sa rýchlo zmeniť.{app_link}</p>
</div>"""
    return subject, html


def send_flow(deals, cfg, webhook_url, email_to, dashboard_url):
    """Teams karta + polia pre e-mail; oboje odošle ten istý Power Automate flow."""
    payload = build_card(deals, cfg, dashboard_url)
    subject, html = build_email(deals, cfg, dashboard_url)
    payload["email_to"] = email_to or ""
    payload["email_subject"] = subject
    payload["email_html"] = html
    r = requests.post(webhook_url, json=payload, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"Teams webhook vrátil {r.status_code}: {r.text[:300]}")


def send_ntfy(deals, topic, cfg, dashboard_url):
    """Okamžitá push notifikácia na mobil (aplikácia ntfy). Jedna správa na ponuku."""
    top = deals[:5]
    for d in top:
        payload = {
            "topic": topic,
            "title": f"✈️ {d['origin']} → {d['city']} za {shown_price(d)} €",
            "message": f"{details_text(d, cfg)} · limit {d['limit']} € · {freshness_text(d)}",
            "click": buy_link(d),
            "tags": ["airplane"],
            "priority": 4,
            "actions": [
                {"action": "view", "label": "Kúpiť", "url": buy_link(d)},
                {"action": "view", "label": second_link(d)[0], "url": second_link(d)[1]},
            ],
        }
        requests.post(NTFY_URL, json=payload, timeout=20).raise_for_status()
    if len(deals) > len(top):
        rest = len(deals) - len(top)
        payload = {
            "topic": topic,
            "title": f"✈️ A {rest} {plural(rest, 'ďalšia ponuka', 'ďalšie ponuky', 'ďalších ponúk')}",
            "message": "Všetky ponuky nájdeš v aplikácii.",
            "tags": ["airplane"],
        }
        if dashboard_url:
            payload["click"] = dashboard_url
        requests.post(NTFY_URL, json=payload, timeout=20).raise_for_status()


def notify(deals, cfg, dashboard_url):
    """Pošle upozornenie všetkými nastavenými kanálmi. Vráti True, ak aspoň jeden uspel."""
    ok = False
    webhook = os.environ.get("TEAMS_WEBHOOK_URL")
    email_to = os.environ.get("EMAIL_TO") or cfg.get("notify", {}).get("email_to", "")
    topic = cfg.get("notify", {}).get("ntfy_topic", "").strip()
    if webhook:
        try:
            send_flow(deals, cfg, webhook, email_to, dashboard_url)
            ok = True
        except (requests.RequestException, RuntimeError) as e:
            print(f"Teams/e-mail zlyhal: {e}", file=sys.stderr)
    if topic:
        try:
            send_ntfy(deals, topic, cfg, dashboard_url)
            ok = True
        except requests.RequestException as e:
            print(f"ntfy zlyhal: {e}", file=sys.stderr)
    if not webhook and not topic:
        print("Nie je nastavený žiadny kanál (TEAMS_WEBHOOK_URL ani ntfy_topic).", file=sys.stderr)
    return ok


# ─── Dáta pre webovú aplikáciu ───────────────────────────────────────────────

def public_offer(o, cfg):
    keys = ("origin", "destination", "city", "country", "region", "price", "limit", "departure",
            "return", "days", "transfers", "airline")
    out = {k: o[k] for k in keys}
    out["buy"] = buy_link(o)
    out["google"] = google_flights_link(o)
    out["aviasales"] = o["link"]
    out["age"] = o.get("age")
    if "verified_price" in o:
        out["verified_price"] = o["verified_price"]
    return out


def update_history(history, cheapest_dest, cfg, today):
    """Denné minimum ceny pre destinácie, ktoré sú blízko limitu alebo sú sledované."""
    watched = {w["code"] for w in cfg.get("watchlist", [])}
    day = today.isoformat()
    for dest, o in cheapest_dest.items():
        ref = o["limit"] or region_rule(o["region"], cfg)["max_price"]
        if not (dest in watched or o["country"] in watched or (ref and o["price"] <= ref * 2)):
            continue
        entry = history.setdefault(dest, {"points": []})
        entry.update(name=o["city"], country=o["country"], region=o["region"])
        pts = entry["points"]
        if pts and pts[-1][0] == day:
            pts[-1][1] = min(pts[-1][1], o["price"])
        else:
            pts.append([day, o["price"]])
    cutoff = (today - dt.timedelta(days=HISTORY_DAYS)).isoformat()
    for dest in list(history):
        history[dest]["points"] = [p for p in history[dest]["points"] if p[0] >= cutoff]
        if not history[dest]["points"]:
            del history[dest]
    return history


def write_site(offers, deals, history, places, country_names, cfg, now, verify_info):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if WEB_SOURCE.exists():
        shutil.copyfile(WEB_SOURCE, SITE_DIR / "index.html")
    (SITE_DIR / ".nojekyll").touch()

    cheapest_dest = cheapest_by(offers, lambda o: o["destination"])
    by_region = {}
    for o in sorted(cheapest_dest.values(), key=lambda o: o["price"]):
        lst = by_region.setdefault(o["region"], [])
        if len(lst) < 10:
            lst.append(public_offer(o, cfg))

    regions = {k: v["label"] for k, v in cfg["regions"].items()}
    regions["other"] = OTHER_REGION["label"]
    write_json(DATA_DIR / "deals.json", {
        "updated_at": now.isoformat(),
        "origins": cfg["origins"],
        "regions": regions,
        "deals": [public_offer(d, cfg) for d in deals[:200]],
        "cheapest": by_region,
        "offers_checked": len(offers),
        "verify": verify_info,
        "max_price_age_days": cfg.get("max_price_age_days", 4),
    })
    write_json(HISTORY_FILE, history)

    seen = {o["destination"] for o in offers} | {w["code"] for w in cfg.get("watchlist", [])}
    cities = sorted(([c, places[c][0], places[c][1]] for c in seen if c in places), key=lambda x: x[1])
    countries = sorted(([c, n] for c, n in country_names.items()), key=lambda x: x[1])
    write_json(DATA_DIR / "places.json", {"cities": cities, "countries": countries})


# ─── Hlavný beh ──────────────────────────────────────────────────────────────

SAMPLE_DEAL = {
    "origin": "VIE", "origin_airport": "VIE", "destination": "BKK", "destination_airport": "BKK",
    "city": "Bangkok", "country": "TH", "region": "asia", "price": 399, "limit": 450,
    "departure": "2026-11-10", "return": "2026-11-24", "days": 14, "transfers": 1,
    "airline": "TK", "link": None,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="nič neposielať, neukladať stav upozornení")
    parser.add_argument("--test-notify", action="store_true", help="poslať skúšobné upozornenie")
    args = parser.parse_args()

    cfg = load_config()
    dashboard_url = os.environ.get("DASHBOARD_URL", "")

    if args.test_notify:
        ok = notify([SAMPLE_DEAL], cfg, dashboard_url)
        print("Skúšobné upozornenie odoslané." if ok else "Odoslanie zlyhalo.")
        sys.exit(0 if ok else 1)

    token = os.environ.get("TRAVELPAYOUTS_TOKEN")
    if not token:
        sys.exit("Chýba premenná TRAVELPAYOUTS_TOKEN.")

    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    today = now.date()
    places, country_names = load_places()

    offers, failures, calls = [], 0, 0
    for origin in cfg["origins"]:
        for month in upcoming_months(cfg["months_ahead"], today):
            calls += 1
            try:
                items = fetch_prices(origin, month, token)
            except (requests.RequestException, RuntimeError) as e:
                failures += 1
                print(f"Chyba pri {origin} {month}: {e}", file=sys.stderr)
                continue
            found = [o for o in (to_offer(it, places, cfg, today) for it in items) if o]
            print(f"{origin} {month}: {len(items)} cien, {sum(map(is_deal, found))} pod limitom")
            offers.extend(found)
    if calls and failures == calls:
        sys.exit("Všetky dopyty na Travelpayouts zlyhali.")

    state = read_json(STATE_FILE, {"notified": {}})
    apply_verified(offers, state, now)
    candidates = [o for o in offers if is_deal(o) and verification_ok(o, cfg)]
    deals = sorted(cheapest_by(candidates, lambda o: f"{o['origin']}-{o['destination']}").values(),
                   key=lambda d: d["price"] / d["limit"])

    fresh = filter_new(deals, state, cfg, now)[:cfg["max_alerts_per_run"] * 2]
    serpapi_key = os.environ.get("SERPAPI_KEY")
    if serpapi_key and fresh and not args.dry_run:
        fresh = verify_deals(fresh, state, cfg, serpapi_key, now)
        deals = [d for d in deals if verification_ok(d, cfg)]
    fresh = fresh[:cfg["max_alerts_per_run"]]

    print(f"\nPonúk pod limitom: {len(deals)}, nových na odoslanie: {len(fresh)}")
    for d in fresh:
        print(f"  {d['origin']} → {d['city']} ({d['country']}): {shown_price(d)} € · {freshness_text(d)} · "
              f"{d['departure']} – {d['return']} · {transfers_text(d['transfers'])}")

    history = update_history(read_json(HISTORY_FILE, {}), cheapest_by(offers, lambda o: o["destination"]), cfg, today)
    write_site(offers, deals, history, places, country_names, cfg, now, {
        "enabled": bool(serpapi_key),
        "used": state.get("verify_usage", {}).get("count", 0),
        "budget": cfg["verify"]["monthly_budget"],
    })

    if args.dry_run:
        if fresh:
            _, html = build_email(fresh, cfg, dashboard_url)
            (ROOT / "email-preview.html").write_text(html, encoding="utf-8")
        print(f"\nDáta pre web: {SITE_DIR}")
        return

    if fresh and notify(fresh, cfg, dashboard_url):
        for d in fresh:
            state["notified"][f"{d['origin']}-{d['destination']}"] = {"price": d["price"], "at": now.isoformat()}
    cutoff = now - dt.timedelta(days=60)
    state["notified"] = {k: v for k, v in state["notified"].items()
                         if dt.datetime.fromisoformat(v["at"]) >= cutoff}
    state["last_run"] = now.isoformat()
    write_json(STATE_FILE, state)


if __name__ == "__main__":
    main()
