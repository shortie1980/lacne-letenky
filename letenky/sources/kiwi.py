"""Kiwi.com – živé ceny cez verejný MCP server (nástroj search-flight). Bez kľúča; používať striedmo."""
import datetime as dt
import json
import sys

import requests

from ..geo import EXPLORE_COUNTRIES, image_slug, region_of
from ..rules import fits_rules, limit_for, region_rule, rule_for_destination

KIWI_MCP_URL = "https://mcp.kiwi.com/"


class KiwiError(Exception):
    pass


class Budget:
    """Počítadlo volaní Kiwi počas jedného behu (aby sme verejnú službu nezaťažovali)."""
    def __init__(self):
        self.calls = 0
        self.errors = 0

    def ok(self):
        return self.calls > 0 and self.errors < self.calls


def kiwi_search(arguments, budget=None):
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "search-flight", "arguments": {"currency": "EUR", "sort": "price", **arguments}}}
    if budget:
        budget.calls += 1
    try:
        r = requests.post(KIWI_MCP_URL, json=body, timeout=90, headers={
            "Accept": "application/json, text/event-stream",
            "User-Agent": "lacne-letenky/2.0 (osobne sledovanie cien)",
        })
        r.raise_for_status()
        return parse_response(r.text, r.headers.get("content-type", ""))
    except (requests.RequestException, ValueError, KeyError, KiwiError) as e:
        if budget:
            budget.errors += 1
        raise KiwiError(str(e)) from e


def parse_response(text, content_type=""):
    payload = None
    for line in text.splitlines():
        if line.startswith("data:"):
            payload = json.loads(line[5:])
    if payload is None and "json" in content_type:
        payload = json.loads(text)
    if not payload or "error" in payload:
        raise KiwiError(str((payload or {}).get("error", "prázdna odpoveď")))
    result = payload["result"]
    data = result.get("structuredContent")
    if data is None:
        data = json.loads(result["content"][0]["text"])
    if data.get("error"):
        raise KiwiError(str(data["error"]))
    return data.get("itineraries", [])


def kiwi_date(iso):
    y, m, d = iso.split("-")
    return f"{d}/{m}/{y}"


def common_args(cfg, rule):
    """Parametre spoločné pre všetky vyhľadávania: cestujúci, batožina, prestupy, filtre."""
    pax, f = cfg["passengers"], cfg["filters"]
    args = {"adults": pax["adults"], "max_sector_stopovers": cfg["max_transfers"]}
    if pax["hold_bags"]:
        args["adults_hold_bags"] = [pax["hold_bags"]] * pax["adults"]
    if f["earliest_departure_hour"] > 0:
        args["dtime_from"] = f["earliest_departure_hour"]
    if f["latest_departure_hour"] < 23:
        args["dtime_to"] = f["latest_departure_hour"]
    if f.get("exclude_airlines"):
        args["exclude_airlines"] = ",".join(f["exclude_airlines"])
    if rule.get("out_days"):
        args["fly_days"] = ",".join(str(d % 7) for d in rule["out_days"])       # ISO 1=po → Kiwi 1=po, 7=ne → 0
    if rule.get("back_days"):
        args["ret_fly_days"] = ",".join(str(d % 7) for d in rule["back_days"])
    return args


def leg(raw):
    return {
        "dep": raw["departureTime"][:16], "arr": raw["arrivalTime"][:16],
        "duration": raw.get("durationSeconds"), "route": raw.get("route", []),
        "segments": [{
            "from": s.get("from"), "to": s.get("to"), "from_city": s.get("fromCity"), "to_city": s.get("toCity"),
            "dep": (s.get("departureTime") or "")[:16], "arr": (s.get("arrivalTime") or "")[:16],
            "carrier": s.get("carrier"), "carrier_name": s.get("carrierName"), "flight": s.get("flightNumber"),
        } for s in raw.get("segments", [])],
    }


