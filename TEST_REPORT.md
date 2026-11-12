# 🧪 LS 수급·차트 스크리너 검증 및 테스트 리포트 (`TEST_REPORT.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[검증 및 테스트]` 전담 대화창**에서 테스트 실행 결과, `STRATEGY.md` 대조 검수, 데이터 정합성 검증 리포트, 발견된 버그 및 구체적인 코드 수정 제안을 기록하는 문서입니다.
> * **`[프로그램 개발 및 수정(메인)]` 대화창**은 작업 시작 전 본 `TEST_REPORT.md`와 `STRATEGY.md`를 확인하여 미해결 버그(`2.1절 신규 수정 요청 사항`)를 코드에 반영하고, 수정이 완료된 항목의 상태를 **`[해결 완료]`**로 업데이트합니다.

---

## 1. 최신 검수 요약 (v1.4 ~ v1.4.2 커밋 `56518de`, `aa880f7`, `f6ffca9` 정밀 검수)

* **검수 일시**: `2026-11-12 14:56 KST` (`2026-11-11 21:56 PST`)
* **대상 커밋**:
  * `56518de` — `Feat(v1.4): Implement 1,477 full universe, 2-year 500d chart/supply sliding backfill, smart resume, and 700k-row web query optimization`
  * `aa880f7` — `Fix(v1.4.1): Handle LS Open API gateway 302->404 rate-limit redirects and set safe 0.62s interval on t1444`
  * `f6ffca9` — `Refactor(v1.4.2): Remove PRIORITY_SHCODES and _prioritize_candidates reference stock routines`
* **기본 단위 테스트 (`python3 test_screener_verification.py`)**: **5 / 5 항목 통과 (`OK`)**
* **GitHub Actions 배치 실행 상태**: 워크플로우 Run `43161372160` (`mode: backfill`, `timeout-minutes: 360`) 현재 실시간 백필 진행 중 (`stocks_master` **1,463종목** 선등록 완료, 상위 대형주 및 핵심 레퍼런스 종목 500영업일 적재 완료 후 순차 적재 중)

---

### 1.1 `STRATEGY.md` 0.2절 (수정 1~6) & 0.4절 (`AC-1` ~ `AC-6`) 대조 검수 결과표

