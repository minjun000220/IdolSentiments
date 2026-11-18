import { github, isAdmin, unauthorized, workflowPath } from "@/lib/server";

export const dynamic = "force-dynamic";

type Run = {
  id: number;
  display_title: string;
  status: string;
  conclusion: string | null;
  created_at: string;
  updated_at: string;
  html_url: string;
  event: string;
};

/** 관리자 전용: 최근 분석 실행 상태 */
export async function GET(req: Request) {
  if (!isAdmin(req)) return unauthorized();
  try {
    const r = await github(`${workflowPath}/runs?per_page=10`);
    if (!r.ok) return Response.json({ error: `GitHub 응답 ${r.status}` }, { status: 502 });
    const data = (await r.json()) as { workflow_runs: Run[] };
    return Response.json({
      runs: data.workflow_runs.map((x) => ({
        id: x.id,
        title: x.display_title,
        status: x.status,
        conclusion: x.conclusion,
        created_at: x.created_at,
        updated_at: x.updated_at,
        url: x.html_url,
        event: x.event,
      })),
    });
  } catch (e) {
    return Response.json({ error: (e as Error).message }, { status: 500 });
  }
}
