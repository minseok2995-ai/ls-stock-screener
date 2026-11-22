# 🧪 LS 수급·차트 스크리너 검증 및 테스트 리포트 (`TEST_REPORT.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[검증 및 테스트]` 전담 대화창**에서 테스트 실행 결과, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md) 대조 검수, 데이터 정합성 검증 리포트, 발견된 버그 및 구체적인 코드 수정 제안을 기록하는 문서입니다.
> * **`[프로그램 개발 및 수정(메인)]` 대화창**은 작업 시작 전 본 `TEST_REPORT.md`와 `STRATEGY.md`를 확인하여 미해결 버그(`2.1절 신규 수정 요청 사항`)를 코드에 반영하고, 수정이 완료된 항목의 상태를 **`[해결 완료]`**로 업데이트합니다.

---

## 1. 최신 검수 요약 (`v3.0.1` 핫픽스 커밋 `bf117fd` 최종 검수 — **`ISSUE-023 ~ 028` 6건 전부 해결 확인, `AC-63` FAIL → PASS 전환, `AC-61 ~ AC-66` 및 `AC-1 ~ AC-60` 전 항목 합격**)

* **검수 일시**: `2026-11-23 00:57 KST` (`2026-11-22 15:57 UTC`) — 첫 v3.0 운영 배치(`2026-11-23(월) 16:05 KST`) **이전 검수 완료**
* **대상 커밋**: `bf117fd` — `fix(v3.0.1): resolve ISSUE-023~028 snapshot column freeze, stale DSA cleanup, 750-bar window parity, PGRST204 body check & 0.1% mcap boundary` (5개 파일 `+1,027 / −124`: `run_daily_screener.py` · `common.js` · `index.html` · `STRATEGY.md 16.2절 3항` 문구 1곳 · 신규 [`tests/test_v301_fixes.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/tests/test_v301_fixes.py))
* **범위 준수**: `TEST_REPORT.md`·`watchlist.html`·`holdings.html`·SQL 스키마/마이그레이션·기존 테스트 파일 **무변경**, `STRATEGY.md`는 지시서 허용 범위(16.2절 3항 "300영업일 → 750영업일(약 1,150달력일)") 1줄만 수정.
* **단위·통합 테스트 스위트 실행 결과 (`총 157 / 157 통과 — ALL PASS`)**:
  * `python3 test_screener_verification.py`: **8 / 8 통과 (`OK`)**
  * `python3 -m unittest discover -s tests`: **149 / 149 통과 (`OK`)** — 신규 `test_v301_fixes.py` `9개`(ISSUE-023 2 · 024 1 · 025 2 · 026 1 · 027 2 · 028 1) + 기존 `140개` 전부 유지(삭제·완화 `0건`)
  * `python3 run_daily_screener.py --mode verify`: **Exit 0** (운영 DB `관심 46 · 보유 1 · 제외 0` 보존)
* **독립 심층 검증 (운영 Supabase `1,466종목` 100% 읽기 전용 — 모든 비-GET 요청·Upsert 가로채기, 검증 후 운영 DB 무변경 재확인: `stocks_master` 추세값 `0건`, `daily_supply_analysis` `783행`, `005930` 시세 컬럼 원본 유지)**:
  * ✅ **ISSUE-023 (HIGH) 해결**: [`STOCKS_MASTER_TREND_UPSERT_COLS`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L5097-L5106)가 `shcode·hname·market + trend_* 5개`로 축소되고, 오케스트레이터가 [`existing_masters=None`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L3044)을 넘겨 파이프라인이 배치 종료 후 `stocks_master`를 **재조회**(호출 `1회` 확인). 실DB 드라이런 prelim/final 각 `1,466행` 스냅샷 payload에 `shares·market_cap_eok·avg_vol_20d·avg_val_20d_eok·is_universe·last_close` 키 **`0건`**, `hname/market` 공란 `0건`(NOT NULL 안전). `005930`에 **일부러 배치 시작 시점의 오래된 master**를 넣은 최악 시나리오에서도 배치 갱신값 6개 컬럼 **전부 보존**, 추세 라벨만 기록.
  * ✅ **ISSUE-024 (MED) 해결**: Upsert 성공 직후 [`cleanup_stale_same_day_dsa_rows`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L4637-L4659)가 `trade_date=eq.{T}&shcode=not.in.(이번 결과 종목)` DELETE 1회 수행(URL `1,553자`, 대상 집합 = `ranked_rows` 정확 일치), 예외는 경고 로그로 격리. 기존 재현 시나리오(prelim `206` → final `205`, `000080` 탈락) 재실행 결과 **DB 잔존 `205행` = final `205종목`, 잔존 행 `0`, `daily_rank` 중복 `0`**(1..N 연속). `ranked_rows == []`이면 DELETE `0회`(빈 결과로 하루치가 통째로 삭제되는 사고 방지).
  * ✅ **ISSUE-025 (MED) 해결**: 배치(`DSA_CHART_WARMUP_BARS = 750`)·리스트(`index.html` 종목당 `limit=750`)·`C.TrendCycle.classifyLatest`·차트 모달/호버(`limit=750` + [`classifyWindowedSeries`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L2182-L2191))가 모두 **"`T` 이하 최근 750봉"**으로 통일. 실DB `350종목`(750봉 초과 `323종목`) 대조: Python 배치 ↔ JS 리스트 / `classifyLatest` / 차트 모달 최종봉 불일치 **`0`**, 750봉 ↔ 전체 이력 최종봉 불일치 **`0`**, 호버 최근 60봉 `20,947봉` 불일치 **`0`**(v3.0: `10.7%`). 1,000행 잘림 방지: 운영 조회 경로 [`_fetch_chart_window_for_codes`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L5153-L5197)로 후보 `200종목`을 받아 캐시 전체 이력의 마지막 750봉과 날짜열 **완전 일치**, 3종목 청크 `offset` 페이지네이션 경로도 단일 종목 경로와 일치. [`syncRecommendationAfterLoad`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L1487-L1497)는 더 이상 `applyScreening()`으로 재분류하지 않아 차트 `240일/720일` 클릭 시 **탭/선택 종목이 바뀌지 않음**. DSA 행 라벨 ↔ `stocks_master` 스냅샷 라벨 `206/206` 일치.
  * ✅ **ISSUE-026 (MED-LOW) 해결**: [`_is_v30_stage_signal`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L4015-L4023) 판별 후 v3.0 단계 라벨 행은 기존 3트랙 직접 집계에서 제외(차트 기반 재계산에 위임). `A-1/A-3/B-2/C-1` 라벨 4행 + 구형 `단기혼조` 1행 입력 시 `단기혼합` 표본 **`1`**(구형만), 점수 수식 무변경.
  * ✅ **ISSUE-027 (LOW) 해결**: [`_extract_http_error_text`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L4585-L4603)가 `HTTPError` 본문을 읽어 판정. 로컬 HTTP 서버 실측: `400 PGRST204` → trend 컬럼 POST `1회` + **기본 컬럼 폴백 POST `1회` 성공**, 기타 `400`(23502) → 재시도 없이 즉시 raise(폴백 없음), `500` → 기존대로 `3회` 재시도 후 raise.
  * ✅ **ISSUE-028 (LOW) 해결**: Python [L3670](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L3670) · [common.js L2209](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L2209) · [index.html L463](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L463) 동일하게 `amt >= mcap * 0.001 - 1e-9`. `700억/0.7억`·`2,900억/2.9억`·`300억/0.3억`·`100억/0.1억` 통과, `0.6999억`·`2.8999억`·`거래대금 4.99억`·`0`·음수 탈락 — **10개 경계 3중 구현 전부 일치**. 운영 후보 `206종목` 명세 수식 재계산 불일치 `0건`.
  * ℹ️ **성능 (지시서 목표 `≤ 90초` 충족)**: 실DB 드라이런 prelim Step 1 **`60.9초`**(스냅샷 `43.3초`, `daily_chart` GET `1,497회`) · final 전체 `62.2초`. v3.0(`24.6초`) 대비 약 `+36초`이며 일일 배치 30분 예산 내. `index.html` 후보 워밍업은 `67요청/61,081행/5.2초` → `200요청/143,589행/9.0초`(VM 측정, 1회 로드 시).

---

### 1.1 `v3.0` 요구사항 (`AC-61` ~ `AC-66`) 재검수 결과표 (`v3.0.1` 적용 후)

| 검증 코드 | 검증 항목 (`STRATEGY.md` 16.5절) | `v3.0.1` 재검수 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-61** | **16단계·63세부현황 엔진 결정론 및 Python·JS 100% 일치** | • 엔진 본체 무변경(v3.0 `3,251`계열 `1,258,306봉` 패리티 유지)<br>• 750봉 표준 윈도우로 배치·리스트·모달·호버 불일치 `0`, 전체 이력 대비 불일치 `0` (`ISSUE-025` 해결) | **PASS** |
| **AC-62** | **신규 자격 기준(`5억` & `3억`/`시총 0.1%`) 정확성** | • 10개 경계 3중 일치, 정확 경계 `0.1%` 통과 (`ISSUE-028` 해결), 운영 후보 재계산 불일치 `0건` | **PASS** |
| **AC-63** | **prelim+final DB 적재 · `stocks_master` 스냅샷 · `gemini-3.5-flash-lite` 기본값** | • 스냅샷이 추세 컬럼만 갱신, 시세/유동성 보존 (`ISSUE-023` 해결)<br>• final 후 동일 일자 행 = 최종 후보와 정확 일치, rank 중복 `0` (`ISSUE-024` 해결)<br>• PGRST204 폴백 실작동 (`ISSUE-027` 해결), 슬롯 게이트·기본 모델 유지 | **PASS** (FAIL → PASS) |
| **AC-64** | **`index.html` 3단 UI** | • 차트 재로딩 시 탭/선택 유지, 리스트 분류 750봉 통일 | **PASS** |
| **AC-65** | **차트 당일 배지 + 캔들 호버 시점별 추세** | • 호버 최근 60봉 라벨이 배치 기준과 `100%` 일치, 크게 보기 모달 로드 완료 시 배지 갱신 | **PASS** |
| **AC-66** | **마이그레이션 정합성 · 전체 회귀 100% PASS** | • 스키마 변경 없음, 전체 **`157 / 157`** PASS | **PASS** |

---

### 1.2 기존 요구사항 (`AC-1` ~ `AC-60`) 회귀 검증 요약 (`v3.0.1` 적용 후)

| 검증 코드 | 검증 항목 요약 | `v3.0.1` (`bf117fd`) 적용 후 회귀 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-1 ~ AC-18** | 유니버스, EMA·순수기관 수식, 배치 Cron, 멱등성 가드, 엑셀 | `test_screener_verification.py`(8/8), `test_v2_acceptance.py`(9/9), `--mode verify` Exit 0 | **PASS** |
| **AC-19 ~ AC-23** | 차트 5년·수급 3년 적재, 앵커 EMA, 무지연 PK 조회 | `test_v23_acceptance.py`(19/19) | **PASS** |
| **AC-24 ~ AC-29** | 3페이지 분리, 추천/비추천, 영구제외, 스마트 병합, 보유/청산 | `test_v24_watchlist_holdings.py`(29/29), `stocks_master` 시세 컬럼 동결 위험 해소(`ISSUE-023`), 운영 DB 무손상 | **PASS** |
| **AC-30 ~ AC-48** | 패턴·4축 평가, 프로 차트, 2회 배치, 실시간 시세 | `test_v25`(17/17) · `test_v26`(11/11) · `test_v27`(18/18) | **PASS** |
| **AC-49 ~ AC-56** | Keep-Alive, 프리페치, 정속 페이서 | `test_v28_batch_perf.py`(21/21); `supabase_upsert`가 영구 4xx(408/429 제외)는 즉시 raise, 5xx는 3회 재시도 유지 | **PASS** |
| **AC-57 ~ AC-60** | 일일 수급 분석·Gemini Top N·사후 복기 | `test_v29_daily_analysis.py`(10/10), 과거 승률 트랙 오염 해소(`ISSUE-026`) | **PASS** |

---

## 2. 버그 및 수정 요청 트래커 (Issue & Fix Tracker)

### 🚨 2.1 `[프로그램 개발 및 수정]` 대화창 신규 수정 요청 사항

> [!NOTE]
> **현재 미해결 수정 요청 사항 없음.** `ISSUE-023 ~ 028` 6건은 `bf117fd`에서 전부 해결되어 2.2절로 이관했습니다. 첫 v3.0 운영 배치(`2026-11-23(월) 16:05 KST` prelim) 진행에 차단 요소가 없습니다.
>
> **배치 후 확인 권장(선택)**: 첫 prelim/final 실행 로그의 `[DSA-Step1] … 잔존정리 N건 | 마스터 추세갱신 1466종목 | ~60초` 수치와, `stocks_master.last_close`·`updated_at`이 당일 값으로 갱신되었는지 1회 확인.

---

### ✅ 2.2 해결 완료된 이슈 히스토리 아카이브

* **[v3.0.1 검증 완료 (`bf117fd`)]** v3.0 검수 이슈 6건 전부 해결: `ISSUE-023`(HIGH, Step 1-B 스냅샷이 `stocks_master` 시세·유동성 컬럼을 배치 시작 값으로 되돌려 영구 동결 → 추세 컬럼만 Upsert + 배치 후 master 재조회), `ISSUE-024`(MED, prelim 잔존 행 → Upsert 직후 `trade_date=eq.&shcode=not.in.()` 정리, 빈 결과 시 삭제 금지), `ISSUE-025`(MED, 308봉 윈도우로 진영 반전 `2.1%`·차트 재분류로 선택 이동 → 배치·리스트·모달·호버 750봉 통일, 1,000행 잘림 방지 단일 종목/페이지네이션 조회, 불일치 `0`), `ISSUE-026`(MED-LOW, v3.0 라벨의 `단기혼합` 오염 → 직접 집계 제외), `ISSUE-027`(LOW, PGRST204 폴백 미작동 → `HTTPError` 본문 판정), `ISSUE-028`(LOW, `0.1%` 정확 경계 부동소수 오차 → `-1e-9` 허용오차 3중 통일). 실DB 읽기 전용 드라이런 prelim `60.9초`(목표 ≤90초), 전체 `157/157` 테스트 합격, `AC-63` FAIL → PASS.
* **[v3.0 검증 (`a444979`)]** 양극 추세 사이클(16단계·63세부현황) 엔진 Python↔common.js↔index 내장본 `3,251`계열 `1,258,306봉` 불일치 `0`, 63/63 코드 도달, 신규 자격 기준·슬롯 게이트·`gemini-3.5-flash-lite` 기본값·스키마/마이그레이션 동치 확인(`148/148` 테스트). 배치 데이터 무결성 결함 등 `ISSUE-023 ~ 028` 발견으로 `AC-63` FAIL 판정 → `v3.0.1`에서 해결.
* **[v2.9 검증 완료 (`d667654`)]** `daily_supply_analysis` 일일 수급 전수 정량 분석(Step 1: `100점` 4축 스코어 · 4대 자격 필터 · 과열 5일선 눌림가/종가~5일선 밴드 매수참고가 · `low` 손절가 · `+7%/+15%` 목표가 · 유사조건 과거 승률, 운영 `1,466종목` 중 `192후보` `8.55초` 처리) + Top 10 Gemini AI 압축 요약(Step 2: `40봉×13원소` `~5.3KB` 페이로드 · `GEMINI_MODEL`/`AI_TOP_N` 환경변수 · 3워커 병렬 · `429/503` 백오프 재시도 · 무중단 예외 격리) + 사후 복기 자동 백필(Step 3: `ret_5d/10d/20d`, `max/min_ret_10d`, `365일` 보관 정리, `DSA_UPSERT_COLUMNS` 분리 멱등성) 및 운영 Supabase 테이블/GitHub Secret 준비 완료 확인, 전체 `142/142` 테스트(`AC-57 ~ AC-60` 및 `AC-1 ~ AC-56` 회귀) 전 항목 합격.
* **[v2.8.2 검증 완료 (`011bdf3`, 실전 `Run #44075513243` `28분 58초` 완주)]** 실전 `Run #43893079642`(`47분 25초`, `1.96s/종목`)에서 규명된 LS 서버 `t8410` 초당 1건(`1.00s`) 제한 및 재시도 슬롯 미갱신 도미노 페널티 해결 전수 합격: ① `TR_SERVER_FLOOR_BY_CD = {"t8410": 1.04, "t1717": 0.54}` 정속 예약으로 실시간 2-스레드 Keep-Alive E2E에서 `1.040s/종목` 정속 주행 및 실전 배치 `28분 58초 < 30분` 완주 달성, ② `_on_rate_limit_wait`의 `_tr_learned_floor` 즉시 승격(`1.04 ~ 1.30`)·`_global_learned_gap` 보정·`_acquire_tr_slot` 재예약으로 도미노 재시도 `0회` 원천 차단, ③ `[PERF]` 완료 로그 텔레메트리 및 전체 `132/132` 테스트(`AC-56`) 전 항목 합격.
* **[v2.8.1 검증 완료 (`f2e1b68`)]** 실전 2차 배치(`Run #43859068236`, `57분 56초`)에서 확인된 3대 잔여 병목 핫픽스 전수 합격: ① `supabase_prefetch_daily_context(..., target_codes=pf_codes)` 50종목 복합 PK 인덱스 청크 병렬 조회(`HTTP 500` 타임아웃 원천 제거, 운영 실DB `1,466종목` + 미해결 `63종목` 병렬 사전 해결까지 총 `6.52초`, 메인 루프 내 단건 DB GET `0회`, 3인자 경로와 불일치 `0건`), ② `ANCHOR_RECENT_CALENDAR_DAYS = 105` · `ANCHOR_RECENT_COUNT = 60` 조정으로 LS `t8410` 비압축 `100건` 상한 하 단일 페이지 호출(`1회 × 0.38s/종목`, `1,466종목` 이론 `11.28분 < 15분`) 보장, ③ `pair_pool.shutdown(wait=True)` 및 `len(supply_to_upsert)` 로그 정합성 반영 (`AC-54 ~ AC-55` 및 전체 `129/129` 테스트 합격).
* **[v2.8 검증 완료 (`e4f2eca`)]** `KeepAliveHttpPool`(영구 HTTP/TLS 재사용·끊김 재연결·`chunked+gzip`·`HTTPError` 호환), `supabase_prefetch_daily_context`(운영 실DB `2.11초` 일괄 프리페치, 단건 조회 `96.6%` 제거, `T-5` 확정 앵커 일관 선택), `LSApiClient` 경과시간 차감 페이서·적응형 백오프·`t8410`‖`t1717` 2-스레드 병렬(`ANCHOR-MISMATCH` 전체 재적재 보존), `BatchUpsertBuffer` 50종목 원자적 묶음 Upsert(`chart → supply → master`, 개별 격리 복구, 증분 수급 슬림화 및 누락일 치유, `1,463종목` `~11.3~13.0분 < 15분`) 및 전체 `127/127` 테스트(`AC-49 ~ AC-53`) 전 항목 합격.
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
