// Ručné vyhľadávanie letov na konkrétne dátumy (živé ceny z Kiwi.com)
import { useMemo, useRef, useState } from "preact/hooks";
import { ORIGIN_OPTIONS } from "../lib/config";
import { flag, plural } from "../lib/format";
import { storage } from "../lib/github";
import { kiwiSearch, toOffer, type SearchParams } from "../lib/kiwi";
import { draft, history, places } from "../store";
import type { Offer } from "../types";
import { DealCard } from "./Deal";
import { Arrow, Close } from "./icons";
import { SearchBox, Segmented, Stepper, type SearchItem } from "./ui";

interface Dest { code: string; name: string; country: string; kind: "city" | "country" | "anywhere" }
const ANYWHERE: Dest = { code: "anywhere", name: "Kamkoľvek", country: "", kind: "anywhere" };
const addDays = (iso: string, n: number) => { const d = new Date(iso + "T12:00:00"); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10); };
const today = () => new Date().toISOString().slice(0, 10);

interface Form { from: string[]; dest: Dest; oneWay: boolean; dep: string; depFlex: number; ret: string; retFlex: number; adults: number; bags: number; stops: number }

function initialForm(): Form {
  try { const f = JSON.parse(storage.get("search") || ""); if (f?.dep >= today()) return f; } catch { /* nič uložené */ }
  const cfg = draft.value;
  const dep = addDays(today(), 30);
  return { from: cfg?.origins ?? ["VIE", "BTS", "BUD", "PRG"], dest: ANYWHERE, oneWay: false, dep, depFlex: 0, ret: addDays(dep, 7), retFlex: 0,
    adults: cfg?.passengers.adults ?? 1, bags: cfg?.passengers.hold_bags ?? 0, stops: 2 };
}

