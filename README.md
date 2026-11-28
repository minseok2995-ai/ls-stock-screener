# 📈 LS증권 Open API 기반 기관 수급 · 양극 추세 사이클 스크리너 (`ls-stock-screener`)

정규장 마감 직후 **평일 `16:05 KST` (`[1차 정규장 가집계]` `prelim`)** 및 야간시장(NXT, `20:00 KST` 종료) 마감·정산 이후 **평일 `20:30 KST` (`[2차 최종 확정]` `final`)** 하루 2회 **무결점 스케줄 아키텍처**(Google Apps Script 정각 웹훅 `16:05`·`20:30 KST` + GitHub Actions 슬롯별 핵심 백업 `16:25`·`20:47 KST` + `v3.1` 비허용 시간대[`00:00~15:44`·`19:00~20:04 KST`·주말] 0.1초 무음 스킵 + `--skip-if-completed` 98.5% 완주 멱등성 가드 + 실패 경보)로 자동 기동되어, **코스피·코스닥 시가총액 700억 원 이상 보통주 전수(약 1,466종목)**의 **수정주가 일봉 차트(기본 5년+) + 지수이동평균(EMA 5, 20, 60, 120, 240)**, **투자주체별 확정 수급(기본 3년+)**, **양극 추세 사이클(16단계·63세부현황) 및 일일 수급 정량·사후 복기(`daily_supply_analysis`, `v3.2` 기준 Gemini AI 코멘트 추출 기본 중단·온디맨드 재개 지원)**를 수집·분석하여 **Supabase 클라우드 DB** 적재, **텔레그램 요약·장애 알림 발송**, **3페이지 실시간 웹 매매 관리 대시보드(`수급 스크리너` · `관심종목` · `보유종목`) 시각화 및 엑셀(`.xlsx`) 다운로드**를 수행하는 시스템입니다.

---

## 🤝 3원화 대화창 협업 워크플로우 (`StudyRemote` 운영 규칙)

본 프로젝트는 역할이 분리된 3개의 대화창을 통해 파일 기반으로 유기적으로 운영됩니다:

1. **[전략 개발] 대화창**:
   * 주식 종목 발굴 전략 및 수급·차트·추세 사이클·배치 아키텍처 기획 전담 (`STRATEGY.md`에 기록 및 최신화)
2. **[프로그램 개발 및 수정(메인)] 대화창**:
   * **[작업 시작 전 - 읽을 파일]**: 항상 `git status` 및 `git pull`을 먼저 실행한 뒤 `STRATEGY.md`(설계된 전략·수식·요구사항)와 `TEST_REPORT.md`(보고된 버그·수정 요청)를 읽고 작업 파악 (`STRATEGY.md`는 임의 수정 금지)
   * **[작업 완료 후 - 작성할 파일]**: 실제 프로그램 소스코드 구현/수정 및 테스트 검증 후 `README.md`의 (1) 개발 환경 및 폴더 구조, (2) 실행 방법, (3) 적용된 전략 요약, (4) 하단 `최근 수정 내역(Changelog)`을 최신 상태로 상세히 업데이트하고, `TEST_REPORT.md`의 해결된 버그 항목이 있으면 `[해결 완료]`로 표시한 뒤 `git commit`·`git push` 및 `[검증 및 테스트]` 전달용 지시서 작성 수행
3. **[검증 및 테스트] 대화창**:
   * `README.md`, `STRATEGY.md`와 최신 커밋을 바탕으로 전체 테스트 스위트(`test_screener_verification.py`, `tests/test_*.py`, `run_daily_screener.py --mode verify`) 실행 및 `TEST_REPORT.md`에 합격 기준(`AC-1` ~ `AC-73`) 검증 결과·수정 요청 작성

---

## 🖥️ 1. 개발 및 운영 환경 및 폴더 구조 (Environment & Directory Structure)

### 1.1 기술 스택 및 운영 환경

| 구분 | 상세 환경 및 구성 |
| :--- | :--- |
| **OS / 실행 환경** | Linux (Ubuntu 24.04 / GitHub Actions `ubuntu-latest`, 단일 Job 최대 360분 타임아웃, `KST = UTC+9` 코드 레벨 표준시 고정) |
| **Backend 언어** | **Python 3.11+** (외부 pip 패키지 의존성 없이 표준 라이브러리 `http.client`, `urllib`, `json`, `ssl`, `gzip`, `datetime`, `argparse`, `concurrent.futures`, `threading`만으로 동작) |
| **증권사 API** | **LS증권 Open API** (`https://openapi.ls-sec.co.kr:8080`) — OAuth2 토큰 자동 발급/80분 주기 갱신 및 TR(`t8436`, `t1444`, `t1463`, `t1102`, `t8410`, `t1717`) 영구 Keep-Alive + 서버 바닥 정속 페이서(`t8410: 1.04s`, `t1717: 0.54s`) 호출 |
| **AI 요약 엔진 (`v3.2`)** | **Google Gemini REST API** (`gemini-3.5-flash-lite` 기본 모델, **`DEFAULT_AI_TOP_N = 0` 기본 추출 중단[API 호출 `0회`]** — DB 컬럼 4종·함수·과거 이력 보존, `AI_TOP_N=10` 환경변수/Repository Variable 지정 시 무코드 즉시 재개) |
| **Database** | **Supabase (PostgreSQL + PostgREST)** (`https://rwvvrtjsxzecmdykwrxg.supabase.co`, 7개 테이블: `stocks_master`, `daily_chart`[5년+], `daily_investor_supply`[3년+], `daily_supply_analysis`[365일 보관], `watchlist_items`, `portfolio_holdings`, `excluded_stocks`) |
| **Frontend 대시보드** | HTML5 + TailwindCSS (CDN) + SheetJS (`xlsx-0.20.3` CDN, 9열 `.xlsx` 다운로드) + HTML5 Canvas 2D 프로 차트 (`index.html`, `watchlist.html`, `holdings.html`, `common.js`) — GitHub Pages 배포 (`https://minseok2995-ai.github.io/ls-stock-screener/`) |
| **배치 스케줄러 (v3.1)** | **주 스케줄러**: Google Apps Script 정각 웹훅 (`16:05 KST` `prelim` + `20:30 KST` `final`, `scripts/trigger_daily_batch.gs`)<br/>**보조 백업**: GitHub Actions 내장 Cron 2개 (`16:25 KST` `'25 7 * * 1-5'` + `20:47 KST` `'47 11 * * 1-5'`, `.github/workflows/daily_batch.yml`) + `is_allowed_auto_batch_window` 비허용 시간대 무음 차단 + `concurrency` 직렬화 |
| **알림 채널** | **Telegram Bot HTTP API** (`@my_ls_stock_bot`, 기본 수신 `TELEGRAM_CHAT_ID: 1018392459` — 정상 완료 리포트[Markdown 400 자동 평문 폴백, `0종목` 공회전 발송 차단] 및 `if: failure()` 즉시 장애 경보) |

### 1.2 필수 및 선택 환경변수 (GitHub Repository Secrets / Variables / 로컬 환경변수)

| 변수명 | 구분 | 필수 여부 | 설명 |
| :--- | :---: | :---: | :--- |
| `LS_APP_KEY` | Secret | 필수 | LS증권 Open API App Key |
| `LS_APP_SECRET` | Secret | 필수 | LS증권 Open API Secret Key |
| `SUPABASE_URL` | Secret | 선택 (기본값 내장) | Supabase 프로젝트 URL (`https://rwvvrtjsxzecmdykwrxg.supabase.co`) |
| `SUPABASE_KEY` | Secret | 선택 (기본값 내장) | Supabase API Key (Publishable Key 또는 Service Role Key) |
| `TELEGRAM_BOT_TOKEN` | Secret | 필수 (알림용) | 텔레그램 봇 HTTP API 토큰 |
| `TELEGRAM_CHAT_ID` | Secret | 선택 (기본값 내장) | 텔레그램 수신자 Chat ID (기본값: `1018392459`) |
| `GEMINI_API_KEY` | Secret | 선택 (재개 대비 보존) | Google Gemini API Key (`AI_TOP_N > 0` 지정 시에만 사용, 기본 `AI_TOP_N=0` 상태에서는 호출 `0회`) |
| `GEMINI_MODEL` | Variable | 선택 (기본값 내장) | Gemini 모델명 (기본값: `gemini-3.5-flash-lite`) |
| `AI_TOP_N` | Variable | 선택 (기본값 `0`) | `final` 슬롯 AI 요약 생성 상위 종목 수 (**`v3.2` 기본값: `0` [추출 중단]**, 재개 시 `10` 등 양수 지정; `0`일 때도 정량 상위 Top 10 `is_top_pick=True`는 그대로 유지) |

