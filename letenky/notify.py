"""Odoslanie upozornení: Teams + e-mail (jeden Power Automate flow) a push na mobil cez ntfy."""
import os
import sys
from html import escape

import requests

from .geo import image_url
from .text import (baggage_text, buy_link, details_text, flag, fmt_date, freshness_text, google_flights_link,
                   nights_text, plural, price_text, transfers_text, why_text)

NTFY_URL = "https://ntfy.sh"


def headline(deals, tips):
    if deals:
        best = min(deals, key=lambda d: d["price_pp"])
        s = f"✈️ {best['origin']} → {best['city']} za {best['price_pp']} €"
        rest = len(deals) - 1
        if rest == 1:
            s += " a ďalšia lacná letenka"
        elif rest > 1:
            s += f" a {rest} {plural(rest, '', 'ďalšie lacné letenky', 'ďalších lacných leteniek')}"
        return s
    return f"💡 {len(tips)} {plural(len(tips), 'nový akciový tip', 'nové akciové tipy', 'nových akciových tipov')}"


# ─── Teams (Adaptive Card) ───────────────────────────────────────────────────

def build_card(deals, tips, cfg, airlines, dashboard_url):
    adults = cfg["passengers"]["adults"]
    body = [{"type": "TextBlock", "text": headline(deals, tips), "weight": "Bolder", "size": "Large", "wrap": True}]
    for d in deals:
        items = [
            {"type": "TextBlock", "wrap": True,
             "text": f"{flag(d['country'])} **{d['origin']} → {d['city']}** · **{price_text(d, adults)}**"},
            {"type": "TextBlock", "text": details_text(d, cfg, airlines), "isSubtle": True, "spacing": "None", "wrap": True},
        ]
        why = why_text(d)
        if why:
            items.append({"type": "TextBlock", "text": why, "color": "Good", "size": "Small", "spacing": "None", "wrap": True})
        items.append({"type": "TextBlock", "wrap": True, "spacing": "Small",
                      "text": f"**[🛒 Kúpiť na Kiwi.com]({buy_link(d)})** · [porovnať na Google Flights]({google_flights_link(d)})"})
        img = image_url(d.get("image_id"))
        column = {"type": "ColumnSet", "columns": [
            {"type": "Column", "width": "auto", "items": [{"type": "Image", "url": img, "size": "Medium"}]} if img else None,
            {"type": "Column", "width": "stretch", "items": items},
        ]}
        column["columns"] = [c for c in column["columns"] if c]
        body.append({"type": "Container", "separator": True, "spacing": "Medium",
                     "selectAction": {"type": "Action.OpenUrl", "url": buy_link(d)}, "items": [column]})
    if tips:
        body.append({"type": "TextBlock", "text": "💡 Akciové tipy (fly4free)", "weight": "Bolder", "separator": True, "wrap": True})
        for t in tips:
            body.append({"type": "TextBlock", "wrap": True, "spacing": "Small", "text": f"[{t['title']}]({t['link']})"})
    footer = "Upozornenia chodia len na živé ceny z Kiwi.com."
    if dashboard_url:
        footer += f" [Otvoriť aplikáciu]({dashboard_url})"
    body.append({"type": "TextBlock", "text": footer, "isSubtle": True, "size": "Small", "wrap": True})
    return {"type": "message", "attachments": [{
        "contentType": "application/vnd.microsoft.card.adaptive",
        "content": {"$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard",
                    "version": "1.4", "msteams": {"width": "Full"}, "body": body},
    }]}


# ─── E-mail ──────────────────────────────────────────────────────────────────

