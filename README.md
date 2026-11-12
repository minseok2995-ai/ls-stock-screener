# 📈 LS증권 Open API 기반 기관 수급 종목 스크리너 (`ls-stock-screener`)

야간시장(NXT, `20:00 KST` 종료) 마감 및 투자자별 확정 수급 집계 직후 **평일 매일 저녁 20:30(KST)** 에 **4중 무결점 스케줄 아키텍처**(외부 정각 웹훅 + GitHub Actions 본 스케줄 `20:30` 및 백업 `20:47`·`21:17 KST` + `--skip-if-completed` 멱등성 가드 + 실패 경보)로 자동 기동되어, **코스피·코스닥 시가총액 700억 원 이상 보통주 전수(약 1,463종목)**의 **2년치(약 500영업일) 수정주가 일봉 차트 + 지수이동평균(EMA 5, 20, 60, 120, 240)** 및 **투자주체별 수급(수량·금액)**을 수집하고 **Supabase 클라우드 DB** 업데이트, **텔레그램 요약·장애 알림 발송**, **실시간 웹 대시보드(`기관 수급 종목 스크리너`) 시각화·엑셀(`.xlsx`) 다운로드**를 수행하는 시스템입니다.

---

## 🤝 3원화 대화창 협업 워크플로우 (`StudyRemote` 운영 규칙)

본 프로젝트는 역할이 분리된 3개의 대화창을 통해 파일 기반으로 유기적으로 운영됩니다:

1. **[전략 개발] 대화창**:
   * 주식 종목 발굴 전략 및 수급·차트·배치 아키텍처 기획 전담 (`STRATEGY.md`에 기록 및 최신화)
2. **[프로그램 개발 및 수정(메인)] 대화창**:
   * **[작업 시작 전 - 읽을 파일]**: 항상 `git pull`을 먼저 실행한 뒤 `STRATEGY.md`(설계된 전략·수식·요구사항)와 `TEST_REPORT.md`(보고된 버그·수정 요청)를 읽고 작업 파악 (`STRATEGY.md`는 임의 수정 금지)
   * **[작업 완료 후 - 작성할 파일]**: 실제 프로그램 소스코드 구현/수정 후 `README.md`의 (1) 개발 환경 및 폴더 구조, (2) 실행 방법, (3) 하단 `최근 수정 내역(Changelog)`을 최신 상태로 업데이트하고, `TEST_REPORT.md`의 해결된 버그 항목을 `[해결 완료]`로 표시한 뒤 `git commit` 및 `git push` 수행
3. **[검증 및 테스트] 대화창**:
   * `README.md`, `STRATEGY.md`와 최신 커밋을 바탕으로 테스트(`test_screener_verification.py`, `tests/test_v2_acceptance.py`, `run_daily_screener.py --mode verify`) 실행 및 `TEST_REPORT.md`에 합격 기준(`AC-1` ~ `AC-15`) 검증 결과·수정 요청 작성

---

## 🖥️ 1. 개발 및 운영 환경 및 폴더 구조 (Environment & Directory Structure)

### 1.1 기술 스택 및 운영 환경

