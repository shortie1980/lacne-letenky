"""Travelpayouts (Aviasales) – ceny z cache vyhľadávaní iných ľudí. Rýchle a široké, ale pri diaľkových
letoch často nepresné, preto slúžia len ako kandidáti na živé overenie."""
import datetime as dt
import re

import requests

from ..geo import image_slug, region_of
from ..rules import limit_for

TP_PRICES_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"


class TravelpayoutsError(Exception):
    pass


def upcoming_months(count, today):
    months, year, month = [], today.year, today.month
    for _ in range(count):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return months


def fetch_prices(origin, month, token):
    params = {
        "origin": origin, "departure_at": month, "one_way": "false", "direct": "false",
        "sorting": "price", "unique": "false", "currency": "eur", "limit": 1000, "page": 1, "token": token,
    }
    try:
        r = requests.get(TP_PRICES_URL, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        raise TravelpayoutsError(str(e)) from e
    if not data.get("success"):
        raise TravelpayoutsError(f"{origin} {month}: {data.get('error')}")
    return data.get("data", [])


def price_age(link, today):
    """Pred koľkými dňami niekto túto cenu našiel (z parametra search_date v odkaze)."""
    m = re.search(r"search_date=(\d{2})(\d{2})(\d{4})", link or "")
    if not m:
        return None
    try:
        return (today - dt.date(int(m[3]), int(m[2]), int(m[1]))).days
    except ValueError:
        return None


def to_offer(it, places, cfg, today, max_age=None):
    """Záznam z API → ponuka. None, ak chýbajú údaje, let už bol alebo je cena príliš stará."""
    dest = it.get("destination")
    if not places.city(dest) or not it.get("return_at") or it.get("price") is None:
        return None
    city, country = places.city(dest)
    dep = dt.date.fromisoformat(it["departure_at"][:10])
    ret = dt.date.fromisoformat(it["return_at"][:10])
    if dep <= today:
        return None
    age = price_age(it.get("link"), today)
    if age is not None and age > (max_age if max_age is not None else cfg["max_price_age_days"]):
        return None
    region = region_of(country)
    adults = cfg["passengers"]["adults"]
    return {
        "source": "cache",
        "live": False,
        "origin": it.get("origin"),
        "origin_airport": it.get("origin_airport") or it.get("origin"),
        "destination": dest,
        "destination_airport": it.get("destination_airport") or dest,
        "city": city,
        "country": country,
        "region": region,
        "price_pp": it["price"],
        "price_total": it["price"] * adults,
        "limit": limit_for(dest, country, region, cfg),
        "departure": dep.isoformat(),
        "return": ret.isoformat(),
        "days": (ret - dep).days,
        "transfers": max(it.get("transfers", 0), it.get("return_transfers", 0)),
        "airline": it.get("airline", ""),
        "airlines": [it.get("airline", "")],
        "dep_hour": int(it["departure_at"][11:13]) if len(it["departure_at"]) >= 13 else None,
        "link": "https://www.aviasales.com" + it["link"] if it.get("link") else None,
        "age": age,
        "image_id": image_slug(city, country),
        "baggage": None,
    }
