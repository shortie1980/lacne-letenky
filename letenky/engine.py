"""Jeden beh vyhľadávania: kandidáti z cache → živé ceny z Kiwi → výber ponúk → upozornenia → dáta pre web."""
import argparse
import datetime as dt
import os
import sys
from pathlib import Path

from . import config, health, notify, rules
from .geo import load_places
from .site import read_json, update_history, update_market, write_json, write_site
from .sources import fly4free, kiwi, travelpayouts, letenkyzababku, thriftytraveler
from .text import freshness_text, price_text, transfers_text

STATE_VERSION = 2
MARKET_MAX_AGE_DAYS = 30
SITE_DIR = Path(os.environ.get("SITE_DIR", config.ROOT / "site"))
DATA_DIR = SITE_DIR / "data"


def filter_new(deals, state, cfg, now):
    """Ponuky, o ktorých ešte neprišlo upozornenie (alebo odvtedy výrazne zlacneli), max. N z regiónu."""
    fresh = []
    for d in deals:
        prev = state["notified"].get(f"{d['origin']}-{d['destination']}")
        if prev:
            age_days = (now - dt.datetime.fromisoformat(prev["at"])).days
            dropped = d["price_pp"] <= prev["price"] * (1 - cfg["renotify_drop_pct"] / 100)
            if age_days < cfg["renotify_days"] and not dropped:
                continue
        fresh.append(d)
    fresh.sort(key=lambda d: (not d.get("exceptional"), rules.score(d)))
    per_region, out = {}, []
    for d in fresh:
        per_region[d["region"]] = per_region.get(d["region"], 0) + 1
        if per_region[d["region"]] <= cfg["max_alerts_per_region"]:
            out.append(d)
    return out


def pick_deals(offers, cfg, history):
    """Najlepšia ponuka pre každú trasu. Živá cena má prednosť pred cache."""
    best = {}
    for o in offers:
        if o.get("unavailable") or not rules.fits_rules(o, cfg):
            continue
        rules.evaluate(o, cfg, history)
        if not rules.is_deal(o):
            continue
        k = f"{o['origin']}-{o['destination']}"
        rank = (not o.get("live"), o["price_pp"])
        if k not in best or rank < (not best[k].get("live"), best[k]["price_pp"]):
            best[k] = o
    return sorted(best.values(), key=rules.score)


def migrate(state):
    if state.get("version") != STATE_VERSION:
        for key in ("verified", "explore", "explore_cursor"):
            state.pop(key, None)
        state["version"] = STATE_VERSION
    state.setdefault("notified", {})
    return state


SAMPLE_DEAL = {
    "source": "kiwi", "live": True, "origin": "VIE", "origin_airport": "VIE", "destination": "BKK",
    "destination_airport": "BKK", "city": "Bangkok", "country": "TH", "region": "asia", "price_pp": 399,
    "price_total": 399, "limit": 450, "departure": "2026-11-10", "return": "2026-11-18", "days": 8, "transfers": 1,
    "airline": "EY", "airlines": ["EY"], "link": None, "image_id": "bangkok_th",
    "baggage": {"personalItem": 1, "cabinBag": 1, "checkedBag": 1}, "reasons": ["limit", "smart"],
    "typical": 690, "drop_pct": 42, "typical_source": "market", "exceptional": True,
}
SAMPLE_TIP = {"title": "Skúšobný tip: lety z Viedne do Ázie od 399 €", "link": "https://www.fly4free.com/", "origin": "VIE"}


