# 📈 LS증권 Open API 기반 기관 수급 종목 스크리너 (`ls-stock-screener`)

야간시장(NXT) 마감 이후 **매일 밤 21:05(KST)** GitHub Actions에서 자동으로 LS증권 Open API를 호출하여 **코스피·코스닥 시가총액 700억 원 이상 보통주 전수(약 1,463종목)**의 **2년치(약 500영업일) 수정주가 일봉 차트 + 지수이동평균(EMA 5, 20, 60, 120, 240)** 및 **투자주체별 수급(수량·금액)**을 수집하고, **Supabase 클라우드 DB** 업데이트와 **텔레그램 알림 발송** 및 **실시간 웹 대시보드(`기관 수급 종목 스크리너`) 시각화·엑셀(`.xlsx`) 다운로드**를 수행하는 시스템입니다.

---

## 🤝 3원화 대화창 협업 워크플로우 (`StudyRemote` 운영 규칙)

본 프로젝트는 역할이 분리된 3개의 대화창을 통해 파일 기반으로 유기적으로 운영됩니다:

1. **[전략 개발] 대화창**:
   * 주식 종목 발굴 전략 및 수급·차트 알고리즘 기획 전담 (`STRATEGY.md`에 기록 및 최신화)
2. **[프로그램 개발 및 수정(메인)] 대화창**:
   * **[작업 시작 전 - 읽을 파일]**: 항상 `git pull`을 먼저 실행한 뒤 `STRATEGY.md`(설계된 전략·수식·요구사항)와 `TEST_REPORT.md`(보고된 버그·수정 요청)를 읽고 작업 파악 (`STRATEGY.md`는 임의 수정 금지)
   * **[작업 완료 후 - 작성할 파일]**: 실제 프로그램 소스코드 구현/수정 후 `README.md`의 (1) 개발 환경 및 폴더 구조, (2) 실행 방법, (3) 하단 `최근 수정 내역(Changelog)`을 최신 상태로 업데이트하고, `TEST_REPORT.md`의 해결된 버그 항목을 `[해결 완료]`로 표시한 뒤 `git commit` 및 `git push` 수행
3. **[검증 및 테스트] 대화창**:
   * `README.md`, `STRATEGY.md`와 최신 커밋을 바탕으로 테스트(`test_screener_verification.py`, `run_daily_screener.py --mode verify`) 실행 및 `TEST_REPORT.md`에 합격 기준(`AC-1` ~ `AC-12`) 검증 결과·수정 요청 작성

---

## 🖥️ 1. 개발 및 운영 환경 및 폴더 구조 (Environment & Directory Structure)

### 1.1 기술 스택 및 운영 환경

| 구분 | 상세 환경 및 구성 |
| :--- | :--- |
| **OS / 실행 환경** | Linux (Debian 12 / GitHub Actions `ubuntu-latest`, 단일 Job 최대 360분 타임아웃) |
| **Backend 언어** | **Python 3.11+** (외부 pip 패키지 의존성 없이 표준 라이브러리 `urllib`, `json`, `ssl`, `datetime`, `argparse`, `concurrent.futures`만으로 동작하여 이식성 극대화) |
| **증권사 API** | **LS증권 Open API** (`https://openapi.ls-sec.co.kr:8080`) — OAuth2 토큰 자동 발급/갱신 및 TR(`t8436`, `t1444`, `t1463`, `t1102`, `t8410`, `t1717`) 호출 |
| **Database** | **Supabase (PostgreSQL + PostgREST)** (`https://rwvvrtjsxzecmdykwrxg.supabase.co`, 약 1,463종목 × 500영업일 ≈ 테이블당 약 71만 행 규모, 복합 PK `(shcode, trade_date)` 인덱스 최적화) |
| **Frontend 대시보드** | HTML5 + TailwindCSS (CDN) + SheetJS (`xlsx-0.20.3` CDN, `.xlsx` 다운로드) + HTML5 Canvas 2D (`index.html`) — GitHub Pages 배포 (`https://minseok2995-ai.github.io/ls-stock-screener/`) |
| **배치 스케줄러** | **GitHub Actions** (`.github/workflows/daily_batch.yml`) — 평일 월~금 **21:05 KST** (`cron: '5 12 * * 1-5'`) 자동 실행 및 `workflow_dispatch` 수동 실행 |
| **알림 채널** | **Telegram Bot HTTP API** (`@my_ls_stock_bot`, 기본 수신 `TELEGRAM_CHAT_ID: 1018392459`) |

