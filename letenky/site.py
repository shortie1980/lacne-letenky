"""Dáta pre webovú aplikáciu (GitHub Pages) a história cien."""
import datetime as dt
import json

from . import health
from .geo import image_url
from .rules import OTHER_REGION, region_rule, score
from .text import buy_link, google_flights_link

HISTORY_DAYS = 120
PUBLIC_KEYS = ("origin", "destination", "city", "country", "region", "price_pp", "price_total", "limit",
               "departure", "return", "days", "transfers", "airline", "airlines", "age", "live", "baggage",
               "duration", "out", "back", "typical", "drop_pct", "reasons")


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def public_offer(o, airlines):
    out = {k: o.get(k) for k in PUBLIC_KEYS}
    out["airline_name"] = airlines.get(o.get("airline"), o.get("airline"))
    out["buy"] = buy_link(o)
    out["google"] = google_flights_link(o)
    out["image"] = image_url(o.get("image_id"))
    out["score"] = round(score(o), 3)
    return out


def cheapest_by(offers, key, price="price_pp"):
    best = {}
    for o in offers:
        k = key(o)
        if k not in best or o[price] < best[k][price]:
            best[k] = o
    return best


def update_history(history, offers, cfg, today):
    """Denné minimum ceny za osobu: `points` z cache, `live` zo živých cien (základ pre chytré upozornenia)."""
    watched = {w["code"] for w in cfg.get("watchlist", [])}
    day = today.isoformat()

    def add(entry, series, price):
        pts = entry.setdefault(series, [])
        if pts and pts[-1][0] == day:
            pts[-1][1] = min(pts[-1][1], price)
        else:
            pts.append([day, price])

    usable = [o for o in offers if not o.get("unavailable")]
    for series, subset in (("points", [o for o in usable if not o.get("live")]), ("live", [o for o in usable if o.get("live")])):
        for dest, o in cheapest_by(subset, lambda o: o["destination"]).items():
            ref = o.get("limit") or region_rule(o["region"], cfg)["max_price"]
            if series == "points" and not (dest in watched or o["country"] in watched or (ref and o["price_pp"] <= ref * 2)):
                continue
            entry = history.setdefault(dest, {})
            entry.update(name=o["city"], country=o["country"], region=o["region"])
            add(entry, series, o["price_pp"])

    cutoff = (today - dt.timedelta(days=HISTORY_DAYS)).isoformat()
    for dest in list(history):
        for series in ("points", "live"):
            if series in history[dest]:
                history[dest][series] = [p for p in history[dest][series] if p[0] >= cutoff]
        if not history[dest].get("points") and not history[dest].get("live"):
            del history[dest]
    return history


def write_site(data_dir, offers, deals, tips, history, places, cfg, state, now):
    usable = [o for o in offers if not o.get("unavailable")]
    by_region = {}
    for o in sorted(cheapest_by(usable, lambda o: o["destination"]).values(), key=lambda o: (not o.get("live"), o["price_pp"])):
        lst = by_region.setdefault(o["region"], [])
        if len(lst) < 12:
            lst.append(public_offer(o, places.airlines))
    for lst in by_region.values():
        lst.sort(key=lambda o: o["price_pp"])

    regions = {k: v["label"] for k, v in cfg["regions"].items()}
    regions["other"] = OTHER_REGION["label"]
    write_json(data_dir / "deals.json", {
        "version": 2,
        "updated_at": now.isoformat(),
        "origins": cfg["origins"],
        "regions": regions,
        "passengers": cfg["passengers"],
        "deals": [public_offer(d, places.airlines) for d in deals[:200]],
        "cheapest": by_region,
        "tips": tips[:30],
        "health": health.public(state),
        "stats": {"offers_checked": len(offers), "live": sum(1 for d in deals if d.get("live")), "deals": len(deals),
                  "kiwi_calls": state.get("last_kiwi_calls", 0)},
    })
    write_json(data_dir / "history.json", history)

    seen = {o["destination"] for o in offers} | {w["code"] for w in cfg.get("watchlist", []) if len(w["code"]) == 3}
    cities = sorted(([c, places.city(c)[0], places.city(c)[1]] for c in seen if places.city(c)), key=lambda x: x[1])
    countries = sorted(([c, n] for c, n in places.countries.items()), key=lambda x: x[1])
    airlines = sorted(({o.get("airline") for o in offers if o.get("airline")} | set(cfg["filters"].get("exclude_airlines", []))))
    write_json(data_dir / "places.json", {
        "cities": cities, "countries": countries,
        "airlines": [[a, places.airlines.get(a, a)] for a in airlines],
    })
