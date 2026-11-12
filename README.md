# 📈 LS증권 Open API 기반 기관·외국인 수급 & EMA 스크리닝 시스템 (`ls-stock-screener`)

야간시장(NXT) 마감 이후 **매일 밤 21:05(KST)** GitHub Actions에서 자동으로 LS증권 Open API를 호출하여 **코스피·코스닥 시가총액 700억 원 이상 보통주 전수(약 1,477종목)**의 **2년치(약 500영업일) 수정주가 일봉 차트 + 지수이동평균(EMA 5, 20, 60, 120, 240)** 및 **투자주체별 수급(수량·금액)**을 수집하고, **Supabase 클라우드 DB** 업데이트와 **텔레그램 알림 발송** 및 **실시간 웹 대시보드 시각화**를 수행하는 시스템입니다.

---

## 🤝 3원화 대화창 협업 워크플로우 (`StudyRemote` 운영 규칙)

본 프로젝트는 역할이 분리된 3개의 대화창을 통해 파일 기반으로 유기적으로 운영됩니다:

1. **[전략 개발] 대화창**:
   * 주식 종목 발굴 전략 및 수급·차트 알고리즘 기획 전담 (`STRATEGY.md`에 기록 및 최신화)
2. **[프로그램 개발 및 수정(메인)] 대화창**:
   * **[작업 시작 전 - 읽을 파일]**: 항상 `git pull`을 먼저 실행한 뒤 `STRATEGY.md`(설계된 전략·수식·요구사항)와 `TEST_REPORT.md`(보고된 버그·수정 요청)를 읽고 작업 파악 (`STRATEGY.md`는 임의 수정 금지)
   * **[작업 완료 후 - 작성할 파일]**: 실제 프로그램 소스코드 구현/수정 후 `README.md`의 (1) 개발 환경 및 폴더 구조, (2) 실행 방법, (3) 하단 `최근 수정 내역(Changelog)`을 최신 상태로 업데이트하고, `TEST_REPORT.md`의 해결된 버그 항목을 `[해결 완료]`로 표시한 뒤 `git commit` 및 `git push` 수행
3. **[검증 및 테스트] 대화창**:
   * `README.md`, `STRATEGY.md`와 최신 커밋을 바탕으로 테스트(`test_screener_verification.py`, `run_daily_screener.py --mode verify`) 실행 및 `TEST_REPORT.md`에 합격 기준(`AC-1` ~ `AC-6`) 검증 결과·수정 요청 작성

---

## 🖥️ 1. 개발 및 운영 환경 및 폴더 구조 (Environment & Directory Structure)

### 1.1 기술 스택 및 운영 환경