### 1.2 필수 환경변수 (GitHub Repository Secrets / 로컬 환경변수)

| 변수명 | 필수 여부 | 설명 |
| :--- | :---: | :--- |
| `LS_APP_KEY` | 필수 | LS증권 Open API App Key |
| `LS_APP_SECRET` | 필수 | LS증권 Open API Secret Key |
| `SUPABASE_URL` | 선택 (기본값 내장) | Supabase 프로젝트 URL (`https://rwvvrtjsxzecmdykwrxg.supabase.co`) |
| `SUPABASE_KEY` | 선택 (기본값 내장) | Supabase API Key (Publishable Key 또는 Service Role Key) |
| `TELEGRAM_BOT_TOKEN` | 필수 (알림용) | 텔레그램 봇 HTTP API 토큰 |
| `TELEGRAM_CHAT_ID` | 선택 (기본값 내장) | 텔레그램 수신자 Chat ID (기본값: `1018392459`) |

### 1.3 프로젝트 폴더 및 파일 구조

```text
ls-stock-screener/
├── .github/
│   └── workflows/
│        └── daily_batch.yml          # 평일 21:05(KST) 자동 배치 및 수동 실행 워크플로우 (timeout: 360분, mode/max_stocks 지원)
├── README.md                        # [프로그램 개발 및 수정] 창 관리: 환경, 폴더 구조, 실행 방법, 최근 수정 내역(Changelog)
├── STRATEGY.md                      # [전략 개발] 창 관리 (임의 수정 금지): 종목 발굴 전략 v2.0 및 UI·DB 요구사항 명세서 (SSOT)
├── TEST_REPORT.md                   # [검증 및 테스트] 창 관리: AC-1~AC-12 검증 리포트 및 버그/수정 요청 트래커
├── run_daily_screener.py            # 메인 백엔드: 1,463종목 유니버스 산출, 2년치(500일) 일봉·수급 슬라이딩 수집, Strategy v2.0 평가 및 AC-1~AC-12 검증
├── index.html                       # 실시간 웹 대시보드(기관 수급 종목 스크리너): 2대 스크리닝 모드, 1줄 7열 리스트, 11열 엑셀(.xlsx) 저장, 70만 행 PK 청크 고속 로드
├── supabase_schema.sql              # Supabase 테이블(3종), 복합 기본키(shcode, trade_date) 인덱스, 뷰, RPC 함수 스키마
├── test_screener_verification.py    # 6단계 핵심 로직(유니버스·미완성감지·EMA·t1717 페이지네이션·스마트 Resume·Strategy v2.0 2대 모드 & T+1 차단) 단위 테스트
└── .gitignore                       # Python 캐시(__pycache__) 등 버전 관리 제외 설정
```

---

## 🎯 2. 적용된 핵심 전략(Strategy v2.0) 및 대용량 DB 아키텍처 (`STRATEGY.md` 준수)

### 2.1 데이터 구축 및 기준일($T$) 정합성 원칙
1. **분석 대상 유니버스 (시총 700억 이상 보통주 전수 — 약 1,463종목)**:
   * 코스피(`KOSPI`) + 코스닥(`KOSDAQ`) 통합 보통주 (`t8436` 마스터 기준, ETF/ETN/ELW/스팩/리츠/우선주/인버스/레버리지 제외).
   * 수집 단계 거래대금 사전 차단 없이 `market_cap_eok >= 700.0`인 모든 보통주의 2년치(약 500영업일) 수정주가 일봉(`daily_chart`) 및 투자주체별 수급(`daily_investor_supply`)을 100% 적재합니다.
