"""Formátovanie textov pre upozornenia (slovenské skloňovanie, dátumy, batožina)."""
import datetime as dt
from urllib.parse import quote

from .rules import region_label

WEEKDAYS = ["po", "ut", "st", "št", "pi", "so", "ne"]


def flag(country):
    if not country or len(country) != 2 or not country.isalpha():
        return "🌍"
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in country.upper())


def plural(n, one, few, many):
    if n == 1:
        return one
    return few if 2 <= n <= 4 else many


def fmt_date(iso, weekday=True):
    d = dt.date.fromisoformat(iso[:10])
    return (f"{WEEKDAYS[d.weekday()]} " if weekday else "") + f"{d.day}. {d.month}."


def transfers_text(n):
    return "priamy let" if n == 0 else f"{n} {plural(n, 'prestup', 'prestupy', 'prestupov')}"


def nights_text(days):
    return f"{days} {plural(days, 'deň', 'dni', 'dní')}"


def baggage_text(b, adults):
    if not b:
        return None
    if b.get("checkedBag", 0) >= adults:
        return "🧳 kufor v cene"
    if b.get("cabinBag", 0) >= adults:
        return "🎒 príručná batožina v cene"
    return "👜 len malá taška"


def google_flights_link(o):
    q = f"Flights from {o['origin']} to {o['destination']} on {o['departure']} through {o['return']}"
    return "https://www.google.com/travel/flights?q=" + quote(q)


def buy_link(o):
    return o.get("link") or google_flights_link(o)


def price_text(o, adults):
    return f"{o['price_pp']} €" + (f" / os. (spolu {o['price_total']} €)" if adults > 1 else "")


def why_text(o):
    parts = []
    if "smart" in o.get("reasons", []) and o.get("drop_pct"):
        parts.append(f"📉 o {o['drop_pct']} % lacnejšie ako bežne ({o['typical']} €)")
    if "limit" in o.get("reasons", []):
        parts.append(f"pod tvojím limitom {o['limit']} €")
    return " · ".join(parts)


def freshness_text(o):
    if o.get("live"):
        return "✓ živá cena z Kiwi.com"
    age = o.get("age")
    if age is None:
        return "cena z cache, neoverená"
    return "cena z cache nájdená dnes" if age == 0 else f"cena z cache spred {age} {plural(age, 'dňa', 'dní', 'dní')}"


def details_text(o, cfg, airlines=None):
    airline = (airlines or {}).get(o.get("airline"), o.get("airline", ""))
    bits = [f"{fmt_date(o['departure'])} – {fmt_date(o['return'])}", nights_text(o["days"]),
            transfers_text(o["transfers"]), airline, region_label(o["region"], cfg)]
    bag = baggage_text(o.get("baggage"), cfg["passengers"]["adults"])
    if bag:
        bits.append(bag)
    return " · ".join(b for b in bits if b)
