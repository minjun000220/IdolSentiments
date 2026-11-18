import fs from "node:fs";
import path from "node:path";

export type Member = {
  rank: number;
  name: string;
  favor: number;
  interest: number;
  intensity: number;
  controversy: number;
  net: number;
  n: number;
  share: number;
  rank_lo: number;
  rank_hi: number;
  favor_lo: number;
  favor_hi: number;
  low_sample: boolean;
  quadrant: string;
  mention_share?: number;
  examples: string[];
};

export type HistoryPoint = {
  date: string;
  favor: number;
  interest: number | null;
  members: Record<string, number>;
};

export type GroupPage = {
  key: string;
  name: string;
  aliases: string[];
  updated_at: string;
  days: number;
  sentiment_model: string;
  counts: { docs: number; sentences: number; mentions: number };
  group: {
    favor: number;
    favor_direct: number | null;
    favor_members: number;
    interest: number | null;
    mentions_per_day?: number;
    controversy: number;
    net: number;
    n: number;
  };
  members: Member[];
  by_source: Record<string, { n: number; pos_ratio: number; net: number; controversy: number }>;
  history: HistoryPoint[];
};

export type GroupSummary = {
  key: string;
  name: string;
  aliases: string[];
  updated_at: string;
  favor: number;
  interest: number | null;
  members: string[];
  top_member: string | null;
  mentions: number;
};

const DATA_DIR = path.join(process.cwd(), "public", "data");

function readJson<T>(file: string, fallback: T): T {
  try {
    return JSON.parse(fs.readFileSync(path.join(DATA_DIR, file), "utf-8")) as T;
  } catch {
    return fallback;
  }
}

export function listGroups(): GroupSummary[] {
  return readJson<{ groups: GroupSummary[] }>("index.json", { groups: [] }).groups;
}

export function getGroup(key: string): GroupPage | null {
  if (!/^[\p{L}\p{N}_-]+$/u.test(key)) return null; // 경로 조작 방지
  return readJson<GroupPage | null>(path.join("groups", `${key}.json`), null);
}

export const SOURCE_NAME: Record<string, string> = { youtube: "유튜브", dcinside: "디시인사이드" };

export function formatDate(iso: string): string {
  const d = new Date(iso);
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

export function formatDay(iso: string): string {
  return new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", month: "long", day: "numeric" }).format(new Date(iso));
}