2. **순수 기관(`real_inst`) 정의**:
   * 단기 차익·LP 물량 왜곡이 있는 **금융투자(`fn_inv`)를 제외**하고 **`투신 + 보험 + 은행 + 종금(기타금융) + 연기금 등 + 사모펀드`** 6대 주체만 합산합니다.
3. **기준 확정 거래일($T$) 산정 및 장중 $T+1$ 데이터 혼입 원천 차단**:
   * 장중 미확정(`전 주체 수량 0`) 더미 행을 제외한 **가장 최근 확정 수급 거래일**을 기준일 $T$로 산정합니다.
   * 낮 시간대(장중) 배치 실행으로 `daily_chart`에 $T+1$ 장중 캔들이 적재되어 있더라도 시계열 인덱스가 밀리지 않도록 모든 일봉·수급 조회 및 판정에 **`trade_date <= T` 상한**을 강제하며, 확정 수급과 일봉 모두 `trade_date === T` 레코드가 존재하는 종목만 스크리닝합니다.
   * 조건 비교와 내림차순 정렬은 재계산 부동소수점 오차 없이 DB 확정 저장값(`inst_vol_ratio`, `frg_vol_ratio`)을 사용하며, 모든 모드에서 **마지막 날(기준일 $T$) 당일의 `수급비중`(`inst_vol_ratio`) 및 `수급금액`(`real_inst_amt`)**을 표시·정렬 기준으로 사용합니다.

### 2.2 2대 핵심 스크리닝 모드 (`STRATEGY.md` 2.2절 ~ 2.3절)
1. **[모드 1] `기관 수급 발생 종목`** (차트 추세 무관 순수기관 수급 포착 — 4개 하위 옵션):
   * **`당일 10% 이상`** *(기본값)*: $\text{inst\_vol\_ratio}_T \ge 10.0\%$
   * **`당일 15% 이상`**: $\text{inst\_vol\_ratio}_T \ge 15.0\%$
   * **`당일 20% 이상`**: $\text{inst\_vol\_ratio}_T \ge 20.0\%$
   * **`3일 연속 5% 이상`**: 최근 3거래일($T-2, T-1, T$) **매일** 일별 순수기관 거래량 비중 $\ge 5.0\%$ ($\text{consec\_5p\_days}_T \ge 3$)
2. **[모드 2] `하락 추세 전환 수급 발생`** (최소 65거래일 일봉 & 13거래일 수급 보유 종목 중 ① ∧ ② ∧ ③ 모두 충족):
   * **① 사전 장기 하락 추세 & 하락 진정**:
     * 직전 거래일($T-1$) 중장기 이평선 역배열 필수: $\text{EMA}_{20, T-1} < \text{EMA}_{60, T-1} < \text{EMA}_{120, T-1}$
     * 수급 유입 직전 기준점 $P$(`유형 A`는 $P = T-1$, `유형 B`는 $P = T-1$ 또는 $P = T-3$ 중 하나 이상)에서:
       * **(a) 60거래일 최고가 대비 낙폭 과대**: $((\text{Close}_P / \max_{k=0..59} \text{High}_{P-k}) - 1) \times 100 \le -15.0\%$
       * **(b) 직전 20거래일 최저가 미이탈**: $\min(\text{Close}_{P-2}, \text{Close}_{P-1}, \text{Close}_P) \ge \min_{k=3..19} \text{Low}_{P-k}$
       * **(c) 3거래일 연속 저점 지지**: $\text{Close}_{P-2} \ge \text{Low}_{P-3} \;\land\; \text{Close}_{P-1} \ge \text{Low}_{P-2} \;\land\; \text{Close}_P \ge \text{Low}_{P-1}$
   * **② 당일 첫 순수기관 수급 발생 (`유형 A` 또는 `유형 B`)**:
     * **`[유형 A]`**: 당일($T$) $\text{inst\_vol\_ratio}_T \ge 10.0\%$ 이고 직전 10거래일($T-10 \sim T-1$) 모두 $< 5.0\%$
     * **`[유형 B]`**: 직전 10거래일($T-12 \sim T-3$) 모두 $< 5.0\%$ 후 최근 3거래일($T-2, T-1, T$) 연속 모두 $\ge 5.0\%$
   * **③ 당일 추세 전환 양봉 및 5일선 상회 마감**:
     * $\text{Close}_T \ge \text{EMA}_{5, T} \;\land\; \text{Close}_T > \text{Open}_T$

