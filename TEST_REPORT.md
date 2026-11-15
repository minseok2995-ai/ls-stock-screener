# 🧪 LS 수급·차트 스크리너 검증 및 테스트 리포트 (`TEST_REPORT.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[검증 및 테스트]` 전담 대화창**에서 테스트 실행 결과, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md) 대조 검수, 데이터 정합성 검증 리포트, 발견된 버그 및 구체적인 코드 수정 제안을 기록하는 문서입니다.
> * **`[프로그램 개발 및 수정(메인)]` 대화창**은 작업 시작 전 본 `TEST_REPORT.md`와 `STRATEGY.md`를 확인하여 미해결 버그(`2.1절 신규 수정 요청 사항`)를 코드에 반영하고, 수정이 완료된 항목의 상태를 **`[해결 완료]`**로 업데이트합니다.

---

## 1. 최신 검수 요약 (`v2.5.2` 커밋 `f7aa980` 최종 검수 완료 — `AC-1 ~ AC-38` 전 항목 최종 PASS)

* **검수 일시**: `2026-11-15 22:26 KST` (`2026-11-15 13:26 UTC`)
* **대상 커밋**: `f7aa980` — `feat(v2.5.2): 와이드 레이아웃, 관심종목 6컬럼·전용 브리핑, 프로 차트 대화면 (AC-36~38)` ([`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L1057-L1151) `9절` 전 요구사항)
* **단위·통합 테스트 스위트 및 회귀 검증 실행 결과 (`총 82 / 82 통과`)**:
  * `python3 test_screener_verification.py`: **8 / 8 통과 (`OK`)**
  * `python3 -m unittest discover -s tests -v`: **74 / 74 통과 (`OK`, `3.19s` — `test_v25_pattern_chart.py` `17개` [`TestV252Wide` 3개 신설 포함] + `test_v24_watchlist_holdings.py` `29개` + `test_v23_acceptance.py` `19개` + `test_v2_acceptance.py` `9개`)**
  * `python3 run_daily_screener.py --mode verify`: **전 항목 정상 통과 (`Exit 0`, `1,463` 유니버스 · 차트 `1,233일` · 수급 `739일` 무손상)**
* **운영 Supabase 실서버(`T = 2026-11-13`, 읽기 전용 실데이터 검증) + Node VM 3페이지 E2E 최종 확인 결과**:
  * ✅ **`AC-36` PASS (3페이지 와이드 뷰포트 개방 & 차트 중심 비대칭 그리드 & `watchlist.html` 6컬럼 슬림화)**:
    * [`watchlist.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/watchlist.html#L14-L15), [`holdings.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/holdings.html#L14-L15), [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L38-L39) 3개 페이지 모두 `max-w-7xl` 제한이 완전 제거(`0건`)되고 `w-full max-w-[1920px] 2xl:max-w-[96vw] mx-auto` 및 `p-3 md:px-5 md:py-4`가 일관 적용됨을 확인했습니다.
    * [`watchlist.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/watchlist.html#L32-L58)이 `lg:grid-cols-[440px_minmax(0,1fr)] xl:grid-cols-[470px_minmax(0,1fr)]`로 전환되었고, 좌측 테이블은 정확히 **`6컬럼`(`체크 · 등급 · 종목명 · 최초 대비 · 포착 · 작업`, `colspan="6"` 3곳 일치)** 만 렌더링하며 실등록 `43종목` 전 행(`43/43`)에서 `recommend_tag`·`현재가`·`이후 기관누적`·`상태` 열 유출이 `0건`(`truncate max-w-[125px]` 고정폭 유지)임을 확인했습니다. 상단 미니 정렬 바(`#btnSortDefault`, `[data-sort="score"]` `#wlSortLabel`)의 `▼ / ▲ / 기본` 단조 정렬·초기화도 정확히 작동합니다.
  * ✅ **`AC-37` PASS (우측 상단 `#wlDetailHeader` 선택 종목 전용 2단 종합 브리핑 영역)**:
    * [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L285-L315)의 `evaluateWatchlistItem` / `evaluateHolding` `priceDiff` 산출 및 [`lookupMasters()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L479-L490)(`market_cap_eok,avg_val_20d_eok`, 100종목 청크 병렬 조회) 연동으로, 운영 DB 실등록 관심종목 **`43 / 43종목 전원`** 선택 시 `#wlDetailHeader`에 시장(`KOSPI/KOSDAQ`)·종목명·코드·현재가·전일대비 등락폭(`▲/▼ 원`)·등락률(`%`)·시가총액(`시총 X억 · 20일평균 거래대금 X억`)·즉시 액션 3종(`보유편입·제외·영구제외`)·종합판단 배지·출신 추천태그·기관수급 추적·실시간 상태 배지가 누락 없이 표시됨을 실증했습니다 (예: `138930 BNK금융지주 · KOSPI · 13,580원 · ▲ 720원 · +5.60% · 시총 41,669억 · 20일평균 거래대금 178억 · 73점 · ⏳ 눌림대기 · 🌱 쌍바닥돌파 · 당일신규(+148.2억) · 🎯 20일선 눌림`).
    * [`holdings.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/holdings.html#L156-L169) `#hdDetailSummary` 역시 보유(`HOLDING`) 및 청산(`CLOSED`) 행 선택 시 등락폭/률·수익률·손익·시가총액을 정확히 표시합니다.
  * ✅ **`AC-38` PASS (프로 차트 대화면 세로 확장 `560px+` · 하단 2열 병렬화 · 반응형 리사이즈 & 전 버전 회귀)**:
    * 뷰포트(`innerHeight = 960` 실증 기준)에서 프로 차트 캔버스 높이가 `watchlist.html` **`700px`**(`범위 560~760px`), `holdings.html` **`710px`**(`범위 560~760px`), `index.html` **`630px`**(`범위 480~640px`), `[🔍 크게 보기]` 모달 `max-w-[95vw]` & **`620~840px`** 로 확대되었고, `watchlist.html` 하단 `#wlScoreCard`와 매매 계획 폼이 `grid-cols-1 xl:grid-cols-2` 2열 병렬 배치되었습니다.
    * [`drawProChart()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1079-L1103) 우측 가격축 여백 `Rm = 68` 및 `topH >= 320` 대화면 `6등분(7개 가격선)` 그리드 렌더링, [`mountProChartPanel()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1414-L1417)의 `ResizeObserver`(가로 폭 `800 → 1380px` 변경 시 즉시 `2760px` 물리 캔버스 재렌더) 및 `window.resize`(`920 → 1080p` 변경 시 `660 → 760px` 즉시 갱신) + Node VM 안전 가드가 모두 정상 작동하며, 운영 Supabase 실데이터(`watchlist_items = 43`, `portfolio_holdings = 0`, `excluded_stocks = 0`)는 단 1건의 쓰기 없이 **100% 무변경 보존**되었습니다.

---

### 1.1 `v2.5.2` 신규 합격 기준 (`STRATEGY.md` 9.6절 — `AC-36` ~ `AC-38`) 최종 검수 결과표

| 검증 코드 | 검증 항목 (`STRATEGY.md` 9.6절) | 코드 감사 · 운영 Supabase(`2026-11-13`) · Node VM 3페이지 실증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-36** | **3페이지 와이드 뷰포트 개방 및 `watchlist`·`holdings`·`index` 차트 중심 그리드 전환 검증** | • `index.html`, `watchlist.html`, `holdings.html` 3페이지 모두 `max-w-7xl` 완전 제거(`0건`) 및 `w-full max-w-[1920px] 2xl:max-w-[96vw] mx-auto` 적용 확인<br/>• `watchlist.html` 비대칭 그리드(`lg:440px / xl:470px + minmax(0,1fr)`), 좌측 스크롤(`max-h-[calc(100vh-185px)] min-h-[760px]`), 상단 미니 정렬 바(`기본` / `종합판단 ▼·▲`) 및 정확히 **`6컬럼`(`체크·등급·종목명·최초대비·포착·작업`)** 적용; 실데이터 `43종목` 전 행(`43/43`)에서 `recommend_tag`·현재가·기관누적·상태 배지 제거 확인<br/>• `holdings.html`(`460/500px + 1fr`), `index.html`(`lg:6:6 / xl:5:7`, 7컬럼 헤더 유지) 차트 중심 그리드 전환 완료 | **PASS** |
| **AC-37** | **우측 상단 `선택 종목 전용 브리핑 영역` (`현재가·등락폭·등락률·시가총액·수급·상태·종합판단`) 검증** | • `evaluateWatchlistItem`·`evaluateHolding`에 `priceDiff: Math.round(close - prev)` 추가 및 `lookupMasters`의 `market_cap_eok,avg_val_20d_eok` 100종목 청크 병렬 로드(`Promise.all`) 정상 동작<br/>• 운영 DB 실등록 `43종목` 전수 순회(`selectRow`) 검증 결과 **`43 / 43종목 전원`** `#wlDetailHeader`에 시장·종목명·코드·현재가·등락폭·등락률·시가총액(및 20일 평균 거래대금)·즉시 액션 버튼 3종·종합판단 점수/라벨·출신 패턴태그·당일신규/이후 기관누적·눌림/이탈 배지 정상 렌더링 확인 (`185일 ↔ 750일` 점수 차이 `0건`) | **PASS** |
| **AC-38** | **프로 차트 세로 높이 대폭 확대(`560px+`) · 하단 2열 배치 · 자동 리사이즈 및 `AC-1 ~ AC-35` 회귀 검증** | • 동적 `heightFn` 검증 완료: `watchlist.html`(`560~760px`), `holdings.html`(`560~760px`), `index.html`(`480~640px`), `[🔍 크게 보기]`(`max-w-[95vw]`, `620~840px`), `Rm = 68` 가격축 여백 및 `topH >= 320` 6등분(`7개` 가격선) 그리드 정상 작동<br/>• `watchlist.html` 차트 하단 `#wlScoreCard` + 입력 폼 `grid-cols-1 xl:grid-cols-2` 2열 배치 확인<br/>• `ResizeObserver` 폭 변경 및 `window.resize` 높이 변경 자동 `redraw()`와 Node VM 안전 가드 정상 작동; 전체 자동화 테스트 **`82 / 82` (`test_screener_verification.py` 8 + `unittest` 74) 100% PASS** | **PASS** |

---

### 1.2 `v2.5 / v2.5.1` 합격 기준 (`STRATEGY.md` 8.6절 — `AC-30` ~ `AC-35`) 회귀 검수 결과표

| 검증 코드 | 검증 항목 (`STRATEGY.md` 8.6절) | `v2.5.2` (`f7aa980`) 적용 후 회귀 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-30** | **무미래참조(`Zero Look-ahead`) 피봇·기하학 패턴 5종 · 반전 캔들 4종 · 보조지표 수식 정합성 검증** | `computeIndicators`, `findConfirmedPivots`, 4대 반전 캔들, 5대 패턴(`flag` 양봉 돌파 `C > O` 포함) 및 단기 시계열 오탐 `0건` 무결성 유지 | **PASS** |
| **AC-31** | **`index.html` 패턴 승격(`쌍바닥·역H&S`) · 4대 진입성향 서브태그 · `125일` 일봉 프리로드 보강 검증** | `2026-11-13` `당일10%` `123종목`(`추천 49 / 보류 74`), 서브태그 중복 `0건`, 비추천 `[하락채널저항]` `22/22` 표시 유지 | **PASS** |
| **AC-32** | **`watchlist.html` 4축 `100점 종합 판단` 수식 · 4단계 신호등 · 우측 스코어 브리핑 검증** | 4축 `100점` 합산·4단계 신호등, `[🔥 타점완성]` 필터, 미니 정렬 바(`종합판단 ▼/▲`), 2열 `#wlScoreCard` 및 `추천 진입 대기선` 원클릭 적용 정상 유지 | **PASS** |
| **AC-33** | **3페이지 통합 2단 프로 차트(`drawProChart`) · 패턴 자동 작도 · 기간 전환(`60~720일`) 연동 검증** | 3페이지 대화면 프로 차트, `index.html` 일봉 `240` + 수급 `240` 병렬 보강, `watchlist.html` `720일` 전환 시 일봉 `750` + 수급 `739` 로드, `ctx.clip()` 하단 침범 `0건` 유지 | **PASS** |
| **AC-34** | **`[🔍 크게 보기]` 대화면 차트 모달 및 `[📸 PNG 차트 이미지 저장]` 검증** | `[🔍 크게 보기]` `max-w-[95vw]`(`620~840px`) 풀스크린급 모달 오픈 및 `[📸 이미지 저장]`(`2200×1368px` PNG DataURL)·클립보드 복사 정상 동작, 텔레그램 사진 전송 미추가 유지 | **PASS** |
| **AC-35** | **전 버전 통합 회귀 무결성 검증 (`AC-1 ~ AC-29` 전수 PASS)** | `AC-1 ~ AC-35` 및 신규 `AC-36 ~ AC-38` 포함 총 **`82 / 82` 자동화 테스트 100% 통과**, `--mode verify` `Exit 0` | **PASS** |

---

### 1.3 기존 요구사항 (`AC-1` ~ `AC-29`) 회귀 검증 요약 (`v2.5.2` 적용 후 전 항목 PASS 유지)

| 검증 코드 | 검증 항목 요약 | `v2.5.2` (`f7aa980`) 적용 후 회귀 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-1 ~ AC-18** | 유니버스(`1,463종목`), EMA·순수기관 수식, 4중 배치 Cron, 멱등성 가드, 유동성 제외 필터, 9열 엑셀 | `test_screener_verification.py`(8/8), `test_v2_acceptance.py`(9/9), `--mode verify` 전 항목 오차 `0건` (`index.html` 7컬럼 헤더 계약 보존) | **PASS** |
| **AC-19 ~ AC-23** | 차트 5년(`1,678,171행`) · 수급 3년(`1,040,512행`) 비대칭 적재, 앵커 EMA, 무지연 PK 조회 | `test_v23_acceptance.py`(19/19), 7종목 `1,233일 / 739일` 범위 및 웹 초기 로드 무결성 유지 | **PASS** |
| **AC-24 ~ AC-29** | 3페이지 분리, 추천/비추천 기본 계약, 영구제외 즉시 반영, 스마트 병합, 보유/청산(`A안`), 텔레그램 폴백 | `test_v24_watchlist_holdings.py`(29/29) 전 항목 무수정 통과, 운영 DB 실등록 관심종목 `43건` 읽기 전용 검증 완료 및 무손상 보존 | **PASS** |

---

## 2. 버그 및 수정 요청 트래커 (Issue & Fix Tracker)

### 🚨 2.1 `[프로그램 개발 및 수정]` 대화창 신규 수정 요청 사항

* **현재 미해결 버그 없음 (`0건`)** — `AC-1 ~ AC-38` 전 항목 최종 합격(`ALL PASS`).

---

### ✅ 2.2 해결 완료된 이슈 히스토리 아카이브

* **[v2.5.2 검증 완료 (`f7aa980`)]** 3페이지 와이드 뷰포트(`max-w-[1920px] 2xl:max-w-[96vw]`) 전면 개방, `watchlist.html` 좌측 `6컬럼`(`440/470px`) 초슬림화 + 우측 `#wlDetailHeader`(시총·등락폭·종합판단·패턴·기관수급·상태 2단 브리핑) 신설, 3페이지 프로 차트 대화면 확장(`560~760px` / `480~640px` / 모달 `max-w-[95vw]` `620~840px`)·하단 2열 배치·`ResizeObserver`/`resize` 자동 리사이즈(`AC-36 ~ AC-38`) 전 항목 합격.
* **[ISSUE-015 ~ ISSUE-018] `[해결 완료 (v2.5.1, 9bbc56f)]`** `index.html` 수급 `240건` 병렬 보강(`ISSUE-015`), 서브태그 중복 제거 및 비추천 `[하락채널저항]` `22/22` 노출(`ISSUE-016`), `holdings.html` 선택 행 캐시 격리·`setData` `dataKey` 리셋·`drawProChart` 상단 `ctx.clip()` 적용(`ISSUE-017`), `flag` 양봉(`C > O`) 조건 및 `watchlist.html` `종합판단` 정렬 토글(`ISSUE-018`) 해결 완료 (`AC-30 ~ AC-35` 합격).
* **[ISSUE-011 ~ ISSUE-014] `[해결 완료 (v2.4.1, 16f575d + 운영 DB RLS 해제/GRANT 반영)]`** 운영 Supabase 신규 3개 테이블 실서버 CRUD 정상화 및 `42501` 배너, 대바닥 출신 관심종목 이평 이탈 오판 제거, 제외관리 모달 복구·프리셋 체크박스 즉시 반영, 보유종목 현재가 목표가 배지 및 `CLOSED` 온디맨드 차트 로드(`AC-24 ~ AC-29`) 전 항목 합격.
* **[v2.3.1 검증 완료 (`353f92a`, `Run #43682739754` & `Run #43685346608`)]** 차트 5년(`2021-11-01~`, `1,678,171행`) · 수급 3년(`2023-11-01~`, `1,040,512행`) 비대칭 확장 백필 1회차 `2시간 44분` 100% 완주, 앵커 시드 EMA 연속성, 거래정지 `25종목` 미확정 오판 차단, `80분` 주기 토큰 자동 갱신 및 `271.8만 행` 대용량 DB 무지연(`AC-19 ~ AC-23`) 전 항목 합격.
* **[v2.2 검증 완료 (`6bfbbd5`)]** `[기관 수급 발생 종목]` 유동성·수급금액 제외 필터(`당일 기준` vs `3일 연속 3일 평균 기준`) 및 `[엑셀 저장]` 9개 컬럼 개편(`AC-16 ~ AC-18`) 전 항목 합격.
* **[v2.1 검증 완료 (`1aecd41`)]** `20:30 KST` 다중 백업 Cron, `KST` 표준시 고정, `--skip-if-completed` 멱등성 가드(`< 2.3초` 종료), `if: failure()` 장애 알림, Apps Script 외부 정각 웹훅(`AC-13 ~ AC-15`) 및 `두산에너빌리티(034020)` 백필 자동 복구 확인 완료.
* **[ISSUE-006 ~ ISSUE-010] `[해결 완료 (v1.4.3 ~ v2.0)]`** `PRIORITY_SHCODES` 제거, `has_2yr_history` 판정 분리, 장중 미확정 수급 차단, 복합 PK 병렬 조회 전환(`HTTP 500` 해소), `AC-1 ~ AC-12` 검증 체계 구축 완료.
* **[ISSUE-001 ~ ISSUE-005] `[해결 완료 (v1.4)]`** 1,463종목 시총 ≥ 700억 전수 유니버스 구축, 일봉·수급 500영업일 역순 슬라이딩 적재, Actions 360분 타임아웃 상향 완료.
