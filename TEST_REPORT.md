# 🧪 LS 수급·차트 스크리너 검증 및 테스트 리포트 (`TEST_REPORT.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[검증 및 테스트]` 전담 대화창**에서 테스트 실행 결과, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md) 대조 검수, 데이터 정합성 검증 리포트, 발견된 버그 및 구체적인 코드 수정 제안을 기록하는 문서입니다.
> * **`[프로그램 개발 및 수정(메인)]` 대화창**은 작업 시작 전 본 `TEST_REPORT.md`와 `STRATEGY.md`를 확인하여 미해결 버그(`2.1절 신규 수정 요청 사항`)를 코드에 반영하고, 수정이 완료된 항목의 상태를 **`[해결 완료]`**로 업데이트합니다.

---

## 1. 최신 검수 요약 (`v2.5` 커밋 `3f3f3f2` 정밀 검수 완료 — `AC-34`, `AC-35`(`AC-1~AC-29`) PASS / `AC-30 ~ AC-33` 보완 필요 4건 발견)

* **검수 일시**: `2026-11-15 21:02 KST` (`2026-11-15 12:02 UTC`)
* **대상 커밋**: `3f3f3f2` — `feat(v2.5): 패턴·캔들·지표 100점 종합판단 및 프로 차트 PNG 저장 (AC-30~AC-35)` ([`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L847-L1054) `8절` 구현)
* **단위·통합 테스트 스위트 및 회귀 검증 실행 결과**:
  * `python3 test_screener_verification.py`: **8 / 8 통과 (`OK`)**
  * `python3 -m unittest discover -s tests -v`: **68 / 68 통과 (`OK`, `3.423s` — `test_v25_pattern_chart.py` `11개` + `test_v24_watchlist_holdings.py` `29개` + `test_v23_acceptance.py` `19개` + `test_v2_acceptance.py` `9개`)**
  * `python3 run_daily_screener.py --mode verify`: **전 항목 정상 통과 (`Exit 0`, `1,463` 유니버스 · 차트 `1,233일` · 수급 `739일` · 신규 3개 테이블 `0/0/0` 무손상)**
* **운영 Supabase 실데이터(`T = 2026-11-13`, `271.8만 행`) + Python 독립 수식 대조 + Node VM 3페이지 E2E 정밀 검수 결과**:
  * ✅ **합격 항목 (`AC-34`, `AC-35`, 기존 `AC-1 ~ AC-29` 전 항목)**:
    * **핵심 수식·회귀 무결성**: `computeIndicators`(`Wilder RSI 14`, `Wilder ATR 14%`, `BB(20,2)` 모표준편차 및 `60봉 백분위`, `VolMA20`)가 독립 Python 레퍼런스 수식과 실데이터 200봉 전 구간에서 **최대 오차 `0.00e+00` (`< 1e-9`)** 으로 일치하며, `findConfirmedPivots`의 미래 봉 변조 불변성(`Zero Look-ahead`), 4종 반전 캔들(`망치형·상승장악형·관통형·도지양봉전환`), `idx < 45` 단기 시계열 오탐 `0건`, `index.html` `125일` 후보 프리로드(`121종목` 로드 → 전 종목 200일 전수 조회 대비 **분류 오차 `0건`**), 4축 `100점 종합판단` 배점 합산(`35+30+20+15=100`) 및 대바닥 출신(`🌱 쌍바닥돌파` 포함) 이탈 오판 `0건`(`READY 1 · WAIT 38 · WATCH 10 · EXIT 0`), `[🔍 크게 보기]` 대화면 모달·더블클릭 오픈, `[📸 이미지 저장]`(`2200×1368px` 고해상도 헤더 합성 PNG 및 클립보드 복사, 텔레그램 이미지 코드 미추가)이 정상 동작합니다.
  * 🚨 **필수 수정 요청 항목 (`4건`: `[ISSUE-015]` ~ `[ISSUE-018]`)**:
    1. **`[ISSUE-015]` (`HIGH` — `index.html` 프로 차트 기본 `120일/60일` 뷰에서 하단 순수기관 수급 막대 `73%` 누락 | `AC-33`)**: [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L1230-L1255) `ensureStockFullChart()`가 종목 선택 시 `daily_chart`(`limit=240`)만 보강 조회하고 **`daily_investor_supply`는 초기 `45달력일(32영업일)` 상태 그대로 방치**하여, 기본 `120일` 차트 좌측 **`88봉(73.3%)`** 및 `60일` 차트 좌측 **`28봉(46.7%)`** 구간의 순수기관 막대가 완전히 비어 있고 호버 시 `"순수기관 수급 없음"`으로 표시됩니다.
    2. **`[ISSUE-016]` (`HIGH` — `index.html` 행 배지 서브태그 이중 중복 표시 & 비추천 `[하락채널저항]` 22종목 전량 누락 | `AC-31`)**: [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L907-L916) `buildRowBadges()`가 `🟢🌱 쌍바닥돌파` 옆에 `🌱 쌍바닥돌파`를 또 찍어 **`당일10%` 추천 49종목 중 15종목(`30.6%`)에서 동일 배지가 2회 중복 출력**되며, 비추천 분기에서 `rec.subReason`을 누락해 `common.js`가 감지한 **`[하락채널저항]` 22종목(`22/22`, `100%`)이 화면 배지에서 전량 누락**됩니다.
    3. **`[ISSUE-017]` (`MEDIUM` — `holdings.html` 클로저 캐시 오염 · 동일 종목(`A안`) `240일/720일` 전환 시 미갱신 · 프로 차트 상단 패널 Y축 하단 침범 | `AC-33`)**: ① [`holdings.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/holdings.html#L188) `onDataLoaded`가 최초 선택 행의 `const h`를 클로저로 영구 캡처하여 보유/청산 캐시가 교차 오염되고, ② [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1405-L1413) `setData()`가 `d.shcode !== st.shcode`만 검사해 동일 종목(`005930`)의 과거 `CLOSED` 행(`240일` 조회 후)에서 현재 `HOLDING` 행 클릭 시 `fetchLong()`이 스킵되어 `80봉`에 고착되며, ③ [`drawProChart()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1118-L1158) 상단 플롯 영역에 `ctx.clip()`이 없어 `EMA 120/240` 및 외삽 추세선이 하단 `[기관·거래량]`/`[RSI 14]` 패널 내부(`y = 205~227px`)를 침범해 그려집니다.
    4. **`[ISSUE-018]` (`LOW/MEDIUM` — `detectChartPatterns` `flag(깃발·박스돌파)` 당일 양봉(`C > O`) 조건 누락 & `watchlist.html` `종합판단` 컬럼 클릭 정렬 미구현 | `AC-30`, `AC-32`)**: ① [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L819) `flag` 판정식에 명세(`8.1절 4-2항`: **양봉 돌파**)의 `C > O` 조건이 빠져 갭상승 후 밀린 음봉(`C < O`)에서도 `flag = true`(`+14점`·`🚀` 배지)로 오탐되며, ② [`watchlist.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/watchlist.html#L42) `<th data-sort="score" style="cursor:pointer">종합판단</th>`에 클릭 정렬 핸들러가 없습니다.

---

### 1.1 `v2.5` 신규 합격 기준 (`STRATEGY.md` 8.6절 — `AC-30` ~ `AC-35`) 상세 검수 결과표

| 검증 코드 | 검증 항목 (`STRATEGY.md` 8.6절) | 코드 감사 · 운영 Supabase(`2026-11-13`) · Node VM 실증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-30** | **무미래참조(`Zero Look-ahead`) 피봇·기하학 패턴 5종 · 반전 캔들 4종 · 보조지표 수식 정합성 검증** | • `computeIndicators`(`RSI 14`, `ATR 14%`, `BB(20,2) & 60봉 백분위`, `VolMA20`) 실데이터 4종목(`005930`, `039490`, `448900`, `003570`) 200봉 Python 독립 수식 대조 **최대 오차 `0.00e+00`**<br/>• `findConfirmedPivots` 미래 봉(`endIdx+1..N`) 극단 변조 시 과거 피봇 `100%` 불변, 4대 반전 캔들(`HAMMER·ENGULFING·PIERCING·DOJI_TURN`) 및 음봉 배제 정확, `idx < 45` 단기 시계열 전 패턴 `false` 확인<br/>• ⚠️ **보완 필요 (`[ISSUE-018-①]`)**: `detectChartPatterns`의 `flag`(`819행`)에 당일 양봉(`C > O`) 조건이 누락되어 시가 갭상승 음봉(`Open > Close > maxPullClose`)에서도 `flag = true`로 오탐됨 | **FAIL** (`ISSUE-018`) |
| **AC-31** | **`index.html` 패턴 승격(`쌍바닥·역H&S`) · 4대 진입성향 서브태그 · `125일` 일봉 프리로드 보강 검증** | • `EMA 60` 하회 구간에서도 기관 수급(`>=12%` 또는 `2일 연속 5%+`) 동반 `🌱 쌍바닥돌파` / `🌱 역H&S전환` 추천 승격 정상 작동 (`2026-11-13` `당일10%` 추천 `47 → 49종목` 확장)<br/>• 4대 서브태그(`⚡ 급등기준봉·눌림대기 6`, `🚀 VCP·수렴돌파 1`, `📐 깃발·박스돌파 1`, `🕯️ 이평지지반전 2`) 분류 및 `125일` 일봉 프리로드(`121종목` 로드 → 전수 200일 대비 **분류 오차 `0건`**) 확인<br/>• ❌ **보완 필요 (`[ISSUE-016]`)**: `buildRowBadges()`에서 서브태그 보유 `15종목`의 배지가 **`🟢🌱 쌍바닥돌파 🌱 쌍바닥돌파` 형태로 이중 출력**되고, 비추천 `[하락채널저항]` 감지 **`22종목` 전원(`100%`)의 화면 배지가 누락**됨 | **FAIL** (`ISSUE-016`) |
| **AC-32** | **`watchlist.html` 4축 `100점 종합 판단` 수식 · 4단계 신호등 · 우측 스코어 브리핑 검증** | • `수급(35) + 구조(30) + 트리거(20) + 지표(15) = 100점` 산출식, 4단계 등급(`🔥 타점완성 80+` / `⏳ 눌림대기 60~79` / `👀 관망유지 40~59` / `⚠️ 정리권고 <40·이탈`), 대바닥 트랙(`🌱 쌍바닥돌파`·`🌱 역H&S전환` 포함) 20/60일선 이탈 면제(`EXIT 0건`) 정확 작동<br/>• `[🔥 타점완성]` 빠른 필터, 우측 4축 프로그레스바·3줄 코멘트·`추천 진입 대기선` 원클릭 적용 및 초기 `185달력일` 시계열 로드 정상 확인<br/>• ⚠️ **보완 필요 (`[ISSUE-018-②]`)**: 테이블 헤더 `<th data-sort="score" style="cursor:pointer">종합판단</th>` 클릭 시 정렬 핸들러 미구현(클릭 무반응) 및 `onDataLoaded` 후 스코어카드 재렌더링 누락 | **FAIL** (`ISSUE-018`) |
| **AC-33** | **3페이지 통합 2단 프로 차트(`drawProChart`) · 패턴 자동 작도 · 기간 전환(`60~720일`) 연동 검증** | • 3페이지 모두 `mountProChartPanel` 탑재, `[240일/720일]` 클릭 시 단건 `limit=750` 일봉+수급 병렬 조회, 레이어 체크박스(`패턴작도·BB스퀴즈·가격선·하단 기관/RSI/숨김`), 마우스 크로스헤어 일별 브리핑 정상 작동<br/>• ❌ **보완 필요 (`[ISSUE-015]`, `[ISSUE-017]`)**: ① `index.html` 기본 `120일`/`60일` 차트에서 `ensureStockFullChart`가 일봉(`240봉`)만 받고 수급(`32봉`)을 받지 않아 **좌측 `88봉(73.3%)` 순수기관 막대가 공백**으로 비어 있음, ② `holdings.html` `onDataLoaded` 첫 행 `h` 클로저 오염 및 `setData` 동일 `shcode` 다른 기준일(`T`) 전환 시 `fetchedLong` 미초기화 버그, ③ `drawProChart` 상단 플롯 클리핑 부재로 `EMA 120/240`이 하단 서브패널을 침범 | **FAIL** (`ISSUE-015`, `ISSUE-017`) |
| **AC-34** | **`[🔍 크게 보기]` 대화면 차트 모달 및 `[📸 PNG 차트 이미지 저장]` 검증** | • `[🔍 크게 보기]` 버튼 및 캔버스 더블클릭 시 `max-w-6xl`(`height: 560`) 대화면 모달 오픈, 기간·레이어 상태 동기화 정상<br/>• `[📸 이미지 저장]` 클릭 시 `2200×1368px`(`dpr=2`) 오프스크린 캔버스에 종목명·코드·기준일·현재가·판단/패턴 배지 상단 헤더 합성 후 `{기준일}_{종목명}_{상태}.png` 다운로드 및 `[📋 클립보드 복사]` 작동 확인; `run_daily_screener.py` 내 텔레그램 사진 전송 코드 미추가(`0건`) 확인 | **PASS** |
| **AC-35** | **전 버전 통합 회귀 무결성 검증 (`AC-1 ~ AC-29` 전수 PASS)** | • `test_screener_verification.py` (`8/8`), `tests/test_v2_acceptance.py` (`9/9`), `tests/test_v23_acceptance.py` (`19/19`), `tests/test_v24_watchlist_holdings.py` (`29/29`), `tests/test_v25_pattern_chart.py` (`11/11`) 총 **`76 / 76` 테스트 100% 통과**, `--mode verify` `Exit 0` | **PASS** |

---

### 1.2 `2026-11-13` 운영 DB 실데이터 기준 `v2.5` 5개 모드별 추천 세부 태그 & 비추천 사유 실측표

| 스크리닝 모드 / 옵션 | 전체 (`tabAll`) | `🟢 추천 후보` (`tabRec`) | `v2.5` 추천 세부 `displayTag` 분해 | `⚪ 비추천 보류` (`tabHold`) | `[하락채널저항]` 감지 건수 (`subReason`) |
| :--- | :---: | :---: | :--- | :---: | :---: |
| **`기관 수급 · 당일 10% 이상`** | **123종목** | **49종목** *(+2)* | `추세수급(일반) 20` · `🌱 바닥지지 연속수급 11` · `⚡ 급등기준봉·눌림대기 6` · `🌱 쌍바닥돌파 5` · `🔄 바닥전환 첫수급 3` · `🕯️ 이평지지반전 2` · `🚀 VCP·수렴돌파 1` · `📐 깃발·박스돌파 1` | **74종목** | **22종목** *(화면 배지 미표시 → `ISSUE-016`)* |
| **`기관 수급 · 당일 15% 이상`** | **81종목** | **31종목** *(+1)* | `추세수급(일반) 13` · `🌱 바닥지지 연속수급 8` · `⚡ 급등기준봉·눌림대기 4` · `🌱 쌍바닥돌파 2` · `🔄 바닥전환 첫수급 1` · `🕯️ 이평지지반전 1` · `🚀 VCP·수렴돌파 1` · `📐 깃발·박스돌파 1` | **50종목** | **15종목** |
| **`기관 수급 · 당일 20% 이상`** | **47종목** | **21종목** *(+1)* | `추세수급(일반) 8` · `🌱 바닥지지 연속수급 8` · `⚡ 급등기준봉·눌림대기 2` · `🌱 쌍바닥돌파 2` · `🕯️ 이평지지반전 1` | **26종목** | **10종목** |
| **`기관 수급 · 3일 연속 5% 이상`** | **43종목** | **23종목** | `추세수급(일반) 8` · `🌱 바닥지지 연속수급 8` · `⚡ 급등기준봉·눌림대기 4` · `🌱 쌍바닥돌파 1` · `🕯️ 이평지지반전 1` · `🚀 VCP·수렴돌파 1` | **20종목** | **5종목** |
| **`하락 추세 전환 수급 발생`** | **4종목** | **4종목** | `🔄 바닥전환 첫수급 4` (`448900, 000320, 437730, 098460`) | **0종목** | **0종목** |

---

### 1.3 기존 요구사항 (`AC-1` ~ `AC-29`) 회귀 검증 요약 (`v2.5` 적용 후 전 항목 PASS 유지)

| 검증 코드 | 검증 항목 요약 | `v2.5` (`3f3f3f2`) 적용 후 회귀 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-1 ~ AC-18** | 유니버스(`1,463종목`), EMA·순수기관 수식, 4중 배치 Cron, 멱등성 가드, 유동성 제외 필터, 9열 엑셀 | `test_screener_verification.py`(8/8), `test_v2_acceptance.py`(9/9), `--mode verify` 전 항목 오차 `0건` | **PASS** |
| **AC-19 ~ AC-23** | 차트 5년(`1,678,171행`) · 수급 3년(`1,040,512행`) 비대칭 적재, 앵커 EMA, 무지연 PK 조회 | `test_v23_acceptance.py`(19/19), 7종목 `1,233일 / 739일` 범위 및 웹 초기 로드 무결성 유지 | **PASS** |
| **AC-24 ~ AC-29** | 3페이지 분리, 추천/비추천 기본 계약, 영구제외 즉시 반영, 스마트 병합, 보유/청산(`A안`), 텔레그램 폴백 | `test_v24_watchlist_holdings.py`(29/29) 전 항목 무수정 통과, 운영 DB 3개 테이블 초기 클린 상태(`0/0/0`) 유지 | **PASS** |

---

## 2. 버그 및 수정 요청 트래커 (Issue & Fix Tracker)

### 🚨 2.1 `[프로그램 개발 및 수정]` 대화창 신규 수정 요청 사항 (`미해결 4건: ISSUE-015 ~ ISSUE-018`)

---

#### 🔴 `[ISSUE-015]` `[신규 — HIGH]` `index.html` 종목 선택 시 프로 차트 기본 `120일 / 60일` 뷰에서 하단 순수기관 수급 막대 `73%` 누락 공백 (`ensureStockFullChart` 수급 미조회)
* **관련 합격 기준**: `AC-33`, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L1022) `8.4절 2항` (1022행)
* **대상 파일**: [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L1230-L1281)
* **원인 및 실데이터 재현**:
  * `STRATEGY.md` 1022행은 **`"index.html 및 holdings.html의 CLOSED 히스토리 행에서도 차트 조회·확대 시 daily_investor_supply가 함께 보강 로드되어야 하단 순수기관 수급 막대가 빈칸 없이 그려집니다"`** 라고 명시하고 있습니다.
  * 현재 `index.html` 초기 로드는 `daily_investor_supply`를 `45달력일(32영업일, 2026-09-29 ~ 2026-11-13)`만 적재하며, 종목 클릭 시 호출되는 [`ensureStockFullChart(stock)`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L1230-L1255)는 **`daily_chart`(`limit=240`)만 추가 조회하고 `daily_investor_supply`는 조회하지 않습니다**.
  * 또한 `PRO_PANEL`의 기본 표시 기간은 `period: 120`이어서 `mountProChartPanel`의 `fetchLong()`(`period >= 240` 전용)이 실행되지 않습니다.
  * 그 결과 `2026-11-13` 실데이터에서 첫 종목(`138930 BNK금융지주` 등 전 종목) 선택 시 `candlesLen = 240`(`2025-11-20~`)인 데 반해 **`suppliesLen = 32`(`2026-09-29~`)에 그쳐**, 기본 `120일` 차트 좌측 **`88개 봉(73.3%)`** 및 `60일` 차트 좌측 **`28개 봉(46.7%)`** 구간에 순수기관 막대가 전혀 그려지지 않고 마우스 호버 브리핑에도 `"순수기관 수급 없음"`이 출력됩니다.
* **구체적 코드 수정 제안 (`index.html` `ensureStockFullChart`)**:
  * `ensureStockFullChart(stock)`에서 `daily_chart`(`limit=240`)와 **`daily_investor_supply`(`limit=240`, `trade_date <= TOP_TRADE_DATE`, `SUPPLY_SELECT_COLS`)** 를 `Promise.all`로 병렬 조회한 뒤, 확정 수급 가드(`r.trade_date < TOP_TRADE_DATE || isSettledSupplyRow(r)`)를 거쳐 `RAW_SUPPLIES_BY_CODE[stock.shcode]`에도 `mergeSortedByTradeDate`로 병합하고 `selectedShcode === stock.shcode`일 때 `drawCandlestickAndEmaChart(stock)`를 호출해 주십시오 (`PRO_CACHE[stock.shcode]`가 이미 `750봉`으로 채워진 경우는 덮어쓰지 않도록 유지).

---

#### 🔴 `[ISSUE-016]` `[신규 — HIGH]` `index.html` `buildRowBadges()` 서브태그 배지 이중 중복 렌더링(`15종목`) 및 비추천 `[하락채널저항]`(`subReason`) 배지 전량 누락(`22종목`)
* **관련 합격 기준**: `AC-31`, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L936-L937) `8.2절 1항` (936~937행)
* **대상 파일**: [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L907-L919), [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L1277-L1278)
* **원인 및 실데이터 재현**:
  1. **추천 배지 이중 중복**: [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L903-L919) `classifyRecommendation()`은 `subTag`가 존재할 때 `displayTag`에도 동일한 `subTag`(예: `"🌱 쌍바닥돌파"`, `"⚡ 급등기준봉·눌림대기"`)를 설정합니다. 그런데 [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L911-L912) `buildRowBadges()`는 `🟢${rec.displayTag || rec.tag}` 배지를 그린 직후 `if (rec.subTag)`로 또 동일한 `rec.subTag` 배지를 추가하여, `2026-11-13` `당일 10%` 추천 49종목 중 **15종목(`BNK금융지주`, `더블유게임즈` 등 `30.6%`)에서 `🟢🌱 쌍바닥돌파` `🌱 쌍바닥돌파` 처럼 동일 문구가 두 번 연속 출력**됩니다.
  2. **비추천 `[하락채널저항]` 배지 전량 누락**: `STRATEGY.md` 936행은 **`"pat.downChannel === true 이면 subReason: '[하락채널저항]' 을 추가하여 화면 배지에 ⚪[60일선이탈][하락채널저항] 형태로 함께 안내합니다"`** 라고 규정하나, `index.html` 914행은 `rec.reasons.join("")`만 렌더링하고 `rec.subReason`을 연결하지 않아 `2026-11-13` `당일 10%`에서 감지된 **`22종목` 전원(`22/22`)의 `[하락채널저항]` 배지가 누락**됩니다.
* **구체적 코드 수정 제안 (`index.html` `buildRowBadges` & `drawProForStock`)**:
  ```javascript
  if (rec && rec.recommended) {
    const label = rec.displayTag || rec.tag;
    const cls = /급등/.test(label)
      ? "bg-amber-500/15 text-amber-300"
      : (rec.subTag && rec.tag === "추세수급" ? "bg-sky-500/15 text-sky-300" : "bg-emerald-500/15 text-emerald-400");
    html += ` <span class="px-1 rounded text-[10px] ${cls}">🟢${escapeHtml(label)}</span>`;
  } else if (rec && rec.reasons && rec.reasons.length) {
    html += ` <span class="px-1 rounded text-[10px] bg-slate-500/20 text-slate-300">⚪${escapeHtml(rec.reasons.join("") + (rec.subReason || ""))}</span>`;
  }
  ```
  * 아울러 `drawProForStock`의 `badges`(1277행)도 비추천 종목일 때 `["⚪" + rec.reasons.join("") + (rec.subReason || "")]`를 전달하면 PNG 저장 헤더에 `"감지된 패턴 없음"` 대신 정확한 비추천 사유가 표시됩니다.

---

#### 🟠 `[ISSUE-017]` `[신규 — MEDIUM]` `holdings.html` `onDataLoaded` 클로저 캐시 오염 · `mountProChartPanel.setData` 동일 종목(`A안`) 기준일 전환 시 `240일/720일` 미갱신 · `drawProChart` 상단 차트 Y축 하단 패널 침범
* **관련 합격 기준**: `AC-33`, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L1007-L1023) `8.4절 1항·2항`
* **대상 파일**: [`holdings.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/holdings.html#L185-L190), [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1079-L1158), [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1404-L1414)
* **원인 및 재현**:
  1. **`holdings.html` 188행 첫 행 `h` 클로저 고착 버그**: `if (!PANEL)` 내부의 `onDataLoaded: (c, cs, ss) => { if (h.status !== "CLOSED") { CHARTS[c] = cs; SUPPLIES[c] = ss; } }`에서 `h`가 **페이지 진입 후 가장 먼저 선택된 행의 `h`로 영구 고정**됩니다. 첫 행이 `HOLDING`일 때 나중에 동일 종목의 과거 `CLOSED` 행(`endDate = sell_date + 10일`)에서 `[240일]`을 누르면 과거 시점 절단 시계열이 현재 보유중 `CHARTS[c]`/`SUPPLIES[c]`를 오염시키며, 첫 행이 `CLOSED`이면 이후 `HOLDING` 행의 장기 데이터가 캐시되지 않습니다.
  2. **`common.js` 1405·1410행 동일 `shcode` 다른 `T` 전환 시 `fetchedLong` 미초기화**: `setData(d)`가 `const changed = d.shcode !== st.shcode;`만 비교합니다. `holdings.html`에서 `005930`의 과거 `CLOSED` 행(`T = 2025-06-20`)을 `[240일]`로 조회(`st.fetchedLong = true`)한 뒤 `005930`의 현재 `HOLDING` 행(또는 두 번째 `CLOSED` 행, `T = 2026-11-13`, 초기 `80봉`)을 클릭하면 `changed === false`여서 `fetchLong()`이 실행되지 않고 **`240일` 차트가 `80봉`에 영구 고착**됩니다.
  3. **`drawProChart` 상단 플롯 영역 클리핑 부재로 인한 하단 서브패널 침범**: `lo/hi` 스케일 산정(1081행)에 `ema_120`/`ema_240`이 포함되지 않은 상태에서 상단 플롯(`[Lm, Tm, cssW - Lm - Rm, topH]`)에 `ctx.clip()`이 없어, `2026-11-13` 실데이터 `131290`(`maxY = 227`), `032830`(`maxY = 205`), `137310`(`minY = -3`) 등에서 **`EMA 120`·`EMA 240` 및 외삽 추세선이 상단 밖이나 하단 `[기관·거래량]`/`[RSI 14]` 서브패널(`lowTop = 205px~`) 내부를 가로질러 그려집니다**. 또한 추세선 `t.x1 < start`일 때 `xOf(Math.max(start, t.x1))`에 원래 `yOf(t.y1)`을 그대로 써서 기울기가 왜곡됩니다.
* **구체적 코드 수정 제안**:
  1. `holdings.html` 188행: `onDataLoaded: (c, cs, ss) => { const cur = byId(SELECTED); if (cur && cur.status === "CLOSED") { CLOSED_CHARTS[cur.id] = cs; CLOSED_SUPPLIES[cur.id] = ss; } else { CHARTS[c] = cs; SUPPLIES[c] = ss; } }` 로 변경하십시오.
  2. `common.js` `setData(d)`(1405~1413행): `const changed = d.shcode !== st.shcode || String(d.T || "") !== String(st.T || "");`로 변경하고, `if (!d.keepFetched && (changed || (st.period >= 240 && st.candles.length < Math.min(st.period, 200)))) st.fetchedLong = false;`를 적용하십시오.
  3. `common.js` `drawProChart`(1096~1158행): 상단 플롯 시리즈(BB 구름대·캔들·5개 EMA·패턴 추세선/아크/피봇) 그리기 전 `ctx.save(); ctx.beginPath(); ctx.rect(Lm, Tm, cssW - Lm - Rm, topH); ctx.clip();`을 걸고 `ctx.restore();`로 해제하며, 추세선 `t.x1 < start && t.x2 > t.x1`일 때 `start`에서의 선형 보간 `yStart = t.y1 + (t.y2 - t.y1) * (start - t.x1) / (t.x2 - t.x1)`(`t.x2 < start`면 스킵)로 그리도록 보정하십시오.

---

#### 🟡 `[ISSUE-018]` `[신규 — LOW/MEDIUM]` `common.js` `detectChartPatterns` `flag(깃발·박스돌파)` 당일 양봉(`C > O`) 조건 누락 및 `watchlist.html` `종합판단` 컬럼 클릭 정렬 미연결
* **관련 합격 기준**: `AC-30`, `AC-32`, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L903) `8.1절 4-2항` (903행) & `8.3절 2항` (996행)
* **대상 파일**: [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L819), [`watchlist.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/watchlist.html#L42) (`render`, `onDataLoaded`, `click` 핸들러)
* **원인 및 수정 제안**:
  1. **`flag` 당일 양봉 조건(`C > O`) 추가 (`common.js` 819행)**: 명세 903행은 **"당일 종가가 조정 구간 최고 종가를 양봉 돌파"** 로 정의하나 현재 `Lpull >= e20 * 0.98 && retr <= 0.50 && C > maxPullClose && pc >= 0.58 && V >= 1.15 * vm`에 `C > O`가 빠져 있어, 시가 갭상승 후 밀린 음봉(`Open > Close > maxPullClose`, `pc >= 0.58`)에서도 `res.flag = true`가 되어 관심종목 구조 점수 `+14점` 및 프로 차트 `🚀` 배지가 오탐됩니다. 조건에 `&& C > O`를 추가해 주십시오.
  2. **`watchlist.html` `종합판단` 헤더 클릭 정렬 연결 (`watchlist.html` 42·137·201·338행)**: `<th data-sort="score" style="cursor:pointer"><span>종합판단</span></th>`에 클릭 핸들러가 없어 클릭해도 반응하지 않습니다. `let SORT_MODE = "grade";` 변수를 두고 `[data-sort="score"]` 클릭 시 `"score"`(등급 무관 순수 `totalScore` 내림차순) ↔ `"grade"`(기본 등급 우선 + `totalScore` 내림차순) 토글을 지원하며, 201행 `onDataLoaded` 말미에 `if (x && SELECTED === c) renderScoreCard(x, EVAL[c]); render();`를 추가해 주십시오.

---

### ✅ 2.2 해결 완료된 이슈 히스토리 아카이브

* **[ISSUE-011 ~ ISSUE-014] `[해결 완료 (v2.4.1, 16f575d + 운영 DB RLS 해제/GRANT 반영)]`** 운영 Supabase 신규 3개 테이블 실서버 CRUD 정상화 및 `42501` 배너, 대바닥 출신 관심종목 이평 이탈 오판 제거, 제외관리 모달 복구·프리셋 체크박스 즉시 반영, 보유종목 현재가 목표가 배지 및 `CLOSED` 온디맨드 차트 로드(`AC-24 ~ AC-29`) 전 항목 합격.
* **[v2.3.1 검증 완료 (`353f92a`, `Run #43682739754` & `Run #43685346608`)]** 차트 5년(`2021-11-01~`, `1,678,171행`) · 수급 3년(`2023-11-01~`, `1,040,512행`) 비대칭 확장 백필 1회차 `2시간 44분` 100% 완주, 앵커 시드 EMA 연속성, 거래정지 `25종목` 미확정 오판 차단, `80분` 주기 토큰 자동 갱신 및 `271.8만 행` 대용량 DB 무지연(`AC-19 ~ AC-23`) 전 항목 합격.
* **[v2.2 검증 완료 (`6bfbbd5`)]** `[기관 수급 발생 종목]` 유동성·수급금액 제외 필터(`당일 기준` vs `3일 연속 3일 평균 기준`) 및 `[엑셀 저장]` 9개 컬럼 개편(`AC-16 ~ AC-18`) 전 항목 합격.
* **[v2.1 검증 완료 (`1aecd41`)]** `20:30 KST` 다중 백업 Cron, `KST` 표준시 고정, `--skip-if-completed` 멱등성 가드(`< 2.3초` 종료), `if: failure()` 장애 알림, Apps Script 외부 정각 웹훅(`AC-13 ~ AC-15`) 및 `두산에너빌리티(034020)` 백필 자동 복구 확인 완료.
* **[ISSUE-006 ~ ISSUE-010] `[해결 완료 (v1.4.3 ~ v2.0)]`** `PRIORITY_SHCODES` 제거, `has_2yr_history` 판정 분리, 장중 미확정 수급 차단, 복합 PK 병렬 조회 전환(`HTTP 500` 해소), `AC-1 ~ AC-12` 검증 체계 구축 완료.
* **[ISSUE-001 ~ ISSUE-005] `[해결 완료 (v1.4)]`** 1,463종목 시총 ≥ 700억 전수 유니버스 구축, 일봉·수급 500영업일 역순 슬라이딩 적재, Actions 360분 타임아웃 상향 완료.