| 구분 | 상세 환경 및 구성 |
| :--- | :--- |
| **OS / 실행 환경** | Linux (Debian 12 / GitHub Actions `ubuntu-latest`, 단일 Job 최대 360분 타임아웃) |
| **Backend 언어** | **Python 3.11+** (외부 pip 패키지 의존성 없이 표준 라이브러리 `urllib`, `json`, `ssl`, `datetime`, `argparse`만으로 동작하여 이식성 극대화) |
| **증권사 API** | **LS증권 Open API** (`https://openapi.ls-sec.co.kr:8080`) — OAuth2 토큰 자동 발급/갱신 및 TR(`t8436`, `t1444`, `t1463`, `t1102`, `t8410`, `t1717`) 호출 |
| **Database** | **Supabase (PostgreSQL + PostgREST)** (`https://rwvvrtjsxzecmdykwrxg.supabase.co`, 약 1,477종목 × 500영업일 ≈ 테이블당 70만 행 규모 지원) |
| **Frontend 대시보드** | HTML5 + TailwindCSS (CDN) + HTML5 Canvas 2D (`index.html`) — GitHub Pages 배포 (`https://minseok2995-ai.github.io/ls-stock-screener/`) |
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
├── STRATEGY.md                      # [전략 개발] 창 관리 (임의 수정 금지): 종목 발굴 전략 및 데이터 요구사항 명세서 (SSOT)
├── TEST_REPORT.md                   # [검증 및 테스트] 창 관리: AC-1~AC-6 검증 리포트 및 버그/수정 요청 트래커
├── run_daily_screener.py            # 메인 백엔드: 1,463종목 유니버스 산출, 2년치(500일) 일봉·수급 슬라이딩 수집, 스마트 이어받기, AC 검증
├── index.html                       # 실시간 웹 대시보드: 70만 행 DB 인덱스 윈도우 동적 필터링 및 1,463종목 실시간 스크리닝
├── supabase_schema.sql              # Supabase 테이블(3종), 인덱스, 뷰, RPC 함수(get_screened_stocks) 생성 SQL 스키마
├── test_screener_verification.py    # 5단계 핵심 로직(유니버스·미완성감지·EMA·t1717 역순 페이지네이션·스마트 Resume & 장중 미확정 수급 방어) 단위 테스트
└── .gitignore                       # Python 캐시(__pycache__) 등 버전 관리 제외 설정
```

---

## 🎯 2. 적용된 핵심 전략 및 데이터 수집 아키텍처 (`STRATEGY.md` 준수)

1. **분석 대상 유니버스 (시총 700억 이상 보통주 전수 — 약 1,463종목)**:
   * 코스피(`KOSPI`) + 코스닥(`KOSDAQ`) 통합 보통주 (`t8436` 마스터 기준)
   * 제외 대상: ETF, ETN, ELW, 스팩(`SPAC`), 리츠(`REITs`), 우선주, 인버스/레버리지/선물/채권형
   * **수집 단계 거래대금 사전 차단 제거**: `market_cap_eok >= 700.0`인 모든 보통주를 거래대금 규모와 무관하게 `stocks_master`(`is_universe = True`)에 100% 편입하고 일봉·수급을 적재합니다 (`avg_val_20d_eok`는 계산하여 기록하되 사전 탈락시키지 않음).
   * **불완전 유니버스 고착화 자동 복구 (`is_quarterly_rebuild_due`)**: `stocks_master` 내 유니버스 종목 수가 `1,200종목` 미만이면 자동으로 `t1444` 전수 시가총액 산출 모드로 전환하여 약 1,463종목 전체를 선등록합니다.
2. **2년치(약 500영업일) 차트(`daily_chart`) 및 수급(`daily_investor_supply`) 전수 확보**:
   * **`daily_chart`**: `t8410`에서 `start_date = today - 760일`, `qrycnt = 500`, `sujung = "Y"`(수정주가)로 최근 2년치(약 480~500영업일)를 수집하고, 500영업일 전체 시계열로 `ema_5`, `ema_20`, `ema_60`, `ema_120`, `ema_240`을 계산한 뒤 **절단 없이 500영업일 전체를 Upsert**합니다.
   * **`daily_investor_supply`**: `t1717`의 1회 호출 제한(25~30영업일)을 해결하기 위해 `oldest_date - 1일`로 `todt`를 역순 이동하는 **날짜 슬라이딩 연속조회(Pagination, 최대 25페이지)**를 구현하여 2년치(약 500영업일) 수급을 전수 수집하고 `daily_chart`의 동일 `trade_date` 거래량·종가와 1:1 매칭합니다.
   * **장중 미확정(`전 주체 0`) 수급 방어**: 장중(투자자별 확정 수급 집계 전)에 `t1717`이 반환하는 당일 `0` 수급 더미 행은 `is_unsettled_supply_row()`로 적재를 원천 차단하며, 이미 적재된 장중 미확정 행도 `supabase_cleanup_unsettled_supply()` 및 `supabase_get_stock_data_status_detail()`에서 감지하여 장 마감 후 확정 데이터로 덮어씁니다.
   * **평일 `daily` 모드 최적화**: `has_2yr_history`(최근 20일 내 데이터 보유 & 400영업일 이상 적재) 판정과 당일 확정 여부를 분리하여, 이미 2년치 히스토리가 구축된 종목은 평일 `daily` 실행 시 최근 25영업일(1페이지)만 약 1.1초 만에 고속 증분 Upsert하며, 2년치 미적재 종목만 2년치 전체 백필을 수행합니다.
3. **대량 백필 중단 방지 (스마트 이어받기 `--skip-existing` & CLI 구간 분할 `--chunk`)**:
   * `backfill` 실행 시 각 종목의 DB 적재 상태(`chart_cnt`, `supply_cnt`, `latest_date`, `is_latest_supply_unsettled`)를 확인하여 이미 2년치(400영업일 이상)가 확정 적재된 종목은 API 호출 없이 즉시 건너뛰어(Skip), 중간 타임아웃 후 재실행 시에도 끊긴 지점부터 100% 완주합니다.

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

# 6) [데이터 정합성(AC-1~AC-5) 및 기관 수급 상위 종목 검증 리포트 출력]
python3 run_daily_screener.py --mode verify
```

