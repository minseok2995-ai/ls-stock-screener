# 🧪 LS 수급·차트 스크리너 검증 및 테스트 리포트 (`TEST_REPORT.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[검증 및 테스트]` 전담 대화창**에서 테스트 실행 결과, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md) 대조 검수, 데이터 정합성 검증 리포트, 발견된 버그 및 구체적인 코드 수정 제안을 기록하는 문서입니다.
> * **`[프로그램 개발 및 수정(메인)]` 대화창**은 작업 시작 전 본 `TEST_REPORT.md`와 `STRATEGY.md`를 확인하여 미해결 버그(`2.1절 신규 수정 요청 사항`)를 코드에 반영하고, 수정이 완료된 항목의 상태를 **`[해결 완료]`**로 업데이트합니다.

---

## 1. 최신 검수 요약 (`v2.8.2` 커밋 `011bdf3` 최종 전수 검수 — `AC-1 ~ AC-56` 전 항목 최종 PASS · TR 서버 물리 바닥 `1.04s` 정속 페이싱 및 `IGW00201` 도미노 재시도 원천 차단 입증)

* **검수 일시**: `2026-11-17 01:39 KST` (`2026-11-16 16:39 UTC`)
* **대상 커밋**: `011bdf3` — `perf(v2.8.2): TR 서버 물리 바닥 정속 페이서 및 IGW00201 도미노 재시도 차단` ([`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L1650-L1706) `14절` `AC-56` 전 요구사항 및 `AC-1 ~ AC-55` 전수 회귀)
* **단위·통합 테스트 스위트 및 회귀 검증 실행 결과 (`총 132 / 132 통과 — ALL PASS`)**:
  * `python3 test_screener_verification.py -v`: **8 / 8 통과 (`OK`, `0.010s`)**
  * `python3 -m unittest discover -s tests -v`: **124 / 124 통과 (`OK`, `6.23s` — [`test_v28_batch_perf.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/tests/test_v28_batch_perf.py) `21개`[`TestV282ServerFloorPacer` `AC-56` 신규 `3개` + `TestV281Hotfix` `2개` + `v2.8` `16개`] + `test_v27` `18개` + `test_v26` `11개` + `test_v25` `17개` + `test_v24` `29개` + `test_v23` `19개` + `test_v2` `9개`)**
  * `python3 run_daily_screener.py --mode verify`: **전 항목 정상 통과 (`Exit 0`, `1,466` 유니버스 · 차트 `1,234일` · 수급 `740일`[`1,061,706행`] · `2026-11-16` 확정 스크리닝 `124 / 87 / 52 / 42 / 1` 정합성 확인, 운영 DB `관심 46건 · 보유 1건 · 제외 0건` 읽기 전용 100% 보존)**