def build_email(deals, tips, cfg, airlines, dashboard_url):
    adults = cfg["passengers"]["adults"]
    rows = []
    for d in deals:
        img = image_url(d.get("image_id"))
        why = why_text(d)
        airline = airlines.get(d.get("airline"), d.get("airline", ""))
        bag = baggage_text(d.get("baggage"), adults)
        rows.append(f"""
<tr><td style="padding:0 0 14px">
 <table cellpadding="0" cellspacing="0" width="100%" style="border:1px solid #e7e5e4;border-radius:14px;overflow:hidden;background:#ffffff">
  <tr>
   {f'<td width="132" style="width:132px;vertical-align:top"><img src="{escape(img)}" width="132" height="132" alt="" style="display:block;width:132px;height:132px;object-fit:cover"></td>' if img else ''}
   <td style="padding:14px 16px;vertical-align:top">
    <div style="font-size:12px;color:#78716c;letter-spacing:.04em;text-transform:uppercase">{escape(d['origin'])} → {flag(d['country'])} {escape(d['country'])}</div>
    <div style="font-size:19px;font-weight:700;color:#1c1917;margin:2px 0 4px">{escape(d['city'])}</div>
    <div style="font-size:13px;color:#57534e">{fmt_date(d['departure'])} – {fmt_date(d['return'])} · {nights_text(d['days'])} · {transfers_text(d['transfers'])}{' · ' + escape(airline) if airline else ''}</div>
    {f'<div style="font-size:13px;color:#57534e;margin-top:2px">{escape(bag)}</div>' if bag else ''}
    {f'<div style="font-size:13px;color:#15803d;margin-top:6px;font-weight:600">{escape(why)}</div>' if why else ''}
   </td>
   <td style="padding:14px 16px;vertical-align:top;text-align:right;white-space:nowrap">
    <div style="font-size:24px;font-weight:800;color:#1c1917">{d['price_pp']} €</div>
    <div style="font-size:12px;color:#78716c;margin-bottom:10px">{'za osobu · spolu ' + str(d['price_total']) + ' €' if adults > 1 else 'spiatočná'}</div>
    <a href="{escape(buy_link(d))}" style="display:inline-block;background:#1c1917;color:#ffffff;text-decoration:none;padding:9px 16px;border-radius:999px;font-weight:600;font-size:14px">Kúpiť</a>
   </td>
  </tr>
 </table>
</td></tr>""")
    tip_html = ""
    if tips:
        items = "".join(f'<li style="margin:0 0 6px"><a href="{escape(t["link"])}" style="color:#1c1917">{escape(t["title"])}</a></li>'
                        for t in tips)
        tip_html = f"""<tr><td style="padding:6px 0 0"><div style="font-size:15px;font-weight:700;color:#1c1917;margin-bottom:6px">💡 Akciové tipy od fly4free</div>
<ul style="margin:0;padding-left:18px;font-size:14px;color:#44403c">{items}</ul></td></tr>"""
    app_link = (f'<a href="{escape(dashboard_url)}" style="color:#1c1917;font-weight:600">Otvoriť aplikáciu</a> · '
                if dashboard_url else "")
    html = f"""<div style="background:#f5f5f4;padding:24px 12px;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif">
<table cellpadding="0" cellspacing="0" width="100%" style="max-width:640px;margin:0 auto">
<tr><td style="padding:0 0 16px"><div style="font-size:13px;color:#78716c">Lacné letenky</div>
<div style="font-size:24px;font-weight:800;color:#1c1917">{escape(headline(deals, tips))}</div></td></tr>
{''.join(rows)}{tip_html}
<tr><td style="padding:16px 0 0;font-size:12px;color:#78716c">{app_link}Ceny sú živé z Kiwi.com v čase odoslania a môžu sa rýchlo meniť.</td></tr>
</table></div>"""
    return headline(deals, tips), html


def send_flow(payload, subject, html, webhook_url, email_to):
    payload = dict(payload, email_to=email_to or "", email_subject=subject, email_html=html)
    r = requests.post(webhook_url, json=payload, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"Teams webhook vrátil {r.status_code}: {r.text[:300]}")


# ─── ntfy (push na mobil) ────────────────────────────────────────────────────

def ntfy_post(topic, **fields):
    requests.post(NTFY_URL, json={"topic": topic, **fields}, timeout=20).raise_for_status()


