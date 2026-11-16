# 🧪 LS 수급·차트 스크리너 검증 및 테스트 리포트 (`TEST_REPORT.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[검증 및 테스트]` 전담 대화창**에서 테스트 실행 결과, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md) 대조 검수, 데이터 정합성 검증 리포트, 발견된 버그 및 구체적인 코드 수정 제안을 기록하는 문서입니다.
> * **`[프로그램 개발 및 수정(메인)]` 대화창**은 작업 시작 전 본 `TEST_REPORT.md`와 `STRATEGY.md`를 확인하여 미해결 버그(`2.1절 신규 수정 요청 사항`)를 코드에 반영하고, 수정이 완료된 항목의 상태를 **`[해결 완료]`**로 업데이트합니다.

---

## 1. 최신 검수 요약 (`v2.6` 커밋 `049d4d4` 1차 전수 검수 — `AC-39 ~ AC-41` 및 `AC-1 ~ AC-38` PASS / 실화면 `AC-42 · AC-43` 미비 2건 `ISSUE-019 · ISSUE-020` 수정 요청)

* **검수 일시**: `2026-11-16 14:14 KST` (`2026-11-16 05:14 UTC`)
* **대상 커밋**: `049d4d4` — `feat(v2.6): 1일 2회 배치, 역배열 추세돌파/하락채널 보정, 패턴 상시 표기, 3페이지 초슬림 리스트 (AC-39~43)` ([`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L1154-L1340) `10절` 전 요구사항)
* **단위·통합 테스트 스위트 및 회귀 검증 실행 결과 (`총 90 / 90 통과`)**:
  * `python3 test_screener_verification.py`: **8 / 8 통과 (`OK`)**
  * `python3 -m unittest discover -s tests -v`: **82 / 82 통과 (`OK`, `3.75s` — `test_v26_acceptance.py` `8개` 신설 + `test_v25_pattern_chart.py` `17개` + `test_v24_watchlist_holdings.py` `29개` + `test_v23_acceptance.py` `19개` + `test_v2_acceptance.py` `9개`)**
  * `python3 run_daily_screener.py --mode verify`: **전 항목 정상 통과 (`Exit 0`, `1,463` 유니버스 · 차트 `1,233일` · 수급 `739일` · `2026-11-13` 스크리닝 `123 / 81 / 47 / 43 / 4` 무손상)**
* **운영 Supabase 실서버(`T = 2026-11-13`, 읽기 전용 실데이터 전수 검증) + 2-슬롯 배치 시뮬레이션 + Headless Chromium(`Tailwind CSS` 실구동) 3페이지 실화면 계측 핵심 결과**:
  * ✅ **`AC-39` PASS (1일 2회 배치 `16:05 KST` 가집계 + `20:30 KST` 최종 확정 · UTC 타임스탬프 비교 · 공휴일 스킵)**:
    * [`.github/workflows/daily_batch.yml`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/.github/workflows/daily_batch.yml#L6-L64)에 평일 5중 크론(`5 7`, `25 7`, `30 11`, `47 11`, `17 12 * * 1-5`) 및 `batch_slot`(`auto`/`prelim`/`final`, 총 7개 input ≤ 10개 상한)이 정확히 반영되었고, [`scripts/trigger_daily_batch.gs`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/scripts/trigger_daily_batch.gs#L86-L103)에 `setupDaily1605And2030Triggers()`가 기존 함수 보존 상태로 추가되었습니다.
    * [`run_daily_screener.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L845-L989) 및 `run_standalone_batch`(`lines 1918-1966, 2132-2151, 2327-2329`) End-to-End 시뮬레이션 검증 결과:
      1. `16:05 KST`(`prelim`) 적재 시 PostgREST가 `updated_at`을 UTC(`2026-11-16T07:05:10+00:00`)로 저장하고 텔레그램 헤더 `📊 *[1차 정규장 가집계]*`가 전송되며, `16:25 KST` 백업은 `100.0% >= 98.5%`로 `0.00초` 즉시 스킵됩니다.
      2. `20:30 KST`(`final`) 실행 시 `min_updated_at_kst = "2026-11-16T20:00:00+09:00"` 타임존 인식(`dt.datetime.fromisoformat`) 비교로 최상단 가드(`completion_pct = 0.0%`)와 루프 내부 `2-B [DAILY-SKIP]`(`0건`) 모두 건너뛰지 않고 **전 종목 확정 데이터를 100% 덮어쓰며**(`ANCHOR-MISMATCH 0건`), 텔레그램 헤더 `✅ *[2차 최종 확정]*`가 전송됩니다.
      3. `20:30` 부분 중단 후 `20:47` 이어받기 시 `20:00 KST` 이후 갱신 종목만 정확히 `[DAILY-SKIP]`하고 미갱신 종목만 재수집하며, 완주 후 `20:47`/`21:17` 백업 및 분기월(`3·6·9·12월`) 평일 공휴일(`latest_krx_date != today_str`, `rebuild_due`보다 `[HOLIDAY]` 우선) 모두 `0.00초` 즉시 스킵됩니다. [`is_in_daily_yield_window`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1375-L1384) 역시 평일 `15:55~16:45` 및 `20:10~21:20 KST` 두 구간 모두 양보(`True`)를 반환합니다.
  * ✅ **`AC-40` PASS (`SNT다이내믹스` 등 `🚀 역배열 추세돌파` 승격 · `[하락채널저항]` 오탐 `0건` · `[역배열낙하]` 세분화)**:
    * 운영 DB(`T = 2026-11-13`, `당일10%` `123종목`) 전수 평가 결과 [`detectTurnaroundBreakout`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L921-L947)에 의해 **`SNT다이내믹스`(`003570`, `28,300원 +8.64%`, 순수기관 `78.81% / +102.1억`)**, **`SNT에너지`(`100840`, `+6.49%`, 기관 `34.47%`)**, **`아이엠바이오로직스`(`493280`, `+10.34%`, 기관 `16.61%`)** 가 `Step 2` **`🚀 역배열 추세돌파`(`turnaroundBreakout`)** 로 정상 추천 승격되었습니다 (`125일` 초기 프리로드와 `240봉` 정밀 조회 간 분류 차이 `0건`).
    * [`detectChartPatterns`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L889-L905)에서 하락 추세선(`yRes`)을 `+1.5%` 이상 양봉 돌파한 **`17종목`**(`SNT다이내믹스`, `솔브레인`, `피에스케이`, `두산테스나`, `티씨케이`, `하나머티리얼즈`, `브이엠` 등) 전원이 `[하락채널저항]`에서 해제되어 `downChannelBreakout = true`(`하락추세돌파↑`, `#34d399`)로 전환되었으며(**양봉 돌파 종목의 `[하락채널저항]` 오탐 `0건`**), 비추천 사유도 `[역배열·60일선저항]`(`9건`)·`[역배열·20일선저항]`(`10건`)으로 분리되어 `Close >= EMA 20` 또는 `+3%` 이상 양봉 반등 종목에 `[역배열낙하]`가 찍힌 건수는 **`0건`** 입니다.
  * ✅ **`AC-41` PASS (`watchlist.html` `수동등록·직접추가·역배열 추세돌파` 매도권고 오탐 제거 & 당일 재병합 동기화)**:
    * [`evaluateWatchlistBase`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L290-L296) 및 [`scoreWatchlist`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1008-L1012) 출신 태그 엄격화로, 운영 DB 실등록 관심종목 **`37종목` 전수 평가 결과 `⚠️ 정리권고(EXIT)` 오탐이 기존 `4건`에서 `0건`(`READY 1 · WAIT 24 · WATCH 12 · EXIT 0`)으로 완전 해소**되었습니다 (`003570 SNT다이내믹스` `68점 WAIT`, `357780 솔브레인` `63점 WAIT`, `319660 피에스케이` `51점 WATCH`, `012330 현대모비스` `67점 WAIT`, `218410 RFHIC` `52점 WATCH` 전원 `ema20Break=false, ema60Break=false`). [`planWatchlistMerge`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L214-L229)의 당일(`first_signal_date === T`) 재병합 시 `signal_count` 무증가 확정치 패치 및 `"수동등록" → "역배열 추세돌파"` 승격도 정확히 작동합니다.
  * ⚠️ **`AC-43` FAIL → `[ISSUE-019]` (`index.html` · `watchlist.html` 좌측 테이블 실제 렌더링 폭 초과 + `overflow-x-hidden` 결합으로 우측 열 및 `[🚫 영구제외]` 버튼 절단 결함)**:
    * 3페이지 모두 `lg:items-stretch` + `lg:absolute lg:inset-0` 구조로 **좌·우 최하단 끝선은 `bottomDiffPx = 0px`(`1px` 오차 없음)로 완벽 일치**합니다.
    * **그러나 Headless Chromium(`Tailwind CSS` 실구동) 실화면 픽셀 계측 결과**:
      * [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L149-L164): `STRATEGY.md` `10.4.1`(`line 1300`)이 요구한 `px-1.5 py-1.5 text-[11px]` 축소가 반영되지 않고 `text-xs`(`12px`) 및 `px-3`/`px-2.5`(`20~24px`)가 남아 9개 열 실제 폭이 **`623px`** 인데, 컨테이너는 `520px`(`xl`, 가용 `508px`) / `490px`(`lg`, 가용 `478px`) + `overflow-x-hidden`이라 **`1920×1080`에서도 8열 `연속일수`(`60px` 잘림)와 9열 `작업 [🚫]` 버튼(`105px` 잘림)이 화면 밖으로 영구 절단되어 클릭이 불가능**합니다 (`1180×900 lg`에서는 7열 `외국인비중`까지 3개 열 절단).
      * [`watchlist.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/watchlist.html#L49-L61): `text-xs` 유지로 6컬럼 실제 폭 `414px` > 가용폭 `398px`(`xl`) / `383px`(`lg`)이 되어 `lg`에서 우측 끝 `[영구제외]` 버튼 우측 `15px`가 잘립니다. (`2.1절 ISSUE-019`에 `overflow = 0px` 검증 완료된 CSS 수치 명세 기록)
  * ⚠️ **`AC-42` 부분 미결 → `[ISSUE-020]` (프로 차트 상단 및 `[🔍 크게 보기]` 모달 내 `st.badges` 미표시 + 상세 헤더/PNG 배지 중복 출력)**:
    * `describeStockPattern` 자체와 3페이지 우측 상세 헤더(`#detailBadgesBar`, `#wlDetailBrief`, `#hdDetailSummary`)는 전 종목(`추천·비추천·관심 37·보유·청산`)에 대해 1개 이상의 패턴·추세 배지를 100% 표시합니다.
    * 단, [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1389-L1504) `mountProChartPanel`이 전달받은 `st.badges`를 차트 상단 DOM/오버레이 및 `[🔍 크게 보기]`(`openBig`) 모달에 전혀 렌더링하지 않고(PNG 저장 시에만 사용), `#detailBadgesBar`·`#wlDetailBrief`·PNG 헤더에 동일 배지(`🚀 역배열 추세돌파`, `🌱 쌍바닥돌파` 등)가 2회 중복 출력되며, `watchlist.html` `240일/720일` 클릭 시 `#wlDetailBrief` 재갱신 누락이 확인되었습니다 (`2.1절 ISSUE-020` 참조).

---

### 1.1 `v2.6` 신규 합격 기준 (`STRATEGY.md` 10.6절 — `AC-39` ~ `AC-43`) 검수 결과표

| 검증 코드 | 검증 항목 (`STRATEGY.md` 10.6절) | 코드 감사 · 운영 Supabase(`2026-11-13`) · Headless Chromium 실화면 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-39** | **1일 2회 배치(`16:05 KST` 가집계 + `20:30 KST` 최종 확정) 2-슬롯 완료 판정·덮어쓰기·공휴일 스킵 검증** | • `daily_batch.yml` 5개 크론(`5 7`, `25 7`, `30 11`, `47 11`, `17 12 * * 1-5`), `batch_slot` input, `setupDaily1605And2030Triggers()`, `is_in_daily_yield_window`(`15:55~16:45` & `20:10~21:20 KST`) 모두 정확히 반영<br/>• 6대 함정 E2E 시뮬레이션 통과: `16:05`(`07:05+00:00` UTC 저장) → `16:25` 백업 `0.00초` 스킵 → `20:30`(`final`, `min_updated_at_kst=20:00+09:00`) 스킵 없이 전 종목 100% 덮어쓰기(`ANCHOR-MISMATCH 0건`) → 부분 중단 시 미갱신 종목만 선별 이어받기 → `20:47` 백업 및 분기월 평일 공휴일 `0.00초` 스킵, 텔레그램 `[1차 정규장 가집계]` / `[2차 최종 확정]` 분리 확인 | **PASS** |
| **AC-40** | **`SNT다이내믹스` 등 `🚀 역배열 추세돌파` 승격 및 `[하락채널저항]`·`[역배열낙하]` 오판 제거 검증** | • `2026-11-13` 실DB `당일10%` `123종목` 전수 검증: `SNT다이내믹스`(`003570`), `SNT에너지`(`100840`), `아이엠바이오로직스`(`493280`)가 `Step 2` `🚀 역배열 추세돌파`(`turnaroundBreakout`)로 정상 승격 (`125일 ↔ 240봉` 차이 `0건`)<br/>• 하락 추세선 `+1.5%` 이상 양봉 돌파 `17종목` 전원 `[하락채널저항]` 오탐 해소 → `downChannelBreakout`(`하락추세돌파↑`) 전환 (`오탐 0건`), 비추천 역배열 사유 `[역배열·60일선저항]`(`9건`)·`[역배열·20일선저항]`(`10건`) 정상 세분화 (`오표기 0건`) | **PASS** |
| **AC-41** | **`watchlist.html` `수동등록·직접추가·역배열 추세돌파` 출신 종목의 `⚠️ 정리권고(매도 추천)` 오탐 제거 검증** | • 운영 DB 관심종목 `37종목` 전수 검증 결과 `EXIT` 오탐 `4건 → 0건`(`READY 1 · WAIT 24 · WATCH 12 · EXIT 0`); `SNT다이내믹스`·`솔브레인`·`피에스케이`·`현대모비스`·`RFHIC` 전원 `ema20Break=false, ema60Break=false` 확인 (`stop_price` 종가 이탈 시에만 `EXIT` 발동)<br/>• `planWatchlistMerge` 당일(`first_signal_date === T`) 재병합 시 `signal_count` 증가 없이 확정 수치 및 `"수동등록" → "역배열 추세돌파"` 승격 패치 정상 동작 | **PASS** |
| **AC-42** | **전 페이지(`index`·`watchlist`·`holdings`) · 전 종목(`추천·비추천·관심·보유·청산`) 차트 패턴 정보 상시 표기 검증** | • `describeStockPattern` 및 3페이지 우측 상세 헤더(`#detailBadgesBar`, `#wlDetailBrief`, `#hdDetailSummary`), `holdings.html` `-185달력일`(`126~145봉`) 확장 로드는 정상 작동<br/>• **미비(`[ISSUE-020]`)**: `mountProChartPanel`이 `st.badges`를 프로 차트 상단 화면 및 `[🔍 크게 보기]` 모달에 표시하지 않으며, 상세 헤더·PNG에 동일 배지가 2중 출력되고 `240일/720일` 전환 시 헤더 패턴 배지가 갱신되지 않음 | **FAIL (`ISSUE-020`)** |
| **AC-43** | **3페이지 리스트 극한 축소 · 무가로스크롤 · 최하단 1:1 높이 일치 및 `AC-1 ~ AC-38` 회귀 검증** | • 좌·우 최하단 높이 1:1 정렬(`3페이지 모두 bottomDiffPx = 0px`), `index.html` 행 배지 우측 이동, `watchlist.html` 무아이콘 행 버튼, 자동화 회귀 스위트 **`90 / 90` PASS** 확인<br/>• **결함(`[ISSUE-019]`)**: `index.html` 테이블 폭 `623px` > 가용폭 `508px(xl)`/`478px(lg)` + `overflow-x-hidden`으로 **8열 `연속일수` 및 9열 `작업 [🚫]` 버튼이 잘려 클릭 불가**; `watchlist.html`도 `414px` > `383px(lg)`으로 `[영구제외]` 버튼 우측 `15px` 절단 | **FAIL (`ISSUE-019`)** |

---

### 1.2 기존 요구사항 (`AC-1` ~ `AC-38`) 회귀 검증 요약 (`v2.6` 적용 후 전 항목 PASS 유지)

| 검증 코드 | 검증 항목 요약 | `v2.6` (`049d4d4`) 적용 후 회귀 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-1 ~ AC-18** | 유니버스(`1,463종목`), EMA·순수기관 수식, 5중 배치 Cron 확장, 멱등성 가드, 유동성 제외 필터, 9열 엑셀 | `test_screener_verification.py`(8/8), `test_v2_acceptance.py`(9/9), `--mode verify` 전 항목 오차 `0건` (`index.html` 7개 `<th>` 헤더 계약 보존) | **PASS** |
| **AC-19 ~ AC-23** | 차트 5년(`1,678,171행`) · 수급 3년(`1,040,512행`) 비대칭 적재, 앵커 EMA, 양보 구간 확장, 무지연 PK 조회 | `test_v23_acceptance.py`(19/19), 7종목 `1,233일 / 739일` 범위 및 2회 덮어쓰기 시 `ANCHOR-MISMATCH 0건` 무결성 유지 | **PASS** |
| **AC-24 ~ AC-29** | 3페이지 분리, 추천/비추천 기본 계약, 영구제외 즉시 반영, 스마트 병합, 보유/청산(`A안`), 텔레그램 폴백 | `test_v24_watchlist_holdings.py`(29/29) 무수정 100% 통과, 운영 DB 실등록 관심종목 `37건` 읽기 전용 검증 완료 및 무손상 보존 | **PASS** |
| **AC-30 ~ AC-38** | 무미래참조 패턴·캔들·4축 100점 평가, 2단 프로 차트, 크게 보기·PNG 저장, 와이드 뷰포트·전용 브리핑 | `test_v25_pattern_chart.py`(17/17) 전 항목 통과 (`ctx.clip()`, `Rm=68`, `ResizeObserver`/`resize` 정상 유지) | **PASS** |

---

## 2. 버그 및 수정 요청 트래커 (Issue & Fix Tracker)

### 🚨 2.1 `[프로그램 개발 및 수정]` 대화창 신규 수정 요청 사항 (`2건`)

#### 1. `[ISSUE-019]` (`AC-43` — 최우선 Critical) [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html) 및 [`watchlist.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/watchlist.html) 좌측 리스트 테이블 폭 초과 + `overflow-x-hidden` 결합으로 우측 컬럼·`[🚫 영구제외]` 버튼 절단(클릭 불가) 결함
* **현상 및 실측 근거 (Headless Chromium + Tailwind CSS 실구동 계측)**:
  1. **[`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L149-L165) & [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L872-L883)**: [`STRATEGY.md` `10.4.1`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L1300)에서 명시한 `<th>`/`<td>` 셀 패딩·폰트 축소(`px-1.5 py-1.5 text-[11px]`)가 누락된 채 기존 `text-xs`(`12px`)와 넓은 패딩(`px-3` / `px-2.5` = 좌우 `20~24px`)이 그대로 남아 있습니다. 그 결과 9개 컬럼 테이블 실제 폭이 **`623px`**(`29+130+70+70+64+74+75+64+45`)에 달하는 반면, `.slim-scroll` 래퍼는 `overflow-x-hidden`이고 가용 폭(`clientWidth`)이 **`508px`(`1920×1080 xl`) / `478px`(`1180×900 lg`)** 에 불과하여 **`1920×1080` 화면에서도 8열 `연속일수`(`60px` 잘림)와 9열 `작업 [🚫]` 영구제외 버튼(`105px` 완전 잘림)이 화면 밖으로 잘려 스크롤도 클릭도 불가능**합니다 (`lg`에서는 `외국인비중`까지 3개 열 절단).
  2. **[`watchlist.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/watchlist.html#L49-L61) & [`watchlist.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/watchlist.html#L181-L191)**: `<thead>`/`<tbody>`에 `text-xs`(`12px`)가 유지되어 6컬럼 테이블 폭이 **`414px`** 이며, `xl`(`410px`, 가용 `398px`)에서 `+16px`, `lg`(`395px`, 가용 `383px`)에서 `+31px` 초과하여 우측 끝 **`[영구제외]` 버튼 우측 `15px`가 절단**됩니다.
* **구체적 코드 수정 제안 (기존 그리드 클래스 단언 및 7개 `<th>` 텍스트 계약 100% 보존, Chromium 실측 `overflow = 0px` 검증 완료)**:
  1. **[`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L151-L165) 및 [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L872-L883)**:
     * 그리드 클래스(`lg:grid-cols-[490px_minmax(0,1fr)] xl:grid-cols-[520px_minmax(0,1fr)]`)와 `<th>` 텍스트 7종(`종목명`, `현재가`, `등락율`, `수급비중`, `수급금액`, `외국인비중`, `연속일수`)은 **절대 변경하지 마십시오** (`test_v26_acceptance.py` · `test_v2_acceptance.py` 계약 유지).
     * `<thead>` `<tr>`(`line 152`)을 `text-[10.5px] tracking-tight`, `#screenerTableBody`(`line 164`)를 `text-[11px]`로 줄이고, `<thead>` 모든 `<th>`(`lines 153-161`)와 `renderScreenerTable` 내 모든 `<td>`(`lines 874-882`)의 좌우 패딩을 **`px-[3px]`** (또는 `px-1` + 수치열 `px-[3px]`)로 축소하며, 종목명 `<span>`(`line 875`) 폭을 `w-[6em] max-w-[6em]`(`title` 전체명 유지), 작업 버튼(`line 882`)을 `px-1 py-0.5 text-[10px]`로 조정하십시오 → Chromium `1180×900(lg)` 최소 가용폭(`488px`)에서도 `scrollWidth === clientWidth === 488px` (`horizontalOverflowPx = 0px`, 9개 전 컬럼 100% 노출) 달성 확인 완료!
  2. **[`watchlist.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/watchlist.html#L49-L59) 및 [`watchlist.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/watchlist.html#L181-L191)**:
     * 그리드 클래스(`lg:grid-cols-[395px_minmax(0,1fr)] xl:grid-cols-[410px_minmax(0,1fr)]`)는 그대로 유지하고, `<thead>` `<tr>`(`line 49`)과 `#wlBody`(`line 58`)의 `text-xs`를 **`text-[11px]`** 로 변경하며, `<th>`/`<td>` 패딩을 **`px-1 py-1.5`**, 종목명 `<div class="w-[7em] max-w-[7em] truncate">`(`line 184`), 행 내 작업 버튼 3개(`lines 188-190`) 패딩을 `px-1 py-0.5 text-[10px]`로 조이십시오 → Chromium `1180×900(lg)` 최소 가용폭(`383px`)에서도 `scrollWidth === clientWidth === 383px` (`horizontalOverflowPx = 0px`) 달성 확인 완료!

#### 2. `[ISSUE-020]` (`AC-42` — High) 프로 차트 상단(`mountProChartPanel` · `[🔍 크게 보기]`) 패턴 배지 상시 표기 누락 및 상세 헤더/PNG 배지 중복·리로드 동기화 보완
* **현상 및 원인**:
  1. **프로 차트 상단 및 `[🔍 크게 보기]` 모달에 패턴 배지 미표시**: [`STRATEGY.md` `10.3.2`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L1285) 및 [`10.6 AC-42`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L1338)는 우측 상세 헤더뿐 아니라 **`PRO_PANEL.setData({ badges })`를 통해 프로 차트 상단(및 `[🔍 크게 보기]` 모달)에도 패턴·추세 진단 배지가 100% 상시 표시될 것**을 요구합니다. 현재 [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1389-L1504)의 `mountProChartPanel`은 `st.badges`를 저장만 하고 화면 DOM이나 캔버스 상단, `openBig()` 모달 어디에도 표시하지 않습니다(PNG 다운로드 시에만 사용).
  2. **동일 배지 중복 표기**: `index.html`(`lines 1232-1241, 1319`)에서 `SNT다이내믹스(003570)` 선택 시 `#detailBadgesBar`에 `🟢🚀 역배열 추세돌파`와 `🚀 역배열 추세돌파`가 중복 출력되고 PNG 헤더에도 `"🚀 역배열 추세돌파 · 🚀 하락추세선돌파 · 🚀 역배열 추세돌파"`로 중복 찍힙니다(비추천 `[하락채널저항]` + `⚠️ 하락채널저항` 및 `watchlist.html` `🌱 쌍바닥돌파` 중복 동일).
  3. **`240일/720일` 전환 시 헤더 미갱신 & PNG 파일명 이모지 잔존**:
     * [`watchlist.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/watchlist.html#L256) `onDataLoaded`에서 `EVAL[c]` 재계산 후 `renderDetailHeader` + `describeStockPattern` 배지 재부착 및 `PANEL.state.badges` 갱신이 누락되어 있고, [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L1290-L1293) `ensureStockFullChart`도 `attachRecommendation(stock)` 후 해당 행의 `🟢/⚪` 표시 및 추천/보류 탭 카운트 갱신이 누락되어 있습니다 (`PRO_PANEL` `onDataLoaded` `line 1307`도 동일).
     * [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1327) `sanitizeFilePart`가 구버전 이모지 10개만 제거하여 `🔄`, `🟦`, `📈`, `↗️`(`\uFE0F` 포함), `📉`, `🔨`, `✨`, `ℹ️` 등 `v2.6` 배지 이모지가 PNG 파일명에 남습니다.
* **구체적 코드 수정 제안**:
  1. **[`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1396-L1501) `mountProChartPanel`**:
     * `container.innerHTML`의 `bar` 바로 아래(또는 `brief` 위)에 `<div data-role="badges" class="flex flex-wrap items-center gap-1 text-[11px] mb-1"></div>`를 추가하고, `renderBadges()` 헬퍼에서 `[...new Set(st.badges || [])]`(비어 있으면 `describeStockPattern(st.candles, st.supplies, st.T).badges` 자동 폴백!)를 배지 칩으로 상시 렌더링하십시오 (`setData` 및 `fetchLong` 완료 시 모두 호출하면 일반 차트와 `openBig()` 모달 양쪽에 100% 자동 표시됩니다!).
     * `buildChartImageCanvas`(`line 1348`)에서도 `const badges = [...new Set(state.badges && state.badges.length ? state.badges : pats)];`로 중복을 제거하고, `sanitizeFilePart`(`line 1327`)를 `.replace(/[\p{Extended_Pictographic}\uFE0F\u200D↗↘↑↓]/gu, "")`로 일반화하십시오.
  2. **배지 중복 제거 및 `onDataLoaded` 동기화**:
     * [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L1232-L1243): `rec`에서 이미 표시된 태그(`rec.displayTag`, `rec.tag`, 또는 `rec.subReason === "[하락채널저항]"`일 때 `"⚠️ 하락채널저항"`)와 동일한 문자열은 `d.badges` 렌더링 시 제외하고, `PRO_PANEL.setData`(`line 1319`)에도 `[...new Set([...(rec && rec.recommended ? [rec.displayTag || rec.tag] : []), ...(stock.patternBadges || [])])]`로 중복 제거하여 전달하십시오. 또한 `ensureStockFullChart`(`line 1291`) 완료 시 좌측 행 점/탭 카운트도 동기화하십시오.
     * [`watchlist.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/watchlist.html#L256-L276): 패턴 배지 부착을 별도 헬퍼(예: `syncDetailAndBadges(it, ev)`)로 분리하여 `it.recommend_tag`와 동일한 문자열 중복을 제외해 `#wlDetailBrief`와 `PANEL.state.badges`에 반영하고, `onDataLoaded`(`line 256`)에서도 `SELECTED === c`일 때 동일 헬퍼를 호출하십시오.

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
