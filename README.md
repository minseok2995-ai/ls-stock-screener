# 📈 LS증권 Open API 기반 기관·외국인 수급 & EMA 스크리닝 시스템 (`ls-stock-screener`)

야간시장(NXT) 마감 이후 **매일 밤 21:05(KST)** GitHub Actions에서 자동으로 LS증권 Open API를 호출하여 **수정주가 일봉 차트 + 지수이동평균(EMA 5, 20, 60, 120, 240)** 및 **투자주체별 수급(수량·금액)**을 수집하고, **Supabase 클라우드 DB** 업데이트와 **텔레그램 알림 발송** 및 **실시간 웹 대시보드 시각화**를 수행하는 시스템입니다.

---

## 🤝 3원화 대화창 협업 워크플로우 (StudyRemote 운영 규칙)

본 프로젝트는 역할이 분리된 3개의 대화창을 통해 유기적으로 운영됩니다:

1. **[전략 개발] 대화창**:
   * 주식 종목 발굴 전략 및 수급·차트 알고리즘 기획 전담 (`STRATEGY.md`에 기록 및 최신화)
2. **[프로그램 개발 및 수정(메인)] 대화창**:
   * 작업 시작 전 `git status` 및 원격 저장소 최신 상태를 확인
   * `STRATEGY.md`의 기획안 및 [검증 및 테스트] 대화창의 피드백을 바탕으로 실제 코드 구현, 버그 수정, 환경 구성 수행
   * 작업 완료 후 `README.md`에 개발 환경, 폴더 구조, 실행 방법, 적용 전략 및 변경 사항을 상세히 업데이트하고 Git 커밋/푸시 수행
3. **[검증 및 테스트] 대화창**:
   * `README.md`와 최신 커밋을 바탕으로 테스트(`test_screener_verification.py`, `run_daily_screener.py --mode verify`) 실행 및 데이터 정합성 검증 리포트 작성

---

## 🖥️ 개발 및 운영 환경 (Environment & Tech Stack)

| 구분 | 상세 환경 및 구성 |
| :--- | :--- |
| **OS / 실행 환경** | Linux (Debian 12 / GitHub Actions `ubuntu-latest`) |
| **Backend 언어** | **Python 3.11+** (외부 pip 패키지 의존성 없이 표준 라이브러리 `urllib`, `json`, `ssl`, `datetime`, `argparse`만으로 동작하여 이식성 극대화) |
| ** 증권사 API** | **LS증권 Open API** (`https://openapi.ls-sec.co.kr:8080`) — OAuth2 토큰 발급 및 TR(`t8436`, `t1444`, `t1463`, `t8410`, `t1717`) 호출 |
| **Database** | **Supabase (PostgreSQL + PostgREST)** (`https://rwvvrtjsxzecmdykwrxg.supabase.co`) |
| **Frontend 대시보드** | HTML5 + TailwindCSS (CDN) + HTML5 Canvas 2D (`index.html`) — GitHub Pages 배포 (`https://minseok2995-ai.github.io/ls-stock-screener/`) |
| **배치 스케줄러** | **GitHub Actions** (`.github/workflows/daily_batch.yml`) — 평일 월~금 **21:05 KST** (`cron: '5 12 * * 1-5'`) 자동 실행 및 `workflow_dispatch` 수동 실행 |
| **알림 채널** | **Telegram Bot HTTP API** (`@my_ls_stock_bot`, 기본 수신 `TELEGRAM_CHAT_ID: 1018392459`) |

### 필수 환경변수 (GitHub Repository Secrets / 로컬 환경변수)

| 변수명 | 필수 여부 | 설명 |
| :--- | :---: | :--- |
| `LS_APP_KEY` | 필수 | LS증권 Open API App Key |
| `LS_APP_SECRET` | 필수 | LS증권 Open API Secret Key |
| `SUPABASE_URL` | 선택 (기본값 내장) | Supabase 프로젝트 URL (`https://rwvvrtjsxzecmdykwrxg.supabase.co`) |
| `SUPABASE_KEY` | 선택 (기본값 내장) | Supabase API Key (Publishable Key 또는 Service Role Key) |
| `TELEGRAM_BOT_TOKEN` | 필수 (알림용) | 텔레그램 봇 HTTP API 토큰 |
| `TELEGRAM_CHAT_ID` | 선택 (기본값 내장) | 텔레그램 수신자 Chat ID (기본값: `1018392459`) |

