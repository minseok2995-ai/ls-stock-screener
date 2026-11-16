# 🧪 LS 수급·차트 스크리너 검증 및 테스트 리포트 (`TEST_REPORT.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[검증 및 테스트]` 전담 대화창**에서 테스트 실행 결과, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md) 대조 검수, 데이터 정합성 검증 리포트, 발견된 버그 및 구체적인 코드 수정 제안을 기록하는 문서입니다.
> * **`[프로그램 개발 및 수정(메인)]` 대화창**은 작업 시작 전 본 `TEST_REPORT.md`와 `STRATEGY.md`를 확인하여 미해결 버그(`2.1절 신규 수정 요청 사항`)를 코드에 반영하고, 수정이 완료된 항목의 상태를 **`[해결 완료]`**로 업데이트합니다.

---

## 1. 최신 검수 요약 (`v2.8.1` 커밋 `f2e1b68` 최종 전수 검수 — `AC-1 ~ AC-55` 전 항목 최종 PASS · 3대 잔여 병목 완전 제거 및 루프 내 DB GET `0회` 실증)

* **검수 일시**: `2026-11-16 23:59 KST` (`2026-11-16 14:59 UTC`)
* **대상 커밋**: `f2e1b68` — `perf(v2.8.1): 50종목 PK 청크 프리페치, 소수 종목 병렬 사전 해결, t8410 단건 0.38s 보장` ([`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L1596-L1647) `13절` `AC-54 ~ AC-55` 전 요구사항 및 `AC-1 ~ AC-53` 전수 회귀)
* **단위·통합 테스트 스위트 및 회귀 검증 실행 결과 (`총 129 / 129 통과 — ALL PASS`)**:
  * `python3 test_screener_verification.py -v`: **8 / 8 통과 (`OK`, `0.011s`)**
  * `python3 -m unittest discover -s tests -v`: **121 / 121 통과 (`OK`, `6.00s` — [`test_v28_batch_perf.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/tests/test_v28_batch_perf.py) `18개`[`TestV281Hotfix` `AC-54/AC-55` 신규 `2개` 포함] + `test_v27` `18개` + `test_v26` `11개` + `test_v25` `17개` + `test_v24` `29개` + `test_v23` `19개` + `test_v2` `9개`)**
  * `python3 run_daily_screener.py --mode verify`: **전 항목 정상 통과 (`Exit 0`, `1,466` 유니버스 · 차트 `1,234일` · 수급 `740일` · `2026-11-16` 확정 스크리닝 `124 / 87 / 52 / 42 / 1` 정합성 확인, 운영 DB `관심 46건 · 보유 1건 · 제외 0건` 읽기 전용 100% 보존)**
