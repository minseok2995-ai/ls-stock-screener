# 🧪 LS 수급·차트 스크리너 검증 및 테스트 리포트 (`TEST_REPORT.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[검증 및 테스트]` 전담 대화창**에서 테스트 실행 결과, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md) 대조 검수, 데이터 정합성 검증 리포트, 발견된 버그 및 구체적인 코드 수정 제안을 기록하는 문서입니다.
> * **`[프로그램 개발 및 수정(메인)]` 대화창**은 작업 시작 전 본 `TEST_REPORT.md`와 `STRATEGY.md`를 확인하여 미해결 버그(`2.1절 신규 수정 요청 사항`)를 코드에 반영하고, 수정이 완료된 항목의 상태를 **`[해결 완료]`**로 업데이트합니다.

---

## 1. 최신 검수 요약 (`v2.9` 커밋 `d667654` 최종 전수 검수 — `AC-1 ~ AC-60` 전 항목 최종 PASS · 일일 수급 전수 `100점` 정량 분석 · Top 10 Gemini AI 요약 · 사후 복기 파이프라인 무결성 입증)

* **검수 일시**: `2026-11-18 02:20 KST` (`2026-11-17 17:20 UTC`)
* **대상 커밋**: `d667654` — `feat(v2.9): 일일 수급 전수 정량 분석 · Top 10 Gemini AI 요약 · 사후 복기 파이프라인 구현` ([`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L1709-L1917) `15절` `AC-57 ~ AC-60` 전 요구사항 및 `AC-1 ~ AC-56` 전수 회귀)
* **단위·통합 테스트 스위트 및 회귀 검증 실행 결과 (`총 142 / 142 통과 — ALL PASS`)**:
  * `python3 test_screener_verification.py -v`: **8 / 8 통과 (`OK`, `0.011s`)**
  * `python3 -m unittest discover -s tests -v`: **134 / 134 통과 (`OK`, `5.81s` — 신규 [`test_v29_daily_analysis.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/tests/test_v29_daily_analysis.py#L1-L584) `10개`[`AC-57 ~ AC-60`] + `test_v28` `21개` + `test_v27` `18개` + `test_v26` `11개` + `test_v25` `17개` + `test_v24` `29개` + `test_v23` `19개` + `test_v2` `9개`)**
  * `python3 run_daily_screener.py --mode verify`: **전 항목 정상 통과 (`Exit 0`, `1,466` 유니버스 · 차트 `1,235일`[`1,679,450행`] · 수급 `741일`[`1,101,306행`] · `2026-11-17` 확정 스크리닝 `99 / 73 / 46 / 55 / 1` 정합성 확인, 운영 DB `관심 46건 · 보유 1건 · 제외 0건` 읽기 전용 100% 보존 및 실전 `v2.8.2` 배치 `Run #44075513243` `28분 58초 < 30분` 완주 확인)**
* **독립 심층 검증(운영 Supabase `1,466종목` 읽기 전용 실데이터 Step 1/2/3 시뮬레이션 · 경계값 정밀 대조 · PostgREST `PGRST102`/멱등성 검증) 결과**:
  * ✅ **`AC-57` PASS ([`score_daily_supply_candidate`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L3749-L4150) 4축 `100점` 채점 · 4대 자격 필터 · 과열/눌림 매수가 · 손절가 · 목표가 `+7%/+15%`)**:
    * **운영 실DB(`2026-11-17` 확정 데이터) 전수 시뮬레이션**: 전체 `1,466` 유니버스 중 수급 유입(`당일 >= 10%` 또는 `3일 누적 >= 10%`) **`192종목`**을 **`8.55초`** 만에 추출·채점 완료(`자격 통과 39종목` · `자격 미달 153종목`). 상위 선정 예: `1위 유한양행(000100, 정배열, 88.0점, 매수참고 82,073원 / 손절 80,300원 / 1차 87,818원 / 2차 94,384원, R:R 3.24)`, `2위 SK바이오팜(326030, 정배열, 86.45점)`, `3위 현대백화점(069960, 60일선위, 86.10점, 과열=True → 종가 96,000원 대신 5일선 눌림가 89,090원 자동 산출)`.
    * **경계값 전수 대조**: `avg_val_20d_eok`(`19.99` vs `20.00`), `real_inst_amt_eok`(`2.99` vs `3.00`), `close < open` vs `close >= open`, `avg_range_20d`(`2.49` vs `2.50`), 6단계 추세 점수(`18 / 15 / 14 / 11 / 10 / 5`), 과열 경계(`disp_ema5 4.99% vs 5.00%`, `rsi_14 71.99 vs 72.00`), `low >= entry_price_ref` 극단 케이스 `round(entry * 0.95)` 보정, 자격 미달 종목(`케이씨 029460, 85.95점, 거래대금20억미만`)의 `is_top_pick=False` 강제 후순위(`#40`) 배치가 [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L1722-L1771) `15.1절` 수식과 `0.00` 오차로 일치함을 확인했습니다.
  * ✅ **`AC-58` PASS ([`build_gemini_stock_payload`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L4195-L4296) 40봉 압축 · `GEMINI_MODEL`/`AI_TOP_N` 환경변수 · 3워커 병렬 · 무중단 예외 격리)**:
    * 실전 `1위 유한양행(000100)` 기준 압축 페이로드 크기는 **`5,263자` (`5,301 bytes`, 약 `1,700 토큰`, `recent_bars = 40봉 × 13원소`)**로 토큰 예산(`~2,000~2,500 토큰`) 이내에 수렴하며, 마크다운 코드펜스 응답·단일 문자열 `risk_points` 정규화, `HTTP 429/503` 지수 백오프 최대 3회 재시도([`call_gemini_stock_summary`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L4342-L4385)), `prelim` 슬롯 자동 생략 / `final` 슬롯 및 `ANALYSIS_FORCE_RUN=1` 실행([`should_run_v29_analysis`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L3356-L3362)), 키 미설정·개별 API 장애 시 `SKIPPED`/`ERROR` 격리 및 메인 배치 정상 종료([`run_standalone_batch`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L3021-L3045))를 검증했습니다.
  * ✅ **`AC-59` PASS ([`compute_signal_outcomes`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L4452-L4498) · [`backfill_daily_supply_outcomes`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L4500-L4588) · [`cleanup_old_daily_supply_analysis`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L4590-L4605))**:
    * `T+5` / `T+10` / `T+20` 종가 수익률 및 `T+1~T+10` 장중 최고/최저 수익률(`max_ret_10d`, `min_ret_10d`) 계산 정확성, 단계적 경과(`T+6`에 `ret_5d` 선백필 후 `T+11`에 `ret_10d` 추가 백필 시 기존 `ai_summary`·`ret_5d` 무손실 보존), [`DSA_UPSERT_COLUMNS`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L3268-L3330)에서 복기 컬럼을 분리해 동일 과거일 재실행 시 기적재 복기 성적표가 덮어써지지 않는 멱등성, `trade_date < ref_date - 365일` 자동 정리를 전수 확인했습니다.
  * ✅ **`AC-60` PASS (DDL 동치 · 운영 Supabase 테이블/GitHub Secret 준비 상태 확인 · 프론트엔드 무변경 · `142/142` 회귀 통과)**:
    * [`supabase_schema.sql`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/supabase_schema.sql#L284-L386) ↔ [`scripts/migration_v29_daily_supply_analysis.sql`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/scripts/migration_v29_daily_supply_analysis.sql#L1-L108) 간 컬럼·복합 PK(`trade_date, shcode`)·3개 인덱스·RLS 비활성화·`GRANT` 완전 동치, [`.github/workflows/daily_batch.yml`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/.github/workflows/daily_batch.yml#L98-L101) 환경변수 주입 확인, **운영 Supabase 내 `daily_supply_analysis` 테이블 생성 완료(`HTTP 200`) 및 GitHub Secrets `GEMINI_API_KEY` 등록 완료** 확인, 웹 프론트엔드(`index.html`, `watchlist.html`, `holdings.html`, `common.js`) 변경 **`0건`** 준수.

---

### 1.1 `v2.9` 신규 요구사항 (`AC-57` ~ `AC-60`) 최종 검수 결과표

| 검증 코드 | 검증 항목 (`STRATEGY.md` 15.4절) | 코드 감사 · 운영 실DB(`1,466종목` / `192후보`) 시뮬레이션 · 경계값 · 단위 테스트 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-57** | **정량 `100점` 스코어링 · 자격 필터 · 매수가/손절가/목표가(`+7%/+15%`) 정확성 검증** | • 운영 실DB `2026-11-17` 후보 `192종목` 전수 채점 `8.55초` 완주(`자격통과 39` · `미달 153`), 4대 자격 필터(`20억`/`3억`/양봉/`2.5%`) 및 과열(`disp_ema5 >= 5%` 또는 `RSI >= 72`) 5일선 눌림가·손절가(`low` 및 `0.95` 폴백)·목표가(`+7%`/`+15%`)·손익비 오차 `0건` | **PASS** |
| **AC-58** | **Gemini 압축 페이로드(`40봉+요약`) · 환경변수(`GEMINI_MODEL`, `AI_TOP_N`) · 무중단 폴백 검증** | • `40봉 × 13원소` 압축 페이로드(`~5.3KB`, `~1,700 토큰`), `GEMINI_MODEL`·`AI_TOP_N` 즉시 반영, `HTTP 429/503` 지수 백오프 3회 재시도, API 키 미설정/오류 시 `SKIPPED`/`ERROR` 격리 및 Step 1·Step 3·메인 배치 무중단 완주 확인 | **PASS** |
| **AC-59** | **사후 복기 수익률(`ret_5d/10d/20d`, `max/min_ret_10d`) 자동 백필 및 365일 보관 정리 검증** | • 경과일별 종가 수익률 및 `T+1~T+10` 장중 최고/최저 수익률 무오차 산출, 단계별 부분 백필 시 기존 `ai_summary`·기백필 수익률 보존, `DSA_UPSERT_COLUMNS` 분리로 재실행 멱등성 보장, `365일` 초과분 `DELETE` 정리 확인 | **PASS** |
| **AC-60** | **스키마 정합성 & 기존 `AC-1 ~ AC-56` (`132개` + 신규 `10개` = `142개`) 100% 회귀 통과 검증** | • `supabase_schema.sql` ↔ `migration_v29_daily_supply_analysis.sql` DDL·인덱스·`GRANT` 일치, 운영 Supabase `daily_supply_analysis` 및 GitHub Secret `GEMINI_API_KEY` 준비 완료 확인, 프론트엔드 무변경, 전체 **`142 / 142` 테스트 PASS** | **PASS** |

---

### 1.2 기존 요구사항 (`AC-1` ~ `AC-56`) 회귀 검증 요약 (`v2.9` 적용 후 전 항목 PASS 유지)

| 검증 코드 | 검증 항목 요약 | `v2.9` (`d667654`) 적용 후 회귀 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-1 ~ AC-18** | 유니버스(`1,466종목`), EMA·순수기관 수식, 5중 배치 Cron, 멱등성 가드, 유동성 제외 필터, 9열 엑셀 | `test_screener_verification.py`(8/8), `test_v2_acceptance.py`(9/9), `--mode verify` 오차 `0건` (`2026-11-17` 확정 데이터 `99/73/46/55/1` 확인) | **PASS** |
| **AC-19 ~ AC-23** | 차트 5년(`1,235일`) · 수급 3년(`741일`) 비대칭 적재, 앵커 EMA, 양보 구간, 무지연 PK 조회 | `test_v23_acceptance.py`(19/19) 전 항목 정상 통과 (`daily_chart` 약 `167.9만 행`, `daily_investor_supply` 약 `110.1만 행`) | **PASS** |
| **AC-24 ~ AC-29** | 3페이지 분리, 추천/비추천 분류, 영구제외 즉시 반영, 스마트 병합, 보유/청산(`A안`), 텔레그램 폴백 | `test_v24_watchlist_holdings.py`(29/29) 통과, 운영 DB(`관심 46 · 보유 1 · 제외 0`) 읽기 전용 무손상 보존 | **PASS** |
| **AC-30 ~ AC-38** | 무미래참조 패턴·캔들·4축 100점 평가, 2단 프로 차트, 크게 보기·PNG 저장, 와이드 뷰포트 | `test_v25_pattern_chart.py`(17/17) 전 항목 통과 및 프론트엔드 파일 무변경 유지 | **PASS** |
| **AC-39 ~ AC-48** | 1일 2회 배치(`16:05`/`20:30`), 역배열 돌파 승격, 상단 1줄(`40px`), 4단계 실시간 시세·브릿지 | `test_v26_acceptance.py`(11/11) · `test_v27_acceptance.py`(18/18) 전 항목 통과 | **PASS** |
| **AC-49 ~ AC-56** | Keep-Alive 풀, 50종목 PK 프리페치, `ANCHOR_RECENT_COUNT=60`, `t8410: 1.04s` 정속 페이서 | `test_v28_batch_perf.py`(21/21) 통과 및 실전 배치 `Run #44075513243` **`28분 58초` (`< 30분`)** 완주 실증 | **PASS** |

---

## 2. 버그 및 수정 요청 트래커 (Issue & Fix Tracker)

### 🚨 2.1 `[프로그램 개발 및 수정]` 대화창 신규 수정 요청 사항

* **현재 미해결 버그 없음 (`0건`) — `AC-1 ~ AC-60` 전 항목 최종 합격(`ALL PASS`).**

---

### ✅ 2.2 해결 완료된 이슈 히스토리 아카이브

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