* **독립 심층 검증(실제 로컬 Keep-Alive HTTP 서버 · 2-스레드 `t8410`‖`t1717` 실시간 `monotonic/sleep` E2E · `1,466종목` 전수 시뮬레이션) 결과**:
  * ✅ **`AC-56` PASS ([`TR_SERVER_FLOOR_BY_CD`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L86) `1.04s` 정속 예약 · [`_on_rate_limit_wait`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L489-L518) 도미노 재시도 차단 · 자가 보정 학습 바닥값)**:
    * **실시간 벽시계(Wall-Clock) Keep-Alive HTTP + 2-스레드 `pair_pool`(`t8410`‖`t1717`) 증분 E2E 실측**: `1.000초` 슬라이딩 윈도우 제한을 강제하는 실제 로컬 HTTP 서버 대상으로 `8종목` 일일 증분 배치를 구동한 결과, 종목당 완료 시각 간격이 **`+1.039s ~ +1.040s`** (`t8410_arrival_gaps_sec = [1.041, 1.04, 1.04, 1.04, 1.04, 1.04, 1.04, 1.04]`)로 밀리초 단위까지 정확히 정속 예약되어 **`IGW00201` 발생 `0회` (`rate_limit_retry_count = 0`, 전체 8종목 완주 `8.46초`)** 를 실증했습니다(실전 `Run #43893079642`의 `1.96s/종목` 도미노 페널티 → **`1.04s/종목`으로 `46.9%` 단축**, `1,466종목` 기준 API `25.4분` · 전체 배치 **`~26.4분 < 30.0분`** 달성).
    * **기습 제한(`t1717 = 1.00s` 다중 페이지) 시 도미노 재시도 원천 차단 및 자가 보정 학습 실증**: `t1717`에도 `1.000초` 서버 제한을 건 다중 페이지 E2E(`8종목`, 총 `53회` TR 호출)에서 최초 `0.5402s` 발송 시 **단 `1회`만 `IGW00201`이 발생**한 직후 [`_on_rate_limit_wait`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L502-L518)가 즉시 `_tr_learned_floor['t1717'] = 1.04` 로 승격하고 재시도 발송 슬롯 자체를 [`_acquire_tr_slot`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L464-L484)으로 `_tr_last_ts`·`_global_last_ts`에 정식 예약하여, **나머지 전 구간(`52회` 호출)에서 도미노 `IGW00201` 재시도가 `0회`** 임을 입증했습니다.
    * **`HTTP 429`·연속 제한 에스컬레이션 및 `[PERF]` 텔레메트리 로그 검증**: `HTTP 429` / `IGW00103` / `IGW00201` 3회 연속 유입 시 `_tr_learned_floor` 단계적 상향(`1.04 → 1.10 → 1.16`, 상한 `1.30`) 및 `_global_learned_gap >= 0.52` 스파이크 방어선 가동과 [`run_standalone_batch`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L2920-L2927)의 `[PERF] 배치 루프 완료: ... (플러시 %d회 | TR호출 %d회 | 제한재시도 %d회 | 학습바닥 %s)` 출력 및 기존 `129개` 단위 테스트 하위 호환(`sleep_sec <= 0` 경로·`_acquire_tr_slot` 직접 호출 계약) 100% 유지를 확인했습니다.
    * **변경 범위 보호(`43458bc..011bdf3`)**: 수정 파일이 `STRATEGY.md`, `run_daily_screener.py`, `tests/test_v28_batch_perf.py` 3개에만 제한되어 프론트엔드·실시간 브릿지·DB 스키마 변경 **`0건`** 준수.

---

### 1.1 `v2.8.2` (`AC-56`) · `v2.8.1` (`AC-54 ~ AC-55`) · `v2.8` (`AC-49 ~ AC-53`) 최종 검수 결과표

| 검증 코드 | 검증 항목 (`STRATEGY.md` 12.6절 · 13.3절 · 14.2절) | 코드 감사 · 실시간 Keep-Alive 서버 병렬 E2E · 운영 Supabase 실DB(`1,466종목`) 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-56** | **TR 서버 물리 바닥값(`t8410: 1.04s`) 적용 · `IGW00201` 도미노 재시도 차단 · 자가 보정 학습 검증** | • 실제 Keep-Alive HTTP + 2-스레드 병렬 E2E에서 `t8410` 도착 간격 **`1.040s` 정속 유지(`IGW00201 = 0회`, `1,466종목` `~26.4분 < 30분`)**<br/>• `t1717` `1.00s` 기습 제한 시 최초 **`1회` 학습(`{'t1717': 1.04}`) 및 슬롯 재예약 후 연속 호출 도미노 재시도 `0회`**, `[PERF]` 텔레메트리 로그 및 **`132 / 132` 테스트 PASS** | **PASS** |
| **AC-54** | **50종목 PK 인덱스 청크 프리페치(`target_codes`) · 소수 폴백 병렬 사전 해결 · 루프 내 직렬 DB 조회 `0회` 검증** | • 운영 실DB `1,466종목` 대상 `shcode=in.(50개)&trade_date=in.(...)` PK 청크 `60회` + 미해결 `63종목` 병렬 사전 조회 **`6.52초` 완주(`HTTP 500 = 0건`)**, 메인 루프 단건 DB GET **`0회`** | **PASS** |
| **AC-55** | **`ANCHOR_RECENT_COUNT = 60` 단일 `t8410` 페이지 호출 보장 및 `0.38s` 증분 인자 전달 검증** | • LS `t8410` 비압축 회당 `100건` 상한 모사 65종목 E2E에서 종목당 정확히 **`1회` `t8410` 호출(`65종목 = 65회`)** 및 `sleep_override == 0.38` 전달(실전 `call_tr`에서 서버 바닥 `1.04s` 승격) 확인 | **PASS** |
| **AC-49 ~ AC-53** | **`KeepAliveHttpPool` · `T-5` 앵커 · `t8410`‖`t1717` 동치 · `BatchUpsertBuffer` 원자적 순서 · 범위 보호** | • HTTP/TLS 소켓 재사용·끊김 재연결, `T-5` 확정 앵커 일관 선택, 병렬↔순차 차트·수급·스크리닝 100% 동치, `chart → supply → master` 원자적 순서·개별 격리 복구, 프론트엔드·스키마 무변경 보존 | **PASS** |