### 1.3 프로젝트 폴더 및 파일 구조

```text
ls-stock-screener/
├── .github/
│   └── workflows/
│        └── daily_batch.yml                       # [v3.1/v3.2] 평일 16:25·20:47 KST 2중 백업 Cron + AI_TOP_N 기본 '0' + 직렬화 + 실패 경보
├── scripts/
│   ├── trigger_daily_batch.gs                     # 평일 16:05(prelim)·20:30(final) KST 정각 GitHub workflow_dispatch 외부 웹훅 (Google Apps Script)
│   ├── ls_realtime_bridge.py                      # [v2.7] 로컬 LS 실시간 시세 브리지 서버 (127.0.0.1:8765, 표준 라이브러리 전용)
│   ├── migration_v24_watchlist_holdings.sql       # [v2.4] 관심종목·보유종목·영구제외 3개 테이블 DDL 및 권한 부여 SQL
│   ├── migration_v29_daily_supply_analysis.sql    # [v2.9] 일일 수급 정량·AI·복기 테이블(daily_supply_analysis) DDL
│   ├── migration_v30_trend_cycle.sql              # [v3.0] 양극 추세 사이클(trend_camp/stage/detail 등) 컬럼 확장 DDL
│   └── sync_common_sql.py                         # SQL 변경분을 common.js(MIGRATION_SQL 상수)에 동기화하는 유틸리티
├── tests/
│   ├── test_v2_acceptance.py                      # AC-7 ~ AC-18 프론트엔드·워크플로우·멱등성·자격 경계·9열 엑셀 회귀 검증
│   ├── test_v23_acceptance.py                     # AC-19 ~ AC-23 차트 5년·수급 3년 확장·probe_10y·앵커 EMA·양보/체인 가드 검증
│   ├── test_v24_watchlist_holdings.py             # AC-24 ~ AC-29 3페이지 매매관리·스마트 병합·목표가/청산·텔레그램 400 폴백 검증
│   ├── test_v25_pattern_chart.py                  # AC-30 ~ AC-38 패턴·캔들·지표 엔진, 100점 종합판단, 프로 차트·와이드 UI 검증
│   ├── test_v26_acceptance.py                     # AC-39 ~ AC-43 1일 2회 배치 슬롯, 패턴 상시 표기, 역배열 추세돌파, 초슬림 리스트 검증
│   ├── test_v27_acceptance.py                     # AC-44 ~ AC-48 실시간 시세 엔진(4-Tier), 장전/휴일 가짜봉 방어, 프로 차트 실시간 봉 검증
│   ├── test_v28_batch_perf.py                     # AC-49 ~ AC-56 Keep-Alive 풀, PK 청크 프리페치, TR 서버 바닥 페이서, 50종목 버퍼 검증
│   ├── test_v29_daily_analysis.py                 # AC-57 ~ AC-60 일일 수급 정량 스코어링, Gemini Top N, 5/10/20일 사후 복기 백필 검증
│   ├── test_v30_trend_cycle.py                    # AC-61 ~ AC-66 양극 추세 사이클(16단계·63세부현황) Python↔JS 패리티·3단 UI·호버 검증
│   ├── test_v301_fixes.py                         # ISSUE-023 ~ 028 스냅샷 컬럼 격리·잔존행 정리·750봉 윈도우 통일·PGRST204 폴백 검증
│   ├── test_v31_batch_schedule.py                 # AC-67 ~ AC-71 비허용 시간대 무음 차단·유니버스 700억 유지/분기 탈락·409 복구·신규상장 백필·2중 백업 크론 검증
│   └── test_v32_gemini_pause.py                   # [v3.2] AC-72 ~ AC-73 Gemini AI 기본 중단(DEFAULT_AI_TOP_N=0)·Top 10 유지·DB/함수 보존·양수 지정 재개 검증
├── README.md                                      # [프로그램 개발 및 수정] 창 관리: 환경, 폴더 구조, 실행 방법, 적용 전략 및 최근 수정 내역(Changelog)
├── STRATEGY.md                                    # [전략 개발] 창 관리 (임의 수정 금지): 종목 발굴 전략 v1.4 ~ v3.2 명세서 (SSOT)
├── TEST_REPORT.md                                 # [검증 및 테스트] 창 관리: AC-1 ~ AC-73 검증 리포트 및 버그/수정 요청 트래커
├── run_daily_screener.py                          # 메인 백엔드: v3.1 오프아워 가드·유니버스·일봉/수급 고속 수집·양극 추세 사이클·일일 정량/AI(기본중단)/복기
├── index.html                                     # [페이지 1] 기관 수급 스크리너: 양극 추세 3단 드릴다운 UI, 수급 자격 필터, AI 브리핑, 프로 차트, 9열 엑셀
├── watchlist.html                                 # [페이지 2] 관심종목 작전판: A/B 등급, 100점 종합판단, 수급·기준저가·눌림 배지, 보유편입
├── holdings.html                                  # [페이지 3] 보유종목 & 청산 히스토리: 실시간 손익, 목표가·20일선 청산 알림, 누적 승률 요약
├── common.js                                      # 3페이지 공통: PostgREST 헬퍼, 실시간 시세 엔진, 패턴·지표·양극 추세 사이클 엔진, 프로 차트
├── supabase_schema.sql                            # Supabase 전체 테이블·인덱스·뷰·권한 통합 스키마
├── test_screener_verification.py                  # 핵심 백엔드 8개 단위 테스트 (유니버스·EMA·t1717·스마트 이어받기·Strategy v2·KST/멱등성)
└── .gitignore                                     # Python 캐시(__pycache__) 등 버전 관리 제외 설정
```

---

## 🎯 2. 적용된 핵심 전략 및 무결점 배치 아키텍처 요약 (`v2.0` ~ `v3.2`)

### 2.1 데이터 구축 및 분기 유니버스 정합성 원칙 (`v1.4` ~ `v3.1`)
1. **분석 대상 유니버스 (시총 700억 이상 보통주 전수 — 약 1,466종목)**:
   * 코스피(`KOSPI`) + 코스닥(`KOSDAQ`) 통합 보통주 (`t8436` 마스터 기준, ETF/ETN/ELW/스팩/리츠/우선주/인버스/레버리지 제외).
   * **분기 정기 재산출 (`3·6·9·12월` 첫 거래일, `rebuild_due == True`)**: 전 종목 시가총액을 재산출하여 `700억 이상` 종목은 `is_universe=True`로 선등록하고, 기준 미달 탈락 구 유니버스 종목은 외래키(`ON DELETE CASCADE`) 보존을 위해 **`DELETE` 없이 `is_universe=False`로 동기화 Upsert**합니다 (`v3.1`, KST 월 기준 판별 및 일괄 프리페치 지원).
   * **평일 일일 증분 (`daily`, `rebuild_due == False`)**: 기존 분기 유니버스(`is_universe=True`) 종목이 분기 중 주가 하락으로 시가총액 `700억 미만`이 되더라도 건너뛰지 않고 차트·수급·마스터를 끝까지 정상 적재하여 완주율 **`99.9%+ (>= 98.5%)`** 를 유지합니다. 당일 거래대금 상위(`t1463`)에서 포착된 신규 `700억 이상` 급등주는 루프 진입 전 `stocks_master`에 시드(`updated_at='1970-01-01T00:00:00+09:00'`)를 선등록하여 외래키 `HTTP 409` 충돌 없이 즉시 편입합니다 (`v3.1`).
2. **순수 기관(`real_inst`) 정의**:
   * 단기 차익·LP 물량 왜곡이 있는 **금융투자(`fn_inv`)를 제외**하고 **`투신 + 보험 + 은행 + 종금(기타금융) + 연기금 등 + 사모펀드`** 6대 주체만 합산합니다.
3. **기준 확정 거래일($T$) 산정 및 장전·장중 미확정 데이터 원천 차단**:
   * `fetch_latest_krx_trading_date()`가 장전 빈 더미 일봉(`jdiff_vol <= 0 and open <= 0`) 및 정규장 마감(`15:30 KST`) 이전 당일 봉을 제외하여 직전 확정 개장일만 반환하며 (`v3.1`), 모든 화면·수급 판정에 `trade_date <= T` 상한을 강제합니다.

