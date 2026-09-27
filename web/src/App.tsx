import { useEffect, useState } from "preact/hooks";
import { DealSheet } from "./components/Deal";
import { Bulb, Chart, Gear, Plane, Ticket } from "./components/icons";
import { SettingsView } from "./components/Settings";
import { DealsView, MarketView, TipsView } from "./components/Views";
import { ago } from "./lib/format";
import {
  connected, data, dirty, draft, loadConfig, loadData, run, save, saved, saving, setTab, tab, toastMsg, type Tab,
} from "./store";

const TABS: [Tab, string, () => preact.JSX.Element][] = [
  ["deals", "Ponuky", Ticket], ["tips", "Tipy", Bulb], ["market", "Ceny", Chart], ["settings", "Nastavenia", Gear],
];

function Status() {
  const [, force] = useState(0);
  useEffect(() => { const t = setInterval(() => force((n) => n + 1), 30_000); return () => clearInterval(t); }, []);
  const d = data.value;
  const r = run.value;
  if (r.state === "waiting" || r.state === "running")
    return <span class="status"><span class="dot run" />{r.state === "waiting" ? "Spúšťam vyhľadávanie…" : "Hľadám nové ceny…"}</span>;
  if (r.state === "error")
    return <a class="status" href={r.url} target="_blank" rel="noopener"><span class="dot err" />Vyhľadávanie zlyhalo</a>;
  if (!d) return <span class="status"><span class="dot warn" />Načítavam…</span>;
  const down = Object.values(d.health ?? {}).filter((h) => !h.ok);
  const stale = (Date.now() - new Date(d.updated_at).getTime()) / 60000 > 90;
  const title = down.map((h) => `${h.label}: ${h.last_error ?? "chyba"}`).join("\n") || "Všetky zdroje fungujú";
  return (
    <span class="status" title={title}>
      <span class={`dot ${stale || down.length ? "warn" : ""}`} />
      <span class="long">{down.length ? `${down.length} zdroj mimo prevádzky · ` : "Kontrola "}</span>{ago(d.updated_at)}
    </span>
  );
}

function SaveBar() {
  return (
    <div class={`savebar ${dirty.value ? "show" : ""}`} role="region" aria-label="Neuložené zmeny">
      <span class="msg">{connected.value ? "Máš neuložené zmeny" : "Neuložené · pripoj GitHub"}</span>
      <button class="btn ghost small" onClick={() => (draft.value = structuredClone(saved.value))}>Zahodiť</button>
      <button class="btn light small" disabled={saving.value} onClick={save}>{saving.value ? "Ukladám…" : connected.value ? "Uložiť a hľadať" : "Pripojiť"}</button>
    </div>
  );
}

function Toast() {
  const t = toastMsg.value;
  const [show, setShow] = useState(false);
  useEffect(() => {
    if (!t) return;
    setShow(true);
    const h = setTimeout(() => setShow(false), 4200);
    return () => clearTimeout(h);
  }, [t?.id]);
  return <div class={`toast ${show ? "show" : ""}`} role="status" aria-live="polite">{t?.text}</div>;
}

export function App() {
  useEffect(() => {
    loadData().then(loadConfig);
    const t = setInterval(loadData, 5 * 60_000);
    const warn = (e: BeforeUnloadEvent) => { if (dirty.value) { e.preventDefault(); e.returnValue = ""; } };
    addEventListener("beforeunload", warn);
    return () => { clearInterval(t); removeEventListener("beforeunload", warn); };
  }, []);
  const count = data.value?.deals.filter((o) => o.live).length ?? 0;
  return (
    <>
      <header class="topbar">
        <div class="wrap topbar-in">
          <a class="brand" href="#" onClick={(e) => { e.preventDefault(); setTab("deals"); }}>
            <span class="brand-mark"><Plane /></span><span class="brand-name">Lacné letenky</span>
          </a>
          <nav class="nav" aria-label="Hlavná navigácia">
            {TABS.map(([id, label]) => (
              <button aria-current={tab.value === id ? "page" : undefined} onClick={() => setTab(id)}>
                {label}{id === "deals" && count ? <span class="count">{count}</span> : null}
              </button>
            ))}
          </nav>
          <Status />
        </div>
      </header>
      <main class="wrap">
        {tab.value === "deals" && <DealsView />}
        {tab.value === "tips" && <TipsView />}
        {tab.value === "market" && <MarketView />}
        {tab.value === "settings" && <SettingsView />}
      </main>
      <footer class="foot wrap">
        Živé ceny a rezervácie: Kiwi.com · kandidáti: Travelpayouts/Aviasales · tipy: fly4free.com<br />
        Ceny sa môžu rýchlo meniť, pred kúpou si ich vždy skontroluj.
      </footer>
      <nav class="bottom-nav" aria-label="Navigácia">
        {TABS.map(([id, label, Icon]) => (
          <button aria-current={tab.value === id ? "page" : undefined} onClick={() => setTab(id)}><Icon />{label}</button>
        ))}
      </nav>
      <SaveBar />
      <Toast />
      <DealSheet />
    </>
  );
}
