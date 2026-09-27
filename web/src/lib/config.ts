// Predvolené nastavenia – rovnaké ako letenky/config.py, aby aplikácia vedela zobraziť aj staršie config.json.
import type { Config, Region } from "../types";

const REGION_EXTRA = { out_days: [] as number[], back_days: [] as number[] };

export const DEFAULTS: Config = {
  origins: ["VIE", "BTS", "BUD", "PRG"],
  months_ahead: 6, max_transfers: 2, max_alerts_per_run: 15, max_alerts_per_region: 4,
  renotify_days: 7, renotify_drop_pct: 10, max_price_age_days: 4,
  passengers: { adults: 1, hold_bags: 0 },
  filters: { earliest_departure_hour: 0, latest_departure_hour: 23, exclude_airlines: [] },
  regions: {
    europe: { label: "Európa", enabled: true, max_price: 35, min_days: 3, max_days: 7, ...REGION_EXTRA },
    middle_east: { label: "Kaukaz a Blízky východ", enabled: true, max_price: 100, min_days: 7, max_days: 10, ...REGION_EXTRA },
    central_asia: { label: "Stredná Ázia", enabled: false, max_price: 250, min_days: 7, max_days: 10, ...REGION_EXTRA },
    asia: { label: "Ázia", enabled: true, max_price: 450, min_days: 7, max_days: 10, ...REGION_EXTRA },
    north_america: { label: "Severná Amerika", enabled: true, max_price: 350, min_days: 7, max_days: 10, ...REGION_EXTRA },
    latam: { label: "Južná Amerika a Karibik", enabled: true, max_price: 650, min_days: 7, max_days: 10, ...REGION_EXTRA },
  },
  watchlist: [], excluded: [],
  smart: { enabled: true, drop_pct: 25, min_history_days: 4, max_over_limit_pct: 50 },
  tips: { enabled: true },
  notify: { ntfy_topic: "", health_alerts: true },
  live: { max_verify_per_run: 10, max_watch_searches: 10, explore_per_run: 14, cache_hours: 6 },
};

export const REGION_MAX_PRICE: Record<string, number> = {
  europe: 300, middle_east: 600, central_asia: 900, asia: 1500, north_america: 1500, latam: 2000,
};

const isObj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);

function deepMerge<T>(base: T, user: unknown): T {
  if (!isObj(base) || !isObj(user)) return (user === undefined ? structuredClone(base) : user) as T;
  const out: Record<string, unknown> = structuredClone(base as Record<string, unknown>);
  for (const [k, v] of Object.entries(user)) {
    out[k] = isObj(v) && isObj(out[k]) && k !== "regions" ? deepMerge(out[k], v) : structuredClone(v);
  }
  return out as T;
}

export function withDefaults(user: Partial<Config>): Config {
  const c = deepMerge(DEFAULTS, user);
  for (const [k, r] of Object.entries(c.regions)) {
    const base: Region = DEFAULTS.regions[k] ?? { label: k, enabled: false, max_price: 0, min_days: 7, max_days: 10, ...REGION_EXTRA };
    c.regions[k] = { ...base, ...REGION_EXTRA, ...r };
  }
  return c;
}

export const ORIGIN_OPTIONS: [string, string][] = [
  ["VIE", "Viedeň"], ["BTS", "Bratislava"], ["BUD", "Budapešť"], ["PRG", "Praha"], ["KSC", "Košice"],
  ["BRQ", "Brno"], ["KRK", "Krakov"], ["KTW", "Katovice"], ["MUC", "Mníchov"], ["LJU", "Ľubľana"], ["GRZ", "Graz"],
];
export const originName = (code: string) => ORIGIN_OPTIONS.find((o) => o[0] === code)?.[1] ?? code;
