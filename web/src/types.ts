// Dátové typy – zodpovedajú JSON súborom, ktoré generuje letenky/site.py

export interface Segment {
  from: string; to: string; from_city?: string; to_city?: string;
  dep: string; arr: string; carrier?: string; carrier_name?: string; flight?: string;
}

export interface Leg { dep: string; arr: string; duration?: number; route: string[]; segments: Segment[] }

export interface Baggage { personalItem?: number; cabinBag?: number; checkedBag?: number }

export interface Offer {
  origin: string; destination: string; city: string; country: string; region: string;
  price_pp: number; price_total: number; limit: number | null;
  departure: string; return: string; days: number; transfers: number;
  airline: string; airlines?: string[]; airline_name?: string;
  age: number | null; live: boolean; baggage: Baggage | null; duration?: number | null;
  out?: Leg | null; back?: Leg | null;
  typical?: number | null; drop_pct?: number | null; reasons?: string[];
  buy: string; google: string; image: string | null; score: number;
}

export interface Tip {
  title: string; link: string; published: string; origin: string;
  price: number | null; destination: string | null; package: boolean; id: string;
}

export interface SourceHealth { label: string; ok: boolean; fails: number; last_ok: string | null; last_error: string | null }

export interface DealsData {
  version: number; updated_at: string; origins: string[];
  regions: Record<string, string>;
  passengers: { adults: number; hold_bags: number };
  deals: Offer[]; cheapest: Record<string, Offer[]>; tips: Tip[];
  health: Record<string, SourceHealth>;
  stats: { offers_checked: number; live: number; deals: number; kiwi_calls: number };
}

export interface HistoryEntry { name: string; country: string; region: string; points?: [string, number][]; live?: [string, number][] }
export type History = Record<string, HistoryEntry>;

export interface Places { cities: [string, string, string][]; countries: [string, string][]; airlines: [string, string][] }

export interface Region {
  label: string; enabled: boolean; max_price: number; min_days: number; max_days: number;
  out_days: number[]; back_days: number[];
}

export interface WatchItem { code: string; name: string; max_price: number }

export interface Config {
  origins: string[]; months_ahead: number; max_transfers: number;
  max_alerts_per_run: number; max_alerts_per_region: number;
  renotify_days: number; renotify_drop_pct: number; max_price_age_days: number;
  passengers: { adults: number; hold_bags: number };
  filters: { earliest_departure_hour: number; latest_departure_hour: number; exclude_airlines: string[] };
  regions: Record<string, Region>;
  watchlist: WatchItem[]; excluded: string[];
  smart: { enabled: boolean; drop_pct: number; min_history_days: number; max_over_limit_pct: number };
  tips: { enabled: boolean };
  notify: { ntfy_topic: string; health_alerts: boolean };
  live: { max_verify_per_run: number; max_watch_searches: number; explore_per_run: number; cache_hours: number };
  [key: string]: unknown;
}
