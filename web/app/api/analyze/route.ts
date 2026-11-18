import { github, isAdmin, unauthorized, workflowPath } from "@/lib/server";

export const dynamic = "force-dynamic";

const CLEAN = /[\u0000-\u001f\u007f<>`$\\]/g;

/** 관리자 전용: GitHub Actions 분석 워크플로 실행 */
export async function POST(req: Request) {
  if (!isAdmin(req)) return unauthorized();

  let body: { group?: unknown; members?: unknown; days?: unknown; refresh?: unknown };
  try {
    body = await req.json();
  } catch {
    return Response.json({ error: "잘못된 요청" }, { status: 400 });
  }
  const group = String(body.group ?? "").replace(CLEAN, "").trim();
  const members = String(body.members ?? "").replace(CLEAN, "").trim();
  const days = Number(body.days ?? 90);
  if (!group || group.length > 40) return Response.json({ error: "그룹 이름은 1~40자" }, { status: 400 });
  if (members.length > 300) return Response.json({ error: "멤버 목록이 너무 깁니다" }, { status: 400 });
  if (!Number.isInteger(days) || days < 7 || days > 365)
    return Response.json({ error: "기간은 7~365일" }, { status: 400 });

  try {
    const r = await github(`${workflowPath}/dispatches`, {
      method: "POST",
      body: JSON.stringify({
        ref: "main",
        inputs: { group, members, days: String(days), refresh: body.refresh ? "true" : "false" },
      }),
    });
    if (r.status !== 204) {
      const text = await r.text();
      return Response.json({ error: `GitHub 응답 ${r.status}: ${text.slice(0, 200)}` }, { status: 502 });
    }
    return Response.json({ ok: true });
  } catch (e) {
    return Response.json({ error: (e as Error).message }, { status: 500 });
  }
}
