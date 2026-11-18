"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

type Item = { key: string; name: string; aliases: string[] };

const norm = (s: string) => s.replace(/\s+/g, "").toLowerCase();

export default function SearchBox({ groups }: { groups: Item[] }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [miss, setMiss] = useState<string | null>(null);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const n = norm(q);
    if (!n) return;
    const hit =
      groups.find((g) => norm(g.key) === n || norm(g.name) === n || g.aliases.some((a) => norm(a) === n)) ??
      groups.find((g) => norm(g.name).includes(n) || g.aliases.some((a) => norm(a).includes(n)));
    if (hit) router.push(`/g/${encodeURIComponent(hit.key)}`);
    else setMiss(q.trim());
  }

  return (
    <form onSubmit={submit}>
      <div className="search">
        <input
          value={q}
          onChange={(e) => { setQ(e.target.value); setMiss(null); }}
          placeholder="그룹 이름 (예: 아일릿, BTS, NewJeans)"
          aria-label="그룹 이름 검색"
          list="group-names"
        />
        <button className="btn" type="submit">보기</button>
      </div>
      <datalist id="group-names">
        {groups.map((g) => <option key={g.key} value={g.name} />)}
      </datalist>
      {miss && (
        <div className="notice">
          ‘{miss}’ 결과가 없습니다.
        </div>
      )}
    </form>
  );
}
