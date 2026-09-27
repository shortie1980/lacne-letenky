"""Regióny, krajiny a číselník letísk a miest (z Travelpayouts)."""
import re
import unicodedata
from dataclasses import dataclass, field

import requests

TP_CITIES_URL = "https://api.travelpayouts.com/data/en/cities.json"
TP_AIRPORTS_URL = "https://api.travelpayouts.com/data/en/airports.json"
TP_COUNTRIES_URL = "https://api.travelpayouts.com/data/en/countries.json"
TP_AIRLINES_URL = "https://api.travelpayouts.com/data/en/airlines.json"

REGION_COUNTRIES = {
    "europe": """AL AD AT BY BE BA BG HR CY CZ DK EE FI FR DE GR HU IS IE IT XK LV LI LT
        LU MT MD MC ME NL MK NO PL PT RO SM RS SK SI ES SE CH UA GB TR GI FO IM JE GG""",
    "middle_east": "AE QA OM BH KW SA JO IL LB IQ EG GE AM AZ",
    "central_asia": "AF KZ KG TJ TM UZ",
    "asia": "BD BT BN KH CN HK MO IN ID JP LA MY MV MN MM NP KR PK PH SG LK TW TH TL VN",
    "north_america": "US CA MX",
    "latam": """AR BO BR CL CO EC GY PY PE SR UY VE GF BZ CR SV GT HN NI PA CU DO HT JM PR
        BS BB TT AG DM GD KN LC VC AW CW SX BQ KY TC VG VI GP MQ BL MF AI MS BM""",
}
COUNTRY_TO_REGION = {cc: region for region, codes in REGION_COUNTRIES.items() for cc in codes.split()}

# Krajiny, ktoré sa prehľadávajú naživo v Kiwi (diaľkové lety, kde je cache nepresná)
EXPLORE_COUNTRIES = {
    "middle_east": "AE OM JO EG IL",
    "central_asia": "KZ UZ KG",
    "asia": "TH VN ID MY LK MV IN JP PH KH SG KR CN",
    "north_america": "US CA MX",
    "latam": "BR AR CU DO CO PE CR PA CL",
}


def region_of(country):
    return COUNTRY_TO_REGION.get(country, "other")


@dataclass
class Places:
    places: dict = field(default_factory=dict)          # IATA mesta/letiska -> (názov mesta, krajina)
    airport_city: dict = field(default_factory=dict)    # IATA letiska -> IATA mesta
    countries: dict = field(default_factory=dict)       # kód krajiny -> názov
    airlines: dict = field(default_factory=dict)        # IATA aerolínie -> názov

    def city(self, code):
        return self.places.get(code)

    def city_of_airport(self, airport):
        return self.airport_city.get(airport, airport)


def load_places():
    cities = requests.get(TP_CITIES_URL, timeout=60).json()
    airports = requests.get(TP_AIRPORTS_URL, timeout=60).json()
    countries = requests.get(TP_COUNTRIES_URL, timeout=60).json()
    try:
        airlines = requests.get(TP_AIRLINES_URL, timeout=60).json()
    except (requests.RequestException, ValueError):
        airlines = []
    p = Places()
    city_names = {c["code"]: c.get("name") or c["code"] for c in cities if c.get("code")}
    for a in airports:
        if a.get("code") and a.get("country_code"):
            city = a.get("city_code") or a["code"]
            p.airport_city[a["code"]] = city
            p.places[a["code"]] = (city_names.get(city) or a.get("name") or a["code"], a["country_code"])
    for c in cities:
        if c.get("code") and c.get("country_code"):
            p.places[c["code"]] = (c.get("name") or c["code"], c["country_code"])
    p.countries = {c["code"]: c.get("name") or c["code"] for c in countries if c.get("code")}
    p.airlines = {a["code"]: a.get("name") or a.get("name_translations", {}).get("en") or a["code"]
                  for a in airlines if a.get("code")}
    return p


def image_slug(city, country):
    """Odhad identifikátora fotky Kiwi (napr. „Chiang Mai“, TH → chiang-mai_th)."""
    s = unicodedata.normalize("NFKD", city).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return f"{s}_{country.lower()}" if s and country else None


def image_url(image_id):
    return f"https://images.kiwi.com/photos/600x600/{image_id}.jpg" if image_id else None
