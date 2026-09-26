# ✈️ Lacné letenky

Aplikácia, ktorá každých 30 minút prehľadá lacné spiatočné letenky z tvojich letísk (predvolene VIE, BTS, BUD, PRG)
do celého sveta. Keď nájde cenu pod tvojím limitom, pošle ti upozornenie:

- **push notifikáciu na mobil** cez aplikáciu ntfy (najrýchlejšie),
- **správu do Teams** a **e-mail** cez Power Automate.

Pri každej ponuke je tlačidlo **Kúpiť**, ktoré otvorí presne ten let na Aviasales. Tam si vyberieš predajcu a zaplatíš.

**Webová aplikácia** (`https://<tvoje-meno>.github.io/lacne-letenky/`) funguje aj na mobile:
- **Ponuky:** všetky aktuálne ponuky pod limitom, filtre podľa regiónu a letiska, graf vývoja ceny.
- **Ceny teraz:** najlacnejšie destinácie v každom regióne aj nad limitom, aby si videl, koľko letenky stoja.
- **Nastavenia:** letiská, limity podľa regiónu s posuvníkmi, sledované destinácie s vlastným limitom,
  vylúčené destinácie, počet prestupov a notifikácie. Po uložení sa hneď spustí nové vyhľadávanie.

## Ako to funguje

```
GitHub Actions (každých 30 min, zadarmo)
  └─ watcher.py ── Travelpayouts API (ceny) ──► nájde ponuky pod limitom
        ├─► ntfy push · Teams · e-mail
        └─► dáta pre web ──► GitHub Pages (aplikácia)
Aplikácia ── uloží config.json cez GitHub API ──► spustí nové vyhľadávanie
```

## Nastavenie (asi 20 minút, jednorazovo)

### 1. Token pre Travelpayouts
Zaregistruj sa na https://www.travelpayouts.com, otvor **Profile → API token** a skopíruj token.

### 2. Teams + e-mail cez Power Automate
1. V Teams si vytvor kanál, napr. **Letenky**.
2. Pri kanáli klikni na **⋯ → Workflows** a vyber šablónu **„Post to a channel when a webhook request is received“**.
   Dokonči sprievodcu.
3. Otvor https://make.powerautomate.com → **My flows** a vyber flow, ktorý sa práve vytvoril → **Edit**.
4. Pod posledný krok pridaj akciu **Office 365 Outlook → Send an email (V2)** a vyplň:
   - **To:** klikni na *fx* a zadaj `triggerBody()?['email_to']`
   - **Subject:** `triggerBody()?['email_subject']`
   - **Body:** prepni na zobrazenie kódu `</>` a vlož `triggerBody()?['email_html']`
5. Ulož flow. V prvom kroku (trigger) skopíruj **HTTP URL**.

### 3. GitHub repozitár
1. Na https://github.com/new vytvor repozitár `lacne-letenky` ako **Public**.
   GitHub Pages je pre súkromné repozitáre zadarmo len v platenom pláne. V repozitári nie je nič citlivé:
   tokeny, webhook aj e-mail sú v Secrets.
2. Nahraj doň obsah tohto priečinka.
3. **Settings → Secrets and variables → Actions → New repository secret:**
   - `TRAVELPAYOUTS_TOKEN`: token z kroku 1
   - `TEAMS_WEBHOOK_URL`: URL z kroku 2
   - `EMAIL_TO`: tvoj e-mail
   - `SERPAPI_KEY`: *(voliteľné)* slúži na overenie cien cez Google Flights
4. **Settings → Pages → Source: GitHub Actions**
5. **Actions → Lacné letenky → Run workflow**. Po asi 2 minútach je aplikácia na `https://<meno>.github.io/lacne-letenky/`.

### 4. Pripojenie aplikácie (aby mohla ukladať nastavenia)
V aplikácii otvor **Nastavenia → Pripojenie** a postupuj podľa návodu. Vytvoríš fine-grained token
iba pre tento repozitár s oprávneniami **Contents** a **Actions: Read and write**.
Token sa uloží len v prehliadači na danom zariadení.

### 5. Push notifikácie na mobil (odporúčané)
V aplikácii otvor **Nastavenia → Upozornenia → Vygenerovať** a ulož. Potom si nainštaluj aplikáciu **ntfy**
a prihlás sa na odber zobrazenej témy.

## Lokálne skúšanie

```bash
pip install -r requirements.txt
export TRAVELPAYOUTS_TOKEN=...
python watcher.py --dry-run          # nájde ponuky, vygeneruje web do site/, nič neposiela
python -m http.server 8765           # web potom beží na http://localhost:8765/site/
python watcher.py --test-notify      # pošle skúšobné upozornenie (potrebuje TEAMS_WEBHOOK_URL alebo ntfy tému)
```

## Dobré vedieť
- Ceny pochádzajú z **cache vyhľadávaní** na Aviasales. Väčšinou sedia a líšia sa o pár eur,
  no výpredaje môžu zmiznúť aj za pár hodín.
- Aviasales zobrazuje ceny predvolene v dolároch. Menu si prepneš vpravo hore a stránka si ju zapamätá.
- Tú istú trasu aplikácia pošle znova až po nastavenom počte dní, alebo skôr, ak výrazne zlacnie.
- Ak repozitár 60 dní nikto neupraví, GitHub môže plánované behy pozastaviť. Príde ti o tom e-mail
  a obnovíš ich jedným klikom v záložke Actions.
