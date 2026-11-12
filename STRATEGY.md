# 🎯 LS 수급·차트 스크리너 종목 발굴 전략 명세서 (`STRATEGY.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[전략 개발]` 전담 대화창**에서 관리하는 **단일 진실 공급원(Single Source of Truth, SSOT)** 전략 설계서 및 데이터/시스템 요구사항 명세서입니다.
> * `[전략 개발]` 대화창은 실제 애플리케이션 코드([`run_daily_screener.py`](file:///home/antigravity/ls-stock-screener/run_daily_screener.py), [`index.html`](file:///home/antigravity/ls-stock-screener/index.html), [`.github/workflows/daily_batch.yml`](file:///home/antigravity/ls-stock-screener/.github/workflows/daily_batch.yml) 등)나 [`README.md`](file:///home/antigravity/ls-stock-screener/README.md), [`TEST_REPORT.md`](file:///home/antigravity/ls-stock-screener/TEST_REPORT.md)를 직접 수정하지 않으며, 오직 본 `STRATEGY.md`에만 기록하고 Git 커밋/푸시합니다.
> * **`[프로그램 개발 및 수정]` 대화창**은 작업 시작 전 `git pull` 후 본 `STRATEGY.md`를 읽고 아래 **0절의 필수 수정 사항**을 모두 구현합니다.
> * **`[검증 및 테스트]` 대화창**은 본 `STRATEGY.md`의 **0.4절 검증 및 테스트 항목(AC-1 ~ AC-6)**을 실행하여 `TEST_REPORT.md`에 기록합니다.

---

## 🚨 0. [최우선 아키텍처 수정 및 데이터 구축 요청서] 시총 700억 이상 전 종목(약 1,477종목) × 2년치(500영업일) 차트·수급 완비

### 0.1 현행 시스템의 4대 치명적 결함 진단 (원인 규명 완료)

직전 GitHub Actions 배치 로그(`43054796030`) 및 코드 전수 분석 결과, 원래 구축되어야 할 **코스피·코스닥 시가총액 700억 이상 보통주 전수(`1,477종목`)의 2년치 데이터** 대신 **불완전한 `247종목 × 25일(수급)/60일(차트)`**만 적재된 원인은 다음 4가지입니다:

1. **[결함 1] 초반 1~285번 최상위 대형주 285개 통째 누락**:
   * 첫 배치 실행 초반(`16:08 ~ 16:27`) Supabase RLS 해제 전 발생한 `HTTP 401 Unauthorized` 에러로 인해, 거래대금·시가총액 최상위 **1번~285번 종목(삼성전자, SK하이닉스, 현대차, 셀트리온, 한화에어로스페이스, 알테오젠, 에코프로 등 285개 핵심 종목)**이 전부 건너뛰어짐 (`Max mcap`이 4.7조 원에서 끊긴 이유).
2. **[결함 2] 603번째 후보에서 GitHub Actions `45분 타임아웃` 강제 종료로 뒤쪽 874개 종목 누락**:
   * `.github/workflows/daily_batch.yml`의 `timeout-minutes: 45` 제한 때문에 전체 1,477개 후보 중 603번째까지만 처리되고 작업이 강제 취소(`cancelled`)되어 **604번~1,477번(874개 종목)이 미처리**됨.
3. **[결함 3] 수집 단계의 `20일 평균 거래대금 < 20억` 사전 차단 및 `247종목 유니버스 고착화` 버그**:
   * `run_daily_screener.py` 733행에서 `avg_val_20d_eok < 20.0`인 종목을 DB 적재 전에 버리는 바람에, 평소 거래가 줄어들어 바닥을 다지다가 기관 첫 수급이 유입되는 종목들이 DB에서 영구 누락됨.
   * 또한 `is_quarterly_rebuild_due()`가 **"DB에 1종목이라도 있으면 유니버스 구축 완료"**로 판정하여, 사고로 중단된 247종목만 전체 유니버스인 것처럼 고정됨.
4. **[결함 4] 수급(`t1717`) 25일 단일 호출 제한 및 차트(`t8410`) 60일 절단 저장**:
   * `t1717` TR은 1회 호출 시 최대 25~30영업일만 반환하는데 연속조회(Pagination)가 구현되지 않아 수급 데이터가 `2026-10-07 ~ 2026-11-11`(25영업일)만 저장되었고, 차트는 `enriched_charts[-60:]` 슬라이싱으로 60영업일만 저장됨.

---

### 0.2 `[프로그램 개발 및 수정]` 대화창 필수 수정 명세 ( 총 6개 항목 )

`[프로그램 개발 및 수정]` 대화창에서는 `run_daily_screener.py`, `supabase_schema.sql`, `index.html`, `.github/workflows/daily_batch.yml`에 대해 아래 6가지 수정을 반드시 수행해 주십시오.

#### 🛠️ 수정 1: 유니버스 기준 변경 — "시가총액 700억 이상 보통주 전수(약 1,477종목) 100% 적재"
* **대상**: `run_daily_screener.py` (유니버스 판정 및 수집 루프)
* **요구사항**:
  1. 코스피(`KOSPI`) + 코스닥(`KOSDAQ`)에서 **ETF, ETN, ELW, 스팩(SPAC), 우선주, 리츠, 인버스/레버리지만 제외**하고, **시가총액 700억 원 이상(`market_cap_eok >= 700.0`)인 모든 보통주(약 1,450~1,500종목 전수)**를 예외 없이 DB 구축 대상(`is_universe = True`)으로 편입합니다.
  2. **수집 단계의 거래대금 사전 차단 제거**: `run_daily_screener.py` 733행의 `if avg_val_20d_eok < 20.0: continue` 코드를 **제거**하십시오. `avg_val_20d_eok`(20일 평균 거래대금) 값은 계산하여 `stocks_master`에 저장하되, 거래대금 조건을 이유로 종목 수집을 건너뛰지 마십시오. (거래대금 필터는 웹 대시보드/전략 조회 시에만 옵션으로 사용)
  3. **불완전 유니버스 고착화 방지 (`is_quarterly_rebuild_due` 수정)**:
     * 현재 `stocks_master`의 `is_universe=True` 종목 수가 **1,200종목 미만**(현재 247종목)이면 **"미완성 초기 상태"**로 판정하여 자동으로 `t1444` 전수 시가총액 추출(`fetch_market_cap_above_threshold`)을 다시 수행하도록 수정하십시오.

#### 🛠️ 수정 2: `daily_chart` (일봉 및 5개 EMA) 2년치(500영업일) 전수 적재
* **대상**: `run_daily_screener.py` (`fetch_daily_chart` 및 Upsert 로직)
* **요구사항**:
  1. `t8410` 호출 시 `qrycnt = 500`, `start_date = (today - 760일)`, `end_date = today`, `sujung = "Y"`로 호출하여 **종목당 최근 2년치(약 480~500영업일, 신규 상장주는 상장일 이후 전 기간)** 일봉을 가져옵니다. (만약 `t8410` 1회 호출로 500건이 다 오지 않는 경우 `cts_date` / `tr_cont="Y"` 또는 구간 분할로 500영업일을 채울 것)
  2. 500영업일 전체 시계열로 `ema_5`, `ema_20`, `ema_60`, `ema_120`, `ema_240`을 계산합니다.
  3. **`enriched_charts[-60:]` 절단 로직을 폐기**하고:
     * `backfill` 모드(또는 해당 종목의 DB 내 차트 행 수가 400건 미만인 경우): **500영업일 전체를 `daily_chart`에 Upsert**합니다.
     * 이미 2년치(450건 이상)가 DB에 적재된 종목에 대해 평일 `daily` 모드를 실행할 때: 과거 데이터를 지우지 않고 **최근 10~30영업일 분량만 빠르게 Upsert**하여 DB에 2년치 히스토리가 영구 보존되도록 합니다.

#### 🛠️ 수정 3: `daily_investor_supply` (수급) 2년치(500영업일) 역순 슬라이딩 연속 수집
* **대상**: `run_daily_screener.py` (`fetch_investor_supply`)
* **요구사항**:
  1. LS증권 `t1717` TR은 1회 호출당 최신일(`todt`)부터 과거 약 25~30영업일만 반환합니다.
  2. 따라서 **2년치(약 500영업일) 수급 데이터를 모두 수집하기 위해 역순 날짜 슬라이딩 루프(Pagination)**를 구현하십시오:
     * `curr_todt = end_date`에서 시작하여 `t1717` 호출 → 응답된 행들 중 가장 과거 일자(`oldest_date`) 확인
     * `oldest_date > target_start_date`이고 새로 추가된 행이 존재하면, `curr_todt = (oldest_date - 1일)`로 갱신하여 반복 호출 (종목당 약 17~20회 호출이면 2년치 500영업일 완비)
     * 수집된 모든 일자에 대해 `daily_chart`의 동일 `trade_date` 거래량(`vol_by_date`)·종가(`close_by_date`)를 1:1 매칭하여 `real_inst_vol`, `real_inst_amt`, `inst_vol_ratio`, `frg_vol_ratio` 및 6대 세부주체 데이터를 계산 후 일괄 Upsert합니다.
  3. **평일 `daily` 모드 최적화**:
     * 이미 DB에 해당 종목의 2년치 수급 데이터(예: 400영업일 이상)가 적재되어 있는 경우, 평일 `daily` 모드에서는 `t1717`을 **단 1회(최근 25영업일)**만 호출하여 Upsert함으로써 일일 배치 속도를 빠르게 유지합니다.
     * 반대로 DB에 해당 종목의 수급 데이터가 부족한 경우(미적재 신규 종목 등) 자동으로 2년치 전체를 백필합니다.

#### 🛠️ 수정 4: 대량 적재(1,477종목 × 2년치) 중단 방지 — 이어받기(Resume) 및 분할(Chunk) CLI 옵션 추가
* **대상**: `run_daily_screener.py` CLI 인자 및 루프 제어
* **배경**: 1,477종목 × `t1717` 18회 호출 = 약 26,500회 API 호출이 필요하며, LS증권 API Rate Limit(초당 약 1.5~2회) 준수 시 전체 백필에 약 4~5시간이 소요됩니다.
* **요구사항**:
  1. **자동 이어받기 (`--skip-existing` / 스마트 Resume)**:
     * `backfill` 실행 시, 이미 DB(`daily_chart` 및 `daily_investor_supply`)에 최근 거래일(`2026-11-11`)까지 포함하여 **충분한 과거 데이터(예: 400영업일 이상, 또는 상장 이후 전 기간)가 적재되어 있는 종목은 API 재호출 없이 즉시 건너뛰는(Skip) 로직**을 기본 탑재하십시오.
     * 이렇게 하면 설령 작업이 중간에 타임아웃되더라도 재실행 시 이미 완료된 종목을 건너뛰고 나머지 종목부터 즉시 이어서 100% 완주할 수 있습니다.
  2. **구간 분할 옵션 (`--start-idx`, `--end-idx` 또는 `--chunk`) 지원**:
     * 필요 시 전체 후보 리스트에서 특정 순번 구간(예: `--start-idx 0 --end-idx 500`)만 지정해 실행할 수 있는 CLI 옵션을 추가하십시오.
  3. **배치 Upsert 단위를 500건 단위 청크로 안전하게 전송**하여 Supabase HTTP Payload 에러나 타임아웃이 발생하지 않도록 처리하십시오.

#### 🛠️ 수정 5: GitHub Actions 워크플로우(`.github/workflows/daily_batch.yml`) 타임아웃 및 입력 개선
* **대상**: `.github/workflows/daily_batch.yml`
* **요구사항**:
  1. `timeout-minutes: 45`를 GitHub Actions 단일 Job 최대치인 **`timeout-minutes: 360` (6시간)**으로 상향 수정하십시오.
  2. `workflow_dispatch` 수동 실행 입력값(`inputs`)에서 `mode` 선택지로 `backfill`, `daily`, `universe`, `verify`를 유지하고, 필요 시 구간 분할/이어받기가 원활히 동작하도록 구성하십시오.

#### 🛠️ 수정 6: 대용량 DB(약 70만 행) 환경에서의 웹 대시보드(`index.html`) 및 검증 쿼리 최적화
* **대상**: `index.html`, `supabase_schema.sql`, `run_daily_screener.py --mode verify`
* **배경**: 1,477종목 × 500영업일 적재 시 `daily_chart`와 `daily_investor_supply`는 각각 **약 70만 행(Row)**이 됩니다.
* **요구사항**:
  1. `index.html`에서 페이지 로드 시 70만 행 전체를 스캔하지 않도록, 최신 거래일(`trade_date`) 기준으로 **최근 $N$영업일(예: 최근 10~15영업일치, `trade_date >= 최근기준일`)만 필터링 조회**하여 1,477종목 전체의 당일/3일/5일/10일 누적 수급 스크리닝이 누락 없이 즉시 계산되도록 페이지네이션/쿼리 조건을 최적화하십시오.
  2. 종목 클릭 시 우측 상세 차트는 해당 종목(`shcode=eq.XXXXXX`)의 최근 120~240영업일 데이터를 온디맨드 조회하여 캔들과 EMA(5·20·60·120·240)를 렌더링하도록 유지하십시오.

---

### 0.3 사용자(User)께서 GitHub에서 확인·조치하실 사항 안내

1. **GitHub Actions 권한으로 인한 `.github/workflows/daily_batch.yml` 푸시 제한 여부 확인**:
   * `[프로그램 개발 및 수정]` 대화창에서 코드 수정 후 `git push`를 할 때, 만약 GitHub 보안 정책상 워크플로우 파일(`.github/workflows/daily_batch.yml`) 수정 푸시가 거부(`refusing to allow a GitHub App to create or update workflow`)된다면, `[프로그램 개발 및 수정]` 창이 안내드리는 대로 GitHub 웹페이지에서 `.github/workflows/daily_batch.yml`의 **`timeout-minutes: 45` 한 줄만 `timeout-minutes: 360`으로 수정(Commit)**해 주시면 됩니다. (푸시가 정상 통과되면 직접 수정하실 필요 없습니다.)
2. **GitHub Actions에서 `backfill` 워크플로우 실행**:
   * `[프로그램 개발 및 수정]` 창이 코드 푸시를 완료하면, GitHub 저장소의 **Actions 탭 → `Daily LS Stock Supply & Chart Batch Update` → `Run workflow`** 버튼을 눌러 **`mode: backfill`**, **`max_stocks: 0`**으로 실행해 주십시오.

---

### 0.4 `[검증 및 테스트]` 대화창 확인용 합격 기준 (Acceptance Criteria, AC-1 ~ AC-6)

`[검증 및 테스트]` 대화창에서는 개발 및 백필 완료 후 아래 **6가지 검증 항목**을 테스트하고 결과를 `TEST_REPORT.md`에 상세히 기록해 주십시오:

| 검증 코드 | 검증 항목 | 합격 기준 (PASS 조건) |
| :---: | :--- | :--- |
| **AC-1** | **시총 700억 이상 보통주 전수 유니버스 구축 확인** | • `stocks_master` 내 `is_universe = True` 종목 수가 기존 247개가 아니라 **코스피·코스닥 시총 ≥ 700억 보통주 전수(약 1,400 ~ 1,550종목)**일 것<br/>• ETF/ETN/ELW/스팩/우선주/리츠 혼입 `0건`일 것<br/>• 기존 `401 에러`로 누락되었던 대형주(**삼성전자 `005930`, SK하이닉스 `000660`, 현대차 `005380`, 한화에어로스페이스 `012450`, 알테오젠 `196170`**)가 모두 포함되어 있을 것 |
| **AC-2** | **수집 단계의 거래대금 20억 미만 차단 해제 확인** | • 시가총액은 700억 이상이지만 최근 20일 평균 거래대금이 20억 미만(`avg_val_20d_eok < 20.0`)인 중소형 보통주들도 누락 없이 `stocks_master`, `daily_chart`, `daily_investor_supply`에 적재되어 있을 것 |
| **AC-3** | **`daily_chart` 2년치(약 500영업일) 적재 및 EMA 정합성** | • 상장 후 2년 이상 경과한 종목들의 `daily_chart` 보유 일수가 **약 470~500영업일(`2024-11` ~ `2026-11-11`)**일 것<br/>• 500영업일 시계열 기반으로 계산된 `ema_5`, `ema_20`, `ema_60`, `ema_120`, `ema_240` 수식 오차가 `0건`일 것 |
| **AC-4** | **`daily_investor_supply` 2년치(약 500영업일) 연속 적재 및 1:1 매칭** | • `t1717` 역순 연속 수집을 통해 종목당 `daily_investor_supply` 보유 일수가 기존 25일에서 **약 470~500영업일(`2024-11` ~ `2026-11-11`)**로 확장되었을 것<br/>• `daily_chart`와 동일 `(shcode, trade_date)` 1:1 매칭 및 순수기관 6대 주체 합산(`real_inst_vol`, `inst_vol_ratio`) 오차가 `0건`일 것 |
| **AC-5** | **핵심 레퍼런스 종목(`태광`, `대한유화`) 과거 데이터 실증 확인** | • **태광(`023160`)의 `2026-08-25`**(및 `2026-08-01 ~ 2026-09-15` 전 구간)의 `daily_chart` 및 `daily_investor_supply` 수급 데이터가 결측(`NULL`) 없이 조회될 것<br/>• **대한유화(`006650`)의 `2026-11-03`** 및 최근 2년치 차트·수급 데이터가 결측 없이 조회될 것 |
| **AC-6** | **웹 대시보드(`index.html`) 1,477종목 실시간 스크리닝 동작 확인** | • 1,477종목 × 500일 대용량 적재 상태에서도 `index.html`이 최신 거래일(`2026-11-11`) 기준 전 종목(1,477종목) 대상 당일/3일/5일/10일 스크리닝을 누락이나 페이지 절단 없이 정상 렌더링할 것 |

---

## 1. 현행 베이스라인 전략 명세 (Strategy v1.0 — 기적용)

### 1.1 분석 대상 유니버스 (Universe Definition)
* **DB 수집 유니버스 (모집단)**: 코스피(`KOSPI`) + 코스닥(`KOSDAQ`) 통합 보통주 중 **시가총액 700억 원 이상 전 종목 (약 1,477종목)**
  * 제외 대상: ETF / ETN / ELW, 스팩(`SPAC`, `기업인수목적`), 리츠(`리츠`, `맥쿼리인프라`), 인버스/레버리지/선물/채권형, 우선주
* **스크리닝 시 유동성 옵션**: 웹 대시보드 및 전략 실행 시 최소 거래대금 필터는 사용자가 선택적으로 조절 가능.

### 1.2 핵심 수급 정의: 순수 기관 (`real_inst`)
* 단기 차익거래 및 유동성공급자(LP) 물량으로 인해 추세 왜곡이 심한 **금융투자(`fn_inv`, `tjj0001`)를 제외**합니다.
* **순수 기관 합산 수식**:
  $$\text{real\_inst\_vol} = \text{itc\_vol}(\text{투신}) + \text{pef\_vol}(\text{사모펀드}) + \text{pen\_vol}(\text{연기금}) + \text{ins\_vol}(\text{보험}) + \text{etc\_fin\_vol}(\text{기타금융}) + \text{bank\_vol}(\text{은행})$$
  $$\text{real\_inst\_amt} = \text{itc\_amt} + \text{pef\_amt} + \text{pen\_amt} + \text{ins\_amt} + \text{etc\_fin\_amt} + \text{bank\_amt}$$

### 1.3 핵심 포착 및 정렬 지표: 기간 거래량 대비 순매수 비중 (%)
* 동일 거래일(`trade_date` 1:1 매칭) 기준 **기간 누적 거래량 대비 순매수 수량 비중(%)**:
  $$\text{inst\_vol\_ratio}_{N\text{d}}(\%) = \left( \frac{\sum_{t=1}^{N} \text{real\_inst\_vol}_t}{\sum_{t=1}^{N} \text{volume}_t} \right) \times 100$$

---

## 2. 신규 개발 전략 후보 명세 (Strategy v2.0 — 하락 추세 5일선 이탈 후 기관 첫 매수 유입 전략)

> 📌 **상태**: `0절`의 **시총 700억 이상 전 종목(약 1,477종목) × 2년치(500영업일) 차트·수급 데이터 구축 완료 후**, 태광(`2026-08-25`)과 대한유화(`2026-11-03`)를 포함한 1,477종목 × 2년 전수 백테스트를 통해 최종 파라미터를 확정할 예정입니다.

### 2.1 전략 모티브 (Reference Cases)
1. **대한유화 (`006650`, `2026-11-03`)**:
   * 10거래일간 하락 추세(5일선 하회 및 `EMA5 < EMA20 < EMA60 < EMA120` 역배열) 및 직전 5일 연속 순수기관 순매도(`-29,485주`) 이후,
   * `11/03` 당일 거래량 3.77배 급증과 함께 **순수기관 첫 대량 순매수(`+34,534주`, 거래량 비중 `31.57%`, `30.4억 원`)**가 유입되며 `+8.17%` 양봉으로 5일선·20일선을 동시 돌파 → 이후 `+10.4%` 추가 상승.
2. **태광 (`023160`, `2026-08-25`)**:
   * `08/13 ~ 08/24` 7거래일 연속 종가가 5일선(`EMA5`) 아래에서 하락 추세를 이어간 뒤,
   * `08/25` 기관의 의미 있는 첫 매수 유입과 함께 `+4.44%` 양봉으로 5일선을 첫 상향 돌파 → 직후 3거래일 만에 `+19.0%`, 이후 `+34.2%` 급등.

### 2.2 1차 설계 수식 (1,477종목 × 2년치 데이터 백테스트 검증 대상)
기준일 $T$에 대하여 다음 4가지 조건을 충족하는 종목 발굴:
1. **사전 하락 추세 (5일선 이탈 지속)**:
   * $\text{EMA}_{5, T-1} < \text{EMA}_{20, T-1}$ 이고, 직전 5거래일($T-5 \sim T-1$) 중 최소 3일 이상 $\text{Close}_{T-k} < \text{EMA}_{5, T-k}$
2. **기관 수급 공백 후 첫 의미 있는 매수 전환**:
   * 직전 $M$거래일($M=3\text{ 또는 }5$) 동안 순수기관 누적 순매도($\sum_{k=1}^{M} \text{real\_inst\_vol}_{T-k} \le 0$) 또는 일별 순수기관 비중 모두 $10\%$ 미만
   * 당일($T$) $\text{inst\_vol\_ratio}_T \ge 20.0\%$ (탐색 범위: $15\% \sim 25\%$) 및 $\text{real\_inst\_amt}_T \ge 500\text{ (백만 원)}$
3. **당일 추세 반전 양봉 및 5일선 회복**:
   * $\text{Close}_T > \text{Open}_T$, $\text{Close}_T \ge \text{EMA}_{5, T}$, 적정 등락률 $+2.0\% \le \text{change\_rate}_T \le +12.0\%$
4. **거래량 증가 동반**:
   * $\text{Volume}_T \ge 1.2 \times \left(\frac{1}{5}\sum_{k=1}^{5} \text{Volume}_{T-k}\right)$
