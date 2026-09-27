"""Pravidlá: cenové limity, dĺžka pobytu, dni odletu, časy, aerolínie a chytré upozornenia.

Ceny v pravidlách sú vždy za osobu (`price_pp`), aby limit znamenal to isté pri 1 aj 4 cestujúcich.
"""
import datetime as dt
import statistics

from .geo import region_of

OTHER_REGION = {"label": "Ostatné", "enabled": False, "max_price": 0, "min_days": 7, "max_days": 10,
                "out_days": [], "back_days": []}


def region_rule(region, cfg):
    return cfg["regions"].get(region) or OTHER_REGION


def region_label(region, cfg):
    return region_rule(region, cfg)["label"]


def limit_for(dest, country, region, cfg):
    """Limit na osobu pre destináciu, alebo None, ak ju nesledujeme."""
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
    return rule["max_price"] or None


def rule_for_destination(code, cfg, places):
    """Pravidlo regiónu pre IATA mesto alebo kód krajiny (pri sledovaných destináciách)."""
    country = code if len(code) == 2 else (places.city(code) or ("", ""))[1]
    return region_rule(region_of(country), cfg)


def fits_rules(o, cfg):
    """Dĺžka pobytu, prestupy, dni odletu a návratu, čas odletu a vylúčené aerolínie."""
    rule = region_rule(o["region"], cfg)
    if o["transfers"] > cfg["max_transfers"]:
        return False
    if not rule["min_days"] <= o["days"] <= rule["max_days"]:
        return False
    if rule.get("out_days") and dt.date.fromisoformat(o["departure"]).isoweekday() not in rule["out_days"]:
        return False
    if rule.get("back_days") and dt.date.fromisoformat(o["return"]).isoweekday() not in rule["back_days"]:
        return False
    f = cfg["filters"]
    hour = o.get("dep_hour")
    if hour is not None and not f["earliest_departure_hour"] <= hour <= f["latest_departure_hour"]:
        return False
    if set(o.get("airlines") or [o.get("airline")]) & set(f.get("exclude_airlines") or []):
        return False
    return True


def typical_price(history_entry, cfg):
    """Bežná cena za osobu: medián denných miním živých cien (len ak je dosť histórie)."""
    pts = (history_entry or {}).get("live") or []
    if len({p[0] for p in pts}) < cfg["smart"]["min_history_days"]:
        return None
    return statistics.median(p[1] for p in pts)


def evaluate(o, cfg, history):
    """Doplní do ponuky dôvod upozornenia (`reasons`), bežnú cenu a percento zľavy."""
    o["reasons"] = []
    limit = o.get("limit")
    if not limit:
        return o
    if o["price_pp"] <= limit:
        o["reasons"].append("limit")
    s = cfg["smart"]
    typical = typical_price(history.get(o["destination"]), cfg) if s["enabled"] else None
    o["typical"] = round(typical) if typical else None
    if typical:
        o["drop_pct"] = round((1 - o["price_pp"] / typical) * 100)
        if (o["drop_pct"] >= s["drop_pct"] and o["live"]
                and o["price_pp"] <= limit * (1 + s["max_over_limit_pct"] / 100)):
            o["reasons"].append("smart")
    return o


def is_deal(o):
    return bool(o.get("reasons"))


def score(o):
    """Čím menšie, tým lepšia ponuka: podiel ceny voči limitu, pri chytrej ponuke voči bežnej cene."""
    parts = [o["price_pp"] / o["limit"]] if o.get("limit") else []
    if o.get("typical"):
        parts.append(o["price_pp"] / o["typical"])
    return min(parts) if parts else 9
