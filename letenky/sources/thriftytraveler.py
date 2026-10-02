"""Lacné letenky z RSS kanála thriftytraveler.com - lacné lety z USA a celosvetovo."""
import datetime as dt
import email.utils
import re
import xml.etree.ElementTree as ET

import requests

FEED_URL = "https://www.thriftytraveler.com/feed/"
ORIGIN_CODES = {"VIE", "BTS", "BUD", "PRG", "KSC", "BRQ", "KRK", "KTW", "MUC", "LJU", "GRZ", "WAW", "BER", "VCE", "FCO", "CDG", "LHR", "AMS", "MAD", "BCN", "OMS"}


class ThriftyTravelerError(Exception):
    pass


def fetch(timeout=30):
    try:
        r = requests.get(FEED_URL, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 (lacne-letenky)"})
        r.raise_for_status()
        return r.text
    except requests.RequestException as e:
        raise ThriftyTravelerError(str(e)) from e


def parse(xml_text, origins, places=None, now=None, max_age_days=14):
    """Parse RSS feed from thriftytraveler.com - cheap flights from US and worldwide."""
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise ThriftyTravelerError(str(e)) from e

    tips = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = item.findtext("link") or ""
        low = title.lower()

        # Only include flight deals
        if not re.search(r"flight|fare|airfare|round-trip|round trip|one-way", low):
            continue

        # Extract price from title
        m = re.search(r"(?:from\s+)?(?:\$|€|£)(\d+)|(\d+)\s*(?:\$|€|£)", title)
        price = int(m[1] or m[2]) if m else None

        # Try to find origin airport code
        origin = None
        for code in origins:
            if re.search(rf"\b{code}\b", title, re.I):
                origin = code
                break

        try:
            published = email.utils.parsedate_to_datetime(item.findtext("pubDate"))
        except (TypeError, ValueError):
            published = dt.datetime.now(dt.timezone.utc)

        if now - published > dt.timedelta(days=max_age_days):
            continue

        tips.append({
            "title": re.sub(r"\s+", " ", title),
            "link": link,
            "published": published.astimezone(dt.timezone.utc).isoformat(),
            "origin": origin,
            "price": price,
            "destination": None,
            "package": False,
            "id": item.findtext("guid") or link,
        })

    tips.sort(key=lambda t: t["published"], reverse=True)
    return tips