def send_ntfy(deals, tips, topic, cfg, airlines, dashboard_url):
    adults = cfg["passengers"]["adults"]
    for d in deals[:5]:
        img = image_url(d.get("image_id"))
        fields = dict(
            title=f"✈️ {d['origin']} → {d['city']} za {d['price_pp']} €" + (" / os." if adults > 1 else ""),
            message="\n".join(x for x in [details_text(d, cfg, airlines), why_text(d)] if x),
            click=buy_link(d), tags=["airplane"], priority=4,
            actions=[{"action": "view", "label": "Kúpiť", "url": buy_link(d)},
                     {"action": "view", "label": "Google Flights", "url": google_flights_link(d)}],
        )
        if img:
            fields["attach"] = img
        ntfy_post(topic, **fields)
    rest = len(deals) - 5
    if rest > 0:
        ntfy_post(topic, title=f"✈️ A {rest} {plural(rest, 'ďalšia ponuka', 'ďalšie ponuky', 'ďalších ponúk')}",
                  message="Všetky nájdeš v aplikácii.", tags=["airplane"], **({"click": dashboard_url} if dashboard_url else {}))
    for t in tips[:3]:
        ntfy_post(topic, title="💡 Akciový tip", message=t["title"], click=t["link"], tags=["bulb"], priority=3)


# ─── Spoločné ────────────────────────────────────────────────────────────────

def channels(cfg):
    return {"webhook": os.environ.get("TEAMS_WEBHOOK_URL"),
            "email_to": os.environ.get("EMAIL_TO", ""),
            "topic": (cfg.get("notify", {}).get("ntfy_topic") or "").strip()}


def notify(deals, tips, cfg, airlines, dashboard_url):
    """Pošle ponuky a tipy všetkými nastavenými kanálmi. Vráti (úspech, chyba)."""
    ch, ok, errors = channels(cfg), False, []
    if ch["webhook"]:
        try:
            subject, html = build_email(deals, tips, cfg, airlines, dashboard_url)
            send_flow(build_card(deals, tips, cfg, airlines, dashboard_url), subject, html, ch["webhook"], ch["email_to"])
            ok = True
        except (requests.RequestException, RuntimeError) as e:
            errors.append(f"Teams/e-mail: {e}")
    if ch["topic"]:
        try:
            send_ntfy(deals, tips, ch["topic"], cfg, airlines, dashboard_url)
            ok = True
        except requests.RequestException as e:
            errors.append(f"ntfy: {e}")
    if not ch["webhook"] and not ch["topic"]:
        errors.append("nie je nastavený žiadny kanál")
    for e in errors:
        print(e, file=sys.stderr)
    return ok, "; ".join(errors) or None


def notify_health(source_label, event, error, cfg, dashboard_url):
    """Krátke upozornenie o výpadku alebo obnovení zdroja."""
    ch = channels(cfg)
    if event == "down":
        title, text = f"⚠️ {source_label} nefunguje", f"Posledné 3 pokusy zlyhali: {error or 'neznáma chyba'}"
    else:
        title, text = f"✅ {source_label} znova funguje", "Vyhľadávanie beží normálne."
    card = {"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": {
        "type": "AdaptiveCard", "version": "1.4", "body": [
            {"type": "TextBlock", "text": title, "weight": "Bolder", "size": "Medium", "wrap": True},
            {"type": "TextBlock", "text": text, "wrap": True, "isSubtle": True}]}}]}
    html = (f'<div style="font-family:Segoe UI,Arial,sans-serif"><h3 style="margin:0 0 6px">{escape(title)}</h3>'
            f'<p style="color:#555">{escape(text)}</p>'
            + (f'<p><a href="{escape(dashboard_url)}">Otvoriť aplikáciu</a></p>' if dashboard_url else "") + "</div>")
    try:
        if ch["webhook"]:
            send_flow(card, title, html, ch["webhook"], ch["email_to"])
        if ch["topic"]:
            ntfy_post(ch["topic"], title=title, message=text, tags=["warning" if event == "down" else "white_check_mark"])
    except (requests.RequestException, RuntimeError) as e:
        print(f"Upozornenie o stave zlyhalo: {e}", file=sys.stderr)