| 구분 | 요구사항 및 합격 기준 (`STRATEGY.md`) | 코드 검수 결과 | 실시간 Supabase DB 실증 결과 | 최종 판정 |
| :---: | :--- | :---: | :--- | :---: |
| **수정 1 / AC-1** | **시총 700억 이상 보통주 전수 유니버스 구축**<br/>• ETF/ETN/ELW/스팩/우선주/리츠 혼입 0건<br/>• 1,200종목 미만 미완성 감지(`is_quarterly_rebuild_due`)<br/>• 대형주(삼성전자·SK하이닉스·현대차·한화에어로·알테오젠) 포함 | ⚠️ **구현 완료했으나 1036행 `NameError` 버그 존재** (`[ISSUE-006]`) | ✅ **`stocks_master` 1,463종목 등록 완료**<br/>• 제외종목 혼입: **0건** / 시총 700억 미만: **0건**<br/>• 5대 대형주 모두 `chart=500일, supply=500일` 적재 완료 | **조건부 PASS**<br/>(`ISSUE-006` 수정 필요) |
| **수정 1 / AC-2** | **수집 단계 거래대금 20억 미만(`avg_val_20d_eok < 20.0`) 사전 차단 제거** | ✅ **구현 완료**<br/>(`if avg_val_20d_eok < 20.0: continue` 삭제 확인) | ⏳ 시총 상위부터 순차 백필 중 (현재 상위 294종목 완료, 중소형주 구간 진입 시 `avg_val_20d_eok` 갱신 예정) | **코드 PASS**<br/>(백필 완주 대기) |
| **수정 2 / AC-3** | **`daily_chart` 2년치(500영업일) 전수 적재 및 EMA(5·20·60·120·240) 정합성**<br/>• `[-60:]` 절단 폐기 및 500일 전수 Upsert | ✅ **구현 완료**<br/>(`fetch_daily_chart` count=500, 역순 보완 및 전수 Upsert) | ✅ 백필 완료된 종목 모두 정확히 **500영업일** 적재 및 EMA 5·20·60·120·240 산출 확인 | **PASS** |
| **수정 3 / AC-4** | **`daily_investor_supply` 2년치(500영업일) 역순 슬라이딩 연속 수집 및 1:1 매칭**<br/>• 평일 `daily` 모드 최근 25일(1페이지) 고속 증분 | ❌ **구현되었으나 2건의 중요 로직 결함 발견**<br/>(`ISSUE-007`, `ISSUE-008`) | ⚠️ 백필 종목당 **500영업일** 적재 및 6대 주체 수식 오차 **0건** 확인했으나, 장중 실행분(`2026-11-12`)에 전 주체 `0`인 미확정 수급 행이 적재됨 | **FAIL (수정 요청)**<br/>(`ISSUE-007`, `ISSUE-008`) |
| **AC-5** | **핵심 레퍼런스 종목(`태광 023160`, `대한유화 006650`) 2년치 과거 데이터 실증 확인** | ⚠️ 본체 수집은 정상이나 `--mode verify`에서 AC-5 검증 출력 코드가 `f6ffca9`에서 삭제됨 (`ISSUE-009`) | ✅ **DB 적재 완벽 확인 (각 500영업일)**:<br/>• **태광(`023160`) `2026-08-25`**: 종가 `22,350원`(`+4.44%`), 거래량 `101,653주`, `EMA5=21,748.88`, 순수기관 `+13,065주`(`+282.9백만원`, 비중 `12.85%`)<br/>• **대한유화(`006650`) `2026-11-03`**: 종가 `87,400원`(`+8.17%`), 거래량 `109,377주`, `EMA5=82,707.19`, 순수기관 `+34,534주`(`+3,038.45백만원`, 비중 `31.57%`) | **DB 데이터 PASS**<br/>(`--mode verify` 복원 권장) |
| **수정 4 & 5** | **스마트 이어받기(`--skip-existing`), 구간 분할(`--chunk`), Actions 360분 타임아웃** | ⚠️ 타임아웃 360분 및 CLI 옵션 구현 완료했으나, 날짜 변경 시 이어받기 무력화(`ISSUE-007`) 및 워크플로우 `chunk` 입력 누락(`ISSUE-010`) | ✅ GitHub Actions `timeout-minutes: 360` 동작 중 | **조건부 PASS**<br/>(`ISSUE-007`, `ISSUE-010`) |
| **수정 6 / AC-6** | **70만 행 대응 웹 대시보드(`index.html`) 인덱스 윈도우 필터링 및 실시간 스크리닝** | ⚠️ 병렬 윈도우 조회(`trade_date >= cutoffDate`)는 구현 완료했으나 장중 `0` 수급 행 매칭 및 16일 초과 기간 조회 한계 존재 (`ISSUE-008`, `ISSUE-009`) | ⚠️ 장중 적재된 `2026-11-12`(`real_inst_vol=0`) 행 때문에 `index.html`에서 당일(1일) 선택 시 오늘 백필된 종목들의 수급이 `0.0%`로 표시됨 | **FAIL (수정 요청)**<br/>(`ISSUE-008`, `ISSUE-009`) |

---

### 1.2 [특별 검증] 11월 12일 장중 적재된 데이터가 장 마감 후(21:05 KST) 배치 실행 시 최종 확정 데이터로 정상 Update 되는가?

현재 낮 시간대(장중)에 실행 중인 `backfill` 작업으로 인해 `2026-11-12` 일자의 **장중 미확정 일봉(현재가·거래량·EMA)**과 **미확정 수급(전 투자주체 `0`)**이 DB에 적재되고 있습니다(15:05 KST 기준 72종목). 오늘 밤 장 마감 후 배치가 돌 때 이 데이터들이 최종 확정치로 정상 Update 될 수 있는지 검증한 결과는 다음과 같습니다:

1. **DB Upsert 메커니즘 자체는 100% 덮어쓰기(Overwrite) 지원 (`정상`)**:
   * `supabase_upsert()`([`run_daily_screener.py` 773~798행](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L773-L798))는 `Prefer: resolution=merge-duplicates` 헤더와 복합 PK(`on_conflict=shcode,trade_date`)를 사용합니다.
   * 따라서 장 마감 후 LS API를 다시 호출하여 `supabase_upsert()`가 실행되기만 하면, 기존 `(shcode, '2026-11-12')` 레코드의 장중 주가·거래량·EMA 및 `0`이었던 수급 수치가 **장 마감 최종 종가·거래량·EMA 및 확정 기관·외국인 수급 수치로 완벽히 덮어써집니다.**
