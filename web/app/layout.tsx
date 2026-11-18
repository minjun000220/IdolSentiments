import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "아이돌 호감도 지도",
  description: "유튜브·디시인사이드 반응을 SBERT로 분석한 아이돌 그룹 멤버별 호감도와 관심도",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <header className="site-header">
          <div className="wrap">
            <Link href="/" className="brand">아이돌 호감도 지도</Link>
            <nav><Link href="/admin">관리</Link></nav>
          </div>
        </header>
        <div className="wrap">
          {children}
          <footer className="site-footer">
            유튜브 댓글과 디시인사이드 게시글을 문장 단위로 분석한 추정치입니다. 실제 인기나 여론 전체를 대표하지 않으며,
            수집 출처와 기간에 따라 달라집니다.
          </footer>
        </div>
      </body>
    </html>
  );
}
