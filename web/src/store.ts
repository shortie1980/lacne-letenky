// Globálny stav aplikácie (Preact signals) a akcie.
import { computed, signal } from "@preact/signals";
import { withDefaults } from "./lib/config";
import { GitHub, GitHubError, detectRepo, readLocalConfig, storage } from "./lib/github";
import { plural } from "./lib/format";
import type { Config, DealsData, History, Offer, Places } from "./types";

export type Tab = "deals" | "tips" | "market" | "settings";
export type Sort = "value" | "price" | "date";

export const data = signal<DealsData | null>(null);
export const history = signal<History>({});
export const places = signal<Places>({ cities: [], countries: [], airlines: [] });
export const loadError = signal<string | null>(null);

export const saved = signal<Config | null>(null);
export const draft = signal<Config | null>(null);
export const sha = signal<string | null>(null);
export const repo = signal<string>(detectRepo());
export const token = signal<string>(storage.get("gh_token") || "");
export const saving = signal(false);
export const run = signal<{ state: "idle" | "waiting" | "running" | "done" | "error"; url?: string }>({ state: "idle" });

export const tab = signal<Tab>((storage.get("tab") as Tab) || "deals");
export const region = signal<string>(storage.get("region") || "all");
export const origin = signal<string>("all");
export const sort = signal<Sort>((storage.get("sort") as Sort) || "value");
export const liveOnly = signal<boolean>(storage.get("liveOnly") !== "0");
export const selected = signal<Offer | null>(null);
export const toastMsg = signal<{ text: string; id: number } | null>(null);

export const dirty = computed(() => !!draft.value && !!saved.value && JSON.stringify(draft.value) !== JSON.stringify(saved.value));
export const connected = computed(() => !!repo.value && !!token.value);
const gh = () => new GitHub(repo.value, token.value);

export function setTab(t: Tab) { tab.value = t; storage.set("tab", t); window.scrollTo({ top: 0, behavior: "smooth" }); }
export function toast(text: string) { toastMsg.value = { text, id: Date.now() }; }

export function editDraft(fn: (c: Config) => void) {
  if (!draft.value) return;
  const c = structuredClone(draft.value);
  fn(c);
  draft.value = c;
}

// ─── Dáta ────────────────────────────────────────────────────────────────────

export async function loadData() {
  const t = Date.now();
  const get = async <T,>(p: string): Promise<T | null> => {
    try { const r = await fetch(`data/${p}?t=${t}`); return r.ok ? await r.json() : null; } catch { return null; }
  };
  const [d, h, p] = await Promise.all([get<DealsData>("deals.json"), get<History>("history.json"), get<Places>("places.json")]);
  if (d && d.version >= 2) { data.value = d; loadError.value = null; }
  else loadError.value = d ? "Dáta sú v starom formáte – počkaj na ďalšie vyhľadávanie." : "Dáta sa zatiaľ nepodarilo načítať.";
  if (h) history.value = h;
  if (p) places.value = p;
}

export async function loadConfig() {
  let cfg: Config | null = null;
  if (repo.value) {
    try { const r = await gh().readConfig(); cfg = r.config; sha.value = r.sha; }
    catch (e) { console.warn("config", e); }
  }
  cfg ??= await readLocalConfig();
  if (!cfg) return;
  saved.value = withDefaults(cfg);
  if (!dirty.value || !draft.value) draft.value = structuredClone(saved.value);
}

// ─── GitHub ──────────────────────────────────────────────────────────────────

export async function connect(repoName: string, tok: string): Promise<boolean> {
  const hadEdits = dirty.value;
  const prev = { repo: repo.value, token: token.value };
  repo.value = repoName; token.value = tok;
  try {
    const r = await gh().readConfig();
    storage.set("repo", repoName); storage.set("gh_token", tok);
    sha.value = r.sha; saved.value = withDefaults(r.config);
    if (!hadEdits) draft.value = structuredClone(saved.value);
    toast(hadEdits ? "Pripojené ✓ Ukladám tvoje zmeny…" : "Pripojené ✓");
    if (hadEdits) await save();
    return true;
  } catch (e) {
    repo.value = prev.repo; token.value = prev.token;
    toast(`Pripojenie zlyhalo: ${(e as Error).message}`);
    return false;
  }
}

export function disconnect() { storage.set("gh_token", null); token.value = ""; toast("Toto zariadenie je odpojené."); }

