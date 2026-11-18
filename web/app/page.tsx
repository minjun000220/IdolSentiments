import Link from "next/link";
import SearchBox from "@/components/SearchBox";
import { formatDay, listGroups } from "@/lib/data";

export const dynamic = "force-static";

export default function Home() {
  const groups = listGroups();
  return (
    <main>
      <section className="hero">
        <h1>아이돌 그룹 멤버별 호감도 · 관심도</h1>
        <p className="sub">
          유튜브 댓글과 디시인사이드 게시글을 문장 단위로 나누고, SBERT 임베딩으로 긍정·부정을 분석했습니다.
          <br />
          <b>호감도</b>는 긍정 반응만, <b>관심도</b>는 긍정과 부정을 합친 감정 반응의 양입니다.
        </p>
        <SearchBox groups={groups.map(({ key, name, aliases }) => ({ key, name, aliases }))} />
      </section>

      <section style={{ marginTop: 32 }}>
        <h2>분석된 그룹 {groups.length > 0 && <span className="muted">{groups.length}</span>}</h2>
        {groups.length === 0 ? (
          <div className="notice">아직 분석된 그룹이 없습니다.</div>
        ) : (
          <div className="grid">
            {groups.map((g) => (
              <Link key={g.key} href={`/g/${encodeURIComponent(g.key)}`} className="gcard">
                <div className="name">{g.name}</div>
                <div className="meta">
                  멤버 {g.members.length}명 · {formatDay(g.updated_at)} 갱신
                </div>
                <div className="nums">
                  <div>
                    <div className="num-label">그룹 호감도</div>
                    <div className="num-value">{g.favor.toFixed(1)}</div>
                  </div>
                  <div>
                    <div className="num-label">호감도 1위</div>
                    <div className="num-value" style={{ fontSize: 16, paddingTop: 4 }}>{g.top_member ?? "-"}</div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
