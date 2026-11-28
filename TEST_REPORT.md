# 🧪 LS 수급·차트 스크리너 검증 및 테스트 리포트 (`TEST_REPORT.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[검증 및 테스트]` 전담 대화창**에서 테스트 실행 결과, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md) 대조 검수, 데이터 정합성 검증 리포트, 발견된 버그 및 구체적인 코드 수정 제안을 기록하는 문서입니다.
> * **`[프로그램 개발 및 수정(메인)]` 대화창**은 작업 시작 전 본 `TEST_REPORT.md`와 `STRATEGY.md`를 확인하여 미해결 버그(`2.1절 신규 수정 요청 사항`)를 코드에 반영하고, 수정이 완료된 항목의 상태를 **`[해결 완료]`**로 업데이트합니다.

---


## 1. 최신 검수 요약 (`v3.2` Gemini AI 코멘트 추출 기본 중단 커밋 `0245422` 최종 검수 — **`AC-72 ~ AC-73` 및 `AC-1 ~ AC-71` 전 항목 합격, 신규 결함 `0건`**)

* **대상 커밋**: `0245422` (`feat(v3.2): Gemini AI 코멘트 추출 기본 중단(DEFAULT_AI_TOP_N=0) 및 Top 10 정량 순위·DB/함수 보존 (AC-72 ~ AC-73)`, 전략 기준 커밋 `8a35925`)
* **범위 및 무변경 원칙 (`AC-73`)**: `git diff --name-status 8a35925..0245422` = 허용 파일만 변경([`run_daily_screener.py`](/home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py), [`daily_batch.yml`](/home/antigravity/minseok2995-ai/ls-stock-screener/.github/workflows/daily_batch.yml), [`README.md`](/home/antigravity/minseok2995-ai/ls-stock-screener/README.md), [`tests/test_v29_daily_analysis.py`](/home/antigravity/minseok2995-ai/ls-stock-screener/tests/test_v29_daily_analysis.py), [`tests/test_v30_trend_cycle.py`](/home/antigravity/minseok2995-ai/ls-stock-screener/tests/test_v30_trend_cycle.py), 신규 [`tests/test_v32_gemini_pause.py`](/home/antigravity/minseok2995-ai/ls-stock-screener/tests/test_v32_gemini_pause.py)). `index.html`·`watchlist.html`·`holdings.html`·`common.js`·`supabase_schema.sql`·`scripts/*.sql`·`STRATEGY.md`·`TEST_REPORT.md` `git diff --stat` **`0 line`**. (`6ea6a98..0245422` 범위에 `STRATEGY.md`가 보이는 것은 전략 커밋 `8a35925` 때문이며 개발 커밋과 무관.)
* **기존 테스트 완화·삭제 여부**: diff 전수 확인 — `test_v29`는 워크플로 단언 `'10'→'0'` 1줄만 변경, `test_v30`은 final 슬롯 케이스를 (2-A) `AI_TOP_N` 미지정 시 Gemini 호출 `0회`·전 행 `SKIPPED` 단언 신설 + (2-B) `AI_TOP_N="2"` 명시 시 기존 `gemini-3.5-flash-lite` 호출 단언 유지로 **강화**(삭제·완화 `0건`).
* **테스트 결과 (`총 175 / 175 통과`)**: `test_screener_verification.py` **8/8 OK** · `unittest discover -s tests` **167/167 OK** (163 + 신규 4) · `run_daily_screener.py --mode verify` **Exit 0**.
* **독립 검증 결과 (`AC-72`)**:
  * 상수·워크플로: `DEFAULT_AI_TOP_N == 0`, `DEFAULT_TOP_PICK_LIMIT == 10` 분리, `AI_TOP_N: ${{ vars.AI_TOP_N || '0' }}` 확인(`GEMINI_API_KEY`·`GEMINI_MODEL` 보존). [`resolve_ai_top_n`](/home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L3996-L4005) 실측: `None/''/'0'/'abc'/'-5' → 0`, `'10' → 10`, `'300' → 200`.
  * 호출 `0회`: `has_api_key=bool(eff_key and run_step2_and_3 and eff_top_n>0)`, `eff_top_n<=0`이면 Step 2 블록 전체 생략 + `[DSA-Step2] Gemini AI 코멘트 추출 비활성(AI_TOP_N=0) — 호출 생략` 로그(추가 Upsert 없음). `test_v30`(2-A)·`test_v32`에서 키 설정 final 슬롯에도 네트워크 호출 `0`, 전 행 `ai_status=='SKIPPED'`·`ai_summary is None` 통과.
  * Top 10 정량 순위(합성 60행 직접 실행, [`rank_daily_supply_candidates`](/home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L4819)): `AI_TOP_N=0` → `daily_rank` 1..60 연속, 자격 통과 상위 정확히 `10`개만 `is_top_pick`, 미자격 `is_top_pick=True` `0`, `PENDING` `0`. `AI_TOP_N=10` → top_pick 10 + `PENDING` 10(재개), `3` → 3/3. 운영 DB `2026-11-27` `is_top_pick=True` 정확히 `10행`(전부 `SKIPPED`).
  * 과거 AI 이력 보존: 운영 DB에 `ai_status='SUCCESS'` 과거 행 `40건`(`2026-11-17 ~ 11-20`) 존재(읽기 전용 확인). Step 3 [`backfill_daily_supply_outcomes`](/home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L5254)는 조회한 기존 행 전체(`dict(row)`)에 `ret_*`·`outcome_updated_at`·`updated_at`만 덮어쓰므로 `ai_summary/ai_status/ai_model` 기존 값이 그대로 재기록(보존)되며, v3.2는 이 경로 무변경.
  * 프론트엔드: [`index.html#L1293`](/home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L1293) `dsa.ai_status !== "SUCCESS" || !dsa.ai_summary`이면 AI 카드만 숨김(널 안전) → `SKIPPED` 행 선택 시 오류 없음(코드 무변경, 정적 검수).
  * 무코드 재개: `build_gemini_stock_payload`·`call_gemini_stock_summary`·`populate_gemini_summaries` diff `0 line`(원형 보존), `AI_TOP_N=2` 명시 시 기본 `gemini-3.5-flash-lite` 호출 경로 재동작(test_v30 2-B 통과).
  * ℹ️ 운영 참고(결함 아님): ① 같은 날 final 슬롯 재실행 시 당일 행은 Step 1 Upsert로 `SKIPPED/None` 재기록되므로 당일 기존 AI 코멘트는 소실(과거 일자 무영향, `2026-11-27` 행은 이미 `SKIPPED`). ② `AI_TOP_N>20` 지정 시 `is_top_pick`은 10개로 제한되나 AI 대상은 `AI_TOP_N`개(기존 동작). ③ GitHub 저장소 변수 `AI_TOP_N`이 이미 설정돼 있으면 기본값 `'0'`을 덮어쓰므로 중단/재개는 변수로 제어.