### 3.2 단위·통합 검증 테스트 스위트 실행 (`[검증 및 테스트]` 대화창용)

```bash
# 5대 핵심 로직(보통주 필터, 1200종목 미만 미완성 유니버스 감지, EMA/순수기관 수식, t1717 역순 슬라이딩 페이지네이션 & 장중 미확정 0수급 차단, 스마트 이어받기) 검증
python3 test_screener_verification.py
```

### 3.3 GitHub Actions 수동/자동 실행 방법
* **2년치 백필 실행**: GitHub 저장소 → **Actions** 탭 → **Daily LS Stock Supply & Chart Batch Update** → **Run workflow** 클릭 → `mode: backfill`, `max_stocks: 0` 선택 후 실행 (`timeout-minutes: 360` 단일 Job 최대 6시간 적용, 중단 시 재실행하면 `--skip-existing` 스마트 이어받기로 자동 완주).
* **정기 일일 배치**: 평일(월~금) **밤 21:05 KST (`UTC 12:05`)**에 자동 실행.

---

## 📝 4. 최근 수정 내역 (Changelog)

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
     * `run_daily_screener.py --mode verify`(`verify_supabase_data`)에서 최신 확정 거래일 기준 `order=inst_vol_ratio.desc` 정렬 조회 및 `AC-1 ~ AC-5` 핵심 정합성 지표(시총 700억 이상 유니버스 수, 거래대금 20억 미만 종목 포함 수, 5대 대형주 500일 적재 현황, 태광 `2026-08-25` 및 대한유화 `2026-11-03` 검증) 출력을 복원.
  5. **`[ISSUE-010]` 해결 (`README.md`)**:
     * `.github/workflows/daily_batch.yml`의 실제 입력 파라미터(`mode`, `max_stocks`)와 CLI 전용 분할 옵션(`--chunk`, `--start-idx`, `--end-idx`) 안내를 일치하도록 `README.md` 정비.
* **2026-11-11 (v1.4.2 — 불필요한 최우선 레퍼런스 종목(`PRIORITY_SHCODES`, `_prioritize_candidates`) 루틴 제거 및 단순화)**:
  * 시가총액 700억 원 이상 보통주 전체에 대한 수급·차트 데이터 구축 및 기관 수급 발생 종목 표시에 집중하도록, 특정 종목을 하드코딩하여 우선 수집·검증하던 `PRIORITY_SHCODES` 및 `_prioritize_candidates()` 루틴을 `run_daily_screener.py`와 `test_screener_verification.py`에서 전면 제거.
  * 시가총액 700억 이상 보통주 전 종목을 시가총액 순(동일 기준)으로 일관되게 수집·갱신하도록 단순화.