| 구분 | 상세 환경 및 구성 |
| :--- | :--- |
| **OS / 실행 환경** | Linux (Debian 12 / GitHub Actions `ubuntu-latest`, 단일 Job 최대 360분 타임아웃, `KST = UTC+9` 코드 레벨 표준시 고정) |
| **Backend 언어** | **Python 3.11+** (외부 pip 패키지 의존성 없이 표준 라이브러리 `urllib`, `json`, `ssl`, `datetime`, `argparse`, `concurrent.futures`만으로 동작하여 이식성 극대화) |
| **증권사 API** | **LS증권 Open API** (`https://openapi.ls-sec.co.kr:8080`) — OAuth2 토큰 자동 발급/갱신 및 TR(`t8436`, `t1444`, `t1463`, `t1102`, `t8410`, `t1717`) 호출 |
| **Database** | **Supabase (PostgreSQL + PostgREST)** (`https://rwvvrtjsxzecmdykwrxg.supabase.co`, 약 1,463종목 × 500영업일 ≈ 테이블당 약 72만 행 규모, 복합 PK `(shcode, trade_date)` 인덱스 최적화) |
| **Frontend 대시보드** | HTML5 + TailwindCSS (CDN) + SheetJS (`xlsx-0.20.3` CDN, `.xlsx` 다운로드) + HTML5 Canvas 2D (`index.html`) — GitHub Pages 배포 (`https://minseok2995-ai.github.io/ls-stock-screener/`) |
| **배치 스케줄러 (4중 방어)** | **GitHub Actions** (`.github/workflows/daily_batch.yml`) 평일 **20:30 KST** (`30 11 * * 1-5`) + 피크 회피 백업 **20:47 / 21:17 KST** (`47 11`, `17 12`) + **Google Apps Script 정각 웹훅** (`scripts/trigger_daily_batch.gs`) + `concurrency` 직렬화 |
| **알림 채널** | **Telegram Bot HTTP API** (`@my_ls_stock_bot`, 기본 수신 `TELEGRAM_CHAT_ID: 1018392459` — 정상 완료 리포트 및 `if: failure()` 즉시 장애 경보 겸용) |

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
│        └── daily_batch.yml          # 평일 20:30 KST 본 실행 + 20:47·21:17 KST 백업 Cron + concurrency 직렬화 + 실패 텔레그램 경보
├── scripts/
│   └── trigger_daily_batch.gs        # [방어선 4] 평일 20:30 KST 정각 GitHub workflow_dispatch 외부 웹훅 트리거 (Google Apps Script)
├── tests/
│   └── test_v2_acceptance.py         # AC-7 ~ AC-15 프론트엔드·워크플로우·멱등성·배지 통합 회귀 검증 테스트 스위트
├── README.md                         # [프로그램 개발 및 수정] 창 관리: 환경, 폴더 구조, 실행/웹훅 설정 방법, 최근 수정 내역(Changelog)
├── STRATEGY.md                       # [전략 개발] 창 관리 (임의 수정 금지): 종목 발굴 전략 v2.0 및 v2.1 4중 배치 아키텍처 명세서 (SSOT)
├── TEST_REPORT.md                    # [검증 및 테스트] 창 관리: AC-1 ~ AC-15 검증 리포트 및 버그/수정 요청 트래커
├── run_daily_screener.py             # 메인 백엔드: KST 표준시, --skip-if-completed 멱등성 가드, 부분 이어받기, 1,463종목 일봉·수급 수집 및 검증
├── index.html                        # 실시간 웹 대시보드(기관 수급 종목 스크리너): 10종목 분산 기준일 탐색, 동기화 배지, 2대 전략 스크리닝, 11열 엑셀 저장
├── supabase_schema.sql               # Supabase 테이블(3종), 복합 기본키(shcode, trade_date) 인덱스, 뷰, RPC 함수 스키마
├── test_screener_verification.py     # 7단계 핵심 백엔드 단위 테스트 (유니버스·EMA·t1717·스마트 이어받기·Strategy v2.0·v2.1 KST & 멱등성 가드)
└── .gitignore                        # Python 캐시(__pycache__) 등 버전 관리 제외 설정
```

---

## 🎯 2. 적용된 핵심 전략(Strategy v2.0) 및 4중 무결점 배치 아키텍처(v2.1)

### 2.1 데이터 구축 및 기준일($T$) 정합성 원칙
1. **분석 대상 유니버스 (시총 700억 이상 보통주 전수 — 약 1,463종목)**:
   * 코스피(`KOSPI`) + 코스닥(`KOSDAQ`) 통합 보통주 (`t8436` 마스터 기준, ETF/ETN/ELW/스팩/리츠/우선주/인버스/레버리지 제외).
   * 수집 단계 거래대금 사전 차단 없이 `market_cap_eok >= 700.0`인 모든 보통주의 2년치(약 500영업일) 수정주가 일봉(`daily_chart`) 및 투자주체별 수급(`daily_investor_supply`)을 100% 적재합니다.
2. **순수 기관(`real_inst`) 정의**:
   * 단기 차익·LP 물량 왜곡이 있는 **금융투자(`fn_inv`)를 제외**하고 **`투신 + 보험 + 은행 + 종금(기타금융) + 연기금 등 + 사모펀드`** 6대 주체만 합산합니다.
3. **기준 확정 거래일($T$) 산정 및 장중 $T+1$ 데이터 혼입 원천 차단**:
   * 장중 미확정(`전 주체 수량 0`) 더미 행을 제외한 **가장 최근 확정 수급 거래일**을 기준일 $T$로 산정합니다.
   * 모든 일봉·수급 조회 및 판정에 **`trade_date <= T` 상한**을 강제하며, 조건 비교와 내림차순 정렬은 DB 확정 저장값(`inst_vol_ratio`, `frg_vol_ratio`) 및 **마지막 날(기준일 $T$) 당일의 `수급비중`·`수급금액`**을 기준으로 수행합니다.

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

### 2.3 웹 대시보드(`index.html`) UI/UX 슬림화, 엑셀 저장 및 분산 기준일 탐색 (`AC-7 ~ AC-15`)
* **상단 슬림 헤더 & 동기화 진행 배지(`4.5절`)**:
  * 타이틀(`기관 수급 종목 스크리너`), 기준일 배지, 순수 기관 산식 안내만 깔끔히 표기합니다.
  * 최신 확정 기준일($T$)은 시가총액 상·중·하위 분산 대표 10종목(`005930,000660,005380,012450,196170,006650,023160,218410,166090,009420`) 복합 PK 인덱스로 **0.3초 이내**에 탐색하여 상위 종목 미갱신 시에도 최신일 $T$를 즉시 감지합니다.
  * 야간 배치 진행 중이어서 전체 유니버스 대비 $T$ 확정 데이터 적재 비율이 `95% 미만`일 때는 `기준일: YYYY-MM-DD (일일 배치 동기화 진행 중: N/M종목)`을 표시하고, 완주(`>= 95%`) 후에는 `기준일: YYYY-MM-DD`로 표기합니다.
* **1줄(Single-line) 7컬럼 리스트 & 11컬럼 엑셀(`.xlsx`) 다운로드**:
  * 화면 7컬럼: `종목명 | 현재가 | 등락율 | 수급비중 | 수급금액 | 외국인비중 | 연속일수`
  * `[엑셀 저장]`: 5종 표준 파일명(`{기준일}_{조건명}.xlsx`) 및 11컬럼(`종목코드, 종목명, 현재가, 등락폭/율, 수급 비중, 수급 금액, Ema5, Ema20, Ema60, Ema120, Ema240`).

### 2.4 평일 `20:30 KST` 스케줄 누락 4중 원천 방지 아키텍처 (`STRATEGY.md` 4절)
1. **[방어선 1] 3중 Cron 슬롯 + `concurrency` 직렬화 (`.github/workflows/daily_batch.yml`)**:
   * 주 스케줄 **`20:30 KST`**(`30 11 * * 1-5`) 외에 피크 시간대 큐 드롭을 대비한 홀수 분 백업 스케줄 **`20:47 KST`**(`47 11 * * 1-5`), **`21:17 KST`**(`17 12 * * 1-5`)을 등록하고, `concurrency: { group: daily-ls-stock-batch, cancel-in-progress: false }`로 실행 중인 본 배치가 절대 취소되지 않고 순차 대기하도록 보호합니다.
2. **[방어선 2] KST 표준시 고정 · 공휴일 보호 · `--skip-if-completed` 멱등성 가드 · 고속 이어받기 (`run_daily_screener.py`)**:
   * 러너 UTC 타임존과 무관하게 `KST(UTC+9)` 기준일을 산출하고, `005930` `t8410` 1회 조회로 실제 최신 KRX 개장일(`latest_krx_date`)을 확인하여 평일 공휴일 불필요 재수집을 차단합니다.
   * `--skip-if-completed` 실행 시 50종목 단위 PK 병렬 청크로 `latest_krx_date` 완주율(`>= 98.5%` & 대표 대형주 3종 확정)을 검사하여 이미 완주된 경우 **약 2~3초 이내(`5초 미만`)에 중복 API 호출 및 중복 텔레그램 발송 없이 즉시 정상 종료(`Exit 0`)** 합니다.
   * 중단 후 부분 적재(`< 98.5%`) 상태에서 백업 배치가 이어받을 때는 기적재 종목 API 호출을 스킵하여 수 분 내 복구하되, 최종 텔레그램 리포트(`screened_1d`, `screened_3d`)는 전체 유니버스 DB 확정 데이터 기준으로 재집계하여 누락을 원천 방지합니다.
3. **[방어선 3] 배치 실패 시 텔레그램 즉시 장애 경보 (`.github/workflows/daily_batch.yml`)**:
   * `if: failure()` 전용 스텝이 비정상 종료 시 발생 시각(KST), 실행 이벤트(`schedule`/`workflow_dispatch`), GitHub Actions Run 로그 URL을 텔레그램으로 즉시 발송합니다.
4. **[방어선 4] 외부 정각 웹훅 트리거 (`scripts/trigger_daily_batch.gs`)**:
   * Google Apps Script에서 평일 매일 `20:30 KST` 정각에 GitHub REST API(`workflow_dispatch`, `skip_if_completed: "true"`)를 호출하여 GitHub 내장 Cron 지연이나 GitHub App 푸시 제약을 100% 우회합니다.

---

## 🚀 3. 실행, 웹훅 트리거 설정 및 검증 방법 (Execution & Setup Guide)

### 3.1 로컬 / 서버 CLI 실행 명령어

```bash
# 1) 환경변수 설정
export LS_APP_KEY="발급받은_LS_APP_KEY"
export LS_APP_SECRET="발급받은_LS_APP_SECRET"
export SUPABASE_URL="https://rwvvrtjsxzecmdykwrxg.supabase.co"
export SUPABASE_KEY="sb_publishable_vH_-2K-y5HwQ9oqiT1gtIw_P9pKdJ26"
export TELEGRAM_BOT_TOKEN="텔레그램_봇_토큰"
export TELEGRAM_CHAT_ID="1018392459"

