import datetime as dt
import json
from pathlib import Path

import pytest

from letenky import config, health, notify, rules
from letenky.engine import filter_new, migrate, pick_deals
from letenky.geo import Places, image_slug
from letenky.site import update_history
from letenky.sources import fly4free, kiwi, travelpayouts
from letenky.text import plural

FIX = Path(__file__).parent / "fixtures"
NOW = dt.datetime(2026, 9, 27, 10, tzinfo=dt.timezone.utc)
TODAY = NOW.date()


@pytest.fixture
def cfg():
    return config.merge(config.DEFAULTS, {"excluded": ["KZ"], "watchlist": [{"code": "TYO", "name": "Tokyo", "max_price": 600}]})


@pytest.fixture
def places():
    p = Places()
    p.places = {"BKK": ("Bangkok", "TH"), "DMK": ("Bangkok", "TH"), "VIE": ("Vienna", "AT"), "TYO": ("Tokyo", "JP"),
                "EVN": ("Yerevan", "AM"), "ALA": ("Almaty", "KZ"), "PRG": ("Prague", "CZ"), "SHJ": ("Sharjah", "AE")}
    p.airport_city = {"DMK": "BKK", "BKK": "BKK", "VIE": "VIE", "NRT": "TYO", "HND": "TYO"}
    p.countries = {"TH": "Thailand", "JP": "Japan"}
    return p


def offer(**kw):
    base = {"source": "kiwi", "live": True, "origin": "VIE", "origin_airport": "VIE", "destination": "BKK",
            "destination_airport": "BKK", "city": "Bangkok", "country": "TH", "region": "asia", "price_pp": 400,
            "price_total": 400, "limit": 450, "departure": "2026-11-10", "return": "2026-11-18", "days": 8,
            "transfers": 1, "airline": "EY", "airlines": ["EY"], "dep_hour": 10, "link": "https://kiwi.com/u/x"}
    base.update(kw)
    return base


# ─── Konfigurácia ────────────────────────────────────────────────────────────

def test_config_fills_missing_keys_but_keeps_user_values():
    c = config.merge(config.DEFAULTS, {"regions": {"asia": {"label": "Ázia", "max_price": 500}}, "months_ahead": 3})
    assert c["months_ahead"] == 3
    assert c["passengers"] == {"adults": 1, "hold_bags": 0}
    assert c["regions"]["asia"]["max_price"] == 500 and c["regions"]["asia"]["min_days"] == 7
    assert c["regions"]["asia"]["out_days"] == []
    assert "europe" not in c["regions"]          # región, ktorý používateľ nemá, sa nepridá


def test_repository_config_is_valid():
    c = config.load()
    assert c["origins"] and all(len(o) == 3 for o in c["origins"])
    for r in c["regions"].values():
        assert r["min_days"] <= r["max_days"]


# ─── Pravidlá ────────────────────────────────────────────────────────────────

def test_limits_watchlist_and_exclusions(cfg):
    assert rules.limit_for("BKK", "TH", "asia", cfg) == 450
    assert rules.limit_for("TYO", "JP", "asia", cfg) == 600            # sledovaná destinácia má prednosť
    assert rules.limit_for("ALA", "KZ", "central_asia", cfg) is None    # vylúčená krajina
    cfg["regions"]["asia"]["enabled"] = False
    assert rules.limit_for("BKK", "TH", "asia", cfg) is None


def test_fits_rules_days_weekdays_hours_airlines(cfg):
    assert rules.fits_rules(offer(), cfg)
    assert not rules.fits_rules(offer(days=12), cfg)                     # Ázia max 10 dní
    assert not rules.fits_rules(offer(transfers=3), cfg)
    cfg["regions"]["asia"]["out_days"] = [4, 5]                          # št, pi
    assert not rules.fits_rules(offer(departure="2026-11-10"), cfg)      # utorok
    assert rules.fits_rules(offer(departure="2026-11-12", days=8), cfg)  # štvrtok
    cfg["filters"]["earliest_departure_hour"] = 11
    assert not rules.fits_rules(offer(departure="2026-11-12", dep_hour=6), cfg)
    cfg["filters"]["earliest_departure_hour"] = 0
    cfg["filters"]["exclude_airlines"] = ["EY"]
    assert not rules.fits_rules(offer(departure="2026-11-12"), cfg)


def test_smart_deal_needs_history_and_live_price(cfg):
    history = {"BKK": {"live": [[f"2026-09-{d:02d}", 600] for d in range(20, 26)]}}
    o = rules.evaluate(offer(price_pp=500, limit=450), cfg, history)     # nad limitom, ale −17 %
    assert o["reasons"] == [] and o["typical"] == 600 and o["drop_pct"] == 17
    o = rules.evaluate(offer(price_pp=420, limit=450), cfg, history)     # pod limitom aj −30 %
    assert o["reasons"] == ["limit", "smart"]
    o = rules.evaluate(offer(price_pp=440, limit=280), cfg, history)     # −27 %, ale viac ako +50 % nad limit
    assert o["reasons"] == []
    o = rules.evaluate(offer(price_pp=420, limit=300), cfg, history)
    assert o["reasons"] == ["smart"]
    o = rules.evaluate(offer(price_pp=420, limit=300, live=False), cfg, history)
    assert o["reasons"] == []                                            # chytré upozornenie len so živou cenou
    assert rules.evaluate(offer(), cfg, {"BKK": {"live": [["2026-09-25", 600]]}})["typical"] is None


# ─── Výber a upozornenia ─────────────────────────────────────────────────────