* **운영 DB 무손상**: 검수 중 GET만 사용(`stocks_master` 유니버스 1,466 · 관심 46 · 보유 1 · 제외 0 · DSA(2026-11-27) 206 변동 없음).

---

### 1.1 `v3.2` 요구사항 (`AC-72` ~ `AC-73`) 검수 결과표

| 검증 코드 | 검증 항목 (`STRATEGY.md` 18절) | `v3.2` (`0245422`) 검수 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-72** | **Gemini AI 코멘트 기본 중단(API 호출 `0회`) · Top 10 정량 순위·`is_top_pick`·추세 스냅샷·과거 AI 이력·함수 원형 보존 · 무코드 재개** | • `DEFAULT_AI_TOP_N=0`/`DEFAULT_TOP_PICK_LIMIT=10`, 워크플로 `'0'` 기본<br>• final 슬롯+API 키에서도 호출 `0`·Step 2 Upsert 없음·비활성 로그·전 행 `SKIPPED`<br>• 상위 10 `is_top_pick`, 순위 연속, 과거 AI `SUCCESS` 40건 보존, 프론트 널 안전<br>• `AI_TOP_N` 양수 시 Gemini 경로 재동작 | **PASS** |
| **AC-73** | **전체 회귀 + 신규 테스트 100% PASS 및 범위 준수** | • `175/175` PASS, 프론트 4종·SQL·`STRATEGY.md` `0 line` 무변경 | **PASS** |

---

### 1.2 기존 요구사항 (`AC-1` ~ `AC-71`) 회귀 검증 요약 (`v3.2` 적용 후)

