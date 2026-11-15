# 🧪 LS 수급·차트 스크리너 검증 및 테스트 리포트 (`TEST_REPORT.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[검증 및 테스트]` 전담 대화창**에서 테스트 실행 결과, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md) 대조 검수, 데이터 정합성 검증 리포트, 발견된 버그 및 구체적인 코드 수정 제안을 기록하는 문서입니다.
> * **`[프로그램 개발 및 수정(메인)]` 대화창**은 작업 시작 전 본 `TEST_REPORT.md`와 `STRATEGY.md`를 확인하여 미해결 버그(`2.1절 신규 수정 요청 사항`)를 코드에 반영하고, 수정이 완료된 항목의 상태를 **`[해결 완료]`**로 업데이트합니다.

---

## 1. 최신 검수 요약 (`v2.3.1` 커밋 `353f92a` & 확장 백필 `Run #43685346608` 최종 실데이터 검수 완료 — `AC-1` ~ `AC-23` 전 항목 PASS)

* **검수 일시**: `2026-11-15 19:10 KST` (`2026-11-15 10:10 UTC`)
* **대상 커밋 및 GitHub Actions 실행 이력**:
  * **코드 커밋**: `353f92a` — `feat(v2.3.1): chart 5y/supply 3y asymmetric expansion, halted-stock unsettled fix, token refresh, chart_start/supply_start params` (`STRATEGY.md` `6절` 반영, 전략 커밋 `f4aa044` / 현재 `HEAD` `c7633ea`)
  * **사전 프로브 실행 (`probe_10y`)**: [`Run #43682739754`](https://github.com/minseok2995-ai/ls-stock-screener/actions/runs/43682739754) (`2026-11-15 14:49:48 ~ 14:50:15 KST`, `27초`, `success`) — 대표 대형주 3종(`005930`, `000660`, `005380`) `2016-01-04` 일봉·수급 실존 및 합산 수식 오차 `0건` 확인
  * **비대칭 확장 백필 완주 (`backfill_10y`)**: [`Run #43685346608`](https://github.com/minseok2995-ai/ls-stock-screener/actions/runs/43685346608) (`2026-11-15 15:25:11 ~ 18:09:41 KST`, **`2시간 44분 30초` 1회차 단판 완주**, `success`) — 유니버스 `1,463종목` 전수(`기완주 스킵 71종목` + `확장 처리 1,392종목`, 종목 에러 `0건`) 완료
* **단위·수용 회귀 테스트 실행 결과**:
  * `python3 test_screener_verification.py`: **8 / 8 통과 (`OK`)**
  * `python3 -m unittest discover -s tests -v`: **28 / 28 통과 (`OK`, `0.476s` — [`tests/test_v23_acceptance.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/tests/test_v23_acceptance.py) `19개` + [`tests/test_v2_acceptance.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/tests/test_v2_acceptance.py) `9개`)**
* **운영 Supabase 대용량 DB(합산 `271.8만 행`, `2026-11-13` 확정 상태) 전수 실데이터 검증**:
  * `python3 run_daily_screener.py --mode verify`: **전 항목 정상 통과 (`Exit 0`, `HTTP 500` 타임아웃 `0건`)**
  * `1,463개` 유니버스 전 종목 `count=exact` 정밀 전수 합산 결과:
    * **`daily_chart`**: 정확히 **`1,678,171행`** (`pg_class` 추정치 약 `1,560,693행`, 상장 5년 이상 `1,254종목` `2021-11-01 ~ 2026-11-13` **`1,233영업일`** + 2021-11 이후 신규 상장 `209종목` 상장일 전 기간 적재)
    * **`daily_investor_supply`**: 정확히 **`1,040,512행`** (`pg_class` 추정치 약 `1,039,832행`, 상장 3년 이상 `1,335종목` `2023-11-01 ~ 2026-11-13` **`739영업일`** [`Backward Delta` `238영업일` 무결점 결합] + 2023-11 이후 상장·이전상장 `128종목` 전 기간 적재)
    * 전 종목 조회 오류(`error=True`) **`0건`**, 장중 미확정 오판(`is_latest_supply_unsettled=True`) **`0건`** (거래정지 `volume=0` `25종목` 포함 100% 정상 처리).
* **확장 DB(`271.8만 행`) 성능 및 `index.html` 3자 교차 검증 (`기준일 T = 2026-11-13`)**:
  * 대표 10종목 기준일(`TOP_TRADE_DATE`) PK 조회 **`0.248 ~ 0.279초` (`< 0.30초`)**, `--mode daily --skip-if-completed` **`1.97 ~ 1.99초` (`< 5.0초`)** 즉시 종료(`Exit 0`), `index.html` 1,463종목 라이브 초기 로드 **`5.40초` (`5,397ms`, 콘솔 에러/경고 `0건`)**.
  * 5개 전 스크리닝 모드(`123 / 81 / 47 / 43 / 4종목`)에서 **`index.html` === `run_daily_screener.py` === 독립 클린룸 파이썬 100% 일치(오차 `0건`)** 및 5개 `.xlsx` 내보내기(`298행 × 9열 = 2,682셀`) 불량 셀 **`0건`** 확인 완료.
  * ✅ **결론**: `STRATEGY.md` `6.7절(AC-19 ~ AC-23)` 및 기존 `AC-1 ~ AC-18` 전 항목 최종 **PASS**. `STRATEGY.md` `7절`(`v2.4` 3페이지 관심·보유·제외 시스템) 구현 및 배포에 즉시 착수 가능합니다.

---

### 1.1 `v2.3.1` 차트 5년·수급 3년 비대칭 확장 백필 (`STRATEGY.md` 6.7절 — `AC-19` ~ `AC-23`) 상세 검수 결과표

| 검증 코드 | 검증 항목 (`STRATEGY.md` 6.7절) | 코드·워크플로우 및 `Run #43685346608` 완주 후 운영 DB(`271.8만 행`) 실증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-19** | **`probe_10y` 실서버 검증 보존 및 단일 페이지 하한 탐색(`20160131`) 정합성 검증** | • [`Run #43682739754`](https://github.com/minseok2995-ai/ls-stock-screener/actions/runs/43682739754) 실측: `삼성전자(005930)`·`SK하이닉스(000660)`·`현대차(005380)` 3종 모두 `t8410` 최초일 `2016-01-04`(`38건`) 및 `t1717` 최초일 `2016-01-04`(`38건`, `itc/pef/pen/frg/fn_inv` 전일 비영`!=0`, 순수기관 합산 오차 `0건`, `verdict=OK`) 실증 완료<br/>• [`find_supply_floor_for_stock()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1528-L1557)의 첫 탐색 윈도우를 `20160101~20160131`(단일 페이지 20영업일 이내)로 좁힌 패치가 [`Run #43685346608`](https://github.com/minseok2995-ai/ls-stock-screener/actions/runs/43685346608) 시작 시 실제 작동하여 `effective_supply_floor=2016-01-04 | effective_supply_target=2023-11-01`로 정확히 감지됨 (`test_ac19_floor_first_window_is_20160131` 외 단위 테스트 통과) | **PASS** |
| **AC-20** | **차트 5년치(`2021-11-01 ~ 현재`) 수집 · 앵커 EMA 연속성 · 액면분할 자동 재구축 검증** | • 상장 5년 이상 `1,254종목` 전수 `chart_oldest = 2021-11-01`, `chart_latest = 2026-11-13`(`1,233영업일`) 적재 및 2021-11 이후 상장 `209종목` 상장일 전 기간 적재 확인 (`1,254 + 209 = 1,463종목` 100%)<br/>• 대표 12종목(`005930, 000660, 005380, 012450, 196170, 006650, 023160, 034020, 166090, 098460, 437730, 448900`)의 `daily_chart` 전 구간 **`13,753행`(`68,765개` EMA 셀)** 전수 대조 결과: `NULL`/`0` 값 **`0건`**, 클린룸 `compute_ema_series` 재산출 대비 최대 절대 오차 **`0.00원` (`max_abs_diff = 0.0`)**<br/>• 실DB [`supabase_get_anchor_row()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1386-L1409)(`anchor_date = 2026-11-06`, `offset=5`) 시드 기반 [`build_anchor_seeded_charts()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1412-L1432) 이어 계산 결과 5년 전체 시계열 EMA와 최대 차이 **`0.01원` (`0.00%` 수준, 소수 둘째 자리 반올림 시드 한계 내 일치)** 확인 및 종가 불일치(`mismatch`) 시 `count=TARGET_10Y_CHART_COUNT(3000)` 전체 재수집 트리거 검증 완료 | **PASS** |
| **AC-21** | **수급 3년치(`2023-11-01 ~ 현재`) `Backward Delta` 이어붙이기 및 무코드 재확장 파라미터 검증** | • 기존 2년치(`2024-10-24 ~ 2026-11-13`, `501일`) 수급을 재호출하지 않고 `2023-11-01 ~ 2024-10-23`(`238영업일`) 과거 차분만 역방향 수집하여 상장 3년 이상 `1,335종목` 모두 **`739영업일`(`2023-11-01 ~ 2026-11-13`)** 연속 적재 완료<br/>• 대표 12종목 `daily_investor_supply` **`8,772행`** 전수 감사 결과: **`2024-10-23 ↔ 2024-10-24` 경계선 단절·중복 `0건`**, 순수기관 6대 주체 합산(`금융투자` 제외) 수식 오차 **`0건`**, 과거 확장 구간(`2023-11 ~ 2024-10`)의 [`supabase_get_chart_vol_close()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1435-L1458) 연동 `inst_vol_ratio` 오차 **`0건`** *(참고: 코넥스→코스닥 이전상장주 `한국피아이엠 448900`의 `2024-10-23` 1일은 당시 거래량 `0주`로 장중 더미 가드에 의해 제외되었으며 실거래일 누락은 `0건`)*<br/>• `--chart-start 2016-01-01 --supply-start 2016-01-01` 전달 시 코드 수정 없이 `needs_chart_fetch("2021-11-01", "2016-01-01") == True` 및 `plan_supply_fetch(...) == ("backward", "2016-01-04", "2023-10-31")`가 즉시 작동함을 검증 (`test_ac21_future_expansion_plan_2016`) | **PASS** |
| **AC-22** | **평일 `daily` 배치 속도 보호(`비대칭 행 수 호환`) 및 자동 체이닝·양보 가드·토큰 갱신 검증** | • **평일 `daily` 고속 증분 호환성 전수 실증**: `1,463종목` 중 상장 3개월 초과 **`1,452종목`(`99.25%`)** — 비대칭 적재 종목(`차트 1,233일 / 수급 739일` → `chart_cnt >= 400 and supply_cnt >= 400`), 2024~2026년 신규 상장주(`abs(c-s) <= 5`), 거래정지 `25종목`(`resolve_supply_unsettled == False`) 전원 — 이 [`is_stock_already_backfilled()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1224-L1252) `True`(`max_pages=1` 고속 증분)로 판정됨. 나머지 `11종목`(`0.75%`)은 최근 3개월 이내 초신규 상장주(`2~60영업일`, 예: `넥스아이 493410` `2일`)로 자연스럽게 1페이지 내 즉시 수집 종료됨<br/>• [`.github/workflows/daily_batch.yml`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/.github/workflows/daily_batch.yml) 내 `chart_start` / `supply_start` 입력·체이닝 전달, `permissions: actions: write`, 평일 `20:10~21:20 KST` 양보 가드([`is_in_daily_yield_window()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1320-L1326)), `80분` 주기 OAuth 토큰 선제 재발급 및 `IGW00121` 즉시 재발급 로직([`LSApiClient`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L305-L363)) 정합성 확인 완료 (`Run #43685346608` `164분` 연속 실행 중 토큰 만료 에러 `0건` 실증!) | **PASS** |
| **AC-23** | **확장 완료 후 실데이터 정합성 · 영구 누적 정책 · 웹 대시보드(`index.html`) 무지연 검증** | • **영구 누적(No Rolling Delete) 검증**: 코드베이스 전수 검사 결과 과거 거래일 삭제(`DELETE`) 쿼리 **`0건`** 확인 (유일한 `DELETE`는 [`supabase_cleanup_unsettled_supply()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L774-L812)의 당일 `trade_date=eq.{t_date}` 장중 전 주체 `0` 더미 행 정리용 1곳뿐)<br/>• `--mode verify` 대표 7종목 모두 `일봉: 1,233일 (2021-11-01 ~ 2026-11-13) | 수급: 739일 (2023-11-01 ~ 2026-11-13)` 정확 출력<br/>• `271.8만 행` DB 상태에서 `index.html` 라이브 구동 **`5.40초`**, `HTTP 500` 타임아웃 **`0건`**, 기존 **`AC-1 ~ AC-18` 회귀 오차 `0건`** | **PASS** |

---

### 1.2 `1,463개` 유니버스 전 종목 DB 적재 분포 및 대용량 성능 실측 요약 (`기준일: 2026-11-13`)

| 점검 구분 | 세부 측정 항목 | 실측 수치 (`2026-11-15` 기준) | 비고 |
| :--- | :--- | :---: | :--- |
| **시계열 적재 규모** | `daily_chart` 유니버스 전수 행 합계 | **`1,678,171행`** | 상장 5년+ `1,254종목`(`2021-11-01~`, `1,233일`) + 2021-11 이후 상장 `209종목` |
| **시계열 적재 규모** | `daily_investor_supply` 유니버스 전수 행 합계 | **`1,040,512행`** | 상장 3년+ `1,335종목`(`2023-11-01~`, `739일`) + 2023-11 이후 상장·이전 `128종목` |
| **결측·미확정 점검** | 조회 에러(`error=True`) / 미확정 수급 오판 종목 수 | **`0종목` / `0종목`** | 거래정지(`volume=0`) `25종목` 전원 `is_latest_supply_unsettled=False` 정상 판정 |
| **대용량 쿼리 응답** | 대표 10종목 최신 확정일(`TOP_TRADE_DATE`) 조회 | **`0.248 ~ 0.279초`** | 목표 `< 0.30초` 충족 (73만 행 → 272만 행 3.7배 확장 후에도 무지연) |
| **배치 멱등성 속도** | `--mode daily --skip-if-completed` 실행 시간 | **`1.97 ~ 1.99초`** | 목표 `< 5.0초` 충족 (`완주율 99.52% >= 98.5%`, 중복 수집·중복 알림 `0건`) |
| **웹 대시보드 성능** | `index.html` `connectSupabaseLive()` 전체 동기화 | **`5.40초` (`5,397ms`)** | 콘솔 에러/경고 `0건`, 배지 `기준일: 2026-11-13` 정상 표시 |

---

### 1.3 기존 요구사항 (`AC-1` ~ `AC-18`) 회귀 검증 요약 (`2026-11-13` 확정 · `271.8만 행` DB 기준 전 항목 PASS)

| 검증 코드 | 검증 항목 요약 | `2026-11-13` 운영 DB 및 3자 교차 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-1 ~ AC-5** | 시총 ≥ 700억 보통주 유니버스(`1,463종목`), EMA 5종 & 순수기관 수식 | 부적격 혼입 `0건`, 20억 미만 중소형주 `909종목` 포함, EMA·순수기관 수식 오차 `0건`, `태광(023160)` `2026-08-25`(`+12.85%`) & `대한유화(006650)` `2026-11-03`(`+31.57%`) 정상 보존 | **PASS** |
| **AC-6 ~ AC-12** | 대시보드 전 종목 무절단 로드, 컨트롤 바, 7열 테이블, 장중 `T+1` 차단 | 5개 전 조건(`당일10%=123` / `당일15%=81` / `당일20%=47` / `3일연속5%=43` / `하락추세전환=4` [`448900, 000320, 437730, 098460`]) `index.html` === `run_daily_screener.py` === 클린룸 파이썬 **100% 일치** | **PASS** |
| **AC-13 ~ AC-15** | `20:30 KST` 3중 Cron, `--skip-if-completed` 멱등성 가드, 분산 표본 기준일 | 3중 Cron(`11:30 / 11:47 / 12:17 UTC`) 유지, 완주 상태 스킵 `< 2.0초` 종료, 대표 10종목 PK 조회 `< 0.28초` 정상 유지 | **PASS** |
| **AC-16 ~ AC-18** | `1억 / 3만주 / 5억` 유동성 제외 필터(당일 vs 3일 평균) & 9열 엑셀 저장 | 당일 저유동성 `36종목`(`조흥 002600`, `푸른저축은행 007330`, `롯데웰푸드 280360` 등) 정확 제외 및 3일 평균 충족 종목(`대양전기공업 108380`, `롯데웰푸드 280360`) 정확 포함; 생성된 5개 `.xlsx`(`2,682셀`) 불량 셀 `0건` 및 `이동평균 추세 현황` 문자열 오차 `0건` | **PASS** |

---

## 2. 버그 및 수정 요청 트래커 (Issue & Fix Tracker)

### 🚨 2.1 `[프로그램 개발 및 수정]` 대화창 필수 수정 요청 사항 (`v2.3.1` 기준 미해결 차단 버그 0건)

* **`v2.3.1`(`AC-1 ~ AC-23`) 범위 내 미해결 차단 버그는 없습니다 (`전 항목 PASS`).**

> **📌 `[프로그램 개발 및 수정]` 창 `v2.4`(`STRATEGY.md` 7절) 구현 착수 시 참고할 실측 트레이스 (`STRATEGY.md` `7.5절 4항` 이미 반영됨)**:
> * **[텔레그램 Markdown 언더바(`_`) `HTTP 400` 폴백 — `STRATEGY.md` 828행 명세 연결]**: [`Run #43685346608`](https://github.com/minseok2995-ai/ls-stock-screener/actions/runs/43685346608) 종료 직전(`09:09:18Z`), [`run_backfill_10y()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1775-L1780)가 완주 알림 문자열(`... daily_chart 약 1,560,693행 | daily_investor_supply 약 1,039,832행 ...`)을 [`send_telegram_alert()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1291-L1308)(`"parse_mode": "Markdown"`)로 전송할 때 이스케이프되지 않은 홀수 개(`3개`)의 `_`로 인해 `HTTP Error 400: Bad Request` 경고가 기록되었습니다(비치명적 예외 처리 덕분에 배치 및 후속 `verify` 스텝은 정상 `Exit 0` 성공). `[전략 개발]` 창에서 이미 [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L828) `7.5절 4항`(커밋 `c7633ea`)에 `HTTPError(400)` 시 `"parse_mode"` 제거 Plain Text 자동 재전송 폴백 요건을 반영해 두었으므로, 이어지는 `v2.4` 개발 시 [`send_telegram_alert()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L1291-L1308)에 함께 반영해 주시면 됩니다.
> * **[초경계 상장일 12종목 + 이전상장 1종목 참고 메모 (비차단)]**: `2024-10-21 ~ 2024-11-14` 사이에 실제 신규 상장된 `12종목`(`클로봇 466100`, `더본코리아 475560`, `씨메스로보틱스 475400` 등) 및 코넥스→코스닥 이전상장주 `우양에이치씨(101970)`는 이미 상장일 전 기간 데이터가 DB에 100% 적재되어 있어 실사용 및 평일 `daily` 배치(`max_pages=1`)에는 전혀 영향이 없으며, 혹시 향후 `backfill_10y`를 동일 인자로 재실행하더라도 총 `13종목`(약 `15초` 미만)만 확인 후 즉시 종료됩니다.

---

### ✅ 2.2 해결 완료된 이슈 히스토리 아카이브

* **[v2.3.1 검증 완료 (`353f92a`, `Run #43682739754` & `Run #43685346608`)]** 차트 5년(`2021-11-01~`, `1,678,171행`) · 수급 3년(`2023-11-01~`, `1,040,512행`) 비대칭 확장 백필 1회차 `2시간 44분` 100% 완주, 앵커 시드 EMA 연속성, 거래정지 `25종목` 미확정 오판 차단, `80분` 주기 토큰 자동 갱신 및 `271.8만 행` 대용량 DB 무지연(`AC-19 ~ AC-23`) 전 항목 합격.
* **[v2.2 검증 완료 (`6bfbbd5`)]** `[기관 수급 발생 종목]` 유동성·수급금액 제외 필터(`당일 기준` vs `3일 연속 3일 평균 기준`) 및 `[엑셀 저장]` 9개 컬럼 개편(`AC-16 ~ AC-18`) 전 항목 합격.
* **[v2.1 검증 완료 (`1aecd41`)]** `20:30 KST` 다중 백업 Cron, `KST` 표준시 고정, `--skip-if-completed` 멱등성 가드(`< 2.3초` 종료), `if: failure()` 장애 알림, Apps Script 외부 정각 웹훅(`AC-13 ~ AC-15`) 및 `두산에너빌리티(034020)` 백필 자동 복구 확인 완료.
* **[ISSUE-006 ~ ISSUE-010] `[해결 완료 (v1.4.3 ~ v2.0)]`** `PRIORITY_SHCODES` 제거, `has_2yr_history` 판정 분리, 장중 미확정 수급 차단, 복합 PK 병렬 조회 전환(`HTTP 500` 해소), `AC-1 ~ AC-12` 검증 체계 구축 완료.
* **[ISSUE-001 ~ ISSUE-005] `[해결 완료 (v1.4)]`** 1,463종목 시총 ≥ 700억 전수 유니버스 구축, 일봉·수급 500영업일 역순 슬라이딩 적재, Actions 360분 타임아웃 상향 완료.