---

## 📂 프로젝트 폴더 및 파일 구조 (Directory Structure)

```text
ls-stock-screener/
├── .github/
│   └── workflows/
│       └── daily_batch.yml          # 평일 21:05(KST) 자동 배치 및 수동 실행(workflow_dispatch) 워크플로우
├── README.md                        # 프로젝트 종합 가이드 (환경, 구조, 실행법, 전략 명세, 변경 이력)
├── STRATEGY.md                      # [전략 개발] 대화창에서 작성·관리하는 종목 발굴 전략 기획 문서 (생성 시 연동)
├── run_daily_screener.py            # 메인 백엔드 수집·분석·DB적재·텔레그램 알림·4단계 검증 스크립트
├── index.html                       # 실시간 Supabase 연동 웹 대시보드 (GitHub Pages 메인 엔트리)
├── supabase_schema.sql              # Supabase 테이블(3종), 인덱스, 뷰, RPC 함수 생성 SQL 스키마
├── test_screener_verification.py    # 4단계 핵심 로직(유니버스·EMA·순수기관 수식·DB 스키마) 자동 검증 테스트 스크립트
└── .gitignore                       # Python 캐시(__pycache__) 등 버전 관리 제외 설정
```

---

## 🎯 적용된 핵심 전략 및 알고리즘 명세 (Applied Strategy)

### 1. 분석 대상 유니버스 필터링 (Universe Selection)
* **대상 시장**: 코스피(`KOSPI`) + 코스닥(`KOSDAQ`) 통합 보통주 (`t8436` 전 종목 마스터 기준)
* **제외 대상**:
  * ETF, ETN, ELW (`etfgubun != "0"` 또는 브랜드 접두어 `KODEX`, `TIGER`, `ACE`, `SOL`, `RISE`, `PLUS`, `HANARO`, `KOSEF`, `ARIRANG`, `TIMEFOLIO`, `히어로즈`, `마이티`, `원큐`, `파워` 등)
  * 스팩(`SPAC`, `기업인수목적`), 리츠(`리츠`, `맥쿼리인프라`), 인버스/레버리지/선물/채권형
  * 우선주 (종목코드 마지막 자리가 `'0'`이 아닌 종목 및 종목명이 `우`, `우B`, `우C`로 끝나는 종목)
* **정량 편입 조건**:
  * **시가총액 700억 원 이상** (`market_cap_eok >= 700`)
  * **최근 20영업일 평균 거래대금 20억 원 이상** (`avg_val_20d_eok >= 20`)

### 2. 시가총액 산출 및 유니버스 갱신 주기 (부하 최소화 하이브리드)
* **정기 전수 산출 (`universe` 모드 / 분기 초 자동 전환)**:
  * **최초 1회(DB 미구축 시)** 및 **매년 3·6·9·12월 첫 거래일**에 `t1444`(시가총액 상위 연속조회)와 `t8436`(보통주 마스터)을 결합하여 시가총액 ≥ 700억 종목과 상장주식수(`shares`)를 산출·저장합니다.
* **평일 일일 증분 + 급등주 자동 편입 (`daily` 모드)**:
  * 평일 일일 배치에서는 이미 편입된 유니버스 종목만 조회하고 **`상장주식수(shares) × 당일종가(close)`**로 API 추가 부하 없이 시가총액을 매일 갱신합니다.
  * 동시에 당일 거래대금 상위(`t1463`, 코스피·코스닥 각 1회 호출)를 체크하여, 분기 도중 거래대금이 폭발하며 시가총액 700억 원 이상으로 올라선 신규 주도주를 자동으로 유니버스에 편입합니다.

### 3. 순수 기관(`real_inst`) 정의 및 투자주체별 수급 분해 (`t1717`)
* 단기 차익거래·유동성공급(LP) 물량이 많아 추세적 수급을 왜곡하는 **금융투자(`fn_inv`, `tjj0002`)를 순수기관 합산에서 제외**합니다.
* **순수 기관 합산 공식**:
  $$\text{순수 기관}(\texttt{real\_inst}) = \text{투신}(\texttt{tjj0003}) + \text{사모펀드}(\texttt{tjj0000}) + \text{연기금}(\texttt{tjj0006}) + \text{보험}(\texttt{tjj0004}) + \text{기타금융}(\texttt{tjj0007}) + \text{은행}(\texttt{tjj0005})$$
