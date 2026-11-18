"use client";

import { useCallback, useEffect, useState } from "react";

type Run = {
  id: number; title: string; status: string; conclusion: string | null;
  created_at: string; updated_at: string; url: string; event: string;
};

const KEY = "idol-admin-pw";

function readPw(): string {
  try { return sessionStorage.getItem(KEY) ?? ""; } catch { return ""; }
}
function savePw(v: string) {
  try { sessionStorage.setItem(KEY, v); } catch { /* 저장 불가 환경 */ }
}

function statusOf(r: Run): { cls: string; text: string } {
  if (r.status !== "completed") return { cls: "run", text: r.status === "queued" ? "대기 중" : "분석 중" };
  if (r.conclusion === "success") return { cls: "ok", text: "완료" };
  return { cls: "fail", text: r.conclusion === "cancelled" ? "취소됨" : "실패" };
}

const fmt = (iso: string) =>
  new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(iso));

export default function Admin() {
  const [pw, setPw] = useState("");
  const [group, setGroup] = useState("");
  const [members, setMembers] = useState("");
  const [days, setDays] = useState(90);
  const [refresh, setRefresh] = useState(false);
  const [msg, setMsg] = useState<{ text: string; error?: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [runs, setRuns] = useState<Run[] | null>(null);

  useEffect(() => setPw(readPw()), []);

  const loadRuns = useCallback(async (password: string) => {
    if (!password) return;
    const r = await fetch("/api/runs", { headers: { "x-admin-password": password } });
    const d = await r.json();
    if (r.ok) setRuns(d.runs);
    else { setRuns(null); setMsg({ text: d.error, error: true }); }
  }, []);

  useEffect(() => { if (pw) loadRuns(pw); }, [pw, loadRuns]);

  // 진행 중인 분석이 있으면 15초마다 상태 확인
  useEffect(() => {
    if (!pw || !runs?.some((r) => r.status !== "completed")) return;
    const t = setInterval(() => loadRuns(pw), 15000);
    return () => clearInterval(t);
  }, [pw, runs, loadRuns]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setMsg(null);
    try {
      const r = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-admin-password": pw },
        body: JSON.stringify({ group, members, days, refresh }),
      });
      const d = await r.json();
      if (!r.ok) { setMsg({ text: d.error, error: true }); return; }
      savePw(pw);
      setMsg({ text: `‘${group}’ 분석을 요청했습니다. 보통 10~40분 걸리고, 끝나면 1~2분 뒤 사이트에 반영됩니다.` });
      setGroup(""); setMembers(""); setRefresh(false);
      setTimeout(() => loadRuns(pw), 4000);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>분석 관리</h1>
      <p className="sub">새 그룹 분석 요청은 관리자만 할 수 있습니다. 결과는 누구나 볼 수 있습니다.</p>

      <section className="card">
        <form className="form" onSubmit={submit}>
          <label>
            관리자 비밀번호
            <input type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="current-password" required />
          </label>
          <label>
            그룹 이름
            <input type="text" value={group} onChange={(e) => setGroup(e.target.value)} placeholder="예: 아일릿, BTS" maxLength={40} required />
          </label>
          <label>
            멤버 직접 지정 <span className="muted small">(선택 · 비우면 위키데이터에서 자동으로 찾음)</span>
            <input type="text" value={members} onChange={(e) => setMembers(e.target.value)} placeholder="예: 윤아,민주,모카,원희,이로하" maxLength={300} />
          </label>
          <div className="row">
            <label style={{ width: 140 }}>
              분석 기간 (일)
              <input type="number" min={7} max={365} value={days} onChange={(e) => setDays(Number(e.target.value))} />
            </label>
            <label className="check">
              <input type="checkbox" checked={refresh} onChange={(e) => setRefresh(e.target.checked)} />
              그룹 설정(멤버·갤러리) 다시 만들기
            </label>
          </div>
          <div className="row">
            <button className="btn" type="submit" disabled={busy || !pw || !group}>{busy ? "요청 중…" : "분석 요청"}</button>
            <button className="btn secondary" type="button" onClick={() => { savePw(pw); loadRuns(pw); }} disabled={!pw}>상태 새로고침</button>
          </div>
        </form>
        {msg && <div className={`notice${msg.error ? " error" : ""}`}>{msg.text}</div>}
      </section>

      {runs && (
        <section className="card">
          <div className="card-head"><h2>최근 실행</h2><span className="muted small">진행 중이면 15초마다 갱신</span></div>
          {runs.length === 0 ? <p className="muted">아직 실행 기록이 없습니다.</p> : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>작업</th><th>상태</th><th>시작</th><th></th></tr></thead>
                <tbody>
                  {runs.map((r) => {
                    const s = statusOf(r);
                    return (
                      <tr key={r.id}>
                        <td>{r.title}</td>
                        <td><span className={`status ${s.cls}`}><span className="dot" />{s.text}</span></td>
                        <td className="muted">{fmt(r.created_at)}</td>
                        <td><a href={r.url} target="_blank" rel="noreferrer" className="small">로그</a></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
