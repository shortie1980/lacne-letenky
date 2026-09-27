import { originName } from "../lib/config";
import { REGION_ICON, REGION_ORDER, ago, dateRange, discount, euro, flag, nights, plural, safeUrl, transfers } from "../lib/format";
import {
  addWatch, data, dealCountText, liveOnly, loadError, origin, region, selected, setTab, sort, visibleDeals, type Sort,
} from "../store";
import { storage } from "../lib/github";
import type { Offer } from "../types";
import { DealCard } from "./Deal";
import { Photo, Switch } from "./ui";

function Hero() {
  const d = data.value!;
  const live = d.deals.filter((o) => o.live);
  if (!live.length) return null;
  const best = live.slice().sort((a, b) => a.score - b.score)[0];
  const cheapestBy = (r: string) => live.filter((o) => o.region === r).sort((a, b) => a.price_pp - b.price_pp)[0];
  const picks = REGION_ORDER.map(cheapestBy).filter((o): o is Offer => !!o && o !== best).slice(0, 4);
  const off = discount(best);
  return (
    <section class="hero">
      <a class="hero-card" href="#" onClick={(e) => { e.preventDefault(); selected.value = best; }}>
        <Photo src={best.image} country={best.country} />
        <div class="hero-body">
          <div>
            <div class="eyebrow">Najlepšia ponuka práve teraz{off && off > 0 ? ` · −${off} %` : ""}</div>
            <div class="hero-city">{best.city}</div>
            <div class="hero-meta">
              <span>{flag(best.country)} z {originName(best.origin)}</span>
              <span>{dateRange(best.departure, best.return)}</span>
              <span>{nights(best.days)}</span>
              <span>{transfers(best.transfers)}</span>
            </div>
          </div>
          <div class="hero-price"><b class="num">{euro(best.price_pp)}</b><span>{d.passengers.adults > 1 ? "za osobu" : "spiatočná letenka"}</span></div>
        </div>
      </a>
      <div class="hero-side">
        <div class="stat-grid">
          <div class="stat"><small>Živé ponuky</small><b class="num">{live.length}<em>z {d.deals.length}</em></b></div>
          <div class="stat"><small>Akciové tipy</small><b class="num">{d.tips.length}<em>{plural(d.tips.length, "tip", "tipy", "tipov")}</em></b></div>
        </div>
        <div class="mini-list">
          <h3>Najlacnejšie podľa regiónu</h3>
          {picks.map((o) => (
            <button class="mini" onClick={() => (selected.value = o)}>
              <Photo src={o.image} country={o.country} />
              <span class="t">{o.city}<small>{REGION_ICON[o.region]} {d.regions[o.region]} · z {o.origin}</small></span>
              <span class="p num">{euro(o.price_pp)}</span>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

export function DealsView() {
  const d = data.value;
  if (!d) {
    return loadError.value
      ? <div class="empty" style={{ marginTop: 30 }}><div class="big">Zatiaľ tu nič nie je</div>{loadError.value}</div>
      : <div class="grid" style={{ marginTop: 30 }}>{[0, 1, 2, 3, 4, 5].map(() => <div class="skeleton" style={{ height: 420 }} />)}</div>;
  }
  const pool = d.deals.filter((o) => !liveOnly.value || o.live);
  const counts: Record<string, number> = {};
  pool.forEach((o) => (counts[o.region] = (counts[o.region] ?? 0) + 1));
  const origins = [...new Set(pool.map((o) => o.origin))].sort();
  const list = visibleDeals.value;
  const setSort = (s: Sort) => { sort.value = s; storage.set("sort", s); };
  return (
    <>
      <Hero />
      <div class="section-head">
        <h2>Ponuky</h2>
        <p>{dealCountText(list.length)} · {liveOnly.value ? "len živé ceny z Kiwi.com" : "vrátane neoverených cien z cache"}</p>
        <span class="spacer" />
        <Switch checked={liveOnly.value} onChange={(v) => { liveOnly.value = v; storage.set("liveOnly", v ? "1" : "0"); }} label="Len živé ceny" />
      </div>
      <div class="toolbar">
        <div class="chips">
          <button class="chip" aria-pressed={region.value === "all"} onClick={() => (region.value = "all")}>Všetko <span class="n">{pool.length}</span></button>
          {REGION_ORDER.filter((r) => counts[r]).map((r) => (
            <button class="chip" aria-pressed={region.value === r} onClick={() => { region.value = r; storage.set("region", r); }}>
              {REGION_ICON[r]} {d.regions[r]} <span class="n">{counts[r]}</span>
            </button>
          ))}
        </div>
        <span class="spacer" />
        {origins.length > 1 && (
          <select class="select" value={origin.value} onChange={(e) => (origin.value = (e.target as HTMLSelectElement).value)} aria-label="Letisko odletu">
            <option value="all">Zo všetkých letísk</option>
            {origins.map((o) => <option value={o}>z {originName(o)}</option>)}
          </select>
        )}
        <select class="select" value={sort.value} onChange={(e) => setSort((e.target as HTMLSelectElement).value as Sort)} aria-label="Zoradiť">
          <option value="value">Najvýhodnejšie</option>
          <option value="price">Najlacnejšie</option>
          <option value="date">Najskôr odlet</option>
        </select>
      </div>
      {list.length ? (
        <div class="grid">{list.map((o, i) => <DealCard key={`${o.origin}-${o.destination}-${o.departure}`} o={o} index={i} />)}</div>
      ) : (
        <div class="empty">
          <div class="big">Momentálne nič pod limitom</div>
          Pozri si <a href="#" onClick={(e) => { e.preventDefault(); setTab("market"); }}>aktuálne ceny</a> a uprav limity, alebo vypni „Len živé ceny“.
        </div>
      )}
    </>
  );
}

export function TipsView() {
  const tips = data.value?.tips ?? [];
  return (
    <>
      <div class="section-head" style={{ marginTop: 26 }}>
        <h2>Akciové tipy</h2>
        <p>Výpredaje a chybné ceny, ktoré našli ľudia z fly4free.com · len s odletom z tvojich letísk</p>
      </div>
      {tips.length ? (
        <div class="tips">
          {tips.map((t) => (
            <a class="tip" href={safeUrl(t.link)} target="_blank" rel="noopener">
              <div class="tip-top"><span class="pill dark" style={{ background: "var(--surface-3)", color: "var(--ink-2)" }}>z {originName(t.origin)}</span>{t.package ? <span>✈️ + 🏨 balík</span> : <span>✈️ letenka</span>}<span style={{ marginLeft: "auto" }}>{ago(t.published)}</span></div>
              <div class="tip-title">{t.title}</div>
              {t.price ? <div class="tip-price num">od {euro(t.price)}</div> : null}
            </a>
          ))}
        </div>
      ) : <div class="empty"><div class="big">Žiadne čerstvé tipy</div>Za posledné dva týždne nebol tip s odletom z tvojich letísk.</div>}
    </>
  );
}

export function MarketView() {
  const d = data.value;
  if (!d) return null;
  const order = REGION_ORDER.filter((r) => d.cheapest[r]?.length);
  return (
    <>
      <div class="section-head" style={{ marginTop: 26 }}>
        <h2>Ceny teraz</h2>
        <p>Najlacnejšie destinácie v každom regióne, aj nad limitom · podľa toho si nastav limity</p>
      </div>
      <div class="market">
        {order.map((r) => {
          const rows = d.cheapest[r];
          const scale = Math.max(...rows.map((o) => Math.max(o.price_pp, o.limit ?? 0)));
          const limit = rows.find((o) => o.limit)?.limit;
          return (
            <div class="panel">
              <div class="panel-head"><h3>{REGION_ICON[r]} {d.regions[r]}</h3><span>{limit ? `limit ${euro(limit)}` : "nesledované"}</span></div>
              {rows.map((o) => {
                const over = !o.limit || o.price_pp > o.limit;
                return (
                  <button class="mrow" onClick={() => (selected.value = o)}>
                    <span style={{ fontSize: 18 }}>{flag(o.country)}</span>
                    <span>
                      <span class="n">{o.city}<small>z {o.origin} · {o.live ? "živá" : "cache"}</small></span>
                      <div class="bar"><i class={over ? "over" : ""} style={{ width: `${(o.price_pp / scale) * 100}%` }} />{o.limit ? <span class="lim" style={{ left: `${(o.limit / scale) * 100}%` }} /> : null}</div>
                    </span>
                    <span class="p num">{euro(o.price_pp)}<small>{over ? <a href="#" onClick={(e) => { e.preventDefault(); e.stopPropagation(); addWatch(o.destination, o.city, o.price_pp); }}>🔔 sledovať</a> : "✓ pod limitom"}</small></span>
                  </button>
                );
              })}
            </div>
          );
        })}
      </div>
    </>
  );
}
