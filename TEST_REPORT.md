# 🧪 LS 수급·차트 스크리너 검증 및 테스트 리포트 (`TEST_REPORT.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[검증 및 테스트]` 전담 대화창**에서 테스트 실행 결과, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md) 대조 검수, 데이터 정합성 검증 리포트, 발견된 버그 및 구체적인 코드 수정 제안을 기록하는 문서입니다.
> * **`[프로그램 개발 및 수정(메인)]` 대화창**은 작업 시작 전 본 `TEST_REPORT.md`와 `STRATEGY.md`를 확인하여 미해결 버그(`2.1절 신규 수정 요청 사항`)를 코드에 반영하고, 수정이 완료된 항목의 상태를 **`[해결 완료]`**로 업데이트합니다.

---

## 1. 최신 검수 요약 (`v2.1` 커밋 `1aecd41` & `v2.2` 커밋 `6bfbbd5` 검수 완료 — `AC-1` ~ `AC-18` 전 항목 PASS)

* **검수 일시**: `2026-11-13 03:05 KST` (`2026-11-12 10:05 PST`)
* **대상 커밋**:
  * `6bfbbd5` — `Feat(v2.2): Add inst_supply liquidity/amount filters and overhaul Excel export to 9 columns` (`STRATEGY.md` `2.2절`·`3.3절`·`5절` 반영, 전략 커밋 `05e78c4`)
  * `1aecd41` — `Feat(v2.1): Stabilize 20:30 KST batch with multi-cron, KST idempotency guard, failure alert, and Apps Script webhook` (`STRATEGY.md` `4절` 반영, 전략 커밋 `28d8ce8`)
