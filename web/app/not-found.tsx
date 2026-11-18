import Link from "next/link";

export default function NotFound() {
  return (
    <main>
      <h1>아직 분석되지 않은 그룹입니다</h1>
      <p className="sub">분석된 그룹은 <Link href="/">처음 화면</Link>에서 볼 수 있습니다.</p>
    </main>
  );
}
