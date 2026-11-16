# 🧪 LS 수급·차트 스크리너 검증 및 테스트 리포트 (`TEST_REPORT.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[검증 및 테스트]` 전담 대화창**에서 테스트 실행 결과, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md) 대조 검수, 데이터 정합성 검증 리포트, 발견된 버그 및 구체적인 코드 수정 제안을 기록하는 문서입니다.
> * **`[프로그램 개발 및 수정(메인)]` 대화창**은 작업 시작 전 본 `TEST_REPORT.md`와 `STRATEGY.md`를 확인하여 미해결 버그(`2.1절 신규 수정 요청 사항`)를 코드에 반영하고, 수정이 완료된 항목의 상태를 **`[해결 완료]`**로 업데이트합니다.

---

## 1. 최신 검수 요약 (`v2.7` 커밋 `a3478f0` 1차 전수 검수 — `AC-44 · AC-46 · AC-48` 및 `AC-1 ~ AC-43` PASS / 주말·장전 가짜 봉·전일비 100% 오탐 및 청산 차트 실시간 오염 `ISSUE-021 · ISSUE-022` 수정 요청)

* **검수 일시**: `2026-11-16 16:54 KST` (`2026-11-16 07:54 UTC`)
* **대상 커밋**: `a3478f0` — `feat(v2.7): 상단 슬림화, 실시간 시세 엔진·로컬 브릿지, 거래량 전일비, 프로 차트 실시간 봉` ([`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L1343-L1480) `11절` `AC-44 ~ AC-48`)
* **단위·통합 테스트 스위트 및 회귀 검증 실행 결과 (`총 107 / 107 통과`)**:
  * `python3 test_screener_verification.py`: **8 / 8 통과 (`OK`)**
  * `python3 -m unittest discover -s tests -v`: **99 / 99 통과 (`OK`, `4.96s` — `test_v27_acceptance.py` `14개` 신설 + `test_v26_acceptance.py` `11개` + `test_v25_pattern_chart.py` `17개` + `test_v24_watchlist_holdings.py` `29개` + `test_v23_acceptance.py` `19개` + `test_v2_acceptance.py` `9개`)**
  * `python3 run_daily_screener.py --mode verify`: **전 항목 정상 통과 (`Exit 0`, `1,463` 유니버스 · 차트 `1,233일` · 수급 `739일` · `2026-11-13` 스크리닝 `123 / 81 / 47 / 43 / 4` 무손상, 운영 DB `관심 37건 · 보유 1건 · 제외 0건` 읽기 전용 무손상 보존)**
* **Headless Chromium(`Tailwind CSS` 실구동) 3페이지·2해상도(`1920×1080 xl` / `1180×900 lg`) 실화면 계측 + 실시간 시세 엣지케이스 정밀 검증 결과**:
  * ✅ **`AC-44` PASS (3페이지 단일 슬림 상단바 `40px` 통합 · 배너 삭제 · `EMA 5~240` 1줄 `27px` 스트립 · 전체 영역 대폭 상단 이동)**:
    * Headless Chromium 실측 결과 3페이지 모두 최상단 `<header>` 높이가 **`40px`(`top: 10px`)** 단일 1줄로 통합되었고, `watchlist.html`(`⭐ 관심종목 작전판` 배너 삭제)·`holdings.html`(`💼 보유종목 & 청산 히스토리` 배너 삭제)은 좌측 리스트 상단이 **`114px`**, `index.html`은 컨트롤 바(`height: 68px`) 직하단 **`134px`** 까지 끌어올려져 `1920×1080` 화면 안에 하단 `🏛️ 투자주체별 순매수 상세 분석` 카드(`top: 980px`)까지 진입했습니다.
    * [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L116-L133) 좌측 리스트 상단 바(`🔍 포착된 종목 리스트` + `52종목` + `⭐ 선택 종목 관심종목 병합 (52)` + `📥 엑셀 저장`)도 `1920×1080`(`518px`)과 `1180×900`(`488px`) 양쪽 모두 **`height: 44px` 단 1줄, 우측 잘림 `0px`(`mergeBtnClippedRightPx = 0`, `excelBtnClippedRightPx = 0`)** 로 정렬되었으며, `EMA 5~240` 1줄 스트립(`height: 27px`), 메인 3페이지 차트 내부 `hideInlineBadges: true`(`hidden`), `[🔍 크게 보기]` 모달 내 배지 노출(`bigBadgesHidden = false, 2개`) 모두 완벽히 작동합니다.
  * ✅ **`AC-46` PASS (3페이지 대형 1줄 시세 헤더 + `당일 거래량` · `거래량 전일비(%)` 전 탭·전 종목 연동)**:
    * `computeQuoteMetrics` 수식(`round2(volume / prevVolume * 100)`, `prevVolume <= 0` 시 `null → "-"`) 검증 완료.
    * Headless Chromium 실시간 브릿지 주입 검증 결과: `index.html` **`🟢 추천 후보`(`SNT다이내믹스` `30,350원 / ▲ 2,050 / +7.24% / 거래량 220,043 / 전일비 47.28% / 🟢 실시간`)** · **`⚪ 비추천 보류`(`미스토홀딩스` `44,100원 / ▲ 1,150 / +2.68% / 거래량 85,000 / 전일비 19.42%`)** · `전체` 탭(좌측 테이블 행 `28,300` 기준일 정합성 보존), `watchlist.html`(`최초포착 대비 +7.2%` 및 종합판단 점수 실시간 갱신), `holdings.html`(`HOLDING` `수익률 +14.53% · 손익 +385,000원` 실시간 갱신) 모두 정확히 작동합니다.
  * ✅ **`AC-48` PASS (`AC-1 ~ AC-43` 전 회귀 스위트 + 신규 스위트 총 `107 / 107` 통과, 브라우저 런타임 예외 `0건`)**.
  * ⚠️ **`AC-45` FAIL → `[ISSUE-021]` (주말·공휴일·평일 개장 전 `00:00~08:59 KST`에 네이버 JSONP `res.time` 및 `ls_realtime_bridge.py` 서버 시각이 그대로 `tradeDate`로 찍혀 직전 거래일 종가 봉이 가짜 당일 캔들로 복제되고 전 종목 `전일비 100.00%`가 오표시되는 결함)**:
    * 시크릿 노출 `0건`, 표준 라이브러리 로컬 브릿지 PNA/CORS 헤더(`Access-Control-Allow-Private-Network: true`), JSONP `<script>` 및 전역 콜백 정리, `open=0 && volume=0` 가드는 정상 작동합니다.
    * **그러나 실제 네이버 폴링 API(`polling.finance.naver.com`) 및 LS `t1102`는 토·일요일, 공휴일, 평일 아침 개장 전(`00:00~08:30 KST` 동시호가 리셋 전)에도 `open=0, volume=0`이 아니라 직전 거래일(예: 금요일 `2026-11-13`)의 확정 시가·고가·저가·종가·누적거래량(`ov=26150 > 0, aq=512323 > 0, ms="CLOSE"`)을 그대로 내려주면서 `res.time`만 조회 시점 현재 시각(예: 일요일 `2026-11-15`, 월요일 `08:20 KST`)으로 반환**합니다.
    * 그 결과 `isPreOpenEmptyQuote`가 통과되어 **주말·공휴일·평일 09시 이전 접속 시 모든 종목에 가짜 주말/장전 일봉(`_live: true, change_rate: 0%`)이 복제 추가되고 `EMA 5~240`이 왜곡되며, 금요일 거래량을 금요일 거래량으로 나누어 모든 종목에 `전일비 100.00%` 및 `당일시세 2026-11-15(일요일)`가 찍히는 치명적 오작동**이 재현되었습니다 (`2.1절 ISSUE-021` 참조).
  * ⚠️ **`AC-47` 부분 미결 → `[ISSUE-022]` (`holdings.html` 동일 종목 `HOLDING → CLOSED` 전환 시 `setData` `liveQuote: null` 무시에 따른 과거 청산 차트 실시간 봉 오염 & PNG/클립보드 저장 시 실시간 봉 미반영)**:
    * `mergeLiveQuoteIntoCandles` 원본 불변성, 증분 `EMA 5~240`, 단일가 합성, `updateLive` 상태 유지(`240일`, `BB스퀴즈 해제` 유지), 우측 Y축 현재가 점선·태그(`Price Pill`) 작도는 정상입니다.
    * 단, [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1526) `mountProChartPanel.setData`의 `st.liveQuote = d.liveQuote || (prevCode === d.shcode ? st.liveQuote : null)` 코드가 명시적 `liveQuote: null`을 falsy로 무시하여, **`holdings.html`에서 현재 보유 중인 종목(`003570`)을 본 뒤 동일 종목의 과거 청산 이력(`003570`, `2026-10-30`)을 클릭하면 과거 청산 차트 끝에 `2026-11-16` 실시간 봉(`30,350원`)이 달라붙어 차트가 오염**되는 현상이 Chromium E2E에서 실측되었고, `downloadChartPng`/`copyChartToClipboard` 시 `viewCandles()` 대신 원본 `st.candles`가 그려져 실시간 봉이 PNG에서 누락됩니다 (`2.1절 ISSUE-022` 참조).

---

### 1.1 `v2.7` 신규 합격 기준 (`STRATEGY.md` 11.6절 — `AC-44` ~ `AC-48`) 검수 결과표

| 검증 코드 | 검증 항목 (`STRATEGY.md` 11.6절) | 코드 감사 · 운영 Supabase(`2026-11-13`) · Headless Chromium 실화면 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-44** | **3페이지 상단 불필요 영역 삭제 · 단일 1줄 상단바 통합 · `EMA 5~240` 1줄 최소화 및 전체 영역 상단 이동 검증** | • 3페이지 모두 단일 `<header>` `40px` 1줄 통합(`watchlist`·`holdings` 타이틀 배너 완전 제거), 좌측 리스트 상단 `114px~134px` 상단 이동(`1080p` 내 하단 수급 분석 카드 진입)<br/>• `index.html` 좌측 리스트 상단 바 `xl`/`lg` 모두 `44px` 1줄 정렬(버튼 잘림 `0px`), `EMA 5~240` `27px` 1줄 스트립, 메인 3페이지 `hideInlineBadges: true` 및 `[🔍 크게 보기]` 모달 내 배지 노출 정상 | **PASS** |
| **AC-45** | **다중 티어 실시간 시세 엔진(`LiveQuoteManager`) & 로컬 LS 브릿지(`scripts/ls_realtime_bridge.py`) 보안·폴백·장전 가드 검증** | • 시크릿 하드코딩 `0건`, 표준 라이브러리 `ls_realtime_bridge.py` `/health`·`OPTIONS` PNA/CORS 헤더(`Access-Control-Allow-Private-Network: true`), 네이버 JSONP `<script>`/콜백 자동 제거, Tier 3 무상한 `limit=2` 폴백 확인<br/>• **결함(`[ISSUE-021]`)**: 주말·공휴일·평일 `09:00 KST` 이전에 네이버 JSONP(`ms="CLOSE"`, 전일 `ov>0, aq>0` 유지) 및 `ls_realtime_bridge.py`(`marketState="OPEN"` 고정)가 조회 시점 날짜를 그대로 `tradeDate`로 부여해 가짜 봉 추가 및 `전일비 100.00%` 오표시 발생 | **FAIL (`ISSUE-021`)** |
| **AC-46** | **3페이지 우측 종목 헤더 대형화 + `당일 거래량` · `거래량 전일비(%)` 계산 및 `추천·비추천·전체` 전 종목 적용 검증** | • `computeQuoteMetrics` 전일비 수식(`42.95%`, `prevVolume <= 0 → null`) 정확히 일치<br/>• `index.html`(`추천 후보`·`비추천 보류`·`전체`, 좌측 행 기준일 수치 보존), `watchlist.html`(실시간 수익률·100점 평가 연동), `holdings.html`(`HOLDING` 실시간 손익·수익률 연동) 전 페이지 1줄 대형 헤더 정상 작동 | **PASS** |
| **AC-47** | **프로 차트(`PRO_PANEL`) 당일 실시간 캔들 · 증분 EMA(5~240) · 현재가 수평태그 무깜빡임 연동 검증** | • `mergeLiveQuoteIntoCandles` 원본 불변·증분 EMA·단일가 합성, `updateLive` 및 `240일` 로드 시 레이어·기간 유지, 현재가 수평 점선·우측 가격표(`Rm=68`) 작도 정상<br/>• **미비(`[ISSUE-021 · ISSUE-022]`)**: 주말·공휴일·장전 가짜 캔들 오염(`ISSUE-021`), `setData`의 `d.liveQuote || ...` 처리로 동일 종목 `HOLDING → CLOSED` 전환 시 과거 청산 차트에 실시간 봉 잔존 및 PNG/클립보드 저장 시 실시간 봉 미반영(`ISSUE-022`) | **FAIL (`ISSUE-021 · 022`)** |
| **AC-48** | **기존 `AC-1 ~ AC-43` 전 스위트 무결성 회귀 및 Node/브라우저 무오류 검증** | • `test_screener_verification.py`(8/8) + `tests/test_*.py`(99/99) = **`107 / 107` 100% PASS**, `--mode verify` `Exit 0`, Headless Chromium 3페이지 런타임 예외 `0건`, 좌·우 하단 정렬(`bottomDiffPx = 0px`) 및 무가로스크롤(`overflow = 0px`) 유지 | **PASS** |

---

### 1.2 기존 요구사항 (`AC-1` ~ `AC-43`) 회귀 검증 요약 (`v2.7` 적용 후 전 항목 PASS 유지)

| 검증 코드 | 검증 항목 요약 | `v2.7` (`a3478f0`) 적용 후 회귀 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-1 ~ AC-18** | 유니버스(`1,463종목`), EMA·순수기관 수식, 5중 배치 Cron, 멱등성 가드, 유동성 제외 필터, 9열 엑셀 | `test_screener_verification.py`(8/8), `test_v2_acceptance.py`(9/9), `--mode verify` 오차 `0건` (`<h1>`, 순수기관 공식, 7개 `<th>` 보존) | **PASS** |
| **AC-19 ~ AC-23** | 차트 5년(`1,233일`) · 수급 3년(`739일`) 비대칭 적재, 앵커 EMA, 양보 구간, 무지연 PK 조회 | `test_v23_acceptance.py`(19/19) 전 항목 정상 통과 | **PASS** |
| **AC-24 ~ AC-29** | 3페이지 분리, 추천/비추천 분류, 영구제외 즉시 반영, 스마트 병합, 보유/청산(`A안`), 텔레그램 폴백 | `test_v24_watchlist_holdings.py`(29/29) 통과, 운영 DB(`관심 37 · 보유 1 · 제외 0`) 읽기 전용 무손상 보존 | **PASS** |
| **AC-30 ~ AC-38** | 무미래참조 패턴·캔들·4축 100점 평가, 2단 프로 차트, 크게 보기·PNG 저장, 와이드 뷰포트 | `test_v25_pattern_chart.py`(17/17) 전 항목 통과 | **PASS** |
| **AC-39 ~ AC-43** | 1일 2회 배치(`16:05`/`20:30`), `역배열 추세돌파` 승격, 관심종목 매도권고 오탐 제거, 3페이지 초슬림 리스트(`overflow 0px`) | `test_v26_acceptance.py`(11/11) 통과, Chromium `1920×1080` & `1180×900` `tableOverflowX = 0px`, `bottomDiffPx = 0px` 유지 | **PASS** |

---

## 2. 버그 및 수정 요청 트래커 (Issue & Fix Tracker)

### 🚨 2.1 `[프로그램 개발 및 수정]` 대화창 신규 수정 요청 사항 (`2건`)

#### 1. `[ISSUE-021]` (`AC-45 · AC-47` — 최우선 Critical) 주말(토·일)·공휴일·평일 개장 전(`00:00~08:59 KST`)에 네이버 JSONP 및 `ls_realtime_bridge.py`가 조회 시점 날짜를 그대로 `tradeDate`로 부여하여 가짜 당일 봉 복제·EMA 왜곡·`전일비 100.00%` 오표시가 발생하는 결함
* **현상 및 실측 재현 근거 ([`STRATEGY.md` `11.2.1`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L1390) & [`11.2.2`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L1401) 위반)**:
  1. 실제 네이버 실시간 폴링 API(`polling.finance.naver.com/api/realtime`)와 LS `t1102`는 **토요일·일요일·평일 공휴일·평일 아침 `00:00~08:30 KST`(장전 리셋 전)** 에 `open = 0, volume = 0`을 주는 것이 아니라, **직전 개장일(예: 금요일 `2026-11-13`)의 확정 시가(`ov=26150`)·고가(`hv=28650`)·저가(`lv=26050`)·종가(`nv=28300`)·누적거래량(`aq=512323`)·전일종가(`pcv=26050`) 및 `ms="CLOSE"`** 를 그대로 유지하면서 `result.time`만 **현재 서버 시각(예: 일요일 `2026-11-15`, 월요일 `08:20 KST`)** 으로 내려줍니다.
  2. 현재 [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1688) `parseNaverRealtime`은 `res.time`을 무조건 `kstDate(Number(res.time))`으로 변환하고, [`isPreOpenEmptyQuote`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1608-L1614)는 `open === 0 && volume === 0`만 검사하므로 이를 신규 거래일 시세로 통과시킵니다. 또한 [`scripts/ls_realtime_bridge.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/scripts/ls_realtime_bridge.py#L75-L80) 역시 주말·심야·장전 구분 없이 `tradeDate`를 벽시계 오늘 날짜로, `marketState`를 `"OPEN"`으로 하드코딩하고 있습니다.
  3. **오작동 실측 결과** (예: 일요일 `2026-11-15 15:00 KST` 또는 월요일 `2026-11-16 08:20 KST` 접속 시):
     * `mergeLiveQuoteIntoCandles`가 금요일 봉을 복제한 **가짜 일요일/장전 캔들(`trade_date: "2026-11-15"`, `change_rate: 0%`, `_live: true`)** 을 우측 끝에 추가하여 `EMA 5`가 `26,700 → 27,233`으로 왜곡되고 `watchlist.html` 100점 평가 점수가 변질됩니다.
     * `computeQuoteMetrics`에서 `prevBar`가 금요일(`2026-11-13`, `volume = 512,323`)로 잡혀 `512,323 / 512,323 * 100`이 계산되면서 **전 종목 헤더에 `전일비 100.00%` 및 `당일시세 2026-11-15(일요일)`가 오표시**됩니다.
* **구체적 코드 수정 제안**:
  1. **[`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1608-L1782)**:
     * **1단계 (시각 기반 비개장 시간대 날짜 보정)**: KST 기준 토요일(`dow === 6`)·일요일(`dow === 0`), 또는 평일 `09:00 KST` 이전(`hm < 9 * 60`)이면서 `marketState !== "OPEN"`인 응답은 아직 당일 정규장이 열리지 않은 직전 거래일 종가 스냅샷이므로, `parseNaverRealtime`에서 `res.time` 기반 날짜를 **직전 평일(토 `-1일`, 일 `-2일`, 월 `09시 전` `-3일`, 화~금 `09시 전` `-1일`)** 로 롤백하십시오. *(참고: 기존 단위 테스트 `test_naver_parse_and_jsonp_cleanup`의 픽스처 시각은 `Date.UTC(2026,10,16,1,0,0)` = 월요일 `10:00 KST`이므로 `"2026-11-16"` 단언이 100% 그대로 통과합니다!)*
     * **2단계 (캔들 대조 기반 평일 공휴일·장전 중복 스냅샷 완벽 차단 — 공휴일 달력 불필요!)**: `normalizeQuoteForCandles(q, cList)` 헬퍼를 두어 `lastBar = cList[cList.length - 1]`, `prevBar = cList.length > 1 ? cList[cList.length - 2] : null`이 존재하고 `q.tradeDate > lastBar.trade_date`일 때:
       * `q.tradeDate`의 요일이 토/일(`0` 또는 `6`)이거나,
       * `q.marketState !== "OPEN"` 이면서 **(a) `prevBar && num(prevBar.close) !== num(lastBar.close) && num(q.prevClose) > 0 && num(q.prevClose) === num(prevBar.close)`** (진짜 신규 거래일이면 `q.prevClose`는 반드시 `lastBar.close`여야 함! `prevBar.close`와 같다면 100% 직전 거래일 스냅샷) 또는 **(b) `num(q.price) === num(lastBar.close) && num(q.open) === num(lastBar.open) && num(q.high) === num(lastBar.high) && num(q.low) === num(lastBar.low) && Math.round(num(q.volume)) === Math.round(num(lastBar.volume))`** 인 경우,
       * 이는 평일 공휴일(성탄절·명절 등) 또는 장전 미갱신 스냅샷이므로 `q = Object.assign({}, q, { tradeDate: lastBar.trade_date })`로 보정하십시오(`computeQuoteMetrics`, `mergeLiveQuoteIntoCandles`, `getQuote` 모두 동일 적용). 그러면 공휴일·주말·장전 언제 접속하더라도 가짜 봉이 절대 생기지 않고 직전 확정 거래일 전일비가 정확히 표시됩니다!
  2. **[`scripts/ls_realtime_bridge.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/scripts/ls_realtime_bridge.py#L73-L82) 및 [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1739)**:
     * `fetch_t1102`에서 KST 시각(`kst = time.gmtime(time.time() + 9 * 3600)`)을 기준으로 평일 `09:00 ~ 15:35 KST`(또는 동시호가/시간외 포함 `08:50 ~ 18:00 KST`)일 때만 `"marketState": "OPEN"`, 그 외 야간·주말·장전에는 `"CLOSE"`를 반환하고, 토·일 및 평일 `09:00 KST` 이전에는 `tradeDate`를 직전 평일 날짜로 산출하십시오.
     * `common.js` `fetchBridge`(`line 1739`)에서 `bridgeOk = !!(h && h.ok && h.configured !== false)`로 판정하여 환경변수 미설정 브릿지 기동 시 불필요한 `/quote` 빈 호출 없이 즉시 Tier 2로 폴백하도록 보완하십시오.

#### 2. `[ISSUE-022]` (`AC-46 · AC-47` — High) `holdings.html` 동일 종목 `HOLDING → CLOSED` 전환 시 `setData` `liveQuote: null` 무시에 따른 과거 청산 차트 실시간 봉 오염 및 PNG/클립보드 저장 시 실시간 봉 누락
* **현상 및 실측 근거**:
  1. **[`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1526) `mountProChartPanel.setData`**:
     * 현재 `st.liveQuote = d.liveQuote || (prevCode === d.shcode ? st.liveQuote : null);`로 작성되어 있어, 호출 측([`holdings.html` `line 273`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/holdings.html#L273))이 과거 청산 이력(`CLOSED`) 행 선택 시 명시적으로 `liveQuote: null`을 넘겨도 `d.liveQuote`가 falsy이고 `prevCode === d.shcode`(동일 종목 재매수·과거 청산 이력 조회 시나리오)이면 이전 `HOLDING`의 `st.liveQuote`가 그대로 남습니다.
     * Headless Chromium E2E 실측 결과, 보유 중인 `SNT다이내믹스(003570)` 조회 후 과거 `2026-10-20` 청산된 `SNT다이내믹스(003570)` 행을 클릭하면 `panelT = "2026-10-30"`인 과거 차트 우측 끝에 `2026-11-16 (30,350원)` 실시간 봉이 달라붙어 과거 매매 복기 차트가 오염됩니다. 또한 `holdings.html`에서 `CLOSED` 행 선택 시 백그라운드 `LiveQuoteManager` 폴링이 중지되지 않고 계속 도는 점도 함께 정리해야 합니다.
  2. **PNG 이미지 저장 / 클립보드 복사 시 실시간 봉 미반영 ([`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1479-L1484))**:
     * `downloadChartPng(snapshot())` 및 `copyChartToClipboard(snapshot())` 호출 시 `snapshot()`의 `candles`가 `viewCandles()`가 아닌 원본 `st.candles`여서, 화면 차트에는 당일 실시간 봉과 현재가 태그가 보이는데 저장된 PNG 이미지에는 실시간 봉이 빠진 전일 기준 차트가 저장됩니다.
  3. **단일 일봉(`cList.length === 1`, 신규 상장주 등) 초기 등락률 폴백 ([`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1631))**:
     * `computeQuoteMetrics`에서 `quote` 미수신(`!useQ`)이고 `cList`가 1봉뿐(`prevClose === 0`)일 때 `last.change_rate`가 존재함에도 `0.00%`로 덮어써집니다.
* **구체적 코드 수정 제안**:
  1. **[`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1526)**: `st.liveQuote = (d.liveQuote !== undefined) ? d.liveQuote : (prevCode === d.shcode ? st.liveQuote : null);` 로 변경하여 명시적 `liveQuote: null` 전달 시 즉시 해제되게 하십시오. 또한 [`holdings.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/holdings.html#L224) `selectRow`에서 `if (h.status !== "CLOSED") startLive(h); else { C.LiveQuoteManager.stop(); LIVE = { code: "", quote: null }; }` 를 추가하십시오.
  2. **[`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1479-L1484)**: `act === "png"` 및 `act === "copy"`에서는 `Object.assign({}, snapshot(), { candles: viewCandles() })`를 전달하여 저장/복사되는 이미지에도 화면과 동일한 실시간 당일 봉·현재가 태그가 포함되도록 하십시오 *(단, `openBig()`은 이중 병합 방지를 위해 기존처럼 `snapshot()` 원본 `candles` + `liveQuote`를 그대로 전달)*.
  3. **[`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1631)**: `const changeRate = prevClose > 0 ? round2((price / prevClose - 1) * 100) : (!useQ && last ? round2(num(last.change_rate)) : 0);` 로 보완하십시오.

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