### 2.2 수급 포착 자격 기준 및 양극 추세 사이클 (`v2.2` · `v3.0` · `v3.0.1` · `v3.2`)
1. **수급 자격 기준 (`v3.0` / `v3.0.1` 개정, `AC-62`)**:
   * **기본 유동성**: 당일 거래대금 $\ge 5$억 원 (`trading_value_m >= 500.0`) **필수**.
   * **기관 순매수 규모**: 당일 순수기관 순매수 금액 $\ge 3$억 원 (`real_inst_amt >= 300.0`) **또는** 시가총액 대비 $\ge 0.1\%$ (`real_inst_amt_eok >= market_cap_eok * 0.001 - 1e-9`) 충족 시 자격 통과 (`3일 연속 5% 이상`은 최근 3일 평균 기준 동일 적용).
   * **`[하락 추세 전환 수급 발생]`**: 60거래일 고점 대비 낙폭 $\le -15.0\%$, 20일 최저가 미이탈, 3거래일 연속 저점 지지 후 첫 순수기관 수급(`유형 A` 당일 $\ge 10\%$ / `유형 B` 3일 연속 $\ge 5\%$) 및 양봉·5일선 상회 종목 포착.
2. **양극 추세 사이클 엔진 (`16단계 · 63세부현황`, `v3.0` / `v3.0.1`, `AC-61 ~ AC-66`)**:
   * 기준일 $T$ 이하 **최근 `750영업일` 표준 윈도우**를 사용하여 Python 배치(`run_daily_screener.py`), `common.js`(`C.TrendCycle`), `index.html`(리스트·모달·최근 60봉 캔들 호버) 간 **불일치 `0건`** 결정론적 분류를 보장합니다.
   * **상승 진영(정배열·전환 `A-1 ~ A-8`)** 및 **하락·바닥 진영(역배열·침체 `B-1 ~ B-8`)** 총 16단계와 63개 세부현황 코드를 산출하며, `index.html`에서 `진영 탭 → 단계 필터 → 세부현황 배지` 3단 드릴다운 UI로 제공합니다.
3. **일일 수급 정량 분석 · Gemini AI 코멘트(기본 중단/무코드 재개) · 사후 복기 파이프라인 (`v2.9` ~ `v3.2`, `AC-57 ~ AC-63`, `AC-72`)**:
   * **Step 1 (`prelim` & `final` 공통)**: 수급 자격 통과 전 후보에 대해 100점 4축 정량 점수, `DEFAULT_TOP_PICK_LIMIT = 10` 기반 상위 10종목 `is_top_pick=True` 및 `daily_rank(1..N)`, 매수참고가·손절가·목표가(`+7% / +15%`), 유사 조건 과거 승률 및 추세 사이클을 `daily_supply_analysis`에 Upsert(동일 일자 탈락 잔존 행 자동 정리)하고, 전 유니버스 추세 컬럼만 `stocks_master`에 안전 스냅샷합니다.
   * **Step 2 (`final` 전용, `v3.2` 기본 중단)**: `DEFAULT_AI_TOP_N = 0` 및 `daily_batch.yml` 기본값 `'0'` 설정으로 평소에는 **Gemini API 호출 `0회`** 및 추가 Upsert 없이 전 행 `ai_status = 'SKIPPED'`로 즉시 통과합니다 (`index.html`은 `SUCCESS`일 때만 AI 카드를 렌더링하므로 자동 숨김). DB 컬럼 4종(`ai_model`, `ai_status`, `ai_summary`, `ai_generated_at`)·과거 적재 데이터·호출 함수는 보존되어 추후 `AI_TOP_N=10` 지정만으로 무코드 즉시 재개됩니다.
   * **Step 3 (`final` 전용)**: 과거 포착 종목의 `5일/10일/20일` 사후 수익률 및 `10일` 장중 최대수익·최대낙폭을 자동 백필(과거 `ai_summary` 보존)하고 `365일` 초과 이력을 정리합니다.

### 2.3 초고속 배치 파이프라인 (`v2.8 ~ v2.8.2`) 및 1일 2회 무결점 스케줄 아키텍처 (`v3.1`, `AC-67 ~ AC-71`)
1. **초고속 수집·적재 엔진 (`~29분` 내 1,466종목 완주)**:
   * `KeepAliveHttpPool` 영구 TLS 소켓 재사용, 50종목 복합 PK 인덱스 병렬 프리페치(`supabase_prefetch_daily_context`), `LSApiClient` 서버 물리 바닥 정속 페이서(`t8410: 1.04s`, `t1717: 0.54s`) + `t8410`‖`t1717` 2-스레드 병렬 수집, `BatchUpsertBuffer` 50종목 원자적 묶음 Upsert(`daily_chart → daily_investor_supply → stocks_master`, `HTTP 409` 발생 시 시드 선등록 후 단건 자가 복구).
   * 상장 `65영업일 이하` 신규 상장주(`1~399영업일`, 차트·수급 오차 5일 이내)를 백필 완료로 정확히 판정하고 초신규(`chart_cnt <= 5` 등 무앵커 단기 상장주)는 `105달력일(count=60)` 1페이지로 조회하여 매회 불필요한 전체 백필을 원천 차단합니다 (`v3.1`).
2. **1일 2회 무결점 자동 스케줄 방어 체계 (`v3.1`)**:
   * **허용 시간창 가드 (`is_allowed_auto_batch_window`)**: 자동 실행(`--mode daily --skip-if-completed`)은 오직 **평일 `15:45 ~ 18:59 KST`(`prelim` 창, 수능일 `17:05` 포함)** 및 **평일 `20:05 ~ 23:59 KST`(`final` 창)** 두 구간에서만 본 로직으로 진입하며, **평일 새벽·장중(`00:00 ~ 15:44 KST`)**, **야간장 진행 데드존(`19:00 ~ 20:04 KST`)**, **토·일요일 전 시간대**에 지연 발화된 크론은 LS API 인증·DB 조회·텔레그램 발송 없이 **0.1초 이내에 `[SKIP-OFFHOURS]` 무음 정상 종료(`Exit 0`)** 됩니다. *(수동 강제 실행 `skip_if_completed=false`는 시간 무관 언제든 동작)*
   * **완주 멱등성 가드 (`check_daily_batch_completion`)**: 대표 대형주 3종(`005930, 000660, 005380`) 확정 수급 존재 시 거래정지(`volume=0`) 및 극소량 개인 간 체결(`0 <= volume <= 100`, 일봉·수급 행 모두 존재) 종목까지 완료 집합에 포함하여 `>= 98.5%` 완주 시 5초 내 즉시 종료합니다.
   * **공회전 알림 차단**: LS 서버 점검 등으로 `universe_count == 0`인 경우 완료 텔레그램 및 DSA 분석을 생략합니다.

### 2.4 3페이지 실전 매매 관리 · 프로 차트 · 실시간 시세 (`v2.4 ~ v2.7.1`, `AC-24 ~ AC-48`)
* **3페이지 연동**: `index.html`(수급·추세 스크리너 & 관심종목 스마트 병합) / `watchlist.html`(관심종목 100점 4축 종합판단 `🔥 타점완성 / ⏳ 눌림대기 / 👀 관망유지 / ⚠️ 정리권고`) / `holdings.html`(보유종목 실시간 평가손익·청산 히스토리·누적 승률) + 전역 `🚫 제외관리` 모달.
* **프로 차트 & 실시간 시세**: 2단 캔들·EMA·볼린저·패턴 작도(VCP·플래그·쌍바닥·역H&S·하락채널)·기관수급/RSI 차트, `60/120/240/720일` 전환(750봉 윈도우), 캔들 호버 시점별 추세 배지, PNG 저장/클립보드 복사, 4-Tier 실시간 시세 엔진(`LiveQuoteManager`: 로컬 LS 브리지 → 네이버 JSONP → Supabase 일봉 → 메모리 캐시, 휴일·장전 가짜 봉 복제 차단).

