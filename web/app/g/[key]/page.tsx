import type { Metadata } from "next";
import { notFound } from "next/navigation";
import QuadrantChart from "@/components/QuadrantChart";
import TrendChart from "@/components/TrendChart";
import { SOURCE_NAME, formatDate, getGroup, listGroups } from "@/lib/data";

export const dynamicParams = false;

export function generateStaticParams() {
  return listGroups().map((g) => ({ key: g.key }));
}

type Props = { params: Promise<{ key: string }> };

function decode(k: string) {
  try { return decodeURIComponent(k); } catch { return k; }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const g = getGroup(decode((await params).key));
  return g ? { title: `${g.name} 멤버별 호감도 · 아이돌 호감도 지도` } : {};
}

const signed = (v: number) => (v > 0 ? "+" : "") + v.toFixed(2);

function Bar({ value, color }: { value: number; color: string }) {
  return (
    <div className="bar">
      <div className="track"><div className="fill" style={{ width: `${Math.max(2, value)}%`, background: color }} /></div>
      <span className="v">{value.toFixed(1)}</span>
    </div>
  );
}

export default async function GroupPage({ params }: Props) {
  const g = getGroup(decode((await params).key));
  if (!g) notFound();
  const gr = g.group;

  return (
    <main>
      <h1>{g.name}</h1>
      <p className="sub">
        {g.aliases.filter((a) => a !== g.name).slice(0, 4).join(" · ")}
        {g.aliases.length > 1 && " — "}
        최근 {g.days}일 · 언급 {g.counts.mentions.toLocaleString()}개 · {formatDate(g.updated_at)} 갱신
      </p>

      <div className="kpis">
        <div className="kpi">
          <div className="label"><span className="swatch" style={{ background: "var(--favor)" }} />그룹 호감도</div>
          <div className="value">{gr.favor.toFixed(1)}</div>
        </div>
        <div className="kpi">
          <div className="label"><span className="swatch" style={{ background: "var(--interest)" }} />그룹 관심도</div>
          <div className="value">{gr.interest == null ? "—" : gr.interest.toFixed(0)}</div>
        </div>
        <div className="kpi">
          <div className="label">순호감</div>
          <div className={`value ${gr.net >= 0 ? "pos" : "neg"}`}>{signed(gr.net)}</div>
        </div>
        <div className="kpi">
          <div className="label">부정 비율</div>
          <div className="value">{Math.round(gr.controversy * 100)}%</div>
        </div>
      </div>

      <section className="card">
        <div className="card-head">
          <h2>멤버별 순위</h2>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>멤버</th>
                <th className="barcell">호감도</th>
                <th className="barcell">관심도</th>
                <th className="num">순호감</th>
                <th className="num">언급</th>
                <th className="num">순위 구간</th>
                <th>유형</th>
              </tr>
            </thead>
            <tbody>
              {g.members.map((m) => (
                <tr key={m.name}>
                  <td className="rank">{m.rank}</td>
                  <td className="mname">{m.name}{m.low_sample && <span className="warn">표본 적음</span>}</td>
                  <td className="barcell"><Bar value={m.favor} color="var(--favor)" /></td>
                  <td className="barcell"><Bar value={m.interest} color="var(--interest)" /></td>
                  <td className={`num ${m.net >= 0 ? "pos" : "neg"}`}>{signed(m.net)}</td>
                  <td className="num">{m.n.toLocaleString()}</td>
                  <td className="num">{m.rank_lo === m.rank_hi ? m.rank_lo : `${m.rank_lo}–${m.rank_hi}`}위</td>
                  <td><span className="badge">{m.quadrant}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className={g.history.length >= 2 ? "charts" : undefined}>
        <section className="card">
          <div className="card-head"><h2>호감도 × 관심도</h2></div>
          <QuadrantChart members={g.members} />
        </section>
        {g.history.length >= 2 && (
          <section className="card">
            <div className="card-head"><h2>그룹 호감도 추이</h2></div>
            <TrendChart history={g.history} />
          </section>
        )}
      </div>

      <section className="card">
        <div className="card-head"><h2>출처별 반응</h2></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>출처</th><th className="num">언급</th><th className="num">긍정 비율</th><th className="num">순호감</th></tr></thead>
            <tbody>
              {Object.entries(g.by_source).map(([k, v]) => (
                <tr key={k}>
                  <td>{SOURCE_NAME[k] ?? k}</td>
                  <td className="num">{v.n.toLocaleString()}</td>
                  <td className="num">{Math.round(v.pos_ratio * 100)}%</td>
                  <td className={`num ${v.net >= 0 ? "pos" : "neg"}`}>{signed(v.net)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {g.members.some((m) => m.examples.length) && (
        <section className="card">
          <div className="card-head"><h2>긍정 반응</h2></div>
          <div className="quotes">
            {g.members.filter((m) => m.examples.length).map((m) => (
              <div className="quote" key={m.name}>
                <div className="who">{m.name}</div>
                {m.examples.map((x, i) => <p key={i}>“{x}”</p>)}
              </div>
            ))}
          </div>
        </section>
      )}

    </main>
  );
}
