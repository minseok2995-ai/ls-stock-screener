# 🧪 LS 수급·차트 스크리너 검증 및 테스트 리포트 (`TEST_REPORT.md`)

> **문서 역할 및 협업 규칙 (`StudyRemote` 3원화 워크플로우)**
> * 본 문서는 **`[검증 및 테스트]` 전담 대화창**에서 테스트 실행 결과, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md) 대조 검수, 데이터 정합성 검증 리포트, 발견된 버그 및 구체적인 코드 수정 제안을 기록하는 문서입니다.
> * **`[프로그램 개발 및 수정(메인)]` 대화창**은 작업 시작 전 본 `TEST_REPORT.md`와 `STRATEGY.md`를 확인하여 미해결 버그(`2.1절 신규 수정 요청 사항`)를 코드에 반영하고, 수정이 완료된 항목의 상태를 **`[해결 완료]`**로 업데이트합니다.

---

## 1. 최신 검수 요약 (`v2.4` 커밋 `9cdfd9a` 정밀 검수 완료 — `AC-25`, `AC-29` PASS / `AC-24`, `AC-26 ~ AC-28` 보완 필요 4건 발견)

* **검수 일시**: `2026-11-15 19:50 KST` (`2026-11-15 10:50 UTC`)
* **대상 커밋**: `9cdfd9a` — `feat(v2.4): 3페이지 관심종목·보유종목·영구제외, 추천/비추천 3단계 분류, 텔레그램 400 폴백` ([`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L599-L844) `7절` 구현)
* **단위·통합 테스트 스위트 및 회귀 검증 실행 결과**:
  * `python3 test_screener_verification.py`: **8 / 8 통과 (`OK`)**
  * `python3 -m unittest discover -s tests -v`: **53 / 53 통과 (`OK`, `2.160s` — `test_v24_watchlist_holdings.py` `25개` + `test_v23_acceptance.py` `19개` + `test_v2_acceptance.py` `9개`)**
  * `python3 run_daily_screener.py --mode verify`: **전 항목 정상 통과 (`Exit 0`, `1,463` 유니버스 · 차트 `1,233일` · 수급 `739일` 무손상)**
* **운영 Supabase 실데이터(`T = 2026-11-13`, `271.8만 행`) + Node VM 3페이지 E2E 동적 검수 결과**:
  * ✅ **합격 항목 (`AC-25`, `AC-29`, `AC-1 ~ AC-23`)**:
    * `index.html`의 `🟢 추천 / ⚪ 비추천` 3단계 분류 수식, 양봉(윗꼬리·단기과열 포함) 미제외 원칙, `패턴 B(바닥지지 연속수급)` `125일` 일봉 선행 보강 로드(`41종목` 프리로드 → 전 종목 125일 전수 조회 대비 **분류 오차 `0건`, `132 / 132` 100% 일치**), `send_telegram_alert()` `HTTP 400` Plain Text 자동 재전송 폴백, 탭별 9열 `.xlsx` 내보내기(`추천 47행` / `비추천 76행` / `전체 123행`) 및 기존 `AC-1 ~ AC-23` 회귀 무결성은 완벽히 구현되었습니다.
  * 🚨 **필수 수정·조치 필요 항목 (`4건`: `[ISSUE-011]` ~ `[ISSUE-014]`)**:
    1. **`[ISSUE-011]` (`CRITICAL` — 운영 DB RLS 차단 & `42501` 복구 배너 누락 | `AC-24, AC-26, AC-27, AC-28`)**: 운영 Supabase에 생성된 신규 3개 테이블(`excluded_stocks`, `watchlist_items`, `portfolio_holdings`)에 현재 **RLS(Row-Level Security)가 활성화된 상태**여서 `GET`은 빈 배열 `[]`(`200`)만 반환하고, 웹(`anon` 키)에서의 모든 쓰기(`POST/PATCH/DELETE`)가 **`HTTP 401 (code: 42501, new row violates row-level security policy)`** 로 100% 실패합니다. 또한 `common.js`가 `404/PGRST205`만 감지하고 `42501`은 감지하지 않아 상단 원클릭 SQL 복구 배너가 뜨지 않습니다. *(사용자 SQL Editor 1회 실행 SQL + `common.js`/`migration_v24_watchlist_holdings.sql` 동시 보강 필요)*
    2. **`[ISSUE-012]` (`HIGH` — 전략 명세 `7.4절 2항` 위반 | `AC-27`)**: `common.js` [`evaluateWatchlistItem()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L291-L299)이 `recommend_tag === '추세수급'` 조건을 확인하지 않아, 대바닥 예외 승격으로 추천된 **`바닥지지 연속수급` 11종목 중 10종목(`90.9%`)** 과 **`바닥전환 첫수급` 4종목 중 3종목(`75.0%`)** 이 관심종목 병합 당일 즉시 **`⚠️ 60일선 이탈` (`isExit = true`, `[⚠️ 이탈·정리 대상]`)** 로 오판됩니다.
    3. **`[ISSUE-013]` (`HIGH` — 합격 기준 `AC-26` 불충족 | `AC-26`)**: `common.js` [`renderNav()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L441-L442)에서 상단 `🚫 제외관리` 클릭 시 `openExcludedModal()`에 변경 콜백이 연결되지 않아, 모달에서 **`[복구]`**(또는 프리셋·검색 추가)를 눌러도 `index.html`의 `EXCLUDED_SET` 및 화면 리스트가 새로고침 전까지 갱신되지 않습니다. 또한 `7.3절 1항`의 상단 `영구제외 K종목 자동 숨김` 안내 표시와 프리셋 체크박스 선택 기능이 누락되어 있습니다.
    4. **`[ISSUE-014]` (`MEDIUM` — 명세 `7.5절 2항·4항` 불일치 | `AC-28`)**: ① `common.js` [`evaluateHolding()`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L320-L327)의 `tp1Reached`/`tp2Reached`가 명세(`7.5절 2항 5호`: **`현재가`** 기준)와 달리 `매수일 이후 장중 최고가(maxHigh)`를 사용하여 매수 당일 오전 고점이나 현재 손실(`-2%`) 상태에서도 `🎯 1차도달`이 점등되며, ② `holdings.html`에서 `[📜 청산 히스토리]` 종목 클릭 시 일봉 미로드로 **`"차트 데이터 없음"`** 이 표시되고 동일 종목 재매매(`A안`) 시 `shcode` 단일 키(`EVAL[h.shcode]`, `SELECTED`) 충돌이 발생합니다.

---

### 1.1 `v2.4` 신규 합격 기준 (`STRATEGY.md` 7.6절 — `AC-24` ~ `AC-29`) 상세 검수 결과표

| 검증 코드 | 검증 항목 (`STRATEGY.md` 7.6절) | 코드 감사 · 운영 Supabase(`2026-11-13`) · Node VM 3페이지 실증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-24** | **3페이지 독립 분리(`index` · `watchlist` · `holdings`) · 신규 3개 테이블 스키마 · PostgREST 안전 처리 검증** | • `index.html` / `watchlist.html` / `holdings.html` + `common.js` 분리, 상단 4개 내비게이션(`<a href>` 새 탭 호환), DDL(`idx_holdings_active_shcode WHERE status = 'HOLDING'` 부분 고유 인덱스 포함), `Prefer: return=representation` 및 `204 No Content`/빈 본문 안전 파싱(`parseBodySafe`) 정상 작동 확인<br/>• ❌ **차단 이슈 (`[ISSUE-011]`)**: 운영 Supabase의 신규 3개 테이블에 RLS가 켜져 있어 `anon` 키 `POST` 요청이 전부 **`HTTP 401 (code: 42501)`** 로 거부되며, `common.js`가 `42501` 에러 시 SQL 복구 배너/모달을 노출하지 않음 (`GRANT` 구문도 마이그레이션 SQL에 보강 필요) | **FAIL** (`ISSUE-011`) |
| **AC-25** | **`🟢 추천 / ⚪ 비추천` 3단계 자동 분류 수식 및 `125일` 바닥 후보 일봉 보강 검증** | • `Step 1` 공통 비추천(`20일 평균 일중변동폭 < 2.5%` `[저변동]`, `Close < Open` `[음봉마감]`, `Close < EMA 5` `[5일선이탈]`) 경계값 및 **양봉(`Close >= Open`) 윗꼬리·단기과열 미제외 원칙** 정확 동작 확인<br/>• `getStage1ReversalCandidateCodes()`가 `패턴 A` + `패턴 B` 1차 후보(`2026-11-13` 기준 `41종목`)를 모두 추출해 `applyScreening()` 전 `125달력일`(`84영업일`) 일봉을 보강 로드하며, 포착 전 종목(`132종목`) 125일 전수 조회 대비 **분류 오차 `0건`(`100%` 일치)** 실증 완료<br/>• `2026-11-13` 실측: `당일10%` `123종목` = **`🟢 추천 47`** (`추세수급 33` · `바닥지지 연속수급 11` · `바닥전환 첫수급 3`) + **`⚪ 비추천 76`**; `하락추세전환` `4종목` 전원 `🟢 바닥전환 첫수급` 승격 확인 | **PASS** |
| **AC-26** | **`🚫 영구 제외 사전` 차단 · 복구 및 프리셋 도우미 검증** | • 행 우측 `[🚫]` 버튼 제외 시 `EXCLUDED_SET` 반영 및 즉시 숨김은 구현됨<br/>• ❌ **불충족 (`[ISSUE-013]`, `[ISSUE-011]`)**: 상단 `[🚫 제외관리]` 모달(`common.js` 442행)이 `onChange` 콜백 없이 열려 모달에서 **`[복구]` 클릭 시 `index.html` 리스트에 즉시 재노출되지 않음**(`122종목` 고착, F5 필요). 또한 상단 `영구제외 K종목 자동 숨김` 안내 표시 및 업종 프리셋 체크박스 선택 등록 기능(`7.3절 1항`) 누락 | **FAIL** (`ISSUE-011`, `ISSUE-013`) |
| **AC-27** | **`⭐ 스마트 병합` 멱등성 · 기존 관심종목 보호 · 수작업 제외 3종 검증** | • 신규 병합 기준봉 박제, 동일일(`T <= last_signal_date`) 재병합 멱등성(`신규 0 · 재수급 0 · 변경없음 47`), 후속일(`T > last_signal_date`) `signal_count + 1` 및 `grade/memo/stop_price` 보존, **`⚪ 비추천` 기존 관심종목 무삭제·무증가 보호**, 개별/일괄 제외 UI 및 등록 종목 온디맨드 조회(`48종목` 전체 `0.88초`, `2종목` `0.21초`) 정상 확인<br/>• ❌ **전략 위반 (`[ISSUE-012]`)**: `evaluateWatchlistItem()`이 `7.4절 2항`(`일반 추세수급 출신 종목이...`) 조건을 누락하여 **`바닥지지 연속수급(10/11종목)`·`바닥전환 첫수급(3/4종목)` 총 13종목을 병합 당일 즉시 `⚠️ 60일선 이탈`(`isExit = true`, `[⚠️ 이탈·정리 대상]`)로 오분류**함 | **FAIL** (`ISSUE-011`, `ISSUE-012`) |
| **AC-28** | **`💼 보유종목` 목표가(`+5%/+10%`) · 추천 청산가(`20일선`) 연동 및 실제 청산가 수동 입력 히스토리(`A안`) 검증** | • 진입가 `+5%/+10%` 자동 계산, 기준일 $T$ `EMA 20` 추천 청산가·`🚨 20일선 이탈` 경보, 청산 모달 실제 청산가 수작업 입력·실시간 수익률/손익 미리보기, `idx_holdings_active_shcode` 보유중 중복 `409` 차단 & `CLOSED` 전환 후 동일 종목 재매수(`A안`), `[청산 종목 함께 보기]` 토글 및 통산 승률 요약 카드 4종 정상 확인<br/>• ❌ **정합성 결함 (`[ISSUE-014]`)**: ① `tp1Reached`/`tp2Reached`가 명세(`7.5절 2항 5호`: **`현재가`** 이상) 대신 `maxHigh`(`buy_date` 이후 고가)를 써서 손실 상태·당일 오전 고점에서도 `🎯 1차도달` 오점등, ② `[📜 청산 히스토리]` 카드 클릭 시 차트 미로드(`"차트 데이터 없음"`) 및 동일 종목 다회 매매 시 `shcode` 키 충돌 | **FAIL** (`ISSUE-011`, `ISSUE-014`) |
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

### 1.3 기존 요구사항 (`AC-1` ~ `AC-23`) 회귀 검증 요약 (`v2.4` 적용 후 전 항목 PASS 유지)

| 검증 코드 | 검증 항목 요약 | `v2.4` (`9cdfd9a`) 적용 후 회귀 검증 결과 | 최종 판정 |
| :---: | :--- | :--- | :---: |
| **AC-1 ~ AC-18** | 유니버스(`1,463종목`), EMA·순수기관 수식, 4중 배치 Cron, 멱등성 가드, 유동성 제외 필터, 9열 엑셀 | `test_screener_verification.py`(8/8), `test_v2_acceptance.py`(9/9), `--mode verify` 전 항목 오차 `0건` | **PASS** |
| **AC-19 ~ AC-23** | 차트 5년(`1,678,171행`) · 수급 3년(`1,040,512행`) 비대칭 적재, 앵커 EMA, 무지연 PK 조회 | `test_v23_acceptance.py`(19/19), 7종목 `1,233일 / 739일` 범위 및 웹 초기 로드 무결성 정상 유지 | **PASS** |

---

## 2. 버그 및 수정 요청 트래커 (Issue & Fix Tracker)

### 🚨 2.1 `[프로그램 개발 및 수정]` 대화창 필수 수정 요청 사항 (`미해결 4건: ISSUE-011 ~ ISSUE-014`)

---

#### 🔴 `[ISSUE-011]` `[미해결 — CRITICAL]` 운영 Supabase 신규 3개 테이블 RLS 활성화(`HTTP 401 / code 42501`)로 인한 전 쓰기 차단 & `common.js` `42501` 복구 배너 미노출 + 마이그레이션 SQL `GRANT` 보강
* **관련 합격 기준**: `AC-24`, `AC-26`, `AC-27`, `AC-28`, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L700-L705) `7.2절`
* **대상 파일**: [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L77-L92), [`scripts/migration_v24_watchlist_holdings.sql`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/scripts/migration_v24_watchlist_holdings.sql#L76-L81), [`supabase_schema.sql`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/supabase_schema.sql#L276-L279)
* **실측 증상**:
  * 운영 Supabase REST API에 브라우저와 동일한 `sb_publishable_...` 키로 요청 시 `GET`은 `HTTP 200 -> []`을 반환하나, `excluded_stocks` / `watchlist_items` / `portfolio_holdings` 3개 테이블 모두 `POST` 시 아래 에러로 **100% 차단**됩니다:
    ```json
    {"code":"42501","details":null,"hint":null,"message":"new row violates row-level security policy for table \"watchlist_items\""}
    ```
  * 현재 `common.js` 88행(`err.tableMissing = resp.status === 404 || code === "PGRST205" || code === "42P01"`)은 테이블 미생성만 감지하고 `code === "42501"`(RLS 차단 / 권한 부족)은 감지하지 않으며, 초기 `GET`이 `200 []`으로 성공하므로 상단 `테이블 생성 SQL 원클릭 복사` 배너도 표시되지 않습니다.
* **필수 조치 및 코드 수정 방안**:
  1. **[SQL 보강 (`scripts/migration_v24_watchlist_holdings.sql`, `supabase_schema.sql` 동기화 후 `scripts/sync_common_sql.py` 실행)]**:
     * 하단 RLS 비활성화 블록에 명시적 `GRANT` 및 혹시 Supabase Security Advisor 등에서 RLS가 다시 켜지더라도 `anon, authenticated`가 동작할 수 있는 멱등 정책(또는 확실한 `DISABLE ROW LEVEL SECURITY` + `GRANT`)을 함께 수록해 주십시오:
       ```sql
       ALTER TABLE excluded_stocks DISABLE ROW LEVEL SECURITY;
       ALTER TABLE watchlist_items DISABLE ROW LEVEL SECURITY;
       ALTER TABLE portfolio_holdings DISABLE ROW LEVEL SECURITY;

       GRANT ALL ON TABLE excluded_stocks, watchlist_items, portfolio_holdings TO anon, authenticated, service_role;
       GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;

       NOTIFY pgrst, 'reload schema';
       ```
     * *(사용자 안내용 즉시 복구 SQL)*: 사용자께서도 Supabase 대시보드 → **SQL Editor**에서 위 5줄(`ALTER TABLE ... DISABLE ROW LEVEL SECURITY;` + `GRANT ...`)을 붙여넣고 **Run**을 1회 눌러 주시면 운영 DB 쓰기 차단이 즉시 해제됩니다.
  2. **[`common.js` `42501` RLS 차단 감지 및 원클릭 SQL 복구 배너 자동 노출]**:
     * `sbRequest()`(88행)에서 `err.rlsBlocked = (code === "42501" || (resp.status === 401 || resp.status === 403) && /row-level security|permission denied/i.test(err.message));` 를 설정하고, `isSetupRequiredError(err)`(`err.tableMissing || err.rlsBlocked`) 발생 시 `showMissingTableBanner(err)`를 호출하여 **"⚠️ 신규 테이블이 아직 생성되지 않았거나 RLS 쓰기 권한 비활성화 SQL 실행이 필요합니다"** 배너와 **`[복구/생성 SQL 원클릭 복사]`** 버튼을 즉시 노출해 주십시오 (`index.html`, `watchlist.html`, `holdings.html`의 `POST/PATCH/DELETE` catch 블록 모두 포함).

---

#### 🔴 `[ISSUE-012]` `[미해결 — HIGH]` `evaluateWatchlistItem()`이 대바닥 예외 승격 종목(`바닥전환 첫수급` · `바닥지지 연속수급`)까지 `⚠️ 20일선/60일선 이탈`(`isExit = true`)로 오판하는 버그
* **관련 합격 기준**: `AC-27`, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L776) `7.4절 2항` (776행) & `7.4절 3항 ③` (783행)
* **대상 파일**: [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L291-L299), [`tests/test_v24_watchlist_holdings.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/tests/test_v24_watchlist_holdings.py#L155-L173)
* **원인 및 실측 재현**:
  * `STRATEGY.md` 776행은 **`"⚠️ 20일선 이탈 / ⚠️ 60일선 이탈: 일반 추세수급 출신 종목이 Close_T < EMA_{20, T} (또는 Close_T < EMA_{60, T}) 이탈 시 표시"`** 라고 명시하고 있습니다.
  * 대바닥 예외 승격(`Step 2`: `바닥전환 첫수급`, `바닥지지 연속수급`) 종목은 정의상 `EMA 20 < EMA 60 < EMA 120` 역배열 대바닥 구간에서 포착되므로 포착 시점에 주가가 `EMA 60`(및 다수 `EMA 20`) 아래에 위치합니다.
  * 그러나 [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L292-L293)는 `item.recommend_tag` 확인 없이 무조건 `ema20Break = close < ema20`, `ema60Break = close < ema60`으로 계산하여, `2026-11-13` 실데이터 추천 48종목 병합 시 **`바닥지지 연속수급` 11종목 중 10종목(`현대엘리베이터`, `현대백화점`, `HD현대중공업`, `HD건설기계` 등)** 과 **`바닥전환 첫수급` 4종목 중 3종목(`한국피아이엠`, `고영`, `노루홀딩스`)** 총 **13종목이 병합 당일 즉시 `[⚠️ 이탈·정리 대상]`(`isExit = true`)으로 분류**됩니다.
* **구체적 코드 수정 제안 (`common.js` `evaluateWatchlistItem`)**:
  ```javascript
  const isTrendOrigin = String(item.recommend_tag || "") === "추세수급";
  const ema20Break = isTrendOrigin && ema20 > 0 && close < ema20;
  const ema60Break = isTrendOrigin && ema60 > 0 && close < ema60;
  ```
  * 단위 테스트(`test_watchlist_alerts`)에도 `recommend_tag: "추세수급"` 케이스(`ema20Break/ema60Break` 작동)와 `recommend_tag: "바닥전환 첫수급"` / `"바닥지지 연속수급"` 케이스(`close < ema60`이어도 `ema20Break === false && ema60Break === false && isExit === false`, 단 `stopBreak`나 `supplyExit`일 때는 정상 `isExit === true`)를 모두 추가해 주십시오.

---

#### 🟠 `[ISSUE-013]` `[미해결 — HIGH]` `index.html`에서 상단 `[🚫 제외관리]` 모달 복구·추가 시 화면 즉시 재노출 미작동(`AC-26`) + 상단 `영구제외 K종목 자동 숨김` 안내 및 프리셋 체크박스 선택 보완
* **관련 합격 기준**: `AC-26`, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L714-L716) `7.3절 1항` (714·716행) & `7.6절 AC-26` (840행)
* **대상 파일**: [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L441-L540), [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L136-L141) (`#recTabBar`, `applyScreening`, `DOMContentLoaded`)
* **원인 및 실측 재현**:
  1. `common.js` 442행 `renderNav()` 내부에서 `#navExcluded` 클릭 핸들러가 `openExcludedModal()`을 인자 없이 호출하며, `refreshNavCounts()` 호출 시에도 `renderNav()`가 재실행되어 핸들러를 덮어씁니다. 이로 인해 `index.html`에서 `[🚫 제외관리]` 모달을 열어 종목을 **`[복구]`** 하거나 프리셋/검색으로 제외 종목을 추가해도 `EXCLUDED_SET` 갱신과 `applyScreening()` 재호출이 일어나지 않아 **즉시 재노출/제외(`AC-26`)가 작동하지 않습니다**.
  2. `7.3절 1항`(714행)의 리스트 상단 **`영구제외 K종목 자동 숨김`** 안내 표시가 `index.html`에 없습니다.
  3. `7.3절 1항`(716행)의 **`[저변동·규제 업종 프리셋 도우미]`(체크박스 선택 일괄 등록)** 가 현재 체크박스 없이 업종 버튼 클릭 즉시 전 종목 등록 방식으로만 동작합니다.
* **구체적 코드 수정 제안**:
  1. `common.js`에 모듈 수준 콜백(예: `let onExcludedChangeHook = null; function onExcludedChange(fn) { onExcludedChangeHook = fn; }`)을 두고 `openExcludedModal`의 `notify()`에서 `o.onChange`와 `onExcludedChangeHook`을 모두 호출하도록 한 뒤, `index.html` 초기화 시 `C.onExcludedChange(async () => { await loadV24State(); applyScreening(); });`를 등록하십시오.
  2. `index.html` `#recTabBar`에 `<span id="excludedHiddenNotice" class="hidden ..."></span>`을 추가하여, `applyScreening()`에서 `EXCLUDED_SET.size > 0`(또는 전체 제외 건수 > 0)일 때 `🚫 영구제외 K종목 자동 숨김`(클릭 시 제외관리 모달 오픈)을 표시하십시오.
  3. `openExcludedModal()`의 프리셋 영역에서 업종 버튼 클릭 시(또는 기본 펼침으로) 해당 업종 종목들이 체크박스로 나열되고 `[선택 프리셋 종목 일괄 등록]` 버튼으로 등록할 수 있도록 보완해 주십시오.

---

#### 🟡 `[ISSUE-014]` `[미해결 — MEDIUM]` `holdings.html` 목표가 도달 배지 기준(`현재가` vs `maxHigh`) 불일치, `[📜 청산 히스토리]` 클릭 시 차트 미표시 및 동일 종목 재매매(`A안`) 행 선택 충돌
* **관련 합격 기준**: `AC-28`, [`STRATEGY.md`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/STRATEGY.md#L803-L826) `7.5절 2항·4항`
* **대상 파일**: [`common.js`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/common.js#L311-L332), [`holdings.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/holdings.html#L68-L185), [`index.html`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/index.html#L125-L128), [`tests/test_v24_watchlist_holdings.py`](file:///home/antigravity/minseok2995-ai/ls-stock-screener/tests/test_v24_watchlist_holdings.py#L174-L184)
* **원인 및 수정 제안**:
  1. **목표가 도달 배지 기준 (`common.js` 326~327행 & `STRATEGY.md` 809행)**:
     * 명세 809행은 **`"현재가가 1차 목표가 이상이면 🎯 1차도달, 2차 목표가 이상이면 🚀 2차도달 강조 배지 표시"`** 로 정의합니다(과거 부분 익절 실행 여부는 `[1차완료 ✓]`/`[2차완료 ✓]` 토글로 별도 관리). 현재 `maxHigh >= target` 방식은 매수 당일 오전 고점(매수 전 고가)이나 고점 후 하락 손실 구간에서도 `🎯 1차도달`을 띄우므로 `close >= num(h.target_1_price)` 및 `close >= num(h.target_2_price)`로 수정하고 `test_holding_ema20_exit_and_targets` 테스트도 이에 맞춰 갱신해 주십시오.
  2. **`[📜 청산 히스토리]` 차트 로드 및 `id` 기반 선택 (`holdings.html` 68~184행)**:
     * `A안`에서는 동일 `shcode`에 대해 `CLOSED` 여러 건 + `HOLDING` 1건이 공존할 수 있으므로 `EVAL`과 `SELECTED` 키를 `h.shcode` 대신 **`h.id`**(`data-row-id`) 기준으로 관리하고, `CLOSED` 행 카드를 클릭해 `selectRow(id)`가 호출될 때 `CHARTS[h.shcode]`가 아직 없으면 온디맨드로 최근 120일(또는 `buy_date ~ sell_date` 포함 구간) 일봉을 조회해 우측 캔들차트(매수가·청산가·목표가 라인 포함)를 정상 렌더링해 주십시오.
  3. **소폭 UI 정합성 함께 반영 권장**:
     * `holdings.html` 87행 매수일 표시에 경과일(`매수일 YYYY-MM-DD (D+N일)`, `7.5절 2항 2호` 805행)을 병기하고, `index.html`의 `#btnMergeWatchlist` 버튼 라벨에 현재 체크된 종목 건수(`⭐ 선택 종목 관심종목 병합 (N)`, `7.3절 3항` 751행) 및 `#chkAllRows` 체크 상태 동기화를 반영해 주십시오.
     * `common.js` `loadSeriesForCodes`(343행)에서 초장기 보유(`fromDate`가 `T` 대비 1,300달력일 초과) 시 `order=trade_date.asc&limit=1000`으로 인해 최신일 `T` 부근 데이터가 잘리지 않도록 일봉 조회 시작일 하한(또는 1,300일 단위 분할) 안전장치를 추가하면 5년 차트 DB에서도 영구 안전합니다.

---

### ✅ 2.2 해결 완료된 이슈 히스토리 아카이브

* **[v2.3.1 검증 완료 (`353f92a`, `Run #43682739754` & `Run #43685346608`)]** 차트 5년(`2021-11-01~`, `1,678,171행`) · 수급 3년(`2023-11-01~`, `1,040,512행`) 비대칭 확장 백필 1회차 `2시간 44분` 100% 완주, 앵커 시드 EMA 연속성, 거래정지 `25종목` 미확정 오판 차단, `80분` 주기 토큰 자동 갱신 및 `271.8만 행` 대용량 DB 무지연(`AC-19 ~ AC-23`) 전 항목 합격.
* **[v2.2 검증 완료 (`6bfbbd5`)]** `[기관 수급 발생 종목]` 유동성·수급금액 제외 필터(`당일 기준` vs `3일 연속 3일 평균 기준`) 및 `[엑셀 저장]` 9개 컬럼 개편(`AC-16 ~ AC-18`) 전 항목 합격.
* **[v2.1 검증 완료 (`1aecd41`)]** `20:30 KST` 다중 백업 Cron, `KST` 표준시 고정, `--skip-if-completed` 멱등성 가드(`< 2.3초` 종료), `if: failure()` 장애 알림, Apps Script 외부 정각 웹훅(`AC-13 ~ AC-15`) 및 `두산에너빌리티(034020)` 백필 자동 복구 확인 완료.
* **[ISSUE-006 ~ ISSUE-010] `[해결 완료 (v1.4.3 ~ v2.0)]`** `PRIORITY_SHCODES` 제거, `has_2yr_history` 판정 분리, 장중 미확정 수급 차단, 복합 PK 병렬 조회 전환(`HTTP 500` 해소), `AC-1 ~ AC-12` 검증 체계 구축 완료.
* **[ISSUE-001 ~ ISSUE-005] `[해결 완료 (v1.4)]`** 1,463종목 시총 ≥ 700억 전수 유니버스 구축, 일봉·수급 500영업일 역순 슬라이딩 적재, Actions 360분 타임아웃 상향 완료.
