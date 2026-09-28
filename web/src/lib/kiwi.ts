// Živé vyhľadávanie letov priamo z prehliadača cez verejný MCP server Kiwi.com (povoľuje CORS).
import type { Baggage, HistoryEntry, Leg, Offer, Places } from "../types";

const KIWI_MCP_URL = "https://mcp.kiwi.com/";

export interface SearchParams {
  from: string[];
  to: string;                 // IATA mesta, názov krajiny alebo "anywhere"
  toCountry?: string;         // kód krajiny, ak je cieľ krajina alebo mesto
  departure: string;          // YYYY-MM-DD
  departureFlex: number;
  returnDate: string | null;  // null = jednosmerná
  returnFlex: number;
  adults: number;
  holdBags: number;
  maxStops: number | null;    // null = bez obmedzenia
}

interface RawSegment {
  from: string; to: string; fromCity?: string; toCity?: string; fromCountry?: string; toCountry?: string;
  departureTime: string; arrivalTime: string; carrier?: string; carrierName?: string; flightNumber?: string;
}
interface RawLeg { departureTime: string; arrivalTime: string; durationSeconds?: number; stops: number; route: string[]; segments: RawSegment[] }
interface RawItinerary {
  price: number; bookingUrl: string; imageId?: string; totalDurationSeconds?: number; baggage?: Baggage;
  outbound: RawLeg; inbound?: RawLeg;
}

const kiwiDate = (iso: string) => iso.split("-").reverse().join("/");

export async function kiwiSearch(p: SearchParams, signal?: AbortSignal): Promise<RawItinerary[]> {
  const args: Record<string, unknown> = {
    flyFrom: p.from.join(","), flyTo: p.to, currency: "EUR", sort: "price", adults: p.adults,
    departureDate: kiwiDate(p.departure), departureDateFlexDays: p.departureFlex,
    one_for_city: p.to === "anywhere" || p.to.length > 3,
  };
  if (p.returnDate) { args.returnDate = kiwiDate(p.returnDate); args.returnDateFlexDays = p.returnFlex; }
  if (p.holdBags) args.adults_hold_bags = Array(p.adults).fill(p.holdBags);
  if (p.maxStops != null) args.max_sector_stopovers = p.maxStops;
  const r = await fetch(KIWI_MCP_URL, {
    method: "POST", signal,
    headers: { "Content-Type": "application/json", Accept: "application/json, text/event-stream" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name: "search-flight", arguments: args } }),
  });
  if (!r.ok) throw new Error(`Kiwi odpovedal ${r.status}`);
  const text = await r.text();
  const line = text.split("\n").reverse().find((l) => l.startsWith("data:"));
  const payload = JSON.parse(line ? line.slice(5) : text);
  if (payload.error) throw new Error(payload.error.message ?? "Kiwi vrátil chybu");
  const result = payload.result;
  const data = result.structuredContent ?? JSON.parse(result.content[0].text);
  if (data.error) throw new Error(String(data.error));
  return data.itineraries ?? [];
}

const toLeg = (raw: RawLeg): Leg => ({
  dep: raw.departureTime.slice(0, 16), arr: raw.arrivalTime.slice(0, 16), duration: raw.durationSeconds, route: raw.route,
  segments: raw.segments.map((s) => ({
    from: s.from, to: s.to, from_city: s.fromCity, to_city: s.toCity, dep: s.departureTime.slice(0, 16),
    arr: s.arrivalTime.slice(0, 16), carrier: s.carrier, carrier_name: s.carrierName, flight: s.flightNumber,
  })),
});

/** Itinerár z Kiwi → Offer, aby sa dal zobraziť rovnakou kartou a detailom ako automatické ponuky. */
export function toOffer(it: RawItinerary, places: Places, history: Record<string, HistoryEntry>, adults: number): Offer {
  const out = it.outbound, back = it.inbound;
  const last = out.segments[out.segments.length - 1];
  const countryName = last?.toCountry ?? "";
  const country = places.countries.find((c) => c[1] === countryName)?.[0] ?? "";
  const city = last?.toCity ?? out.route[out.route.length - 1];
  const histKey = Object.keys(history).find((k) => history[k].name === city && history[k].country === country);
  const hist = histKey ? history[histKey] : undefined;
  const typical = median((hist?.live?.length ?? 0) >= 4 ? hist!.live!.map((p) => p[1]) : (hist?.market ?? []).slice(-14).map((p) => p[1]));
  const pricePP = Math.round(it.price / adults);
  const carriers = [...out.segments, ...(back?.segments ?? [])].map((s) => s.carrier).filter(Boolean) as string[];
  const dep = out.departureTime.slice(0, 10), ret = back ? back.departureTime.slice(0, 10) : "";
  return {
    origin: out.route[0], destination: histKey ?? out.route[out.route.length - 1], city, country, region: hist?.region ?? "other",
    price_pp: pricePP, price_total: Math.round(it.price), limit: null,
    departure: dep, return: ret, days: ret ? Math.round((Date.parse(ret) - Date.parse(dep)) / 86_400_000) : 0,
    transfers: Math.max(out.stops, back?.stops ?? 0),
    airline: carriers[0] ?? "", airlines: [...new Set(carriers)], airline_name: out.segments[0]?.carrierName,
    age: 0, live: true, baggage: it.baggage ?? null, duration: it.totalDurationSeconds,
    out: toLeg(out), back: back ? toLeg(back) : null,
    typical: typical ? Math.round(typical) : null,
    drop_pct: typical ? Math.round((1 - pricePP / typical) * 100) : null,
    reasons: [], exceptional: false, adults,
    buy: it.bookingUrl, google: googleLink(out.route[0], out.route[out.route.length - 1], dep, ret),
    image: it.imageId ? `https://images.kiwi.com/photos/600x600/${it.imageId}.jpg` : null, score: 0,
  };
}

function median(v: number[]): number | null {
  if (!v.length) return null;
  const s = [...v].sort((a, b) => a - b), m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

export function googleLink(from: string, to: string, dep: string, ret: string): string {
  const q = `Flights from ${from} to ${to} on ${dep}` + (ret ? ` through ${ret}` : " one way");
  return "https://www.google.com/travel/flights?q=" + encodeURIComponent(q);
}