def to_offer(it, places, cfg, origin=None, destination=None):
    """Itinerár z Kiwi → ponuka so živou cenou, detailom letov a odkazom na rezerváciu."""
    out, back = it.get("outbound"), it.get("inbound")
    if not out or not back or not out.get("route"):
        return None
    airport = out["route"][-1]
    dest = destination or places.city_of_airport(airport)
    city, country = places.city(dest) or places.city(airport) or (out["segments"][-1].get("toCity", airport), "")
    region = region_of(country)
    dep, ret = out["departureTime"][:10], back["departureTime"][:10]
    adults = cfg["passengers"]["adults"]
    carriers = [s.get("carrier") for s in out.get("segments", []) + back.get("segments", []) if s.get("carrier")]
    start = out["route"][0]
    return {
        "source": "kiwi",
        "live": True,
        "origin": origin or places.city_of_airport(start),
        "origin_airport": start,
        "destination": dest,
        "destination_airport": airport,
        "city": city,
        "country": country,
        "region": region,
        "price_pp": round(it["price"] / adults),
        "price_total": round(it["price"]),
        "limit": limit_for(dest, country, region, cfg),
        "departure": dep,
        "return": ret,
        "days": (dt.date.fromisoformat(ret) - dt.date.fromisoformat(dep)).days,
        "transfers": max(out.get("stops", 0), back.get("stops", 0)),
        "airline": carriers[0] if carriers else "",
        "airlines": sorted(set(carriers)),
        "dep_hour": int(out["departureTime"][11:13]),
        "link": it.get("bookingUrl"),
        "age": 0,
        "image_id": it.get("imageId") or image_slug(city, country),
        "baggage": it.get("baggage"),
        "duration": it.get("totalDurationSeconds"),
        "out": leg(out),
        "back": leg(back),
    }


def range_search(cfg, today, fly_to, rule, one_for_city, budget, price_to=None):
    """Hľadanie zo všetkých letísk naraz na celé obdobie s daným počtom nocí."""
    last = today + dt.timedelta(days=30 * cfg["months_ahead"])
    args = {
        **common_args(cfg, rule),
        "flyFrom": ",".join(cfg["origins"]), "flyTo": fly_to,
        "departureDate": kiwi_date((today + dt.timedelta(days=1)).isoformat()),
        "departureDateTo": kiwi_date(last.isoformat()),
        # Kiwi počíta noci od príletu, my dni od odletu po návrat → o deň širšie, presne filtruje fits_rules
        "nights_in_dst_from": max(1, rule["min_days"] - 1), "nights_in_dst_to": rule["max_days"],
        "one_for_city": one_for_city,
    }
    if price_to:
        args["price_to"] = round(price_to * cfg["passengers"]["adults"])
    return kiwi_search(args, budget)


def offers_from(its, places, cfg, destination=None):
    return [o for o in (to_offer(it, places, cfg, destination=destination) for it in its) if o and fits_rules(o, cfg)]


# ─── Overenie ponúk z cache ──────────────────────────────────────────────────

def verify_key(o):
    return f"{o['origin']}-{o['destination']}-{o['departure']}-{o['return']}"


def merge_live(o, live):
    if live is None:
        o["unavailable"] = True
        return
    keep = {k: o[k] for k in ("origin", "destination", "city", "country", "region", "limit")}
    o.clear()
    o.update(live, **keep)


def apply_cached_verifications(offers, state, cfg, now):
    cache = state.setdefault("verified", {})
    ttl = dt.timedelta(hours=cfg["live"]["cache_hours"])
    for k in [k for k, v in cache.items() if now - dt.datetime.fromisoformat(v["at"]) > ttl]:
        del cache[k]
    for o in offers:
        k = verify_key(o)
        v = cache.get(k)
        if v and v["live"] is not None and not fits_rules(dict(v["live"], region=o["region"]), cfg):
            del cache[k]          # overené pred zmenou pravidiel → overiť znova
        elif v:
            merge_live(o, v["live"])


