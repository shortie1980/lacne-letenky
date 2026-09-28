import qrcode from "qrcode-generator";
import type { ComponentChildren } from "preact";
import { useMemo, useState } from "preact/hooks";
import { ORIGIN_OPTIONS, REGION_MAX_PRICE } from "../lib/config";
import { REGION_ICON, WEEKDAYS, WEEKDAYS_LONG, euro, flag, plural } from "../lib/format";
import {
  addExclude, addWatch, connect, connected, disconnect, draft, editDraft, lastLivePrice, places, repo, runNow,
} from "../store";
import type { Config, Region } from "../types";
import { Refresh } from "./icons";
import { SearchBox, Segmented, Stepper, Switch, type SearchItem } from "./ui";

function Section({ id, icon, title, lead, children }: { id: string; icon: string; title: string; lead?: ComponentChildren; children: ComponentChildren }) {
  return (
    <section class="set" id={id}>
      <h3><span aria-hidden="true">{icon}</span> {title}</h3>
      {lead ? <p class="lead">{lead}</p> : <div style={{ height: 14 }} />}
      {children}
    </section>
  );
}

function Row({ title, hint, children }: { title: string; hint?: string; children: ComponentChildren }) {
  return <div class="row"><div class="label"><b>{title}</b>{hint ? <small>{hint}</small> : null}</div>{children}</div>;
}

const PRESETS: [string, number[], number[]][] = [
  ["Kedykoľvek", [], []],
  ["Predĺžený víkend", [4, 5], [7, 1]],
  ["Víkend", [5, 6], [7]],
];

function Days({ value, onChange, label }: { value: number[]; onChange: (v: number[]) => void; label: string }) {
  return (
    <div class="days" role="group" aria-label={label}>
      {WEEKDAYS.map((w, i) => {
        const d = i + 1, on = value.includes(d);
        return <button type="button" title={WEEKDAYS_LONG[i]} aria-pressed={on} onClick={() => onChange(on ? value.filter((x) => x !== d) : [...value, d].sort())}>{w}</button>;
      })}
    </div>
  );
}

function RegionEditor({ k, r }: { k: string; r: Region }) {
  const set = (fn: (r: Region) => void) => editDraft((c) => fn(c.regions[k]));
  const max = REGION_MAX_PRICE[k] ?? 2000;
  const preset = PRESETS.find(([, o, b]) => JSON.stringify(o) === JSON.stringify(r.out_days) && JSON.stringify(b) === JSON.stringify(r.back_days));
  return (
    <div class={`region ${r.enabled ? "" : "off"}`}>
      <div class="region-head">
        <Switch checked={r.enabled} onChange={(v) => set((x) => (x.enabled = v))} />
        <span class="name">{REGION_ICON[k]} {r.label}</span>
        <span class="val">do {euro(r.max_price)}</span>
      </div>
      <input class="range" type="range" min={10} max={max} step={5} value={r.max_price} aria-label={`Limit ${r.label}`}
        onInput={(e) => set((x) => (x.max_price = +(e.target as HTMLInputElement).value))} />
      <div class="region-grid">
        <span>Pobyt</span>
        <span style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <Stepper value={r.min_days} min={1} max={r.max_days} onChange={(v) => set((x) => (x.min_days = v))} format={(v) => `${v} d`} />
          až
          <Stepper value={r.max_days} min={r.min_days} max={30} onChange={(v) => set((x) => (x.max_days = v))} format={(v) => `${v} d`} />
        </span>
        <span>Termín</span>
        <div class="presets">
          {PRESETS.map(([name, o, b]) => (
            <button type="button" class="chip" aria-pressed={preset?.[0] === name} onClick={() => set((x) => { x.out_days = o; x.back_days = b; })}>{name}</button>
          ))}
          {!preset ? <span class="chip" aria-pressed="true">Vlastné</span> : null}
        </div>
        <span>Odlet v</span><Days label="Dni odletu" value={r.out_days} onChange={(v) => set((x) => (x.out_days = v))} />
        <span>Návrat v</span><Days label="Dni návratu" value={r.back_days} onChange={(v) => set((x) => (x.back_days = v))} />
      </div>
    </div>
  );
}