### 2.5 전 종목 확장 백필 아키텍처 (`v2.3.1`, `AC-19 ~ AC-23`)
* 기본 차트 5년(`2021-11-01~`) · 수급 3년(`2023-11-01~`) 비대칭 확장 백필(`--mode backfill_10y`), 사전 실측 프로브(`--mode probe_10y`), 앵커 EMA 시드 이어받기, 최대 6회차 무중단 자동 체인 디스패치 및 평일 `15:55~16:45`·`20:10~21:20 KST` 일일 배치 양보 가드를 지원합니다.

---

## 🚀 3. 실행, 웹훅 트리거 설정 및 검증 방법 (Execution & Setup Guide)

### 3.1 로컬 / 서버 CLI 실행 명령어

```bash
# 1) 환경변수 설정 (v3.2 기준 AI_TOP_N 기본값은 0[중단]; AI 코멘트 추출 재개 시에만 export AI_TOP_N=10 지정)
export LS_APP_KEY="발급받은_LS_APP_KEY"
export LS_APP_SECRET="발급받은_LS_APP_SECRET"
export SUPABASE_URL="https://rwvvrtjsxzecmdykwrxg.supabase.co"
export SUPABASE_KEY="sb_publishable_vH_-2K-y5HwQ9oqiT1gtIw_P9pKdJ26"
export TELEGRAM_BOT_TOKEN="텔레그램_봇_토큰"
export TELEGRAM_CHAT_ID="1018392459"

# 2) [일일 증분 배치 — 수동 강제 실행] 시간대 무관 즉시 실행 (auto: 19:30 KST 미만 prelim / 이상 final)
python3 run_daily_screener.py --mode daily --batch-slot auto

# 3) [일일 증분 배치 — 자동 스케줄 무결점 모드]
#    - 비허용 시간대(평일 00:00~15:44 · 19:00~20:04 KST · 주말): 0.1초 내 [SKIP-OFFHOURS] 무음 종료(Exit 0)
#    - 허용 시간대 내 당일 98.5% 이상 완주 상태: 5초 내 [SKIP-COMPLETED] 즉시 종료(Exit 0)
#    - 미완주 상태: 미처리 종목만 고속 이어받기 수행
python3 run_daily_screener.py --mode daily --batch-slot auto --skip-if-completed

# 4) [분기 시가총액·유니버스 강제 재산출 / 2년치 백필]
python3 run_daily_screener.py --mode universe
python3 run_daily_screener.py --mode backfill

# 5) [빠른 샘플 테스트] 상위 10종목만 즉시 테스트
python3 run_daily_screener.py --mode daily --max-stocks 10

# 6) [데이터 정합성 및 스크리닝 검증 리포트 출력 (DB 읽기 전용, Exit 0)]
python3 run_daily_screener.py --mode verify

# 7) [LS 실서버 2016-01 차트·수급 사전 실측 프로브 및 차트 5년·수급 3년 확장 백필]
python3 run_daily_screener.py --mode probe_10y
python3 run_daily_screener.py --mode backfill_10y --max-runtime-minutes 320 --chart-start 2021-11-01 --supply-start 2023-11-01

# 8) [선택: 로컬 LS 실시간 시세 브리지 서버 기동]
python3 scripts/ls_realtime_bridge.py
```

### 3.2 단위·통합 검증 테스트 스위트 실행 (`[검증 및 테스트]` 대화창용)

```bash
# 1) 백엔드 8단계 핵심 단위 테스트 (유니버스·EMA·t1717·스마트 이어받기·Strategy v2·KST/멱등성)
python3 test_screener_verification.py

# 2) 전체 통합 회귀 + v3.1/v3.2 신규 검증 스위트 일괄 실행 (AC-7 ~ AC-73, 167개 테스트)
python3 -m unittest discover -s tests -v

# 3) v3.2 Gemini 기본 중단 검증 스위트 단독 실행 (AC-72 ~ AC-73, 4개 테스트)
python3 -m unittest tests/test_v32_gemini_pause.py -v

# 4) 운영 Supabase 읽기 전용 데이터 정합성 검증
python3 run_daily_screener.py --mode verify
```

### 3.3 평일 `16:05 KST` & `20:30 KST` 정각 외부 웹훅 트리거 설정 가이드 (`Google Apps Script`)

주 스케줄러인 Google Apps Script(`16:05 KST` `prelim` + `20:30 KST` `final`)와 GitHub Actions 보조 백업 크론(`16:25 KST` + `20:47 KST`)의 2중 체계로 운영됩니다:

1. **GitHub Fine-grained PAT 발급**: 대상 저장소 `minseok2995-ai/ls-stock-screener`, Repository permissions → `Actions: Read and write` 권한으로 토큰 발급.
2. **Google Apps Script 설정**: `https://script.google.com` → [`scripts/trigger_daily_batch.gs`](./scripts/trigger_daily_batch.gs) 코드 붙여넣기 → 프로젝트 설정(시간대 `GMT+09:00 서울`) → 스크립트 속성 `GITHUB_PAT` 저장.
3. **1일 2회 트리거 등록**: 편집기 상단 함수 선택에서 **`setupDaily1605And2030Triggers`** 실행 → 평일 `16:05 KST`(`prelim`) 및 `20:30 KST`(`final`) 트리거 2개가 자동 설정됩니다.

### 3.4 웹 대시보드 접속 및 DB 마이그레이션 안내
* **실시간 웹 대시보드**: `https://minseok2995-ai.github.io/ls-stock-screener/` (`index.html`) · `.../watchlist.html` · `.../holdings.html`
* **DB 스키마/마이그레이션**: 초기 구축 시 `supabase_schema.sql` 또는 버전별 증분 SQL(`scripts/migration_v24_watchlist_holdings.sql`, `scripts/migration_v29_daily_supply_analysis.sql`, `scripts/migration_v30_trend_cycle.sql`)을 Supabase SQL Editor에서 실행합니다 (`v3.1` · `v3.2`는 DB 스키마 변경 없음).

---

## 📝 4. 최근 수정 내역 (Changelog)

* **2026-11-28 (v3.2 — `daily_supply_analysis` Gemini AI 코멘트 추출 기본 중단 · DB 컬럼/함수/Top 10 정량 순위 보존, AC-72 ~ AC-73)**:
  1. **Gemini AI 코멘트 추출 기본 중단 (`DEFAULT_AI_TOP_N = 0` & `daily_batch.yml` 기본 `'0'`, `AC-72`)**:
     * `run_daily_screener.py`의 `DEFAULT_AI_TOP_N`을 `10 → 0`으로 전환하고 `.github/workflows/daily_batch.yml`의 `AI_TOP_N` 기본값을 `'0'`으로 변경하여, `GEMINI_API_KEY`가 설정된 `final` 슬롯에서도 `AI_TOP_N` 미지정 시 Gemini API 호출이 **`0회`**로 차단되고 추가 Step 2 Upsert 없이 `[DSA-Step2] Gemini AI 코멘트 추출 비활성(AI_TOP_N=0) — 호출 생략` 로그를 남기도록 구현 (`ai_status='SKIPPED'`, `ai_summary=None`).
     * `DEFAULT_TOP_PICK_LIMIT = 10`을 분리하여 `AI_TOP_N=0` 상태에서도 자격 통과 정량 상위 10종목의 `is_top_pick = True` 및 `daily_rank(1..N)` 산정(Step 1)과 사후 복기 백필(Step 3, 과거 `ai_summary` 보존)이 100% 동일하게 동작하도록 보호.
     * `build_gemini_stock_payload`·`call_gemini_stock_summary`·`populate_gemini_summaries` 함수, `DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"`, 워크플로우 `GEMINI_API_KEY`/`GEMINI_MODEL` 선언을 그대로 보존하여 추후 `AI_TOP_N=10` 환경변수/Repository Variable 설정만으로 코드 수정 없이 즉시 재개 지원.
  2. **DB 스키마·프론트엔드 무변경 및 테스트 스위트 확장 (`AC-73`)**:
     * `supabase_schema.sql`(AI 4개 컬럼 보존), 프론트엔드 4종(`index.html`, `watchlist.html`, `holdings.html`, `common.js`), `STRATEGY.md`, `TEST_REPORT.md` 무변경 준수.
     * 기존 `tests/test_v29_daily_analysis.py`·`tests/test_v30_trend_cycle.py` 단언 동기화 및 신규 `tests/test_v32_gemini_pause.py`(4개 테스트) 추가 — 전체 `175 / 175` 테스트(`8 + 167`) 100% PASS.