* **지원하는 수급 주체 필터 (`index.html`)**:
  1. `real_inst`: 순수 기관 합산 (6대 주체)
  2. `both`: 양매수 (순수 기관 순매수 `> 0` AND 외국인 순매수 `> 0` 동시 충족)
  3. `frg`: 외국인 단독 (`tjj0016`)
  4. `itc`: 투신 단독 (`tjj0003`)
  5. `pef`: 사모펀드 단독 (`tjj0000`)
  6. `pen`: 연기금 단독 (`tjj0006`)
  7. `ins`: 보험 + 기타금융 + 은행 합산 (`tjj0004 + tjj0007 + tjj0005`)

### 4. 핵심 정렬 및 포착 지표: 거래량 대비 순매수 비중 (%)
* 시가총액 규모 차이에 따른 단순 순매수 금액 왜곡을 막기 위해, **기간 누적 거래량 대비 순매수 수량 비중(%)**을 핵심 정렬 기준으로 사용합니다:
  $$\text{거래량 대비 순매수 비중}(\%) = \left( \frac{\sum_{t=1}^{N} \text{선택 주체 순매수 수량}_t}{\sum_{t=1}^{N} \text{총 거래량}_t} \right) \times 100$$
* **정합성 보장**: 수급 테이블(`daily_investor_supply`)과 일봉 차트 테이블(`daily_chart`)의 **`trade_date`를 1:1로 정확히 매칭**하여 동일 거래일의 거래량과 순매수 수량만 합산합니다.
* **지원 누적 기간**: 당일(`1일`), `3일`, `5일`, `10일` 및 사용자 지정 `N일`(최대 60영업일).
* **기본 포착 기준**: 거래량 대비 순수기관 순매수 비중 **10.0% 이상** (슬라이더로 0%~25% 실시간 조절 가능).

### 5. 기술적 분석 지표 (수정주가 일봉 & EMA 5·20·60·120·240)
* LS증권 `t8410` TR에서 **수정주가(`sujung="Y"`)** 기준 최근 260영업일 일봉을 받아 지수이동평균(EMA) 5개 선을 계산합니다 ($\alpha = \frac{2}{\text{span}+1}$):
  * 단기: **EMA 5**, **EMA 20**
  * 중기: **EMA 60**, **EMA 120**
  * 장기: **EMA 240**
* **지원하는 차트 기술적 조건 필터**:
  * `all`: 전체 (차트 조건 제한 없음)
  * `above_20`: 종가 ≥ 20일 EMA 위 (`close >= ema_20`)
  * `align_short`: 단기 정배열 (`ema_5 > ema_20 > ema_60`)
  * `align_mid`: 중장기 정배열 (`ema_20 > ema_60 > ema_120`)
  * `align_full`: 완전 정배열 (`ema_5 > ema_20 > ema_60 > ema_120 > ema_240`)
  * `pullback_20`: 20일 EMA 눌림목 (`20일선 이격도 -2.0% ~ +3.5%` 구간)

---

## 🗄️ 데이터베이스 스키마 요약 (`supabase_schema.sql`)

1. **`stocks_master` (유니버스 종목 마스터)**
   * PK: `shcode` (종목코드 6자리)
   * 주요 컬럼: `hname`(종목명), `market`(`KOSPI`/`KOSDAQ`), `shares`(상장주식수), `market_cap_eok`(시가총액 억 원), `avg_val_20d_eok`(20일 평균 거래대금 억 원), `last_close`(최근 종가), `is_universe`(유니버스 편입 여부), `updated_at`
2. **`daily_chart` (수정주가 일봉 및 5개 EMA — 종목당 최근 60영업일 유지)**
   * PK: `(shcode, trade_date)`
   * 주요 컬럼: `open`, `high`, `low`, `close`, `volume`, `value_million`, `change_rate`, `ema_5`, `ema_20`, `ema_60`, `ema_120`, `ema_240`
3. **`daily_investor_supply` (투자주체별 일별 순매수 수량·금액 — 종목당 최근 30영업일 유지)**
   * PK: `(shcode, trade_date)`
   * 주요 컬럼: `real_inst_vol`, `real_inst_amt`(순수기관 합산), `frg_vol`, `frg_amt`(외국인), `ind_vol`, `ind_amt`(개인), `fn_inv_vol`, `fn_inv_amt`(금융투자-제외분), 6대 세부주체(`itc_vol/amt`, `pef_vol/amt`, `pen_vol/amt`, `ins_vol/amt`, `etc_fin_vol/amt`, `bank_vol/amt`)

