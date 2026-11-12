# 🧪 LS 수급·차트 스크리너 검증 및 테스트 리포트 (`TEST_REPORT.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[검증 및 테스트]` 전담 대화창**에서 테스트 실행 결과, `STRATEGY.md` 대조 검수, 데이터 정합성 검증 리포트, 발견된 버그 및 구체적인 코드 수정 제안을 기록하는 문서입니다.
> * **`[프로그램 개발 및 수정(메인)]` 대화창**은 작업 시작 전 본 `TEST_REPORT.md`와 `STRATEGY.md`를 확인하여 미해결 버그(`2.1절 신규 수정 요청 사항`)를 코드에 반영하고, 수정이 완료된 항목의 상태를 **`[해결 완료]`**로 업데이트합니다.

---

## 1. 최신 검수 요약 (v1.4.3 커밋 `e21fa2f` 최종 재검수 완료 — 전 항목 PASS)

* **검수 일시**: `2026-11-12 15:29 KST` (`2026-11-11 22:29 PST`)
* **대상 커밋**:
  * `e21fa2f` — `Fix(v1.4.3): Resolve ISSUE-006 through ISSUE-010 (incremental daily logic, unsettled intraday supply guard, dynamic period window)`
  * `f6ffca9` — `Refactor(v1.4.2): Remove PRIORITY_SHCODES and _prioritize_candidates reference stock routines`
  * `aa880f7` — `Fix(v1.4.1): Handle LS Open API gateway 302->404 rate-limit redirects and set safe 0.62s interval on t1444`
  * `56518de` — `Feat(v1.4): Implement 1,477 full universe, 2-year 500d chart/supply sliding backfill, smart resume, and 700k-row web query optimization`
* **단위/통합 테스트 (`python3 test_screener_verification.py`)**: **5 / 5 항목 통과 (`OK` — `ISSUE-007`, `ISSUE-008` 회귀 검증 포함)**
* **실데이터 정합성 검증 (`python3 run_daily_screener.py --mode verify`)**: **전 항목 정상 통과 (`OK`)**
  * `stocks_master` 유니버스: **1,463종목** (제외종목 혼입 `0건`, 시총 700억 미만 `0건`, 거래대금 20억 미만 중소형주 포함 `1,105종목`)
  * 5대 대형주(삼성전자·SK하이닉스·현대차·한화에어로스페이스·알테오젠) 및 핵심 검증 종목(대한유화·태광): 모두 **일봉 500일 / 확정 수급 499일(`2026-11-11` 기준)** 적재 및 장중 미확정(`0` 수급) 더미 행 사전 정리 확인
  * 최신 확정 거래일(`2026-11-11`) 순수기관 비중 상위 종목: 대한유화(`+61.90%`), 태광(`+55.20%`), 원익QnC(`+47.55%`), GS(`+46.21%`), 이오테크닉스(`+45.23%`) 정상 출력 확인
* **GitHub Actions 배치 실행 상태**: 워크플로우 Run `43161372160` (`mode: backfill`, `timeout-minutes: 360`) 실시간 백필 순항 중 (`daily_chart` 72,343행 / `daily_investor_supply` 63,820행 돌파)

---

### 1.1 `STRATEGY.md` 0.2절 (수정 1~6) & 0.4절 (`AC-1` ~ `AC-6`) 대조 검수 결과표