def verify(candidates, state, cfg, places, now, budget, limit):
    """Overí ponuky z cache naživo (±2 dni okolo termínu). Zdražené/nedostupné označí `unavailable`."""
    cache = state.setdefault("verified", {})
    used = 0
    for o in candidates:
        if o.get("live") or o.get("unavailable") or used >= limit:
            continue
        key, before = verify_key(o), o["price_pp"]
        used += 1
        rule = region_rule(o["region"], cfg)
        try:
            its = kiwi_search({
                **common_args(cfg, rule),
                "flyFrom": o["origin"], "flyTo": o["destination"],
                "departureDate": kiwi_date(o["departure"]), "departureDateFlexDays": 2,
                "returnDate": kiwi_date(o["return"]), "returnDateFlexDays": 2,
            }, budget)
        except KiwiError as e:
            print(f"  Kiwi overenie zlyhalo ({o['origin']}→{o['city']}): {e}", file=sys.stderr)
            continue
        live = next(iter(offers_from(its, places, cfg, o["destination"])), None)
        city = o["city"]
        merge_live(o, live)
        cache[key] = {"at": now.isoformat(), "live": live}
        print(f"  Overené {o['origin']}→{city}: cache {before} € → " +
              ("nedostupné" if live is None else f"naživo {live['price_pp']} €/os."))


# ─── Sledované destinácie a hľadanie po krajinách ────────────────────────────

def watch(cfg, places, today, budget):
    offers = []
    for w in cfg.get("watchlist", [])[:cfg["live"]["max_watch_searches"]]:
        code = w["code"]
        is_country = len(code) == 2
        try:
            its = range_search(cfg, today, w.get("name") if is_country else code,
                               rule_for_destination(code, cfg, places), is_country, budget)
        except KiwiError as e:
            print(f"  Kiwi sledovanie zlyhalo ({code}): {e}", file=sys.stderr)
            continue
        found = offers_from(its, places, cfg, None if is_country else code)
        offers.extend(found)
        best = min(found, key=lambda o: o["price_pp"], default=None)
        print(f"  Sledované {w.get('name', code)}: " +
              (f"naživo od {best['price_pp']} €/os. z {best['origin']}" if best else "nič"))
    return offers


def explore(cfg, places, today, state, budget, now):
    """Prehľadá naživo krajiny v diaľkových regiónoch, každý beh ďalšiu časť. Nálezy platia cache_hours."""
    excluded = set(cfg.get("excluded", []))
    combos = [(region, cc) for region, codes in EXPLORE_COUNTRIES.items()
              if cfg["regions"].get(region, {}).get("enabled") for cc in codes.split()
              if cc not in excluded and limit_for(cc, cc, region, cfg)]
    store = state.setdefault("explore", {})
    if combos:
        cursor = state.get("explore_cursor", 0) % len(combos)
        batch = [combos[(cursor + i) % len(combos)] for i in range(min(cfg["live"]["explore_per_run"], len(combos)))]
        state["explore_cursor"] = (cursor + len(batch)) % len(combos)
        smart_room = 1 + cfg["smart"]["max_over_limit_pct"] / 100 if cfg["smart"]["enabled"] else 1
        for region, cc in batch:
            try:
                its = range_search(cfg, today, places.countries.get(cc, cc), region_rule(region, cfg), True, budget,
                                   price_to=limit_for(cc, cc, region, cfg) * smart_room)
            except KiwiError as e:
                print(f"  Kiwi hľadanie zlyhalo ({cc}): {e}", file=sys.stderr)
                continue
            found = [o for o in offers_from(its, places, cfg) if o["country"] == cc]
            store[cc] = {"at": now.isoformat(), "offers": found}
            print(f"  Naživo {places.countries.get(cc, cc)}: " +
                  (", ".join(f"{o['city']} {o['price_pp']} €" for o in sorted(found, key=lambda o: o['price_pp'])[:4])
                   or "nič"))

    ttl = dt.timedelta(hours=cfg["live"]["cache_hours"])
    wanted = {cc for _, cc in combos}
    offers = []
    for cc in list(store):
        if cc not in wanted or now - dt.datetime.fromisoformat(store[cc]["at"]) > ttl:
            del store[cc]
            continue
        for o in store[cc]["offers"]:
            o = dict(o, limit=limit_for(o["destination"], o["country"], o["region"], cfg))  # limity sa mohli zmeniť
            if dt.date.fromisoformat(o["departure"]) > today and fits_rules(o, cfg):
                offers.append(o)
    return offers
