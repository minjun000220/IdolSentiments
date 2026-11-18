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
  const anyLow = g.members.some((m) => m.low_sample);

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
          <div className="hint">0~100, 긍정 반응만</div>
        </div>
        <div className="kpi">
          <div className="label"><span className="swatch" style={{ background: "var(--interest)" }} />그룹 관심도</div>
          <div className="value">{gr.interest == null ? "—" : gr.interest.toFixed(0)}</div>
          <div className="hint">{gr.interest == null ? "비교할 그룹이 더 필요" : "분석된 그룹 중 백분위"}</div>
        </div>
        <div className="kpi">
          <div className="label">순호감</div>
          <div className={`value ${gr.net >= 0 ? "pos" : "neg"}`}>{signed(gr.net)}</div>
          <div className="hint">(긍정−부정)/(긍정+부정)</div>
        </div>
        <div className="kpi">
          <div className="label">부정 비율</div>
          <div className="value">{Math.round(gr.controversy * 100)}%</div>
          <div className="hint">감정 반응 중 부정</div>
        </div>
      </div>

      <section className="card">
        <div className="card-head">
          <h2>멤버별 순위</h2>
          <span className="muted small">호감도 순 · 95% 순위 구간은 표본 재추출로 계산</span>
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
        {anyLow && <p className="muted small" style={{ marginBottom: 0 }}>표본 적음: 언급이 30개 미만이라 순위가 불안정합니다.</p>}
      </section>

      <div className="charts">
        <section className="card">
          <div className="card-head"><h2>호감도 × 관심도</h2></div>
          <QuadrantChart members={g.members} />
          <p className="muted small" style={{ margin: "8px 0 0" }}>점선은 멤버 중앙값. 흐린 점은 표본이 적은 멤버.</p>
        </section>
        <section className="card">
          <div className="card-head"><h2>그룹 호감도 추이</h2></div>
          <TrendChart history={g.history} />
        </section>
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
          <div className="card-head"><h2>멤버별 긍정 반응 예시</h2><span className="muted small">가중치가 높은 문장</span></div>
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

      <section className="card">
        <details className="method">
          <summary>점수는 어떻게 계산하나요?</summary>
          <ul>
            <li>게시글과 댓글을 문장으로 나누고, 멤버 이름(별명·본명 포함)이 나온 문장을 그 멤버에게 연결합니다. 이름이 없으면 앞 문장이나 영상·글 제목의 멤버를 낮은 신뢰도로 연결합니다.</li>
            <li>문장마다 SBERT 임베딩으로 긍정·중립·부정 확률을 계산합니다 (감성 모델: <code>{g.sentiment_model}</code>).</li>
            <li>문장 가중치 = 출처 가중치 × 좋아요 수(로그) × 최근성(반감기 30일) × 연결 신뢰도 × 관련성.</li>
            <li><b>호감도</b> = 0.7 × 평균 긍정 확률(표본이 적으면 그룹 평균 쪽으로 보정) + 0.3 × 긍정 반응 총량(1위 대비).</li>
            <li><b>관심도</b> = 긍정+부정 반응 총량의 로그 값을 그룹 내 1위 대비로 환산. 중립 문장은 제외합니다.</li>
            <li>같은 문장 복붙·도배는 임베딩 유사도로 걸러냅니다.</li>
          </ul>
        </details>
      </section>
    </main>
  );
}
