# 🎯 LS 수급·차트 스크리너 종목 발굴 전략 명세서 (`STRATEGY.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[전략 개발]` 전담 대화창**에서 관리하는 **단일 진실 공급원(Single Source of Truth, SSOT)** 전략 설계서입니다.
> * `[전략 개발]` 대화창은 실제 애플리케이션 코드([`run_daily_screener.py`](file:///home/antigravity/ls-stock-screener/run_daily_screener.py), [`index.html`](file:///home/antigravity/ls-stock-screener/index.html) 등)나 [`README.md`](file:///home/antigravity/ls-stock-screener/README.md), [`TEST_REPORT.md`](file:///home/antigravity/ls-stock-screener/TEST_REPORT.md)를 직접 수정하지 않으며, 오직 본 `STRATEGY.md`에만 **전략 검증을 위한 데이터 요건, 발굴 전략 수식, 필터 조건**을 기록하고 Git 커밋/푸시합니다.
> * **`[프로그램 개발 및 수정]` 대화창**은 본 `STRATEGY.md`의 최신 명세를 읽고 데이터 수집기·백엔드·프론트엔드·DB 적재를 구현합니다.
> * **`[검증 및 테스트]` 대화창**은 `STRATEGY.md`에 정의된 데이터 적재 기간, 수식, 필터 조건이 오차 없이 구현되었는지 검증합니다.

---

## 🚨 0. [긴급/최우선] 전략 검증을 위한 과거 데이터 확충 요구사항 (Data Backfill Specification)

### 0.1 현행 DB 적재 현황 및 문제점 진단
현재 Supabase DB(`stocks_master` 247종목 기준)에 보관된 데이터 기간은 다음과 같으며, **전략 백테스트 및 시계열 검증에 턱없이 부족한 상태**입니다:

| 테이블명 | 현재 보관 일수 (종목당) | 실제 적재 기간 | 총 행(Row) 수 | 전략 검증상 문제점 |
| :--- | :---: | :---: | :---: | :--- |
| **`daily_chart`** (일봉·EMA) | **60영업일** (약 3개월) | `2026-08-13` ~ `2026-11-11` | 14,710건 | `EMA 120`, `EMA 240`의 초기 수렴(Warm-up) 부족 및 3개월 이전 차트 패턴 검증 불가 |
| **`daily_investor_supply`** (수급) | **25영업일** (약 1개월) | `2026-10-07` ~ `2026-11-11` | 6,175건 | **태광(`023160`)의 `2026-08-25` 사례 등 10월 7일 이전의 모든 기관 수급 데이터 결측**, 최근 1개월(하락장) 편향으로 통계적 유의성 확보 불가 |

### 0.2 원인 분석 (`run_daily_screener.py` 구조적 제약)
1. **일일 모드(`daily`) 슬라이싱 제한**:
   * `daily_chart` 적재 시 `enriched_charts[-60:]`으로 최근 60영업일만 남기고 절단하며, `supply_start`를 `len(enriched_charts) - 25`로 지정해 최근 25영업일만 요청함.
2. **LS증권 API `t1717`(수급) 1회 호출당 반환 건수 제한 (Pagination 미구현)**:
   * `t1717` TR은 `fromdt ~ todt` 기간을 길게 요청하더라도 **1회 호출 시 최대 약 25~30영업일 분량만 반환**함.
   * 현재 `fetch_investor_supply()`는 연속조회(`tr_cont="Y"` 및 `cts_date` 갱신 또는 구간 분할 호출) 없이 1회만 호출하므로, `--mode backfill`을 실행하더라도 수급 데이터는 최근 25~30일치만 적재됨.

### 0.3 `[프로그램 개발 및 수정]` 대화창 구현 요청 명세 (Data Expansion Spec)
전략 개발 및 과거 사례(태광 `2026-08-25` 등 포함) 전수 검증을 위해 아래 데이터 확충을 최우선으로 구현·적재 요청합니다:

1. **보관 및 적재 목표 기간**:
   * **최소 최근 1년(약 250영업일) ~ 권장 2년(약 500영업일)**의 **`daily_chart`** 및 **`daily_investor_supply`** 데이터를 1:1 거래일 매칭 상태로 Supabase DB에 구축할 것 (최소한 `2026-01-01 ~ 현재` 또는 최근 250~500영업일 전체).
2. **`t8410` (일봉 차트) 수집 및 EMA 정밀도 개선**:
   * `EMA 240`의 정확한 수렴을 위해 일봉 조회 시 충분한 과거 구간(최소 360~500영업일, 필요 시 `cts_date` 연속조회 활용)을 조회하여 EMA(5·20·60·120·240)를 계산한 뒤 DB에 Upsert할 것.
3. **`t1717` (투자주체별 수급) 연속조회(Pagination / 구간 분할) 구현**:
   * `fetch_investor_supply()`에서 단일 호출(25일)에 그치지 않고, 목표 시작일(`start_date`)까지 도달할 때까지 **날짜 구간 분할(예: 25~30영업일 단위 역순 슬라이딩) 또는 `t1717` 연속조회(`tr_cont="Y"`, `cts_date`)**를 반복 호출하여 `daily_chart`의 거래일과 동일한 기간의 수급 데이터를 모두 적재할 것.
   * **필수 검증 포인트**: 적재 완료 후 **태광(`023160`)의 `2026-08-25` 전후(`2026-08-13 ~ 2026-09-10`) `daily_investor_supply` 수급 데이터**가 DB에 정상 조회되어야 함.
4. **평일 일일 배치(`--mode daily`) 증분 유지**:
   * 최초 Backfill 완료 후, 평일 저녁 21:05 일일 배치에서는 기존 과거 데이터를 삭제/절단하지 않고 최근 증분만 빠르게 Upsert하여 DB에 최소 1~2년치 히스토리가 상시 유지되도록 할 것.

---

## 1. 현행 베이스라인 전략 명세 (Strategy v1.0 — 기적용)

### 1.1 분석 대상 유니버스 (Universe Filtering)
* **대상 시장**: 코스피(`KOSPI`) + 코스닥(`KOSDAQ`) 통합 보통주 (`t8436` 마스터 기준)
* **제외 대상**:
  * ETF / ETN / ELW (`etfgubun != "0"` 또는 브랜드 접두어)
  * 스팩(`SPAC`, `기업인수목적`), 리츠(`리츠`, `맥쿼리인프라`), 인버스/레버리지/선물/채권형
  * 우선주 (종목코드 끝자리 `!= '0'` 또는 종목명 `우`, `우B`, `우C` 종료)
* **정량 기준**:
  * 시가총액: $\text{market\_cap\_eok} \ge 700\text{ (억 원)}$
  * 유동성: 최근 20영업일 평균 거래대금 $\text{avg\_val\_20d\_eok} \ge 20\text{ (억 원)}$

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

> **모티브 사례 (Reference Cases)**:
> 1. **대한유화 (`006650`, `2026-11-03`)**: 10거래일간 하락 추세(5일선 하회 및 `EMA5 < EMA20 < EMA60 < EMA120` 역배열) & 직전 5일 연속 순수기관 순매도(`-29,485주`) 이후, `11/03` 당일 거래량 3.77배 급증과 함께 **순수기관 첫 대량 순매수(`+34,534주`, 거래량 비중 `31.57%`, `30.4억 원`)**가 유입되며 `+8.17%` 양봉으로 5일선·20일선을 동시 돌파 → 이후 `+10.4%` 추가 상승.
> 2. **태광 (`023160`, `2026-08-25` 및 `2026-11-09 ~ 11/11`)**: `08/13 ~ 08/24` 7거래일 연속 종가가 5일선(`EMA5`) 아래에서 하락한 뒤, `08/25` 기관 첫 유의미한 매수 유입과 함께 `+4.44%` 양봉으로 5일선을 첫 상향 돌파 → 직후 3거래일 만에 `+19.0%`, 이후 `+34.2%` 대시세 분출.

### 2.1 전략 핵심 조건 수식 (Draft Formula — Backfill 완료 후 파라미터 최종 확정 예정)
기준일 $T$에 대하여 다음 4가지 조건을 동시에 만족하는 종목을 포착합니다:

1. **사전 하락 추세 및 5일선 이탈 조건 (Prior Downtrend & Below EMA 5)**:
   * 직전일($T-1$) 기준 단기 이평선 역배열:
     $$\text{EMA}_{5, T-1} < \text{EMA}_{20, T-1}$$
   * 직전 5거래일($T-5 \sim T-1$) 중 **최소 3거래일 이상(또는 직전 3거래일 연속) 종가가 5일 지수이동평균선 아래**에 위치:
     $$\sum_{k=1}^{5} \mathbb{I}\left(\text{Close}_{T-k} < \text{EMA}_{5, T-k}\right) \ge 3$$
2. **기관 수급 공백 후 '첫 의미 있는 매수' 유입 조건 (First Meaningful Institutional Buy)**:
   * 직전 $M$거래일($M=3\text{ 또는 }5$, $T-M \sim T-1$) 동안 순수기관 누적 순매수가 $\le 0$(순매도)이거나, 직전 $M$거래일 각각의 일별 순수기관 거래량 비중이 모두 $10\%$ 미만:
     $$\left(\sum_{k=1}^{3} \text{real\_inst\_vol}_{T-k} \le 0\right) \quad \text{OR} \quad \left(\max_{1 \le k \le 3} \text{inst\_vol\_ratio}_{T-k} < 10.0\%\right)$$
   * 당일($T$) **순수기관 거래량 대비 순매수 비중** 및 **순매수 금액**이 임계값을 돌파:
     $$\text{inst\_vol\_ratio}_T \ge 20.0\% \quad (\text{기본 탐색 범위: } 15.0\% \sim 25.0\%)$$
     $$\text{real\_inst\_amt}_T \ge 500\text{ (백만 원, 즉 5억 원 이상)}$$
3. **당일 추세 반전 캔들 및 5일선 회복 (Bullish Reversal & EMA 5 Recovery)**:
   * 당일 양봉 마감($\text{Close}_T > \text{Open}_T$) 및 종가의 **5일선 상향 회복($\text{Close}_T \ge \text{EMA}_{5, T}$)**
   * 당일 과열 추격매수 방지를 위한 적정 등락률 필터:
     $$+2.0\% \le \text{change\_rate}_T \le +12.0\%$$
4. **거래량 활성화 필터 (Volume Expansion)**:
   * 당일 거래량이 직전 5영업일 평균 거래량 대비 유의미하게 증가:
     $$\text{Volume}_T \ge 1.2 \times \left(\frac{1}{5}\sum_{k=1}^{5} \text{Volume}_{T-k}\right)$$

> 📌 **다음 단계**: `0절`의 과거 데이터 확충(최소 1~2년치 차트·수급 Backfill)이 완료되면, 태광(`2026-08-25`)의 실제 수급 수치를 대조 확인하고 전체 확장 표본에서 위 파라미터($M$, 기관 비중 임계값, 등락률 상한, 거래량 배율)를 정밀 최적화하여 최종 확정합니다.
