# 🧪 LS 수급·차트 스크리너 검증 및 테스트 리포트 (`TEST_REPORT.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[검증 및 테스트]` 전담 대화창**에서 테스트 실행 결과, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md) 대조 검수, 데이터 정합성 검증 리포트, 발견된 버그 및 구체적인 코드 수정 제안을 기록하는 문서입니다.
> * **`[프로그램 개발 및 수정(메인)]` 대화창**은 작업 시작 전 본 `TEST_REPORT.md`와 `STRATEGY.md`를 확인하여 미해결 버그(`2.1절 신규 수정 요청 사항`)를 코드에 반영하고, 수정이 완료된 항목의 상태를 **`[해결 완료]`**로 업데이트합니다.

---

## 1. 최신 검수 요약 (`v2.8` 커밋 `e4f2eca` 최종 전수 검수 — `AC-1 ~ AC-53` 전 항목 최종 PASS · 일일 배치 초고속 파이프라인 무결성 입증)

* **검수 일시**: `2026-11-16 19:47 KST` (`2026-11-16 10:47 UTC`)
* **대상 커밋**: `e4f2eca` — `perf(v2.8): Keep-Alive 풀, 일괄 프리페치, TR 페이서, t8410||t1717 병렬, 50종목 버퍼 Upsert` ([`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L1483-L1593) `12절` `AC-49 ~ AC-53` 전 요구사항)
* **단위·통합 테스트 스위트 및 회귀 검증 실행 결과 (`총 127 / 127 통과 — ALL PASS`)**:
  * `python3 test_screener_verification.py -v`: **8 / 8 통과 (`OK`)**
  * `python3 -m unittest discover -s tests -v`: **119 / 119 통과 (`OK`, `5.39s` — 신규 [`test_v28_batch_perf.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/tests/test_v28_batch_perf.py) `16개` + `test_v27` `18개` + `test_v26` `11개` + `test_v25` `17개` + `test_v24` `29개` + `test_v23` `19개` + `test_v2` `9개`)**
  * `python3 run_daily_screener.py --mode verify`: **전 항목 정상 통과 (`Exit 0`, `1,463~1,464` 유니버스 · 차트 `1,234일` · 수급 `740일` · `2026-11-16` 스크리닝 `123 / 87 / 53 / 41 / 1` 정합성 확인, 운영 DB `관심 55건 · 보유 1건 · 제외 0건` 읽기 전용 100% 보존)**