# 2) [일일 증분 배치 — 수동 강제 실행] 평일 야간장 마감(20:30 KST) 후 실행
python3 run_daily_screener.py --mode daily

# 3) [일일 증분 배치 — 자동 스케줄 멱등성 모드] 당일 98.5% 이상 완주 시 5초 이내 즉시 종료(Exit 0), 미완주 시 미처리분만 고속 이어받기
python3 run_daily_screener.py --mode daily --skip-if-completed

# 4) [2년치 전수 백필 및 구간 분할 백필]
python3 run_daily_screener.py --mode backfill
python3 run_daily_screener.py --mode backfill --chunk "1/3"
python3 run_daily_screener.py --mode backfill --start-idx 0 --end-idx 500

# 5) [빠른 샘플 테스트] 상위 10종목만 즉시 테스트
python3 run_daily_screener.py --mode daily --max-stocks 10

# 6) [데이터 정합성(AC-1~AC-15) 및 Strategy v2.1 전 종목 PK 스크리닝 검증 리포트 출력]
python3 run_daily_screener.py --mode verify
```

### 3.2 단위·통합 검증 테스트 스위트 실행 (`[검증 및 테스트]` 대화창용)

```bash
# 백엔드 7단계 핵심 단위 테스트 (유니버스·EMA·t1717·스마트 이어받기·Strategy v2.0·v2.1 KST/멱등성/부분 이어받기)
python3 test_screener_verification.py

