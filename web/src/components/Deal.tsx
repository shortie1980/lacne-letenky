import { useEffect } from "preact/hooks";
import { originName } from "../lib/config";
import {
  baggage, dateShort, discount, duration, euro, flag, freshness, minutesBetween, nights, safeUrl, time, transfers,
} from "../lib/format";
import { addExclude, addWatch, data, history, places, selected } from "../store";
import type { Leg, Offer } from "../types";
import { PriceChart, Sparkline } from "./charts";
import { Arrow, Ban, Bell, Close, External } from "./icons";
import { Photo } from "./ui";

const adults = () => data.value?.passengers.adults ?? 1;

function Why({ o }: { o: Offer }) {
  if (o.reasons?.includes("smart") && o.typical)
    return <div class="why smart">📉 o {o.drop_pct} % lacnejšie ako bežne ({euro(o.typical)})</div>;
  if (o.limit) return <div class="why">✓ pod tvojím limitom {euro(o.limit)}</div>;
  return <div class="why muted">bez limitu</div>;
}

export function DealCard({ o, index = 0 }: { o: Offer; index?: number }) {
  const off = discount(o);
  const bag = baggage(o.baggage, adults());
  return (
    <article class="card" style={{ animationDelay: `${Math.min(index, 12) * 35}ms` }}>
      <button class="card-media" onClick={() => (selected.value = o)} aria-label={`Detail: ${o.city}`}>
        <Photo src={o.image} country={o.country} />
        <div class="media-top">
          <span class={`pill ${o.live ? "" : "dark"}`}>{o.live ? "● živá cena" : freshness(o)}</span>
          {off != null && off > 0 ? <span class={`pill ${o.reasons?.includes("smart") ? "hot" : "good"}`}>−{off} %</span> : null}
        </div>
        <div class="media-bottom">
          <div class="from">{flag(o.country)} z {originName(o.origin)}</div>
          <div class="city">{o.city}</div>
        </div>
      </button>
      <div class="card-body">
        <div class="price-row">
          <span class="price num">{euro(o.price_pp)}</span>
          <span class="price-sub">{adults() > 1 ? `/ os. · spolu ${euro(o.price_total)}` : "spiatočná"}</span>
          {o.typical && o.typical > o.price_pp ? <span class="was num">{euro(o.typical)}</span> : null}
        </div>
        <div class="dates">{dateShort(o.departure)} <span class="arrow">→</span> {dateShort(o.return)}</div>
        <div class="meta">
          <span class="tag">🌙 {nights(o.days)}</span>
          <span class="tag">🔁 {transfers(o.transfers)}</span>
          {o.airline_name ? <span class="tag">✈ {o.airline_name}</span> : null}
          {bag ? <span class="tag">{bag.icon} {bag.text}</span> : null}
        </div>
        <Why o={o} />
        <Sparkline entry={history.value[o.destination]} limit={o.limit} />
        <div class="actions">
          <a class="btn cta" href={safeUrl(o.buy)} target="_blank" rel="noopener">{o.live ? "Kúpiť" : "Pozrieť"} <Arrow /></a>
          <button class="btn" onClick={() => (selected.value = o)}>Detail</button>
        </div>
      </div>
    </article>
  );
}

function Itinerary({ title, leg }: { title: string; leg: Leg }) {
  return (
    <div class="itin">
      <div class="itin-head">{title} <span>{duration(leg.duration)}</span></div>
      {leg.segments.map((s, i) => {
        const next = leg.segments[i + 1];
        const wait = next ? minutesBetween(s.arr, next.dep) : 0;
        return (
          <>
            <div class="seg">
              <span class="t">{time(s.dep)}</span><span class="line" />
              <div class="where"><b>{s.from_city ?? s.from}</b> · {s.from}<small>{s.carrier_name} {s.flight}</small></div>
            </div>
            <div class={`seg ${next ? "" : "end"}`}>
              <span class="t">{time(s.arr)}</span><span class="line" />
              <div class="where"><b>{s.to_city ?? s.to}</b> · {s.to}{s.arr.slice(0, 10) !== s.dep.slice(0, 10) ? <small>prílet {dateShort(s.arr)}</small> : null}</div>
            </div>
            {next ? <div class="layover">⏱ prestup {Math.floor(wait / 60)} h {wait % 60} min v {s.to_city ?? s.to}</div> : null}
          </>
        );
      })}
    </div>
  );
}

export function DealSheet() {
  const o = selected.value;
  useEffect(() => {
    if (!o) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && (selected.value = null);
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [o]);
  if (!o) return null;
  const bag = baggage(o.baggage, adults());
  const close = () => (selected.value = null);
  return (
    <>
      <div class="scrim" onClick={close} />
      <aside class="sheet" role="dialog" aria-modal="true" aria-label={`Detail letu do ${o.city}`}>
        <div class="sheet-media">
          <Photo src={o.image} country={o.country} />
          <button class="sheet-close" onClick={close} aria-label="Zavrieť"><Close /></button>
          <div class="sheet-title">
            <div class="eyebrow">{originName(o.origin)} → {flag(o.country)} {places.value.countries.find((c) => c[0] === o.country)?.[1] ?? o.country}</div>
            <div class="city">{o.city}</div>
          </div>
        </div>
        <div class="sheet-body">
          <div class="sheet-price">
            <div><b class="num">{euro(o.price_pp)}</b><div class="price-sub">{adults() > 1 ? `za osobu · spolu ${euro(o.price_total)}` : "spiatočná letenka"}</div></div>
            <div style={{ marginLeft: "auto", textAlign: "right" }}><Why o={o} /><div class="price-sub">{o.live ? "✓ živá cena z Kiwi.com" : freshness(o)}</div></div>
          </div>
          <div class="kv">
            <div>Odlet<b>{dateShort(o.departure)}</b></div>
            <div>Návrat<b>{dateShort(o.return)}</b></div>
            <div>Dĺžka pobytu<b>{nights(o.days)}</b></div>
            <div>Prestupy<b>{transfers(o.transfers)}</b></div>
            {o.airline_name ? <div>Aerolínia<b>{o.airline_name}</b></div> : null}
            {bag ? <div>Batožina<b>{bag.icon} {bag.text}</b></div> : null}
          </div>
          {o.out && o.back ? (
            <div class="block"><h4>Lety</h4><Itinerary title="Tam" leg={o.out} /><Itinerary title="Späť" leg={o.back} /></div>
          ) : (
            <div class="callout warn">Cena je z cache vyhľadávaní iných ľudí a ešte nebola overená naživo. Presné lety a cenu uvidíš po kliknutí na Pozrieť.</div>
          )}
          <div class="block"><h4>Vývoj ceny · {o.city}</h4><PriceChart entry={history.value[o.destination]} limit={o.limit} typical={o.typical} /></div>
          <div class="sheet-actions">
            <a class="btn cta" href={safeUrl(o.buy)} target="_blank" rel="noopener">{o.live ? "Kúpiť na Kiwi.com" : "Pozrieť na Aviasales"} <External /></a>
            <a class="btn" href={safeUrl(o.google)} target="_blank" rel="noopener">Google Flights</a>
            <button class="btn" onClick={() => { addWatch(o.destination, o.city, o.price_pp); close(); }}><Bell /> Sledovať</button>
            <button class="btn ghost" style={{ gridColumn: "1 / -1" }} onClick={() => { addExclude(o.destination, o.city); close(); }}><Ban /> {o.city} ma nezaujíma</button>
          </div>
        </div>
      </aside>
    </>
  );
}