---

## 🚀 실행 및 검증 방법 (Execution & Verification Guide)

### 1. 로컬 / 서버 CLI 실행 방법

```bash
# 1) 환경변수 설정 (로컬 테스트 시)
export LS_APP_KEY="발급받은_LS_APP_KEY"
export LS_APP_SECRET="발급받은_LS_APP_SECRET"
export SUPABASE_URL="https://rwvvrtjsxzecmdykwrxg.supabase.co"
export SUPABASE_KEY="sb_publishable_vH_-2K-y5HwQ9oqiT1gtIw_P9pKdJ26"
export TELEGRAM_BOT_TOKEN="텔레그램_봇_토큰"
export TELEGRAM_CHAT_ID="1018392459"

# 2) 일일 자동 배치 실행 (DB가 비어있거나 3·6·9·12월 첫 거래일이면 자동으로 유니버스 재산출 수행)
python3 run_daily_screener.py --mode daily

# 3) 빠른 샘플 적재 테스트 (시가총액 상위 30종목만 1분 내 고속 수집·적재)
python3 run_daily_screener.py --mode daily --max-stocks 30

# 4) 분기 시가총액 및 유니버스 강제 전수 재산출
python3 run_daily_screener.py --mode universe

# 5) 2년치(500영업일) 전체 백필 구축
python3 run_daily_screener.py --mode backfill

# 6) Supabase DB 적재 데이터 4단계 정합성 검증 리포트 출력
python3 run_daily_screener.py --mode verify
```

### 2. 단위·통합 검증 테스트 스크립트 실행 (`[검증 및 테스트]` 대화창용)

```bash
# 4단계 핵심 로직(유니버스 필터링, EMA 계산, 순수기관 6대 주체 수식, DB 스키마) 자동 검증
python3 test_screener_verification.py
```

### 3. GitHub Actions 자동/수동 실행
* **자동 실행**: 평일(월~금) **밤 21:05 KST (`UTC 12:05`)**에 `.github/workflows/daily_batch.yml`이 자동 실행되어 Supabase DB를 업데이트하고 텔레그램으로 당일 포착 종목 리포트를 전송합니다.
* **수동 실행**: GitHub 저장소의 **Actions → Daily LS Stock Supply & Chart Batch Update → Run workflow**에서 `mode`(`daily` / `universe` / `backfill` / `verify`)와 `max_stocks`를 지정하여 언제든 즉시 실행할 수 있습니다.

---

## 📝 주요 변경 이력 (Changelog)

* **2026-11-11 (v1.2 — 웹 대시보드 최신 거래일 페이지네이션 및 1:1 매칭 패치)**:
  * Supabase PostgREST의 1회 요청당 최대 1,000건 반환 제한(`db-max-rows=1000`)으로 인해 오름차순 조회 시 과거 거래일(`2026-08-20`)에서 잘리던 현상 해결.
  * `index.html`에 최신 거래일 역순(`trade_date.desc`) 8페이지 병렬 조회(`fetchRecentPagesDesc`) 적용하여 최신 거래일(`2026-11-11`) 데이터 100% 확보.
  * `buildPeriodAggregation`에서 `daily_investor_supply`와 `daily_chart`를 동일 `trade_date` 기준으로 1:1 매칭하도록 개선.
  * 종목 선택 시 우측 캔들차트용 60영업일 전체 일봉을 온디맨드 로드(`ensureStockFullChart`)하도록 개선.
* **2026-11-11 (v1.1 — 실데이터 적재 및 텔레그램 알림 연동 완료)**:
  * Supabase RLS 해제 및 초기 데모 데이터 정리 후 LS증권 Open API 실데이터 247개 유니버스 종목 적재 완료.
  * 텔레그램 봇(`@my_ls_stock_bot`) 알림 발송 및 GitHub Actions 워크플로우 검증 완료.
* **2026-11-11 (v1.0 — 초기 아키텍처 구축)**:
  * LS증권 Open API(`t8436`, `t1444`, `t1463`, `t8410`, `t1717`) 연동 백엔드(`run_daily_screener.py`), Supabase 스키마(`supabase_schema.sql`), 웹 대시보드(`index.html`), 4단계 검증 스위트(`test_screener_verification.py`) 구현.
