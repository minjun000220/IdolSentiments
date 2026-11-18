import { createHash, timingSafeEqual } from "node:crypto";

/** 관리자 비밀번호 확인 (길이 차이로 정보가 새지 않도록 해시 후 비교) */
export function isAdmin(req: Request): boolean {
  const expected = process.env.ADMIN_PASSWORD;
  if (!expected) return false;
  const given = req.headers.get("x-admin-password") ?? "";
  const a = createHash("sha256").update(given).digest();
  const b = createHash("sha256").update(expected).digest();
  return timingSafeEqual(a, b);
}

const WORKFLOW = "analyze.yml";

function repo(): string {
  const r = process.env.GITHUB_REPO;
  if (!r || !/^[\w.-]+\/[\w.-]+$/.test(r)) throw new Error("GITHUB_REPO 환경변수가 없습니다");
  return r;
}

export async function github(path: string, init?: RequestInit): Promise<Response> {
  const token = process.env.GITHUB_TOKEN;
  if (!token) throw new Error("GITHUB_TOKEN 환경변수가 없습니다");
  return fetch(`https://api.github.com/repos/${repo()}${path}`, {
    ...init,
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
    },
    cache: "no-store",
  });
}

export const workflowPath = `/actions/workflows/${WORKFLOW}`;

export function unauthorized() {
  return Response.json({ error: "비밀번호가 틀렸습니다" }, { status: 401 });
}
