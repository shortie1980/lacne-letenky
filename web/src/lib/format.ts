import type { Baggage, Offer } from "../types";

export const WEEKDAYS = ["po", "ut", "st", "št", "pi", "so", "ne"];
export const WEEKDAYS_LONG = ["pondelok", "utorok", "streda", "štvrtok", "piatok", "sobota", "nedeľa"];
const MONTHS = ["jan", "feb", "mar", "apr", "máj", "jún", "júl", "aug", "sep", "okt", "nov", "dec"];

export const REGION_ICON: Record<string, string> = {
  europe: "🇪🇺", middle_east: "🕌", central_asia: "🏔️", asia: "🌏", north_america: "🗽", latam: "🌴", other: "🌍",
};
export const REGION_ORDER = ["asia", "north_america", "latam", "middle_east", "central_asia", "europe", "other"];

export function flag(cc?: string | null): string {
  if (!cc || !/^[A-Z]{2}$/.test(cc)) return "🌍";
  return String.fromCodePoint(...[...cc].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65));
}

export function plural(n: number, one: string, few: string, many: string): string {
  if (n === 1) return one;
  return n >= 2 && n <= 4 ? few : many;
}

const d = (iso: string) => new Date(iso.slice(0, 10) + "T00:00:00");
const isoWeekday = (iso: string) => ((d(iso).getDay() + 6) % 7);

export const weekday = (iso: string) => WEEKDAYS[isoWeekday(iso)];
export const dayMonth = (iso: string) => `${d(iso).getDate()}. ${MONTHS[d(iso).getMonth()]}`;
export const dateShort = (iso: string) => `${weekday(iso)} ${dayMonth(iso)}`;

export function dateRange(a: string, b: string): string {
  const da = d(a), db = d(b);
  if (da.getMonth() === db.getMonth()) return `${da.getDate()}. – ${db.getDate()}. ${MONTHS[db.getMonth()]}`;
  return `${dayMonth(a)} – ${dayMonth(b)}`;
}

export const time = (isoDateTime: string) => isoDateTime.slice(11, 16);

export function duration(sec?: number | null): string {
  if (!sec) return "";
  const h = Math.floor(sec / 3600), m = Math.round((sec % 3600) / 60);
  return m ? `${h} h ${m} min` : `${h} h`;
}

export function minutesBetween(a: string, b: string): number {
  return Math.round((new Date(b).getTime() - new Date(a).getTime()) / 60000);
}

export function ago(iso: string, now = Date.now()): string {
  const m = Math.round((now - new Date(iso).getTime()) / 60000);
  if (m < 1) return "práve teraz";
  if (m < 60) return `pred ${m} min`;
  const h = Math.round(m / 60);
  if (h < 24) return `pred ${h} h`;
  const days = Math.round(h / 24);
  return `pred ${days} ${plural(days, "dňom", "dňami", "dňami")}`;
}

export const nights = (days: number) => `${days} ${plural(days, "deň", "dni", "dní")}`;
export const transfers = (n: number) => (n === 0 ? "priamy let" : `${n} ${plural(n, "prestup", "prestupy", "prestupov")}`);

export function baggage(b: Baggage | null, adults: number): { icon: string; text: string } | null {
  if (!b) return null;
  if ((b.checkedBag ?? 0) >= adults) return { icon: "🧳", text: "kufor v cene" };
  if ((b.cabinBag ?? 0) >= adults) return { icon: "🎒", text: "príručná batožina" };
  return { icon: "👜", text: "len malá taška" };
}

export const euro = (n: number) => `${Math.round(n).toLocaleString("sk-SK")} €`;

export function discount(o: Offer): number | null {
  if (o.drop_pct && o.reasons?.includes("smart")) return o.drop_pct;
  if (o.limit) return Math.round((1 - o.price_pp / o.limit) * 100);
  return null;
}

export function freshness(o: Offer): string {
  if (o.live) return "živá cena";
  if (o.age == null) return "z cache";
  return o.age === 0 ? "z cache · dnes" : `z cache · spred ${o.age} ${o.age === 1 ? "dňa" : "dní"}`;
}

export const normalize = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export const safeUrl = (u?: string | null) => (u && /^https:\/\//.test(u) ? u : undefined);