function Connection() {
  const [repoIn, setRepo] = useState(repo.value);
  const [tok, setTok] = useState("");
  const [busy, setBusy] = useState(false);
  if (connected.value) {
    return (
      <Section id="connection" icon="🔗" title="Pripojenie" lead={<>Aplikácia je pripojená k <b>{repo.value}</b> a môže ukladať nastavenia.</>}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button class="btn" onClick={runNow}><Refresh /> Spustiť vyhľadávanie teraz</button>
          <button class="btn ghost" onClick={disconnect}>Odpojiť toto zariadenie</button>
        </div>
      </Section>
    );
  }
  return (
    <Section id="connection" icon="🔑" title="Pripojenie ku GitHubu" lead="Aby mohla aplikácia ukladať nastavenia, potrebuje prístupový kľúč. Uloží sa len v tomto zariadení.">
      <div class="callout">
        <ol>
          <li>Otvor <a href="https://github.com/settings/personal-access-tokens/new" target="_blank" rel="noopener">GitHub → nový Fine-grained token</a>.</li>
          <li>Repository access → <b>Only select repositories</b> → vyber tento repozitár.</li>
          <li>Permissions: <b>Contents</b> a <b>Actions</b> → <b>Read and write</b>.</li>
          <li>Generate token, skopíruj ho a vlož sem.</li>
        </ol>
      </div>
      <div style={{ display: "grid", gap: 10, marginTop: 14 }}>
        <div class="field"><label for="repo">Repozitár</label><input id="repo" class="input" value={repoIn} placeholder="meno/lacne-letenky" onInput={(e) => setRepo((e.target as HTMLInputElement).value)} /></div>
        <div class="field"><label for="tok">Token</label><input id="tok" class="input" type="password" autoComplete="off" value={tok} placeholder="github_pat_…" onInput={(e) => setTok((e.target as HTMLInputElement).value)} /></div>
        <div><button class="btn cta" style={{ flex: "none" }} disabled={busy || !tok || !/^[\w.-]+\/[\w.-]+$/.test(repoIn.trim())}
          onClick={async () => { setBusy(true); await connect(repoIn.trim().replace(/^https:\/\/github\.com\//, ""), tok.trim()); setBusy(false); }}>
          {busy ? "Pripájam…" : "Pripojiť"}</button></div>
      </div>
    </Section>
  );
}

function Ntfy({ c }: { c: Config }) {
  const topic = c.notify.ntfy_topic;
  const svg = useMemo(() => {
    if (!topic) return "";
    const q = qrcode(0, "M"); q.addData(`https://ntfy.sh/${topic}`); q.make();
    return q.createSvgTag({ cellSize: 4, margin: 0, scalable: true });
  }, [topic]);
  const generate = () => {
    const alphabet = "abcdefghijkmnpqrstuvwxyz23456789";
    const rnd = Array.from(crypto.getRandomValues(new Uint8Array(10)), (b) => alphabet[b % alphabet.length]).join("");
    editDraft((x) => (x.notify.ntfy_topic = `letenky-${rnd}`));
  };
  if (!topic) {
    return (
      <div class="callout">
        <b>📲 Push notifikácie na mobil</b>
        Najrýchlejší spôsob, ako sa dozvieš o lacnej letenke: pípne ti na mobile s tlačidlom Kúpiť. Zadarmo cez aplikáciu ntfy.
        <div><button class="btn cta" style={{ flex: "none", marginTop: 6 }} onClick={generate}>Zapnúť push notifikácie</button></div>
      </div>
    );
  }
  return (
    <div class="ntfy">
      <div class="qr" dangerouslySetInnerHTML={{ __html: svg }} />
      <div class="callout good">
        <b>📲 Push je zapnutý – ešte sa prihlás na mobile</b>
        <ol>
          <li>Nainštaluj si <b>ntfy</b> (<a href="https://apps.apple.com/app/ntfy/id1625396347" target="_blank" rel="noopener">iPhone</a> · <a href="https://play.google.com/store/apps/details?id=io.heckel.ntfy" target="_blank" rel="noopener">Android</a>).</li>
          <li>Naskenuj QR kód fotoaparátom, alebo v appke daj <b>+</b> a zadaj <code>{topic}</code>.</li>
          <li>Ulož nastavenia. Hotovo.</li>
        </ol>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 4 }}>
          <a class="btn small" href={`ntfy://ntfy.sh/${topic}`}>Otvoriť v ntfy</a>
          <button class="btn small ghost" onClick={generate}>Nová téma</button>
          <button class="btn small ghost" onClick={() => editDraft((x) => (x.notify.ntfy_topic = ""))}>Vypnúť</button>
        </div>
      </div>
    </div>
  );
}

export function SettingsView() {
  const c = draft.value;
  const p = places.value;
  const destItems = useMemo<SearchItem[]>(() => [
    ...p.cities.map(([code, name, country]) => ({ code, name, country, kind: "city" as const })),
    ...p.countries.map(([code, name]) => ({ code, name, country: code, kind: "country" as const })),
  ], [p]);
  const airlineItems = useMemo<SearchItem[]>(() => p.airlines.map(([code, name]) => ({ code, name, country: "", kind: "airline" as const, hint: code })), [p]);
  const placeName = (code: string) => {
    const city = p.cities.find((x) => x[0] === code);
    if (city) return { name: city[1], country: city[2] };
    const k = p.countries.find((x) => x[0] === code);
    return { name: k?.[1] ?? code, country: k ? code : "" };
  };
  if (!c) return <div class="empty" style={{ marginTop: 30 }}><div class="big">Načítavam nastavenia…</div></div>;
  const set = editDraft;
  const origins = [...ORIGIN_OPTIONS, ...c.origins.filter((o) => !ORIGIN_OPTIONS.some((x) => x[0] === o)).map((o) => [o, o] as [string, string])];
  const toc: [string, string][] = [
    ["connection", "Pripojenie"], ["origins", "Odlety"], ["travellers", "Cestujúci"], ["regions", "Limity a termíny"],
    ["watch", "Sledované"], ["excluded", "Nezaujíma ma"], ["flights", "Lety"], ["notify", "Upozornenia"], ["advanced", "Pokročilé"],
  ];
  return (
    <>
      <div class="section-head" style={{ marginTop: 26 }}><h2>Nastavenia</h2><p>Zmeny sa uložia na GitHub a hneď sa spustí nové vyhľadávanie.</p></div>
      <div class="settings">
        <nav class="toc" aria-label="Sekcie nastavení">{toc.map(([id, t]) => <a href={`#${id}`} onClick={(e) => { e.preventDefault(); document.getElementById(id)?.scrollIntoView({ behavior: "smooth" }); }}>{t}</a>)}</nav>
        <div class="set-col">
          <Connection />

          <Section id="origins" icon="🛫" title="Odkiaľ lietam" lead="Letiská, z ktorých ti hľadám letenky.">
            <div class="chips" style={{ flexWrap: "wrap", margin: 0, padding: 0 }}>
              {origins.map(([code, name]) => {
                const on = c.origins.includes(code);
                return <button class="chip" aria-pressed={on} onClick={() => set((x) => {
                  if (on && x.origins.length > 1) x.origins = x.origins.filter((o) => o !== code); else if (!on) x.origins.push(code);
                })}>{name} <span class="n">{code}</span></button>;
              })}
            </div>
          </Section>

          <Section id="travellers" icon="🧳" title="Cestujúci a batožina" lead="Ceny a limity sú vždy za osobu. Kufor sa započíta do ceny už pri hľadaní.">
            <Row title="Dospelí" hint="Ceny sa zobrazia za osobu aj spolu"><Stepper value={c.passengers.adults} min={1} max={6} onChange={(v) => set((x) => (x.passengers.adults = v))} /></Row>
            <Row title="Batožina" hint="S kufrom nájdem len lety, kde je kufor v cene alebo sa dá dokúpiť">
              <Segmented value={c.passengers.hold_bags} options={[[0, "Len príručná"], [1, "S kufrom"]]} onChange={(v) => set((x) => (x.passengers.hold_bags = v))} />
            </Row>
          </Section>

          <Section id="regions" icon="💶" title="Limity a termíny podľa regiónu" lead="Upozorním ťa, keď letenka stojí najviac toľko. Pri Európe môžeš napr. nastaviť len predĺžené víkendy.">
            {Object.entries(c.regions).map(([k, r]) => <RegionEditor k={k} r={r} />)}
            <div class="row" style={{ borderTop: 0, marginTop: 12 }}>
              <div class="label"><b>📉 Chytré upozornenia</b><small>Upozorním ťa aj vtedy, keď je cena výrazne pod bežnou úrovňou – aj mierne nad limitom.</small></div>
              <Switch checked={c.smart.enabled} onChange={(v) => set((x) => (x.smart.enabled = v))} />
            </div>
            {c.smart.enabled && (
              <Row title={`Aspoň o ${c.smart.drop_pct} % lacnejšie ako bežne`} hint={`A najviac o ${c.smart.max_over_limit_pct} % nad limitom. Bežná cena sa počíta z posledných dní.`}>
                <Stepper value={c.smart.drop_pct} min={10} max={60} step={5} onChange={(v) => set((x) => (x.smart.drop_pct = v))} format={(v) => `${v} %`} />
              </Row>
            )}
            <Row title={`🔥 Výnimočná cena od −${c.smart.exceptional_pct} %`} hint="Takáto ponuka príde e-mailom s červenou hlavičkou a vysokou prioritou">
              <Stepper value={c.smart.exceptional_pct} min={20} max={70} step={5} onChange={(v) => set((x) => (x.smart.exceptional_pct = v))} format={(v) => `${v} %`} />
            </Row>
            <Row title={`…a zároveň ušetríš aspoň ${euro(c.smart.exceptional_min_saving)} na osobu`} hint="Aby sa za výnimočné nepovažovali bežné výpredaje lacných európskych liniek">
              <Stepper value={c.smart.exceptional_min_saving} min={0} max={500} step={25} onChange={(v) => set((x) => (x.smart.exceptional_min_saving = v))} format={(v) => euro(v)} />
            </Row>
          </Section>

          <Section id="watch" icon="🔔" title="Sledované destinácie" lead="Konkrétne mestá alebo krajiny s vlastným limitom. Hľadám ich naživo na celé obdobie.">
            <div>
              {c.watchlist.map((w, i) => {
                const pl = placeName(w.code), now = lastLivePrice(w.code);
                return (
                  <div class="watch">
                    <span class="flag">{flag(pl.country)}</span>
                    <span class="nm">{w.name || pl.name}<small>{w.code}{now ? ` · teraz od ${euro(now)}` : ""}</small></span>
                    <Stepper value={w.max_price} min={10} max={5000} step={10} onChange={(v) => set((x) => (x.watchlist[i].max_price = v))} format={(v) => euro(v)} />
                    <button class="btn icon ghost" aria-label="Odstrániť" onClick={() => set((x) => x.watchlist.splice(i, 1))}>✕</button>
                  </div>
                );
              })}
            </div>
            <div style={{ marginTop: 12 }}><SearchBox items={destItems} placeholder="🔍 Pridať mesto alebo krajinu (napr. Tokyo, Bali, Japan)" onPick={(i) => addWatch(i.code, i.name)} /></div>
          </Section>

          <Section id="excluded" icon="🚫" title="Nezaujíma ma" lead="Tieto mestá a krajiny sa nebudú zobrazovať ani posielať.">
            <div class="xchips">
              {c.excluded.length ? c.excluded.map((code) => {
                const pl = placeName(code);
                return <span class="xchip">{flag(pl.country)} {pl.name}<button aria-label={`Odstrániť ${pl.name}`} onClick={() => set((x) => (x.excluded = x.excluded.filter((e) => e !== code)))}>✕</button></span>;
              }) : <span class="note-line" style={{ margin: 0 }}>Nič nie je vylúčené.</span>}
            </div>
            <SearchBox items={destItems} placeholder="🔍 Vylúčiť mesto alebo krajinu" onPick={(i) => addExclude(i.code, i.name)} />
          </Section>

          <Section id="flights" icon="✈️" title="Lety" lead="Filtre, ktoré platia pre všetky ponuky.">
            <Row title="Najviac prestupov" hint="Jedným smerom">
              <Segmented value={c.max_transfers} options={[[0, "Priame"], [1, "1"], [2, "2"], [3, "3"]]} onChange={(v) => set((x) => (x.max_transfers = v))} />
            </Row>
            <Row title="Odlet najskôr o" hint="Žiadne ranné lety pred touto hodinou">
              <Stepper value={c.filters.earliest_departure_hour} min={0} max={c.filters.latest_departure_hour} onChange={(v) => set((x) => (x.filters.earliest_departure_hour = v))} format={(v) => `${v}:00`} />
            </Row>
            <Row title="Odlet najneskôr o">
              <Stepper value={c.filters.latest_departure_hour} min={c.filters.earliest_departure_hour} max={23} onChange={(v) => set((x) => (x.filters.latest_departure_hour = v))} format={(v) => `${v}:59`} />
            </Row>
            <div class="row" style={{ display: "block" }}>
              <div class="label" style={{ marginBottom: 10 }}><b>Vylúčené aerolínie</b></div>
              <div class="xchips">
                {c.filters.exclude_airlines.map((a) => (
                  <span class="xchip">✈ {p.airlines.find((x) => x[0] === a)?.[1] ?? a}<button aria-label="Odstrániť" onClick={() => set((x) => (x.filters.exclude_airlines = x.filters.exclude_airlines.filter((e) => e !== a)))}>✕</button></span>
                ))}
              </div>
              <SearchBox items={airlineItems} placeholder="🔍 Pridať aerolíniu (napr. Wizz Air, Ryanair)" onPick={(i) => set((x) => { if (!x.filters.exclude_airlines.includes(i.code)) x.filters.exclude_airlines.push(i.code); })} />
            </div>
          </Section>

          <Section id="notify" icon="📣" title="Upozornenia" lead="Teams a e-mail sú nastavené cez Power Automate. Upozornenia chodia len na živé ceny z Kiwi.com.">
            <Ntfy c={c} />
            <div style={{ marginTop: 14 }}>
              <Row title="💡 Akciové tipy z fly4free" hint="Výpredaje a chybné ceny, ktoré našli ľudia"><Switch checked={c.tips.enabled} onChange={(v) => set((x) => (x.tips.enabled = v))} /></Row>
              <Row title="⚠️ Upozorniť, keď niečo prestane fungovať" hint="Keď zdroj cien 3× po sebe zlyhá"><Switch checked={c.notify.health_alerts} onChange={(v) => set((x) => (x.notify.health_alerts = v))} /></Row>
              <Row title="Rovnakú trasu znova po" hint={`Skôr, ak zlacnie aspoň o ${c.renotify_drop_pct} %`}>
                <Stepper value={c.renotify_days} min={1} max={60} onChange={(v) => set((x) => (x.renotify_days = v))} format={(v) => `${v} ${plural(v, "dni", "dňoch", "dňoch")}`} />
              </Row>
            </div>
          </Section>

          <Section id="advanced" icon="⚙️" title="Pokročilé">
            <Row title="Hľadať odlety na" hint="Koľko mesiacov dopredu">
              <Segmented value={c.months_ahead} options={[[2, "2 mes."], [3, "3"], [6, "6"], [9, "9"], [12, "12"]]} onChange={(v) => set((x) => (x.months_ahead = v))} />
            </Row>
            <Row title="Ignorovať ceny z cache staršie ako" hint="Kratšie = presnejšie, ale menej kandidátov">
              <Stepper value={c.max_price_age_days} min={1} max={14} onChange={(v) => set((x) => (x.max_price_age_days = v))} format={(v) => `${v} d`} />
            </Row>
            <Row title="Najviac ponúk v jednom upozornení" hint={`Z toho najviac ${c.max_alerts_per_region} z jedného regiónu`}>
              <Stepper value={c.max_alerts_per_run} min={1} max={30} onChange={(v) => set((x) => (x.max_alerts_per_run = v))} />
            </Row>
          </Section>
        </div>
      </div>
    </>
  );
}
