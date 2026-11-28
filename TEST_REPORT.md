# 🧪 LS 수급·차트 스크리너 검증 및 테스트 리포트 (`TEST_REPORT.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[검증 및 테스트]` 전담 대화창**에서 테스트 실행 결과, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md) 대조 검수, 데이터 정합성 검증 리포트, 발견된 버그 및 구체적인 코드 수정 제안을 기록하는 문서입니다.
> * **`[프로그램 개발 및 수정(메인)]` 대화창**은 작업 시작 전 본 `TEST_REPORT.md`와 `STRATEGY.md`를 확인하여 미해결 버그(`2.1절 신규 수정 요청 사항`)를 코드에 반영하고, 수정이 완료된 항목의 상태를 **`[해결 완료]`**로 업데이트합니다.

---

## 1. 최신 검수 요약 (`v3.1` 1일 2회 정기 배치 무결점 정상화 커밋 `775a007` 최종 검수 — **`AC-67 ~ AC-71` 및 `AC-1 ~ AC-66` 전 항목 합격, 신규 결함 `0건`**)

* **검수 일시**: `2026-11-28 11:15 KST` (`2026-11-28 02:15 UTC`) — 차주 첫 평일 배치(`2026-11-30(월) 16:05 KST`) 및 `12월` 분기 정기 재산출(`2026-12-01(화)`) **이전 사전 검수 완료**
* **대상 커밋**: `775a007` (`feat(v3.1): 비허용 시간대 무음 차단 · 분기 유니버스 완주율 복원 · t1463 409 및 신규상장 백필 해소 · 백업 크론 슬림화 (AC-67 ~ AC-71)`, 전략 기준 커밋 `6b374ca`)
* **범위 및 무변경 원칙 준수 (`AC-71`)**: `git diff --name-status 6b374ca..775a007` 대조 결과 허용된 7개 파일([`run_daily_screener.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py), [`.github/workflows/daily_batch.yml`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/.github/workflows/daily_batch.yml), [`README.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/README.md), 크론 배열 단언만 동기화된 [`tests/test_v2_acceptance.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/tests/test_v2_acceptance.py) · [`tests/test_v23_acceptance.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/tests/test_v23_acceptance.py) · [`tests/test_v26_acceptance.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/tests/test_v26_acceptance.py), 신규 [`tests/test_v31_batch_schedule.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/tests/test_v31_batch_schedule.py))만 변경되었으며, 프론트엔드([`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html) · [`watchlist.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/watchlist.html) · [`holdings.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/holdings.html) · [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js)), DB 스키마([`supabase_schema.sql`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/supabase_schema.sql) · `scripts/*.sql`), [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md) **무변경(`0 line diff`)** 확인.
* **단위·통합 테스트 스위트 실행 결과 (`총 171 / 171 통과 — ALL PASS`)**:
  * `python3 test_screener_verification.py`: **8 / 8 통과 (`OK`, `0.029s`)**
  * `python3 -m unittest discover -s tests -v`: **163 / 163 통과 (`OK`, `7.630s`)** — 기존 10개 모듈 `149개` 테스트 조건 완화·삭제 `0건` + 신규 `test_v31_batch_schedule.py` `14개` 전부 통과
  * `python3 run_daily_screener.py --mode verify`: **Exit 0** (`stocks_master` 유니버스 `1,466종목`, 일봉 약 `1,764,385건`, 수급 약 `1,055,744건`, 수식 오차·비보통주 혼입 `0건`, 운영 DB `관심 46 · 보유 1 · 제외 0 · DSA(11/27) 206` 무손상 보존)
* **독립 심층 엣지케이스 및 운영 실DB(`1,466종목` 100% 읽기 전용 — 비-GET 요청 하드 차단 후 검수 전·후 행 수 완전 일치 재확인) 검증 결과**:
  * ✅ **AC-67 (비정상 시간대 무음 차단 · 장전 빈 일봉 방어 · `0종목` 발송 금지) 통과**:
    * 1주일 전체 **`10,080분`(`월 00:00 ~ 일 23:59 KST`) 전수 스캔** 결과 [`is_allowed_auto_batch_window`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1202-L1222)가 평일 `15:45~18:59 KST`(`975분`, 수능일 `17:05` 포함) 및 `20:05~23:59 KST`(`1,175분`)에서만 `True`를 반환하고 나머지 `7,930분`(평일 `00:00~15:44`, 야간장 데드존 `19:00~20:04`, 주말 전 시간대)을 오차 없이 차단했으며, 허용된 `2,150분` 전 구간에서 `resolve_batch_slot("auto")` 슬롯(`prelim`/`final`) 불일치 **`0건`**.
    * 실제 비허용 시간대(토요일 오전 KST)에서 모킹 없는 **실제 CLI 서브프로세스**(`python3 run_daily_screener.py --mode daily --batch-slot auto --skip-if-completed`, 잘못된 DB URL·더미 API 키 주입) 실행 시 네트워크 호출 **`0회`**, **`264.9ms` 내 `Exit 0`**, `[SKIP-OFFHOURS]` 로그 및 `GITHUB_OUTPUT`(`skipped_completed=true` → 워크플로우 후속 `verify` 스텝까지 자동 스킵) 기록 확인. 수동 강제 실행(`skip_if_completed=False`)은 새벽·주말에도 정상 동작.
    * [`fetch_latest_krx_trading_date`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L791-L851)에서 정수 `0`뿐 아니라 LS 문자열 `"0"`으로 반환된 장전 빈 일봉(`jdiff_vol<=0 and open<=0`), `15:30 KST` 이전 당일 미마감 봉 제외, `005930` 빈 봉 시 `000660` 폴백, 최소 픽스처(`{"date": "20261112"}`) 하위 호환 확인. `universe_count == 0` 공회전 시 `[ZERO-UNIVERSE]` 경고 후 텔레그램·DSA 호출 **`0회`** 확인.
  * ✅ **AC-68 (기존 분기 유니버스 시총 `700억` 일시 하회 적재 유지 · 분기 재산출 탈락 동기화) 통과**:
    * 운영 실DB 감사 결과 `2026-11-27` 기준 미적재 `33종목`(`화천기공 000850`, `컴투스홀딩스 063080`, `비투엔 307870`, `대창 012800`, `이에스티 495910` 등 — 분기 중 시총 `700억` 하회 시점부터 적재가 중단되어 완주율이 `97.68%~97.75% < 98.5%`에 고착)을 정확히 확인.
    * 운영 실DB `1,466종목` + 실전 프리페치(`8.03초`, 앵커 `1,463` · 폴백 `84`) 기반 `2026-11-30(월)` 드라이런에서 위 `33종목` 전부의 당일 시총을 `~600억 (< 700억)`으로 강제 하락시켰음에도 [`run_standalone_batch`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L3069-L3084)가 **`33 / 33종목` 전수 정상 적재**(`is_universe=True` 유지, 최신 시총·종가 갱신)하여 시뮬레이션 완주율이 **`100.00%` (`>= 98.5%`)** 로 즉시 복원됨을 실증 (`t1463` 신규 `700억` 미만 후보는 기존대로 차단).
    * 전수 분기 재산출(`rebuild_due=True`) 시 탈락 구 유니버스 종목이 `DELETE` 없이 `is_universe=False`로 일괄 Upsert(배치 내 전 행 10개 키 완전 일치로 `PGRST102` 방지)되고, [`is_quarterly_rebuild_due`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L446-L455)가 PostgREST UTC(`+00:00`) 타임스탬프를 KST 연-월(`YYYY-MM`)로 정확히 변환하며, 분기 재산출 시에도 `supabase_prefetch_daily_context`가 정상 가동됨을 확인.
  * ✅ **AC-69 (`t1463` 신규 급등주 `HTTP 409` 제로화 · 상장 `65영업일 이하` 신규 상장주 백필 판정) 통과**:
    * 미등록 `t1463` 신규 급등주(`471800` 등)가 루프 시작 전 시드 마스터(`updated_at="1970-01-01T00:00:00+09:00"`)로 선등록되어 외래키(`23503`) `HTTP 409` 없이 적재되며, 만약 차트 종가 기준 재계산 시총이 `700억` 미만으로 내려가면 시드 행을 즉시 `is_universe=False`로 롤백함까지 확인. [`BatchUpsertBuffer.flush()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L2162-L2176) 역시 정상 경로의 `daily_chart → daily_investor_supply → stocks_master` 3-POST 계약을 보존하면서 단건 `HTTP 409` 발생 시 시드 선등록 후 자가 복구하며, 비-409 예외는 기존대로 격리함.
    * 운영 실DB 내 `< 400영업일` 유니버스 `53종목` 전수 대조 결과, 기존 `v3.0.1`에서 매회 전체 백필을 유발하던 상장 `65영업일 이하` 신규 상장주 **`11종목` 전수**(`멜콘 32d`, `덕산넵코어스 41d`, `영광와이케이엠씨 10d`, `영광 12d/11d`, `스카이랩스 57d`, `니어스랩 55d`, `인텔리빅스 21d`, `브릴스 40d`, `글로벌테크놀로지 42d`, `넥스아이 12d`, `이에스티 8d`)가 [`is_stock_already_backfilled`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1630-L1660)에서 `False → True`로 전환되어 **기존 유니버스 내 불필요 `2년백필` 대상이 `11종목 → 0종목`으로 완전 제거**됨을 확인 (`60일/25일`, `55일/35일` 구 절단 데이터 `False` 유지 및 초신규 무앵커 종목 `count=60` 1페이지 조회 확인).
  * ✅ **AC-70 (`daily_batch.yml` 2중 백업 크론 슬림화 · 극소량 거래 종목 완료 인정) 통과**:
    * [`.github/workflows/daily_batch.yml`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/.github/workflows/daily_batch.yml#L5-L9)의 `schedule`이 `['25 7 * * 1-5', '47 11 * * 1-5']`(`16:25 KST` · `20:47 KST`) 2개로 정비되었고 `concurrency` 직렬화 및 `if: failure()` 장애 알림이 그대로 유지됨.
    * 운영 실DB `2026-11-27` 기준 극소량 거래 종목(`조흥 002600`: `volume=4`, 전 주체 순매수 `0`, 일봉·수급 행 모두 존재)이 [`check_daily_batch_completion`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1315-L1327) 완료 집합에 즉시 편입(`1,432 → 1,433`)됨을 확인했고, `rep_3_settled=False`(장중) 또는 `volume > 100`(`101주`) 또는 수급 행 미존재 시에는 엄격히 제외됨을 확인.
    * ℹ️ **운영 참고(무결함)**: 당일(`t_date == today_str`) 수집 시점에는 `_parse_t1717_rows`([L1038](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1038))의 장중 미확정 방어 규칙에 따라 전 주체 `0`인 당일 수급 행 적재가 보류되었다가 익일 배치 슬라이딩 윈도우에서 자동 채워집니다. 당일 기준 극소량 전 주체 `0` 종목은 `1,466종목` 중 `0~1종목`(`조흥 002600`, `0.07%`)뿐이므로 당일 백업 크론 완주율은 `99.93% (1,465/1,466 >= 98.5%)`로 `--skip-if-completed` 가드가 100% 정상 작동하며, 공휴일/과거일 점검 시에는 기적재된 `002600`까지 `100.00%` 완료로 인정됩니다.

---

### 1.1 `v3.1` 요구사항 (`AC-67` ~ `AC-71`) 검수 결과표

| 검증 코드 | 검증 항목 (`STRATEGY.md` 17.5절) | `v3.1` (`775a007`) 검수 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-67** | **비정상 시간대 자동 실행 즉시 무음 스킵 · 장전 빈 일봉 차단 · `0종목` 발송 금지** | • 주간 `10,080분` 전수 스캔 경계·슬롯 일치 오차 `0`, 실전 CLI 오프아워 `264.9ms` Exit 0 (`API/DB/TG 0회`, `skipped_completed=true`)<br>• 장전 빈 일봉(`0`/`"0"`)·`15:30` 이전 당일봉 제외, `universe_count==0` 발송·DSA 생략 확인 | **PASS** |
| **AC-68** | **기존 분기 유니버스 시총 `700억` 일시 하회 정상 적재 · 완주율 복원 · 분기 탈락 동기화** | • 운영 실DB 미적재 `33종목`(`<700억`) 드라이런 전수 적재 확인 → 완주율 `97.75%` → **`100.00%`** 복원 (`t1463 <700억` 차단 유지)<br>• 분기 재산출 시 `DELETE` 없이 `is_universe=False` Upsert(키 일치), KST 월 변환 및 프리페치(`8.03초`) 확인 | **PASS** |
| **AC-69** | **`t1463` 신규 급등주 `HTTP 409` 제로화 및 상장 `65영업일 이하` 신규 상장주 백필 판정** | • 루프 전 시드 선등록(`1970-01-01`) + 시총 미달 롤백 + `BatchUpsertBuffer` 409 자가 복구 및 3-POST 순서 보존<br>• 운영 실DB 신규 상장주 `11종목`(`8~57일`) 전수 `True` 전환(`needs_full_2yr: 11 → 0`), `60/25` 절단 `False` 유지, 초신규 1페이지 조회 | **PASS** |
| **AC-70** | **`daily_batch.yml` 2중 백업 크론(`16:25` · `20:47 KST`) 슬림화 및 극소량 종목 완료 인정** | • `schedule` 크론 `['25 7 * * 1-5', '47 11 * * 1-5']` 2개 정비 완료<br>• 대표주 3종 확정 시 `조흥(002600, vol=4)` 완료 인정 및 장중/`vol>100`/수급 미존재 차단 확인 | **PASS** |
| **AC-71** | **전체 회귀 테스트(`AC-1 ~ AC-66`) + `v3.1` 신규 테스트 100% PASS 및 범위 준수** | • 전체 **`171 / 171`** (`8 + 163`) PASS, 프론트엔드 4종·SQL 스키마·`STRATEGY.md` 무변경 확인 | **PASS** |

---

### 1.2 기존 요구사항 (`AC-1` ~ `AC-66`) 회귀 검증 요약 (`v3.1` 적용 후)

| 검증 코드 | 검증 항목 요약 | `v3.1` (`775a007`) 적용 후 회귀 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-1 ~ AC-18** | 유니버스, EMA·순수기관 수식, 배치 Cron, 멱등성 가드, 엑셀 | `test_screener_verification.py`(8/8), `test_v2_acceptance.py`(9/9), `--mode verify` Exit 0 | **PASS** |
| **AC-19 ~ AC-23** | 차트 5년·수급 3년 적재, 앵커 EMA, 무지연 PK 조회 | `test_v23_acceptance.py`(19/19) | **PASS** |
| **AC-24 ~ AC-29** | 3페이지 분리, 추천/비추천, 영구제외, 스마트 병합, 보유/청산 | `test_v24_watchlist_holdings.py`(29/29), 운영 DB(`관심 46 · 보유 1 · 제외 0`) 무손상 | **PASS** |
| **AC-30 ~ AC-48** | 패턴·4축 평가, 프로 차트, 2회 배치, 실시간 시세 | `test_v25`(17/17) · `test_v26`(11/11) · `test_v27`(18/18) | **PASS** |
| **AC-49 ~ AC-56** | Keep-Alive, 프리페치, 정속 페이서, 50종목 묶음 Upsert | `test_v28_batch_perf.py`(21/21), 3-POST 순서 계약 및 비-409 단건 격리 유지 | **PASS** |
| **AC-57 ~ AC-60** | 일일 수급 분석·Gemini Top N·사후 복기 | `test_v29_daily_analysis.py`(10/10) | **PASS** |
| **AC-61 ~ AC-66** | 양극 추세 사이클(16단계·63세부현황), 750봉 패리티, 스냅샷 격리 | `test_v30_trend_cycle.py`(6/6) · `test_v301_fixes.py`(9/9), 프론트·추세 스키마 무변경 | **PASS** |

---

## 2. 버그 및 수정 요청 트래커 (Issue & Fix Tracker)

### 🚨 2.1 `[프로그램 개발 및 수정]` 대화창 신규 수정 요청 사항

> [!NOTE]
> **현재 미해결 수정 요청 사항 없음 (`0건`).** `v3.1` (`775a007`)의 모든 요구사항(`AC-67 ~ AC-71`) 및 기존 회귀 요구사항(`AC-1 ~ AC-66`)이 전수 합격하여 `[프로그램 개발 및 수정]` 대화창에 요청할 추가 코드 수정 사항이 없습니다.
>
> **차주 실전 배치 확인 권장 포인트(선택)**:
> 1. **`2026-11-30(월) 16:05 / 16:25 KST`**: `16:05` 본 배치에서 기존 미적재 `33종목` 복구 및 `2년백필 0~소수(실제 신규 편입만)` 로그 확인 후, `16:25` 백업 크론이 `[SKIP-COMPLETED]`(완주율 `>= 99.9%`) 또는 익일 지연 시 `[SKIP-OFFHOURS]`로 무음 종료되는지 확인.
> 2. **`2026-12-01(화) 16:05 KST` (12월 분기 첫 거래일)**: `stocks_master에 시가총액 ≥ 700억 보통주 N종목 일괄 선등록 완료 (분기 탈락 하향 M종목 포함)` 및 `[PREFETCH]` 정상 가동 로그 확인.

---

### ✅ 2.2 해결 완료된 이슈 히스토리 아카이브

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