def test_pick_prefers_live_price_and_skips_unavailable(cfg):
    cached = offer(live=False, price_pp=300)
    live = offer(price_pp=380)
    gone = offer(price_pp=100, unavailable=True)
    deals = pick_deals([cached, live, gone], cfg, {})
    assert deals == [live]


def test_filter_new_respects_renotify_and_region_cap(cfg):
    state = {"notified": {"VIE-BKK": {"price": 400, "at": (NOW - dt.timedelta(days=2)).isoformat()}}}
    assert filter_new([offer(price_pp=390)], state, cfg, NOW) == []                   # len −2,5 %
    assert len(filter_new([offer(price_pp=350)], state, cfg, NOW)) == 1               # −12,5 %
    many = [offer(destination=f"X{i}", price_pp=300 + i) for i in range(6)]
    for o in many:
        rules.evaluate(o, cfg, {})
    assert len(filter_new(many, {"notified": {}}, cfg, NOW)) == cfg["max_alerts_per_region"]


def test_state_migration_drops_old_caches():
    s = migrate({"verified": {"x": 1}, "explore": {}, "notified": {"a": 1}})
    assert s == {"notified": {"a": 1}, "version": 2}


# ─── Zdroje ──────────────────────────────────────────────────────────────────

def test_travelpayouts_offer_and_price_age(places, cfg):
    it = {"origin": "VIE", "destination": "BKK", "price": 407, "airline": "EY", "transfers": 1, "return_transfers": 1,
          "departure_at": "2026-11-10T22:10:00+01:00", "return_at": "2026-11-18T09:00:00+07:00",
          "link": "/search/VIE1011BKK18111?search_date=26092026"}
    o = travelpayouts.to_offer(it, places, cfg, TODAY)
    assert o["age"] == 1 and o["dep_hour"] == 22 and o["days"] == 8 and not o["live"]
    it["link"] = "/search/x?search_date=01092026"
    assert travelpayouts.to_offer(it, places, cfg, TODAY) is None                     # príliš stará cena


def test_kiwi_parse_and_offer(places, cfg):
    its = kiwi.parse_response("event: message\ndata: " + json.dumps(json.loads((FIX / "kiwi_vie_bkk.json").read_text())))
    assert len(its) == 3
    o = kiwi.to_offer(its[0], places, cfg)
    assert o["live"] and o["destination"] == "BKK" and o["price_pp"] == 502
    assert o["out"]["route"] == ["VIE", "SHJ", "BKK"] and o["out"]["segments"][0]["carrier_name"] == "Air Arabia"
    assert o["baggage"]["cabinBag"] == 1 and o["image_id"] == "bangkok_th"
    cfg["passengers"]["adults"] = 2
    assert kiwi.to_offer(its[0], places, cfg)["price_pp"] == 251


def test_kiwi_common_args_convert_weekdays(cfg):
    rule = dict(cfg["regions"]["europe"], out_days=[4, 5, 7], back_days=[1])
    cfg["passengers"] = {"adults": 2, "hold_bags": 1}
    cfg["filters"].update(earliest_departure_hour=6, exclude_airlines=["W6", "FR"])
    a = kiwi.common_args(cfg, rule)
    assert a["fly_days"] == "4,5,0" and a["ret_fly_days"] == "1"
    assert a["adults"] == 2 and a["adults_hold_bags"] == [1, 1] and a["dtime_from"] == 6
    assert a["exclude_airlines"] == "W6,FR" and "dtime_to" not in a


def test_kiwi_error_payload():
    with pytest.raises(kiwi.KiwiError):
        kiwi.parse_response('data: {"jsonrpc":"2.0","id":1,"error":{"code":-32000,"message":"rate limit"}}')


def test_fly4free_filters_to_our_airports():
    tips = fly4free.parse((FIX / "fly4free.xml").read_text(), ["VIE", "BUD", "PRG"],
                          now=dt.datetime(2026, 9, 28, tzinfo=dt.timezone.utc))
    assert tips and all(t["origin"] in {"VIE", "BUD", "PRG"} for t in tips)
    assert all("hotel" not in t["title"].lower() or "flight" in t["title"].lower() for t in tips)
    prague = [t for t in tips if "Prague to South Africa" in t["title"]]
    assert prague and prague[0]["price"] == 490


# ─── Ostatné ─────────────────────────────────────────────────────────────────

def test_health_alerts_after_three_failures_and_on_recovery():
    s = {}
    assert [health.update(s, "kiwi", False, "x", NOW) for _ in range(4)] == [None, None, "down", None]
    assert health.update(s, "kiwi", True, None, NOW) == "recovered"
    assert health.update(s, "kiwi", True, None, NOW) is None


def test_history_keeps_live_and_cache_series(cfg):
    h = update_history({}, [offer(price_pp=400), offer(price_pp=380), offer(live=False, price_pp=300)], cfg, TODAY)
    assert h["BKK"]["live"] == [[TODAY.isoformat(), 380]] and h["BKK"]["points"] == [[TODAY.isoformat(), 300]]


def test_texts_and_email(cfg):
    assert [plural(n, "a", "b", "c") for n in (1, 3, 5)] == ["a", "b", "c"]
    assert image_slug("Chiang Mai", "TH") == "chiang-mai_th" and image_slug("Kraków", "PL") == "krakow_pl"
    d = rules.evaluate(offer(), cfg, {})
    subject, html = notify.build_email([d, offer(city="Hanoi", price_pp=390)], [], cfg, {"EY": "Etihad"}, "https://x/")
    assert subject == "✈️ VIE → Hanoi za 390 € a ďalšia lacná letenka"
    assert "Etihad" in html and "Kúpiť" in html
    card = notify.build_card([d], [{"title": "Tip", "link": "https://t"}], cfg, {}, "")
    json.dumps(card)
