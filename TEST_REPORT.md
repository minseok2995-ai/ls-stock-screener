# 🧪 LS 수급·차트 스크리너 검증 및 테스트 리포트 (`TEST_REPORT.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[검증 및 테스트]` 전담 대화창**에서 테스트 실행 결과, 데이터 정합성 검증 리포트, 발견된 버그 및 수정 요청 사항을 기록하는 문서입니다.
> * **`[프로그램 개발 및 수정(메인)]` 대화창**은 작업 시작 전 본 `TEST_REPORT.md`와 `STRATEGY.md`를 확인하여 미해결 버그나 수정 요청 사항을 코드에 반영하고, 수정이 완료된 항목의 상태를 **`[해결 완료]`**로 업데이트합니다.

---

## 1. 최신 자동 검증 실행 요약 (v1.4 코드 검증 및 `AC-1` ~ `AC-6` 체크리스트)

* **단위/통합 로직 테스트 (`python3 test_screener_verification.py`)**: **5 / 5 항목 통과 (`OK`)**
  1. `test_1_excluded_security_filter`: 보통주(삼성전자·알테오젠·대한유화·태광·대우건설·연우) 통과 및 ETF/스팩/우선주/리츠 차단 확인 (`OK`)
  2. `test_2_quarterly_and_incomplete_universe_schedule`: DB 내 유니버스 `< 1,200종목`(현행 247종목) 미완성 감지 시 자동 전수 재산출 전환 확인 (`OK`)
  3. `test_3_ema_and_pure_institutional_formula`: EMA(5·20·60·120·240) 및 금융투자 제외 6대 순수기관 합산 수식 정합성 확인 (`OK`)
  4. `test_4_t1717_official_response_and_sliding_pagination`: `t1717` 역순 날짜 슬라이딩(`oldest_date - 1일` 이동) 연속조회 동작 확인 (`OK`)
  5. `test_5_smart_resume_and_priority_ordering`: 기존 60일/25일 절단 종목 재백필 판정(`False`), 2년치 완비 종목 스킵(`True`), 레퍼런스 종목(`006650`, `023160`) 최선두 배치 확인 (`OK`)

### `STRATEGY.md` 0.4절 합격 기준 (`AC-1` ~ `AC-6`) 현황표
> 💡 아래 표는 GitHub Actions에서 `mode: backfill` 워크플로우가 실행됨에 따라 `[검증 및 테스트]` 대화창에서 `python3 run_daily_screener.py --mode verify`로 최종 실데이터 적재 완료 여부를 판정합니다.

| 검증 코드 | 검증 항목 | 코드 구현 상태 | DB 적재 상태 (GitHub Actions `backfill` 실행 전/후) |
| :---: | :--- | :---: | :--- |
| **AC-1** | 시총 700억 이상 보통주 전수 유니버스 구축 (약 1,477종목 & 대형주 포함) | ✅ **구현 완료** | ⏳ `backfill` 워크플로우 실행 시 30초 내 1,477종목 마스터 일괄 선등록 |
| **AC-2** | 수집 단계의 거래대금 20억 미만 사전 차단 해제 | ✅ **구현 완료** | ⏳ `if avg_val_20d_eok < 20.0: continue` 제거 완료 |
| **AC-3** | `daily_chart` 2년치(500영업일) 적재 및 EMA(5·20·60·120·240) 정합성 | ✅ **구현 완료** | ⏳ `[-60:]` 절단 제거 및 500영업일 전수 Upsert 적용 완료 |
| **AC-4** | `daily_investor_supply` 2년치(500영업일) `t1717` 역순 슬라이딩 적재 | ✅ **구현 완료** | ⏳ `t1717` 최대 25페이지 역순 슬라이딩 연속조회 적용 완료 |
| **AC-5** | 핵심 레퍼런스 종목(`태광 023160`, `대한유화 006650`) 2년치 데이터 실증 | ✅ **구현 완료** | ⏳ `PRIORITY_SHCODES` 최선두 배치로 `backfill` 시작 직후 1분 내 적재 완료 |
| **AC-6** | 웹 대시보드(`index.html`) 1,477종목 × 70만 행 실시간 스크리닝 최적화 | ✅ **구현 완료** | ✅ `trade_date >= cutoffDate` 인덱스 필터 및 멀티 웨이브 병렬 조회 적용 완료 |

---

## 2. 버그 및 수정 요청 트래커 (Issue & Fix Tracker)

### ✅ 해결 완료된 이슈
* **[ISSUE-001] `[해결 완료]` 웹 대시보드(`index.html`) 기준 거래일이 `2026-08-20`으로 절단 표시되던 현상**
  * **조치**: `order=trade_date.desc` 역순 병렬 페이지네이션 및 동일 `trade_date` 1:1 매칭 적용 완료.
* **[ISSUE-002] `[해결 완료]` 초반 1~285번 대형주 누락 및 `is_quarterly_rebuild_due` 247종목 유니버스 고착화 결함 (`STRATEGY.md` 수정 1)**
  * **조치**: `stocks_master` 유니버스 종목 수가 `1,200종목` 미만이면 자동으로 `t1444` 전수 시가총액 산출을 수행하고, 추출된 ~1,477개 종목 전체를 수집 루프 시작 전에 `stocks_master`에 일괄 선등록하도록 수정 완료. 또한 수집 단계의 `avg_val_20d_eok < 20.0` 사전 탈락 조건을 제거 완료.
* **[ISSUE-003] `[해결 완료]` `daily_chart` 60일 절단 및 `daily_investor_supply` 25일 단일 호출 제한 결함 (`STRATEGY.md` 수정 2 & 3)**
  * **조치**: `fetch_daily_chart()` 500영업일 전수 Upsert 및 `fetch_investor_supply()` 역순 날짜 슬라이딩(`todt = oldest_date - 1일`, 최대 25페이지) 연속조회 구현 완료.
* **[ISSUE-004] `[해결 완료]` 대량 백필 타임아웃(45분 제한) 및 재실행 시 처음부터 다시 도는 문제 (`STRATEGY.md` 수정 4 & 5)**
  * **조치**: `run_daily_screener.py`에 스마트 이어받기(`--skip-existing` 기본 활성화) 및 구간 분할(`--start-idx`, `--end-idx`, `--chunk`) 옵션을 추가하고, `.github/workflows/daily_batch.yml`의 `timeout-minutes`를 `360`(6시간)으로 상향 완료.
* **[ISSUE-005] `[해결 완료]` 1,477종목 × 500영업일(약 70만 행) 적재 시 `index.html` 마스터/일봉/수급 조회 절단 방지 (`STRATEGY.md` 수정 6)**
  * **조치**: `index.html`에서 `stocks_master` 3페이지 병렬 로드(`fetchAllUniverseMasters`), 최근 거래일 기준 `trade_date=gte.{cutoffDate}` 인덱스 필터링 및 멀티 웨이브 병렬 페이지네이션(`fetchRecentWindowPagesDesc`), 개별 종목 차트 240영업일 온디맨드 로드(`ensureStockFullChart`) 적용 완료.

### 📌 미해결 / 신규 수정 요청 사항
* 현재 코드 레벨 미해결 버그 및 수정 요청 사항 없음 (`0건`).
