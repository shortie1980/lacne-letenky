"""Akciové tipy a chybné ceny (error fares) z RSS kanála fly4free.com, vybrané ľuďmi.
Berieme len tie s odletom z tvojich letísk."""
import datetime as dt
import email.utils
import re
import xml.etree.ElementTree as ET

import requests

FEED_URL = "https://www.fly4free.com/feed/"
ORIGIN_NAMES = {
    "VIE": "Vienna", "BTS": "Bratislava", "BUD": "Budapest", "PRG": "Prague", "KSC": "Kosice",
    "BRQ": "Brno", "KRK": "Krakow", "KTW": "Katowice", "MUC": "Munich", "LJU": "Ljubljana",
    "GRZ": "Graz", "WAW": "Warsaw", "BER": "Berlin",
}


class TipsError(Exception):
    pass


def fetch(timeout=30):
    try:
        r = requests.get(FEED_URL, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 (lacne-letenky)"})
        r.raise_for_status()
        return r.text
    except requests.RequestException as e:
        raise TipsError(str(e)) from e


def parse(xml_text, origins, places=None, now=None, max_age_days=14):
    now = now or dt.datetime.now(dt.timezone.utc)
    names = {code: ORIGIN_NAMES.get(code) or (places.city(code)[0] if places and places.city(code) else code)
             for code in origins}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise TipsError(str(e)) from e
    tips = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        low = title.lower()
        if not re.search(r"flight|fare", low):
            continue                                      # len hotel bez letenky
        origin = next((code for code, name in names.items() if re.search(rf"\bfrom {re.escape(name.lower())}\b", low)), None)
        if not origin:
            continue
        try:
            published = email.utils.parsedate_to_datetime(item.findtext("pubDate"))
        except (TypeError, ValueError):
            continue
        if now - published > dt.timedelta(days=max_age_days):
            continue
        m = re.search(r"€\s?(\d[\d,.]*)", title)
        price = int(re.sub(r"[,.]", "", m[1])) if m else None
        dest = re.search(rf"from {re.escape(names[origin])} to (.+?)(?: for | from €|\s[€(]|$)", title, re.I)
        tips.append({
            "title": re.sub(r"\s+", " ", title),
            "link": item.findtext("link"),
            "published": published.astimezone(dt.timezone.utc).isoformat(),
            "origin": origin,
            "price": price,
            "destination": dest[1].strip(" ,!") if dest else None,
            "package": bool(re.search(r"\bstay\b|hotel|resort|night", low)),
            "id": item.findtext("guid") or item.findtext("link"),
        })
    tips.sort(key=lambda t: t["published"], reverse=True)
    return tips