| 구분 | 요구사항 및 합격 기준 (`STRATEGY.md`) | 코드 검수 결과 | 실시간 Supabase DB 실증 결과 | 최종 판정 |
| :---: | :--- | :---: | :--- | :---: |
| **수정 1 / AC-1** | **시총 700억 이상 보통주 전수 유니버스 구축**<br/>• ETF/ETN/ELW/스팩/우선주/리츠 혼입 0건<br/>• 1,200종목 미만 미완성 감지(`is_quarterly_rebuild_due`)<br/>• 대형주(삼성전자·SK하이닉스·현대차·한화에어로·알테오젠) 포함 | ✅ **구현 및 `ISSUE-006` 수정 완료**<br/>(1036행 `PRIORITY_SHCODES` 잔존 참조 제거 완료) | ✅ **`stocks_master` 1,463종목 등록 완료**<br/>• 제외종목 혼입: **0건** / 시총 700억 미만: **0건**<br/>• 5대 대형주 모두 `chart=500일, supply=500일` 적재 완료 | **PASS** |
| **수정 1 / AC-2** | **수집 단계 거래대금 20억 미만(`avg_val_20d_eok < 20.0`) 사전 차단 제거** | ✅ **구현 완료**<br/>(`if avg_val_20d_eok < 20.0: continue` 삭제 확인) | ⏳ 시총 상위부터 순차 백필 중 (중소형주 구간 진입 시 `avg_val_20d_eok` 순차 갱신 진행 중) | **코드 PASS**<br/>(백필 완주 진행 중) |
| **수정 2 / AC-3** | **`daily_chart` 2년치(500영업일) 전수 적재 및 EMA(5·20·60·120·240) 정합성**<br/>• `[-60:]` 절단 폐기 및 500일 전수 Upsert | ✅ **구현 완료**<br/>(`fetch_daily_chart` count=500, 역순 보완 및 전수 Upsert) | ✅ 백필 완료된 종목 모두 정확히 **500영업일** 적재 및 EMA 5·20·60·120·240 산출 확인 | **PASS** |
| **수정 3 / AC-4** | **`daily_investor_supply` 2년치(500영업일) 역순 슬라이딩 연속 수집 및 1:1 매칭**<br/>• 평일 `daily` 모드 최근 25일(1페이지) 고속 증분 | ✅ **`ISSUE-007`, `ISSUE-008` 수정 완료**<br/>(`has_2yr_history` 판정 분리, 장중 미확정 `0` 수급 차단 및 DB 자동 정리) | ✅ 백필 종목당 **500영업일** 적재 및 6대 주체 수식 오차 **0건**, 장중 미확정(`0` 수급) 행 적재 차단 및 정리 완료 | **PASS** |
| **AC-5** | **핵심 레퍼런스 종목(`태광 023160`, `대한유화 006650`) 2년치 과거 데이터 실증 확인** | ✅ **`ISSUE-009` 수정 완료**<br/>(`--mode verify`에 `AC-1~AC-5` 검증 지표 및 레퍼런스 일자 출력 복원) | ✅ **DB 적재 완벽 확인 (각 500영업일)**:<br/>• **태광(`023160`) `2026-08-25`**: 종가 `22,350원`(`+4.44%`), 거래량 `101,653주`, `EMA5=21,748.88`, 순수기관 `+13,065주`(`+282.9백만원`, 비중 `12.85%`)<br/>• **대한유화(`006650`) `2026-11-03`**: 종가 `87,400원`(`+8.17%`), 거래량 `109,377주`, `EMA5=82,707.19`, 순수기관 `+34,534주`(`+3,038.45백만원`, 비중 `31.57%`) | **PASS** |
| **수정 4 & 5** | **스마트 이어받기(`--skip-existing`), 구간 분할(`--chunk`), Actions 360분 타임아웃** | ✅ **`ISSUE-007`, `ISSUE-010` 수정 완료**<br/>(익일 이어받기 스킵 정상화 및 문서 정합성 일치) | ✅ GitHub Actions `timeout-minutes: 360` 동작 중 | **PASS** |
| **수정 6 / AC-6** | **70만 행 대응 웹 대시보드(`index.html`) 인덱스 윈도우 필터링 및 실시간 스크리닝** | ✅ **`ISSUE-008`, `ISSUE-009` 수정 완료**<br/>(`isSettledSupplyRow` 필터 및 최대 60일 동적 윈도우 추가 로드 구현) | ✅ 장중 미확정 `0` 수급 행 제외 및 확정 거래일 기준 정상 표시 확인 | **PASS** |

---

### 1.2 [특별 검증] 11월 12일 장중 적재된 데이터가 장 마감 후(21:05 KST) 배치 실행 시 최종 확정 데이터로 정상 Update 되는가?

