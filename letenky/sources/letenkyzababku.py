"""Akciové letenky z RSS kanála letenkyzababku.sk - slovenský agregátor lacných letov."""
import datetime as dt
import email.utils
import re
import xml.etree.ElementTree as ET

import requests

FEED_URL = "https://www.letenkyzababku.sk/feed/"
ORIGIN_NAMES = {
    "VIE": "Vienna", "BTS": "Bratislava", "BUD": "Budapest", "PRG": "Prague", "KSC": "Kosice",
    "BRQ": "Brno", "KRK": "Krakow", "KTW": "Katowice", "MUC": "Munich", "LJU": "Ljubljana",
    "GRZ": "Graz", "WAW": "Warsaw", "BER": "Berlin", "VCE": "Venice", "FCO": "Rome",
    "CDG": "Paris", "LHR": "London", "AMS": "Amsterdam", "MAD": "Madrid", "BCN": "Barcelona",
    "OMS": "Ostrava",
}

# Slovak/Czech city name variants for matching
CITY_VARIANTS = {
    "Viedne": "VIE", "Vienna": "VIE",
    "Bratislave": "BTS", "Bratislava": "BTS",
    "Budapeš": "BUD", "Budapest": "BUD",
    "Prahy": "PRG", "Prague": "PRG", "Praha": "PRG",
    "Košice": "KSC", "Kosice": "KSC",
    "Brne": "BRQ", "Brna": "BRQ", "Brno": "BRQ",
    "Krakove": "KRK", "Krakow": "KRK",
    "Ostravy": "OMS", "Ostrava": "OMS",
}


class LetenkyzababkuError(Exception):
    pass


def fetch(timeout=30):
    try:
        r = requests.get(FEED_URL, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 (lacne-letenky)"})
        r.raise_for_status()
        return r.text
    except requests.RequestException as e:
        raise LetenkyzababkuError(str(e)) from e


def parse(xml_text, origins, places=None, now=None, max_age_days=30):
    """Parse RSS feed from letenkyzababku.sk"""
    now = now or dt.datetime.now(dt.timezone.utc)
    names = {code: ORIGIN_NAMES.get(code) or (places.city(code)[0] if places and places.city(code) else code)
             for code in origins}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise LetenkyzababkuError(str(e)) from e

    tips = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = item.findtext("link") or ""
        low = title.lower()

        # Skip items that are not travel deals
        if not re.search(r"letenk|flight|fare|zájaz|dovolen", low):
            continue

        # Extract origin from title using variants (e.g., "z Viedne", "z Brna", "z Ostravy")
        origin = None
        for city_name, code in CITY_VARIANTS.items():
            if code in origins:
                if re.search(rf"\bz\s+{re.escape(city_name)}\b|\bfrom\s+{re.escape(city_name)}\b", low, re.I):
                    origin = code
                    break

        if not origin:
            continue

        try:
            published = email.utils.parsedate_to_datetime(item.findtext("pubDate"))
        except (TypeError, ValueError):
            published = dt.datetime.now(dt.timezone.utc)

        if now - published > dt.timedelta(days=max_age_days):
            continue

        # Extract price from title (e.g., "475€", "319€")
        m = re.search(r"za\s+(\d+)\s*€|(\d+)\s*€", title)
        price = int(m[1] or m[2]) if m else None

        # Extract destination from title (e.g., "Kuala Lumpur z Viedne" or "EGYPT – kompletný zájazd z Ostravy")
        # Try pattern: "word z origin" or "word – ... z origin"
        dest_match = re.search(rf"^(.+?)\s*(?:–|z\s)", title, re.I)
        if dest_match:
            dest_text = dest_match[1].strip(" –").strip()
            # Clean up destination (remove emoji, extra text)
            destination = re.sub(r"\s*\d+\s*\*.*", "", dest_text).strip()
        else:
            destination = None

        # Check if it's a package deal (dovolenka/zájazd with hotel)
        is_package = bool(re.search(r"zájaz|dovolen|hotel|ubytova", low))

        tips.append({
            "title": re.sub(r"\s+", " ", title),
            "link": link,
            "published": published.astimezone(dt.timezone.utc).isoformat(),
            "origin": origin,
            "price": price,
            "destination": destination,
            "package": is_package,
            "id": item.findtext("guid") or link,
        })

    tips.sort(key=lambda t: t["published"], reverse=True)
    return tips
