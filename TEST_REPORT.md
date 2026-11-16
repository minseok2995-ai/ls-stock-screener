# 🧪 LS 수급·차트 스크리너 검증 및 테스트 리포트 (`TEST_REPORT.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[검증 및 테스트]` 전담 대화창**에서 테스트 실행 결과, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md) 대조 검수, 데이터 정합성 검증 리포트, 발견된 버그 및 구체적인 코드 수정 제안을 기록하는 문서입니다.
> * **`[프로그램 개발 및 수정(메인)]` 대화창**은 작업 시작 전 본 `TEST_REPORT.md`와 `STRATEGY.md`를 확인하여 미해결 버그(`2.1절 신규 수정 요청 사항`)를 코드에 반영하고, 수정이 완료된 항목의 상태를 **`[해결 완료]`**로 업데이트합니다.

---

## 1. 최신 검수 요약 (`v2.6.1` 커밋 `f768119` 최종 전수 검수 — `AC-1 ~ AC-43` 전 항목 최종 PASS · `ISSUE-019 ~ ISSUE-020` 해결 완료)

* **검수 일시**: `2026-11-16 14:37 KST` (`2026-11-16 05:37 UTC`)
* **대상 커밋**: `f768119` — `fix(v2.6.1): ISSUE-019 좌측 테이블 폭 절단 해결, ISSUE-020 프로 차트 패턴 배지 상시 표시` ([`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L1154-L1340) `10절` 전 요구사항 및 `ISSUE-019 · ISSUE-020` 반영분)
* **단위·통합 테스트 스위트 및 회귀 검증 실행 결과 (`총 93 / 93 통과 — ALL PASS`)**:
  * `python3 test_screener_verification.py`: **8 / 8 통과 (`OK`)**
  * `python3 -m unittest discover -s tests -v`: **85 / 85 통과 (`OK`, `3.40s` — `test_v26_acceptance.py` `11개`[`TestIssue019020` 3개 포함] + `test_v25_pattern_chart.py` `17개` + `test_v24_watchlist_holdings.py` `29개` + `test_v23_acceptance.py` `19개` + `test_v2_acceptance.py` `9개`)**
  * `python3 run_daily_screener.py --mode verify`: **전 항목 정상 통과 (`Exit 0`, `1,463` 유니버스 · 차트 `1,233일` · 수급 `739일` · `2026-11-13` 스크리닝 `123 / 81 / 47 / 43 / 4` 무손상)**
* **운영 Supabase 실서버(`T = 2026-11-13`, 읽기 전용 실데이터 전수 검증) + 2-슬롯 배치 시뮬레이션 + Headless Chromium(`Tailwind CSS` 실구동) 3페이지·2해상도(`1920×1080 xl` / `1180×900 lg`) 실화면 최종 계측 결과**:
  * ✅ **`AC-39` PASS (1일 2회 배치 `16:05 KST` 가집계 + `20:30 KST` 최종 확정 · UTC 타임스탬프 비교 · 공휴일 스킵)**:
    * [`.github/workflows/daily_batch.yml`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/.github/workflows/daily_batch.yml#L6-L64) 5중 크론(`5 7`, `25 7`, `30 11`, `47 11`, `17 12 * * 1-5`) 및 `batch_slot`(`auto`/`prelim`/`final`), [`scripts/trigger_daily_batch.gs`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/scripts/trigger_daily_batch.gs#L86-L103) `setupDaily1605And2030Triggers()`, [`run_daily_screener.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1375-L1384) `is_in_daily_yield_window`(`15:55~16:45` & `20:10~21:20 KST`) 모두 정상 반영 확인.
    * 6단계 E2E 시뮬레이션(`16:05` UTC `+00:00` 저장 → `16:25` 백업 `0.00초` 스킵 → `20:30` `final` 슬롯 `min_updated_at_kst=20:00+09:00` 전 종목 100% 덮어쓰기 & `ANCHOR-MISMATCH 0건` → 부분 중단 시 미갱신 종목만 선별 이어받기 → `20:47` 백업 및 분기월 평일 공휴일 `0.00초` 스킵 · 텔레그램 `[1차 정규장 가집계]` / `[2차 최종 확정]` 분리) 완벽 통과.
  * ✅ **`AC-40` PASS (`SNT다이내믹스` 등 `🚀 역배열 추세돌파` 승격 · `[하락채널저항]` 오탐 `0건` · `[역배열낙하]` 세분화)**:
    * 운영 DB(`T = 2026-11-13`, `당일10%` `123종목`) 전수 평가 결과 [`detectTurnaroundBreakout`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L921-L947)에 의해 **`SNT다이내믹스`(`003570`, `28,300원 +8.64%`, 순수기관 `78.81% / +102.1억`)**, **`SNT에너지`(`100840`, `+6.49%`, 기관 `34.47%`)**, **`아이엠바이오로직스`(`493280`, `+10.34%`, 기관 `16.61%`)** 가 `Step 2` **`🚀 역배열 추세돌파`** 로 정상 승격되었고(`125일 ↔ 240봉` 분류 차이 `0건`), 하락 추세선 `+1.5%` 이상 양봉 돌파 `17종목` 전원의 `[하락채널저항]` 오탐 해소(`downChannelBreakout = true`, 오탐 `0건`) 및 비추천 사유 `[역배열·60일선저항]`(`9건`)·`[역배열·20일선저항]`(`10건`) 세분화가 정확히 작동합니다.
  * ✅ **`AC-41` PASS (`watchlist.html` `수동등록·직접추가·역배열 추세돌파` 매도권고 오탐 제거 & 당일 재병합 동기화)**:
    * 운영 DB 관심종목 **`37종목` 전수 평가 결과 `⚠️ 정리권고(EXIT)` 오탐 `0건`(`READY 1 · WAIT 24 · WATCH 12 · EXIT 0`)** 달성(`SNT다이내믹스` `68점 WAIT`, `솔브레인` `63점 WAIT`, `피에스케이` `51점 WATCH`, `현대모비스` `67점 WAIT`, `RFHIC` `52점 WATCH` 전원 `ema20Break=false, ema60Break=false`). 당일 재병합(`first_signal_date === T`) 시 `signal_count` 무증가 수치 동기화 및 `"수동등록" → "역배열 추세돌파"` 태그 승격 정상 확인.
  * ✅ **`AC-42` PASS (`ISSUE-020` 해결 확인 — 3페이지 전 종목 우측 헤더 · 프로 차트 상단 `[data-role="badges"]` · `[🔍 크게 보기]` 모달 상시 표시 · 중복 제거 · `240일/720일` 동기화 · PNG 이모지 정제)**:
    * [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1399-L1486) `mountProChartPanel`에 `[data-role="badges"]` 행 및 `renderBadges()`(`Set` 중복 제거 + `describeStockPattern` 자동 폴백)가 추가되어, Headless Chromium 실화면에서 **`index.html`(`추천 후보` `SNT다이내믹스` `["🚀 역배열 추세돌파", "🚀 하락추세선돌파"]`, `비추천 보류` `한국금융지주` `["🌱 바닥권 저점지지"]`, `[🔍 크게 보기]` 모달 `["🚀 역배열 추세돌파", "🚀 하락추세선돌파"]`), `watchlist.html`(`SNT다이내믹스`·`티에프이`), `holdings.html`(`보유 중` `126봉` · `청산 완료` `145봉`) 모두 우측 상세 헤더와 프로 차트 상단에 패턴·추세 진단 배지가 100% 중복 없이 상시 표시**됩니다.
    * `240일(1년)` 클릭 시 [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L1286-L1325) `syncRecommendationAfterLoad` 및 [`watchlist.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/watchlist.html#L254-L280) `onDataLoaded`가 추천 상태·좌측 행 점(`🟢/⚪`)·탭 카운트·상세 헤더·프로 차트 배지를 즉시 동기화하며, [`sanitizeFilePart`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1327-L1329) 확장 정규식(`[\p{Extended_Pictographic}\uFE0F\u200D↗↘↑↓]`)으로 전 배지 PNG 파일명에 이모지 잔존 `0건`을 확인했습니다.
  * ✅ **`AC-43` PASS (`ISSUE-019` 해결 확인 — 3페이지·2해상도 `horizontalOverflowPx = 0px`, 우측 끝 `[🚫]`·`[영구제외]` 잘림 `0px`, 최하단 끝선 `bottomDiffPx = 0px`)**:
    * Headless Chromium(`Tailwind CSS` + 실DB 데이터 로드 완료 상태) 픽셀 실측 결과:
      * **[`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L152-L165) (`52행` 렌더링)**: `1920×1080 (xl)` `clientWidth 508px === scrollWidth 508px`(`overflow 0px`, 9열 `🚫` 버튼 `left 475..right 508`, `clippedRightPx = 0px`, `bottomDiffPx = 0px`) / `1180×900 (lg)` `clientWidth 478px === scrollWidth 478px`(`overflow 0px`, 9열 `🚫` 버튼 `left 447..right 478`, `clippedRightPx = 0px`, `bottomDiffPx = 0px`). 7개 `<th>` 텍스트 계약 100% 유지.
      * **[`watchlist.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/watchlist.html#L49-L59) (`37행` 렌더링)**: `1920×1080 (xl)` `clientWidth 398px === scrollWidth 398px`(`overflow 0px`, `영구제외` `right 385 <= 398`, `clippedRightPx = 0px`, `bottomDiffPx = 0px`) / `1180×900 (lg)` `clientWidth 383px === scrollWidth 383px`(`overflow 0px`, `영구제외` `right 373 <= 383`, `clippedRightPx = 0px`, `bottomDiffPx = 0px`).
      * **[`holdings.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/holdings.html#L46-L61)**: `1920×1080 (xl)` `398px === 398px`(`overflow 0px`, `bottomDiffPx = 0px`) / `1180×900 (lg)` `378px === 378px`(`overflow 0px`, `bottomDiffPx = 0px`).

---

### 1.1 `v2.6 / v2.6.1` 신규 합격 기준 (`STRATEGY.md` 10.6절 — `AC-39` ~ `AC-43`) 최종 검수 결과표

| 검증 코드 | 검증 항목 (`STRATEGY.md` 10.6절) | 코드 감사 · 운영 Supabase(`2026-11-13`) · Headless Chromium 실화면 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-39** | **1일 2회 배치(`16:05 KST` 가집계 + `20:30 KST` 최종 확정) 2-슬롯 완료 판정·덮어쓰기·공휴일 스킵 검증** | • `daily_batch.yml` 5개 크론(`5 7`, `25 7`, `30 11`, `47 11`, `17 12 * * 1-5`), `batch_slot` input, `setupDaily1605And2030Triggers()`, `is_in_daily_yield_window`(`15:55~16:45` & `20:10~21:20 KST`) 모두 정확히 반영<br/>• 6대 함정 E2E 시뮬레이션 통과: `16:05`(`07:05+00:00` UTC 저장) → `16:25` 백업 `0.00초` 스킵 → `20:30`(`final`, `min_updated_at_kst=20:00+09:00`) 스킵 없이 전 종목 100% 덮어쓰기(`ANCHOR-MISMATCH 0건`) → 부분 중단 시 미갱신 종목만 선별 이어받기 → `20:47` 백업 및 분기월 평일 공휴일 `0.00초` 스킵, 텔레그램 `[1차 정규장 가집계]` / `[2차 최종 확정]` 분리 확인 | **PASS** |
| **AC-40** | **`SNT다이내믹스` 등 `🚀 역배열 추세돌파` 승격 및 `[하락채널저항]`·`[역배열낙하]` 오판 제거 검증** | • `2026-11-13` 실DB `당일10%` `123종목` 전수 검증: `SNT다이내믹스`(`003570`), `SNT에너지`(`100840`), `아이엠바이오로직스`(`493280`)가 `Step 2` `🚀 역배열 추세돌파`(`turnaroundBreakout`)로 정상 승격 (`125일 ↔ 240봉` 차이 `0건`)<br/>• 하락 추세선 `+1.5%` 이상 양봉 돌파 `17종목` 전원 `[하락채널저항]` 오탐 해소 → `downChannelBreakout`(`하락추세돌파↑`) 전환 (`오탐 0건`), 비추천 역배열 사유 `[역배열·60일선저항]`(`9건`)·`[역배열·20일선저항]`(`10건`) 정상 세분화 (`오표기 0건`) | **PASS** |
| **AC-41** | **`watchlist.html` `수동등록·직접추가·역배열 추세돌파` 출신 종목의 `⚠️ 정리권고(매도 추천)` 오탐 제거 검증** | • 운영 DB 관심종목 `37종목` 전수 검증 결과 `EXIT` 오탐 `4건 → 0건`(`READY 1 · WAIT 24 · WATCH 12 · EXIT 0`); `SNT다이내믹스`·`솔브레인`·`피에스케이`·`현대모비스`·`RFHIC` 전원 `ema20Break=false, ema60Break=false` 확인 (`stop_price` 종가 이탈 시에만 `EXIT` 발동)<br/>• `planWatchlistMerge` 당일(`first_signal_date === T`) 재병합 시 `signal_count` 증가 없이 확정 수치 및 `"수동등록" → "역배열 추세돌파"` 승격 패치 정상 동작 | **PASS** |
| **AC-42** | **전 페이지(`index`·`watchlist`·`holdings`) · 전 종목(`추천·비추천·관심·보유·청산`) 차트 패턴 정보 상시 표기 검증** | • `describeStockPattern` 산출 배지가 3페이지 우측 상세 헤더(`#detailBadgesBar`, `#wlDetailBrief`, `#hdDetailSummary`), 프로 차트 상단 `[data-role="badges"]`, `[🔍 크게 보기]` 모달, PNG 저장 헤더 모두에 중복 없이 100% 상시 표시됨<br/>• `holdings.html` `-185달력일`(`126~145봉`) 확장 로드, `240일/720일` 전환 시 헤더·차트 배지·추천 탭 동기화, `sanitizeFilePart` 유니코드 이모지 정제 모두 정상 작동 | **PASS** |
| **AC-43** | **3페이지 리스트 극한 축소 · 무가로스크롤 · 최하단 1:1 높이 일치 및 `AC-1 ~ AC-38` 회귀 검증** | • Headless Chromium `1920×1080 (xl)` & `1180×900 (lg)` 실측 결과 3페이지 모두 `horizontalOverflowPx = 0px` (`index 508/478px`, `watchlist 398/383px`, `holdings 398/378px`), 우측 끝 `🚫`·`영구제외` 버튼 잘림 `0px`, 좌·우 최하단 높이 오차 `bottomDiffPx = 0px`<br/>• `index.html` 행 배지 우측 이동·7개 `<th>` 계약 보존, `watchlist.html` 무아이콘 행 버튼(`#wlDetailActions` 기존 문구 보존), 자동화 회귀 스위트 **`93 / 93` PASS** | **PASS** |

---

### 1.2 기존 요구사항 (`AC-1` ~ `AC-38`) 회귀 검증 요약 (`v2.6.1` 적용 후 전 항목 PASS 유지)

| 검증 코드 | 검증 항목 요약 | `v2.6.1` (`f768119`) 적용 후 회귀 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-1 ~ AC-18** | 유니버스(`1,463종목`), EMA·순수기관 수식, 5중 배치 Cron 확장, 멱등성 가드, 유동성 제외 필터, 9열 엑셀 | `test_screener_verification.py`(8/8), `test_v2_acceptance.py`(9/9), `--mode verify` 전 항목 오차 `0건` (`index.html` 7개 `<th>` 헤더 계약 보존) | **PASS** |
| **AC-19 ~ AC-23** | 차트 5년(`1,678,171행`) · 수급 3년(`1,040,512행`) 비대칭 적재, 앵커 EMA, 양보 구간 확장, 무지연 PK 조회 | `test_v23_acceptance.py`(19/19), 7종목 `1,233일 / 739일` 범위 및 2회 덮어쓰기 시 `ANCHOR-MISMATCH 0건` 무결성 유지 | **PASS** |
| **AC-24 ~ AC-29** | 3페이지 분리, 추천/비추천 기본 계약, 영구제외 즉시 반영, 스마트 병합, 보유/청산(`A안`), 텔레그램 폴백 | `test_v24_watchlist_holdings.py`(29/29) 무수정 100% 통과, 운영 DB 실등록 데이터(`관심 37건 · 보유 1건 · 제외 0건`) 읽기 전용 무손상 보존 | **PASS** |
| **AC-30 ~ AC-38** | 무미래참조 패턴·캔들·4축 100점 평가, 2단 프로 차트, 크게 보기·PNG 저장, 와이드 뷰포트·전용 브리핑 | `test_v25_pattern_chart.py`(17/17) 전 항목 통과 (`ctx.clip()`, `Rm=68`, `ResizeObserver`/`resize` 정상 유지) | **PASS** |

---

## 2. 버그 및 수정 요청 트래커 (Issue & Fix Tracker)

### 🚨 2.1 `[프로그램 개발 및 수정]` 대화창 신규 수정 요청 사항

* **현재 미해결 버그 없음 (`0건`) — `AC-1 ~ AC-43` 전 항목 최종 합격(`ALL PASS`).**

---

### ✅ 2.2 해결 완료된 이슈 히스토리 아카이브

* **[ISSUE-019 ~ ISSUE-020] `[해결 완료 (v2.6.1, f768119)]`** `index.html`(`text-[10.5px]`/`text-[11px]`, `px-[3px]`, `w-[6em]`) 및 `watchlist.html`(`text-[11px]`, `px-1`, `w-[7em]`) 슬림화로 `1920×1080(xl)`·`1180×900(lg)` 전 구간 좌측 테이블 `horizontalOverflowPx = 0px`·우측 버튼 절단 `0px` 달성(`ISSUE-019`), `mountProChartPanel` `[data-role="badges"]` 상시 렌더링(일반 차트 + `[🔍 크게 보기]` 모달 + `describeStockPattern` 자동 폴백)·배지 중복 제거·`240일/720일` 로드 후 추천/헤더/행 점 동기화·`sanitizeFilePart` 유니코드 이모지 정제 완료(`ISSUE-020`) (`AC-39 ~ AC-43` 전 항목 합격).
* **[v2.5.2 검증 완료 (`f7aa980`)]** 3페이지 와이드 뷰포트(`max-w-[1920px] 2xl:max-w-[96vw]`) 전면 개방, `watchlist.html` 좌측 `6컬럼`(`440/470px`) 초슬림화 + 우측 `#wlDetailHeader`(시총·등락폭·종합판단·패턴·기관수급·상태 2단 브리핑) 신설, 3페이지 프로 차트 대화면 확장(`560~760px` / `480~640px` / 모달 `max-w-[95vw]` `620~840px`)·하단 2열 배치·`ResizeObserver`/`resize` 자동 리사이즈(`AC-36 ~ AC-38`) 전 항목 합격.
* **[ISSUE-015 ~ ISSUE-018] `[해결 완료 (v2.5.1, 9bbc56f)]`** `index.html` 수급 `240건` 병렬 보강(`ISSUE-015`), 서브태그 중복 제거 및 비추천 `[하락채널저항]` `22/22` 노출(`ISSUE-016`), `holdings.html` 선택 행 캐시 격리·`setData` `dataKey` 리셋·`drawProChart` 상단 `ctx.clip()` 적용(`ISSUE-017`), `flag` 양봉(`C > O`) 조건 및 `watchlist.html` `종합판단` 정렬 토글(`ISSUE-018`) 해결 완료 (`AC-30 ~ AC-35` 합격).
* **[ISSUE-011 ~ ISSUE-014] `[해결 완료 (v2.4.1, 16f575d + 운영 DB RLS 해제/GRANT 반영)]`** 운영 Supabase 신규 3개 테이블 실서버 CRUD 정상화 및 `42501` 배너, 대바닥 출신 관심종목 이평 이탈 오판 제거, 제외관리 모달 복구·프리셋 체크박스 즉시 반영, 보유종목 현재가 목표가 배지 및 `CLOSED` 온디맨드 차트 로드(`AC-24 ~ AC-29`) 전 항목 합격.
* **[v2.3.1 검증 완료 (`353f92a`, `Run #43682739754` & `Run #43685346608`)]** 차트 5년(`2021-11-01~`, `1,678,171행`) · 수급 3년(`2023-11-01~`, `1,040,512행`) 비대칭 확장 백필 1회차 `2시간 44분` 100% 완주, 앵커 시드 EMA 연속성, 거래정지 `25종목` 미확정 오판 차단, `80분` 주기 토큰 자동 갱신 및 `271.8만 행` 대용량 DB 무지연(`AC-19 ~ AC-23`) 전 항목 합격.
* **[v2.2 검증 완료 (`6bfbbd5`)]** `[기관 수급 발생 종목]` 유동성·수급금액 제외 필터(`당일 기준` vs `3일 연속 3일 평균 기준`) 및 `[엑셀 저장]` 9개 컬럼 개편(`AC-16 ~ AC-18`) 전 항목 합격.
* **[v2.1 검증 완료 (`1aecd41`)]** `20:30 KST` 다중 백업 Cron, `KST` 표준시 고정, `--skip-if-completed` 멱등성 가드(`< 2.3초` 종료), `if: failure()` 장애 알림, Apps Script 외부 정각 웹훅(`AC-13 ~ AC-15`) 및 `두산에너빌리티(034020)` 백필 자동 복구 확인 완료.
* **[ISSUE-006 ~ ISSUE-010] `[해결 완료 (v1.4.3 ~ v2.0)]`** `PRIORITY_SHCODES` 제거, `has_2yr_history` 판정 분리, 장중 미확정 수급 차단, 복합 PK 병렬 조회 전환(`HTTP 500` 해소), `AC-1 ~ AC-12` 검증 체계 구축 완료.
* **[ISSUE-001 ~ ISSUE-005] `[해결 완료 (v1.4)]`** 1,463종목 시총 ≥ 700억 전수 유니버스 구축, 일봉·수급 500영업일 역순 슬라이딩 적재, Actions 360분 타임아웃 상향 완료.
