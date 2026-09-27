// Grafy vývoja ceny: malý na karte a väčší v detaile
import { dayMonth, euro } from "../lib/format";
import type { HistoryEntry } from "../types";

function series(h?: HistoryEntry): [string, number][] {
  if (!h) return [];
  return (h.live?.length ?? 0) >= 2 ? h.live! : (h.points ?? []);
}

export function Sparkline({ entry, limit }: { entry?: HistoryEntry; limit?: number | null }) {
  const pts = series(entry).slice(-45);
  if (pts.length < 2) return null;
  const W = 300, H = 38;
  const vals = pts.map((p) => p[1]);
  const lo = Math.min(...vals, limit ?? Infinity) * 0.96, hi = Math.max(...vals, limit ?? 0) * 1.04;
  const x = (i: number) => (i / (pts.length - 1)) * W;
  const y = (v: number) => H - ((v - lo) / (hi - lo || 1)) * H;
  const line = pts.map((p, i) => `${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" ");
  const last = pts[pts.length - 1];
  return (
    <div>
      <svg class="spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
        {limit ? <line x1="0" x2={W} y1={y(limit)} y2={y(limit)} stroke="var(--faint)" stroke-dasharray="3 4" vector-effect="non-scaling-stroke" /> : null}
        <polyline points={`0,${H} ${line} ${W},${H}`} fill="color-mix(in srgb, var(--good) 10%, transparent)" stroke="none" />
        <polyline points={line} fill="none" stroke="var(--good)" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round" stroke-linecap="round" />
        <circle cx={x(pts.length - 1)} cy={y(last[1])} r="3" fill="var(--good)" />
      </svg>
      <div class="spark-legend num"><span>{pts.length} dní · {euro(Math.min(...vals))}–{euro(Math.max(...vals))}</span>{limit ? <span>limit {euro(limit)}</span> : null}</div>
    </div>
  );
}

export function PriceChart({ entry, limit, typical }: { entry?: HistoryEntry; limit?: number | null; typical?: number | null }) {
  const pts = series(entry).slice(-90);
  if (pts.length < 2) return <p class="note-line" style={{ margin: 0 }}>História sa ešte zbiera – graf sa zobrazí po pár dňoch.</p>;
  const W = 460, H = 150, L = 42, B = 22, T = 10;
  const vals = pts.map((p) => p[1]);
  const refs = [limit, typical].filter((v): v is number => !!v);
  const lo = Math.min(...vals, ...refs) * 0.94, hi = Math.max(...vals, ...refs) * 1.04;
  const x = (i: number) => L + (i / (pts.length - 1)) * (W - L - 6);
  const y = (v: number) => T + (H - T - B) - ((v - lo) / (hi - lo || 1)) * (H - T - B);
  const line = pts.map((p, i) => `${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" ");
  const ticks = [lo, (lo + hi) / 2, hi].map((v) => Math.round(v / 10) * 10);
  return (
    <svg class="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Vývoj ceny">
      {ticks.map((t) => (
        <g>
          <line x1={L} x2={W} y1={y(t)} y2={y(t)} stroke="var(--line)" />
          <text x={L - 8} y={y(t) + 4} text-anchor="end" font-size="11" fill="var(--muted)">{t}</text>
        </g>
      ))}
      {typical ? <g><line x1={L} x2={W} y1={y(typical)} y2={y(typical)} stroke="var(--hot)" stroke-dasharray="4 4" /><text x={W - 4} y={y(typical) - 5} text-anchor="end" font-size="11" fill="var(--hot)">bežne {euro(typical)}</text></g> : null}
      {limit ? <g><line x1={L} x2={W} y1={y(limit)} y2={y(limit)} stroke="var(--ink)" stroke-opacity=".45" stroke-dasharray="2 4" /><text x={W - 4} y={y(limit) + 13} text-anchor="end" font-size="11" fill="var(--ink-2)">limit {euro(limit)}</text></g> : null}
      <polyline points={`${L},${H - B} ${line} ${x(pts.length - 1)},${H - B}`} fill="color-mix(in srgb, var(--good) 12%, transparent)" />
      <polyline points={line} fill="none" stroke="var(--good)" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round" />
      <circle cx={x(pts.length - 1)} cy={y(vals[vals.length - 1])} r="4" fill="var(--good)" stroke="var(--surface)" stroke-width="2" />
      <text x={L} y={H - 6} font-size="11" fill="var(--muted)">{dayMonth(pts[0][0])}</text>
      <text x={W - 4} y={H - 6} text-anchor="end" font-size="11" fill="var(--muted)">{dayMonth(pts[pts.length - 1][0])}</text>
    </svg>
  );
}