| 검증 코드 | 검증 항목 요약 | `v3.2` (`0245422`) 적용 후 회귀 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-1 ~ AC-18** | 유니버스, EMA·순수기관 수식, 배치 Cron, 멱등성 가드, 엑셀 | `test_screener_verification.py`(8/8), `test_v2_acceptance.py`(9/9), `--mode verify` Exit 0 | **PASS** |
| **AC-19 ~ AC-23** | 차트 5년·수급 3년 적재, 앵커 EMA, 무지연 PK 조회 | `test_v23_acceptance.py`(19/19) | **PASS** |
| **AC-24 ~ AC-29** | 3페이지 분리, 추천/비추천, 영구제외, 스마트 병합, 보유/청산 | `test_v24_watchlist_holdings.py`(29/29), 운영 DB(`관심 46 · 보유 1 · 제외 0`) 무손상 | **PASS** |
| **AC-30 ~ AC-48** | 패턴·4축 평가, 프로 차트, 2회 배치, 실시간 시세 | `test_v25`(17/17) · `test_v26`(11/11) · `test_v27`(18/18) | **PASS** |
| **AC-49 ~ AC-56** | Keep-Alive, 프리페치, 정속 페이서, 50종목 묶음 Upsert | `test_v28_batch_perf.py`(21/21), 3-POST 순서 계약 및 비-409 단건 격리 유지 | **PASS** |
| **AC-57 ~ AC-60** | 일일 수급 분석·Gemini Top N·사후 복기 | `test_v29_daily_analysis.py`(10/10) | **PASS** |
| **AC-61 ~ AC-66** | 양극 추세 사이클(16단계·63세부현황), 750봉 패리티, 스냅샷 격리 | `test_v30_trend_cycle.py`(6/6) · `test_v301_fixes.py`(9/9), 프론트·추세 스키마 무변경 | **PASS** |
| **AC-67 ~ AC-71** | 비허용 시간대 차단, 분기 유니버스 완주율, t1463 409·신규상장 백필, 크론 슬림화 | `test_v31_batch_schedule.py`(14/14) 및 전체 회귀 통과 | **PASS** |

---

## 2. 버그 및 수정 요청 트래커 (Issue & Fix Tracker)

### 🚨 2.1 `[프로그램 개발 및 수정]` 대화창 신규 수정 요청 사항

> [!NOTE]
> **현재 미해결 수정 요청 사항 없음 (`0건`).** `v3.2` (`0245422`)의 `AC-72 ~ AC-73` 및 회귀 `AC-1 ~ AC-71` 전수 합격하여 `[프로그램 개발 및 수정]` 대화창 추가 지시서는 없습니다.
>
> **AI 코멘트 재개 방법(무코드)**: GitHub Actions 저장소 변수 `AI_TOP_N`을 양수(예: `10`)로 설정하면 즉시 재개. 중단 유지는 변수 미설정 또는 `0`.
>
> **차주 확인 권장**: `2026-11-30(월) 16:05 KST` 배치 로그에 `[DSA-Step2] Gemini AI 코멘트 추출 비활성(AI_TOP_N=0) — 호출 생략` 및 당일 `is_top_pick=True` 10행 확인.
---

### ✅ 2.2 해결 완료된 이슈 히스토리 아카이브

