"use client";

import { useState } from "react";
import type { Member } from "@/lib/data";

const W = 480, H = 360, M = { t: 16, r: 20, b: 44, l: 44 };

function niceRange(vals: number[], pad = 6): [number, number] {
  const lo = Math.max(0, Math.floor((Math.min(...vals) - pad) / 10) * 10);
  const hi = Math.min(100, Math.ceil((Math.max(...vals) + pad) / 10) * 10);
  return lo === hi ? [Math.max(0, lo - 10), Math.min(100, hi + 10)] : [lo, hi];
}

/** 10 또는 20 단위의 깔끔한 눈금 */
function niceTicks([lo, hi]: [number, number]): number[] {
  const step = hi - lo > 50 ? 20 : 10;
  const out = [];
  for (let t = Math.ceil(lo / step) * step; t <= hi; t += step) out.push(t);
  return out;
}

const median = (v: number[]) => {
  const s = [...v].sort((a, b) => a - b);
  return s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2;
};

/** x = 관심도, y = 호감도. 멤버마다 같은 색(색으로 구분하지 않고 이름을 직접 표시). */
export default function QuadrantChart({ members }: { members: Member[] }) {
  const [hover, setHover] = useState<number | null>(null);
  if (members.length === 0) return null;

  const [y0, y1] = niceRange(members.map((m) => m.favor));
  const [x0, x1] = niceRange(members.map((m) => m.interest));
  const x = (v: number) => M.l + ((v - x0) / (x1 - x0)) * (W - M.l - M.r);
  const y = (v: number) => H - M.b - ((v - y0) / (y1 - y0)) * (H - M.t - M.b);
  const xm = median(members.map((m) => m.interest));
  const ym = median(members.map((m) => m.favor));
  const xticks = niceTicks([x0, x1]);
  const yticks = niceTicks([y0, y1]);
  const hm = hover !== null ? members[hover] : null;

  return (
    <div className="chart" onMouseLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="멤버별 호감도와 관심도 산점도">
        {yticks.map((t) => (
          <g key={`y${t}`}>
            <line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} stroke="var(--grid)" strokeWidth={1} />
            <text x={M.l - 8} y={y(t) + 4} textAnchor="end" className="tick">{Math.round(t)}</text>
          </g>
        ))}
        {xticks.map((t) => (
          <text key={`x${t}`} x={x(t)} y={H - M.b + 18} textAnchor="middle" className="tick">{Math.round(t)}</text>
        ))}
        <line x1={M.l} x2={W - M.r} y1={H - M.b} y2={H - M.b} stroke="var(--axis)" />
        {/* 중앙값 기준선 → 4분면 */}
        <line x1={x(xm)} x2={x(xm)} y1={M.t} y2={H - M.b} stroke="var(--axis)" strokeDasharray="4 4" />
        <line x1={M.l} x2={W - M.r} y1={y(ym)} y2={y(ym)} stroke="var(--axis)" strokeDasharray="4 4" />
        <text x={W - M.r - 4} y={M.t + 12} textAnchor="end" className="quad-label">인기</text>
        <text x={M.l + 4} y={M.t + 12} className="quad-label">조용한 호감</text>
        <text x={W - M.r - 4} y={H - M.b - 6} textAnchor="end" className="quad-label">화제성</text>
        <text x={M.l + 4} y={H - M.b - 6} className="quad-label">관심 부족</text>
        <text x={(M.l + W - M.r) / 2} y={H - 6} textAnchor="middle" className="axis-title">관심도 →</text>
        <text transform={`translate(12 ${(M.t + H - M.b) / 2}) rotate(-90)`} textAnchor="middle" className="axis-title">호감도 →</text>

        {members.map((m, i) => (
          <g key={m.name}>
            <circle cx={x(m.interest)} cy={y(m.favor)} r={hover === i ? 7 : 5.5}
              fill="var(--favor)" stroke="var(--surface)" strokeWidth={2} opacity={m.low_sample ? 0.45 : 1} />
            <text x={x(m.interest) + 9} y={y(m.favor) + (i % 2 ? 14 : -6)} className="dot-label">{m.name}</text>
            {/* 넓은 투명 히트 영역 */}
            <circle cx={x(m.interest)} cy={y(m.favor)} r={14} fill="transparent"
              onMouseEnter={() => setHover(i)} onFocus={() => setHover(i)} onBlur={() => setHover(null)}
              tabIndex={0} aria-label={`${m.name} 호감도 ${m.favor.toFixed(1)} 관심도 ${m.interest.toFixed(1)}`} />
          </g>
        ))}
      </svg>
      {hm && (
        <div className="tooltip" style={{ left: `${(x(hm.interest) / W) * 100}%`, top: `${(y(hm.favor) / H) * 100}%` }}>
          <b>{hm.name}</b><br />
          호감도 {hm.favor.toFixed(1)} · 관심도 {hm.interest.toFixed(1)}<br />
          언급 {hm.n.toLocaleString()}개{hm.low_sample ? " (적음)" : ""}
        </div>
      )}
    </div>
  );
}