---

### 1.2 기존 요구사항 (`AC-1` ~ `AC-48`) 회귀 검증 요약 (`v2.8.2` 적용 후 전 항목 PASS 유지)

| 검증 코드 | 검증 항목 요약 | `v2.8.2` (`011bdf3`) 적용 후 회귀 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-1 ~ AC-18** | 유니버스(`1,466종목`), EMA·순수기관 수식, 5중 배치 Cron, 멱등성 가드, 유동성 제외 필터, 9열 엑셀 | `test_screener_verification.py`(8/8), `test_v2_acceptance.py`(9/9), `--mode verify` 오차 `0건` (`2026-11-16` 확정 데이터 정합성 확인) | **PASS** |
| **AC-19 ~ AC-23** | 차트 5년(`1,234일`) · 수급 3년(`740일`) 비대칭 적재, 앵커 EMA, 양보 구간, 무지연 PK 조회 | `test_v23_acceptance.py`(19/19) 전 항목 정상 통과 | **PASS** |
| **AC-24 ~ AC-29** | 3페이지 분리, 추천/비추천 분류, 영구제외 즉시 반영, 스마트 병합, 보유/청산(`A안`), 텔레그램 폴백 | `test_v24_watchlist_holdings.py`(29/29) 통과, 운영 DB(`관심 46 · 보유 1 · 제외 0`) 읽기 전용 무손상 보존 | **PASS** |
| **AC-30 ~ AC-38** | 무미래참조 패턴·캔들·4축 100점 평가, 2단 프로 차트, 크게 보기·PNG 저장, 와이드 뷰포트 | `test_v25_pattern_chart.py`(17/17) 전 항목 통과 | **PASS** |
| **AC-39 ~ AC-43** | 1일 2회 배치(`16:05`/`20:30`), `역배열 추세돌파` 승격, 관심종목 매도권고 오탐 제거, 3페이지 초슬림 리스트 | `test_v26_acceptance.py`(11/11) 통과 및 `20:30 final` 슬롯 완주 결과(`Run #43893079642`) 실DB 정합성 확인 | **PASS** |
| **AC-44 ~ AC-48** | 상단 1줄 통합(`40px`), 4단계 실시간 시세 엔진·로컬 브릿지, 거래량 전일비(%), 실시간 봉·비개장일 가드 | `test_v27_acceptance.py`(18/18) 통과 및 프론트엔드·브릿지 파일 무변경 보존 | **PASS** |

---

## 2. 버그 및 수정 요청 트래커 (Issue & Fix Tracker)

### 🚨 2.1 `[프로그램 개발 및 수정]` 대화창 신규 수정 요청 사항

* **현재 미해결 버그 없음 (`0건`) — `AC-1 ~ AC-56` 전 항목 최종 합격(`ALL PASS`).**

---

### ✅ 2.2 해결 완료된 이슈 히스토리 아카이브

* **[v2.8.2 검증 완료 (`011bdf3`)]** 실전 `Run #43893079642`(`47분 25초`, `1.96s/종목`)에서 규명된 LS 서버 `t8410` 초당 1건(`1.00s`) 제한 및 재시도 슬롯 미갱신 도미노 페널티 해결 전수 합격: ① `TR_SERVER_FLOOR_BY_CD = {"t8410": 1.04, "t1717": 0.54}` 정속 예약으로 실시간 2-스레드 Keep-Alive E2E에서 `1.040s/종목` 정속 주행 및 `IGW00201` `0회`(`1,466종목` `~26.4분 < 30분`) 실증, ② `_on_rate_limit_wait`의 `_tr_learned_floor` 즉시 승격(`1.04 ~ 1.30`)·`_global_learned_gap` 보정·`_acquire_tr_slot` 재예약으로 도미노 재시도 `0회` 원천 차단, ③ `[PERF]` 완료 로그 내 `TR호출 / 제한재시도 / 학습바닥` 텔레메트리 출력 및 전체 `132/132` 테스트(`AC-56` 및 기존 `129개` 하위 호환) 전 항목 합격.
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
