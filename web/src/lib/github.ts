// Prístup ku GitHubu: načítanie a uloženie config.json, spustenie vyhľadávania, stav behov.
import type { Config } from "../types";

export class GitHubError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export const storage = {
  get(k: string): string | null { try { return localStorage.getItem(k); } catch { return null; } },
  set(k: string, v: string | null) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* súkromné okno */ } },
};

export function detectRepo(): string {
  const m = location.hostname.match(/^([^.]+)\.github\.io$/);
  if (m) {
    const seg = location.pathname.split("/").filter(Boolean)[0];
    return seg ? `${m[1]}/${seg}` : `${m[1]}/${m[1]}.github.io`;
  }
  return storage.get("repo") || "";
}

const b64decode = (s: string) => new TextDecoder().decode(Uint8Array.from(atob(s.replace(/\s/g, "")), (c) => c.charCodeAt(0)));
const b64encode = (s: string) => { let bin = ""; new TextEncoder().encode(s).forEach((x) => (bin += String.fromCharCode(x))); return btoa(bin); };

export class GitHub {
  constructor(public repo: string, public token: string) {}

  async api<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = { Accept: "application/vnd.github+json" };
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    const r = await fetch(`https://api.github.com${path}`, { ...init, headers: { ...headers, ...(init.headers as object) } });
    if (!r.ok) {
      let msg = String(r.status);
      try { msg += " " + (await r.json()).message; } catch { /* bez tela */ }
      throw new GitHubError(r.status, msg);
    }
    return (r.status === 204 ? null : r.json()) as T;
  }

  async readConfig(): Promise<{ config: Config; sha: string | null }> {
    if (this.token) {
      const f = await this.api<{ sha: string; content: string }>(`/repos/${this.repo}/contents/config.json?ref=main`);
      return { config: JSON.parse(b64decode(f.content)), sha: f.sha };
    }
    const r = await fetch(`https://raw.githubusercontent.com/${this.repo}/main/config.json?t=${Date.now()}`);
    if (!r.ok) throw new GitHubError(r.status, "config.json sa nepodarilo načítať");
    return { config: await r.json(), sha: null };
  }

  async writeConfig(config: Config, sha: string | null): Promise<string> {
    if (!sha) sha = (await this.readConfig()).sha;
    const res = await this.api<{ content: { sha: string } }>(`/repos/${this.repo}/contents/config.json`, {
      method: "PUT",
      body: JSON.stringify({
        message: "Nastavenia z aplikácie", branch: "main", sha,
        content: b64encode(JSON.stringify(config, null, 2) + "\n"),
      }),
    });
    return res.content.sha;
  }

  runNow() {
    return this.api(`/repos/${this.repo}/actions/workflows/watch.yml/dispatches`, { method: "POST", body: JSON.stringify({ ref: "main" }) });
  }

  async runs(): Promise<{ created_at: string; status: string; conclusion: string | null; html_url: string }[]> {
    const r = await this.api<{ workflow_runs: [] }>(`/repos/${this.repo}/actions/workflows/watch.yml/runs?per_page=3`);
    return r.workflow_runs || [];
  }
}

// Lokálny vývoj: config.json z koreňa projektu
export async function readLocalConfig(): Promise<Config | null> {
  for (const p of ["../config.json", "config.json", "/config.json"]) {
    try { const r = await fetch(p, { cache: "no-store" }); if (r.ok) return await r.json(); } catch { /* ďalšia cesta */ }
  }
  return null;
}
