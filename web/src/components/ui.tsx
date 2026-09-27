// Základné ovládacie prvky
import type { ComponentChildren } from "preact";
import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { flag, normalize } from "../lib/format";

export function Switch({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label?: ComponentChildren }) {
  return (
    <label class="switch">
      <input type="checkbox" checked={checked} onChange={(e) => onChange((e.target as HTMLInputElement).checked)} />
      <span class="track" />
      {label}
    </label>
  );
}

export function Stepper({ value, min, max, step = 1, onChange, format }: {
  value: number; min: number; max: number; step?: number; onChange: (v: number) => void; format?: (v: number) => string;
}) {
  return (
    <div class="stepper" role="group">
      <button type="button" aria-label="Menej" disabled={value <= min} onClick={() => onChange(Math.max(min, value - step))}>−</button>
      <output>{format ? format(value) : value}</output>
      <button type="button" aria-label="Viac" disabled={value >= max} onClick={() => onChange(Math.min(max, value + step))}>+</button>
    </div>
  );
}

export function Segmented<T extends string | number>({ value, options, onChange }: {
  value: T; options: [T, string][]; onChange: (v: T) => void;
}) {
  return (
    <div class="seg-ctl" role="group">
      {options.map(([v, label]) => (
        <button type="button" aria-pressed={v === value} onClick={() => onChange(v)}>{label}</button>
      ))}
    </div>
  );
}

export function Photo({ src, country, alt = "", className }: { src: string | null; country: string; alt?: string; className?: string }) {
  const [failed, setFailed] = useState(!src);
  useEffect(() => setFailed(!src), [src]);
  const hue = useMemo(() => [...(country || "XX")].reduce((a, c) => a + c.charCodeAt(0) * 37, 0) % 360, [country]);
  if (failed) {
    return (
      <div class={`ph ${className ?? ""}`} style={{ "--ph-a": `hsl(${hue} 45% 78%)`, "--ph-b": `hsl(${(hue + 40) % 360} 35% 42%)` }} aria-hidden="true">
        {flag(country)}
      </div>
    );
  }
  return <img class={className} src={src!} alt={alt} loading="lazy" decoding="async" onError={() => setFailed(true)} />;
}

export interface SearchItem { code: string; name: string; country: string; kind: "city" | "country" | "airline"; hint?: string }

export function SearchBox({ items, placeholder, onPick }: { items: SearchItem[]; placeholder: string; onPick: (i: SearchItem) => void }) {
  const [q, setQ] = useState("");
  const [hl, setHl] = useState(0);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLInputElement>(null);
  const results = useMemo(() => {
    const n = normalize(q.trim());
    if (n.length < 2) return [];
    const hits = items.filter((i) => normalize(i.name).includes(n) || i.code.toLowerCase() === n);
    hits.sort((a, b) => Number(!normalize(a.name).startsWith(n)) - Number(!normalize(b.name).startsWith(n)) || a.name.localeCompare(b.name));
    return hits.slice(0, 10);
  }, [q, items]);
  const pick = (i?: SearchItem) => { if (!i) return; onPick(i); setQ(""); setOpen(false); ref.current?.blur(); };
  return (
    <div class="search">
      <input ref={ref} class="input" value={q} placeholder={placeholder} role="combobox" aria-expanded={open && results.length > 0}
        onInput={(e) => { setQ((e.target as HTMLInputElement).value); setHl(0); setOpen(true); }}
        onFocus={() => setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { setHl((h) => Math.min(h + 1, results.length - 1)); e.preventDefault(); }
          else if (e.key === "ArrowUp") { setHl((h) => Math.max(h - 1, 0)); e.preventDefault(); }
          else if (e.key === "Enter") { pick(results[hl]); e.preventDefault(); }
          else if (e.key === "Escape") setOpen(false);
        }} />
      {open && results.length > 0 && (
        <div class="results" role="listbox">
          {results.map((i, idx) => (
            <button type="button" role="option" aria-selected={idx === hl} onMouseDown={(e) => { e.preventDefault(); pick(i); }}>
              <span>{i.kind === "airline" ? "✈️" : flag(i.country)}</span> {i.name}
              <small>{i.hint ?? (i.kind === "country" ? "celá krajina" : i.code)}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
