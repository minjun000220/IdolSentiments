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
        <SearchBox groups={groups.map(({ key, name, aliases }) => ({ key, name, aliases }))} />
      </section>

      <section style={{ marginTop: 32 }}>
        <h2>분석된 그룹 {groups.length > 0 && <span className="muted">{groups.length}</span>}</h2>
        {groups.length === 0 ? (
          <div className="notice">분석된 그룹 없음</div>
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
