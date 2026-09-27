"""Načítanie nastavení. Chýbajúce hodnoty sa doplnia z DEFAULTS, takže staršie config.json fungujú ďalej."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config.json"

DEFAULTS = {
    "origins": ["VIE", "BTS", "BUD", "PRG"],
    "months_ahead": 6,
    "max_transfers": 2,
    "max_alerts_per_run": 15,
    "max_alerts_per_region": 4,
    "renotify_days": 7,
    "renotify_drop_pct": 10,
    "max_price_age_days": 4,
    "passengers": {"adults": 1, "hold_bags": 0},
    "filters": {
        "earliest_departure_hour": 0,
        "latest_departure_hour": 23,
        "exclude_airlines": [],
    },
    "regions": {
        "europe":        {"label": "Európa",                  "enabled": True,  "max_price": 35,  "min_days": 3, "max_days": 7},
        "middle_east":   {"label": "Kaukaz a Blízky východ",  "enabled": True,  "max_price": 100, "min_days": 7, "max_days": 10},
        "central_asia":  {"label": "Stredná Ázia",            "enabled": False, "max_price": 250, "min_days": 7, "max_days": 10},
        "asia":          {"label": "Ázia",                    "enabled": True,  "max_price": 450, "min_days": 7, "max_days": 10},
        "north_america": {"label": "Severná Amerika",         "enabled": True,  "max_price": 350, "min_days": 7, "max_days": 10},
        "latam":         {"label": "Južná Amerika a Karibik", "enabled": True,  "max_price": 650, "min_days": 7, "max_days": 10},
    },
    "region_defaults": {"out_days": [], "back_days": []},
    "watchlist": [],
    "excluded": [],
    "smart": {"enabled": True, "drop_pct": 25, "min_history_days": 4, "max_over_limit_pct": 50},
    "tips": {"enabled": True},
    "notify": {"ntfy_topic": "", "health_alerts": True},
    "live": {"max_verify_per_run": 10, "max_watch_searches": 10, "explore_per_run": 14, "cache_hours": 6},
}


def deep_merge(defaults, user):
    """Rekurzívne doplní chýbajúce kľúče. Zoznamy a hodnoty od používateľa majú prednosť."""
    out = copy.deepcopy(defaults)
    for k, v in (user or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict) and k != "regions":
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def merge(defaults, user):
    out = deep_merge(defaults, user)
    # regióny: doplniť chýbajúce polia v každom regióne, ale nepridávať regióny, ktoré používateľ zmazal
    for key, region in out["regions"].items():
        base = DEFAULTS["regions"].get(key, {"label": key, "enabled": False, "max_price": 0, "min_days": 7, "max_days": 10})
        out["regions"][key] = {**base, **DEFAULTS["region_defaults"], **region}
    return out


def load(path=CONFIG_FILE):
    return merge(DEFAULTS, json.loads(Path(path).read_text(encoding="utf-8")))
