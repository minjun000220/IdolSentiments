"use client";

import { useState } from "react";
import type { HistoryPoint } from "@/lib/data";

const W = 480, H = 220, M = { t: 16, r: 16, b: 32, l: 40 };

/** 그룹 호감도 추이 (단일 계열 + 십자선 툴팁) */
export default function TrendChart({ history }: { history: HistoryPoint[] }) {
  const [hover, setHover] = useState<number | null>(null);
  if (history.length < 2) {
    return <p className="muted small">추이는 두 번 이상 분석된 뒤부터 표시됩니다. (매일 자동 갱신)</p>;
  }
  const vals = history.map((h) => h.favor);
  const lo = Math.max(0, Math.floor((Math.min(...vals) - 5) / 5) * 5);
  const hi = Math.min(100, Math.ceil((Math.max(...vals) + 5) / 5) * 5);
  const x = (i: number) => M.l + (i / (history.length - 1)) * (W - M.l - M.r);
  const y = (v: number) => H - M.b - ((v - lo) / (hi - lo)) * (H - M.t - M.b);
  const path = history.map((h, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(h.favor).toFixed(1)}`).join("");
  const ticks = [lo, (lo + hi) / 2, hi];
  const label = (d: string) => `${Number(d.slice(5, 7))}/${Number(d.slice(8, 10))}`;
  const step = Math.max(1, Math.ceil(history.length / 6));

  function move(e: React.MouseEvent<SVGRectElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * (W - M.l - M.r);
    setHover(Math.max(0, Math.min(history.length - 1, Math.round((px / (W - M.l - M.r)) * (history.length - 1)))));
  }
  const h = hover !== null ? history[hover] : null;

  return (
    <div className="chart" onMouseLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="그룹 호감도 추이">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
            <text x={M.l - 8} y={y(t) + 4} textAnchor="end" className="tick">{Math.round(t)}</text>
          </g>
        ))}
        {history.map((p, i) => (i % step === 0 || i === history.length - 1) && (
          <text key={p.date} x={x(i)} y={H - 10} textAnchor="middle" className="tick">{label(p.date)}</text>
        ))}
        <path d={path} fill="none" stroke="var(--favor)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {h && hover !== null && (
          <>
            <line x1={x(hover)} x2={x(hover)} y1={M.t} y2={H - M.b} stroke="var(--axis)" />
            <circle cx={x(hover)} cy={y(h.favor)} r={5} fill="var(--favor)" stroke="var(--surface)" strokeWidth={2} />
          </>
        )}
        <rect x={M.l} y={M.t} width={W - M.l - M.r} height={H - M.t - M.b} fill="transparent" onMouseMove={move} />
      </svg>
      {h && hover !== null && (
        <div className="tooltip" style={{ left: `${(x(hover) / W) * 100}%`, top: `${(y(h.favor) / H) * 100}%` }}>
          <b>{h.date}</b><br />그룹 호감도 {h.favor.toFixed(1)}
        </div>
      )}
    </div>
  );
}