* **2026-11-28 (v3.1 — 1일 2회 정기 배치 무결점 정상화 · 비허용 시간대 무음 차단 · 분기 유니버스 완주율 99.9%+ 복원 · t1463 409 및 신규상장 백필 해소 · 백업 크론 슬림화, AC-67 ~ AC-71)**:
  1. **비정상 시간대 자동 실행 즉시 무음 스킵 · 장전 빈 일봉 방어 · `0종목` 발송 금지 (`run_daily_screener.py` — `AC-67`)**:
     * `is_allowed_auto_batch_window()`를 신설하여 자동 배치(`mode="daily", skip_if_completed=True`)가 평일 `15:45~18:59 KST`(`prelim`, 수능일 `17:05` 포함) 및 `20:05~23:59 KST`(`final`) 외 구간(평일 새벽·장중 `00:00~15:44`, 야간 데드존 `19:00~20:04`, 주말 전 시간대)에 깨어나면 LS API 인증·DB 조회·텔레그램 발송 `0회`로 즉시 `[SKIP-OFFHOURS]` 정상 종료(`skipped_completed=true`)하도록 구현 (수동 `skip_if_completed=False`는 시간 무관 정상 실행).
     * `LSApiClient.fetch_latest_krx_trading_date()`에서 장전 빈 더미 행(`jdiff_vol<=0 and open<=0`) 및 `15:30 KST` 이전 당일 미마감 봉을 제외하도록 보강하고, `mode="daily"` 실행 후 `universe_count == 0` 공회전 시 완료 텔레그램 및 DSA 파이프라인 실행을 생략.
  2. **기존 분기 유니버스 시총 `700억` 일시 하회 정상 적재 및 분기 재산출 탈락 동기화 (`run_daily_screener.py` — `AC-68`)**:
     * 평일 `daily`(`not rebuild_due`) 모드에서 기존 `is_universe=True` 종목의 당일 시총이 `700억 미만`으로 하락하더라도 건너뛰지 않고 차트·수급·마스터를 정상 적재하여 완주율 `99.9%+` 및 `--skip-if-completed` 정상 작동을 복원 (`t1463` 신규 후보는 `700억` 미만 차단 유지).
     * 전수 분기 재산출(`rebuild_due=True`) 시 신규 `mcap_map`에서 탈락한 구 유니버스 종목을 행 삭제(`DELETE`) 없이 `is_universe=False`로 함께 Upsert하고, `is_quarterly_rebuild_due()` KST 타임존 연-월(`YYYY-MM`) 변환 판별 및 분기 재산출/유니버스 모드 일괄 프리페치(`supabase_prefetch_daily_context`)를 활성화.
  3. **`t1463` 신규 급등주 `HTTP 409 (FK 위반)` 제로화 · 신규 상장주 매회 백필 제거 · 극소량 종목 완료 인정 (`run_daily_screener.py` — `AC-69`, `AC-70`)**:
     * `stocks_master` 미등록 `t1463` 신규 급등주를 루프 시작 전 시드 마스터(`updated_at="1970-01-01T00:00:00+09:00"`)로 선등록하고, `BatchUpsertBuffer.flush()` 단건 격리 루프에서도 `HTTP 409` 발생 시 시드 선등록 후 재시도하도록 이중 방어 (정상 묶음 `daily_chart → daily_investor_supply → stocks_master` 3-POST 계약 보존).
     * `is_stock_already_backfilled()`가 구 `v1.0` 절단 데이터(`60일/25일`)에는 `False`를 유지하되 상장 `1~399영업일` 신규 상장주(`8일/8일`, `40일/40일` 등 오차 5일 이내)에는 `True`를 반환하도록 개선하고, 무앵커 초신규 상장주는 `105달력일(count=60)` 1페이지로 조회.
     * `check_daily_batch_completion()`에서 대표 대형주 3종 확정 시 일봉·수급 행이 모두 존재하고 `0 <= volume <= 100`인 극소량 체결 종목을 완료 집합에 포함.
  4. **내장 백업 크론 슬림화(`5개 → 2개`) 및 테스트 스위트 확장 (`.github/workflows/daily_batch.yml`, `tests/test_v31_batch_schedule.py` — `AC-70`, `AC-71`)**:
     * `daily_batch.yml`의 `schedule`을 슬롯별 핵심 백업 2개(`'25 7 * * 1-5'` [`16:25 KST`], `'47 11 * * 1-5'` [`20:47 KST`])로 슬림화하고 기존 크론 단언 테스트 3곳 동기화 및 신규 `tests/test_v31_batch_schedule.py`(14개 테스트) 추가. 프론트엔드·DB 스키마 무변경, 전체 `171 / 171` 테스트(`8 + 163`) 100% PASS.

* **2026-11-23 (v3.0.1 — ISSUE-023 ~ 028 핫픽스, AC-61 ~ AC-66 PASS)**: Step 1-B `stocks_master` 추세 전용 컬럼 Upsert 격리 및 배치 후 마스터 재조회(`ISSUE-023`), 동일 일자 `prelim→final` 탈락 잔존 행 자동 정리(`ISSUE-024`), 배치·리스트·모달·호버 `750영업일` 표준 윈도우 통일 및 페이지네이션(`ISSUE-025`), 과거 승률 집계 v3.0 라벨 오염 차단(`ISSUE-026`), `HTTPError` 본문 기반 `PGRST204` 폴백(`ISSUE-027`), 시총 `0.1%` 부동소수 허용오차 `-1e-9` 3중 통일(`ISSUE-028`), `tests/test_v301_fixes.py` 추가(157건 OK).

* **2026-11-22 (v3.0 — 양극 추세 사이클 16단계·63세부현황 & 신규 자격 기준 & 3단 드릴다운 UI, AC-61 ~ AC-66)**: 상승 진영(`A-1~A-8`)·하락/바닥 진영(`B-1~B-8`) 16단계·63세부현황 결정론적 분류 엔진(Python·`common.js`·`index.html` 3중 동치), 신규 자격 기준(`거래대금 ≥ 5억` & `순수기관 ≥ 3억 또는 시총 0.1%`), `prelim+final` 정량·추세 적재 및 `gemini-3.5-flash-lite` 기본값 전환, 차트 캔들 호버 시점별 추세 표시, `scripts/migration_v30_trend_cycle.sql` 및 `tests/test_v30_trend_cycle.py` 추가.

* **2026-11-18 (v2.9 — 일일 수급 전수 정량 분석 · Gemini AI Top 10 요약 · 사후 복기 백필, AC-57 ~ AC-60)**: `daily_supply_analysis` 테이블(`scripts/migration_v29_daily_supply_analysis.sql`), 100점 4축 스코어링·매수참고가/손절가/목표가·유사조건 승률(Step 1), 상위 Top N Gemini 압축 요약(Step 2), 5/10/20일 수익률 및 10일 최대/최소 수익률 자동 백필·365일 보관(Step 3), `tests/test_v29_daily_analysis.py` 추가(142건 OK).

* **2026-11-17 (v2.8.2 — TR 서버 물리 바닥 정속 페이서 & 도미노 재시도 원천 차단, AC-56)**: `TR_SERVER_FLOOR_BY_CD = {"t8410": 1.04, "t1717": 0.54}` 도입 및 `_on_rate_limit_wait`의 `_tr_learned_floor` 즉시 학습·슬롯 재예약으로 `IGW00201` 도미노 페널티 제로화(실전 배치 `28분 58초` 완주, 132건 OK).

* **2026-11-16 (v2.8.1 — 복합 PK 청크 병렬 프리페치 & 단일 페이지 증분 차트 핫픽스, AC-54 ~ AC-55)**: `supabase_prefetch_daily_context(..., target_codes)` 50종목 PK 청크 병렬 조회로 프리페치 타임아웃 제거, `ANCHOR_RECENT_CALENDAR_DAYS=105`·`ANCHOR_RECENT_COUNT=60`으로 `t8410` 1페이지 호출 보장(129건 OK).

