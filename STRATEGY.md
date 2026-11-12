# 🎯 LS 수급·차트 스크리너 종목 발굴 전략 명세서 (`STRATEGY.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[전략 개발]` 전담 대화창**에서 관리하는 **단일 진실 공급원(Single Source of Truth, SSOT)** 전략 설계서입니다.
> * `[전략 개발]` 대화창은 실제 애플리케이션 코드([`run_daily_screener.py`](file:///home/antigravity/ls-stock-screener/run_daily_screener.py), [`index.html`](file:///home/antigravity/ls-stock-screener/index.html) 등)를 직접 수정하지 않으며, Supabase에 적재된 실데이터를 기반으로 가설을 검증한 뒤 **전략 수식, 필터 조건, 스코어링 로직, UI/알림 요구사항**을 본 `STRATEGY.md`에 기록하고 Git 커밋/푸시합니다.
> * **`[프로그램 개발 및 수정]` 대화창**은 본 `STRATEGY.md`의 최신 명세를 읽고 백엔드/프론트엔드/DB 스키마를 구현합니다.
> * **`[검증 및 테스트]` 대화창**은 `STRATEGY.md`에 정의된 수식과 필터 조건이 오차 없이 구현되었는지 검증합니다.

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
* 단기 차익거래 및 유동성공급자(LP) 물량으로 인해 추세 왜곡이 심한 **금융투자(`fn_inv`, `tjj0002`)를 제외**합니다.
* **순수 기관 합산 수식**:
  $$\text{real\_inst\_vol} = \text{itc\_vol}(\text{투신}) + \text{pef\_vol}(\text{사모펀드}) + \text{pen\_vol}(\text{연기금}) + \text{ins\_vol}(\text{보험}) + \text{etc\_fin\_vol}(\text{기타금융}) + \text{bank\_vol}(\text{은행})$$
  $$\text{real\_inst\_amt} = \text{itc\_amt} + \text{pef\_amt} + \text{pen\_amt} + \text{ins\_amt} + \text{etc\_fin\_amt} + \text{bank\_amt}$$

### 1.3 핵심 포착 및 정렬 지표: 기간 거래량 대비 순매수 비중 (%)
* 시가총액 및 거래대금 규모 차이에 따른 단순 순매수 금액 왜곡을 제거하기 위해, 동일 거래일(`trade_date` 1:1 매칭) 기준 **기간 누적 거래량 대비 순매수 수량 비중(%)**을 산출합니다:
  $$\text{inst\_vol\_ratio}_{N\text{d}}(\%) = \left( \frac{\sum_{t=1}^{N} \text{real\_inst\_vol}_t}{\sum_{t=1}^{N} \text{volume}_t} \right) \times 100$$
* **기본 포착 임계값**: $\text{inst\_vol\_ratio}_{N\text{d}} \ge 10.0\%$
* **누적 기간($N$)**: `1일(당일)`, `3일`, `5일`, `10일`, 사용자 지정 `N일`

### 1.4 기술적 분석 지표 (EMA & 배열/이격 필터)
* 수정주가(`sujung="Y"`) 일봉 종가 기준 지수이동평균($\alpha = \frac{2}{\text{span}+1}$):
  * 단기: `ema_5`, `ema_20`
  * 중기: `ema_60`, `ema_120`
  * 장기: `ema_240`
* **기본 제공 차트 필터**:
  * `above_20`: $\text{close} \ge \text{ema\_20}$
  * `align_short` (단기 정배열): $\text{ema\_5} > \text{ema\_20} > \text{ema\_60}$
  * `align_mid` (중장기 정배열): $\text{ema\_20} > \text{ema\_60} > \text{ema\_120}$
  * `align_full` (완전 정배열): $\text{ema\_5} > \text{ema\_20} > \text{ema\_60} > \text{ema\_120} > \text{ema\_240}$
  * `pullback_20` (20일 EMA 눌림목): $-2.0\% \le \left(\frac{\text{close}}{\text{ema\_20}} - 1\right) \times 100 \le +3.5\%$

---

## 2. 실데이터 기반 베이스라인 성과 검증 및 차기 전략(v2.0) 설계 대기

* **데이터 기준**: Supabase 적재 유니버스 247개 종목 (`daily_chart` 14,710건, `daily_investor_supply` 6,175건)
* 사용자 아이디어 접수 및 실데이터 백테스트 검증 후, 아래 섹션에 **Strategy v2.0 (신규 발굴 전략, 세부 수식, 진입/필터 조건, 구현 명세)**을 업데이트합니다.