def run(args):
    cfg = config.load()
    dashboard_url = os.environ.get("DASHBOARD_URL", "")
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    today = now.date()

    if args.test_notify:
        ok, err = notify.notify([SAMPLE_DEAL], [SAMPLE_TIP], cfg, {"EY": "Etihad Airways"}, dashboard_url)
        print("Skúšobné upozornenie odoslané." if ok else f"Odoslanie zlyhalo: {err}")
        return 0 if ok else 1

    token = os.environ.get("TRAVELPAYOUTS_TOKEN")
    if not token:
        print("Chýba premenná TRAVELPAYOUTS_TOKEN.", file=sys.stderr)
        return 2

    state = migrate(read_json(DATA_DIR / "state.json", {}))
    history = read_json(DATA_DIR / "history.json", {})
    places = load_places()
    events = []

    # 1) Kandidáti z cache (Travelpayouts)
    offers, tp_errors, tp_calls = [], [], 0
    market = {}                                   # destinácia -> {deň odletu: najnižšia cena za osobu}
    for origin in cfg["origins"]:
        for month in travelpayouts.upcoming_months(cfg["months_ahead"], today):
            tp_calls += 1
            try:
                items = travelpayouts.fetch_prices(origin, month, token)
            except travelpayouts.TravelpayoutsError as e:
                tp_errors.append(str(e))
                continue
            for it in items:
                o = travelpayouts.to_offer(it, places, cfg, today, max_age=MARKET_MAX_AGE_DAYS)
                if not o:
                    continue
                days = market.setdefault(o["destination"], {})
                days[o["departure"]] = min(days.get(o["departure"], o["price_pp"]), o["price_pp"])
                if o["age"] is None or o["age"] <= cfg["max_price_age_days"]:
                    offers.append(o)
    tp_ok = len(tp_errors) < tp_calls
    events.append(("travelpayouts", health.update(state, "travelpayouts", tp_ok, "; ".join(tp_errors[:2]), now), tp_errors[:1]))
    print(f"Travelpayouts: {len(offers)} kandidátov z {tp_calls} dopytov ({len(tp_errors)} chýb)")
    history = update_market(history, market, today)

    # 2) Živé ceny z Kiwi
    budget = kiwi.Budget()
    kiwi.apply_cached_verifications(offers, state, cfg, now)
    offers.extend(kiwi.watch(cfg, places, today, budget))
    offers.extend(kiwi.explore(cfg, places, today, state, budget, now))

    deals = pick_deals(offers, cfg, history)
    new_first = filter_new(deals, state, cfg, now)
    order = new_first + [d for d in deals if d not in new_first]
    kiwi.verify(order, state, cfg, places, now, budget, cfg["live"]["max_verify_per_run"])
    deals = pick_deals(offers, cfg, history)
    state["last_kiwi_calls"] = budget.calls
    kiwi_ok = budget.calls == 0 or budget.errors < budget.calls
    events.append(("kiwi", health.update(state, "kiwi", kiwi_ok, f"{budget.errors}/{budget.calls} vyhľadávaní zlyhalo", now), None))

    # 3) Akciové tipy
    tips, new_tips = [], []
    if cfg["tips"]["enabled"]:
        # fly4free tips
        try:
            tips.extend(fly4free.parse(fly4free.fetch(), cfg["origins"], places, now))
            events.append(("fly4free", health.update(state, "fly4free", True, None, now), None))
        except fly4free.TipsError as e:
            events.append(("fly4free", health.update(state, "fly4free", False, e, now), None))

        # letenkyzababku tips
        try:
            tips.extend(letenkyzababku.parse(letenkyzababku.fetch(), cfg["origins"], places, now))
            events.append(("letenkyzababku", health.update(state, "letenkyzababku", True, None, now), None))
        except letenkyzababku.LetenkyzababkuError as e:
            events.append(("letenkyzababku", health.update(state, "letenkyzababku", False, e, now), None))

        # thriftytraveler tips
        try:
            tips.extend(thriftytraveler.parse(thriftytraveler.fetch(), cfg["origins"], places, now))
            events.append(("thriftytraveler", health.update(state, "thriftytraveler", True, None, now), None))
        except thriftytraveler.ThriftyTravelerError as e:
            events.append(("thriftytraveler", health.update(state, "thriftytraveler", False, e, now), None))

        seen = set(state.get("tips_seen", []))
        recent = now - dt.timedelta(hours=36)
        tips = sorted(tips, key=lambda t: t["published"], reverse=True)
        new_tips = [t for t in tips if t["id"] not in seen and dt.datetime.fromisoformat(t["published"]) >= recent]
        state["tips_seen"] = [t["id"] for t in tips][:200]

    # 4) Čo poslať: len živé ceny
    fresh = filter_new([d for d in deals if d.get("live")], state, cfg, now)[:cfg["max_alerts_per_run"]]
    adults = cfg["passengers"]["adults"]
    print(f"\nPonúk: {len(deals)} (živých {sum(1 for d in deals if d.get('live'))}), "
          f"nových na odoslanie: {len(fresh)}, nových tipov: {len(new_tips)}, Kiwi: {budget.calls} vyhľadávaní")
    for d in fresh:
        print(f"  {d['origin']} → {d['city']} ({d['country']}): {price_text(d, adults)} · {freshness_text(d)} · "
              f"{d['departure']} – {d['return']} · {transfers_text(d['transfers'])} · {','.join(d['reasons'])}")

    history = update_history(history, offers, cfg, today)
    write_site(DATA_DIR, offers, deals, tips, history, places, cfg, state, now)

    if args.dry_run:
        if fresh or new_tips:
            _, html = notify.build_email(fresh, new_tips, cfg, places.airlines, dashboard_url)
            (config.ROOT / "email-preview.html").write_text(html, encoding="utf-8")
        print(f"\nDáta pre web: {SITE_DIR}")
        return 0

    if fresh or new_tips:
        ok, err = notify.notify(fresh, new_tips, cfg, places.airlines, dashboard_url)
        events.append(("notify", health.update(state, "notify", ok, err, now), None))
        if ok:
            for d in fresh:
                state["notified"][f"{d['origin']}-{d['destination']}"] = {"price": d["price_pp"], "at": now.isoformat()}

    if cfg["notify"].get("health_alerts", True):
        for source, event, _ in events:
            if event:
                h = state["health"][source]
                notify.notify_health(health.SOURCES.get(source, source), event, h.get("last_error"), cfg, dashboard_url)

    cutoff = now - dt.timedelta(days=60)
    state["notified"] = {k: v for k, v in state["notified"].items() if dt.datetime.fromisoformat(v["at"]) >= cutoff}
    state["last_run"] = now.isoformat()
    write_json(DATA_DIR / "state.json", state)
    if not tp_ok and not kiwi_ok:
        print("Travelpayouts aj Kiwi zlyhali.", file=sys.stderr)
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Sledovanie lacných leteniek")
    parser.add_argument("--dry-run", action="store_true", help="nič neposielať, neukladať stav upozornení")
    parser.add_argument("--test-notify", action="store_true", help="poslať skúšobné upozornenie")
    sys.exit(run(parser.parse_args(argv)))
