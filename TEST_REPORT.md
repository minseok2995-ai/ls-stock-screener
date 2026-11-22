# 🧪 LS 수급·차트 스크리너 검증 및 테스트 리포트 (`TEST_REPORT.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[검증 및 테스트]` 전담 대화창**에서 테스트 실행 결과, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md) 대조 검수, 데이터 정합성 검증 리포트, 발견된 버그 및 구체적인 코드 수정 제안을 기록하는 문서입니다.
> * **`[프로그램 개발 및 수정(메인)]` 대화창**은 작업 시작 전 본 `TEST_REPORT.md`와 `STRATEGY.md`를 확인하여 미해결 버그(`2.1절 신규 수정 요청 사항`)를 코드에 반영하고, 수정이 완료된 항목의 상태를 **`[해결 완료]`**로 업데이트합니다.

---

## 1. 최신 검수 요약 (`v3.0` 커밋 `a444979` 정밀 전수 검수 — 엔진 Python·JS `100%` 일치 확인, **배치 데이터 무결성 결함 2건(`HIGH`·`MED`) 포함 신규 이슈 6건 발견 → `AC-63` FAIL**)

* **검수 일시**: `2026-11-23 00:10 KST` (`2026-11-22 15:10 UTC`)
* **대상 커밋**: `e2e844a`(명세 [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L1920-L2070) `16절` `AC-61 ~ AC-66`) + `a444979` — `feat(v3.0): 양극 추세 사이클(16단계·63세부현황) 엔진 · DB 확장 · index.html UI 전면 개편` (11개 파일 `+2,595 / −582`)
* **단위·통합 테스트 스위트 실행 결과 (`총 148 / 148 통과 — ALL PASS`)**:
  * `python3 test_screener_verification.py`: **8 / 8 통과 (`OK`)**
  * `python3 -m unittest discover -s tests`: **140 / 140 통과 (`OK`)** — 신규 [`test_v30_trend_cycle.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/tests/test_v30_trend_cycle.py) `6개` + 기존 `134개`(모듈별 개수 `v2 9 · v23 19 · v24 29 · v25 17 · v26 11 · v27 18 · v28 21 · v29 10` 전부 유지, 삭제 `0건`). 기존 테스트 수정분(`test_v2_acceptance.py`의 `filterMode`/`trend_reversal`/AC-16 경계값 → v3.0 자격 경계값, `test_v24`·`test_v29` 무변경 대상 목록에서 `index.html`·`common.js` 제외)은 `16.4절`·`AC-66` "대체된 구 UI/임계값 테스트 정비" 범위로 정당함을 확인.
  * `python3 run_daily_screener.py --mode verify`: **Exit 0** (운영 DB `관심 46 · 보유 1 · 제외 0` 읽기 전용 보존).
* **독립 심층 검증 (운영 Supabase `1,466종목` 100% 읽기 전용 — 모든 비-GET 요청·Upsert 가로채기)**:
  * ✅ **엔진 결정론·3중 구현 일치**: Python [`classify_trend_cycle_series`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L3436-L3649) ↔ JS [`C.TrendCycle.classifySeries`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L2009-L2174) ↔ [`index.html` 내장 폴백 `INLINE_TREND_CYCLE`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L304-L466)에 **실DB 350종목 전체 이력(최대 `1,238봉`) × 5개 윈도우 + 합성 랜덤워크/동률·0·null 스트레스 `1,501`계열 = `3,251`계열 · `1,258,306봉`**을 입력해 `camp·stage·detail·full_label·prob7·prob10` **불일치 `0봉`**, 미분류 `0봉`, 63개 세부코드 **전부 도달**(실데이터만으로도 63/63 도달). 메타 사전(16단계명·63세부명·확률)은 `STRATEGY.md 16.1절` 원문 파싱 대조 오차 `0건`(`B-7 #55~57`은 명세에 세부확률 미기재 → 단계 대표값 `50.0/36.0` 사용).
  * ✅ **AC-62 자격 경계**: `시총 1,000억 + 순매수 1.2억 + 거래대금 6억` 통과, `거래대금 4.5억`·`순매수 0.5억` 탈락, `4.99/5.0억`·`2.99/3.0억`·음수·0 경계 Python/common.js/inline 3중 일치. 운영 `2026-11-20` 후보 `206종목` 전수 재계산 시 명세 수식과 불일치 `0건`(자격통과 `104` · 미달 `102`). 단, 시총 0.1% **정확 경계**에서 부동소수 오차로 탈락하는 케이스 발견(`ISSUE-028`).
  * ✅ **슬롯 게이트·모델 기본값**: `daily/prelim → Step1만`, `daily/final → Step1+2+3`, `ANALYSIS_FORCE_RUN=1 → 전부`, `backfill/universe → 미실행` 12조합 전부 명세 일치, `DEFAULT_GEMINI_MODEL == "gemini-3.5-flash-lite"` 및 [`daily_batch.yml`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/.github/workflows/daily_batch.yml#L99) 기본값 동기화 확인. 실DB 드라이런: prelim `24.6초`(스냅샷 `1,466종목` `15.3초` 포함) · final `26.5초`, `score_trend` 수식 위반 `0건`, `signal_type == "{stage} {name}"` 전수 일치, DSA 행 라벨 ↔ `stocks_master` 스냅샷 라벨 불일치 `0건`.
  * ✅ **DB 스키마**: [`supabase_schema.sql`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/supabase_schema.sql#L387-L413) ↔ [`migration_v30_trend_cycle.sql`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/scripts/migration_v30_trend_cycle.sql) 컬럼 13개·인덱스 2개 완전 동치, **운영 DB에 마이그레이션 적용 완료** 확인(라벨 최대 길이 `40자 < VARCHAR(110)`). 단, v3.0 배치는 아직 미실행(`stocks_master` 추세 컬럼 전부 공란, `daily_supply_analysis` 기존 4개 일자 `783행`은 `trend_stage_code=''`이며 `index.html`은 이 경우 클라이언트 재계산으로 정상 폴백).
  * ❌ **배치 데이터 무결성 결함 발견**: Step 1-B가 `stocks_master`의 `last_close·market_cap_eok·avg_vol_20d·avg_val_20d_eok·shares`를 **배치 시작 시점 값으로 되돌림(영구 동결)**(`ISSUE-023`, HIGH), prelim→final 사이 후보에서 빠진 종목의 prelim 행이 삭제되지 않고 잔존(`ISSUE-024`, MED). **v3.0 배치가 아직 한 번도 돌지 않아 운영 피해는 `0건`이며, 다음 배치(`2026-11-23(월) 16:05 KST`) 전에 수정이 필요합니다.**

---

### 1.1 `v3.0` 신규 요구사항 (`AC-61` ~ `AC-66`) 검수 결과표

| 검증 코드 | 검증 항목 (`STRATEGY.md` 16.5절) | 코드 감사 · 운영 실DB 읽기 전용 드라이런 · 패리티/경계값/시뮬레이션 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-61** | **16단계·63세부현황 엔진 결정론 및 Python·JS 100% 일치** | • `3,251`계열 `1,258,306봉` Python↔common.js↔index 내장본 불일치 `0봉`, 63/63 코드 도달, 메타 사전 명세 대조 오차 `0건`<br>• ⚠️ 엔진 자체는 일치하나 `has_240 = i >= 239`·`camp` 경로 의존성 때문에 **입력 윈도우 길이에 따라 결과가 달라짐**(460달력일 `308봉` 기준 최종봉 `2.1%` 진영 반전) → `ISSUE-025` | **PASS** (조건부: `ISSUE-025`) |
| **AC-62** | **신규 자격 기준(`5억` & `3억`/`시총 0.1%`) 정확성** | • 명세 예시 3종(통과 1 / 탈락 2) 및 경계값 11종 3중 구현 일치, 운영 후보 `206종목` 재계산 불일치 `0건`<br>• ⚠️ `시총 700억 × 0.001 = 0.7000000000000001` 부동소수 오차로 정확 경계(`0.7억`) 탈락 → `ISSUE-028`(LOW) | **PASS** (LOW 1건) |
| **AC-63** | **prelim+final DB 적재 · `stocks_master` 스냅샷 · `gemini-3.5-flash-lite` 기본값** | • 슬롯 게이트 12조합·기본 모델·스냅샷 `1,466종목` 갱신 동작 확인<br>• ❌ 스냅샷 Upsert가 배치가 방금 갱신한 `stocks_master` 시세/유동성 컬럼을 **배치 시작 시점 값으로 덮어써 영구 동결**(`ISSUE-023`)<br>• ❌ final이 prelim 잔존 행을 정리하지 않아 동일 일자 `daily_rank` 중복·탈락 종목 노출(`ISSUE-024`) | **FAIL** |
| **AC-64** | **`index.html` 3단 UI (상승/하락 탭 → 8개 추세 → 세부합산 리스트)** | • 자격 통과 종목만 표시, 진영별 8개 버튼·종목수·`+7%` 확률·세부 미니배지·합산 리스트 렌더링 코드 감사 및 `test_v30` Node VM 검증 통과<br>• ⚠️ 차트 `240일/720일` 클릭 시 `750봉` 재로딩 → 재분류로 선택 종목이 다른 탭으로 이동·선택 해제될 수 있음(`ISSUE-025`) | **PASS** (조건부: `ISSUE-025`) |
| **AC-65** | **차트 당일 배지 + 캔들 호버 시점별 추세 표시** | • `[상위추세 \| 세부현황]` 메인 배지·`+7%/+10%` 확률·호버 시 `📍 호버 날짜` 동적 갱신·마우스 이탈 시 기준일 복귀·크게 보기 모달 배지 확인<br>• ⚠️ 호버 라벨은 로드된 `308봉` 기준이라 최근 60봉 중 `10.7%`가 전체 이력 기준과 다름(`ISSUE-025`) | **PASS** (조건부: `ISSUE-025`) |
| **AC-66** | **마이그레이션 정합성 · 전체 회귀 100% PASS** | • 스키마↔마이그레이션 완전 동치, 운영 DB 적용 확인, `watchlist.html`·`holdings.html` 무변경, 전체 **`148 / 148` PASS** | **PASS** |

---

### 1.2 기존 요구사항 (`AC-1` ~ `AC-60`) 회귀 검증 요약 (`v3.0` 적용 후)

| 검증 코드 | 검증 항목 요약 | `v3.0` (`a444979`) 적용 후 회귀 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-1 ~ AC-18** | 유니버스, EMA·순수기관 수식, 배치 Cron, 멱등성 가드, 엑셀 | `test_screener_verification.py`(8/8), `test_v2_acceptance.py`(9/9, `16.4절` 대체 UI 반영), `--mode verify` Exit 0 | **PASS** |
| **AC-19 ~ AC-23** | 차트 5년·수급 3년 적재, 앵커 EMA, 무지연 PK 조회 | `test_v23_acceptance.py`(19/19) | **PASS** |
| **AC-24 ~ AC-29** | 3페이지 분리, 추천/비추천, 영구제외, 스마트 병합, 보유/청산 | `test_v24_watchlist_holdings.py`(29/29), 운영 DB 무손상. ⚠️ `stocks_master` 시세 컬럼 동결(`ISSUE-023`) 시 `watchlist.html` 시총·평균거래대금 표시가 장기적으로 낡게 됨 | **PASS** (영향 예고) |
| **AC-30 ~ AC-48** | 패턴·4축 평가, 프로 차트, 2회 배치, 실시간 시세 | `test_v25`(17/17) · `test_v26`(11/11) · `test_v27`(18/18), `common.js` 공유 함수(`buildBriefing` 선택 인자·`onHoverCandle`) 하위 호환 확인 | **PASS** |
| **AC-49 ~ AC-56** | Keep-Alive, 프리페치, 정속 페이서 | `test_v28_batch_perf.py`(21/21); v3.0 Step 1 추가 비용 `≈25초/슬롯`으로 30분 예산 내 | **PASS** |
| **AC-57 ~ AC-60** | 일일 수급 분석·Gemini Top N·사후 복기 | `test_v29_daily_analysis.py`(10/10). ⚠️ v3.0 `signal_type` 변경으로 유사조건 과거 승률 트랙이 전부 `단기혼합`으로 오분류(`ISSUE-026`) | **PASS** (MED 1건) |

---

## 2. 버그 및 수정 요청 트래커 (Issue & Fix Tracker)

### 🚨 2.1 `[프로그램 개발 및 수정]` 대화창 신규 수정 요청 사항

> [!IMPORTANT]
> `ISSUE-023`·`ISSUE-024`는 **다음 운영 배치(`2026-11-23(월) 16:05 KST` prelim) 전에 반드시 수정**해야 합니다. 현재까지 v3.0 배치가 한 번도 실행되지 않아 운영 데이터 손상은 `0건`입니다.

* **[ISSUE-023] `[미해결 · HIGH]` Step 1-B `stocks_master` 스냅샷이 배치가 갱신한 시세/유동성 컬럼을 배치 시작 시점 값으로 되돌림 → 영구 동결**
  * **위치**: [`update_universe_trend_snapshots`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L5108-L5131) (`STOCKS_MASTER_TREND_UPSERT_COLS`, [L5029-L5044](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L5029-L5044)) ← [`run_standalone_batch`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L3037-L3044)가 **배치 시작 시 조회한** `existing_masters`([L2446](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L2446))를 그대로 전달.
  * **현상**: 배치 루프([L2857-L2868](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L2857-L2868))가 `last_close·market_cap_eok(shares×종가)·avg_vol_20d·avg_val_20d_eok`를 새로 기록한 직후, Step 1-B가 `on_conflict=shcode` Upsert로 `hname·market·shares·market_cap_eok·avg_vol_20d·avg_val_20d_eok·is_universe·last_close`를 **배치 시작 전 값으로 덮어씁니다.** 다음 날 배치는 그 낡은 값을 다시 `existing_masters`로 읽으므로 **v3.0 최초 실행 시점 값으로 영구 동결**됩니다(분기 재산출 `initial_master_rows`도 동일하게 되돌려짐).
  * **재현(읽기 전용 시뮬레이션, `005930`)**: 배치가 쓴 값 `last_close 182,134 / 시총 10,581,473.43억 / avg_vol 18,176,942 / avg_val 37,826.44억` → Step 1-B 후 `180,900 / 10,575,918.43 / 18,176,165 / 37,727.44`로 **4개 컬럼 전부 원복**(`reverted=True`).
  * **영향**: `index.html` 자격 판정의 `시총 0.1%` 기준, `watchlist.html`/`holdings.html` 시총·평균거래대금 표시, `score_daily_supply_candidate`의 `market_cap_eok` 등이 갈수록 실제와 괴리.
  * **수정 제안**: ① Step 1-B 직전에 `supabase_fetch_existing_masters()`로 **최신 마스터를 재조회**해 사용(또는 `run_standalone_batch`에서 `existing_masters=None` 전달), 그리고/또는 ② 스냅샷 Upsert 페이로드를 `shcode + trend_* 5개 컬럼`만으로 축소하되 NOT NULL 제약 때문에 Upsert가 불가하면 `(trend_camp, stage, detail, label)` 조합별로 묶어 `PATCH stocks_master?shcode=in.(...)` 로 추세 컬럼만 갱신(최대 63개 그룹 × 청크). 회귀 테스트: "배치가 갱신한 `last_close`가 Step 1-B 후에도 유지" 케이스 추가.

* **[ISSUE-024] `[미해결 · MED]` final 슬롯이 prelim에서 적재된 동일 일자 탈락 종목 행을 삭제하지 않음**
  * **위치**: [`run_daily_supply_analysis_pipeline`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L5333-L5339) — prelim(16:05)과 final(20:30) 모두 `trade_date` 동일 행을 Upsert만 하며, `daily_supply_analysis?trade_date=eq.{date}` 정리 DELETE가 없음(존재하는 DELETE는 365일 보관 정리뿐).
  * **재현(실DB `2026-11-20` 드라이런 + final 시점 확정 수급에서 `000080` 비중 하락 시뮬레이션)**: prelim `206행` 적재 → final 후보 `205종목`인데 DB에는 `206행` 잔존, 탈락 종목 `000080`이 prelim 순위 `#73`·`is_qualified=True`·`B-3 저점 중기상승 | 120일선 돌파(240일아래)`로 남아 **`daily_rank` 중복 1건**, `trade_date` 정리 DELETE 요청 `0건`.
  * **영향**: 로컬 미니 HTS·`index.html` AI 카드 조회 시 확정 기준 미달 종목 노출, Step 3 사후 복기 백필이 잔존 행까지 집계해 과거 승률 통계 오염.
  * **수정 제안**: Step 1-A Upsert 직후(최소 final 슬롯) `DELETE /rest/v1/daily_supply_analysis?trade_date=eq.{target_date}&shcode=not.in.({ranked_codes})` 실행(후보 `≤ ~300`개로 URL 길이 안전, `ranked_rows`가 비면 생략). 회귀 테스트: prelim→final 후보 축소 시 잔존 행 `0건`·`daily_rank` 유일성.

* **[ISSUE-025] `[미해결 · MED]` 추세 분류 입력 윈도우(460달력일 ≈ `308봉`)가 짧아 진영 오판 및 화면 간 라벨 불일치**
  * **위치**: [`DSA_CHART_WARMUP_CALENDAR_DAYS = 460`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L106), [`index.html` `ensureSupplyCandidatesWarmup`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L611-L660), 차트 [`fetchLong`(`750봉`)](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L1460-L1475) → [`onDataLoaded`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L1527-L1535) → [`syncRecommendationAfterLoad`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L1497-L1509) → [`applyScreening` 선택 이동](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L944-L946).
  * **실측(실DB `336종목`, 각 종목 전체 이력 `≥400봉` 기준 대조)**: 최종봉 라벨 불일치 — `460달력일(308봉)` **`7/336 (2.1%)`, 전부 진영 반전**(예: `009970` 전체이력 `A-5 #27` ↔ 308봉 `B-7 #55`, `007330` `C-1 #60` ↔ `C-2 #63`; 실제 수급 후보만 보면 `4/191`), `240봉` `64/336 (19%)`, **`750봉` `0/336`**. 최근 60봉(호버 대상) 불일치: 308봉 `2,160/20,160 (10.7%)` vs 750봉 `0/20,160`.
  * **영향**: DB/리스트 라벨이 약 2% 종목에서 반대 진영 탭에 표시, 사용자가 차트 `240일/720일`을 누르면 `750봉`으로 재분류되어 **선택 종목이 다른 탭으로 이동·선택 해제**, 호버 과거 라벨 부정확. (`16.2절` "최소 300영업일"은 형식상 충족하나 `16절` "예외 0%" 목표와 상충.)
  * **수정 제안**: 워밍업을 **`≥ 750봉`(약 `1,100달력일`)**로 확대(차트 조회는 1종목/요청 또는 `offset` 페이지네이션, 스냅샷 `1,466`요청 × 12워커 ≈ 수십 초 수준), 프론트 리스트·차트·호버가 **동일 시계열**을 쓰도록 통일(또는 `onDataLoaded` 재분류 시 현재 선택 종목 유지). 명세 `16.2절 3항`의 "300영업일"을 "750영업일"로 상향하는 `STRATEGY.md` 개정 권고.

* **[ISSUE-026] `[미해결 · MED-LOW]` v3.0 `signal_type` 변경으로 유사조건 과거 승률 트랙 오분류**
  * **위치**: [`map_signal_type_to_track`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L4003-L4009) / [`build_historical_track_stats`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L4026-L4038) / [`signal_type = f"{stage} {name}"`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L4344).
  * **현상**: v3.0 행의 `signal_type`(`"A-1 장기고점(완전정배열)"` 등)은 `map_signal_type_to_track()`에서 전부 `"단기혼합"`으로 매핑되고, 해당 `(trade_date, shcode)`는 `seen_keys`로 차트 기반 재계산에서도 제외 → 사후 복기가 쌓일수록 `정배열`/`바닥첫수급` 표본이 빠지고 `단기혼합`에 섞여 `hist_win_rate_5d/10d`(Gemini 입력 포함)가 왜곡.
  * **수정 제안**: v2.9 트랙을 별도로 판정해 매핑하거나(`classify_v29_trend_structure` 결과를 행에 보존 후 사용), `signal_type`이 `^[ABC]-\d ` 패턴이면 `prior_dsa_rows` 집계에서 제외하고 차트 기반 재계산에 맡김.

* **[ISSUE-027] `[미해결 · LOW]` `_upsert_dsa_rows_safe` PGRST204 폴백이 실제 HTTP 오류에서 작동하지 않는 사실상 죽은 코드**
  * **위치**: [`_upsert_dsa_rows_safe`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L4568-L4591) — `"PGRST204" in str(exc)` 검사. 실제 예외는 [`urllib.error.HTTPError`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L244)이고 `str()`은 `"HTTP Error 400: Bad Request"`(본문 미포함).
  * **재현(로컬 HTTP 서버가 `400 {"code":"PGRST204",...}` 응답)**: trend 컬럼 POST 3회 재시도 후 `HTTPError` 그대로 전파, 기본 컬럼 폴백 POST `0회`. 단위 테스트는 메시지에 `PGRST204`가 담긴 모의 예외로만 통과. (운영 DB는 마이그레이션 적용 완료라 현재 영향 없음.)
  * **수정 제안**: `body = exc.read().decode("utf-8", "replace") if isinstance(exc, urllib.error.HTTPError) else ""` 후 `"PGRST204" in body or "trend_" in body` 로 판정(또는 `supabase_upsert`가 응답 본문을 포함한 예외 메시지를 던지도록 개선).

* **[ISSUE-028] `[미해결 · LOW]` `시총 0.1%` 정확 경계에서 부동소수 오차로 자격 탈락**
  * **위치**: Python [`qualify_supply_candidate_v30`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/run_daily_screener.py#L3667), JS [`qualifySupplyItem`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L2191), [`index.html` 내장본](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L462).
  * **현상**: `시총 700억 × 0.001 = 0.7000000000000001` → 순매수 `0.7억`(정확히 0.1%)이 `≥` 비교에서 탈락(3중 구현 동일하게 탈락하므로 패리티는 유지).
  * **수정 제안**: 3곳 모두 `amt * 1000.0 >= mcap` 또는 `amt >= mcap * 0.001 - 1e-9` 로 통일하고 `700억/0.7억` 경계 테스트 추가.

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
