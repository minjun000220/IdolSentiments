"""아이돌 그룹 멤버별 호감도·관심도 분석기

사용법:
  python main.py run 아일릿                     # 처음 보는 그룹이면 멤버/갤러리 자동 설정 → 수집 + 분석
  python main.py setup 아일릿 --refresh         # 그룹 설정 다시 만들기
  python main.py setup 아일릿 --members 윤아,민주,모카,원희,이로하   # 멤버 직접 지정
  python main.py collect 뉴진스 --sources youtube,dcinside
  python main.py analyze 뉴진스 --days 90 --plot
  python main.py label 뉴진스 --n 200           # 감성 라벨링 (SetFit 학습용)
  python main.py train                          # SetFit 학습
  python main.py groups                         # 등록된 그룹 목록
"""
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import find_group, list_groups, resolve_group, load_settings  # noqa: E402
from storage.db import DB  # noqa: E402


def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    p = argparse.ArgumentParser(description="아이돌 그룹 멤버별 호감도·관심도 분석기")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("run", "collect", "analyze"):
        sp = sub.add_parser(name)
        sp.add_argument("group", help="그룹 이름 (예: 뉴진스, NewJeans)")
        sp.add_argument("--days", type=int, default=None)
        if name in ("run", "collect"):
            sp.add_argument("--sources", default="youtube,dcinside")
        if name in ("run", "analyze"):
            sp.add_argument("--plot", action="store_true", help="4분면 차트 저장")
            sp.add_argument("--no-examples", action="store_true")
    st = sub.add_parser("setup", help="그룹 이름으로 멤버/갤러리를 자동으로 찾아 설정 파일 생성")
    st.add_argument("group")
    st.add_argument("--members", default=None, help="멤버를 직접 지정 (쉼표 구분)")
    st.add_argument("--refresh", action="store_true", help="이미 있는 설정을 다시 만들기")
    lp = sub.add_parser("label")
    lp.add_argument("group")
    lp.add_argument("--n", type=int, default=200)
    sub.add_parser("train")
    sub.add_parser("groups")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("-y", "--yes", action="store_true", help="자동 설정 결과를 확인 없이 저장")
    args = p.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    settings = load_settings()
    db = DB()

    if args.cmd == "groups":
        for g in list_groups():
            print(f"{g.key:15s} {g.name:15s} 멤버: {', '.join(g.member_names)}  | 수집: {db.count_docs(g.key)}")
        return

    if args.cmd == "train":
        from training.train_setfit import train
        train(settings, db)
        return

    if args.cmd == "setup":
        from discovery.builder import auto_setup
        existing = find_group(args.group)
        if existing and not args.refresh and not args.members:
            print(f"이미 설정이 있습니다: config/groups/{existing.key}.yaml (다시 만들려면 --refresh)")
            return
        members = args.members.split(",") if args.members else None
        auto_setup(args.group, settings, members_override=members, assume_yes=args.yes)
        return

    group = resolve_group(args.group, settings, assume_yes=args.yes)

    if args.cmd == "label":
        from training.label_tool import run_labeling
        run_labeling(group, settings, db, args.n)
        return

    import pipeline
    if args.cmd in ("run", "collect"):
        sources = [s.strip() for s in args.sources.split(",") if s.strip()]
        counts = pipeline.collect(group, settings, db, sources, args.days)
        logging.info("수집 완료: %s / DB 누적: %s", counts, db.count_docs(group.key))
    if args.cmd in ("run", "analyze"):
        from report.console import print_report
        result = pipeline.analyze(group, settings, db, args.days, plot=args.plot)
        print_report(result, show_examples=not args.no_examples)


if __name__ == "__main__":
    main()