### 2.3 웹 대시보드(`index.html`) UI/UX 슬림화, 엑셀 저장 및 70만 행 PK 인덱스 아키텍처
* **상단 슬림 헤더 & 컨트롤 바**: `기관 수급 종목 스크리너` 타이틀, `기준일: YYYY-MM-DD` 배지, 순수 기관 산식 안내만 남기고 불필요한 모달·버튼 3종과 차트 EMA 필터 드롭다운을 제거했습니다.
* **1줄(Single-line) 7컬럼 리스트 & 11컬럼 엑셀(`.xlsx`) 다운로드**:
  * 화면 테이블 7컬럼: `종목명 | 현재가 | 등락율 | 수급비중 | 수급금액 | 외국인비중 | 연속일수`
  * `[엑셀 저장]` 클릭 시 조건별 5종 표준 파일명(`{기준일}_기관수급발생_당일10%이상.xlsx`, `..._당일15%이상.xlsx`, `..._당일20%이상.xlsx`, `..._3일연속5%이상.xlsx`, `{기준일}_하락추세전환수급발생.xlsx`)과 11개 컬럼(`종목코드, 종목명, 현재가, 등락폭/율, 수급 비중, 수급 금액, Ema5, Ema20, Ema60, Ema120, Ema240`, 종목코드 앞자리 `0` 보존 문자열 셀 지정)으로 즉시 저장됩니다.
* **70만 행 규모 DB `HTTP 500` 타임아웃 원천 차단 (복합 PK `(shcode, trade_date)` 인덱스 직접 조회)**:
  1. 최신 확정 기준일($T$): 대표 대형주(`shcode=in.(005930,000660,005380)`) PK 인덱스 조건으로 0.3초 내 확정.
  2. 1,463종목 45일 윈도우 로드: 종목 코드를 28종목(`<= 30`) 단위 PK 청크로 분할해 `shcode=in.(...)&and=(trade_date.gte.{T-45일},trade_date.lte.{T})&order=shcode.asc,trade_date.asc&limit=1000`을 8개 동시성 + 청크별 자동 재시도로 고속 로드(청크당 최대 ~880행으로 1,000행 절단 제로).
  3. 하락 추세 전환 1차 후보 정밀 검증: 1차 후보 종목들을 10종목 이하 PK 청크로 `T - 125일 ~ T` 일봉(약 85영업일)을 보강 조회하여 60거래일 고점 대비 낙폭·바닥 진정 조건을 오차 없이 판정.

---

## 🚀 3. 실행 및 검증 방법 (Execution & Verification Guide)

### 3.1 로컬 / 서버 CLI 실행 명령어