2. **오늘 밤 21:05 KST 스케줄 배치와 현재 실행 중인 `backfill` 간의 시간 충돌 여부 (`정상`)**:
   * 현재 실행 중인 GitHub Actions `backfill` Job(`43161372160`)은 `14:26 KST`에 시작되었으며, `max_runtime_minutes=345`(5시간 45분) 안전 가드 및 `timeout-minutes: 360`(6시간)에 의해 늦어도 **`20:11 ~ 20:26 KST` 이전에 종료**됩니다. 따라서 **오늘 밤 `21:05 KST` 정기 스케줄 배치 시작 시각과 겹치지 않습니다.**
3. **🚨 [주의] 장 마감 후 최종 데이터 정상 Update를 가로막는 현행 코드의 3가지 장애 요인 (반드시 오늘 밤 배치 전 수정 필요)**:
   * **장애 요인 ① (`mode: backfill`로 이어받기 실행 시 장중 적재 종목이 `[SKIP]`되어 `0` 수급이 영구 고착됨 — `[ISSUE-008]`)**:
     * 현행 `supabase_get_stock_data_status()`([702~743행](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L702-L743))는 `daily_investor_supply`의 최신 행이 `2026-11-12`이기만 하면 그 안의 수급 값이 전부 `0`(장중 미확정 더미 행)인지 확인하지 않고 `supply_latest = "2026-11-12"`로 반환합니다.
     * 따라서 장 마감 후 `mode: backfill`(`--skip-existing`)을 다시 실행하면, 낮에 적재된 종목들(`chart_cnt=500, supply_cnt=500, supply_latest='2026-11-12'`)을 **"이미 11월 12일까지 완벽히 적재 완료됨(`already_has_2yr = True`)"으로 오판하여 `continue`로 건너뛰어 버립니다!** 이 경우 낮에 들어간 `0` 수급 데이터가 확정 데이터로 업데이트되지 않습니다.
   * **장애 요인 ② (`mode: daily` 실행 시 미백필 종목 + `[ISSUE-007]`로 인해 21:05 배치가 6시간 내 완주하지 못할 위험)**:
     * 밤 `21:05 KST` 정기 배치는 `mode: daily`로 실행됩니다. `mode: daily`는 스킵 분기를 타지 않으므로 낮에 적재된 종목들을 다시 조회하여 `2026-11-12` 확정 데이터로 덮어씁니다.
     * **그러나** `[ISSUE-007]` 버그 때문에 DB의 `chart_latest`가 `2026-11-11`인 종목들은 전부 `already_has_2yr = False`로 판정되어 1페이지(25일) 고속 증분이 아니라 25페이지(500일) 전체 백필을 수행하게 됩니다.
   * **장애 요인 ③ (`[ISSUE-006]` 1036행 `PRIORITY_SHCODES` `NameError`)**:
     * 장 마감 종가 기준으로 시가총액이 700억 원 미만으로 내려간 경계선 종목에서 `NameError`가 발생합니다.

---

## 2. 버그 및 수정 요청 트래커 (Issue & Fix Tracker)

### 🚨 2.1 `[프로그램 개발 및 수정]` 대화창 필수 수정 요청 사항 (미해결 5건)

---

