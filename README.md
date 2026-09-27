# ✈️ Lacné letenky

Osobná aplikácia, ktorá každých 30 minút hľadá lacné spiatočné letenky z tvojich letísk
(predvolene VIE, BTS, BUD, PRG) a hneď ťa upozorní: **push na mobil** (ntfy), **Teams** a **e-mail**.
Upozornenia chodia len na **živé ceny overené na Kiwi.com**, s odkazom priamo na rezerváciu.

**Aplikácia:** https://shortie1980.github.io/lacne-letenky/ (dá sa pridať na plochu mobilu)

## Čo vie

- **Živé ceny.** Kandidátov z cache (Travelpayouts) overí naživo cez Kiwi.com (±2 dni okolo termínu),
  sledované destinácie a hlavné krajiny v Ázii a Amerike prehľadáva naživo na celé obdobie.
- **Chytré upozornenia.** Okrem pevného limitu upozorní aj vtedy, keď je cena výrazne pod bežnou úrovňou
  (napr. −25 % oproti mediánu posledných dní), aj keď je mierne nad limitom.
- **Cestujúci a batožina.** Počet dospelých, kufor v cene. Ceny a limity sú vždy za osobu.
- **Termíny.** Dĺžka pobytu podľa regiónu, dni odletu a návratu (napr. predĺžené víkendy), časy odletov,
  vylúčené aerolínie.
- **Akciové tipy a chybné ceny** z fly4free.com s odletom z tvojich letísk.
- **Kontrola zdrojov.** Ak Kiwi, Travelpayouts alebo fly4free 3× po sebe zlyhá, príde upozornenie.
- **Webová aplikácia.** Ponuky s fotkami, detail letu (prestupy, časy, batožina, graf ceny),
  prehľad cien podľa regiónov a všetky nastavenia. Po uložení sa hneď spustí nové vyhľadávanie.

## Ako to funguje

```
GitHub Actions (každých 30 min, zadarmo)
  ├─ testy (pytest) → zostavenie webu (TypeScript, Vite)
  └─ watcher.py
       ├─ Travelpayouts (cache) ──────── kandidáti po celom svete
       ├─ Kiwi.com MCP (živé ceny) ───── overenie · sledované destinácie · krajiny v Ázii a Amerike
       ├─ fly4free.com (RSS) ─────────── akciové tipy a chybné ceny
       ├─► ntfy push · Teams · e-mail
       └─► dáta pre web ──► GitHub Pages
Aplikácia ── uloží config.json cez GitHub API ──► spustí nové vyhľadávanie
```

| Priečinok | Obsah |
|---|---|
| `letenky/` | Python: pravidlá, zdroje (`sources/`), upozornenia, dáta pre web, stav zdrojov |
| `web/` | Webová aplikácia: TypeScript + Preact + Vite |
| `tests/` | Testy (pytest) s ukážkovými odpoveďami Kiwi a fly4free |
| `config.json` | Nastavenia (upravuje ich aplikácia) |

## Nastavenie

Secrets v repozitári (**Settings → Secrets and variables → Actions**): `TRAVELPAYOUTS_TOKEN`,
`TEAMS_WEBHOOK_URL` (Power Automate flow „Post to a channel when a webhook request is received“
s pridaným krokom *Send an email (V2)*: Subject `triggerBody()?['email_subject']`, Body `triggerBody()?['email_html']`)
a `EMAIL_TO`. GitHub Pages: **Settings → Pages → Source: GitHub Actions**.

V aplikácii: **Nastavenia → Pripojenie** (fine-grained token s právami Contents a Actions: Read and write,
len pre tento repozitár) a **Nastavenia → Upozornenia → Zapnúť push notifikácie**.

## Vývoj

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q                       # testy
TRAVELPAYOUTS_TOKEN=... python watcher.py --dry-run   # beh bez odosielania, dáta do site/
python watcher.py --test-notify           # skúšobné upozornenie

cd web && npm install && npm run build    # web do web/dist (kontrola typov + zostavenie)
cp -R web/dist/. site/ && python -m http.server 8765  # náhľad na http://localhost:8765/site/
```

## Dobré vedieť
- Ceny z cache pri diaľkových letoch často nesedia (napr. Krabi 214 € v cache, 615 € naživo),
  preto upozornenia chodia len na živé ceny.
- Kiwi MCP (`mcp.kiwi.com`) je verejná služba bez kľúča; aplikácia ju používa striedmo (~30 vyhľadávaní za beh).
- Ak repozitár 60 dní nikto neupraví, GitHub môže plánované behy pozastaviť – obnovíš ich v záložke Actions.