* **2026-11-16 (v2.8 — 일일 정기 배치 초고속 파이프라인, AC-49 ~ AC-53)**: `run_daily_screener.py`만 수정(프론트·스키마 무변경). ① `KeepAliveHttpPool`(stdlib Keep-Alive, 끊김 자동 재연결, gzip, `HTTPError` 호환, 프록시 환경 urllib 폴백) ② `supabase_prefetch_daily_context`(단건 사전 조회 4,389회 → 일괄 인덱스 프리페치, `T-5` 앵커 일관, count=exact 미사용) ③ `LSApiClient` 경과시간 차감 페이서·적응형 백오프·토큰 단일 갱신, `t8410`‖`t1717` 2-스레드 병렬(`ANCHOR-MISMATCH` 시 기존 전체 재적재) ④ `BatchUpsertBuffer` 50종목 묶음 Upsert(`chart → supply → master` 순, 오류 시 개별 격리), 증분 수급 윈도우 슬림화, 무스킵 완주 시 사후 DB 재집계 생략. 이론 소요 1,463종목 약 12분(실측은 Actions 실행 로그 `[PERF]`로 확인 필요). 테스트 119건 OK.

* **2026-11-16 (v2.7.1 — ISSUE-021/022)**: 주말·공휴일·장전 가짜 당일 봉 복제 및 `전일비 100%` 오표시 차단(`parseNaverRealtime` 날짜 보정, `normalizeQuoteForCandles`, 브리지 `marketState`/`tradeDate` 보정), HOLDING→CLOSED 전환 시 실시간 봉 해제, PNG 저장·복사에 실시간 봉 반영, 시세 미보유 시 `change_rate` 폴백. 테스트 103건 OK.

* **2026-11-16 (v2.7 — 상단 슬림화 · 실시간 시세 엔진 · 거래량 전일비 · 프로 차트 실시간 봉, AC-44 ~ AC-48)**:
  * **레이아웃**: 3페이지 상단 타이틀 배너 삭제, 내비+타이틀+기준일+`⚡ 실시간` 배지를 단일 1줄 바로 통합, `EMA 5~240` 1줄 스트립, 차트 내부 중복 배지 행 숨김(`hideInlineBadges`).
  * **실시간 시세**: `common.js` `LiveQuoteManager`(Tier1 로컬 브릿지/직접 웹소켓 → Tier2 네이버 HTTPS JSONP → Tier3 Supabase 최신 일봉 → Tier4 메모리 cList), 개장 전 빈 시세 가드, 평일 08:50~20:05 KST 4초 갱신. 신규 `scripts/ls_realtime_bridge.py`(표준 라이브러리, `127.0.0.1:8765`, 환경변수 `LS_APP_KEY`/`LS_APP_SECRET`; 실행: `python3 scripts/ls_realtime_bridge.py`). 키는 코드·DB에 저장하지 않으며 브라우저 설정값은 localStorage에만 보관.
  * **헤더/차트**: 종목명·현재가·등락폭·등락률·거래량·전일비(%) 대형 1줄(`computeQuoteMetrics`), 관심종목 점수/보유종목 평가손익 실시간 연동, `mergeLiveQuoteIntoCandles`(원본 불변·증분 EMA), `panel.updateLive`(기간·레이어 유지), 현재가 수평 점선+우측 가격 태그.
  * 테스트: `tests/test_v27_acceptance.py` 추가(전체 99건 OK).

* **2026-11-16 (v2.6.1 — ISSUE-019/020)**: `index.html`·`watchlist.html` 좌측 테이블 슬림 패딩/폰트로 우측 열·`영구제외` 버튼 절단 해결(AC-43), 프로 차트 패널(`mountProChartPanel`)에 `[data-role="badges"]` 상시 배지 렌더링(중복 제거·`describeStockPattern` 폴백, 크게 보기 모달 포함), PNG 파일명 이모지 제거 확장, 장기 차트 로드 후 추천 판정·헤더·행 점·탭 카운트 동기화(AC-42). 테스트 85건 OK.

* **2026-11-16 (v2.6 — 1일 2회 배치 · 수급 급등주 4대 오판 수정 · 차트 패턴 상시 표기 · 3페이지 초슬림 리스트, AC-39 ~ AC-43)**:
  * **배치**: 16:05 KST 1차 가집계 + 20:30 KST 2차 확정(`--batch-slot auto|prelim|final`, 20:00 KST 이전 적재분은 final 슬롯에서 미완료 처리, tz-aware `updated_at` 비교). `daily_batch.yml` 5중 크론, `trigger_daily_batch.gs`에 `setupDaily1605And2030Triggers()` 추가(웹훅 사용 시 1회 실행 필요), 공휴일 스킵 우선, 텔레그램 `[1차 정규장 가집계]`/`[2차 최종 확정]` 표기.
  * **common.js**: 수동등록/바닥권 태그의 60일선 이탈 오판 제거, 역배열 추세돌파(`detectTurnaroundBreakout`)·하락채널 돌파/저항 구분, 이탈 사유 세분화, 같은 날 재병합 동기화, 전 종목 패턴 배지 `describeStockPattern`.
  * **UI**: 3페이지 리스트 초슬림화(8em 종목명, 행 배지는 우측 `#detailBadgesBar`/브리핑으로 이동), 좌우 `items-stretch` + 내부 스크롤, 보유종목 시계열 185일 확장, 패턴 후보 사전필터 완화.
  * 테스트: `tests/test_v26_acceptance.py` 추가(전체 82건 OK).

* **2026-11-15 (v2.5.2 — 와이드 해상도 개방 · 관심종목 컴팩트 리스트/전용 브리핑 · 프로 차트 대화면, AC-36 ~ AC-38)**:
  1. 3페이지 컨테이너를 `w-full max-w-[1920px] 2xl:max-w-[96vw]` 로 확장(`max-w-7xl` 제거).
  2. `watchlist.html`: 좌측 6컬럼(체크·등급·종목명·최초대비·포착·작업) 440/470px 고정 + 우측 `#wlDetailHeader`(시장·현재가·등락폭/률·시총·종합판단·패턴·기관수급·상태 배지·즉시 액션), 미니 정렬 바(`기본 | 종합판단`), 차트 높이 560~760, 스코어카드·입력폼 `xl:grid-cols-2`.
  3. `common.js`: `priceDiff`(`evaluateWatchlistItem`/`evaluateHolding`), `lookupMasters`(시총·20일 평균 거래대금, 100개 청크), `mountProChartPanel` `ResizeObserver`/`resize`·`heightFn`, 가격축 여백 68·대화면 6등분 그리드, `🔍 크게 보기` `max-w-[95vw]`·620~840px.
  4. `holdings.html`(460/500px 그리드, 우측 요약, 높이 560~760), `index.html`(5:7 비율, 높이 480~640).
  * 테스트 74개 + 백엔드 8개 통과. DB·백엔드·`STRATEGY.md`·`TEST_REPORT.md` 무변경.

* **2026-11-15 (v2.5.1 — `TEST_REPORT.md` ISSUE-015 ~ ISSUE-018 수정)**:
  1. **ISSUE-015**: `index.html` `ensureStockFullChart()` 가 `daily_investor_supply` 240건도 병렬 보강 조회·병합(기본 120일 차트 순수기관 막대 공백 해소).
  2. **ISSUE-016**: `buildRowBadges()` 서브태그가 대표 태그와 같으면 중복 출력하지 않고, 비추천 배지에 `subReason`(`[하락채널저항]`) 표시.
  3. **ISSUE-017**: `holdings.html` `onDataLoaded` 가 현재 선택 행(`SELECTED`)을 조회해 캐시 오염 방지, `setData()` 가 `shcode|T|status` 키 변경 시 `fetchedLong` 초기화, `drawProChart()` EMA·패턴 작도를 상단 플롯 영역으로 `clip()`.
  4. **ISSUE-018**: `flag` 판정에 `C > O`(양봉 돌파) 추가, `watchlist.html` `종합판단` 헤더 클릭 정렬(내림→오름→기본) 구현, 장기 로드 후 스코어카드 재렌더링.
  * 테스트 71개 + 백엔드 8개 통과.

* **2026-11-15 (v2.5 — 패턴·캔들·지표 100점 종합판단 및 프로 차트 PNG 저장, AC-30 ~ AC-35)**: `common.js` 분석 엔진·`drawProChart`·`mountProChartPanel` 추가, 3페이지 통합, `tests/test_v25_pattern_chart.py` 신규(전체 68개 통과). DB 변경·텔레그램 이미지 전송 없음.