```bash
# 1) 환경변수 설정
export LS_APP_KEY="발급받은_LS_APP_KEY"
export LS_APP_SECRET="발급받은_LS_APP_SECRET"
export SUPABASE_URL="https://rwvvrtjsxzecmdykwrxg.supabase.co"
export SUPABASE_KEY="sb_publishable_vH_-2K-y5HwQ9oqiT1gtIw_P9pKdJ26"
export TELEGRAM_BOT_TOKEN="텔레그램_봇_토큰"
export TELEGRAM_CHAT_ID="1018392459"

# 2) [2년치 전수 백필] 시총 700억 이상 전 종목(약 1,463종목) × 500영업일 차트·수급 구축
#    (기본적으로 --skip-existing이 활성화되어 있어 이미 2년치 적재가 끝난 종목은 자동 스킵 후 이어받기됨)
python3 run_daily_screener.py --mode backfill

# 3) [CLI 구간 분할 백필] 로컬/서버 CLI에서 전체 후보를 N등분하거나 시작/종료 인덱스를 지정하여 분할 실행할 때
python3 run_daily_screener.py --mode backfill --chunk "1/3"
python3 run_daily_screener.py --mode backfill --chunk "2/3"
python3 run_daily_screener.py --mode backfill --chunk "3/3"
# 또는 인덱스 직접 지정:
python3 run_daily_screener.py --mode backfill --start-idx 0 --end-idx 500

# 4) [일일 증분 배치] 평일 야간장 마감 후 실행 (미적재 종목은 자동 2년 백필, 기적재 종목은 최근 25일 고속 증분)
python3 run_daily_screener.py --mode daily

# 5) [빠른 샘플 테스트] 상위 10종목만 즉시 백필 테스트
python3 run_daily_screener.py --mode backfill --max-stocks 10

# 6) [데이터 정합성(AC-1~AC-12) 및 Strategy v2.0 전 종목 PK 스크리닝 검증 리포트 출력]
python3 run_daily_screener.py --mode verify
```

### 3.2 단위·통합 검증 테스트 스위트 실행 (`[검증 및 테스트]` 대화창용)

```bash
# 6대 핵심 로직(보통주 필터, 1200종목 미만 미완성 유니버스 감지, EMA/순수기관 수식, t1717 역순 페이지네이션 & 장중 0수급 차단, 스마트 이어받기, Strategy v2.0 2대 모드 & T+1 일봉 차단) 검증
python3 test_screener_verification.py
```

### 3.3 웹 대시보드 접속 및 GitHub Actions 실행 방법
* **실시간 웹 대시보드**: `https://minseok2995-ai.github.io/ls-stock-screener/` (페이지 접속 시 별도 설정 없이 1,463종목 전수 자동 로드 및 스크리닝·엑셀 저장 지원)
* **GitHub Actions 수동 실행**: GitHub 저장소 → **Actions** 탭 → **Daily LS Stock Supply & Chart Batch Update** → **Run workflow** 클릭 → `mode` (`daily` / `backfill` / `universe` / `verify`), `max_stocks` 입력 후 실행 (`timeout-minutes: 360`).
* **정기 일일 배치**: 평일(월~금) **밤 21:05 KST (`UTC 12:05`)**에 자동 실행.

---

## 📝 4. 최근 수정 내역 (Changelog)

