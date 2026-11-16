# 🧪 LS 수급·차트 스크리너 검증 및 테스트 리포트 (`TEST_REPORT.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[검증 및 테스트]` 전담 대화창**에서 테스트 실행 결과, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md) 대조 검수, 데이터 정합성 검증 리포트, 발견된 버그 및 구체적인 코드 수정 제안을 기록하는 문서입니다.
> * **`[프로그램 개발 및 수정(메인)]` 대화창**은 작업 시작 전 본 `TEST_REPORT.md`와 `STRATEGY.md`를 확인하여 미해결 버그(`2.1절 신규 수정 요청 사항`)를 코드에 반영하고, 수정이 완료된 항목의 상태를 **`[해결 완료]`**로 업데이트합니다.

---

## 1. 최신 검수 요약 (`v2.7.1` 커밋 `179f0cf` 최종 전수 검수 — `AC-1 ~ AC-48` 전 항목 최종 PASS · `ISSUE-021 ~ ISSUE-022` 해결 완료)

* **검수 일시**: `2026-11-16 17:36 KST` (`2026-11-16 08:36 UTC`)
* **대상 커밋**: `179f0cf` — `fix(v2.7.1): ISSUE-021 비개장일 가짜 봉 차단, ISSUE-022 실시간 봉 해제·PNG 반영` ([`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L1343-L1480) `11절` `AC-44 ~ AC-48` 전 요구사항)
* **단위·통합 테스트 스위트 및 회귀 검증 실행 결과 (`총 111 / 111 통과 — ALL PASS`)**:
  * `python3 test_screener_verification.py`: **8 / 8 통과 (`OK`)**
  * `python3 -m unittest discover -s tests -v`: **103 / 103 통과 (`OK`, `6.91s` — `test_v27_acceptance.py` `18개`[`TestIssue021022` 4개 포함] + `test_v26_acceptance.py` `11개` + `test_v25_pattern_chart.py` `17개` + `test_v24_watchlist_holdings.py` `29개` + `test_v23_acceptance.py` `19개` + `test_v2_acceptance.py` `9개`)**
  * `python3 run_daily_screener.py --mode verify`: **전 항목 정상 통과 (`Exit 0`, `1,463` 유니버스 · 차트 `1,233일` · 수급 `739일` · `2026-11-13` 스크리닝 `123 / 81 / 47 / 43 / 4` 무손상, 운영 DB `관심 37건 · 보유 1건 · 제외 0건` 읽기 전용 무손상 보존)**
* **Headless Chromium(`Tailwind CSS` 실구동) 3페이지·2해상도(`1920×1080 xl` / `1180×900 lg`) 실화면 계측 + 실시간 시세·비개장일 엣지케이스 최종 검증 결과**:
  * ✅ **`AC-44` PASS (3페이지 단일 슬림 상단바 `40px` 통합 · 배너 삭제 · `EMA 5~240` 1줄 `27px` 스트립 · 전체 영역 대폭 상단 이동)**:
    * 3페이지 모두 최상단 `<header>`가 **`height: 40px`(`top: 10px`)** 단일 1줄로 통합되었고, `watchlist.html`(`⭐ 관심종목 작전판` 배너 삭제)·`holdings.html`(`💼 보유종목 & 청산 히스토리` 배너 삭제)은 좌측 리스트 상단 `114px`, `index.html`은 `134px`로 상단 이동하여 `1080p` 화면 내 하단 `🏛️ 투자주체별 순매수 상세 분석` 카드(`top: 980px`)까지 진입했습니다.
    * [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L116-L133) 좌측 리스트 상단 바(`포착된 종목 리스트` + `52종목` + `⭐ 선택 종목 관심종목 병합 (52)` + `📥 엑셀 저장`)가 `xl`(`518px`)·`lg`(`488px`) 모두 **`height: 44px` 단 1줄, 버튼 잘림 `0px`** 로 정렬되며, `EMA 5~240` `27px` 1줄 스트립, 메인 3페이지 차트 `hideInlineBadges: true`(`hidden`), `[🔍 크게 보기]` 모달 내 배지 노출(`2개`)이 정확히 동작합니다.
  * ✅ **`AC-45` PASS (`ISSUE-021` 해결 확인 — 4단계 폴백 체인 · PNA/CORS 로컬 브릿지 · 주말/공휴일/장전 가짜 당일 봉 및 `전일비 100%` 오탐 완전 차단)**:
    * 코드·DB 내 `LS_APP_KEY`/`LS_APP_SECRET` 하드코딩 노출 `0건`, [`scripts/ls_realtime_bridge.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/scripts/ls_realtime_bridge.py#L61-L107) 표준 라이브러리 구성 및 `/health`·`OPTIONS` `Access-Control-Allow-Private-Network: true` 헤더, 네이버 JSONP `<script>` 및 전역 콜백 자동 정리, `fetchBridge` `h.configured !== false` 체크 모두 확인 완료.
    * [`parseNaverRealtime`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1706-L1718) 날짜 롤백 + [`normalizeQuoteForCandles`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1617-L1630) 캔들 대조 가드 + 브릿지 `_kst_trade_date`/`_market_state` 적용으로 **일요일(`2026-11-15 15:00 KST`), 월요일 개장 전(`2026-11-16 08:20 KST`), 평일 공휴일(`2026-12-25 14:00 KST`) 스냅샷 모두 직전 거래일로 정확히 보정(`mergedLen = 2`, 가짜 봉 `0건`, 직전 거래일 실제 전일비 `284.62%` 유지)** 됨을 실증했습니다.
  * ✅ **`AC-46` PASS (3페이지 대형 1줄 시세 헤더 + `당일 거래량` · `거래량 전일비(%)` 전 탭·전 종목 연동 + 신규 상장 단일봉 등락률 폴백)**:
    * `index.html` **`🟢 추천 후보`(`SNT다이내믹스` `30,350원 / ▲ 2,050 / +7.24% / 거래량 220,043 / 전일비 47.28% / 🟢 실시간`)** · **`⚪ 비추천 보류`(`미스토홀딩스` `44,100원 / ▲ 1,150 / +2.68% / 거래량 85,000 / 전일비 19.42%`)** · `전체` 탭(좌측 행 `28,300` 기준일 보존), `watchlist.html`(실시간 수익률 `+7.2%`·종합판단 점수 연동), `holdings.html`(`HOLDING` 실시간 수익률 `+14.53%`·손익 `+385,000원` 연동), 단일 일봉(`prevClose === 0`) 신규 상장주 초기 등락률(`+10.34%`) 폴백까지 모두 정상 작동합니다.
  * ✅ **`AC-47` PASS (`ISSUE-022` 해결 확인 — 프로 차트 실시간 봉 · 증분 EMA · 현재가 태그 · `HOLDING → CLOSED` 격리 · PNG/클립보드 실시간 봉 반영)**:
    * [`mountProChartPanel.setData`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1526) `d.liveQuote !== undefined` 적용 및 [`holdings.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/holdings.html#L224-L225) `CLOSED` 선택 시 `LiveQuoteManager.stop()` 정리로, Headless Chromium에서 **보유 중인 `SNT다이내믹스(003570)` 조회 후 동일 종목의 과거 청산 이력(`003570`, `2026-10-30`) 클릭 시 `panelLiveQuote === null`, `panelLastCandleDate === "2026-10-30"`로 과거 차트 오염 `0건`** 확인 완료.
    * `📸 이미지 저장` / `📋 클립보드 복사`(`act === "png" | "copy"`) 시 `candles: viewCandles()` 전달로 저장 이미지에도 실시간 당일 봉·현재가 태그가 화면과 100% 동일하게 반영되며, `updateLive` 및 `240일` 장기 차트 로드 시 기간·레이어(`period=240`, `bb=false`) 무깜빡임 유지 확인 완료.
  * ✅ **`AC-48` PASS (`AC-1 ~ AC-48` 전 스위트 총 `111 / 111` 통과, 3페이지 런타임 예외 `0건`, 무가로스크롤 `overflow 0px`, 하단 정렬 `bottomDiffPx = 0px`)**.

---

### 1.1 `v2.7 / v2.7.1` 신규 합격 기준 (`STRATEGY.md` 11.6절 — `AC-44` ~ `AC-48`) 최종 검수 결과표

| 검증 코드 | 검증 항목 (`STRATEGY.md` 11.6절) | 코드 감사 · 운영 Supabase(`2026-11-13`) · Headless Chromium 실화면 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-44** | **3페이지 상단 불필요 영역 삭제 · 단일 1줄 상단바 통합 · `EMA 5~240` 1줄 최소화 및 전체 영역 상단 이동 검증** | • 3페이지 모두 단일 `<header>` `40px` 1줄 통합(`watchlist`·`holdings` 타이틀 배너 완전 제거), 좌측 리스트 상단 `114px~134px` 상단 이동(`1080p` 내 하단 수급 분석 카드 진입)<br/>• `index.html` 좌측 리스트 상단 바 `xl`/`lg` 모두 `44px` 1줄 정렬(버튼 잘림 `0px`), `EMA 5~240` `27px` 1줄 스트립, 메인 3페이지 `hideInlineBadges: true` 및 `[🔍 크게 보기]` 모달 내 배지 노출 정상 | **PASS** |
| **AC-45** | **다중 티어 실시간 시세 엔진(`LiveQuoteManager`) & 로컬 LS 브릿지(`scripts/ls_realtime_bridge.py`) 보안·폴백·장전 가드 검증** | • 시크릿 하드코딩 `0건`, 표준 라이브러리 `ls_realtime_bridge.py` `/health`·`OPTIONS` PNA/CORS 헤더(`Access-Control-Allow-Private-Network: true`), 네이버 JSONP `<script>`/콜백 자동 제거, Tier 3 무상한 `limit=2` 폴백 확인<br/>• 주말·평일 `09:00 KST` 이전 날짜 롤백 및 `normalizeQuoteForCandles` 캔들 대조 가드로 주말·공휴일·장전 가짜 봉 `0건` 및 실제 전일비 정상 유지(`ISSUE-021` 해결) | **PASS** |
| **AC-46** | **3페이지 우측 종목 헤더 대형화 + `당일 거래량` · `거래량 전일비(%)` 계산 및 `추천·비추천·전체` 전 종목 적용 검증** | • `computeQuoteMetrics` 전일비 수식(`42.95%`, `prevVolume <= 0 → null`, 단일봉 `last.change_rate` 폴백) 정확히 일치<br/>• `index.html`(`추천 후보`·`비추천 보류`·`전체`, 좌측 행 기준일 수치 보존), `watchlist.html`(실시간 수익률·100점 평가 연동), `holdings.html`(`HOLDING` 실시간 손익·수익률 연동) 전 페이지 1줄 대형 헤더 정상 작동 | **PASS** |
| **AC-47** | **프로 차트(`PRO_PANEL`) 당일 실시간 캔들 · 증분 EMA(5~240) · 현재가 수평태그 무깜빡임 연동 검증** | • `mergeLiveQuoteIntoCandles` 원본 불변·증분 EMA·단일가 합성, `updateLive` 및 `240일` 로드 시 레이어·기간 유지, 현재가 수평 점선·우측 가격표(`Rm=68`) 작도 정상<br/>• `holdings.html` 동일 종목 `HOLDING → CLOSED` 전환 시 `panelLiveQuote === null` 완전 격리 및 PNG/클립보드 저장 시 `viewCandles()` 실시간 봉 반영(`ISSUE-022` 해결) | **PASS** |
| **AC-48** | **기존 `AC-1 ~ AC-43` 전 스위트 무결성 회귀 및 Node/브라우저 무오류 검증** | • `test_screener_verification.py`(8/8) + `tests/test_*.py`(103/103) = **`111 / 111` 100% PASS**, `--mode verify` `Exit 0`, Headless Chromium 3페이지 런타임 예외 `0건`, 좌·우 하단 정렬(`bottomDiffPx = 0px`) 및 무가로스크롤(`overflow = 0px`) 유지 | **PASS** |

---

### 1.2 기존 요구사항 (`AC-1` ~ `AC-43`) 회귀 검증 요약 (`v2.7.1` 적용 후 전 항목 PASS 유지)

| 검증 코드 | 검증 항목 요약 | `v2.7.1` (`179f0cf`) 적용 후 회귀 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-1 ~ AC-18** | 유니버스(`1,463종목`), EMA·순수기관 수식, 5중 배치 Cron, 멱등성 가드, 유동성 제외 필터, 9열 엑셀 | `test_screener_verification.py`(8/8), `test_v2_acceptance.py`(9/9), `--mode verify` 오차 `0건` (`<h1>`, 순수기관 공식, 7개 `<th>` 보존) | **PASS** |
| **AC-19 ~ AC-23** | 차트 5년(`1,233일`) · 수급 3년(`739일`) 비대칭 적재, 앵커 EMA, 양보 구간, 무지연 PK 조회 | `test_v23_acceptance.py`(19/19) 전 항목 정상 통과 | **PASS** |
| **AC-24 ~ AC-29** | 3페이지 분리, 추천/비추천 분류, 영구제외 즉시 반영, 스마트 병합, 보유/청산(`A안`), 텔레그램 폴백 | `test_v24_watchlist_holdings.py`(29/29) 통과, 운영 DB(`관심 37 · 보유 1 · 제외 0`) 읽기 전용 무손상 보존 | **PASS** |
| **AC-30 ~ AC-38** | 무미래참조 패턴·캔들·4축 100점 평가, 2단 프로 차트, 크게 보기·PNG 저장, 와이드 뷰포트 | `test_v25_pattern_chart.py`(17/17) 전 항목 통과 | **PASS** |
| **AC-39 ~ AC-43** | 1일 2회 배치(`16:05`/`20:30`), `역배열 추세돌파` 승격, 관심종목 매도권고 오탐 제거, 3페이지 초슬림 리스트(`overflow 0px`) | `test_v26_acceptance.py`(11/11) 통과, Chromium `1920×1080` & `1180×900` `tableOverflowX = 0px`, `bottomDiffPx = 0px` 유지 | **PASS** |

---

## 2. 버그 및 수정 요청 트래커 (Issue & Fix Tracker)

### 🚨 2.1 `[프로그램 개발 및 수정]` 대화창 신규 수정 요청 사항

* **현재 미해결 버그 없음 (`0건`) — `AC-1 ~ AC-48` 전 항목 최종 합격(`ALL PASS`).**

---

### ✅ 2.2 해결 완료된 이슈 히스토리 아카이브

* **[ISSUE-021 ~ ISSUE-022] `[해결 완료 (v2.7.1, 179f0cf)]`** `parseNaverRealtime` 주말·장전(`09:00 KST` 이전) 날짜 보정 + `normalizeQuoteForCandles` 캔들 대조 기반 평일 공휴일·장전 중복 스냅샷 차단 + `ls_realtime_bridge.py` `_kst_trade_date`/`_market_state` 및 `h.configured !== false` 체크로 가짜 당일 봉 복제·`전일비 100%` 오탐 완전 해소(`ISSUE-021`), `mountProChartPanel.setData` `d.liveQuote !== undefined` 처리·`holdings.html` `CLOSED` 선택 시 폴링 중지·PNG/클립보드 저장 시 `viewCandles()` 반영·단일 일봉 `change_rate` 폴백 완료(`ISSUE-022`) (`AC-44 ~ AC-48` 전 항목 합격).
* **[ISSUE-019 ~ ISSUE-020] `[해결 완료 (v2.6.1, f768119)]`** `index.html`(`text-[10.5px]`/`text-[11px]`, `px-[3px]`, `w-[6em]`) 및 `watchlist.html`(`text-[11px]`, `px-1`, `w-[7em]`) 슬림화로 `1920×1080(xl)`·`1180×900(lg)` 전 구간 좌측 테이블 `horizontalOverflowPx = 0px`·우측 버튼 절단 `0px` 달성(`ISSUE-019`), `mountProChartPanel` `[data-role="badges"]` 상시 렌더링(일반 차트 + `[🔍 크게 보기]` 모달 + `describeStockPattern` 자동 폴백)·배지 중복 제거·`240일/720일` 로드 후 추천/헤더/행 점 동기화·`sanitizeFilePart` 유니코드 이모지 정제 완료(`ISSUE-020`) (`AC-39 ~ AC-43` 전 항목 합격).
* **[v2.5.2 검증 완료 (`f7aa980`)]** 3페이지 와이드 뷰포트(`max-w-[1920px] 2xl:max-w-[96vw]`) 전면 개방, `watchlist.html` 좌측 `6컬럼`(`440/470px`) 초슬림화 + 우측 `#wlDetailHeader`(시총·등락폭·종합판단·패턴·기관수급·상태 2단 브리핑) 신설, 3페이지 프로 차트 대화면 확장(`560~760px` / `480~640px` / 모달 `max-w-[95vw]` `620~840px`)·하단 2열 배치·`ResizeObserver`/`resize` 자동 리사이즈(`AC-36 ~ AC-38`) 전 항목 합격.
* **[ISSUE-015 ~ ISSUE-018] `[해결 완료 (v2.5.1, 9bbc56f)]`** `index.html` 수급 `240건` 병렬 보강(`ISSUE-015`), 서브태그 중복 제거 및 비추천 `[하락채널저항]` `22/22` 노출(`ISSUE-016`), `holdings.html` 선택 행 캐시 격리·`setData` `dataKey` 리셋·`drawProChart` 상단 `ctx.clip()` 적용(`ISSUE-017`), `flag` 양봉(`C > O`) 조건 및 `watchlist.html` `종합판단` 정렬 토글(`ISSUE-018`) 해결 완료 (`AC-30 ~ AC-35` 합격).
* **[ISSUE-011 ~ ISSUE-014] `[해결 완료 (v2.4.1, 16f575d + 운영 DB RLS 해제/GRANT 반영)]`** 운영 Supabase 신규 3개 테이블 실서버 CRUD 정상화 및 `42501` 배너, 대바닥 출신 관심종목 이평 이탈 오판 제거, 제외관리 모달 복구·프리셋 체크박스 즉시 반영, 보유종목 현재가 목표가 배지 및 `CLOSED` 온디맨드 차트 로드(`AC-24 ~ AC-29`) 전 항목 합격.
* **[v2.3.1 검증 완료 (`353f92a`, `Run #43682739754` & `Run #43685346608`)]** 차트 5년(`2021-11-01~`, `1,678,171행`) · 수급 3년(`2023-11-01~`, `1,040,512행`) 비대칭 확장 백필 1회차 `2시간 44분` 100% 완주, 앵커 시드 EMA 연속성, 거래정지 `25종목` 미확정 오판 차단, `80분` 주기 토큰 자동 갱신 및 `271.8만 행` 대용량 DB 무지연(`AC-19 ~ AC-23`) 전 항목 합격.
* **[v2.2 검증 완료 (`6bfbbd5`)]** `[기관 수급 발생 종목]` 유동성·수급금액 제외 필터(`당일 기준` vs `3일 연속 3일 평균 기준`) 및 `[엑셀 저장]` 9개 컬럼 개편(`AC-16 ~ AC-18`) 전 항목 합격.
* **[v2.1 검증 완료 (`1aecd41`)]** `20:30 KST` 다중 백업 Cron, `KST` 표준시 고정, `--skip-if-completed` 멱등성 가드(`< 2.3초` 종료), `if: failure()` 장애 알림, Apps Script 외부 정각 웹훅(`AC-13 ~ AC-15`) 및 `두산에너빌리티(034020)` 백필 자동 복구 확인 완료.
* **[ISSUE-006 ~ ISSUE-010] `[해결 완료 (v1.4.3 ~ v2.0)]`** `PRIORITY_SHCODES` 제거, `has_2yr_history` 판정 분리, 장중 미확정 수급 차단, 복합 PK 병렬 조회 전환(`HTTP 500` 해소), `AC-1 ~ AC-12` 검증 체계 구축 완료.
* **[ISSUE-001 ~ ISSUE-005] `[해결 완료 (v1.4)]`** 1,463종목 시총 ≥ 700억 전수 유니버스 구축, 일봉·수급 500영업일 역순 슬라이딩 적재, Actions 360분 타임아웃 상향 완료.
