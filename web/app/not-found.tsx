import Link from "next/link";

export default function NotFound() {
  return (
    <main>
      <h1>결과가 없습니다</h1>
      <p className="sub"><Link href="/">처음으로</Link></p>
    </main>
  );
}