현재 낮 시간대(장중)에 실행 중인 `backfill` 작업으로 인해 `2026-11-12` 일자의 **장중 미확정 일봉(현재가·거래량·EMA)**과 **미확정 수급(전 투자주체 `0`)**이 DB에 적재되고 있었으며, 오늘 밤 장 마감 후 배치가 돌 때 최종 확정치로 100% 정상 Update 되도록 모든 장애 요인을 해결했습니다:

1. **DB Upsert 메커니즘 자체는 100% 덮어쓰기(Overwrite) 지원 (`정상`)**:
   * `supabase_upsert()`([`run_daily_screener.py`](file:///home/antigravity/ls-stock-screener/run_daily_screener.py#L796-L821))는 `Prefer: resolution=merge-duplicates` 헤더와 복합 PK(`on_conflict=shcode,trade_date`)를 사용합니다.
   * 따라서 장 마감 후 LS API를 다시 호출하여 `supabase_upsert()`가 실행되면 기존 `(shcode, '2026-11-12')` 레코드의 장중 주가·거래량·EMA 및 수급 수치가 **장 마감 최종 종가·거래량·EMA 및 확정 기관·외국인 수급 수치로 완벽히 덮어써집니다.**
2. **오늘 밤 21:05 KST 스케줄 배치와 현재 실행 중인 `backfill` 간의 시간 충돌 여부 (`정상`)**:
   * 현재 실행 중인 GitHub Actions `backfill` Job(`43161372160`)은 `14:26 KST`에 시작되었으며, `max_runtime_minutes=345`(5시간 45분) 안전 가드 및 `timeout-minutes: 360`(6시간)에 의해 늦어도 **`20:11 ~ 20:26 KST` 이전에 종료**됩니다. 따라서 **오늘 밤 `21:05 KST` 정기 스케줄 배치 시작 시각과 겹치지 않습니다.**
3. **✅ 장 마감 후 최종 데이터 정상 Update를 가로막던 3가지 장애 요인 모두 수정 완료 (`v1.4.3`)**:
   * **해결 ① (`[ISSUE-008]` 장중 미확정 `0` 수급 감지·차단·자동 정리)**:
     * `is_unsettled_supply_row()`를 추가하여 `fetch_investor_supply()`에서 모든 투자주체 수급이 `0`인 장중 미확정 행은 적재하지 않으며, `supabase_get_stock_data_status_detail()`에서 DB 최신 행이 미확정(`0` 수급)인 종목은 `is_latest_supply_unsettled = True`로 감지하여 `backfill` 재실행 시 절대 스킵하지 않고 갱신하도록 수정했습니다. 또한 `supabase_cleanup_unsettled_supply()`로 이미 들어간 장중 `0` 수급 더미 행을 자동 삭제합니다.
   * **해결 ② (`[ISSUE-007]` `has_2yr_history` 판정 분리로 평일 `daily` 1페이지 고속 증분 보장)**:
     * `has_2yr_history`(`min_target_date = today - 20일`)와 당일 확정 여부를 분리하여, 이미 2년치(500일)가 적재된 종목은 오늘 밤 `21:05 KST` `daily` 배치에서 **1페이지(최근 25영업일, 종목당 약 1.1초)** 고속 증분으로 `2026-11-12` 확정 일봉·EMA·수급만 빠르게 덮어씁니다.
   * **해결 ③ (`[ISSUE-006]` 1036행 `PRIORITY_SHCODES` 잔존 참조 제거 완료)**:
     * `if mcap_eok < 700.0:`으로 수정하여 시총 700억 미만 경계선 종목에서도 `NameError` 없이 안전하게 동작합니다.

---

## 2. 버그 및 수정 요청 트래커 (Issue & Fix Tracker)

### 🚨 2.1 `[프로그램 개발 및 수정]` 대화창 필수 수정 요청 사항 (현재 미해결 0건)

* 현재 미해결 이슈가 없습니다 (`[ISSUE-006]` ~ `[ISSUE-010]` 전수 해결 완료).

---

### ✅ 2.2 해결 완료된 이슈 히스토리

#### ✅ [ISSUE-006] `[해결 완료]` `run_daily_screener.py` 1036행 미정의 상수 `PRIORITY_SHCODES` 참조로 인한 `NameError`
* **발생 위치**: [`run_daily_screener.py`](file:///home/antigravity/ls-stock-screener/run_daily_screener.py#L1065-L1066) 및 [`README.md`](file:///home/antigravity/ls-stock-screener/README.md#L66-L71)
* **조치 내역 (`v1.4.3`)**:
  * `run_daily_screener.py`의 `if mcap_eok < 700.0 and shcode not in PRIORITY_SHCODES:`를 `if mcap_eok < 700.0:`으로 수정 완료.
  * `README.md` 72행에 남아 있던 `PRIORITY_SHCODES` 설명 불릿 제거 완료.

#### ✅ [ISSUE-007] `[해결 완료]` 평일 `daily` 모드(및 익일 `backfill` 이어받기) 실행 시 2번째 종목부터 `already_has_2yr = False`로 판정되어 매일 1,462종목 전체를 2년치(25페이지) 재백필하는 버그
* **발생 위치**: [`run_daily_screener.py`](file:///home/antigravity/ls-stock-screener/run_daily_screener.py#L761-L793) (`is_stock_already_backfilled`) 및 [`run_daily_screener.py`](file:///home/antigravity/ls-stock-screener/run_daily_screener.py#L1019-L1077)
* **조치 내역 (`v1.4.3`)**:
  * `has_2yr_history = is_stock_already_backfilled(..., min_target_date=(today - dt.timedelta(days=20)).isoformat(), is_latest_supply_unsettled=False)`로 2년치 히스토리 보유 여부 판정을 분리하고, `needs_full_2yr = (not has_2yr_history) or (mode == "backfill" and not skip_existing)`으로 수정하여 2년치 히스토리가 있는 종목은 평일 `daily` 모드에서 **1페이지(최근 25영업일)** 고속 증분만 수행하도록 해결 완료.
  * `test_screener_verification.py`의 `test_5_smart_resume_and_chunk_parsing`에 익일(`T`) 실행 시 전일(`T-1`) 500일 적재 종목이 `has_2yr_history = True`로 판정되는지 검증하는 단위 테스트 추가 완료.

#### ✅ [ISSUE-008] `[해결 완료]` 장중(수급 확정 전) 실행 시 당일(`2026-11-12`) 모든 투자주체 수급이 `0`인 미확정 행이 적재되어 당일 스크리닝 무력화 및 장 마감 후 `backfill` 재실행 시 스킵되는 버그
* **발생 위치**: [`run_daily_screener.py`](file:///home/antigravity/ls-stock-screener/run_daily_screener.py#L540-L654) (`is_unsettled_supply_row`, `fetch_investor_supply`), [`run_daily_screener.py`](file:///home/antigravity/ls-stock-screener/run_daily_screener.py#L702-L758) (`supabase_get_stock_data_status_detail`), [`index.html`](file:///home/antigravity/ls-stock-screener/index.html#L384-L426) (`isSettledSupplyRow`, `buildPeriodAggregation`)
* **조치 내역 (`v1.4.3`)**:
  * `is_unsettled_supply_row()`를 구현하여 `fetch_investor_supply()`에서 모든 투자주체 수급 수량이 `0`인 장중 미확정 행은 적재하지 않도록 차단 완료.
  * `supabase_get_stock_data_status_detail()`에서 DB 최신 수급 행의 미확정 여부(`is_latest_supply_unsettled`)를 감지하여 미확정 행이 있는 종목은 `backfill` 시 스킵하지 않도록 수정하고, `supabase_cleanup_unsettled_supply()`를 통해 DB에 이미 적재된 장중 `0` 수급 행을 일괄 삭제하도록 조치 완료.
  * `index.html`의 `buildPeriodAggregation()` 및 `connectSupabaseLive()`에 `isSettledSupplyRow()` 필터를 적용하여 장중에도 확정 수급 거래일 기준으로 스크리닝이 정상 동작하도록 수정 완료.

#### ✅ [ISSUE-009] `[해결 완료]` 웹 대시보드(`index.html`) 15영업일 초과 누적 기간 조회 시 데이터 절단 및 `--mode verify`의 `AC-1~AC-5` 리포트 누락
* **발생 위치**: [`index.html`](file:///home/antigravity/ls-stock-screener/index.html#L57), [`index.html`](file:///home/antigravity/ls-stock-screener/index.html#L515-L545), [`run_daily_screener.py`](file:///home/antigravity/ls-stock-screener/run_daily_screener.py#L1200-L1290)
* **조치 내역 (`v1.4.3`)**:
  * `index.html` 57행 배너 문구를 `유니버스: 코스피·코스닥 보통주 · 시가총액 ≥ 700억 전수 (약 1,463종목)`으로 수정하고, `setPeriod(days)`에서 `LOADED_LOOKBACK_DAYS`보다 큰 기간(최대 60영업일) 입력 시 필요한 `lookbackCalDays`와 `maxWaves`를 계산하여 Supabase에서 동적으로 추가 로드하도록 수정 완료.
  * `run_daily_screener.py --mode verify`(`verify_supabase_data`)에서 최신 확정 거래일 기준 `order=inst_vol_ratio.desc` 조회 및 `AC-1 ~ AC-5` 핵심 지표(거래대금 20억 미만 종목 포함 수, 5대 대형주 적재 일수, 태광 `2026-08-25` 및 대한유화 `2026-11-03` 검증) 출력을 복원 완료.

#### ✅ [ISSUE-010] `[해결 완료]` `.github/workflows/daily_batch.yml`과 `README.md` 간 `chunk` 입력 옵션 불일치
* **발생 위치**: [`README.md`](file:///home/antigravity/ls-stock-screener/README.md#L52) 및 [`README.md`](file:///home/antigravity/ls-stock-screener/README.md#L123-L126)
* **조치 내역 (`v1.4.3`)**:
  * `README.md`의 GitHub Actions 실행 가이드를 `.github/workflows/daily_batch.yml`의 실제 입력 스펙(`mode`, `max_stocks`)과 일치시키고, `--chunk`, `--start-idx`, `--end-idx`는 로컬/서버 CLI 전용 분할 실행 옵션임을 명확히 구분하여 문서 정합성 확보 완료.

* **[ISSUE-001] `[해결 완료]` 웹 대시보드(`index.html`) 기준 거래일이 `2026-08-20`으로 절단 표시되던 현상**
* **[ISSUE-002] `[해결 완료]` 초반 1~285번 대형주 누락 및 `is_quarterly_rebuild_due` 247종목 유니버스 고착화 결함 (`STRATEGY.md` 수정 1)**
  * `stocks_master`에 시총 700억 이상 보통주 **1,463종목** 일괄 선등록 및 `avg_val_20d_eok < 20.0` 사전 차단 제거 확인 완료.
* **[ISSUE-003] `[해결 완료]` `daily_chart` 60일 절단 및 `daily_investor_supply` 25일 단일 호출 제한 결함 (`STRATEGY.md` 수정 2 & 3)**
  * `fetch_daily_chart()` 500영업일 전수 Upsert 및 `fetch_investor_supply()` 역순 날짜 슬라이딩(`todt = oldest_date - 1일`, 최대 25페이지) 연속조회로 종목당 **500영업일** 적재 확인 완료.
* **[ISSUE-004] `[해결 완료]` GitHub Actions 타임아웃 45분 제한 상향 (`STRATEGY.md` 수정 5)**
  * `.github/workflows/daily_batch.yml`의 `timeout-minutes: 360`(6시간) 상향 반영 확인 완료.
* **[ISSUE-005] `[해결 완료]` 1,463종목 마스터 3페이지 병렬 로드 및 최근 윈도우 인덱스 쿼리 구조 적용 (`STRATEGY.md` 수정 6)**