export function SearchView() {
  const [f, setF] = useState<Form>(initialForm);
  const [results, setResults] = useState<Offer[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"price" | "duration">("price");
  const abort = useRef<AbortController | null>(null);
  const set = (patch: Partial<Form>) => setF((x) => ({ ...x, ...patch }));
  const p = places.value;
  const items = useMemo<SearchItem[]>(() => [
    ...p.cities.map(([code, name, country]) => ({ code, name, country, kind: "city" as const })),
    ...p.countries.map(([code, name]) => ({ code, name, country: code, kind: "country" as const })),
  ], [p]);
  const origins = [...ORIGIN_OPTIONS, ...f.from.filter((o) => !ORIGIN_OPTIONS.some((x) => x[0] === o)).map((o) => [o, o] as [string, string])];

  const run = async (e?: Event) => {
    e?.preventDefault();
    if (!f.from.length) return setError("Vyber aspoň jedno letisko odletu.");
    if (!f.oneWay && f.ret < f.dep) return setError("Návrat musí byť po odlete.");
    abort.current?.abort();
    const ctl = new AbortController(); abort.current = ctl;
    setBusy(true); setError(null); storage.set("search", JSON.stringify(f));
    const params: SearchParams = {
      from: f.from, to: f.dest.kind === "country" ? f.dest.name : f.dest.code, departure: f.dep, departureFlex: f.depFlex,
      returnDate: f.oneWay ? null : f.ret, returnFlex: f.retFlex, adults: f.adults, holdBags: f.bags, maxStops: f.stops >= 3 ? null : f.stops,
    };
    try {
      const its = await kiwiSearch(params, ctl.signal);
      setResults(its.map((it) => toOffer(it, p, history.value, f.adults)));
    } catch (err) {
      if ((err as Error).name !== "AbortError") setError(`Vyhľadávanie zlyhalo: ${(err as Error).message}. Skús to o chvíľu znova.`);
    } finally { if (abort.current === ctl) setBusy(false); }
  };

  const sorted = (results ?? []).slice().sort((a, b) => sortBy === "price" ? a.price_pp - b.price_pp : (a.duration ?? 0) - (b.duration ?? 0));
  const flexOpts: [number, string][] = [[0, "presne"], [1, "±1 deň"], [2, "±2 dni"], [3, "±3 dni"]];
  return (
    <>
      <div class="section-head" style={{ marginTop: 26 }}>
        <h2>Hľadať let</h2>
        <p>Konkrétne dátumy, živé ceny z Kiwi.com s odkazom na rezerváciu</p>
      </div>
      <form class="search-panel" onSubmit={run}>
        <div class="sp-row">
          <div class="sp-field sp-wide">
            <label>Odkiaľ</label>
            <div class="chips" style={{ flexWrap: "wrap", margin: 0, padding: 0 }}>
              {origins.map(([code, name]) => {
                const on = f.from.includes(code);
                return <button type="button" class="chip" aria-pressed={on} onClick={() => set({ from: on ? f.from.filter((o) => o !== code) : [...f.from, code] })}>{name} <span class="n">{code}</span></button>;
              })}
            </div>
          </div>
        </div>
        <div class="sp-row">
          <div class="sp-field sp-wide">
            <label>Kam</label>
            {f.dest.kind === "anywhere" && <div class="sp-dest"><span>🌍 Kamkoľvek</span><span class="note-line" style={{ margin: 0 }}>alebo vyhľadaj mesto či krajinu:</span></div>}
            {f.dest.kind !== "anywhere" && <div class="sp-dest"><span class="xchip">{flag(f.dest.country)} {f.dest.name}{f.dest.kind === "country" ? " (celá krajina)" : ""}<button type="button" aria-label="Zrušiť" onClick={() => set({ dest: ANYWHERE })}><Close /></button></span></div>}
            <SearchBox items={items} placeholder="🔍 Mesto alebo krajina (napr. Bangkok, Japan, Londýn)" onPick={(i) => set({ dest: { code: i.code, name: i.name, country: i.country, kind: i.kind === "country" ? "country" : "city" } })} />
          </div>
        </div>
        <div class="sp-row sp-dates">
          <div class="sp-field">
            <label for="dep">Odlet</label>
            <input id="dep" class="input" type="date" min={today()} value={f.dep} onInput={(e) => { const v = (e.target as HTMLInputElement).value; set({ dep: v, ret: f.ret < v ? addDays(v, 7) : f.ret }); }} />
            <Segmented value={f.depFlex} options={flexOpts} onChange={(v) => set({ depFlex: v })} />
          </div>
          <div class="sp-field">
            <label for="ret">Návrat <button type="button" class="linkbtn" onClick={() => set({ oneWay: !f.oneWay })}>{f.oneWay ? "pridať návrat" : "len jednosmerná"}</button></label>
            {f.oneWay ? <div class="input sp-oneway">Jednosmerná letenka</div> : <>
              <input id="ret" class="input" type="date" min={f.dep} value={f.ret} onInput={(e) => set({ ret: (e.target as HTMLInputElement).value })} />
              <Segmented value={f.retFlex} options={flexOpts} onChange={(v) => set({ retFlex: v })} />
            </>}
          </div>
        </div>
        <div class="sp-row sp-opts">
          <div class="sp-field"><label>Cestujúci</label><Stepper value={f.adults} min={1} max={6} onChange={(v) => set({ adults: v })} format={(v) => `${v} ${plural(v, "dospelý", "dospelí", "dospelých")}`} /></div>
          <div class="sp-field"><label>Batožina</label><Segmented value={f.bags} options={[[0, "Príručná"], [1, "S kufrom"]]} onChange={(v) => set({ bags: v })} /></div>
          <div class="sp-field"><label>Prestupy</label><Segmented value={f.stops} options={[[0, "Priame"], [1, "Max 1"], [2, "Max 2"], [3, "Hocikoľko"]]} onChange={(v) => set({ stops: v })} /></div>
          <button class="btn cta sp-go" type="submit" disabled={busy}>{busy ? "Hľadám…" : <>Hľadať <Arrow /></>}</button>
        </div>
        {error && <div class="callout warn" style={{ marginTop: 12 }}>{error}</div>}
      </form>

      {busy && <div class="grid" style={{ marginTop: 22 }}>{[0, 1, 2].map(() => <div class="skeleton" style={{ height: 420 }} />)}</div>}
      {!busy && results && (
        <>
          <div class="section-head" style={{ marginTop: 30 }}>
            <h2 style={{ fontSize: 30 }}>{results.length ? `${results.length} ${plural(results.length, "výsledok", "výsledky", "výsledkov")}` : "Nič sa nenašlo"}</h2>
            <p>{results.length ? "najlacnejšie lety podľa Kiwi.com · cena sa pri rezervácii ešte overí" : "Skús iné dátumy, flexibilitu ±2 dni alebo viac prestupov."}</p>
            <span class="spacer" />
            {results.length > 1 && <Segmented value={sortBy} options={[["price", "Najlacnejšie"], ["duration", "Najrýchlejšie"]]} onChange={setSortBy} />}
          </div>
          <div class="grid">{sorted.map((o, i) => <DealCard key={`${o.buy}`} o={o} index={i} />)}</div>
        </>
      )}
    </>
  );
}
