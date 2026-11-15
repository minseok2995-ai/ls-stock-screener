# 🧪 LS 수급·차트 스크리너 검증 및 테스트 리포트 (`TEST_REPORT.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[검증 및 테스트]` 전담 대화창**에서 테스트 실행 결과, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md) 대조 검수, 데이터 정합성 검증 리포트, 발견된 버그 및 구체적인 코드 수정 제안을 기록하는 문서입니다.
> * **`[프로그램 개발 및 수정(메인)]` 대화창**은 작업 시작 전 본 `TEST_REPORT.md`와 `STRATEGY.md`를 확인하여 미해결 버그(`2.1절 신규 수정 요청 사항`)를 코드에 반영하고, 수정이 완료된 항목의 상태를 **`[해결 완료]`**로 업데이트합니다.

---

## 1. 최신 검수 요약 (`v2.4.1` 커밋 `16f575d` + 운영 DB RLS/GRANT 조치 완료 — `AC-1 ~ AC-29` 전 항목 최종 PASS)

* **검수 일시**: `2026-11-15 20:05 KST` (`2026-11-15 11:05 UTC`)
* **대상 커밋**: `16f575d` — `fix(v2.4.1): ISSUE-011~014 RLS GRANT/42501 배너, 바닥종목 이탈 오판, 제외관리 즉시반영, 보유 차트/목표가 기준` ([`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L599-L844) `7절` 전 요구사항)
* **단위·통합 테스트 스위트 및 회귀 검증 실행 결과**:
  * `python3 test_screener_verification.py`: **8 / 8 통과 (`OK`)**
  * `python3 -m unittest discover -s tests -v`: **57 / 57 통과 (`OK`, `2.287s` — `test_v24_watchlist_holdings.py` `29개` + `test_v23_acceptance.py` `19개` + `test_v2_acceptance.py` `9개`)**
  * `python3 run_daily_screener.py --mode verify`: **전 항목 정상 통과 (`Exit 0`, `1,463` 유니버스 · 차트 `1,233일` · 수급 `739일` 무손상)**
* **운영 Supabase 실서버(`T = 2026-11-13`, 무모킹 실제 `POST/PATCH/DELETE` CRUD) + Node VM 3페이지 E2E 최종 검수 결과**:
  * ✅ **`[ISSUE-011]` 해결 확인 (`AC-24` PASS)**: 사용자 SQL Editor 실행으로 운영 Supabase 신규 3개 테이블(`excluded_stocks`, `watchlist_items`, `portfolio_holdings`)의 RLS 쓰기 차단이 완전 해제되어 브라우저 동일 키(`sb_publishable_...`) 기반 실서버 `POST` / `UPSERT` / `PATCH` / `DELETE`가 전 테이블에서 정상 동작함을 실증 완료했습니다. 더불어 [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L90-L92)에 `code === "42501"`(`err.rlsBlocked`) 감지 및 원클릭 복구 SQL 배너 자동 노출이 적용되었고, [`scripts/migration_v24_watchlist_holdings.sql`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/scripts/migration_v24_watchlist_holdings.sql#L79-L83) · [`supabase_schema.sql`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/supabase_schema.sql#L280-L283) · `common.js` 내장 SQL 3곳이 `GRANT ALL ... TO anon, authenticated, service_role`까지 100% 동일하게 동기화되었습니다.
  * ✅ **`[ISSUE-012]` 해결 확인 (`AC-27` PASS)**: [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L297-L299) [`evaluateWatchlistItem()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L284-L315)이 `recommend_tag === "추세수급"` 출신 종목에 한해서만 `ema20Break` / `ema60Break`를 판정하도록 수정되었습니다. 운영 DB에 `2026-11-13` 실제 대바닥 추천 종목(`017800 현대엘리베이터`, `267270 HD건설기계` [`바닥지지 연속수급`], `448900 한국피아이엠`, `098460 고영` [`바닥전환 첫수급`])을 실제 병합 후 `watchlist.html`을 로드(`1,188ms`)한 결과 **4종목 전원 `ema20Break = false`, `ema60Break = false`, `isExit = false`(`0건` 오판)** 로 정상 유지되었으며, 손절가 이탈(`stopBreak`) 및 기관 대량매도(`supplyExit`) 경보는 트랙 무관 정상 작동함을 확인했습니다.
  * ✅ **`[ISSUE-013]` 해결 확인 (`AC-26` PASS)**: [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L507-L569) `onExcludedChange(fn)` 글로벌 훅과 [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L1524-L1527) 자동 재스크리닝 연결을 통해, 상단 `[🚫 제외관리]` 모달에서 **업종 프리셋 체크박스 개별 선택 등록** 및 **`[복구]` 클릭 즉시 F5 없이 화면 리스트 재노출(`hookCalledCount` 즉시 증가)** 이 작동하며 상단 `🚫 영구제외 K종목 자동 숨김` 배지도 정확히 표시됩니다.
  * ✅ **`[ISSUE-014]` 해결 확인 (`AC-28` PASS)**: [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L331-L332) [`evaluateHolding()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L317-L343)이 `현재가(close)` 기준으로 `🎯 1차도달` / `🚀 2차도달`을 판정하고 `1,300달력일` 초과 장기보유 일봉 분할 조회를 지원하며, [`holdings.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/holdings.html#L60-L182)이 `h.id` 고유 키 기반으로 전환되어 **`(D+N일)` 경과일 병기** 및 **동일 종목 다회 청산 히스토리(`005930 삼성전자` `id=5` `57봉`, `id=6` `48봉`) 클릭 시 온디맨드 캔들차트(`매수가` · `1/2차 목표가` · `청산가` 수평선 + `매수`/`청산` 마커) 렌더링**까지 완벽히 통과했습니다.
  * 🧹 **운영 DB 클린업 확인**: 실서버 CRUD E2E 테스트 직후 테스트용 행 전량 삭제 및 검증을 완료하여 운영 DB 신규 3개 테이블 모두 **`0건`(`excluded_stocks: 0`, `watchlist_items: 0`, `portfolio_holdings: 0`)** 깨끗한 초기 상태를 유지하고 있습니다.

---

### 1.1 `v2.4 / v2.4.1` 신규 합격 기준 (`STRATEGY.md` 7.6절 — `AC-24` ~ `AC-29`) 최종 검수 결과표

| 검증 코드 | 검증 항목 (`STRATEGY.md` 7.6절) | 코드 감사 · 운영 Supabase(`2026-11-13`) 무모킹 CRUD · Node VM 3페이지 실증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-24** | **3페이지 독립 분리(`index` · `watchlist` · `holdings`) · 신규 3개 테이블 스키마 · PostgREST 안전 처리 검증** | • `index.html` / `watchlist.html` / `holdings.html` + `common.js` 독립 구성, 상단 4개 내비게이션 실시간 카운트 배지 및 `<a href>` 새 탭 호환 확인<br/>• 운영 Supabase 3개 테이블 실서버 `POST` / `UPSERT` / `PATCH` / `DELETE` 전 구간 `2xx` 정상 작동 확인 (`idx_holdings_active_shcode WHERE status = 'HOLDING'` 부분 고유 인덱스 작동 포함)<br/>• `Prefer: return=representation`, `204 No Content`/빈 본문 안전 파싱(`parseBodySafe`), `404 / PGRST205 / 42P01 / 42501(RLS)` 감지 원클릭 복구 SQL 배너 검증 완료 | **PASS** |
| **AC-25** | **`🟢 추천 / ⚪ 비추천` 3단계 자동 분류 수식 및 `125일` 바닥 후보 일봉 보강 검증** | • `Step 1` 공통 비추천(`[저변동] < 2.5%`, `[음봉마감] Close < Open`, `[5일선이탈] Close < EMA 5`) 경계값 및 **양봉(`Close >= Open`) 윗꼬리·단기과열 미제외 원칙** 정확 동작 확인<br/>• `getStage1ReversalCandidateCodes()`가 `패턴 A` + `패턴 B` 1차 후보(`2026-11-13` 기준 `41종목`)를 추출해 `applyScreening()` 전 `125달력일`(`84영업일`) 일봉을 선행 로드하며, 포착 전 종목(`132종목`) 125일 전수 조회 대비 **분류 오차 `0건`(`100%` 일치)** 실증<br/>• `2026-11-13` 실측: `당일10%` `123종목` = **`🟢 추천 47`** (`추세수급 33` · `바닥지지 연속수급 11` · `바닥전환 첫수급 3`) + **`⚪ 비추천 76`**; `하락추세전환` `4종목` 전원 `🟢 바닥전환 첫수급` 승격 | **PASS** |
| **AC-26** | **`🚫 영구 제외 사전` 차단 · 복구 및 프리셋 도우미 검증** | • 행 우측 `[🚫]` 원클릭 제외 및 상단 `🚫 영구제외 K종목 자동 숨김` 안내 배지 즉시 반영 확인<br/>• `[🚫 제외관리]` 모달 내 **업종 프리셋 2단계 체크박스 개별 선택 등록**(`105560`만 체크 등록 시 `['105560']`만 정확히 저장) 및 **`[복구]` 클릭 시 `onExcludedChange` 훅을 통한 F5 없는 즉시 재노출** 실서버 검증 완료 | **PASS** |
| **AC-27** | **`⭐ 스마트 병합` 멱등성 · 기존 관심종목 보호 · 대바닥 트랙 이탈 예외 · 수작업 제외 3종 검증** | • 실서버 스마트 병합: 최초 병합(`signal_count = 1`), 동일일 재병합 멱등성(`inserts = 0, updates = 0`), 후속일(`T+3`) 재포착 시 `signal_count = 2` 증가 및 `first_signal_date/close` · `grade` · `memo` · `stop_price` 완벽 보존, **`⚪ 비추천` 날 기존 관심종목 무삭제·무증가 보호** 실증 완료<br/>• `바닥지지 연속수급`(`017800`, `267270`) · `바닥전환 첫수급`(`448900`, `098460`) 실데이터 병합 시 `watchlist.html`(`1.19초` 로드)에서 **`ema20Break/ema60Break` 오판 `0건`(`isExit = false`)**, `추세수급` 이평 이탈 및 공통 손절가·수급이탈 경보 정상 작동 확인<br/>• `#mergeBtnLabel`(`⭐ 선택 종목 관심종목 병합 (47)` → 부분 선택 시 `(4)`) 및 `#chkAllRows` 동기화, 개별 `[🗑]` / 체크박스 일괄 / `[이탈·정리 대상 일괄 정리]` 수동 삭제 검증 완료 | **PASS** |
| **AC-28** | **`💼 보유종목` 목표가(`+5%/+10%`) · 추천 청산가(`20일선`) 연동 및 실제 청산가 수동 입력 히스토리(`A안`) 검증** | • 진입가 대비 `+5%/+10%` 자동 계산, **`현재가(close)` 기준 `🎯 1차도달 / 🚀 2차도달` 배지**(`039490 키움증권`: 매수 `200,000`, 현재 `205,500`, 1차 `210,000` → 미점등 정확), 기준일 $T$ `EMA 20`(`207,909원`) 추천 청산가 및 `🚨 20일선 이탈` 경보, 매수일 `(D+N일)` 경과일 표시 확인<br/>• 실서버 `HOLDING` 중복 등록 시 **`HTTP 409`** 차단 → `청산 완료 기록`(`+7.50%`, `+30,000원`) 후 동일 종목 신규 행 재매수(`A안`, `id` 분리) 성공 → 재청산(`-2.00%`, `-4,200원`) 후 통산 요약 카드(`총 2건 · 승률 50.0% · 평균 +2.75% · 누적 +25,800원`) 수식 100% 일치<br/>• 동일 종목(`005930 삼성전자`) 다회 `CLOSED` 히스토리 행 각각 클릭 시 온디맨드 일봉(`57봉` / `48봉`) 로드 및 `진입`·`1차`·`2차`·`청산` 수평선 + `매수`/`청산` 마커 차트 정상 렌더링 확인 | **PASS** |
| **AC-29** | **기존 스크리닝·배치 무결성 회귀 검증 (`AC-1 ~ AC-23` 무손상)** | • `run_daily_screener.py --mode verify` `Exit 0`, `send_telegram_alert()` Markdown `HTTP 400` → Plain Text 재전송 폴백(`test_telegram_400_markdown_fallback`) 정상 동작<br/>• `index.html` `전체` 탭 포착 종목 수(`123 / 81 / 47 / 43 / 4종목`) 기존 `v2.3.1`과 **오차 `0건`**, 탭별 9열 `.xlsx` 다운로드 정상, 기존 3개 핵심 테이블(`271.8만 행`) 무손상 유지 | **PASS** |

---

### 1.2 `2026-11-13` 운영 DB 실데이터 기준 `index.html` 5개 모드별 `🟢 추천 / ⚪ 비추천` 분포 실측표

| 스크리닝 모드 / 옵션 | 전체 포착 (`tabAll`) | `🟢 추천 후보` (`tabRec`) | 추천 세부 유형 분해 (`추세` / `바닥지지 B` / `바닥전환 A`) | `⚪ 비추천 보류` (`tabHold`) | 비추천 세부 사유 분해 |
| :--- | :---: | :---: | :--- | :---: | :--- |
| **`기관 수급 · 당일 10% 이상`** | **123종목** | **47종목** | `추세수급 33` · `바닥지지 연속수급 11` · `바닥전환 첫수급 3` | **76종목** | `[역배열낙하] 35` · `[음봉마감] 15` · `[5일선이탈] 12` · `[음봉마감][5일선이탈] 7` · `[20일선이탈] 6` · `[60일선이탈] 1` |
| **`기관 수급 · 당일 15% 이상`** | **81종목** | **30종목** | `추세수급 21` · `바닥지지 연속수급 8` · `바닥전환 첫수급 1` | **51종목** | `[역배열낙하] 23` · `[음봉마감] 11` · `[5일선이탈] 9` · `[음봉마감][5일선이탈] 4` · `[20일선이탈] 4` |
| **`기관 수급 · 당일 20% 이상`** | **47종목** | **20종목** | `추세수급 12` · `바닥지지 연속수급 8` | **27종목** | `[역배열낙하] 16` · `[음봉마감] 4` · `[5일선이탈] 4` · `[20일선이탈] 2` · `[음봉마감][5일선이탈] 1` |
| **`기관 수급 · 3일 연속 5% 이상`** | **43종목** | **23종목** | `추세수급 15` · `바닥지지 연속수급 8` | **20종목** | `[음봉마감] 9` · `[역배열낙하] 5` · `[20일선이탈] 3` · `[음봉마감][5일선이탈] 2` · `[5일선이탈] 1` |
| **`하락 추세 전환 수급 발생`** | **4종목** | **4종목** | `바닥전환 첫수급 4` (`448900, 000320, 437730, 098460`) | **0종목** | 해당 없음 (`0건`) |

---

### 1.3 기존 요구사항 (`AC-1` ~ `AC-23`) 회귀 검증 요약 (`v2.4.1` 적용 후 전 항목 PASS 유지)

| 검증 코드 | 검증 항목 요약 | `v2.4.1` (`16f575d`) 적용 후 회귀 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-1 ~ AC-18** | 유니버스(`1,463종목`), EMA·순수기관 수식, 4중 배치 Cron, 멱등성 가드, 유동성 제외 필터, 9열 엑셀 | `test_screener_verification.py`(8/8), `test_v2_acceptance.py`(9/9), `--mode verify` 전 항목 오차 `0건` | **PASS** |
| **AC-19 ~ AC-23** | 차트 5년(`1,678,171행`) · 수급 3년(`1,040,512행`) 비대칭 적재, 앵커 EMA, 무지연 PK 조회 | `test_v23_acceptance.py`(19/19), 7종목 `1,233일 / 739일` 범위 및 웹 초기 로드 무결성 정상 유지 | **PASS** |

---

## 2. 버그 및 수정 요청 트래커 (Issue & Fix Tracker)

### 🚨 2.1 `[프로그램 개발 및 수정]` 대화창 신규 수정 요청 사항

* **현재 미해결 버그 없음 (`0건`)** — `AC-1 ~ AC-29` 전 항목 최종 합격(`PASS`).

---

### ✅ 2.2 해결 완료된 이슈 히스토리 아카이브

* **[ISSUE-011 ~ ISSUE-014] `[해결 완료 (v2.4.1, 16f575d + 운영 DB RLS 해제/GRANT 반영)]`**
  * **`[ISSUE-011]`**: 운영 Supabase SQL Editor `DISABLE ROW LEVEL SECURITY` + `GRANT ALL` 실행으로 신규 3개 테이블 실서버 CRUD 차단 완전 해소, `common.js` `code === '42501'`(`rlsBlocked`) 감지 및 원클릭 복구 SQL 배너 노출, 마이그레이션 SQL 3곳 동기화 완료 (`AC-24`).
  * **`[ISSUE-012]`**: `evaluateWatchlistItem()`이 `recommend_tag === '추세수급'` 출신 종목만 `20일선/60일선 이탈`을 판정하도록 수정하여 `바닥지지 연속수급`·`바닥전환 첫수급` 병합 직후 이탈 오판 `0건` 확인 (`AC-27`).
  * **`[ISSUE-013]`**: `common.js` `onExcludedChange` 글로벌 훅 연결로 `[🚫 제외관리]` 모달 `[복구]`·추가 시 `index.html` 즉시 재노출/숨김 반영, 상단 `🚫 영구제외 K종목 자동 숨김` 배지 및 업종 프리셋 체크박스 개별 선택 등록 완료 (`AC-26`).
  * **`[ISSUE-014]`**: `evaluateHolding()` 목표가 배지 기준을 `현재가(close)`로 정합화, `holdings.html` `h.id` 키 분리·`(D+N일)` 경과일 표시·`[📜 청산 히스토리]` 클릭 시 온디맨드 캔들차트(`청산` 라인·마커 포함) 로드 및 `1,300일` 초과 장기보유 일봉 분할 조회 안전장치 반영 완료 (`AC-28`).
* **[v2.3.1 검증 완료 (`353f92a`, `Run #43682739754` & `Run #43685346608`)]** 차트 5년(`2021-11-01~`, `1,678,171행`) · 수급 3년(`2023-11-01~`, `1,040,512행`) 비대칭 확장 백필 1회차 `2시간 44분` 100% 완주, 앵커 시드 EMA 연속성, 거래정지 `25종목` 미확정 오판 차단, `80분` 주기 토큰 자동 갱신 및 `271.8만 행` 대용량 DB 무지연(`AC-19 ~ AC-23`) 전 항목 합격.
* **[v2.2 검증 완료 (`6bfbbd5`)]** `[기관 수급 발생 종목]` 유동성·수급금액 제외 필터(`당일 기준` vs `3일 연속 3일 평균 기준`) 및 `[엑셀 저장]` 9개 컬럼 개편(`AC-16 ~ AC-18`) 전 항목 합격.
* **[v2.1 검증 완료 (`1aecd41`)]** `20:30 KST` 다중 백업 Cron, `KST` 표준시 고정, `--skip-if-completed` 멱등성 가드(`< 2.3초` 종료), `if: failure()` 장애 알림, Apps Script 외부 정각 웹훅(`AC-13 ~ AC-15`) 및 `두산에너빌리티(034020)` 백필 자동 복구 확인 완료.
* **[ISSUE-006 ~ ISSUE-010] `[해결 완료 (v1.4.3 ~ v2.0)]`** `PRIORITY_SHCODES` 제거, `has_2yr_history` 판정 분리, 장중 미확정 수급 차단, 복합 PK 병렬 조회 전환(`HTTP 500` 해소), `AC-1 ~ AC-12` 검증 체계 구축 완료.
* **[ISSUE-001 ~ ISSUE-005] `[해결 완료 (v1.4)]`** 1,463종목 시총 ≥ 700억 전수 유니버스 구축, 일봉·수급 500영업일 역순 슬라이딩 적재, Actions 360분 타임아웃 상향 완료.
