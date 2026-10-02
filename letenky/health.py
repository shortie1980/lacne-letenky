"""Stav zdrojov dát. Ak zdroj zlyhá viackrát po sebe, pošle sa upozornenie (a po obnovení ďalšie)."""
FAILS_BEFORE_ALERT = 3
SOURCES = {"travelpayouts": "Travelpayouts (ceny z cache)", "kiwi": "Kiwi.com (živé ceny)",
           "fly4free": "fly4free (akciové tipy)", "letenkyzababku": "Letenky za babku (akciové tipy)",
           "notify": "odosielanie upozornení"}


def update(state, source, ok, error=None, now=None):
    """Zapíše výsledok zdroja. Vráti 'down', 'recovered' alebo None."""
    h = state.setdefault("health", {}).setdefault(source, {"fails": 0, "alerted": False})
    if ok:
        event = "recovered" if h.get("alerted") else None
        h.update(fails=0, alerted=False, last_ok=now.isoformat() if now else h.get("last_ok"), last_error=None)
        return event
    h["fails"] = h.get("fails", 0) + 1
    h["last_error"] = (str(error) if error else "neznáma chyba")[:300]
    if h["fails"] >= FAILS_BEFORE_ALERT and not h.get("alerted"):
        h["alerted"] = True
        return "down"
    return None


def public(state):
    return {src: {"label": SOURCES.get(src, src), "ok": h.get("fails", 0) == 0, "fails": h.get("fails", 0),
                  "last_ok": h.get("last_ok"), "last_error": h.get("last_error")}
            for src, h in state.get("health", {}).items()}