* **2026-11-12 (v2.0 — `STRATEGY.md` 2절·3절 전면 구현: 2대 스크리닝 전략 확정, 웹 UI/UX 전면 슬림화, 11컬럼 엑셀(`.xlsx`) 저장 및 70만 행 DB PK 인덱스 고속 로드 아키텍처 적용 — `AC-7 ~ AC-12`)**:
  1. **확정 스크리닝 전략 v2.0 구현 (`index.html`, `run_daily_screener.py`, `test_screener_verification.py`)**:
     * 기준 확정 거래일 $T$(`topTradeDate`) 상한(`trade_date <= T`)을 일봉·수급 전 구간에 강제 적용하여 장중 $T+1$ 일봉이 DB에 적재된 상태에서도 시계열 밀림 없이 `trade_date === T` 정합성을 100% 보장.
     * **`[모드 1: 기관 수급 발생 종목]`**: `당일 10% 이상`(기본), `당일 15% 이상`, `당일 20% 이상`, `3일 연속 5% 이상`($T-2, T-1, T$ 각각 $\ge 5.0\%$) 4개 하위 조건 및 마지막 날($T$) 단일 기준 표시·내림차순 정렬 구현.
     * **`[모드 2: 하락 추세 전환 수급 발생]`**: ① 직전일($T-1$) 중장기 이평선 역배열($\text{EMA}_{20} < \text{EMA}_{60} < \text{EMA}_{120}$) 및 기준점 $P$(`유형 A` $P=T-1$, `유형 B` $P=T-1$ 또는 $P=T-3$)에서의 60일 최고가 대비 낙폭 $\le -15.0\%$·20일 최저가 미이탈·3일 연속 저점 지지, ② 첫 순수기관 수급(`유형 A` 또는 `유형 B`), ③ 당일 양봉($\text{Close}_T > \text{Open}_T$) 및 $\text{Close}_T \ge \text{EMA}_{5, T}$ 판정 구현 (`evaluate_strategy_v2_stock`, `test_6_strategy_v2_screening_modes` 추가).
  2. **상단 헤더·컨트롤 바 슬림화 및 런타임 `null` 에러 제로화 (`index.html` — `AC-7`, `AC-8`)**:
     * 타이틀을 `기관 수급 종목 스크리너`로 변경하고 상단에 `기준일` 배지와 순수 기관 합산 산식 안내만 남기며, 우측 버튼 3종·모달 3종(`verifyModal`, `telegramModal`, `supabaseModal`) 및 관련 JS 참조를 완전히 제거.
     * `스크리닝 조건 선택` 드롭다운을 2개 항목으로 단순화하고 `하락 추세 전환 수급 발생` 선택 시 비중 하위 옵션 영역을 자동 숨김(`hidden`) 처리하며 기존 `4. 차트 지수이동평균` 드롭다운 삭제.
  3. **좌측 리스트 1줄(7컬럼) 컴팩트 테이블 개편 및 `[엑셀 저장]` 구현 (`index.html` — `AC-10`, `AC-11`)**:
     * 좌측 리스트를 `종목명 | 현재가 | 등락율 | 수급비중 | 수급금액 | 외국인비중 | 연속일수` 7개 열 1줄 컴팩트 행으로 슬림화.
     * SheetJS(`xlsx-0.20.3`) 기반 `[엑셀 저장]` 기능을 구현하여 5종 표준 파일명(`{기준일}_{조건명}.xlsx`)과 11개 지정 컬럼(`종목코드` 앞자리 `0` 문자열 보존, `등락폭/율` 단일 열 병합 및 `NaN` 방지 포함)으로 즉시 다운로드 지원.
  4. **70만 행 대용량 DB `HTTP 500` 타임아웃 원천 해결 (`index.html`, `run_daily_screener.py` — `AC-12`)**:
     * 무필터 전역 정렬 쿼리를 전면 폐기하고 복합 기본키 `(shcode, trade_date)` 인덱스를 직접 타는 대표 대형주 기준일 조회 + 28종목 단위 PK 청크 병렬 로드(45일 윈도우, 청크별 재시도 포함) + 1차 후보 10종목 단위 125일 일봉 보강 조회로 전환.
     * `run_daily_screener.py --mode verify` 및 `supabase_cleanup_unsettled_supply()`, `supabase_get_table_exact_count()` 역시 71만 행 규모에서 타임아웃 없이 동작하도록 PK 청크 쿼리 및 `count=estimated` 폴백 적용.