# 프론트엔드·워크플로우·정합성 통합 합격 기준(AC-7 ~ AC-15) 자동 검증 스위트
python3 -m unittest discover -s tests -v
```

### 3.3 [방어선 4] 평일 `20:30 KST` 정각 외부 웹훅 트리거 3분 설정 가이드 (`Google Apps Script` + GitHub 웹 활성화)

GitHub 내장 `schedule`(cron)의 플랫폼 큐 지연이나 GitHub App 워크플로우 푸시 제약을 완벽히 우회하여 **평일 저녁 8시 30분 정각(오차 1분 이내)** 에 100% 기동되도록 아래 3단계를 최초 1회 설정해 주십시오:

1. **GitHub 워크플로우 내장 스케줄러 재활성화 확인 (30초)**:
   * GitHub 저장소(`https://github.com/minseok2995-ai/ls-stock-screener`) → **Actions** 탭 → 좌측 **Daily LS Stock Supply & Chart Batch Update** 클릭.
   * 우측 상단 `⋯` 메뉴에서 **`Disable workflow`** 클릭 후 다시 **`Enable workflow`** 를 클릭하면 사용자 본인 계정 권한으로 내장 Cron(`20:30 / 20:47 / 21:17 KST`) 스케줄러가 즉시 정식 활성화됩니다.