* **독립 심층 검증(운영 Supabase 실DB `1,466종목` PK 청크 실측 · 3인자 경로 100% 동치 대조 · `t8410` `100건` 상한 65종목 E2E) 결과**:
  * ✅ **`AC-54` PASS ([`supabase_prefetch_daily_context`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1756-L1952) `50종목` PK 청크 병렬 조회 · 미해결 소수 종목 사전 해결 · 루프 내 DB GET `0회`)**:
    * **운영 Supabase 실DB(`1,466` 유니버스 종목, 약 `273만 행`) 읽기 전용 실측**: `target_codes` 전달 시 `order=shcode.asc` 전체 일자 스캔 및 `Prefer: count=exact` **사용 `0건`** 으로 `shcode=in.(50개)&trade_date=in.(...)` 복합 PK 인덱스 쿼리 `60회`(차트 최대 `350행`·수급 최대 `200행 < limit=1000` 절단 위험 `0%`) + 미해결 소수 종목(`63종목`) 10워커 병렬 사전 조회까지 전 과정을 **`HTTP 500` 타임아웃 `0건`, 총 `6.52초`** 만에 완주했습니다(실전 `Run #43859068236`에서 발생했던 `daily_investor_supply` 비인덱스 정렬 스캔 타임아웃 및 `~33분` 직렬 폴백 원인 원천 제거).
    * **메인 종목 루프 내 단건 DB GET `0회` 달성**: 운영 실DB `1,466종목` 전수 시뮬레이션 결과 `anchor_by_code` **`1,464종목`**, `recent_status` **`1,459종목`**, `fallback_status_by_code` 사전 해결 **`63종목`** 으로 메인 루프 진입 후 [`lookup_prefetched_status`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1954-L1967) 미적중 단건 상태 조회 **`0회` (`main_loop_status_db_gets = 0`)** 및 증분 앵커 단건 폴백 조회 **`0회` (`main_loop_anchor_db_gets = 0`)** 를 실증했습니다.
    * **하위 호환 및 정합성 100% 동치**: `target_codes=None` 3인자 호출 시 기존 `_paginate_trade_date` 경로가 그대로 유지되며(`test_ac50` 무수정 통과), 운영 실DB `1,466종목` 전수 대조에서 PK 청크 경로와 3인자 경로 간 `anchor_by_code`·`recent_status`·`hist_chart_2y_codes`·`hist_supply_2y_codes` 불일치 **`0건` (`parity_vs_3arg_mismatches = 0`)** 확인 완료.
  * ✅ **`AC-55` PASS ([`ANCHOR_RECENT_COUNT = 60`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L64-L65) 단일 `t8410` 페이지 호출 보장 · `0.38s` 증분 페이싱 · 후처리 정합성)**:
    * LS Open API `t8410` 비압축(`comp_yn="N"`) 실제 상한(**1회 최대 `100건` 반환**)을 강제한 **65종목 E2E 파이프라인(`일반 2년+ 64종목 + 상장 6개월 신규상장주 1종목`)** 실행 결과, [`ANCHOR_RECENT_CALENDAR_DAYS = 105`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L64) · [`ANCHOR_RECENT_COUNT = 60`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L65) 적용으로 전 종목이 추가 역순 슬라이딩 없이 **종목당 정확히 `1회` `t8410` 호출(`total_t8410_calls = 65`, `max_t8410_calls_per_stock = 1`)** 로 완주되었으며(기존 `2회 × 0.45s = 0.90s/종목` → **`1회 × 0.38s/종목`**, TR 호출 수 `50%`·소요 시간 `57.8%` 절감), [`fetch_daily_chart`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L770-L772)의 `count <= 60` 분기를 통해 **`sleep_override = 0.38` (`TR_INTERVAL_INCREMENTAL`)** 이 100% 전달됨을 확인했습니다.
    * [`estimate_daily_batch_minutes`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L2017-L2024) 기본 `chart_interval`이 `0.38s`로 동기화되어 `1,466종목` 기준 예상 완주 시간 **`11.28분` (`< 15.0분`)** 을 기록했으며, 루프 종료 시 [`pair_pool.shutdown(wait=True)`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L2870-L2871) 정상 대기 종료 및 진행 로그 실 적재 수급 건수(`차트 5일·수급 10일 적재 완료`, [`len(supply_to_upsert)`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L2859)) 정합성까지 확인 완료했습니다.
    * 변경 범위 감시(`8d87129..f2e1b68`): 수정 파일이 `STRATEGY.md`, `run_daily_screener.py`, `tests/test_v28_batch_perf.py` 3개에만 엄격히 제한되어 프론트엔드·실시간 브릿지·DB 스키마 변경 **`0건`** 준수.

---

### 1.1 `v2.8.1` 신규 합격 기준 (`STRATEGY.md` 13.3절 — `AC-54` ~ `AC-55`) 및 `v2.8` (`AC-49` ~ `AC-53`) 최종 검수 결과표