* **[v3.2 검증 완료 (`0245422`)]** Gemini AI 코멘트 기본 중단 전수 합격(`AC-72 ~ AC-73`, `175/175`): `DEFAULT_AI_TOP_N=0`·워크플로 `'0'`, 키 설정 final 슬롯에서도 API 호출 `0회`, Top 10 `is_top_pick`·순위·과거 AI 이력·함수 원형 보존, `AI_TOP_N` 양수 시 무코드 재개. 신규 결함 `0건`.
* **[v3.1 검증 완료 (`775a007`)]** 1일 2회 정기 배치 무결점 정상화 전수 합격(`AC-67 ~ AC-71`, 총 `171/171` 테스트 통과): ① `is_allowed_auto_batch_window`로 평일 새벽·장중(`00:00~15:44`), 야간 데드존(`19:00~20:04`), 주말 자동 실행을 인증·DB·텔레그램 호출 `0회`로 즉시 `[SKIP-OFFHOURS]` 차단 + `fetch_latest_krx_trading_date` 장전 빈 일봉·`15:30` 이전 당일 봉 제외 + `universe_count == 0` 공회전 알림/DSA 차단(`AC-67`), ② 평일 `daily` 모드에서 시총 `700억` 일시 하회 기존 유니버스(`33종목`) 적재 유지로 완주율 `97.75% → 100.00%` 복원 및 분기 재산출(`rebuild_due=True`) 시 `DELETE` 없이 `is_universe=False` 하향 Upsert·KST 월 판별·프리페치 활성화(`AC-68`), ③ `t1463` 미등록 급등주 루프 전 시드 선등록(`1970-01-01`)·미달 롤백·`BatchUpsertBuffer` `HTTP 409` 자가 복구 및 상장 `65영업일 이하` 신규 상장주(`11종목`) 매회 백필 제거·초신규 1페이지 조회(`AC-69`), ④ `daily_batch.yml` 2중 백업 크론(`16:25`·`20:47 KST`) 슬림화 및 극소량(`0<=vol<=100`, `조흥` 등) 기적재 종목 완료 인정(`AC-70`), ⑤ 프론트엔드·DB 스키마·`STRATEGY.md` 무변경 준수(`AC-71`).
* **[v3.0.1 검증 완료 (`bf117fd`)]** v3.0 검수 이슈 6건 전부 해결: `ISSUE-023`(HIGH, Step 1-B 스냅샷이 `stocks_master` 시세·유동성 컬럼을 배치 시작 값으로 되돌려 영구 동결 → 추세 컬럼만 Upsert + 배치 후 master 재조회), `ISSUE-024`(MED, prelim 잔존 행 → Upsert 직후 `trade_date=eq.&shcode=not.in.()` 정리, 빈 결과 시 삭제 금지), `ISSUE-025`(MED, 308봉 윈도우로 진영 반전 `2.1%`·차트 재분류로 선택 이동 → 배치·리스트·모달·호버 750봉 통일, 1,000행 잘림 방지 단일 종목/페이지네이션 조회, 불일치 `0`), `ISSUE-026`(MED-LOW, v3.0 라벨의 `단기혼합` 오염 → 직접 집계 제외), `ISSUE-027`(LOW, PGRST204 폴백 미작동 → `HTTPError` 본문 판정), `ISSUE-028`(LOW, `0.1%` 정확 경계 부동소수 오차 → `-1e-9` 허용오차 3중 통일). 실DB 읽기 전용 드라이런 prelim `60.9초`(목표 ≤90초), 전체 `157/157` 테스트 합격, `AC-63` FAIL → PASS.
* **[v3.0 검증 (`a444979`)]** 양극 추세 사이클(16단계·63세부현황) 엔진 Python↔common.js↔index 내장본 `3,251`계열 `1,258,306봉` 불일치 `0`, 63/63 코드 도달, 신규 자격 기준·슬롯 게이트·`gemini-3.5-flash-lite` 기본값·스키마/마이그레이션 동치 확인(`148/148` 테스트). 배치 데이터 무결성 결함 등 `ISSUE-023 ~ 028` 발견으로 `AC-63` FAIL 판정 → `v3.0.1`에서 해결.
* **[v2.9 검증 완료 (`d667654`)]** `daily_supply_analysis` 일일 수급 전수 정량 분석(Step 1: `100점` 4축 스코어 · 4대 자격 필터 · 과열 5일선 눌림가/종가~5일선 밴드 매수참고가 · `low` 손절가 · `+7%/+15%` 목표가 · 유사조건 과거 승률, 운영 `1,466종목` 중 `192후보` `8.55초` 처리) + Top 10 Gemini AI 압축 요약(Step 2: `40봉×13원소` `~5.3KB` 페이로드 · `GEMINI_MODEL`/`AI_TOP_N` 환경변수 · 3워커 병렬 · `429/503` 백오프 재시도 · 무중단 예외 격리) + 사후 복기 자동 백필(Step 3: `ret_5d/10d/20d`, `max/min_ret_10d`, `365일` 보관 정리, `DSA_UPSERT_COLUMNS` 분리 멱등성) 및 운영 Supabase 테이블/GitHub Secret 준비 완료 확인, 전체 `142/142` 테스트(`AC-57 ~ AC-60` 및 `AC-1 ~ AC-56` 회귀) 전 항목 합격.
* **[v2.8.2 검증 완료 (`011bdf3`, 실전 `Run #44075513243` `28분 58초` 완주)]** 실전 `Run #43893079642`(`47분 25초`, `1.96s/종목`)에서 규명된 LS 서버 `t8410` 초당 1건(`1.00s`) 제한 및 재시도 슬롯 미갱신 도미노 페널티 해결 전수 합격: ① `TR_SERVER_FLOOR_BY_CD = {"t8410": 1.04, "t1717": 0.54}` 정속 예약으로 실시간 2-스레드 Keep-Alive E2E에서 `1.040s/종목` 정속 주행 및 실전 배치 `28분 58초 < 30분` 완주 달성, ② `_on_rate_limit_wait`의 `_tr_learned_floor` 즉시 승격(`1.04 ~ 1.30`)·`_global_learned_gap` 보정·`_acquire_tr_slot` 재예약으로 도미노 재시도 `0회` 원천 차단, ③ `[PERF]` 완료 로그 텔레메트리 및 전체 `132/132` 테스트(`AC-56`) 전 항목 합격.
* **[v2.8.1 검증 완료 (`f2e1b68`)]** 실전 2차 배치(`Run #43859068236`, `57분 56초`)에서 확인된 3대 잔여 병목 핫픽스 전수 합격: ① `supabase_prefetch_daily_context(..., target_codes=pf_codes)` 50종목 복합 PK 인덱스 청크 병렬 조회(`HTTP 500` 타임아웃 원천 제거, 운영 실DB `1,466종목` + 미해결 `63종목` 병렬 사전 해결까지 총 `6.52초`, 메인 루프 내 단건 DB GET `0회`, 3인자 경로와 불일치 `0건`), ② `ANCHOR_RECENT_CALENDAR_DAYS = 105` · `ANCHOR_RECENT_COUNT = 60` 조정으로 LS `t8410` 비압축 `100건` 상한 하 단일 페이지 호출(`1회 × 0.38s/종목`, `1,466종목` 이론 `11.28분 < 15분`) 보장, ③ `pair_pool.shutdown(wait=True)` 및 `len(supply_to_upsert)` 로그 정합성 반영 (`AC-54 ~ AC-55` 및 전체 `129/129` 테스트 합격).
* **[v2.8 검증 완료 (`e4f2eca`)]** `KeepAliveHttpPool`(영구 HTTP/TLS 재사용·끊김 재연결·`chunked+gzip`·`HTTPError` 호환), `supabase_prefetch_daily_context`(운영 실DB `2.11초` 일괄 프리페치, 단건 조회 `96.6%` 제거, `T-5` 확정 앵커 일관 선택), `LSApiClient` 경과시간 차감 페이서·적응형 백오프·`t8410`‖`t1717` 2-스레드 병렬(`ANCHOR-MISMATCH` 전체 재적재 보존), `BatchUpsertBuffer` 50종목 원자적 묶음 Upsert(`chart → supply → master`, 개별 격리 복구, 증분 수급 슬림화 및 누락일 치유, `1,463종목` `~11.3~13.0분 < 15분`) 및 전체 `127/127` 테스트(`AC-49 ~ AC-53`) 전 항목 합격.
* **[ISSUE-021 ~ ISSUE-022] `[해결 완료 (v2.7.1, 179f0cf)]`** `parseNaverRealtime` 주말·장전(`09:00 KST` 이전) 날짜 보정 + `normalizeQuoteForCandles` 캔들 대조 기반 평일 공휴일·장전 중복 스냅샷 차단 + `ls_realtime_bridge.py` `_kst_trade_date`/`_market_state` 및 `h.configured !== false` 체크로 가짜 당일 봉 복제·`전일비 100%` 오탐 완전 해소(`ISSUE-021`), `mountProChartPanel.setData` `d.liveQuote !== undefined` 처리·`holdings.html` `CLOSED` 선택 시 폴링 중지·PNG/클립보드 저장 시 `viewCandles()` 반영·단일 일봉 `change_rate` 폴백 완료(`ISSUE-022`) (`AC-44 ~ AC-48` 전 항목 합격).
* **[ISSUE-019 ~ ISSUE-020] `[해결 완료 (v2.6.1, f768119)]`** `index.html`(`text-[10.5px]`/`text-[11px]`, `px-[3px]`, `w-[6em]`) 및 `watchlist.html`(`text-[11px]`, `px-1`, `w-[7em]`) 슬림화로 `1920×1080(xl)`·`1180×900(lg)` 전 구간 좌측 테이블 `horizontalOverflowPx = 0px`·우측 버튼 절단 `0px` 달성(`ISSUE-019`), `mountProChartPanel` `[data-role="badges"]` 상시 렌더링(일반 차트 + `[🔍 크게 보기]` 모달 + `describeStockPattern` 자동 폴백)·배지 중복 제거·`240일/720일` 로드 후 추천/헤더/행 점 동기화·`sanitizeFilePart` 유니코드 이모지 정제 완료(`ISSUE-020`) (`AC-39 ~ AC-43` 전 항목 합격).
* **[v2.5.2 검증 완료 (`f7aa980`)]** 3페이지 와이드 뷰포트(`max-w-[1920px] 2xl:max-w-[96vw]`) 전면 개방, `watchlist.html` 좌측 `6컬럼`(`440/470px`) 초슬림화 + 우측 `#wlDetailHeader`(시총·등락폭·종합판단·패턴·기관수급·상태 2단 브리핑) 신설, 3페이지 프로 차트 대화면 확장(`560~760px` / `480~640px` / 모달 `max-w-[95vw]` `620~840px`)·하단 2열 배치·`ResizeObserver`/`resize` 자동 리사이즈(`AC-36 ~ AC-38`) 전 항목 합격.
* **[ISSUE-015 ~ ISSUE-018] `[해결 완료 (v2.5.1, 9bbc56f)]`** `index.html` 수급 `240건` 병렬 보강(`ISSUE-015`), 서브태그 중복 제거 및 비추천 `[하락채널저항]` `22/22` 노출(`ISSUE-016`), `holdings.html` 선택 행 캐시 격리·`setData` `dataKey` 리셋·`drawProChart` 상단 `ctx.clip()` 적용(`ISSUE-017`), `flag` 양봉(`C > O`) 조건 및 `watchlist.html` `종합판단` 정렬 토글(`ISSUE-018`) 해결 완료 (`AC-30 ~ AC-35` 합격).
* **[ISSUE-011 ~ ISSUE-014] `[해결 완료 (v2.4.1, 16f575d + 운영 DB RLS 해제/GRANT 반영)]`** 운영 Supabase 신규 3개 테이블 실서버 CRUD 정상화 및 `42501` 배너, 대바닥 출신 관심종목 이평 이탈 오판 제거, 제외관리 모달 복구·프리셋 체크박스 즉시 반영, 보유종목 현재가 목표가 배지 및 `CLOSED` 온디맨드 차트 로드(`AC-24 ~ AC-29`) 전 항목 합격.
* **[v2.3.1 검증 완료 (`353f92a`, `Run #43682739754` & `Run #43685346608`)]** 차트 5년(`2021-11-01~`, `1,678,171행`) · 수급 3년(`2023-11-01~`, `1,040,512행`) 비대칭 확장 백필 1회차 `2시간 44분` 100% 완주, 앵커 시드 EMA 연속성, 거래정지 `25종목` 미확정 오판 차단, `80분` 주기 토큰 자동 갱신 및 `271.8만 행` 대용량 DB 무지연(`AC-19 ~ AC-23`) 전 항목 합격.
* **[v2.2 검증 완료 (`6bfbbd5`)]** `[기관 수급 발생 종목]` 유동성·수급금액 제외 필터(`당일 기준` vs `3일 연속 3일 평균 기준`) 및 `[엑셀 저장]` 9개 컬럼 개편(`AC-16 ~ AC-18`) 전 항목 합격.
* **[v2.1 검증 완료 (`1aecd41`)]** `20:30 KST` 다중 백업 Cron, `KST` 표준시 고정, `--skip-if-completed` 멱등성 가드(`< 2.3초` 종료), `if: failure()` 장애 알림, Apps Script 외부 정각 웹훅(`AC-13 ~ AC-15`) 및 `두산에너빌리티(034020)` 백필 자동 복구 확인 완료.
* **[ISSUE-006 ~ ISSUE-010] `[해결 완료 (v1.4.3 ~ v2.0)]`** `PRIORITY_SHCODES` 제거, `has_2yr_history` 판정 분리, 장중 미확정 수급 차단, 복합 PK 병렬 조회 전환(`HTTP 500` 해소), `AC-1 ~ AC-12` 검증 체계 구축 완료.
* **[ISSUE-001 ~ ISSUE-005] `[해결 완료 (v1.4)]`** 1,463종목 시총 ≥ 700억 전수 유니버스 구축, 일봉·수급 500영업일 역순 슬라이딩 적재, Actions 360분 타임아웃 상향 완료.