2. **GitHub Fine-grained PAT(개인 액세스 토큰) 1개 발급 (1분)**:
   * GitHub 우측 상단 프로필 → **Settings** → 좌측 최하단 **Developer settings** → **Personal access tokens** → **Fine-grained tokens** → **`Generate new token`** 클릭.
   * **Token name**: `ls-stock-screener-trigger` / **Expiration**: 원하는 만료일(예: 1년) 선택.
   * **Repository access**: `Only select repositories` 선택 → **`minseok2995-ai/ls-stock-screener`** 체크.
   * **Permissions** → **Repository permissions** → **`Actions`** 항목을 **`Read and write`** 로 변경 후 하단 **`Generate token`** 클릭 → 발급된 `github_pat_...` 문자열 복사.
3. **Google Apps Script 등록 및 `20:30 KST` 트리거 설정 (1분 30초)**:
   * `https://script.google.com` 접속 → **`새 프로젝트`** 클릭 → 기존 코드를 지우고 저장소의 [`scripts/trigger_daily_batch.gs`](./scripts/trigger_daily_batch.gs) 전체 코드를 붙여넣은 뒤 저장(`Ctrl + S`).
   * 좌측 메뉴 **프로젝트 설정(⚙️)** 클릭:
     * 시간대가 `(GMT+09:00) 한국 표준시 - 서울`인지 확인합니다.
     * 하단 **스크립트 속성(Script Properties)** → **`스크립트 속성 추가`** 클릭 → 속성: `GITHUB_PAT`, 값: 복사한 `github_pat_...` 토큰 입력 후 **`스크립트 속성 저장`**.
   * 좌측 **편집기(`<>`)** 로 돌아와 상단 함수 드롭다운에서 **`setupDaily2030Trigger`** 를 선택하고 **`실행`** 클릭(최초 1회 Google 권한 승인) → 매일 **오후 8시 30분(`20:30 KST`, 평일 자동 판별)** 정각 트리거가 자동 생성됩니다! *(또는 좌측 **트리거(⏰)** 메뉴 → `트리거 추가` → 실행할 함수: `triggerDailyStockBatch`, 이벤트 소스: `시간 기반`, 유형: `일 단위 타이머`, 시간대: `오후 8시~9시`로 직접 지정해도 동일하게 동작합니다.)*

### 3.4 웹 대시보드 접속 및 GitHub Actions 수동 강제 실행 방법
* **실시간 웹 대시보드**: `https://minseok2995-ai.github.io/ls-stock-screener/`
* **GitHub Actions 수동 실행**: GitHub 저장소 → **Actions** 탭 → **Daily LS Stock Supply & Chart Batch Update** → **Run workflow** 클릭 → `mode`(`daily` / `universe` / `backfill` / `verify`), `max_stocks`(`0`=전체), `skip_if_completed`(기본 `false`: 수동 실행 시 당일 이미 완주되었더라도 강제 재수집 및 텔레그램 재발송 수행) 선택 후 실행.

---

## 📝 4. 최근 수정 내역 (Changelog)

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