* **2026-11-11 (v1.4 — `STRATEGY.md` 0절 6대 필수 아키텍처 수정: 시총 700억 이상 전수 유니버스 & 2년치 500영업일 백필 구현)**:
  1. **[수정 1] 시총 700억 이상 보통주 전수(1,463종목) 편입 및 거래대금 사전 차단 제거 (`run_daily_screener.py`)**:
     * 수집 루프 내 `if avg_val_20d_eok < 20.0: continue` 사전 차단 코드를 제거하여 거래대금 20억 미만 중소형 보통주도 누락 없이 DB에 적재되도록 수정.
     * `is_quarterly_rebuild_due()`에서 DB 내 유니버스 종목 수가 `1,200종목` 미만(기존 247종목)일 때 자동으로 `t1444` 전수 추출을 재수행하도록 개선하고, 추출 즉시 `stocks_master`에 전체 유니버스 종목을 선등록하도록 보강.
     * `supabase_fetch_existing_masters()`에 1,000건 단위 페이지네이션을 적용하여 마스터 종목을 전수 조회하도록 수정.
  2. **[수정 2] `daily_chart` 2년치(500영업일) 전수 적재 (`run_daily_screener.py`)**:
     * `fetch_daily_chart()`가 `start_date = today - 760일`, `count = 500`으로 2년치 수정주가 일봉을 수집(1회 미달 시 역순 연속조회 포함)하고, 기존의 `enriched_charts[-60:]` 절단 로직을 폐기하여 500영업일 전체 시계열과 EMA(5·20·60·120·240)를 `daily_chart`에 Upsert하도록 수정.
  3. **[수정 3] `daily_investor_supply` 2년치(500영업일) 역순 날짜 슬라이딩 연속 수집 (`run_daily_screener.py`)**:
     * `fetch_investor_supply()`에 `oldest_date - 1일`로 `todt`를 이동하며 최대 25페이지까지 반복 호출하는 역순 슬라이딩 페이지네이션을 구현하여 2년치(약 500영업일) 수급을 전수 수집하도록 수정.
     * 평일 `daily` 모드에서는 이미 2년치가 적재된 종목은 1페이지(최근 25영업일)만 고속 증분 수집하고, 미적재 종목은 자동으로 2년치 전체 백필을 수행하도록 최적화.
  4. **[수정 4] 대량 적재 스마트 이어받기(`--skip-existing`) 및 구간 분할(`--start-idx`, `--end-idx`, `--chunk`) 추가**:
     * `is_stock_already_backfilled()`를 통해 이미 2년치(차트·수급 각 400영업일 이상 또는 신규상장 전 기간)가 적재된 종목은 재실행 시 즉시 스킵하고, 기존 60일/25일만 적재된 247종목은 자동으로 2년치 재백필 대상이 되도록 구현.
     * `supabase_upsert()`를 500건 단위 청크 및 3회 자동 재시도 로직으로 보강하고, 345분 실행 시간 안전 가드(`--max-runtime-minutes`) 추가.
  5. **[수정 5] GitHub Actions 워크플로우 타임아웃 확장 (`.github/workflows/daily_batch.yml`)**:
     * `timeout-minutes: 45`를 단일 Job 최대치인 `timeout-minutes: 360`(6시간)으로 상향.
  6. **[수정 6] 대용량 DB(70만 행) 대응 웹 대시보드(`index.html`) 및 검증(`--mode verify`) 쿼리 최적화**:
     * `index.html`에서 `stocks_master`를 3페이지 병렬 조회(`fetchAllUniverseMasters`)하여 전체 유니버스를 전수 로드하고, `daily_chart` 및 `daily_investor_supply`는 `trade_date=gte.{cutoffDate}` 인덱스 필터와 멀티 웨이브 병렬 페이지네이션(`fetchRecentWindowPagesDesc`)을 적용하여 70만 행 테이블에서도 최근 15영업일 수급·차트를 절단 없이 즉시 조회하도록 최적화.
     * 개별 종목 선택 시 `ensureStockFullChart()`가 최근 240영업일 일봉을 온디맨드 조회하여 렌더링하도록 확장.
* **2026-11-11 (v1.3 — 3원화 대화창 파일 연동(`STRATEGY.md`, `README.md`, `TEST_REPORT.md`) 표준 체계 구축)**
* **2026-11-11 (v1.2 — 웹 대시보드 최신 거래일 페이지네이션 및 1:1 매칭 패치)**
* **2026-11-11 (v1.1 — 실데이터 적재 및 텔레그램 알림 연동 완료)**
* **2026-11-11 (v1.0 — 초기 아키텍처 구축)**