| 검증 코드 | 검증 항목 (`STRATEGY.md` 12.6절 · 13.3절) | 코드 감사 · 운영 Supabase 실DB(`1,466종목`) · `t8410` `100건` 상한 65종목 E2E 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-54** | **50종목 PK 인덱스 청크 프리페치(`target_codes`) · 소수 폴백 병렬 사전 해결 · 루프 내 직렬 DB 조회 `0회` 검증** | • 운영 실DB `1,466종목` 대상 `shcode=in.(50개)&trade_date=in.(...)` PK 청크 `60회`(`order=`·`count=exact` 미사용, 청크당 최대 `350행 < 1,000행`) + 미해결 `63종목` 10워커 병렬 사전 조회 **`6.52초` 완주(`HTTP 500 = 0건`)**<br/>• 메인 루프 단건 상태/앵커 DB GET **`0회`**, 3인자(`target_codes=None`) 하위 호환 및 전수 동치 불일치 **`0건`** | **PASS** |
| **AC-55** | **`ANCHOR_RECENT_COUNT = 60` 단일 `t8410` 페이지 호출 보장 및 `0.38s` 증분 페이싱 검증** | • LS `t8410` 비압축 회당 `100건` 상한 모사 65종목 E2E에서 종목당 정확히 **`1회` `t8410` 호출(`65종목 = 65회`)** 및 `sleep_override == 0.38` 100% 전달 확인<br/>• `1,466종목` 예상 시간 **`11.28분 (< 15분)`**, `pair_pool.shutdown(wait=True)`·`len(supply_to_upsert)` 로그 반영, 전체 **`129 / 129` 테스트 PASS** | **PASS** |
| **AC-49** | **표준 라이브러리 `KeepAliveHttpPool` 소켓 재사용 · 끊김 자동 복구 · `gzip` 해제 · `HTTPError` 호환 검증** | • HTTP/TLS 단일 소켓 재사용, `chunked+gzip` 해제, `RemoteDisconnected` 자동 재연결, `HTTPError` 호환, 테스트 소켓 `pool.close()` 정리 확인 | **PASS** |
| **AC-50 ~ AC-53** | **일괄 프리페치 `T-5` 앵커 · `LSApiClient` 페이서 & `t8410`‖`t1717` 병렬 · `BatchUpsertBuffer` 원자적 순서 · 범위 보호** | • `T-5` 확정 앵커 일관 선택, 병렬↔순차 차트·수급·스크리닝 100% 동치(`ANCHOR-MISMATCH` 전체 재적재 보존), `chart → supply → master` 원자적 순서·개별 격리 복구, 프론트엔드·스키마 무변경 보존 | **PASS** |

---

### 1.2 기존 요구사항 (`AC-1` ~ `AC-48`) 회귀 검증 요약 (`v2.8.1` 적용 후 전 항목 PASS 유지)

| 검증 코드 | 검증 항목 요약 | `v2.8.1` (`f2e1b68`) 적용 후 회귀 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-1 ~ AC-18** | 유니버스(`1,466종목`), EMA·순수기관 수식, 5중 배치 Cron, 멱등성 가드, 유동성 제외 필터, 9열 엑셀 | `test_screener_verification.py`(8/8), `test_v2_acceptance.py`(9/9), `--mode verify` 오차 `0건` (`2026-11-16` 확정 데이터 정합성 확인) | **PASS** |
| **AC-19 ~ AC-23** | 차트 5년(`1,234일`) · 수급 3년(`740일`) 비대칭 적재, 앵커 EMA, 양보 구간, 무지연 PK 조회 | `test_v23_acceptance.py`(19/19) 전 항목 정상 통과 | **PASS** |
| **AC-24 ~ AC-29** | 3페이지 분리, 추천/비추천 분류, 영구제외 즉시 반영, 스마트 병합, 보유/청산(`A안`), 텔레그램 폴백 | `test_v24_watchlist_holdings.py`(29/29) 통과, 운영 DB(`관심 46 · 보유 1 · 제외 0`) 읽기 전용 무손상 보존 | **PASS** |
| **AC-30 ~ AC-38** | 무미래참조 패턴·캔들·4축 100점 평가, 2단 프로 차트, 크게 보기·PNG 저장, 와이드 뷰포트 | `test_v25_pattern_chart.py`(17/17) 전 항목 통과 | **PASS** |
| **AC-39 ~ AC-43** | 1일 2회 배치(`16:05`/`20:30`), `역배열 추세돌파` 승격, 관심종목 매도권고 오탐 제거, 3페이지 초슬림 리스트 | `test_v26_acceptance.py`(11/11) 통과 및 `20:30 final` 슬롯 완주 결과(`Run #43859068236`) 실DB 정합성 확인 | **PASS** |
| **AC-44 ~ AC-48** | 상단 1줄 통합(`40px`), 4단계 실시간 시세 엔진·로컬 브릿지, 거래량 전일비(%), 실시간 봉·비개장일 가드 | `test_v27_acceptance.py`(18/18) 통과 및 프론트엔드·브릿지 파일 무변경 보존 | **PASS** |

---

## 2. 버그 및 수정 요청 트래커 (Issue & Fix Tracker)

### 🚨 2.1 `[프로그램 개발 및 수정]` 대화창 신규 수정 요청 사항

* **현재 미해결 버그 없음 (`0건`) — `AC-1 ~ AC-55` 전 항목 최종 합격(`ALL PASS`).**

---

### ✅ 2.2 해결 완료된 이슈 히스토리 아카이브

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