* **2026-11-15 (v2.4.1 — `TEST_REPORT.md` ISSUE-011 ~ ISSUE-014 수정)**:
  1. **ISSUE-011**: 마이그레이션 SQL·`supabase_schema.sql` 에 `GRANT ALL ... TO anon, authenticated, service_role` 및 시퀀스 `GRANT` 추가(`common.js` 임베드 SQL 동기화). `sbRequest()` 가 `42501`/RLS 401·403 을 `rlsBlocked` 로 감지, 쓰기 실패 시 `테이블 생성/복구 SQL 원클릭 복사` 배너 자동 노출.
  2. **ISSUE-012**: `evaluateWatchlistItem()` 의 20/60일선 이탈은 `recommend_tag === '추세수급'` 종목에만 적용(바닥전환·바닥지지 출신 오판 제거, 기준저가·수급이탈 경보는 유지).
  3. **ISSUE-013**: `C.onExcludedChange` 전역 훅으로 제외관리 모달의 복구·추가 즉시 `index.html` 재스크리닝, 상단 `🚫 영구제외 K종목 자동 숨김` 안내, 업종 프리셋 체크박스 선택 일괄 등록, 병합 버튼 `(N)` 건수·전체선택 체크 동기화.
  4. **ISSUE-014**: 목표가 도달 배지를 현재가(종가) 기준으로 변경, `holdings.html` 행 키를 `id` 로 전환하고 청산 행 클릭 시 일봉 온디맨드 조회(매수·청산·목표가 라인), 매수일 `(D+N일)` 병기, `loadSeriesForCodes` 1,300일 단위 분할.
  5. 테스트 57건 통과(`tests/test_v24_watchlist_holdings.py` 보강).

* **2026-11-15 (v2.4 — `STRATEGY.md` 7절 구현: 3페이지 관심종목 · 보유종목 · 영구제외 실전 매매 관리 — `AC-24 ~ AC-29`)**:
  1. `supabase_schema.sql` 하단 및 단독 `scripts/migration_v24_watchlist_holdings.sql` 에 `excluded_stocks`/`watchlist_items`/`portfolio_holdings`(+`idx_holdings_active_shcode` 부분 고유 인덱스, RLS 비활성화) 추가. 기존 3개 테이블 무변경.
  2. 신규 `common.js`(안전 REST 헬퍼·내비게이션·제외관리 모달·분류/병합/청산 순수 로직·캔들 차트), `watchlist.html`, `holdings.html`; `index.html` 에 추천/비추천 3단계 분류·탭·영구제외·`⭐ 선택 종목 관심종목 병합`·`[⭐기존관심]`/`[💼보유중]` 배지·테이블 미생성 배너 반영(`common.js` 미로딩 시 기존 스크리닝 그대로 동작).
  3. `run_daily_screener.py`: `send_telegram_alert()` Markdown `HTTP 400` → 일반 텍스트 재전송 폴백.
  4. 테스트: `tests/test_v24_watchlist_holdings.py` 신규(분류 경계값, 병합 멱등·무삭제, 목표가/20일선/수급이탈, 승률, 204 안전 파싱, 청크 크기, 텔레그램 400, SQL/HTML 정합성). 기존 테스트 전부 통과.

* **2026-11-15 (v2.3.1 — `STRATEGY.md` 6절 반영: 차트 5년 · 수급 3년 비대칭 확장 및 운영 DB 전수 스캔 보완 패치)**:
  1. 기본 상수 `CHART_HISTORY_START_DATE=2021-11-01`, `SUPPLY_HISTORY_START_DATE=2023-11-01`, `TWO_YEAR_CUT_OLD=2024-10-20`; CLI `--chart-start` / `--supply-start` → `run_backfill_10y(..., chart_start, supply_start)`, 워크플로우 `chart_start`/`supply_start` 입력 및 자동 이어받기 전달(추후 `2016-01-01` 등 무코드 확장).
  2. **거래정지(`volume==0`) 종목 `is_latest_supply_unsettled` 오판 제거**: `supabase_get_stock_range_status`·`supabase_get_stock_data_status_detail` 가 최신 일봉 `volume` 을 함께 읽고 `resolve_supply_unsettled` 로 판정.
  3. 일반화 판정식 `needs_chart_fetch(db_chart_oldest, target_chart_start)` / `is_stock_history_completed` (구 `needs_10y_chart_fetch`/`is_stock_10y_completed` 대체), 종목별 `stock_supply_target = max(effective_supply_target, chart_oldest)`.
  4. `call_tr` 토큰 만료(`IGW00121`/`토큰`) 재발급 재시도, `find_supply_floor_for_stock` 첫 구간 `20160101~20160131`, daily 배치의 신규/폴백 수집을 5년·수급 3년 정책으로 통일, 텔레그램 문구에 `(차트 …~ / 수급 …~)` 표기.
  5. 테스트: `tests/test_v23_acceptance.py` 갱신(28건 통과) — 거래정지, 20160131 조회, 2016 재확장 계획 포함.

* **2026-11-15 (v2.3 — `STRATEGY.md` 6절 구현: 전 종목 10년치 확장, `probe_10y` 사전 실측 프로브, 무중단 자동 이어받기 — `AC-19 ~ AC-23`)**:
  1. `run_daily_screener.py`: `HISTORY_START_DATE`/`TARGET_10Y_CHART_COUNT`/`SUPPLY_MAX_PAGES_10Y` 상수, `fetch_daily_chart` 페이지 4→10, `compute_ema_series(seed=)`, 범위 상태(`supabase_get_stock_range_status`)·앵커(`supabase_get_anchor_row`, `build_anchor_seeded_charts`)·완주 판정(`is_stock_10y_completed`, `needs_10y_chart_fetch`)·수급 역방향 델타(`plan_supply_fetch`)·수급 하한 탐색(`detect_ls_server_history_floor`)·`run_probe_10y`·`run_backfill_10y`·양보 가드(`is_in_daily_yield_window`) 추가. argparse `--mode` 에 `backfill_10y`/`probe_10y`, `--chain-round` 추가.
  2. `daily_batch.yml`: `mode` 옵션 확장, `chain_round` 입력, `permissions: actions: write`, 미완주 시 자동 다음 회차 디스패치 스텝(최대 6회), Cron 3개 불변.
  3. `verify`: 7종목 최초일~최신일·영업일수 출력, 리포트 헤더 AC-1~AC-23.
  4. 테스트: `tests/test_v23_acceptance.py`(14건) 신규, `test_screener_verification.py` test_7 에 라이브 DB 격리 패치. 전체 `8 + 23건` 통과.

* **2026-11-12 (v2.2 — `STRATEGY.md` 5절(2.2절·3.3절 연동) 전면 구현: `[기관 수급 발생 종목]` 저유동성·소액수급 제외 필터 추가 및 `[엑셀 저장]` 9개 열 전면 개편 — `AC-16 ~ AC-18`)**:
  1. **`[기관 수급 발생 종목]`(`inst_supply`) 전용 유동성·수급금액 제외 필터 및 `trading_value_m` 조회 연동 (`index.html`, `run_daily_screener.py` — `AC-16`)**:
     * `index.html`의 `CHART_SELECT_COLS` 및 `run_daily_screener.py` `verify_supabase_data()` 내 `c_cols`에 `trading_value_m`(일 거래대금, 백만 원)을 추가하고, `trading_value_m <= 0`인 행에 대해 `(close * volume) / 1,000,000` 안전 폴백 함수(`resolveTradingValueM` / `resolve_trading_value_m`)를 구현.
     * **`당일 10% / 15% / 20% 이상` 단일일 옵션**: 기준일 $T$ 당일 `real_inst_amt_T >= 100.0`(1억 원 이상) $\land$ `volume_T >= 30,000`(3만 주 이상) $\land$ `trading_value_m_T >= 500.0`(5억 원 이상) 필수 통과 조건을 적용하여 소액·저유동성 왜곡 종목을 100% 제외.
     * **`3일 연속 5% 이상`(`consec_3d_5`) 연속 옵션**: 당일 단일일 커트라인 대신 최근 3거래일($T-2, T-1, T$) **3일 평균 수급금액 $\ge 100.0$ $\land$ 3일 평균 거래량 $\ge 30,000$ $\land$ 3일 평균 거래대금 $\ge 500.0$** 기준으로 통일 판정 (화면·엑셀 표기 및 정렬은 기준일 $T$ 당일 수치 유지).
     * **`[하락 추세 전환 수급 발생]`(`trend_reversal`)**: 소수 포착 전략 특성에 맞춰 본 유동성·수급금액 제외 필터를 적용하지 않고 기존 `2.3절` 포착 결과를 그대로 보존 (`2026-11-12` 운영 DB 검증: `87 / 48 / 29 / 47 / 2종목` 웹·파이썬 오차 0건 일치).
  2. **`[엑셀 저장]`(`exportScreenedToExcel`) 11개 열 → 9개 열 전면 개편 및 `[이동평균 추세 현황]` 신설 (`index.html` — `AC-17`, `AC-18`)**:
     * 시트 헤더를 정확히 **`종목코드, 종목명, 현재가, 등락폭, 등락률, 수급 비중, 수급 금액, 연속 일수, 이동평균 추세 현황`** 9개 열로 교체하고 기존 `등락폭/율` 병합 열 및 개별 `Ema5~Ema240` 5개 열을 제거.
     * 양수 `+` 기호와 `"억"`·`"일"` 단위 문자를 전면 제거하고, `등락폭`(정수)·`수급 금액`(소수 첫째 자리 억 환산)·`연속 일수`(정수)는 순수 숫자(`t: "n"`), `등락률`(`"4.11%"`)·`수급 비중`(`"53.6%"`)은 `+` 없는 `%` 문자열(`t: "s"`)로 저장하며 `-0` 및 `"-0.00%"` 경계값을 방어 처리.
     * 기준일($T$)의 5개 EMA(`Ema5, Ema20, Ema60, Ema120, Ema240`)를 수치 내림차순(동률 시 단기 `span` 오름차순)으로 정렬하여 `" > "`로 연결하는 `formatEmaTrendStatus` / `format_ema_trend_status` 함수 및 9번째 열 너비(`{ wch: 42 }`)를 반영.
  3. **백엔드·프론트엔드 자동화 회귀 테스트 확장 (`test_screener_verification.py`, `tests/test_v2_acceptance.py` — `AC-16 ~ AC-18`)**:
     * `test_8_v22_liquidity_filters_and_ema_trend_status` 및 `test_ac16_ac17_ac18_v22_filters_and_excel_9cols_js`를 추가하여 단일일·3일 평균 필터 경계값, `trend_reversal` 비적용, 9열 셀 타입·부호·`-0` 방지, EMA 내림차순 동률 처리를 동적 검증 (총 16개 테스트 100% 통과).