* **독립 심층 검증(로컬 TLS 1.3 서버 · 운영 Supabase 실DB 프리페치 실측 · 65종목 병렬↔순차 E2E 정합성 대조) 결과**:
  * ✅ **`AC-49` PASS ([`KeepAliveHttpPool`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L118-L242) 영구 HTTP/HTTPS 소켓 재사용 · 끊김 재연결 · `chunked+gzip` · `HTTPError` 호환)**:
    * 로컬 HTTP 및 **실제 TLS(`https://127.0.0.1:{port}`) 서버** 대상 연속 5회 호출(`Transfer-Encoding: chunked` + `Content-Encoding: gzip` 및 `HTTP 429 → urllib.error.HTTPError` 바디 소비 포함)에서 **단일 TLS 소켓 재사용(`connect_count = 1`)** 및 비표준 포트 단일 `Host` 헤더(`127.0.0.1:{port}`, 중복 헤더 `0건`) 확인 완료.
    * 서버 측 유휴 소켓 강제 종료(`RemoteDisconnected`) 중 `POST` JSON 전송 시 바디·헤더 변이 없이 **새 소켓 1회 자동 재연결(`connect_count = 2`)** 성공, `6`워커 멀티스레드 동시 요청(`30회`) 시 `threading.local()` 독립 소켓 격리(`connect_count = 6`) 및 프록시 환경 `urllib` 자동 폴백 확인 완료.
  * ✅ **`AC-50` PASS ([`supabase_prefetch_daily_context`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1756-L1869) 운영 Supabase 실DB 프리페치 `2.11초` · 사전 조회 `96.6%` 제거)**:
    * 운영 Supabase 실DB(`1,464` 유니버스 종목, 약 `262만 행`) 대상 읽기 전용 실측 결과, `Prefer: count=exact` **사용 `0건`** 으로 단 `23회` 인덱스 페이지네이션(`order=shcode.asc`)을 **`2.11초`** 만에 완료했습니다.
    * 실DB 유니버스 적중률: **`anchor_by_code` `1,462 / 1,464종목 (99.86%)`**, **`lookup_prefetched_status` `1,401 / 1,464종목 (95.70%)`** (상장 2년 미만 신규상장주 등 `63종목`만 단건 폴백 → 기존 `4,392회` 직렬 GET 대비 **`96.6%` 절감**).
    * `2026-11-16`(`final`, 당일 행 적재 후) 기준 `["2026-11-09", "2026-11-06", "2026-11-05"]` 및 `2026-11-17`(`prelim`, 당일 행 적재 전) 기준 `["2026-11-10", "2026-11-09", "2026-11-06"]`으로 `16:05`·`20:30` 모두 정확히 **`T-5` 확정 앵커**를 일관 선택하며, 계층 표본 `16종목` 대조 결과 단건 조회 대비 불일치 **`0건`** 확인 완료.
  * ✅ **`AC-51` PASS ([`LSApiClient`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L443-L955) 경과시간 차감 페이서 · 적응형 백오프 · `t8410`‖`t1717` 병렬 수집 · `ANCHOR-MISMATCH` 100% 동치)**:
    * `time.monotonic()` 기반 `_acquire_tr_slot` 경과시간 차감(`0.10s` 경과 시 `0.28s`만 대기), `IGW00201`/`429` 적응형 지연 가산(상한 `+0.30s`), `6`스레드 동시 `401`/`IGW00121` 발생 시 단일 토큰 재발급(`calls = 1`) 확인 완료.
    * `80ms` 네트워크 RTT 시뮬레이션 하 `5종목` 병렬 수집 실측 시간이 **`1.721초`**(기존 순차 `6.300초` 대비 API 계층 단독 **`3.66배`** 단축)로 계측되었으며, **65종목 E2E 파이프라인(`일반 63 + 액면분할 ANCHOR-MISMATCH 1 + 직전 누락 1`, `20:30 final` 덮어쓰기)** 에서 병렬·프리페치·버퍼 경로와 기존 순차 경로의 최종 `daily_chart`(EMA 5~240)·`daily_investor_supply`(순수기관 6대 주체 수식)·`stocks_master`·`screened_1d`·`screened_3d`가 **비트 단위까지 100% 일치(`오차 0건`, `ANCHOR-MISMATCH` 종목 자동 10년 전체 재적재 확인)** 함을 입증했습니다.
  * ✅ **`AC-52` PASS ([`BatchUpsertBuffer`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1872-L1928) `50종목` 원자적 순서 `chart → supply → master` · 개별 격리 복구 · `15분 이내` 목표 속도 달성)**:
    * `needs_full_2yr` 즉시 플러시·`50종목` 배치 플러시·루프 종료 잔여분 플러시 3가지 트리거 모두 엄격히 **`daily_chart` → `daily_investor_supply` → `stocks_master`(`updated_at` 최신화)** 순서를 준수하며(`4,389회 POST → ~90회 POST`, **약 `98%` 감소**), 묶음 실패 시 1종목 단위 격리 재시도로 정상 종목 유실 `0건` 보장 확인 완료.
    * 증분 수급 슬림화 적용 시 일반 종목은 최근 `10영업일`(`50종목 = 500행 = 1 POST`)만 전송하면서 수급 지연 종목(`T-14`)은 자동으로 `15영업일`치를 전송해 누락일을 자가 치유함을 실증했습니다.
    * `1,463종목` 기준 예상 완주 시간([`estimate_daily_batch_minutes`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1920-L1928)): 기본(`0.45s/0.38s`) **`12.97분`** / 단건(`0.38s`) **`11.27분`** 으로 합격 기준 **`15분 이내`(`~10~13분`, 기존 `~118분` 대비 약 `9.1~10.5배` 단축)** 충족.
  * ✅ **`AC-53` PASS (기존 `AC-1 ~ AC-48` 전 스위트 무결성 회귀 `127 / 127 PASS` 및 수정 범위 보호 준수)**:
    * `0d9e952..e4f2eca` 변경 파일이 `run_daily_screener.py`, `README.md`, `STRATEGY.md`, `tests/test_v28_batch_perf.py` 4개에 국한되어 검증 완료된 프론트엔드·브릿지·스키마(`index.html`, `watchlist.html`, `holdings.html`, `common.js`, `scripts/ls_realtime_bridge.py`, `supabase_schema.sql`) 무변경 계약 100% 준수.

---

### 1.1 `v2.8` 신규 합격 기준 (`STRATEGY.md` 12.6절 — `AC-49` ~ `AC-53`) 최종 검수 결과표