#### 🔴 [ISSUE-006] `[미해결 / Critical]` `run_daily_screener.py` 1036행 미정의 상수 `PRIORITY_SHCODES` 참조로 인한 `NameError`
* **발생 위치**: [`run_daily_screener.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1036-L1037) (및 [`README.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/README.md#L72))
* **버그 원인**:
  * 커밋 `f6ffca9` (`Refactor(v1.4.2): Remove PRIORITY_SHCODES and _prioritize_candidates reference stock routines`)에서 파일 상단의 `PRIORITY_SHCODES` 상수 정의를 삭제했으나, **1036행의 조건문 내부에는 `PRIORITY_SHCODES` 참조가 그대로 남아 있습니다.**
  ```python
  # run_daily_screener.py 1036~1037행 (현재 코드)
  if mcap_eok < 700.0 and shcode not in PRIORITY_SHCODES:
      continue
  ```
* **재현 방법 및 영향**:
  * `mcap_eok >= 700.0`인 종목에서는 Python `and` 단락 평가(short-circuit)로 인해 뒤쪽 조건이 평가되지 않아 숨겨져 있다가,
  * 주가 변동으로 인해 `mcap_eok = round((shares * last_close) / 100_000_000.0, 2) < 700.0`이 되는 종목을 만나는 즉시 **`NameError: name 'PRIORITY_SHCODES' is not defined` 예외가 발생**합니다.
* **구체적인 코드 수정 제안**:
  1. [`run_daily_screener.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1036-L1037) 1036행을 다음과 같이 수정:
     ```python
     if mcap_eok < 700.0:
         continue
     ```
  2. [`README.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/README.md#L72) 72행에 남아 있는 `PRIORITY_SHCODES` 설명 불릿도 함께 제거.

---

#### 🔴 [ISSUE-007] `[미해결 / High]` 평일 `daily` 모드(및 익일 `backfill` 이어받기) 실행 시 2번째 종목부터 `already_has_2yr = False`로 판정되어 매일 1,462종목 전체를 2년치(25페이지) 재백필하는 버그
* **발생 위치**: [`run_daily_screener.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L746-L771) (`is_stock_already_backfilled`) 및 [`run_daily_screener.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L993-L1059)
* **버그 원인**:
  * 루프 시작 시 `latest_trade_date = ""`였다가, **1번째 종목(`idx=1`, 삼성전자 `005930`)의 일봉을 조회하는 순간 `latest_trade_date`가 당일(`T`, 예: `2026-11-12`)로 갱신**됩니다(1025~1026행).
  * 이어서 **2번째 종목(`idx=2`, SK하이닉스 `000660`)부터 1,463번째 종목까지**는 아직 당일(`T`) 데이터를 적재하기 전이므로 DB의 `chart_latest`와 `supply_latest`가 전일(`T-1`, 예: `2026-11-11`)입니다.
  * 그런데 993~995행에서 `min_target_date=latest_trade_date`(`T`)를 넣어 `is_stock_already_backfilled()`를 호출하면, 762행의 `if min_target_date and (chart_latest < min_target_date or supply_latest < min_target_date): return False` 때문에 **이미 500영업일이 완벽히 적재된 종목들도 2번째 종목부터 전부 `already_has_2yr = False`가 됩니다!**
  * 그 결과 1045행 `needs_full_2yr = (mode == "backfill") or (not already_has_2yr)`가 무조건 `True`가 되어, **평일 저녁 `daily` 모드에서도 1번째 종목만 1페이지 증분(`incremental_count=1`)으로 돌고 나머지 1,462종목 전체가 매일 25페이지(500일) 전체 백필(4.5시간 소요)을 다시 수행**하게 됩니다.
  * 또한 `backfill`이 자정을 넘기거나 다음 거래일에 이어받기(`--skip-existing`)를 실행할 때에도, 전날 이미 500일 백필을 마친 종목(`chart_latest = T-1`)이 스킵되지 않고 25페이지 전체 백필을 다시 도는 문제가 발생합니다.
* **재현 방법**:
  * DB에 `chart_cnt=500, supply_cnt=500, chart_latest="2026-11-11", supply_latest="2026-11-11"`인 종목이 있을 때, 새 거래일 `"2026-11-12"`에 1번째 종목 처리 후 `latest_trade_date="2026-11-12"`가 된 상태에서 `is_stock_already_backfilled(500, "2026-11-11", 500, "2026-11-11", min_target_date="2026-11-12")`를 호출하면 `False`가 반환되어 `needs_full_2yr = True`(25페이지 호출)로 빠짐.
* **구체적인 코드 수정 제안**:
  * **"2년치 히스토리 보유 여부(`has_2yr_history`)"**와 **"당일 최신 확정 거래일까지 업데이트 완료 여부(`is_settled_today`)"**를 명확히 분리해 주십시오:
  ```python
  # 1) 2년치 과거 시계열이 DB에 구축되어 있는지 판정 (최근 20달력일 이내 데이터 보유 & 400영업일 이상 또는 신규상장 전 기간)
  has_2yr_history = is_stock_already_backfilled(
      chart_cnt, chart_latest, supply_cnt, supply_latest,
      min_target_date=(today - dt.timedelta(days=20)).isoformat(),
  )

  # 2) backfill 모드에서 이미 2년치 히스토리가 구축되어 있고, 최신 수급 행이 장중 미확정(0 수급) 상태가 아니라면 즉시 스킵(--skip-existing)
  if mode == "backfill" and skip_existing and has_2yr_history and not is_latest_supply_unsettled:
      skipped_count += 1
      universe_count += 1
      if chart_latest > latest_trade_date:
          latest_trade_date = chart_latest
      ...
      continue

  # 3) 수급 수집 시: 2년치 히스토리가 아직 없는 종목(또는 --force-all)만 25페이지 전체 백필,
  #    이미 2년치 히스토리가 있는 종목(낮에 장중 미확정 데이터가 들어간 종목 포함)은 최근 1페이지(25영업일)만 고속 증분 Upsert!
  needs_full_2yr = (not has_2yr_history) or (mode == "backfill" and not skip_existing)
  ```

---

#### 🔴 [ISSUE-008] `[미해결 / High]` 장중(수급 확정 전) 실행 시 당일(`2026-11-12`) 모든 투자주체 수급이 `0`인 미확정 행이 적재되어 당일 스크리닝 무력화 및 장 마감 후 `backfill` 재실행 시 스킵되는 버그
* **발생 위치**: [`run_daily_screener.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L562-L639) (`fetch_investor_supply`), [`run_daily_screener.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L702-L743) (`supabase_get_stock_data_status`), [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L384-L423) (`buildPeriodAggregation`)
* **버그 원인 및 실증 데이터**:
  1. 현재 GitHub Actions에서 낮 시간대(KST 14:26~)에 실행된 `backfill` 워크플로우(`43161372160`)로 인해, DB의 `daily_chart`와 `daily_investor_supply`에 **`trade_date = '2026-11-12'` 레코드가 적재**되고 있습니다.
  2. 그러나 장 마감 및 투자자별 확정 수급 집계 전에는 LS증권 `t1717` TR이 당일(`20261112`) 행의 **모든 투자주체 순매수 수량·금액(`pef_vol`, `fn_inv_vol`, `ins_vol`, `itc_vol`, `bank_vol`, `etc_fin_vol`, `pen_vol`, `etc_corp_vol`, `ind_vol`, `frg_vol`)을 `0`으로 반환**합니다.
  3. 실제 현재 Supabase DB에서 `trade_date=eq.2026-11-12`인 `daily_investor_supply` 레코드(72건)를 전수 조회한 결과, **72건 모두 `real_inst_vol = 0, frg_vol = 0, ind_vol = 0, fn_inv_vol = 0` (`non-zero rows: 0건`)**임을 확인했습니다.
  4. 이로 인해 발생하는 연쇄 문제:
     * **장 마감 후 `backfill` 재실행 시 미갱신**: `supabase_get_stock_data_status()`가 `supply_latest = '2026-11-12'`, `supply_cnt = 500`만 보고 이미 완료된 종목으로 판정하므로, 장 마감 후 `mode: backfill`을 다시 돌려도 낮에 들어간 1~N번 종목들이 전부 스킵되어 `2026-11-12`의 `0` 수급이 확정 데이터로 업데이트되지 않습니다.
     * **`--mode verify` 및 `index.html` 당일 스크리닝 `0.0%` 무력화**: 최신 거래일이 `2026-11-12`로 잡혀 `--mode verify`의 4번 상위 종목이 `0건`으로 출력되고, `index.html`에서 당일(1일) 선택 시 오늘 백필된 삼성전자, SK하이닉스, 현대차, 대한유화, 태광 등의 기관 비중이 모두 `0.0%`로 표시됩니다.
* **구체적인 코드 수정 제안**:
  1. **`supabase_get_stock_data_status()`에서 최신 수급 행의 미확정(`전 주체 0`) 여부 감지**:
     * [`run_daily_screener.py` 733행](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L733)에서 `select=trade_date,real_inst_vol,frg_vol,ind_vol,fn_inv_vol`을 조회하여, 최신 행의 4개 수량이 모두 `0`이면 장중 미확정 상태(`is_latest_supply_unsettled = True`)로 판정하십시오.
     * 장중 미확정 상태인 종목은 장 마감 후 `backfill`이나 `daily` 실행 시 **절대 스킵하지 않고**, 이미 `chart_cnt >= 400 and supply_cnt >= 400`이므로 **1페이지(`max_pages=1`, 최근 25영업일) 고속 증분 Upsert만 수행하여 `2026-11-12`의 일봉·EMA·수급을 약 1.1초 만에 장 마감 확정 데이터로 덮어쓰도록** 구현하십시오.
  2. **`fetch_investor_supply()`에서 장중 미확정(`전 주체 0`) 당일 행 적재 차단**:
     * `t1717` 응답 행 중 모든 투자주체(`pef_vol`, `fn_inv_vol`, `ins_vol`, `itc_vol`, `bank_vol`, `etc_fin_vol`, `pen_vol`, `etc_corp_vol`, `ind_vol`, `frg_vol`)의 수량이 전부 `0`인 최신일 행은 아직 수급이 집계되지 않은 장중 더미 행이므로 `by_date`에 넣지 않고 건너뛰십시오.
  3. **`index.html` — 미확정(`전 주체 0`) 수급 행 자동 제외 방어 로직 추가**:
     * [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L393-L396)의 `buildPeriodAggregation()`에서 모든 투자주체 수량이 0인 미확정 행을 제외하도록 필터를 보강하십시오:
     ```javascript
     const isSettledSupplyRow = s =>
       Number(s.real_inst_vol || 0) !== 0 ||
       Number(s.frg_vol || 0) !== 0 ||
       Number(s.ind_vol || 0) !== 0 ||
       Number(s.fn_inv_vol || 0) !== 0 ||
       Number(s.etc_corp_vol || 0) !== 0;

     const matchedPairs = supplies
       .filter(s => isSettledSupplyRow(s) && chartByDate[s.trade_date] && Number(chartByDate[s.trade_date].volume || 0) > 0)
       .slice(-periodDays);
     ```

---

#### 🟡 [ISSUE-009] `[미해결 / Medium]` 웹 대시보드(`index.html`) 15영업일 초과 누적 기간 조회 시 데이터 절단 및 `--mode verify`의 `AC-1~AC-5` 리포트 누락
* **발생 위치**: [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L57), [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L129-L132), [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L511-L522), [`run_daily_screener.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1173-L1240)
* **버그 원인**:
  1. **`index.html` 기간 선택(`customDaysInput`) 절단**: UI의 직접 입력창(`#customDaysInput`, 129행)은 `max="60"`(최대 60영업일)까지 입력을 허용하지만, 초기 로드 시 `currentPeriod = 1` 기준으로 `lookbackCalDays = 24`(약 15~16영업일, 3웨이브 최대 24,000행)만 가져오며, 이후 사용자가 `setPeriod(20)` 등을 입력해도 추가 DB 조회 없이 메모리의 15~16영업일 데이터만 합산합니다.
  2. **`index.html` 상단 배너 문구 불일치**: 57행에 여전히 구버전 기준인 `유니버스: 코스피·코스닥 보통주 · 시가총액 ≥ 700억 · 20일 평균 거래대금 ≥ 20억` 문구가 남아 있습니다 (`STRATEGY.md` 수정 1에 따라 수집 유니버스는 시총 700억 이상 보통주 전수임).
  3. **`run_daily_screener.py --mode verify` 최신일 1,000건 절단 및 `AC-2/AC-5` 검증 출력 누락**:
     * `verify_supabase_data()`(1184행)에서 `daily_investor_supply?select=*&order=trade_date.desc&limit=1000`으로 1,000건만 가져오므로, 1,463종목 전수 적재 시 최신 거래일의 나머지 463종목이 누락된 채로 4번 상위 종목 리스트를 출력합니다 (`inst_vol_ratio.desc` 정렬 조건 또는 2페이지 조회 필요).
     * 또한 커밋 `f6ffca9`에서 `PRIORITY_SHCODES`를 제거하면서 `verify_supabase_data()` 내에 있던 `AC-2`(`avg_val_20d_eok < 20.0` 중소형주 포함 건수), `AC-1` 대형주 5종 적재 일수, `AC-5`(태광 `2026-08-25`, 대한유화 `2026-11-03` 레코드 확인) 출력 코드까지 함께 삭제되어 `--mode verify`만으로는 `STRATEGY.md` 0.4절의 `AC-1 ~ AC-5` 통과 여부를 한눈에 확인할 수 없습니다. (수집 우선순위 하드코딩은 제거하더라도, `--mode verify`의 검증 리포트에서는 `AC-1 ~ AC-5` 확인 항목을 출력하는 것이 `STRATEGY.md` 0.4절 규정에 부합합니다.)
* **구체적인 코드 수정 제안**:
  1. `index.html` 57행의 유니버스 설명을 `유니버스: 코스피·코스닥 보통주 · 시가총액 ≥ 700억 전수 (약 1,463종목)`으로 정정하고, `setPeriod(days)`에서 현재 로드된 윈도우 일수보다 큰 기간이 입력되면 추가 웨이브를 조회하거나 입력 범위를 로드된 윈도우에 맞게 동기화하십시오.
  2. `verify_supabase_data()`에서 최신 확정 거래일(`real_inst_vol != 0` 또는 `frg_vol != 0`) 기준으로 상위 종목 조회 시 `order=trade_date.desc,inst_vol_ratio.desc`를 사용하고, `AC-1 ~ AC-5` 핵심 지표(거래대금 20억 미만 종목 수, 태광 `2026-08-25` 및 대한유화 `2026-11-03` 실데이터 존재 여부) 출력을 복원하십시오.

---

#### 🟢 [ISSUE-010] `[미해결 / Low]` `.github/workflows/daily_batch.yml`과 `README.md` 간 `chunk` 입력 옵션 불일치
* **발생 위치**: [`.github/workflows/daily_batch.yml`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/.github/workflows/daily_batch.yml#L8-L50) 및 [`README.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/README.md#L52)
* **원인**:
  * `README.md` 52행, 124행, 148행에는 GitHub Actions 수동 실행(`workflow_dispatch`) 시 `chunk` 옵션(`1/3` 등)을 선택할 수 있다고 안내되어 있으나, 실제 `.github/workflows/daily_batch.yml`에는 `mode`와 `max_stocks` 두 가지만 정의되어 있습니다.
* **구체적인 수정 제안**:
  * `.github/workflows/daily_batch.yml`에 `chunk` input을 추가(또는 GitHub App 워크플로우 파일 푸시 권한 제한 시 `README.md`의 GitHub Actions 실행 안내를 현행 `daily_batch.yml` 스펙과 일치하도록 정리)하십시오.

---

### ✅ 2.2 해결 완료된 이슈 히스토리
* **[ISSUE-001] `[해결 완료]` 웹 대시보드(`index.html`) 기준 거래일이 `2026-08-20`으로 절단 표시되던 현상**
* **[ISSUE-002] `[해결 완료]` 초반 1~285번 대형주 누락 및 `is_quarterly_rebuild_due` 247종목 유니버스 고착화 결함 (`STRATEGY.md` 수정 1)**
  * `stocks_master`에 시총 700억 이상 보통주 **1,463종목** 일괄 선등록 및 `avg_val_20d_eok < 20.0` 사전 차단 제거 확인 완료.
* **[ISSUE-003] `[해결 완료]` `daily_chart` 60일 절단 및 `daily_investor_supply` 25일 단일 호출 제한 결함 (`STRATEGY.md` 수정 2 & 3)**
  * `fetch_daily_chart()` 500영업일 전수 Upsert 및 `fetch_investor_supply()` 역순 날짜 슬라이딩(`todt = oldest_date - 1일`, 최대 25페이지) 연속조회로 종목당 **500영업일** 적재 확인 완료.
* **[ISSUE-004] `[해결 완료]` GitHub Actions 타임아웃 45분 제한 상향 (`STRATEGY.md` 수정 5)**
  * `.github/workflows/daily_batch.yml`의 `timeout-minutes: 360`(6시간) 상향 반영 확인 완료.
* **[ISSUE-005] `[해결 완료]` 1,463종목 마스터 3페이지 병렬 로드 및 최근 윈도우 인덱스 쿼리 구조 적용 (`STRATEGY.md` 수정 6)**