* **단위·수용 회귀 테스트 실행 결과**:
  * `python3 test_screener_verification.py`: **8 / 8 통과 (`OK`, `0.010s` — `v2.1` 멱등성·부분 이어받기 및 `v2.2` 유동성 필터·EMA 추세 문자열 테스트 포함)**
  * `python3 -m unittest discover -s tests -v`: **9 / 9 통과 (`OK`, `0.258s` — [`tests/test_v2_acceptance.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/tests/test_v2_acceptance.py) 내 `AC-7 ~ AC-18` 및 경계값 `99.99 vs 100.0` / `29,999 vs 30,000` / `499.99 vs 500.0` JS↔Python 1:1 패리티 테스트 추가)**
* **운영 Supabase 대용량 DB(약 73만 행, `2026-11-12` 야간 배치 완주 상태) 실데이터 검증 (`python3 run_daily_screener.py --mode verify`)**: **전 항목 정상 통과 (`Exit 0`, `HTTP 500` 타임아웃 `0건`)**
  * 직전 야간 배치(`run 43228952190`, `success`) 완주로 **`daily_chart` `723,986행`**, **`daily_investor_supply` `733,683행`** 적재 확인 (`stocks_master` 유니버스 **`1,463종목`**, 20일 거래대금 20억 미만 중소형주 **`920종목`**, 직전 미적재였던 `두산에너빌리티(034020)`까지 차트 `500일` / 수급 `500일` 자동 복구 완료 실증).
  * 운영 73만 행 DB 대상 `--mode daily --skip-if-completed` 실측 결과 **`1.69 ~ 2.24초` (`< 5.0초`) 내 즉시 정상 종료(`Exit 0`)** 및 중복 API 수집·중복 텔레그램 발송 **`0건`** 실증 (`완주율 99.66% >= 98.5%`, 확정 `1,458 / 1,463종목`, 거래정지 `25종목`).
* **`index.html` 동적 Node VM 라이브 실행 & 백엔드 & 독립 클린룸 파이썬 3자 교차 검증 (`기준일 T = 2026-11-12`)**:
  * 콘솔 에러/경고 **`0건`**, 상단 배지 **`기준일: 2026-11-12`** 정상 표시, 5개 전체 조건에서 **포착 종목 코드·정렬 순서·`이동평균 추세 현황` 문자열 모두 100% 일치 (오차 `0건`)**:
    * `기관 수급 발생 종목 · 당일 10% 이상`: **87종목** 일치 *(제외 필터 전 `131종목` → 소액·저유동성 `44종목` 정제)*
    * `기관 수급 발생 종목 · 당일 15% 이상`: **48종목** 일치 *(제외 필터 전 `80종목` → `32종목` 정제)*
    * `기관 수급 발생 종목 · 당일 20% 이상`: **29종목** 일치 *(제외 필터 전 `51종목` → `22종목` 정제)*
    * `기관 수급 발생 종목 · 3일 연속 5% 이상`: **47종목** 일치 *(제외 필터 전 `64종목` → 3일 평균 미달 `17종목` 정제, `대한유화 006650`·`아이마켓코리아 122900` 정상 포함)*
    * `하락 추세 전환 수급 발생`: **2종목 (`한라캐스트 125490`, `엘오티베큠 083310`)** 일치

---

### 1.1 `v2.2` 신규·개편 요구사항 (`STRATEGY.md` 2.2절·3.3절·5절 — `AC-16` ~ `AC-18` 및 갱신 `AC-9`, `AC-11`) 상세 검수 결과표

| 검증 코드 | 검증 항목 (`STRATEGY.md` 5.4절) | 코드 및 `2026-11-12` 운영 DB(73만 행) 실증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-16** *(겸 `AC-9` 갱신)* | **`[기관 수급 발생 종목]` 유동성·수급금액 제외 필터 정합성 검증** | • [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L325-L327) `CHART_SELECT_COLS` 및 [`run_daily_screener.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L2044-L2049) `verify_supabase_data()` 모두 `trading_value_m` 컬럼 조회 및 `trading_value_m <= 0` 시 `(close * volume) / 1,000,000` 폴백(`resolveTradingValueM` / `_resolve_trading_value_m`) 구현 확인<br/>• **당일 10%/15%/20% 제외 실증 (`2026-11-12`)**:<br/>  - `푸른저축은행(007330)`: 당일 비중 `59.32%`이나 수급금액 `0.26억(<1억)`·거래량 `4,398주(<3만주)`·거래대금 `0.44억(<5억)` → **100% 제외**<br/>  - `세방전지(004490)`: 당일 비중 `46.10%`·수급금액 `6.56억`이나 당일 거래량 `26,360주(<3만주)` → **100% 제외**<br/>  - `대한유화(006650)`: 당일 비중 `21.92%`·수급금액 `4.90억`이나 당일 거래량 `24,611주(<3만주)` → 당일 단일일 옵션에서 **정상 제외**<br/>• **`3일 연속 5% 이상` 3일 평균 기준 실증 (`2026-11-12`)**:<br/>  - `대한유화(006650)`: 최근 3일 비중 `[61.27%, 61.90%, 21.92%] >= 5%`, 3일 평균 수급금액 `24.91억(>=1억)`·3일 평균 거래량 `48,455주(>=3만주)`·3일 평균 거래대금 `45.28억(>=5억)` 충족 → **정상 포함** (`아이마켓코리아 122900` 역시 당일 수급 `0.80억`이나 3일 평균 `2.46억`·`248,031주`·`20.73억`으로 정상 포함)<br/>  - 반면 `미원화학(134380)`(3일 평균 `0.09억`/`2,731주`/`0.32억`), `영원무역홀딩스(009970)`(3일 평균 거래량 `10,066주 < 3만주`) 등 17종목은 정확히 제외됨 (`cList[-3:]`↔`sList[-3:]` 날짜 불일치 종목 `0건` 확인)<br/>• **`[하락 추세 전환 수급 발생]` 필터 미적용 및 수식 실증**: 유동성 제외 필터 미적용 유지 확인(단위 테스트 저유동성 종목 `900099` 통과 및 실데이터 `한라캐스트 125490`[유형 A, `P=11/11`, 낙폭 `-35.22%`, 당일 `+15.03%`], `엘오티베큠 083310`[유형 B, `P=11/11`, 낙폭 `-31.57%`, 시가 `9,500원 < 종가 9,560원` 양봉 & `EMA5 9,104.80원` 상회, 당일 `+11.44%`] **2종목 정확 포착**)<br/>• 5개 전 조건에서 `index.html` === `run_daily_screener.py` === 독립 클린룸 파이썬 **오차 `0건`** | **PASS** |
| **AC-17** *(겸 `AC-11` 갱신)* | **`[엑셀 저장]` 9개 컬럼 순서·부호 제거·숫자/문자열 타입 검증** | • [`exportScreenedToExcel()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L851-L919)를 운영 DB 5개 전 모드에 대해 실제 호출하여 생성된 5개 `.xlsx` 파일(`2026-11-12_기관수급발생_당일10%이상.xlsx` 외 4종, 총 `213행 × 9열 = 1,917셀`) 전수 검사 완료 (**불량 셀 `0건`**)<br/>• 헤더가 정확히 **`종목코드, 종목명, 현재가, 등락폭, 등락률, 수급 비중, 수급 금액, 연속 일수, 이동평균 추세 현황`** 9개 열이며 기존 `등락폭/율` 및 개별 `Ema5~Ema240` 열 완전 삭제 확인<br/>• 셀 타입 및 부호/단위 제거 확인:<br/>  - `종목코드`(`t:"s"`, 6자리 `0` 보존), `종목명`(`t:"s"`), `현재가`(`t:"n"`, 순수 숫자)<br/>  - `등락폭`(`t:"n"`, 예: `-1150`, `1550`, `0`), `수급 금액`(`t:"n"`, `z:"0.0"`, 예: `36.5`, `97.3`, `"억"` 및 `+` 없음), `연속 일수`(`t:"n"`, `수급 금액` 우측 인접 8열, 예: `2`, `3`, `"일"` 및 `+` 없음)<br/>  - `등락률`(`t:"s"`, 예: `"-2.59%"`, `"3.12%"`, `"0.00%"`), `수급 비중`(`t:"s"`, 예: `"53.6%"`, `"43.2%"`) — 양수 `+` 기호 `0건`, `-0` / `"-0.00%"` / `"-0.0%"` / `NaN` **`0건`** | **PASS** |
| **AC-18** | **`[이동평균 추세 현황]` 내림차순 문자열 생성 정확성 검증** | • [`formatEmaTrendStatus()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L828-L844) 및 [`format_ema_trend_status()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1830-L1840) 모두 기준일(`T`)의 5개 EMA(`5, 20, 60, 120, 240`)를 수치 내림차순(동률 시 `span` 오름차순: `Ema5 → Ema20 → Ema60 → Ema120 → Ema240`)으로 정렬하여 `" > "`로 결합함을 검증<br/>• `2026-11-12` 전 모드 포착 종목(`213행`) 전수 대조 결과 독립 파이썬 산출값과 **오차 `0건`** 일치 (예: `하나머티리얼즈 166090` → `"Ema120 > Ema240 > Ema60 > Ema20 > Ema5"`, `한올바이오파마 009420` → `"Ema120 > Ema240 > Ema5 > Ema60 > Ema20"`), 9번째 열 너비 `{ wch: 42 } >= 40` 확인 | **PASS** |

---

### 1.2 `v2.1` 야간 배치 실행 안정화 요구사항 (`STRATEGY.md` 4절 — `AC-13` ~ `AC-15`) 상세 검수 결과표

| 검증 코드 | 검증 항목 (`STRATEGY.md` 4.6절) | 코드·인프라 및 운영 DB 실증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-13** | **`20:30 KST` 다중 백업 Cron · `concurrency` · 실패 경보 워크플로우 검증** | • [`.github/workflows/daily_batch.yml`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/.github/workflows/daily_batch.yml#L4-L36) 원격 푸시 성공 및 GitHub Actions 원격 상태 **`state: active`** 확인 (`gh api .../actions/workflows` 검증 완료)<br/>• 주 스케줄 `30 11 * * 1-5`(`20:30 KST`) + 1차 백업 `47 11 * * 1-5`(`20:47 KST`) + 2차 백업 `17 12 * * 1-5`(`21:17 KST`) 3중 Cron, `concurrency: { group: daily-ls-stock-batch, cancel-in-progress: false }`, `timeout-minutes: 360` 정확히 등록됨<br/>• `if: failure()` 조건의 `배치 실패 시 텔레그램 장애 알림 발송` 스텝(82~126행)이 KST 실패 시각, 이벤트명, 모드, Actions Run URL을 텔레그램으로 즉시 발송하도록 구현됨<br/>• 외부 정각 웹훅 스크립트 [`scripts/trigger_daily_batch.gs`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/scripts/trigger_daily_batch.gs) (`skip_if_completed: "true"`, 주말 자동 스킵, `installDaily2030Trigger`) 및 [`README.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/README.md) 3분 설정 가이드 정합성 확인 완료 | **PASS** |
| **AC-14** | **KST 표준시 고정 · `--skip-if-completed` 멱등성 가드 · 부분 이어받기 검증** | • [`get_kst_now()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L62-L71) / [`get_kst_today()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L69-L71)로 `dt.date.today()` 의존성을 완전히 제거하여 UTC 서버에서도 `KST(UTC+9)` 기준일을 일관 산출함<br/>• [`fetch_latest_krx_trading_date()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L345-L370)로 대표주(`005930`) `t8410` 최신 개장일을 사전 확인하여 평일 공휴일에도 직전 개장일 완주 상태를 감지(`1.65초` 내 즉시 스킵)함<br/>• **실데이터 `--skip-if-completed` 성능 실증**: `2026-11-12` 적재 완료(`99.66% >= 98.5%`, 대표 3종 완비)된 73만 행 운영 DB 대상 `run_standalone_batch(mode="daily", skip_if_completed=True)` 실행 시 **`2.24초` (`LS_APP_KEY` 미설정 경로는 `1.69초`, 기준 `< 5.0초`) 내 정상 종료(`Exit 0`)**, LS TR 수집 호출 **`0건`**, 중복 텔레그램 발송 **`0건`** 확인<br/>• 부분 적재 이어받기 시 기적재 종목 `[DAILY-SKIP]` 처리 및 [`build_daily_screening_lists_from_db()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L920-L1049)를 통한 전 종목 DB 기준 텔레그램 리포트 누락 방지 검증 완료 | **PASS** |
| **AC-15** | **`index.html` 분산 표본 기준일 탐색 및 배치 진행 중 상태 배지 검증** | • [`fetchLatestSettledTradeDate()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L397-L426)가 상·중·하위 분산 대표 10종목(`005930,000660,005380,012450,196170,006650,023160,218410,166090,009420`, `limit=30`)을 PK 인덱스로 초고속 조회하여 상위 대형주 미갱신 상태에서도 최신 확정일 `T`를 정확히 감지함<br/>• [`formatTradeDateBadgeText()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L440-L451)가 적재율 `< 95%` 시 `기준일: YYYY-MM-DD (일일 배치 동기화 진행 중: N/M종목)`을 표시하고, 완주 상태(`2026-11-12` 현재 `1,433~1,458 / 1,463 = 97.9~99.7% >= 95%`)에서 **`기준일: 2026-11-12`**로 깔끔하게 표기함을 목업 및 실데이터 양쪽에서 검증 완료 (`AC-7 ~ AC-12` 회귀 오류 `0건`) | **PASS** |

---

### 1.3 기존 요구사항 (`AC-1` ~ `AC-12`) 회귀 검증 요약 (`2026-11-12` 완주 기준 전 항목 PASS)

| 검증 코드 | 검증 항목 요약 | `2026-11-12` 운영 DB 및 동적 실행 재검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-1 ~ AC-2** | 시총 ≥ 700억 보통주 전수 유니버스 & 20억 미만 차단 해제 | `stocks_master` 유니버스 **1,463종목** (제외종목 `0건`, 20억 미만 중소형주 **920종목** 정상 포함, 5대 대형주 및 `두산에너빌리티 034020` 모두 차트 `500일` / 수급 `500일` 완비) | **PASS** |
| **AC-3 ~ AC-5** | 2년치(500영업일) 차트·수급 적재, EMA·순수기관 수식 & 레퍼런스 실증 | `daily_chart` **723,986행**, `daily_investor_supply` **733,683행**, EMA 5종·순수기관 합산 오차 `0건`, `태광(023160)` `2026-08-25`(`+12.85%`) & `대한유화(006650)` `2026-11-03`(`+31.57%`) 즉시 조회 | **PASS** |
| **AC-6 ~ AC-8** | 대시보드 전 종목 무절단 동기화, 슬림 헤더 & 컨트롤 바 연동 | 73만 행 DB PK 병렬 로드 완료(콘솔 에러/경고 `0건`), 타이틀·2종 배지·2개 모드 드롭다운 및 하위 4개 옵션 토글 정상 동작 | **PASS** |
| **AC-10 & AC-12** | 7열 1줄 컴팩트 테이블, 당일 기준 정렬 & 우측 상세·장중 `T+1` 차단 | 7열(`종목명~연속일수`) `whitespace-nowrap` 렌더링, 당일 `instRatioT` 내림차순 정렬, 우측 캔들/EMA 차트·주체별 수급 상세 및 `trade_date <= T` 장중 데이터 차단 정상 유지 | **PASS** |

---

## 2. 버그 및 수정 요청 트래커 (Issue & Fix Tracker)

### 🚨 2.1 `[프로그램 개발 및 수정]` 대화창 필수 수정 요청 사항 (현재 미해결 0건)

* **현재 미해결 버그 및 필수 수정 요청 사항이 없습니다 (`AC-1 ~ AC-18` 전 항목 합격).**

> **💡 참고용 비차단(Non-blocking) 운영 개선 메모 (향후 `[전략 개발]` 판단 사항 — 현재 스펙 결함 아님)**:
> * 현재 웹 대시보드(`index.html`)와 백엔드 전략 평가(`evaluate_strategy_v2_stock`, `--mode verify`)는 `v2.2` 명세(`5.1절`, `5.3절`)에 따라 `1억 / 3만주 / 5억` 유동성·수급금액 제외 필터가 오차 `0건`(`87종목`)으로 반영되어 있습니다. 반면 야간 배치 완료 시 발송되는 텔레그램 요약 알림(`run_standalone_batch` 내 `screened_1d` / `screened_3d` 및 `build_daily_screening_lists_from_db`, `4.2절 4항`)은 기존 `v1.0` 기준(유동성 커트라인 없는 단순 `inst_vol_ratio >= 10%`, `131종목`)을 유지하고 있어 텔레그램 상위 15선에 `푸른저축은행(007330)` 등 소액·저유동성 종목이 노출될 수 있습니다. 향후 텔레그램 알림도 웹 대시보드(`v2.2`)와 동일하게 정제하고자 할 경우 `[전략 개발]` 창에서 정책 확정 후 반영하면 됩니다.
> * 사소한 문구 참고: [`.github/workflows/daily_batch.yml`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/.github/workflows/daily_batch.yml#L73)의 검증 스텝 표시 이름이 `AC-1~AC-15 데이터 정합성 검증 리포트`로 되어 있으나 실제 실행되는 `run_daily_screener.py --mode verify`는 `AC-1 ~ AC-18` 전체를 정상 검증합니다.

---

### ✅ 2.2 해결 완료된 이슈 히스토리 아카이브

* **[v2.2 검증 완료 (`6bfbbd5`)]** `[기관 수급 발생 종목]` 유동성·수급금액 제외 필터(`당일 기준` vs `3일 연속 3일 평균 기준`) 및 `[엑셀 저장]` 9개 컬럼 개편(`AC-16 ~ AC-18`) 전 항목 합격.
* **[v2.1 검증 완료 (`1aecd41`)]** `20:30 KST` 다중 백업 Cron, `KST` 표준시 고정, `--skip-if-completed` 멱등성 가드(`< 2.3초` 종료), `if: failure()` 장애 알림, Apps Script 외부 정각 웹훅(`AC-13 ~ AC-15`) 및 `두산에너빌리티(034020)` 500일 백필 자동 복구 확인 완료.
* **[ISSUE-006 ~ ISSUE-010] `[해결 완료 (v1.4.3 ~ v2.0)]`** `PRIORITY_SHCODES` 제거, `has_2yr_history` 판정 분리, 장중 미확정 수급 차단, 복합 PK 병렬 조회 전환(`HTTP 500` 해소), `AC-1 ~ AC-12` 검증 체계 구축 완료.
* **[ISSUE-001 ~ ISSUE-005] `[해결 완료 (v1.4)]`** 1,463종목 시총 ≥ 700억 전수 유니버스 구축, 일봉·수급 500영업일 역순 슬라이딩 적재, Actions 360분 타임아웃 상향 완료.