| 검증 코드 | 검증 항목 (`STRATEGY.md` 12.6절) | 코드 감사 · 로컬 TLS 서버 · 운영 Supabase 실DB(`1,464종목`) · 65종목 E2E 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-49** | **표준 라이브러리 `KeepAliveHttpPool` 소켓 재사용 · 끊김 자동 복구 · `gzip` 해제 · `HTTPError` 호환 검증** | • HTTP 및 TLS(`https`) 연속 호출 시 단일 소켓 재사용(`connect_count = 1`), `chunked + gzip` 투명 디코딩, 비표준 포트 단일 `Host` 헤더 확인<br/>• `RemoteDisconnected` 시 `POST` 바디 손실 없이 투명 재연결(`connect_count = 2`), `HTTP 4xx/5xx` 시 바디 소비 후 `urllib.error.HTTPError` 발생 및 소켓 재사용 유지, 프록시 환경 `urllib` 자동 폴백 확인 | **PASS** |
| **AC-50** | **배치 사전 일괄 프리페치(`supabase_prefetch_daily_context`) 정합성 · 무타임아웃 · 신규상장/Mock 폴백 검증** | • 운영 Supabase 실DB 대상 `Prefer: count=exact` `0건`, `order=shcode.asc` 인덱스 스캔 `23회`로 **`2.11초`** 완료 (`anchor_by_code` `99.86%`, `recent_status+2Y` `95.70%` 적중, 직렬 GET `96.6%` 제거)<br/>• `16:05`·`20:30` 모두 `T-5` 확정 앵커 일관 선택, 2년 미만 신규상장주(`63종목`) 및 `unittest.mock` 패치 환경 단건 조회 폴백 오차 `0건` | **PASS** |
| **AC-51** | **`LSApiClient` 스레드 안전 경과시간 차감 페이서 · 적응형 백오프 · `t8410`‖`t1717` 병렬 수집 및 `ANCHOR-MISMATCH` 검증** | • `time.monotonic()` 경과시간 차감 대기, `IGW00201`/`429` 시 `_tr_extra_delay` 적응형 증가(상한 `0.30s`), 멀티스레드 단일 토큰 갱신(`calls = 1`) 확인<br/>• `t8410`‖`t1717` 2-스레드 병렬 실행 시 순차 실행과 차트 EMA·순수기관 6대 주체 수급·`screened_1d/3d` 100% 일치 및 `ANCHOR-MISMATCH` 시 10년 전체 재적재 정상 작동 | **PASS** |
| **AC-52** | **`50종목` 배치 버퍼 Upsert 원자적 순서(`chart → supply → master`) · 개별 격리 복구 · 목표 속도(`15분 이내`) 검증** | • 모든 플러시에서 `daily_chart` → `daily_investor_supply` → `stocks_master`(`updated_at` 최신화) 원자적 순서 엄수(`POST ~98%` 절감), 묶음 오류 시 개별 종목 폴백으로 정상 종목 유실 `0건`, 직전 수급 누락일(`T-14`) 자동 치유 확인<br/>• `1,463종목` 예상 완주 시간 **`11.27분 ~ 12.97분 (< 15.0분)`** 달성 입증 | **PASS** |
| **AC-53** | **기존 `AC-1 ~ AC-48` 전 스위트 무결성 회귀 및 범위 준수 검증** | • `test_screener_verification.py`(8/8) + `tests/test_*.py`(119/119) = **`127 / 127` 100% PASS**, `--mode verify` `Exit 0`, 프론트엔드·스키마 파일 변경 `0건` | **PASS** |

---

### 1.2 기존 요구사항 (`AC-1` ~ `AC-48`) 회귀 검증 요약 (`v2.8` 적용 후 전 항목 PASS 유지)

| 검증 코드 | 검증 항목 요약 | `v2.8` (`e4f2eca`) 적용 후 회귀 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-1 ~ AC-18** | 유니버스(`1,463~1,464종목`), EMA·순수기관 수식, 5중 배치 Cron, 멱등성 가드, 유동성 제외 필터, 9열 엑셀 | `test_screener_verification.py`(8/8), `test_v2_acceptance.py`(9/9), `--mode verify` 오차 `0건` | **PASS** |
| **AC-19 ~ AC-23** | 차트 5년(`1,234일`) · 수급 3년(`740일`) 비대칭 적재, 앵커 EMA, 양보 구간, 무지연 PK 조회 | `test_v23_acceptance.py`(19/19) 전 항목 정상 통과 (함수 블록 순서 및 금지 토큰 규칙 보존) | **PASS** |
| **AC-24 ~ AC-29** | 3페이지 분리, 추천/비추천 분류, 영구제외 즉시 반영, 스마트 병합, 보유/청산(`A안`), 텔레그램 폴백 | `test_v24_watchlist_holdings.py`(29/29) 통과, 운영 DB(`관심 55 · 보유 1 · 제외 0`) 읽기 전용 무손상 보존 | **PASS** |
| **AC-30 ~ AC-38** | 무미래참조 패턴·캔들·4축 100점 평가, 2단 프로 차트, 크게 보기·PNG 저장, 와이드 뷰포트 | `test_v25_pattern_chart.py`(17/17) 전 항목 통과 | **PASS** |
| **AC-39 ~ AC-43** | 1일 2회 배치(`16:05`/`20:30`), `역배열 추세돌파` 승격, 관심종목 매도권고 오탐 제거, 3페이지 초슬림 리스트 | `test_v26_acceptance.py`(11/11) 통과 및 `20:30 final` 슬롯 덮어쓰기 호환 확인 | **PASS** |
| **AC-44 ~ AC-48** | 상단 1줄 통합(`40px`), 4단계 실시간 시세 엔진·로컬 브릿지, 거래량 전일비(%), 실시간 봉·비개장일 가드 | `test_v27_acceptance.py`(18/18) 통과 및 프론트엔드·브릿지 파일 무변경 보존 | **PASS** |

---

## 2. 버그 및 수정 요청 트래커 (Issue & Fix Tracker)

### 🚨 2.1 `[프로그램 개발 및 수정]` 대화창 신규 수정 요청 사항

* **현재 미해결 버그 없음 (`0건`) — `AC-1 ~ AC-53` 전 항목 최종 합격(`ALL PASS`).**

---

### ✅ 2.2 해결 완료된 이슈 히스토리 아카이브

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
