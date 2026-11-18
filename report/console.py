from rich.console import Console
from rich.table import Table

SRC_NAME = {"youtube": "유튜브", "dcinside": "디시"}


def print_report(r: dict, show_examples: bool = True) -> None:
    c = Console()
    g = r["group"]
    gi = f"{g['interest']:.1f} (하루 반응 {g['daily_energy']:,.0f})"
    c.print(f"\n[bold]{r['group_name']}[/bold]  최근 {r['days']}일  "
            f"(원문 {r['n_docs']:,} · 문장 {r['n_sentences']:,} · 언급 {r['n_mentions']:,} · 감성모델 {r['sentiment_model']})")
    c.print(f"  그룹 호감도 [bold green]{g['favor']:.1f}[/]   그룹 관심도 [bold cyan]{gi}[/]   "
            f"논란도 {g['controversy']:.2f}   순호감 {g['net']:+.2f}")
    if g.get("favor_direct") is not None:
        c.print(f"  └ 그룹 직접 언급 {g['favor_direct']:.1f} (n={int(g['n_direct'])}) / 멤버 가중평균 {g['favor_members']:.1f}")

    t = Table(title="멤버별 순위 (호감도 기준)", show_lines=False)
    for col, j in [("순위", "right"), ("멤버", "left"), ("호감도", "right"), ("관심도", "right"),
                   ("논란도", "right"), ("순호감", "right"), ("언급수", "right"), ("95% 순위구간", "center"),
                   ("유형", "left")]:
        t.add_column(col, justify=j)
    for m in r["members"]:
        warn = " ⚠" if m["low_sample"] else ""
        t.add_row(str(m["rank"]), m["name"] + warn, f"{m['favor']:.1f}", f"{m['interest']:.1f}",
                  f"{m['controversy']:.2f}", f"{m['net']:+.2f}", f"{m['n']:,}",
                  f"{m['rank_lo']}–{m['rank_hi']}", m["quadrant"])
    c.print(t)
    if any(m["low_sample"] for m in r["members"]):
        c.print("  ⚠ 언급 수가 적어 순위가 불안정합니다.")

    s = Table(title="출처별 반응")
    for col in ("출처", "언급수", "긍정 비율", "순호감", "논란도"):
        s.add_column(col, justify="right")
    for k, v in r["by_source"].items():
        s.add_row(SRC_NAME.get(k, k), f"{v['n']:,}", f"{v['pos_ratio']:.2f}", f"{v['net']:+.2f}",
                  f"{v['controversy']:.2f}")
    c.print(s)

    if show_examples:
        c.print("[bold]대표 문장[/bold] (가중치 × 확률 상위, 분석이 맞는지 확인용)")
        for m in r["members"]:
            c.print(f"  [bold]{m['name']}[/]")
            for x in m["examples"]["pos"]:
                c.print(f"    [green]+[/] {x}")
            for x in m["examples"]["neg"]:
                c.print(f"    [red]-[/] {x}")
    c.print(f"\n결과 파일: {r['out_dir']}" + (f"\n차트: {r['chart']}" if r.get("chart") else ""))