* **2026-11-12 (v1.4.3 — `TEST_REPORT.md` `[ISSUE-006]` ~ `[ISSUE-010]` 5건 전수 해결: 평일 고속 증분 판정 분리, 장중 미확정 `0` 수급 원천 차단, 웹 대시보드 최대 60영업일 동적 윈도우 확장)**:
  1. **`[ISSUE-006]` 해결 (`run_daily_screener.py`, `README.md`)**:
     * `run_daily_screener.py` 1036행에 남아 있던 `shcode not in PRIORITY_SHCODES` 조건을 제거하여 `mcap_eok < 700.0` 종목 처리 시 발생하던 `NameError`를 수정하고 `README.md` 내 잔존 설명도 정리.
  2. **`[ISSUE-007]` 해결 (`run_daily_screener.py`, `test_screener_verification.py`)**:
     * 1번째 종목 처리 후 `latest_trade_date`가 당일(`T`)로 갱신되면서 2번째 종목(`chart_latest = T-1`)부터 `already_has_2yr = False`로 판정되어 매일 전 종목 25페이지(500일) 재백필로 빠지던 문제를 해결하기 위해, `has_2yr_history`(`min_target_date = today - 20일`)와 `is_latest_supply_unsettled`를 명확히 분리.
     * 이미 2년치 히스토리가 적재된 종목은 평일 `daily` 모드에서 **1페이지(최근 25영업일)** 고속 증분만 수행하도록 수정.
  3. **`[ISSUE-008]` 해결 (`run_daily_screener.py`, `index.html`, `test_screener_verification.py`)**:
     * 장중(수급 확정 전) `t1717` 호출 시 당일 모든 투자주체 수급이 `0`으로 반환되는 미확정 더미 행을 `is_unsettled_supply_row()`로 감지하여 `fetch_investor_supply()`에서 적재를 차단.
     * `supabase_get_stock_data_status_detail()`에서 DB 최신 수급 행의 미확정 여부(`is_latest_supply_unsettled`)를 감지하여 미확정 행이 있는 종목은 스킵하지 않고 장 마감 후 1페이지 고속 증분으로 덮어쓰도록 보강하고, 기존 적재된 미확정 행을 일괄 정리하는 `supabase_cleanup_unsettled_supply()` 추가.
     * `index.html`에서도 `isSettledSupplyRow()` 필터와 확정 수급 기준 최신 거래일 쿼리를 적용하여 장중 실행 중에도 최근 확정 거래일 기준 기관 수급이 정상 표시되도록 개선.
  4. **`[ISSUE-009]` 해결 (`index.html`, `run_daily_screener.py`)**:
     * `index.html` 상단 유니버스 안내 문구를 `시가총액 ≥ 700억 전수 (약 1,463종목)`으로 업데이트하고, 사용자가 `setPeriod(days)`에서 15영업일 초과(최대 60영업일) 기간을 입력할 때 `LOADED_LOOKBACK_DAYS`를 비교하여 부족한 과거 윈도우를 Supabase에서 동적으로 추가 로드하도록 개선.
     * `run_daily_screener.py --mode verify`(`verify_supabase_data`)에서 최신 확정 거래일 기준 `order=inst_vol_ratio.desc` 정렬 조회 및 `AC-1 ~ AC-5` 핵심 정합성 지표 출력을 복원.
  5. **`[ISSUE-010]` 해결 (`README.md`)**:
     * `.github/workflows/daily_batch.yml`의 실제 입력 파라미터(`mode`, `max_stocks`)와 CLI 전용 분할 옵션(`--chunk`, `--start-idx`, `--end-idx`) 안내를 일치하도록 `README.md` 정비.
* **2026-11-11 (v1.4.2 — 불필요한 최우선 레퍼런스 종목(`PRIORITY_SHCODES`, `_prioritize_candidates`) 루틴 제거 및 단순화)**
* **2026-11-11 (v1.4 — `STRATEGY.md` 0절 6대 필수 아키텍처 수정: 시총 700억 이상 전수 유니버스 & 2년치 500영업일 백필 구현)**
* **2026-11-11 (v1.3 — 3원화 대화창 파일 연동(`STRATEGY.md`, `README.md`, `TEST_REPORT.md`) 표준 체계 구축)**
* **2026-11-11 (v1.2 — 웹 대시보드 최신 거래일 페이지네이션 및 1:1 매칭 패치)**
* **2026-11-11 (v1.1 — 실데이터 적재 및 텔레그램 알림 연동 완료)**
* **2026-11-11 (v1.0 — 초기 아키텍처 구축)**