export async function save() {
  if (!draft.value) return;
  if (!connected.value) { setTab("settings"); toast("Na uloženie treba pripojiť GitHub – tvoje zmeny zostanú zachované."); return; }
  saving.value = true;
  try {
    sha.value = await gh().writeConfig(draft.value, sha.value);
    saved.value = structuredClone(draft.value);
    toast("✓ Uložené. Spúšťam nové vyhľadávanie…");
    watchRun(new Date(Date.now() - 60_000));
  } catch (e) {
    if (e instanceof GitHubError && e.status === 409) { toast("Nastavenia sa medzitým zmenili, načítavam aktuálne."); await loadConfig(); }
    else toast(`Uloženie zlyhalo: ${(e as Error).message}`);
  } finally { saving.value = false; }
}

export async function runNow() {
  try { await gh().runNow(); toast("Vyhľadávanie spustené."); watchRun(new Date(Date.now() - 60_000)); }
  catch (e) { toast(e instanceof GitHubError && e.status === 403 ? "Token nemá oprávnenie Actions: Read and write." : `Nepodarilo sa spustiť: ${(e as Error).message}`); }
}

let timer: number | undefined;
export function watchRun(since: Date) {
  clearInterval(timer);
  run.value = { state: "waiting" };
  let n = 0;
  const tick = async () => {
    n++;
    let runs: Awaited<ReturnType<GitHub["runs"]>> = [];
    try { runs = await gh().runs(); } catch { /* skúsime znova */ }
    const r = runs.find((x) => new Date(x.created_at) >= since);
    if (r && r.status !== "completed") run.value = { state: "running", url: r.html_url };
    if (r && r.status === "completed") {
      clearInterval(timer);
      if (r.conclusion === "success") {
        await new Promise((res) => setTimeout(res, 8000));
        await loadData(); await loadConfig();
        run.value = { state: "done" };
        toast("✓ Výsledky podľa nových nastavení sú načítané.");
        setTimeout(() => (run.value = { state: "idle" }), 4000);
      } else run.value = { state: "error", url: r.html_url };
    } else if (n > 60) { clearInterval(timer); run.value = { state: "error" }; }
  };
  timer = window.setInterval(tick, 5000);
  tick();
}

// ─── Úpravy z kariet ponúk ───────────────────────────────────────────────────

export function lastLivePrice(code: string): number | null {
  const h = history.value[code];
  const pts = h?.live?.length ? h.live : h?.points;
  return pts?.length ? pts[pts.length - 1][1] : null;
}

export function addWatch(code: string, name: string, price?: number) {
  if (!draft.value) return toast("Nastavenia ešte nie sú načítané.");
  const now = price || lastLivePrice(code);
  const suggested = now ? Math.max(10, Math.round((now * 0.9) / 5) * 5) : 300;
  if (draft.value.watchlist.some((w) => w.code === code)) return toast(`${name} už sleduješ.`);
  editDraft((c) => {
    c.watchlist.push({ code, name, max_price: suggested });
    c.excluded = c.excluded.filter((x) => x !== code);
  });
  toast(`🔔 ${name}: upozorním ťa pod ${suggested} €${now ? " (o 10 % menej ako teraz)" : ""}. Nezabudni uložiť.`);
}

export function addExclude(code: string, name: string) {
  if (!draft.value) return toast("Nastavenia ešte nie sú načítané.");
  editDraft((c) => {
    if (!c.excluded.includes(code)) c.excluded.push(code);
    c.watchlist = c.watchlist.filter((w) => w.code !== code);
  });
  toast(`🚫 ${name} sa už nebude zobrazovať. Nezabudni uložiť.`);
}

// ─── Odvodené dáta pre zobrazenie ────────────────────────────────────────────

export const visibleDeals = computed(() => {
  const all = (data.value?.deals ?? []).filter((o) => !liveOnly.value || o.live);
  const list = all.filter((o) => (region.value === "all" || o.region === region.value) && (origin.value === "all" || o.origin === origin.value));
  const key: Record<Sort, (o: Offer) => number | string> = { value: (o) => o.score, price: (o) => o.price_pp, date: (o) => o.departure };
  return list.slice().sort((a, b) => (key[sort.value](a) < key[sort.value](b) ? -1 : 1));
});

export const dealCountText = (n: number) => `${n} ${plural(n, "ponuka", "ponuky", "ponúk")}`;
