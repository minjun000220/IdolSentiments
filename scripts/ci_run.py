"""GitHub Actions 에서 실행하는 진입점.

환경변수:
  EVENT    workflow_dispatch | schedule
  GROUP    분석할 그룹 이름 (workflow_dispatch)
  MEMBERS  멤버 직접 지정, 쉼표 구분 (선택)
  REFRESH  "true" 면 그룹 자동 설정을 다시 만듦
  DAYS     분석 기간 (기본 90)
  YOUTUBE_API_KEY, WIKI_USER_AGENT
"""
import logging
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pipeline  # noqa: E402
from core.config import find_group, list_groups, load_settings, resolve_group  # noqa: E402
from discovery.builder import auto_setup  # noqa: E402
from report.web_export import export_result  # noqa: E402
from storage.db import DB  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("ci")


def run_one(group, settings, db, days):
    sources = ["dcinside"] + (["youtube"] if os.environ.get("YOUTUBE_API_KEY") else [])
    if "youtube" not in sources:
        log.warning("YOUTUBE_API_KEY 가 없어 유튜브 수집을 건너뜁니다 (GitHub Secrets 확인)")
    counts = pipeline.collect(group, settings, db, sources, days)
    log.info("[%s] 수집 %s", group.name, counts)
    result = pipeline.analyze(group, settings, db, days)
    path = export_result(result, group)
    log.info("[%s] 웹 데이터 저장: %s", group.name, path)


def main():
    settings = load_settings()
    if os.environ.get("WIKI_USER_AGENT"):
        settings["discovery"]["wiki_user_agent"] = os.environ["WIKI_USER_AGENT"]
    days = int(os.environ.get("DAYS") or settings["collect"]["days"])
    db = DB()

    if os.environ.get("EVENT") == "schedule":
        failed = []
        for g in list_groups():
            try:
                run_one(g, settings, db, days)
            except BaseException:            # 한 그룹 실패가 다른 그룹을 막지 않도록
                traceback.print_exc()
                failed.append(g.name)
        if failed:
            log.error("실패한 그룹: %s", failed)
        return

    query = (os.environ.get("GROUP") or "").strip()
    if not query:
        raise SystemExit("GROUP 이 비어 있습니다.")
    members = [m for m in (os.environ.get("MEMBERS") or "").split(",") if m.strip()]
    if members or (os.environ.get("REFRESH") == "true" and find_group(query)):
        group = auto_setup(query, settings, members_override=members or None, assume_yes=True)
    else:
        group = resolve_group(query, settings, assume_yes=True)
    run_one(group, settings, db, days)


if __name__ == "__main__":
    main()
