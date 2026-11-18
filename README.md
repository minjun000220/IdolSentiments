# 아이돌 그룹 멤버별 호감도·관심도 분석기

그룹 이름만 입력하면 유튜브와 디시인사이드의 반응을 모아 SBERT로 문장 감성을 분석하고, 멤버별 **호감도**(긍정만)와 **관심도**(긍정+부정)를 계산합니다.

## 설치

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # YOUTUBE_API_KEY 입력
```

`config/settings.yaml`의 `discovery.wiki_user_agent`에 연락처(메일 또는 깃허브 주소)를 넣어주세요. 위키미디어 API 정책입니다.

## 실행

```bash
python main.py run 아일릿 --plot      # 처음 보는 그룹이면 자동 설정 → 수집 → 분석
python main.py run BTS                # 영문/한글/별칭 모두 가능
python main.py groups                 # 저장된 그룹과 수집량
```

결과는 `outputs/<그룹>_<시각>/`에 저장됩니다.
- `scores.csv`: 멤버별 점수
- `mentions.csv`: 문장별 감성 확률과 가중치. 분석이 맞는지 **반드시 직접 훑어보세요**
- `summary.json`, `quadrant.png`

## 그룹 자동 설정

처음 보는 그룹 이름을 입력하면:
1. **위키데이터**에서 그룹 정식명, 별칭, **현재 멤버**(탈퇴 멤버 제외)와 멤버별 한/영 이름·본명을 찾습니다. 실패하면 한국어 위키백과 인포박스를 읽습니다.
2. **디시 갤러리 검색**으로 이름이 정확히 같은 그룹 갤러리를 찾습니다.
3. 결과를 보여주고, 확인을 받으면 `config/groups/<키>.yaml`로 저장합니다. 이후에는 저장된 파일을 씁니다.

```bash
python main.py setup 아일릿 --refresh                         # 멤버 변동 후 다시 만들기
python main.py setup 신인그룹 --members 가나,다라,마바          # 위키에 없을 때 직접 지정
python main.py -y run 아일릿                                   # 확인 없이 바로 저장
```

- 자동 설정은 틀릴 수 있으니 처음 한 번은 출력된 멤버와 갤러리를 확인하세요. yaml 파일을 직접 고쳐도 됩니다.
- 1~2글자 이름(예: 진, 뷔, 민주, 모카)은 일반 단어와 겹칠 수 있습니다. 한 글자 이름은 조사가 붙거나 띄어 쓴 경우만 인식합니다("진짜", "뷔페"는 제외). 그래도 오탐이 보이면 `exclude_patterns`에 추가하세요.
- 멤버 개인 갤러리도 수집하려면 `discovery.include_member_galleries: true`로 바꾸세요. 팬 갤러리라 긍정 쪽으로 치우칠 수 있습니다.

## 출처별 수집 방식

| 출처 | 방식 | 비고 |
|---|---|---|
| 유튜브 | Data API v3 | 하루 10,000 유닛. 검색 1회=100, 댓글 100개=1. 할당량이 떨어지면 다음 날 이어서 수집 |
| 디시 | 크롤링 (2.5초 간격, robots.txt 준수) | 댓글 많은 글만 본문+댓글, 나머지는 제목만 |

## 감성 모델 개선 (권장)

처음에는 `config/anchors.yaml`의 기준 문장으로 zero-shot 분석을 합니다. 정확도를 높이려면:

```bash
pip install setfit datasets scikit-learn
python main.py label 아일릿 --n 300      # 1=부정 2=중립 3=긍정
python main.py train                      # models/setfit-sentiment 저장 → 이후 자동 사용
```

## 점수 정의

문장 가중치: `w = 출처가중치 × (1+ln(1+좋아요)) × 0.5^(경과일/30) × 연결신뢰도 × 관련성`

| 지표 | 계산 |
|---|---|
| 호감도 | `100 × [0.7 × 베이지안보정 평균긍정 + 0.3 × 긍정총량/최대]` |
| 관심도 | `100 × ln(1+Σw(p_pos+p_neg)) / ln(1+최대값)`, 중립 제외 |
| 논란도 | 부정 / (긍정+부정) |
| 그룹 호감도 | `0.5 × 그룹 직접 언급 + 0.5 × 멤버 가중평균` |
| 그룹 관심도 | 다른 그룹 분석 결과 대비 백분위 (같은 기간으로 2개 그룹 이상 분석해야 표시) |

95% 순위구간은 bootstrap으로 계산합니다. 언급이 30개 미만이면 ⚠로 표시합니다.

## 테스트
```bash
pip install pytest && python -m pytest tests -q
```