* **2026-11-12 (v2.1 — `STRATEGY.md` 4절 전면 구현: 정기 배치 시각 `평일 20:30 KST` 변경 및 스케줄 누락·중복·무음실패 4중 원천 방지 아키텍처 적용 — `AC-13 ~ AC-15`)**:
  1. **`[방어선 1 & 3]` `20:30 KST` 본 스케줄 + 다중 시간차 백업 Cron + `concurrency` 직렬화 + 실패 텔레그램 경보 (`.github/workflows/daily_batch.yml` — `AC-13`)**:
     * 정기 배치 시각을 `21:05 KST`에서 야간장 마감 직후인 **평일 `20:30 KST` (`cron: '30 11 * * 1-5'`)** 로 앞당기고, GitHub 공용 러너 피크 드롭 대비 자동 백업 슬롯 2회(**`20:47 KST` `47 11 * * 1-5`**, **`21:17 KST` `17 12 * * 1-5`**)를 추가 등록.
     * 최상위 `concurrency: { group: daily-ls-stock-batch, cancel-in-progress: false }` 선언으로 실행 중인 본 배치를 백업 스케줄이 취소하지 않고 순차 대기하도록 보호하며, `schedule` 이벤트 또는 `skip_if_completed == 'true'` 입력 시 `--skip-if-completed` 플래그 자동 전달(수동 `workflow_dispatch` 기본값은 강제 재실행 유지).
     * 워크플로우 말미에 `if: failure()` 조건의 **`배치 실패 시 텔레그램 장애 알림 발송`** 스텝을 추가하여 비정상 종료 시 발생 시각(KST), 실행 이벤트, Actions Run 로그 URL을 즉시 텔레그램 발송.
  2. **`[방어선 2]` KST 표준시 일원화 · 공휴일 보호 · `--skip-if-completed` 5초 내 멱등성 가드 · 부분 적재 고속 이어받기 (`run_daily_screener.py` — `AC-14`)**:
     * `dt.date.today()` 의존을 제거하고 `get_kst_today()` / `get_kst_now()`로 모든 기준일 연산을 한국 표준시(`KST = UTC+9`)로 일원화.
     * LS 토큰 발급 직후 대표 종목(`005930`) `t8410` 1회 조회(`fetch_latest_krx_trading_date`)로 실제 최신 KRX 개장일(`latest_krx_date`)을 획득하여 평일 공휴일 중복 재수집·중복 알림을 원천 차단.
     * `--skip-if-completed` 옵션을 신설하여 50종목 단위 PK 병렬 청크(`check_daily_batch_completion`)로 `latest_krx_date` 완주율(`>= 98.5%`, 거래정지 `volume=0` 종목 반영 및 대표 대형주 3종 확정 필수) 충족 시 **약 2~3초 이내(`5초 미만`)에 즉시 정상 종료(`Exit 0`)** 하도록 구현.
     * 중단 후 부분 적재(`< 98.5%`) 이어받기 실행 시 당일 기적재 완료 종목은 API 호출을 스킵(`[DAILY-SKIP]`)하되, 루프 종료 후 전체 유니버스 DB 확정 데이터 기준으로 `screened_1d`·`screened_3d`를 재집계(`build_daily_screening_lists_from_db`)하여 텔레그램 리포트 누락을 방지.
  3. **`[방어선 4]` 외부 정각 웹훅 트리거 스크립트 작성 및 운영 가이드 문서화 (`scripts/trigger_daily_batch.gs`, `README.md` — `AC-13`)**:
     * 무료 Google Apps Script에서 평일 매일 `20:30 KST` 정각에 GitHub `workflow_dispatch` REST API를 호출하는 완제품 스크립트(`triggerDailyStockBatch`, `setupDaily2030Trigger`, `testTriggerForceNow`, 구버전 YAML 422 자동 폴백 내장)를 작성하고 `README.md` 3.3절에 3분 설정 가이드를 수록.
  4. **`[부수 정합성 보강]` 분산 대표 10종목 기준일(`TOP_TRADE_DATE`) 탐색 및 동기화 진행 중 상태 배지 (`index.html`, `run_daily_screener.py`, `test_screener_verification.py`, `tests/test_v2_acceptance.py` — `AC-15`)**:
     * `fetchLatestSettledTradeDate`(웹) 및 `fetch_latest_settled_trade_date_db`(`--mode verify`)의 조회 대상을 시총 상·중·하위 분산 대표 10종목(`005930,000660,005380,012450,196170,006650,023160,218410,166090,009420`, `limit=30`)으로 확장하여 0.3초 이내 성능을 유지하면서 상위 종목 미갱신 시 기준일 고정 현상을 해소.
     * 전체 유니버스 중 `TOP_TRADE_DATE` 확정 종목 비율이 `95% 미만`일 때 상단 배지에 `기준일: YYYY-MM-DD (일일 배치 동기화 진행 중: N/M종목)`을 표시하고 완주(`>= 95%`) 시 `기준일: YYYY-MM-DD`로 자동 전환하도록 구현 (`AC-7 ~ AC-15` 전 항목 자동 테스트 통과).
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
* **2026-11-12 (v1.4.3 — `TEST_REPORT.md` `[ISSUE-006]` ~ `[ISSUE-010]` 5건 전수 해결: 평일 고속 증분 판정 분리, 장중 미확정 `0` 수급 원천 차단, 웹 대시보드 최대 60영업일 동적 윈도우 확장)**
* **2026-11-11 (v1.4.2 — 불필요한 최우선 레퍼런스 종목(`PRIORITY_SHCODES`, `_prioritize_candidates`) 루틴 제거 및 단순화)**
* **2026-11-11 (v1.4 — `STRATEGY.md` 0절 6대 필수 아키텍처 수정: 시총 700억 이상 전수 유니버스 & 2년치 500영업일 백필 구현)**
* **2026-11-11 (v1.3 — 3원화 대화창 파일 연동(`STRATEGY.md`, `README.md`, `TEST_REPORT.md`) 표준 체계 구축)**
* **2026-11-11 (v1.2 — 웹 대시보드 최신 거래일 페이지네이션 및 1:1 매칭 패치)**
* **2026-11-11 (v1.1 — 실데이터 적재 및 텔레그램 알림 연동 완료)**
* **2026-11-11 (v1.0 — 초기 아키텍처 구축)**
