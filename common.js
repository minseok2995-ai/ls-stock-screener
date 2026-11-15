/* =========================================================================
 * common.js — v2.4 (STRATEGY.md 7절) 3페이지 공통 모듈
 *   index.html(수급 스크리너) / watchlist.html(관심종목) / holdings.html(보유종목)
 *  - PostgREST 안전 통신 헬퍼 (Prefer: return=representation, HTTP 204/빈 본문 JSON.parse 예외 방지)
 *  - 추천/비추천 3단계 분류, 관심종목 스마트 병합, 목표가/청산 계산 등 순수 함수 (Node 테스트 가능)
 *  - 공통 내비게이션, 테이블 미생성 Graceful Fallback 배너 + SQL 복사 모달, 제외관리 모달, 캔들 차트
 * ========================================================================= */
(function (root) {
  "use strict";

  const SUPABASE_URL = "https://rwvvrtjsxzecmdykwrxg.supabase.co";
  const SUPABASE_KEY = "sb_publishable_vH_-2K-y5HwQ9oqiT1gtIw_P9pKdJ26";

  // v2.4 마이그레이션 SQL (scripts/migration_v24_watchlist_holdings.sql 과 동일 — 테스트가 일치 검증)
  const MIGRATION_SQL = "-- =====================================================================\n-- v2.4 마이그레이션: 영구제외 · 관심종목 · 보유종목(청산 히스토리) 테이블 3종\n-- Supabase 대시보드 > SQL Editor 에 전체를 붙여넣고 [Run] 한 번으로 실행하세요.\n-- (기존 stocks_master / daily_chart / daily_investor_supply 는 변경하지 않으며, 여러 번 실행해도 안전합니다)\n-- =====================================================================\n\n-- 5. 영구 제외 종목 사전 (은행·전력·통신 등 사용자 비선호/저변동 상단막힘 종목 영구 차단)\nCREATE TABLE IF NOT EXISTS excluded_stocks (\n    shcode VARCHAR(6) PRIMARY KEY,              -- 종목코드 (6자리)\n    hname VARCHAR(100) NOT NULL,                -- 종목명\n    market VARCHAR(10) DEFAULT '',              -- 시장구분 (KOSPI / KOSDAQ)\n    reason_tag VARCHAR(40) DEFAULT '비선호/저변동', -- 제외 사유 태그 (은행/금융, 공기업/유틸리티, 저변동/상단막힘, 기타)\n    memo TEXT DEFAULT '',                       -- 사용자 메모\n    created_at TIMESTAMPTZ DEFAULT NOW()\n);\n\n-- 6. 통합 관심종목군 (당일 수급 스마트 병합 + 재수급 횟수 누적 + 최종 진입대기 등급 관리)\nCREATE TABLE IF NOT EXISTS watchlist_items (\n    id BIGSERIAL PRIMARY KEY,\n    shcode VARCHAR(6) NOT NULL UNIQUE,          -- 활성 관심종목 종목코드 고유 제약\n    hname VARCHAR(100) NOT NULL,\n    market VARCHAR(10) DEFAULT '',\n    grade VARCHAR(20) NOT NULL DEFAULT 'B_WATCH', -- 'A_READY' (최우선 진입대기) | 'B_WATCH' (일반 관찰)\n    first_signal_date DATE NOT NULL,            -- 최초 포착 기준일 (박제)\n    first_signal_close INTEGER NOT NULL,        -- 최초 포착일 종가 (박제)\n    first_signal_low INTEGER NOT NULL,          -- 최초 포착일 저가 (기준봉 손절 기준선, 박제)\n    first_inst_ratio NUMERIC(8, 2) DEFAULT 0,   -- 최초 포착일 순수기관 비중 (%)\n    first_inst_amt NUMERIC(14, 2) DEFAULT 0,    -- 최초 포착일 순수기관 순매수 금액 (백만원)\n    last_signal_date DATE NOT NULL,             -- 가장 최근 수급 병합 기준일\n    last_inst_ratio NUMERIC(8, 2) DEFAULT 0,    -- 최근 병합일 순수기관 비중 (%)\n    last_inst_amt NUMERIC(14, 2) DEFAULT 0,     -- 최근 병합일 순수기관 순매수 금액 (백만원)\n    signal_count INTEGER NOT NULL DEFAULT 1,    -- 누적 수급 포착(병합) 횟수 (1회, 2회, 3회...)\n    recommend_tag VARCHAR(40) DEFAULT '',       -- 포착 유형 ('추세수급', '바닥전환 첫수급', '바닥지지 연속수급', '수동등록')\n    signal_mode VARCHAR(40) DEFAULT '',         -- 포착 당시 옵션 ('당일10%', '당일15%', '당일20%', '3일연속5%', '하락추세전환', '직접추가')\n    target_entry_price INTEGER,                 -- 사용자 희망 진입가 (선택)\n    stop_price INTEGER,                         -- 사용자 지정 손절가 (기본값: first_signal_low)\n    memo TEXT DEFAULT '',\n    created_at TIMESTAMPTZ DEFAULT NOW(),\n    updated_at TIMESTAMPTZ DEFAULT NOW()\n);\n\nCREATE INDEX IF NOT EXISTS idx_watchlist_grade_last_date\n    ON watchlist_items (grade ASC, last_signal_date DESC);\n\n-- 7. 보유종목 및 청산 매매 히스토리 (A안: 보유중 종목당 1행 고유 + 청산 완료 건별 영구 누적)\nCREATE TABLE IF NOT EXISTS portfolio_holdings (\n    id BIGSERIAL PRIMARY KEY,\n    shcode VARCHAR(6) NOT NULL,\n    hname VARCHAR(100) NOT NULL,\n    market VARCHAR(10) DEFAULT '',\n    status VARCHAR(16) NOT NULL DEFAULT 'HOLDING', -- 'HOLDING' (현재 보유중) | 'CLOSED' (전량 청산 완료)\n    buy_date DATE NOT NULL,                     -- 최초 진입(매수)일\n    avg_buy_price NUMERIC(14, 2) NOT NULL,      -- 진입 평균매수가 (원)\n    quantity BIGINT,                            -- 보유 수량 (주, 선택 입력 — NULL 허용)\n    target_1_price INTEGER NOT NULL,            -- 1차 목표가 (기본값: 진입가의 +5% 반올림, 수정 가능)\n    target_2_price INTEGER NOT NULL,            -- 2차 목표가 (기본값: 진입가의 +10% 반올림, 수정 가능)\n    tp1_done BOOLEAN NOT NULL DEFAULT FALSE,    -- 1차 목표 익절 실행 체크 표시 (수량 분할 입력 불필요)\n    tp2_done BOOLEAN NOT NULL DEFAULT FALSE,    -- 2차 목표 익절 실행 체크 표시\n    entry_source_tag VARCHAR(40) DEFAULT '',    -- 출신 전략 태그 보존 ('추세수급', '바닥전환 첫수급', '바닥지지 연속수급' 등)\n    memo TEXT DEFAULT '',                       -- 매매/복기 메모\n    sell_date DATE,                             -- 최종 전량 청산일 ('CLOSED' 전환 시 기록)\n    avg_sell_price NUMERIC(14, 2),              -- 최종 실제 평균 청산가 (사용자가 수작업 직접 입력!)\n    realized_return_pct NUMERIC(8, 2),          -- 최종 실현 수익률 (%) = ((avg_sell_price - avg_buy_price) / avg_buy_price) * 100\n    realized_pnl_krw BIGINT,                    -- 최종 실현 손익금 (원, quantity 입력 시 자동 계산)\n    close_reason VARCHAR(50) DEFAULT '',        -- 청산 사유 ('목표가 익절', '20일선 이탈 청산', '수급이탈 정리', '수동 청산' 등)\n    created_at TIMESTAMPTZ DEFAULT NOW(),\n    updated_at TIMESTAMPTZ DEFAULT NOW()\n);\n\n-- 현재 보유중('HOLDING') 상태에서는 동일 종목 중복 등록 차단, 청산('CLOSED') 후 재매매 시 신규 행 허용!\nCREATE UNIQUE INDEX IF NOT EXISTS idx_holdings_active_shcode\n    ON portfolio_holdings (shcode) WHERE status = 'HOLDING';\n\nCREATE INDEX IF NOT EXISTS idx_holdings_status_dates\n    ON portfolio_holdings (status, buy_date DESC, sell_date DESC);\n\nALTER TABLE excluded_stocks DISABLE ROW LEVEL SECURITY;\nALTER TABLE watchlist_items DISABLE ROW LEVEL SECURITY;\nALTER TABLE portfolio_holdings DISABLE ROW LEVEL SECURITY;\n\n-- [ISSUE-011] anon(웹 publishable 키) 쓰기 권한 명시 부여 (RLS 재활성화/권한 누락 대비)\nGRANT ALL ON TABLE excluded_stocks, watchlist_items, portfolio_holdings TO anon, authenticated, service_role;\nGRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;\n\n-- PostgREST 스키마 캐시 즉시 갱신 (신규 테이블이 REST API 에 바로 노출되도록)\nNOTIFY pgrst, 'reload schema';\n";

  const CHART_COLS = "shcode,trade_date,open,high,low,close,change_rate,volume,trading_value_m,ema_5,ema_20,ema_60,ema_120,ema_240";
  const SUPPLY_COLS = "shcode,trade_date,real_inst_vol,real_inst_amt,inst_vol_ratio,frg_vol,ind_vol";

  // 영구제외 업종 프리셋 (종목코드 기준, 이름은 stocks_master 에서 확인 / 미존재 시 프리셋 이름 사용)
  const EXCLUDE_PRESETS = {
    "은행/금융": [["105560", "KB금융"], ["055550", "신한지주"], ["086790", "하나금융지주"], ["316140", "우리금융지주"],
      ["024110", "기업은행"], ["138930", "BNK금융지주"], ["175330", "JB금융지주"], ["139130", "iM금융지주"]],
    "보험": [["032830", "삼성생명"], ["000810", "삼성화재"], ["005830", "DB손해보험"], ["001450", "현대해상"],
      ["088350", "한화생명"], ["138040", "메리츠금융지주"], ["003690", "코리안리"]],
    "공기업/유틸리티(전력·가스)": [["015760", "한국전력"], ["036460", "한국가스공사"], ["071320", "지역난방공사"], ["052690", "한전기술"]],
    "통신": [["017670", "SK텔레콤"], ["030200", "KT"], ["032640", "LG유플러스"]]
  };

  // ------------------------------------------------------------------ 공통 유틸
  function esc(str) {
    return String(str == null ? "" : str)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function round2(x) { return Math.round(Number(x) * 100) / 100; }
  function num(x) { const n = Number(x); return Number.isFinite(n) ? n : 0; }
  function fmtInt(x) { return Math.round(num(x)).toLocaleString("ko-KR"); }

  function todayKst() {
    const d = new Date(Date.now() + 9 * 3600 * 1000);
    return d.toISOString().slice(0, 10);
  }
  function addDays(dateStr, days) {
    const d = new Date(dateStr + "T00:00:00Z");
    d.setUTCDate(d.getUTCDate() + days);
    return d.toISOString().slice(0, 10);
  }

  // ------------------------------------------------------------------ PostgREST 안전 통신
  let fetchImpl = null;
  function setFetch(fn) { fetchImpl = fn; }
  function doFetch(url, init) {
    const f = fetchImpl || (typeof root.fetch === "function" ? root.fetch.bind(root) : null);
    if (!f) throw new Error("fetch 를 사용할 수 없습니다.");
    return f(url, init);
  }

  function baseHeaders(prefer) {
    const h = {
      "apikey": SUPABASE_KEY,
      "Authorization": "Bearer " + SUPABASE_KEY,
      "Content-Type": "application/json"
    };
    if (prefer) h["Prefer"] = prefer;
    return h;
  }

  // 본문을 text() 로 읽어 빈 본문/204 에서도 JSON.parse 예외가 나지 않도록 방어
  async function parseBodySafe(resp) {
    let text = "";
    try { text = await resp.text(); } catch (e) { text = ""; }
    if (resp.status === 204 || !text || !String(text).trim()) return null;
    try { return JSON.parse(text); } catch (e) { return null; }
  }

  async function sbRequest(method, path, opts) {
    const o = opts || {};
    const init = { method, headers: baseHeaders(o.prefer) };
    if (o.body !== undefined) init.body = JSON.stringify(o.body);
    const resp = await doFetch(SUPABASE_URL + "/rest/v1/" + path, init);
    const data = await parseBodySafe(resp);
    if (!resp.ok) {
      const code = data && data.code ? String(data.code) : "";
      const err = new Error("HTTP " + resp.status + (data && data.message ? " " + data.message : ""));
      err.status = resp.status;
      err.code = code;
      err.tableMissing = resp.status === 404 || code === "PGRST205" || code === "42P01";
      // [ISSUE-011] RLS 차단 / 권한 부족(42501) 감지 → 설정 SQL 복구 배너 대상
      err.rlsBlocked = code === "42501" ||
        ((resp.status === 401 || resp.status === 403) && /row-level security|permission denied/i.test(err.message));
      if (err.rlsBlocked && method !== "GET" && typeof document !== "undefined") showMissingTableBanner();
      throw err;
    }
    return { status: resp.status, data, headers: resp.headers };
  }

  async function sbGet(path) {
    const r = await sbRequest("GET", path);
    return Array.isArray(r.data) ? r.data : [];
  }
  async function sbPost(table, rows) {
    const r = await sbRequest("POST", table, { body: rows, prefer: "return=representation" });
    return Array.isArray(r.data) ? r.data : [];
  }
  async function sbUpsert(table, rows, onConflict) {
    const q = onConflict ? table + "?on_conflict=" + encodeURIComponent(onConflict) : table;
    const r = await sbRequest("POST", q, { body: rows, prefer: "resolution=merge-duplicates,return=representation" });
    return Array.isArray(r.data) ? r.data : [];
  }
  async function sbPatch(path, patch) {
    const r = await sbRequest("PATCH", path, { body: patch, prefer: "return=representation" });
    return Array.isArray(r.data) ? r.data : [];
  }
  async function sbDelete(path) {
    const r = await sbRequest("DELETE", path, { prefer: "return=representation" });
    return Array.isArray(r.data) ? r.data : [];
  }
  // 총 건수 (Prefer: count=exact + Content-Range)
  async function sbCount(table, filter) {
    const path = table + "?select=shcode&limit=1" + (filter ? "&" + filter : "");
    const resp = await doFetch(SUPABASE_URL + "/rest/v1/" + path, {
      method: "GET", headers: baseHeaders("count=exact")
    });
    await parseBodySafe(resp);
    if (!resp.ok) {
      const err = new Error("HTTP " + resp.status);
      err.status = resp.status;
      err.tableMissing = resp.status === 404;
      throw err;
    }
    const cr = resp.headers && resp.headers.get ? resp.headers.get("content-range") : "";
    const m = /\/(\d+)$/.exec(cr || "");
    return m ? Number(m[1]) : 0;
  }

  // ------------------------------------------------------------------ 순수 로직: 추천/비추천 3단계 분류 (7.3절)
  function avgIntradayRange20(cList) {
    const tail = cList.slice(-20);
    let sum = 0, n = 0;
    tail.forEach(c => {
      const lo = num(c.low), hi = num(c.high);
      if (lo > 0) { sum += (hi - lo) / lo * 100; n++; }
    });
    return n ? sum / n : 0;
  }

  function consec5pDaysOf(sList) {
    let cnt = 0;
    for (let i = sList.length - 1; i >= 0; i--) {
      if (num(sList[i].inst_vol_ratio) >= 5.0) cnt++; else break;
    }
    return cnt;
  }

  function isReverseAligned(c) {
    const e20 = num(c && c.ema_20), e60 = num(c && c.ema_60), e120 = num(c && c.ema_120);
    return e20 > 0 && e60 > 0 && e120 > 0 && e20 < e60 && e60 < e120;
  }

  // 🌱 패턴 B (바닥지지 연속수급) — 4개 조건 모두 충족
  function isBottomSupportPattern(cList, sList) {
    const n = cList.length;
    const t = n - 1;
    if (t < 60) return false;
    if (!isReverseAligned(cList[t - 1])) return false;
    let maxHigh = -Infinity;
    for (let k = 1; k <= 60; k++) maxHigh = Math.max(maxHigh, num(cList[t - k].high));
    if (!(maxHigh > 0)) return false;
    const minClose2 = Math.min(num(cList[t - 1].close), num(cList[t].close));
    if (!((minClose2 / maxHigh - 1) * 100 <= -15.0)) return false;
    let recentLow = Infinity, priorLow = Infinity;
    for (let k = 0; k <= 4; k++) recentLow = Math.min(recentLow, num(cList[t - k].low));
    for (let k = 5; k <= 19; k++) priorLow = Math.min(priorLow, num(cList[t - k].low));
    if (!(recentLow >= priorLow)) return false;
    return consec5pDaysOf(sList) >= 2;
  }

  // ------------------------------------------------------------------ 순수 로직: 관심종목 스마트 병합 (7.3절 4항)
  // selected: [{shcode,hname,market,close,low,instRatioT,instAmtM_T,recommended,tag,signalMode}]
  // existingMap: { shcode: watchlist_row }
  function planWatchlistMerge(selected, existingMap, T) {
    const inserts = [], updates = [], untouched = [];
    (selected || []).forEach(s => {
      const ex = existingMap ? existingMap[s.shcode] : null;
      if (!ex) {
        inserts.push({
          shcode: s.shcode, hname: s.hname, market: s.market || "",
          grade: "B_WATCH",
          first_signal_date: T, first_signal_close: Math.round(num(s.close)), first_signal_low: Math.round(num(s.low)),
          first_inst_ratio: round2(s.instRatioT), first_inst_amt: round2(s.instAmtM_T),
          last_signal_date: T, last_inst_ratio: round2(s.instRatioT), last_inst_amt: round2(s.instAmtM_T),
          signal_count: 1,
          recommend_tag: s.tag || (s.recommended ? "추세수급" : "수동등록"),
          signal_mode: s.signalMode || "",
          stop_price: Math.round(num(s.low))
        });
        return;
      }
      if (s.recommended && T > String(ex.last_signal_date)) {
        updates.push({
          shcode: s.shcode,
          patch: {
            signal_count: num(ex.signal_count) + 1,
            last_signal_date: T,
            last_inst_ratio: round2(s.instRatioT),
            last_inst_amt: round2(s.instAmtM_T),
            updated_at: new Date().toISOString()
          }
        });
        return;
      }
      untouched.push(s.shcode); // ⚪ 비추천 / 같은 기준일 재병합: 삭제·증가 없음(멱등)
    });
    return { inserts, updates, untouched };
  }

  // ------------------------------------------------------------------ 순수 로직: 목표가 / 청산 / 수익률
  function calcTargets(entry) {
    const e = num(entry);
    return { target1: Math.round(e * 1.05), target2: Math.round(e * 1.10) };
  }
  function calcRealizedReturn(buy, sell) {
    const b = num(buy);
    if (!(b > 0)) return 0;
    return round2((num(sell) - b) / b * 100);
  }
  function calcPnl(buy, sell, qty) {
    if (qty === null || qty === undefined || qty === "" || !(num(qty) > 0)) return null;
    return Math.round((num(sell) - num(buy)) * num(qty));
  }
  function summarizeClosed(rows) {
    const closed = (rows || []).filter(r => r && r.status === "CLOSED");
    const count = closed.length;
    const wins = closed.filter(r => num(r.realized_return_pct) > 0).length;
    const sumRet = closed.reduce((a, r) => a + num(r.realized_return_pct), 0);
    const totalPnl = closed.reduce((a, r) => a + num(r.realized_pnl_krw), 0);
    return {
      count, wins,
      winRate: count ? round2(wins / count * 100) : 0,
      avgReturn: count ? round2(sumRet / count) : 0,
      totalPnl
    };
  }

  // 종가·EMA 시계열 기반 보조 계산
  function lastUpTo(list, T) {
    let i = list.length - 1;
    while (i >= 0 && T && list[i].trade_date > T) i--;
    return i;
  }

  // 관심종목 평가 (7.4절)
  function evaluateWatchlistBase(item, cList, sList, T) {
    const idx = lastUpTo(cList || [], T);
    if (idx < 0) return null;
    const c = cList[idx];
    const close = num(c.close);
    const prev = idx > 0 ? num(cList[idx - 1].close) : close;
    const chg = prev > 0 ? (close / prev - 1) * 100 : 0;
    const firstClose = num(item.first_signal_close);
    const retSince = firstClose > 0 ? (close / firstClose - 1) * 100 : 0;
    let postAmt = 0;
    (sList || []).forEach(s => {
      if (s.trade_date > item.first_signal_date && (!T || s.trade_date <= T)) postAmt += num(s.real_inst_amt);
    });
    const firstAmt = num(item.first_inst_amt);
    const stop = num(item.stop_price);
    const supplyExit = firstAmt > 0 && postAmt <= -0.7 * firstAmt;
    const stopBreak = stop > 0 && close < stop;
    const ema5 = num(c.ema_5), ema20 = num(c.ema_20), ema60 = num(c.ema_60);
    // [ISSUE-012] 7.4절 2항: 20/60일선 이탈 배지는 일반 추세수급 출신 종목에만 적용
    const tagStr = String(item.recommend_tag || "").trim();
    const isBottomOrigin = /바닥|역H&S/.test(tagStr);
    const isTrendOrigin = tagStr.length > 0 && !isBottomOrigin;
    const ema20Break = isTrendOrigin && ema20 > 0 && close < ema20;
    const ema60Break = isTrendOrigin && ema60 > 0 && close < ema60;
    const reSignal = item.last_signal_date === T && num(item.signal_count) >= 2;
    const dist = ema => (ema > 0 ? (close / ema - 1) * 100 : null);
    const inBand = d => d !== null && d >= -1.0 && d <= 2.5;
    const pullback5 = inBand(dist(ema5)), pullback20 = inBand(dist(ema20));
    const pullback = !stopBreak && !supplyExit && (pullback5 || pullback20);
    const isExit = supplyExit || stopBreak || ema20Break || ema60Break;
    return {
      close, change: chg, retSince, postAmtM: postAmt, postAmtEok: postAmt / 100,
      isNewToday: item.first_signal_date === T,
      supplyExit, stopBreak, ema20Break, ema60Break, reSignal,
      pullback, pullbackTag: pullback20 ? "20일선" : (pullback5 ? "5일선" : ""),
      isExit, isTodaySetup: pullback || reSignal,
      ema5, ema20, ema60
    };
  }

  // 보유종목 평가 (7.5절)
  function evaluateHolding(h, cList, sList, T) {
    const idx = lastUpTo(cList || [], T);
    if (idx < 0) return null;
    const c = cList[idx];
    const close = num(c.close);
    const buy = num(h.avg_buy_price);
    const ret = buy > 0 ? (close - buy) / buy * 100 : 0;
    const pnl = calcPnl(buy, close, h.quantity);
    let postAmt = 0;
    (sList || []).forEach(s => { if (s.trade_date >= h.buy_date && (!T || s.trade_date <= T)) postAmt += num(s.real_inst_amt); });
    const ema20 = num(c.ema_20);
    return {
      close, ret: round2(ret), pnl,
      // [ISSUE-014] 7.5절 2항: 현재가(기준일 종가) 기준 도달 판정
      tp1Reached: num(h.target_1_price) > 0 && close >= num(h.target_1_price),
      tp2Reached: num(h.target_2_price) > 0 && close >= num(h.target_2_price),
      ema20, ema20ExitPrice: Math.round(ema20),
      ema20Break: ema20 > 0 && close < ema20,
      postAmtEok: postAmt / 100
    };
  }

  // 요청당 1,000행 미만이 되도록 종목 코드 청크 크기 산정 (달력일 기준 영업일 ≈ 5/7 + 여유)
  function chunkCodesForRange(codes, calendarDays) {
    const perCode = Math.max(1, Math.ceil(calendarDays * 5 / 7) + 2);
    const size = Math.max(1, Math.floor(950 / perCode));
    const out = [];
    for (let i = 0; i < codes.length; i += size) out.push(codes.slice(i, i + size));
    return out;
  }

  async function loadSeriesForCodes(table, codes, fromDate, toDate) {
    const cols = table === "daily_chart" ? CHART_COLS : SUPPLY_COLS;
    const out = {};
    codes.forEach(c => { out[c] = []; });
    // 초장기 구간은 1,300달력일 단위로 분할 (요청당 1,000행 제한으로 최신일이 잘리지 않도록)
    const jobs = [];
    let segStart = fromDate;
    while (segStart <= toDate) {
      const segEndCand = addDays(segStart, 1299);
      const segEnd = segEndCand < toDate ? segEndCand : toDate;
      const days = Math.max(1, Math.round((new Date(segEnd) - new Date(segStart)) / 86400000) + 1);
      chunkCodesForRange(codes, days).forEach(ch => jobs.push({ ch, s: segStart, e: segEnd }));
      segStart = addDays(segEnd, 1);
    }
    const results = await Promise.all(jobs.map(j => sbGet(
      table + "?shcode=in.(" + j.ch.join(",") + ")&and=(trade_date.gte." + j.s + ",trade_date.lte." + j.e + ")" +
      "&select=" + cols + "&order=shcode.asc,trade_date.asc&limit=1000"
    )));
    results.forEach(rows => rows.forEach(r => { if (out[r.shcode]) out[r.shcode].push(r); }));
    codes.forEach(c => out[c].sort((a, b) => String(a.trade_date).localeCompare(String(b.trade_date))));
    return out;
  }

  // 최신 확정 수급 기준일 (index.html 과 동일: 대표 10종목, 장중 미확정(전 주체 0) 행 제외)
  async function fetchLatestTradeDate() {
    try {
      const rows = await sbGet("daily_investor_supply?shcode=in.(005930,000660,005380,012450,196170,006650,023160,218410,166090,009420)" +
        "&or=(real_inst_vol.neq.0,frg_vol.neq.0,ind_vol.neq.0,fn_inv_vol.neq.0)&select=shcode,trade_date&order=trade_date.desc&limit=30");
      if (rows.length) return rows.reduce((m, r) => (r.trade_date > m ? r.trade_date : m), rows[0].trade_date);
    } catch (e) { /* fallthrough */ }
    return todayKst();
  }

  // ------------------------------------------------------------------ UI: 모달 / 배너 / 내비게이션
  function openModal(innerHtml, widthClass) {
    const overlay = document.createElement("div");
    overlay.className = "fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4";
    overlay.innerHTML = '<div class="w-full ' + (widthClass || "max-w-xl") +
      ' max-h-[88vh] overflow-y-auto rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-xl text-xs">' +
      innerHtml + "</div>";
    overlay.addEventListener("click", e => { if (e.target === overlay) overlay.remove(); });
    document.body.appendChild(overlay);
    return { el: overlay, close: () => overlay.remove() };
  }

  async function copyText(text) {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) { await navigator.clipboard.writeText(text); return true; }
    } catch (e) { /* fallthrough */ }
    const ta = document.createElement("textarea");
    ta.value = text; document.body.appendChild(ta); ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    ta.remove();
    return ok;
  }

  function openMigrationSqlModal() {
    const m = openModal(
      '<div class="flex items-center justify-between mb-2"><h3 class="text-sm font-bold">🛠️ v2.4 테이블 생성 SQL</h3>' +
      '<button type="button" data-act="close" class="px-2 py-1 rounded border border-[var(--border)]">닫기</button></div>' +
      '<p class="text-[var(--muted-foreground)] mb-2">Supabase 대시보드 → SQL Editor 에 붙여넣고 Run 을 한 번 실행하세요. (여러 번 실행해도 안전)</p>' +
      '<textarea readonly rows="14" class="w-full font-mono text-[11px] rounded border border-[var(--border)] bg-[var(--background)] p-2">' + esc(MIGRATION_SQL) + "</textarea>" +
      '<div class="mt-2 flex gap-2"><button type="button" data-act="copy" class="px-3 py-1.5 rounded bg-emerald-500 text-slate-950 font-semibold">📋 SQL 원클릭 복사</button>' +
      '<span data-role="msg" class="self-center text-emerald-400"></span></div>', "max-w-3xl");
    m.el.querySelector('[data-act="close"]').onclick = m.close;
    m.el.querySelector('[data-act="copy"]').onclick = async () => {
      const ok = await copyText(MIGRATION_SQL);
      m.el.querySelector('[data-role="msg"]').textContent = ok ? "복사되었습니다." : "복사 실패 — 직접 선택해 복사하세요.";
    };
  }

  // 신규 테이블 미생성(404/PGRST205) 시 상단 안내 배너. 스크리닝은 계속 동작해야 함.
  function showMissingTableBanner() {
    if (typeof document === "undefined") return;
    let box = document.getElementById("commonBanner");
    if (!box) {
      box = document.createElement("div");
      box.id = "commonBanner";
      const nav = document.getElementById("commonNav");
      if (nav && nav.parentNode) nav.parentNode.insertBefore(box, nav.nextSibling);
      else document.body.prepend(box);
    }
    box.innerHTML = '<div class="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-2.5 text-xs text-amber-300 flex items-center justify-between gap-3 mb-3">' +
      '<div>⚠️ 신규 테이블이 아직 생성되지 않았거나 RLS 쓰기 권한 비활성화 SQL 실행이 필요합니다. 스크리닝은 정상 동작하며, 해당 기능은 SQL 실행 후 사용할 수 있습니다.</div>' +
      '<button type="button" id="btnShowMigrationSql" class="px-3 py-1 rounded bg-amber-500/20 border border-amber-500/40 font-semibold shrink-0">테이블 생성/복구 SQL 원클릭 복사</button></div>';
    const btn = document.getElementById("btnShowMigrationSql");
    if (btn) btn.onclick = openMigrationSqlModal;
  }

  function isTableMissingError(err) { return !!(err && (err.tableMissing || err.rlsBlocked)); }

  async function renderNav(active) {
    const nav = document.getElementById("commonNav");
    if (!nav) return;
    const items = [
      ["index", "index.html", "🔍 수급 스크리너", null],
      ["watchlist", "watchlist.html", "⭐ 관심종목", "watchlist_items"],
      ["holdings", "holdings.html", "💼 보유종목", "portfolio_holdings"]
    ];
    const cls = on => "px-3 py-1.5 rounded-lg text-xs font-semibold border transition " +
      (on ? "border-emerald-500/50 bg-emerald-500 text-slate-950" : "border-[var(--border)] bg-[var(--card)] hover:bg-[var(--secondary)]");
    nav.className = "flex flex-wrap items-center gap-2 mb-3";
    nav.innerHTML = items.map(it =>
      '<a href="' + it[1] + '" data-nav="' + it[0] + '" class="' + cls(it[0] === active) + '">' +
      '<span>' + it[2] + '</span><span data-count="' + it[0] + '"></span></a>').join("") +
      '<a href="#" id="navExcluded" class="' + cls(false) + '"><span>🚫 제외관리</span><span data-count="excluded"></span></a>';
    const ex = document.getElementById("navExcluded");
    if (ex) ex.onclick = e => { e.preventDefault(); openExcludedModal(); };
    const jobs = [
      ["watchlist", "watchlist_items", ""],
      ["holdings", "portfolio_holdings", "status=eq.HOLDING"],
      ["excluded", "excluded_stocks", ""]
    ];
    let missing = false;
    await Promise.all(jobs.map(async j => {
      try {
        const n = await sbCount(j[1], j[2]);
        const el = nav.querySelector('[data-count="' + j[0] + '"]');
        if (el) el.textContent = " (" + n + ")";
        if (j[0] === "excluded") root.__LS_EXCLUDED_COUNT = n;
      } catch (e) { if (isTableMissingError(e)) missing = true; }
    }));
    if (missing) showMissingTableBanner();
    return !missing;
  }

  async function refreshNavCounts() {
    const active = document.querySelector("#commonNav a[class*='bg-emerald-500']");
    return renderNav(active ? active.getAttribute("data-nav") : "");
  }

  // ------------------------------------------------------------------ 영구 제외 (excluded_stocks)
  async function loadExcludedSet() {
    try {
      const rows = await sbGet("excluded_stocks?select=shcode,hname,market,reason_tag,memo&order=created_at.desc&limit=1000");
      return { ok: true, rows, set: new Set(rows.map(r => r.shcode)) };
    } catch (e) {
      if (isTableMissingError(e)) showMissingTableBanner();
      return { ok: false, rows: [], set: new Set(), missing: isTableMissingError(e) };
    }
  }

  async function addExcluded(list, reason) {
    const rows = list.map(s => ({ shcode: s.shcode, hname: s.hname, market: s.market || "", reason_tag: reason || "기타" }));
    if (!rows.length) return [];
    return sbUpsert("excluded_stocks", rows, "shcode");
  }
  async function removeExcluded(shcode) {
    return sbDelete("excluded_stocks?shcode=eq." + encodeURIComponent(shcode));
  }

  async function lookupMasters(codes) {
    if (!codes.length) return [];
    try { return await sbGet("stocks_master?shcode=in.(" + codes.join(",") + ")&select=shcode,hname,market"); }
    catch (e) { return []; }
  }

  // [ISSUE-013] 내비게이션의 제외관리 모달 변경 시 각 페이지가 화면을 갱신하도록 하는 전역 훅
  let onExcludedChangeHook = null;
  function onExcludedChange(fn) { onExcludedChangeHook = fn; }

  // opts.onChange: 변경 후 콜백
  async function openExcludedModal(opts) {
    const o = opts || {};
    const m = openModal(
      '<div class="flex items-center justify-between mb-2"><h3 class="text-sm font-bold">🚫 영구 제외 사전 관리</h3>' +
      '<button type="button" data-act="close" class="px-2 py-1 rounded border border-[var(--border)]">닫기</button></div>' +
      '<div class="mb-2 flex gap-1.5"><input data-role="q" placeholder="종목명 또는 코드 검색" class="flex-1 rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1.5" />' +
      '<button type="button" data-act="search" class="px-3 py-1.5 rounded border border-emerald-500/40 bg-emerald-500/15 text-emerald-400 font-semibold">검색</button></div>' +
      '<div data-role="results" class="mb-3 space-y-1"></div>' +
      '<div class="mb-3"><div class="font-semibold mb-1">업종 프리셋 도우미 (업종 선택 → 종목 체크 → 일괄 등록)</div><div data-role="presets" class="flex flex-wrap gap-1.5"></div>' +
      '<div data-role="presetBox" class="mt-2"></div></div>' +
      '<div class="font-semibold mb-1">등록된 제외 종목 <span data-role="cnt"></span></div><div data-role="list" class="space-y-1"></div>', "max-w-2xl");
    const q = s => m.el.querySelector(s);
    q('[data-act="close"]').onclick = m.close;

    async function notify() {
      refreshNavCounts();
      if (typeof o.onChange === "function") { try { await o.onChange(); } catch (e) { /* noop */ } }
      if (typeof onExcludedChangeHook === "function") { try { await onExcludedChangeHook(); } catch (e) { /* noop */ } }
    }

    async function renderList() {
      const ex = await loadExcludedSet();
      q('[data-role="cnt"]').textContent = "(" + ex.rows.length + ")";
      q('[data-role="list"]').innerHTML = ex.rows.length ? ex.rows.map(r =>
        '<div class="flex items-center justify-between rounded border border-[var(--border)] px-2 py-1">' +
        '<span>' + esc(r.hname) + ' <span class="text-[var(--muted-foreground)] font-mono">' + esc(r.shcode) + '</span> ' +
        '<span class="text-[var(--muted-foreground)]">' + esc(r.reason_tag || "") + '</span></span>' +
        '<button type="button" data-restore="' + esc(r.shcode) + '" class="px-2 py-0.5 rounded border border-emerald-500/40 text-emerald-400">복구</button></div>').join("")
        : '<div class="text-[var(--muted-foreground)]">등록된 제외 종목이 없습니다.</div>';
      q('[data-role="list"]').querySelectorAll("[data-restore]").forEach(b => {
        b.onclick = async () => { await removeExcluded(b.getAttribute("data-restore")); await renderList(); await notify(); };
      });
    }

    q('[data-role="presets"]').innerHTML = Object.keys(EXCLUDE_PRESETS).map(k =>
      '<button type="button" data-preset="' + esc(k) + '" class="px-2.5 py-1 rounded border border-[var(--border)] hover:bg-[var(--secondary)]">' +
      esc(k) + " (" + EXCLUDE_PRESETS[k].length + ")</button>").join("");
    q('[data-role="presets"]').querySelectorAll("[data-preset]").forEach(b => {
      b.onclick = () => {
        const key = b.getAttribute("data-preset");
        const preset = EXCLUDE_PRESETS[key];
        const box = q('[data-role="presetBox"]');
        box.innerHTML = '<div class="rounded border border-[var(--border)] p-2"><div class="font-semibold mb-1">' + esc(key) + '</div><div class="grid grid-cols-2 gap-1">' +
          preset.map(p => '<label class="flex items-center gap-1"><input type="checkbox" data-pchk="' + esc(p[0]) + '" checked /> ' + esc(p[1]) +
            ' <span class="font-mono text-[var(--muted-foreground)]">' + esc(p[0]) + '</span></label>').join("") +
          '</div><button type="button" data-act="presetReg" class="mt-2 px-3 py-1.5 rounded bg-rose-500/80 text-white font-semibold">선택 프리셋 종목 일괄 등록</button></div>';
        box.querySelector('[data-act="presetReg"]').onclick = async () => {
          const codes = Array.from(box.querySelectorAll("[data-pchk]")).filter(c => c.checked).map(c => c.getAttribute("data-pchk"));
          if (!codes.length) return;
          const found = await lookupMasters(codes);
          const byCode = {};
          found.forEach(f => { byCode[f.shcode] = f; });
          const list = preset.filter(p => codes.includes(p[0])).map(p => byCode[p[0]] || { shcode: p[0], hname: p[1], market: "" });
          try { await addExcluded(list, key); } catch (e) { alert("등록 실패: " + e.message); return; }
          box.innerHTML = "";
          await renderList(); await notify();
        };
      };
    });

    q('[data-act="search"]').onclick = async () => {
      const term = q('[data-role="q"]').value.trim();
      if (!term) return;
      const safe = term.replace(/[(),*%]/g, "");
      let rows = [];
      try {
        rows = await sbGet("stocks_master?or=(hname.ilike.*" + encodeURIComponent(safe) + "*,shcode.like." + encodeURIComponent(safe) + "*)&select=shcode,hname,market&limit=15");
      } catch (e) { rows = []; }
      q('[data-role="results"]').innerHTML = rows.length ? rows.map(r =>
        '<div class="flex items-center justify-between rounded border border-[var(--border)] px-2 py-1"><span>' + esc(r.hname) +
        ' <span class="font-mono text-[var(--muted-foreground)]">' + esc(r.shcode) + '</span></span>' +
        '<button type="button" data-add="' + esc(r.shcode) + '" class="px-2 py-0.5 rounded border border-rose-500/40 text-rose-400">제외 등록</button></div>').join("")
        : '<div class="text-[var(--muted-foreground)]">검색 결과가 없습니다.</div>';
      q('[data-role="results"]').querySelectorAll("[data-add]").forEach(b => {
        b.onclick = async () => {
          const r = rows.find(x => x.shcode === b.getAttribute("data-add"));
          try { await addExcluded([r], "기타"); } catch (e) { alert("등록 실패: " + e.message); return; }
          await renderList(); await notify();
        };
      });
    };
    await renderList();
    return m;
  }

  // ------------------------------------------------------------------ 캔들 차트 (가로선 · 마커 · EMA)
  // opts: { lines:[{price,color,dash,label}], markers:[{date,label,color}], count, highlightEma20 }
  function drawCandleChart(canvas, candles, opts) {
    if (!canvas || !canvas.getContext) return;
    const o = opts || {};
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);
    const data = (candles || []).slice(-(o.count || 100));
    if (!data.length) { ctx.fillStyle = "#94a3b8"; ctx.font = "12px sans-serif"; ctx.fillText("차트 데이터 없음", 12, 24); return; }
    let lo = Infinity, hi = -Infinity;
    data.forEach(c => {
      lo = Math.min(lo, num(c.low)); hi = Math.max(hi, num(c.high));
      ["ema_5", "ema_20", "ema_60"].forEach(k => { const v = num(c[k]); if (v > 0) { lo = Math.min(lo, v); hi = Math.max(hi, v); } });
    });
    (o.lines || []).forEach(l => { if (num(l.price) > 0) { lo = Math.min(lo, num(l.price)); hi = Math.max(hi, num(l.price)); } });
    const pad = (hi - lo) * 0.06 || 1;
    lo -= pad; hi += pad;
    const L = 8, R = 56, Tp = 10, B = 18;
    const plotW = W - L - R, plotH = H - Tp - B;
    const step = plotW / data.length;
    const toX = i => L + step * (i + 0.5);
    const toY = v => Tp + (hi - v) / (hi - lo) * plotH;
    ctx.strokeStyle = "rgba(148,163,184,0.15)"; ctx.fillStyle = "#94a3b8"; ctx.font = "10px sans-serif"; ctx.lineWidth = 1;
    for (let g = 0; g <= 4; g++) {
      const v = lo + (hi - lo) * g / 4, y = toY(v);
      ctx.beginPath(); ctx.moveTo(L, y); ctx.lineTo(W - R, y); ctx.stroke();
      ctx.fillText(Math.round(v).toLocaleString(), W - R + 4, y + 3);
    }
    const bw = Math.max(1, step * 0.6);
    data.forEach((c, i) => {
      const up = num(c.close) >= num(c.open);
      const col = up ? "#10b981" : "#f43f5e";
      ctx.strokeStyle = col; ctx.fillStyle = col;
      ctx.beginPath(); ctx.moveTo(toX(i), toY(num(c.high))); ctx.lineTo(toX(i), toY(num(c.low))); ctx.stroke();
      const yo = toY(num(c.open)), yc = toY(num(c.close));
      ctx.fillRect(toX(i) - bw / 2, Math.min(yo, yc), bw, Math.max(1, Math.abs(yo - yc)));
    });
    function line(key, color, w) {
      ctx.strokeStyle = color; ctx.lineWidth = w; ctx.beginPath();
      let started = false;
      data.forEach((c, i) => {
        const v = num(c[key]); if (!(v > 0)) return;
        if (!started) { ctx.moveTo(toX(i), toY(v)); started = true; } else ctx.lineTo(toX(i), toY(v));
      });
      ctx.stroke();
    }
    line("ema_60", "#0ea5e9", 1.2);
    line("ema_20", "#10b981", o.highlightEma20 ? 2.6 : 1.6);
    line("ema_5", "#f59e0b", 1.2);
    (o.lines || []).forEach(l => {
      if (!(num(l.price) > 0)) return;
      const y = toY(num(l.price));
      ctx.strokeStyle = l.color; ctx.fillStyle = l.color; ctx.lineWidth = 1.4;
      ctx.setLineDash(l.dash ? [6, 4] : []);
      ctx.beginPath(); ctx.moveTo(L, y); ctx.lineTo(W - R, y); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillText((l.label || "") + " " + Math.round(num(l.price)).toLocaleString(), L + 4, y - 3);
    });
    (o.markers || []).forEach(mk => {
      const i = data.findIndex(c => c.trade_date === mk.date);
      if (i < 0) return;
      const x = toX(i), y = toY(num(data[i].low)) + 12;
      ctx.fillStyle = mk.color || "#facc15";
      ctx.beginPath(); ctx.moveTo(x, y - 9); ctx.lineTo(x - 5, y); ctx.lineTo(x + 5, y); ctx.closePath(); ctx.fill();
      if (mk.label) ctx.fillText(mk.label, x - 8, y + 11);
    });
    ctx.lineWidth = 1;
  }

  // =====================================================================================
  // v2.5 (STRATEGY.md 8절) 지표 · 캔들 · 기하학 패턴 엔진 (Zero Look-ahead) / 100점 종합판단 / 프로 차트
  // =====================================================================================

  // ---- 8.1-1 핵심 기술적 지표
  function computeIndicators(cList) {
    const n = cList.length;
    const rsi14 = new Array(n).fill(50.0);
    const atrPct14 = new Array(n).fill(0);
    const bbUpper20 = new Array(n).fill(0), bbMid20 = new Array(n).fill(0), bbLower20 = new Array(n).fill(0);
    const bbWidth20 = new Array(n).fill(0), bbPctile60 = new Array(n).fill(50.0), volMa20 = new Array(n).fill(0);
    const C = cList.map(c => num(c.close)), H = cList.map(c => num(c.high)), L = cList.map(c => num(c.low)), V = cList.map(c => num(c.volume));
    // RSI (Wilder)
    let avgG = 0, avgL = 0;
    for (let i = 14; i < n; i++) {
      if (i === 14) {
        let g = 0, l = 0;
        for (let k = 1; k <= 14; k++) { g += Math.max(0, C[k] - C[k - 1]); l += Math.max(0, C[k - 1] - C[k]); }
        avgG = g / 14; avgL = l / 14;
      } else {
        avgG = (13 * avgG + Math.max(0, C[i] - C[i - 1])) / 14;
        avgL = (13 * avgL + Math.max(0, C[i - 1] - C[i])) / 14;
      }
      rsi14[i] = avgL === 0 ? 100.0 : 100.0 - 100.0 / (1.0 + avgG / avgL);
    }
    // ATR% (Wilder)
    const TR = [];
    let atr = 0, runSum = 0;
    for (let i = 0; i < n; i++) {
      TR[i] = i === 0 ? H[0] - L[0] : Math.max(H[i] - L[i], Math.abs(H[i] - C[i - 1]), Math.abs(L[i] - C[i - 1]));
      if (i < 13) {
        runSum += C[i] > 0 ? (H[i] - L[i]) / C[i] * 100 : 0;
        atrPct14[i] = runSum / (i + 1);
      } else {
        if (i === 13) { let s = 0; for (let k = 0; k <= 13; k++) s += TR[k]; atr = s / 14; }
        else atr = (13 * atr + TR[i]) / 14;
        atrPct14[i] = C[i] > 0 ? atr / C[i] * 100 : 0;
      }
    }
    // Bollinger (20, 2) + width percentile(60)
    for (let i = 19; i < n; i++) {
      let s = 0;
      for (let k = i - 19; k <= i; k++) s += C[k];
      const mu = s / 20;
      let v = 0;
      for (let k = i - 19; k <= i; k++) v += (C[k] - mu) * (C[k] - mu);
      const sd = Math.sqrt(v / 20);
      bbUpper20[i] = mu + 2 * sd; bbMid20[i] = mu; bbLower20[i] = mu - 2 * sd;
      bbWidth20[i] = mu > 0 ? (4 * sd / mu) * 100 : 0;
    }
    for (let i = 19; i < n; i++) {
      let cnt = 0, le = 0;
      for (let k = Math.max(19, i - 59); k <= i; k++) {
        if (bbWidth20[k] > 0) { cnt++; if (bbWidth20[k] <= bbWidth20[i]) le++; }
      }
      bbPctile60[i] = cnt >= 5 ? le / cnt * 100 : 50.0;
    }
    // Volume MA20
    for (let i = 0; i < n; i++) {
      const from = Math.max(0, i - 19);
      let s = 0;
      for (let k = from; k <= i; k++) s += V[k];
      volMa20[i] = s / (i - from + 1);
    }
    return { rsi14, atrPct14, bbUpper20, bbMid20, bbLower20, bbWidth20, bbPctile60, volMa20 };
  }

  // ---- 8.1-2 무미래참조 확정 피봇 (endIdx - right 까지만 순회)
  function findConfirmedPivots(cList, endIdx, lookback, left, right) {
    const lb = lookback === undefined ? 65 : lookback;
    const lf = left === undefined ? 3 : left;
    const rt = right === undefined ? 3 : right;
    const pivotHighs = [], pivotLows = [];
    const start = Math.max(lf, endIdx - lb);
    const stop = Math.min(endIdx - rt, cList.length - 1 - rt);
    for (let i = start; i <= stop; i++) {
      let isH = true, isL = true;
      for (let k = 1; k <= lf; k++) {
        if (!(num(cList[i].high) >= num(cList[i - k].high))) isH = false;
        if (!(num(cList[i].low) <= num(cList[i - k].low))) isL = false;
      }
      for (let k = 1; k <= rt; k++) {
        if (!(num(cList[i].high) > num(cList[i + k].high))) isH = false;
        if (!(num(cList[i].low) < num(cList[i + k].low))) isL = false;
      }
      if (isH) pivotHighs.push({ idx: i, date: cList[i].trade_date, price: num(cList[i].high), type: "H" });
      if (isL) pivotLows.push({ idx: i, date: cList[i].trade_date, price: num(cList[i].low), type: "L" });
    }
    return { pivotHighs, pivotLows };
  }

  // ---- 8.1-3 4대 양봉 반전 캔들
  function detectCandleSignal(cList, idx) {
    if (idx < 1 || idx >= cList.length) return null;
    const cur = cList[idx], prev = cList[idx - 1];
    const O = num(cur.open), Hh = num(cur.high), Ll = num(cur.low), Cc = num(cur.close);
    const R = Hh - Ll;
    if (!(Cc >= O) || !(R > 0)) return null;
    const Op = num(prev.open), Cp = num(prev.close);
    const B = Cc - O, WL = Math.min(O, Cc) - Ll, WU = Hh - Math.max(O, Cc);
    if (WL >= Math.max(1.8 * B, 0.45 * R) && WU <= 0.28 * R) return { code: "HAMMER", label: "🔨망치형" };
    if (Cp < Op && Cc >= Op && O <= Cp && B > 1.05 * (Op - Cp)) return { code: "ENGULFING", label: "🔥상승장악형" };
    if (Cp < Op && (Op - Cp) / Op >= 0.015 && O <= Cp && Cc >= (Op + Cp) / 2) return { code: "PIERCING", label: "⚡관통형" };
    if (Op > 0 && Math.abs(Cp - Op) / Op <= 0.006 && (Cc / Cp - 1) >= 0.02 && B >= 0.55 * R) return { code: "DOJI_TURN", label: "✨도지양봉전환" };
    return null;
  }

  // ---- 8.1-4 기하학 차트 패턴 + 작도 좌표
  function emptyPatterns(idx) {
    return {
      idx, vcp: false, flag: false, doubleBottom: false, ihs: false, downChannel: false, isContracted: false,
      candle: null, overlays: { trendlines: [], arcs: [], pivots: [], squeezeZone: [] }
    };
  }

  function lastSettledSupply(sList, T) {
    let i = (sList || []).length - 1;
    while (i >= 0 && T && sList[i].trade_date > T) i--;
    return i;
  }

  function detectChartPatterns(cList, sList, T) {
    const idx = lastUpTo(cList || [], T);
    if (idx < 45) return emptyPatterns(idx);
    const res = emptyPatterns(idx);
    const cs = cList.slice(0, idx + 1);
    const ind = computeIndicators(cs);
    const cur = cs[idx];
    const C = num(cur.close), O = num(cur.open), Hh = num(cur.high), Ll = num(cur.low), V = num(cur.volume);
    const e20 = num(cur.ema_20), e60 = num(cur.ema_60);
    const pc = Hh > Ll ? (C - Ll) / (Hh - Ll) : 0.5;
    const vm = ind.volMa20[idx];
    res.candle = detectCandleSignal(cs, idx);
    const ov = res.overlays;

    // 기관 진성 수급 동반 여부
    const sIdx = lastSettledSupply(sList, T);
    const sl = sIdx >= 0 ? sList.slice(0, sIdx + 1) : [];
    const instT = sIdx >= 0 ? num(sList[sIdx].inst_vol_ratio) : 0;
    const instOk = instT >= 12.0 || consec5pDaysOf(sl) >= 2;
    res.instRatioT = instT;

    // 1) VCP
    let maxHE = -Infinity, minLE = Infinity, maxHL = -Infinity, minLL = Infinity;
    for (let k = idx - 40; k <= idx - 8; k++) { maxHE = Math.max(maxHE, num(cs[k].high)); minLE = Math.min(minLE, num(cs[k].low)); }
    for (let k = idx - 8; k <= idx - 1; k++) { maxHL = Math.max(maxHL, num(cs[k].high)); minLL = Math.min(minLL, num(cs[k].low)); }
    const dEarly = maxHE > 0 ? (maxHE - minLE) / maxHE * 100 : 0;
    const dLate = maxHL > 0 ? (maxHL - minLL) / maxHL * 100 : 0;
    let maxBw = 0;
    for (let k = idx - 40; k <= idx - 1; k++) maxBw = Math.max(maxBw, ind.bbWidth20[k]);
    res.isContracted = dEarly >= 10.0 && (dLate <= 0.62 * dEarly || (maxBw > 0 && ind.bbWidth20[idx - 1] <= 0.65 * maxBw));
    let prior15 = -Infinity;
    for (let k = idx - 15; k <= idx - 1; k++) prior15 = Math.max(prior15, num(cs[k].close));
    res.vcp = ind.atrPct14[idx] >= 3.0 && e20 >= e60 && res.isContracted && C > prior15 &&
      V >= 1.35 * vm && pc >= 0.60 && C > O;
    if (res.isContracted) {
      ov.arcs.push({ from: idx - 40, to: idx - 8, hi: maxHE, lo: minLE, label: "-" + Math.round(dEarly) + "%", color: "#a78bfa" });
      ov.arcs.push({ from: idx - 8, to: idx - 1, hi: maxHL, lo: minLL, label: "-" + Math.round(dLate) + "%", color: "#a78bfa" });
    }
    if (res.vcp) ov.trendlines.push({ x1: idx - 15, y1: prior15, x2: idx, y2: prior15, color: "#a78bfa", dash: true, label: "돌파선" });

    // 2) 깃발·박스
    let pmax = idx - 18;
    for (let k = idx - 18; k <= idx - 3; k++) if (num(cs[k].high) > num(cs[pmax].high)) pmax = k;
    let Lpole = Infinity;
    for (let k = Math.max(0, pmax - 12); k <= pmax; k++) Lpole = Math.min(Lpole, num(cs[k].low));
    const Hp = num(cs[pmax].high);
    const poleUp = Lpole > 0 ? Hp / Lpole - 1 : 0;
    const since = idx - pmax;
    if (poleUp >= 0.14 && since >= 3 && since <= 14 && ind.atrPct14[idx] >= 3.2) {
      let Lpull = Infinity, maxPullClose = -Infinity, boxHigh = -Infinity;
      for (let k = pmax + 1; k <= idx - 1; k++) {
        Lpull = Math.min(Lpull, num(cs[k].low)); maxPullClose = Math.max(maxPullClose, num(cs[k].close));
        boxHigh = Math.max(boxHigh, num(cs[k].high));
      }
      const retr = Hp > Lpole ? (Hp - Lpull) / (Hp - Lpole) : 1;
      if (Lpull >= e20 * 0.98 && retr <= 0.50 && C > O && C > maxPullClose && pc >= 0.58 && V >= 1.15 * vm) {
        res.flag = true;
        ov.trendlines.push({ x1: pmax, y1: boxHigh, x2: idx, y2: boxHigh, color: "#38bdf8", dash: true, label: "박스상단" });
        ov.trendlines.push({ x1: pmax, y1: Lpull, x2: idx, y2: Lpull, color: "#38bdf8", dash: true, label: "지지" });
      }
    }

    const piv = findConfirmedPivots(cs, idx);
    const pl = piv.pivotLows, ph = piv.pivotHighs;
    const maxH50 = (() => { let m = 0; for (let k = Math.max(0, idx - 50); k <= idx - 1; k++) m = Math.max(m, num(cs[k].high)); return m; })();
    const todayOk = C >= e20 && C > O;

    // 3) 쌍바닥
    if (pl.length >= 2) {
      const a = pl[pl.length - 2], b = pl[pl.length - 1];
      if (b.idx - a.idx >= 6 && b.idx - a.idx <= 45 && idx - b.idx <= 10 && a.price > 0 &&
          b.price / a.price >= 0.99 && b.price / a.price <= 1.08) {
        let neck = 0;
        for (let k = a.idx + 1; k <= b.idx - 1; k++) neck = Math.max(neck, num(cs[k].high));
        if (neck >= 1.045 * a.price && a.price <= 0.88 * maxH50 && todayOk && C >= 0.985 * neck && instOk) {
          res.doubleBottom = true;
          ov.pivots.push({ idx: a.idx, price: a.price, label: "L1", type: "L" });
          ov.pivots.push({ idx: b.idx, price: b.price, label: "L2↑", type: "L" });
          ov.trendlines.push({ x1: a.idx, y1: a.price, x2: b.idx, y2: b.price, color: "#10b981", dash: false, label: "" });
          ov.trendlines.push({ x1: a.idx, y1: neck, x2: idx, y2: neck, color: "#a78bfa", dash: true, label: "넥라인" });
        }
      }
    }
    // 4) 역H&S
    if (pl.length >= 3) {
      const a = pl[pl.length - 3], b = pl[pl.length - 2], c3 = pl[pl.length - 1];
      if (b.price < 0.985 * a.price && c3.price > 1.015 * b.price && idx - c3.idx <= 10 && c3.idx - a.idx <= 55) {
        let neck = 0;
        for (let k = b.idx + 1; k <= c3.idx - 1; k++) neck = Math.max(neck, num(cs[k].high));
        if (neck > 0 && todayOk && C >= 0.985 * neck && instOk) {
          res.ihs = true;
          ov.pivots.push({ idx: a.idx, price: a.price, label: "LS", type: "L" });
          ov.pivots.push({ idx: b.idx, price: b.price, label: "Head", type: "L" });
          ov.pivots.push({ idx: c3.idx, price: c3.price, label: "RS", type: "L" });
          ov.trendlines.push({ x1: b.idx, y1: neck, x2: idx, y2: neck, color: "#a78bfa", dash: true, label: "넥라인" });
        }
      }
    }
    // 5) 하락채널
    if (ph.length >= 2 && pl.length >= 2 && C < e60) {
      const h2 = ph[ph.length - 2], h1 = ph[ph.length - 1], l2 = pl[pl.length - 2], l1 = pl[pl.length - 1];
      if (h1.price < 0.985 * h2.price && l1.price < 0.985 * l2.price) {
        res.downChannel = true;
        const slope = (h1.price - h2.price) / Math.max(1, h1.idx - h2.idx);
        ov.trendlines.push({ x1: h2.idx, y1: h2.price, x2: idx, y2: h1.price + slope * (idx - h1.idx), color: "#fb7185", dash: true, label: "하락저항" });
      }
    }
    // BB 스퀴즈 구간 (최근 60봉)
    let segStart = -1;
    for (let k = Math.max(19, idx - 60); k <= idx + 1; k++) {
      const on = k <= idx && ind.bbPctile60[k] <= 25.0;
      if (on && segStart < 0) segStart = k;
      if (!on && segStart >= 0) { ov.squeezeZone.push({ from: segStart, to: k - 1 }); segStart = -1; }
    }
    return res;
  }

  const PATTERN_LABELS = {
    vcp: "🚀 VCP·수렴돌파", flag: "📐 깃발·박스돌파", doubleBottom: "🌱 쌍바닥돌파", ihs: "🌱 역H&S전환", downChannel: "[하락채널저항]"
  };

  // ---- 8.2 추천/비추천 분류 확장 (v2.4 반환 필드 보존 + subTag/displayTag/subReason/pattern)
  function classifyRecommendation(cList, sList, isTrendReversal) {
    const n = cList.length;
    const T = cList[n - 1];
    const close = num(T.close), open = num(T.open);
    const avgRange = avgIntradayRange20(cList);
    const mk = (rec, tag, reasons, step, extra) => Object.assign(
      { recommended: rec, tag, reasons, step, avgRange, subTag: "", displayTag: tag, subReason: "", pattern: "" }, extra || {});
    const reasons = [];
    // Step 1: 공통 비추천 (양봉은 윗꼬리·과열 여부와 무관하게 절대 제외하지 않음)
    if (avgRange < 2.5) reasons.push("[저변동]");
    if (close < open) reasons.push("[음봉마감]");
    if (close < num(T.ema_5)) reasons.push("[5일선이탈]");
    if (reasons.length) return mk(false, "", reasons, 1, { displayTag: "" });
    // Step 2: 대바닥 예외 승격
    if (isTrendReversal) return mk(true, "바닥전환 첫수급", [], 2, { displayTag: "🔄 바닥전환 첫수급" });
    if (isBottomSupportPattern(cList, sList || [])) return mk(true, "바닥지지 연속수급", [], 2, { displayTag: "🌱 바닥지지 연속수급" });
    const pat = n >= 46 ? detectChartPatterns(cList, sList || [], T.trade_date) : null;
    if (pat && pat.doubleBottom) return mk(true, "쌍바닥돌파", [], 2, { subTag: "🌱 쌍바닥돌파", displayTag: "🌱 쌍바닥돌파", pattern: "doubleBottom" });
    if (pat && pat.ihs) return mk(true, "역H&S전환", [], 2, { subTag: "🌱 역H&S전환", displayTag: "🌱 역H&S전환", pattern: "ihs" });
    // Step 3: 일반 추세 검증 + 4대 진입성향 서브태그
    if (close >= num(T.ema_5) && close >= num(T.ema_20) && close >= num(T.ema_60)) {
      let sub = "", pattern = "";
      if (n >= 30) {
        const ind = computeIndicators(cList);
        const i = n - 1;
        const ema20 = num(T.ema_20), ema60 = num(T.ema_60);
        const surge = ind.rsi14[i] >= 75.0 || (ema20 > 0 && (close / ema20 - 1) * 100 >= 15.0) || num(T.change_rate) >= 13.0;
        const near = e => e > 0 && ((close / e - 1) * 100 <= 3.5 || (num(T.low) / e - 1) * 100 <= 3.5);
        if (surge) sub = "⚡ 급등기준봉·눌림대기";
        else if (pat && pat.vcp) { sub = "🚀 VCP·수렴돌파"; pattern = "vcp"; }
        else if (pat && pat.flag) { sub = "📐 깃발·박스돌파"; pattern = "flag"; }
        else if (ind.atrPct14[i] >= 3.0 && (near(ema20) || near(ema60)) && detectCandleSignal(cList, i)) sub = "🕯️ 이평지지반전";
      }
      return mk(true, "추세수급", [], 3, { subTag: sub, displayTag: sub || "추세수급", pattern });
    }
    if (isReverseAligned(T)) reasons.push("[역배열낙하]");
    else if (close < num(T.ema_20)) reasons.push("[20일선이탈]");
    else reasons.push("[60일선이탈]");
    return mk(false, "", reasons, 3, { displayTag: "", subReason: pat && pat.downChannel ? "[하락채널저항]" : "" });
  }

  // ---- 8.3 4축 100점 종합판단
  function scoreWatchlist(item, base, cList, sList, T, idx) {
    const cs = cList.slice(0, idx + 1);
    const ind = computeIndicators(cs);
    const cur = cs[idx];
    const close = num(cur.close), open = num(cur.open), hi = num(cur.high), lo = num(cur.low), vol = num(cur.volume);
    const e5 = num(cur.ema_5), e20 = num(cur.ema_20), e60 = num(cur.ema_60);
    const tagStr = String(item.recommend_tag || "").trim();
    const isBottomOrigin = /바닥|역H&S/.test(tagStr);
    const stopBreak = base.stopBreak;
    const pat = detectChartPatterns(cs, sList || [], T);
    const candle = idx >= 1 ? detectCandleSignal(cs, idx) : null;

    // ① 수급 (35)
    const sIdx = lastSettledSupply(sList, T);
    const sT = sIdx >= 0 && sList[sIdx].trade_date === T ? sList[sIdx] : null;
    const instT = sT ? num(sT.inst_vol_ratio) : 0;
    let supply = 0;
    if (!base.supplyExit) {
      const firstAmt = num(item.first_inst_amt);
      const R = firstAmt > 0 ? (firstAmt + base.postAmtM) / firstAmt : 1.0;
      supply = R >= 1.4 ? 22 : (R >= 0.9 ? 18 : (R >= 0.5 ? 12 : 6));
      if (instT >= 8.0) supply += 7; else if (instT >= 3.0) supply += 4;
      supply += Math.min(4, Math.max(0, num(item.signal_count) - 1) * 2);
      if (sT && num(sT.frg_vol) > 0) supply += 2;
      supply = Math.min(35, supply);
    }
    // ② 구조 (30)
    let structure = 0;
    if (close >= e5 && e5 >= e20 && e20 >= e60) structure = 12;
    else if (close >= e20 && close >= e60) structure = 8;
    else if (isBottomOrigin && !stopBreak && close >= e20) structure = 8;
    else if (isBottomOrigin && !stopBreak && close >= e5) structure = 6;
    else if (close >= e60) structure = 4;
    let recent5Low = Infinity, prior15Low = Infinity;
    if (idx >= 19) {
      for (let k = idx - 4; k <= idx; k++) recent5Low = Math.min(recent5Low, num(cs[k].low));
      for (let k = idx - 19; k <= idx - 5; k++) prior15Low = Math.min(prior15Low, num(cs[k].low));
    }
    if (pat.vcp || pat.flag) structure += 14;
    else if (pat.doubleBottom || pat.ihs) structure += 12;
    else if (pat.isContracted) structure += 8;
    else if (idx >= 19 && recent5Low >= prior15Low) structure += 6;
    const dist5 = e5 > 0 ? (close / e5 - 1) * 100 : null;
    if ((close >= e20 || (isBottomOrigin && !stopBreak && close >= e5)) && dist5 !== null && dist5 >= -1.0 && dist5 <= 4.5) structure += 4;
    if (stopBreak || (!isBottomOrigin && close < e20)) structure = Math.max(0, structure - 15);
    structure = Math.min(30, structure);
    // ③ 트리거 (20)
    const vm = ind.volMa20[idx];
    const vr = vm > 0 ? vol / vm : 0;
    let p3 = 0;
    if (idx >= 3 && vm > 0) p3 = ((num(cs[idx - 3].volume) + num(cs[idx - 2].volume) + num(cs[idx - 1].volume)) / 3) / vm;
    else p3 = 1;
    const pc = hi > lo ? (close - lo) / (hi - lo) : 0.5;
    let trigger = 0;
    if (close >= open) {
      trigger = 5;
      let best = 0;
      if (vr >= 1.5 && pc >= 0.60) best = Math.max(best, 9);
      if (candle && (close >= e20 || isBottomOrigin)) best = Math.max(best, 8);
      if (p3 <= 0.70 && close >= e5) best = Math.max(best, 7);
      if (close >= e5 && pc >= 0.55) best = Math.max(best, 4);
      trigger += best;
    } else if (p3 <= 0.65 && (close >= e20 || (isBottomOrigin && !stopBreak))) {
      trigger = 4;
    }
    trigger = Math.min(20, trigger);
    // ④ 지표 (15)
    const atr = ind.atrPct14[idx], rsi = ind.rsi14[idx];
    let indicator = atr >= 4.0 ? 8 : (atr >= 3.0 ? 5 : (atr >= 2.5 ? 2 : 0));
    if (rsi >= 50.0 && rsi <= 72.0) indicator += 5;
    else if ((rsi >= 42.0 && rsi < 50.0) || (rsi > 72.0 && rsi <= 78.0)) indicator += 3;
    if (idx >= 1 && ind.bbPctile60[idx - 1] <= 35.0) indicator += 2;
    indicator = Math.min(15, indicator);

    const totalScore = supply + structure + trigger + indicator;
    let verdictCode = "WATCH", verdictLabel = "👀 관망유지";
    if (base.isExit || totalScore < 40) { verdictCode = "EXIT"; verdictLabel = "⚠️ 정리권고"; }
    else if (totalScore >= 80 && close >= open && rsi < 78.0) { verdictCode = "READY"; verdictLabel = "🔥 타점완성"; }
    else if (totalScore >= 60) { verdictCode = "WAIT"; verdictLabel = "⏳ 눌림대기"; }
    const suggestedEntryPrice = verdictCode === "READY" ? Math.round(close)
      : Math.round(close > e5 * 1.03 ? e5 : Math.max(e20, num(item.stop_price) || 0));
    const patNames = ["vcp", "flag", "doubleBottom", "ihs"].filter(k => pat[k]).map(k => PATTERN_LABELS[k]);
    const reasons = [
      "수급: " + (base.supplyExit ? "누적 순매수 급감(수급이탈)" : "최초 대비 잔존 " + Math.round((num(item.first_inst_amt) > 0 ? (num(item.first_inst_amt) + base.postAmtM) / num(item.first_inst_amt) : 1) * 100) + "%, 포착 " + num(item.signal_count) + "회") + " (" + supply + "/35)",
      "구조: " + (patNames.length ? patNames.join("·") : (pat.isContracted ? "변동성 수렴 진행" : (close >= e20 ? "20일선 위 추세 유지" : "20일선 아래 바닥 다지기"))) + " (" + structure + "/30)",
      "트리거: " + (candle ? candle.label + " · " : "") + "거래량 " + (vr ? vr.toFixed(1) : "-") + "배, RSI " + rsi.toFixed(0) + ", ATR " + atr.toFixed(1) + "% (" + (trigger + indicator) + "/35)"
    ];
    return {
      totalScore, axisScores: { supply, structure, trigger, indicator },
      verdictCode, verdictLabel, suggestedEntryPrice, reasons,
      patterns: pat, candle, isBottomOrigin, isTrendOrigin: tagStr.length > 0 && !isBottomOrigin,
      rsi14: rsi, atrPct14: atr
    };
  }

  function evaluateWatchlistItem(item, cList, sList, T) {
    const base = evaluateWatchlistBase(item, cList, sList, T);
    if (!base) return null;
    const idx = lastUpTo(cList || [], T);
    return Object.assign(base, scoreWatchlist(item, base, cList, sList, T, idx));
  }

  // ---- 8.4 통합 2단 프로 차트
  function fmtDateShort(d) { return String(d || "").slice(2); }

  function buildBriefing(candles, supplies, ind, idx) {
    const c = candles[idx];
    if (!c) return "";
    const prev = idx > 0 ? num(candles[idx - 1].close) : num(c.close);
    const chg = prev > 0 ? (num(c.close) / prev - 1) * 100 : 0;
    let s = null;
    for (let k = 0; k < (supplies || []).length; k++) if (supplies[k].trade_date === c.trade_date) { s = supplies[k]; break; }
    const inst = s ? (num(s.real_inst_amt) / 100).toFixed(1) + "억 (비중 " + num(s.inst_vol_ratio).toFixed(1) + "%)" : "수급 없음";
    return c.trade_date + " | 종가 " + fmtInt(c.close) + "원 (" + (chg > 0 ? "+" : "") + chg.toFixed(2) + "%) | 거래량 " + fmtInt(c.volume) +
      "주 | 순수기관 " + inst + " | RSI " + (ind ? ind.rsi14[idx].toFixed(0) : "-");
  }

  // data: { candles, supplies } / opts: { width,height,dpr,count,layers,lines,markers,highlightEma20,hoverIdx,background }
  function drawProChart(canvas, data, opts) {
    const o = opts || {};
    const layers = Object.assign({ pattern: true, bb: true, price: true, lower: "inst" }, o.layers || {});
    const dpr = o.dpr || ((typeof root.devicePixelRatio === "number" && root.devicePixelRatio) || 1);
    const cssW = o.width || canvas.clientWidth || 520;
    const cssH = o.height || 320;
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
    if (canvas.style) { canvas.style.width = o.width ? o.width + "px" : "100%"; canvas.style.height = cssH + "px"; }
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);
    if (o.background) { ctx.fillStyle = o.background; ctx.fillRect(0, 0, cssW, cssH); }
    const candles = (data && data.candles) || [];
    const supplies = (data && data.supplies) || [];
    const n = candles.length;
    if (!n) { ctx.fillStyle = "#94a3b8"; ctx.font = "12px sans-serif"; ctx.fillText("차트 데이터 없음", 12, 24); return null; }
    const ind = computeIndicators(candles);
    const T = candles[n - 1].trade_date;
    const pat = layers.pattern || layers.bb ? detectChartPatterns(candles, supplies, T) : emptyPatterns(n - 1);
    const count = o.count || 120;
    const start = Math.max(0, n - count);
    const vis = n - start;
    const hasLower = layers.lower === "inst" || layers.lower === "rsi";
    const Lm = 6, Rm = 58, Tm = 8, Bm = 16;
    const plotH = cssH - Tm - Bm;
    const topH = hasLower ? Math.floor(plotH * 0.70) - 4 : plotH;
    const lowTop = Tm + topH + 8, lowH = hasLower ? plotH - topH - 8 : 0;
    const step = (cssW - Lm - Rm) / vis;
    const xOf = i => Lm + step * (i - start + 0.5);
    let lo = Infinity, hi = -Infinity;
    const upd = v => { if (v > 0) { lo = Math.min(lo, v); hi = Math.max(hi, v); } };
    for (let i = start; i < n; i++) {
      const c = candles[i];
      upd(num(c.low)); upd(num(c.high)); upd(num(c.ema_5)); upd(num(c.ema_20)); upd(num(c.ema_60));
      if (layers.bb && ind.bbUpper20[i] > 0) { upd(ind.bbUpper20[i]); upd(ind.bbLower20[i]); }
    }
    if (layers.price) (o.lines || []).forEach(l => upd(num(l.price)));
    const pad = (hi - lo) * 0.06 || 1;
    lo -= pad; hi += pad;
    const yOf = v => Tm + (hi - v) / (hi - lo) * topH;
    ctx.lineWidth = 1; ctx.font = "10px sans-serif";
    for (let g = 0; g <= 4; g++) {
      const v = lo + (hi - lo) * g / 4, y = yOf(v);
      ctx.strokeStyle = "rgba(148,163,184,0.15)";
      ctx.beginPath(); ctx.moveTo(Lm, y); ctx.lineTo(cssW - Rm, y); ctx.stroke();
      ctx.fillStyle = "#94a3b8"; ctx.fillText(Math.round(v).toLocaleString(), cssW - Rm + 4, y + 3);
    }
    // BB 구름대 + 스퀴즈
    if (layers.bb) {
      ctx.fillStyle = "rgba(56,189,248,0.10)";
      ctx.beginPath();
      let first = true;
      for (let i = Math.max(start, 19); i < n; i++) { const x = xOf(i), y = yOf(ind.bbUpper20[i]); if (first) { ctx.moveTo(x, y); first = false; } else ctx.lineTo(x, y); }
      for (let i = n - 1; i >= Math.max(start, 19); i--) ctx.lineTo(xOf(i), yOf(ind.bbLower20[i]));
      ctx.closePath(); ctx.fill();
      ctx.fillStyle = "rgba(20,184,166,0.85)";
      for (let i = Math.max(start, 19); i < n; i++) {
        if (ind.bbPctile60[i] <= 25.0) ctx.fillRect(xOf(i) - step / 2, Tm + topH - 4, Math.max(1, step), 4);
      }
    }
    // 캔들
    const bw = Math.max(1, step * 0.6);
    for (let i = start; i < n; i++) {
      const c = candles[i];
      const col = num(c.close) >= num(c.open) ? "#10b981" : "#f43f5e";
      ctx.strokeStyle = col; ctx.fillStyle = col;
      ctx.beginPath(); ctx.moveTo(xOf(i), yOf(num(c.high))); ctx.lineTo(xOf(i), yOf(num(c.low))); ctx.stroke();
      const yo = yOf(num(c.open)), yc = yOf(num(c.close));
      ctx.fillRect(xOf(i) - bw / 2, Math.min(yo, yc), bw, Math.max(1, Math.abs(yo - yc)));
    }
    // EMA (ISSUE-017③: 상단 플롯 영역으로 클리핑해 하단 서브패널 침범 방지)
    ctx.save(); ctx.beginPath(); ctx.rect(Lm, Tm - 2, cssW - Lm - Rm + 2, topH + 4); ctx.clip();
    [["ema_240", "#f43f5e", 1], ["ema_120", "#f97316", 1], ["ema_60", "#0ea5e9", 1.2], ["ema_20", "#10b981", o.highlightEma20 ? 2.8 : 1.6], ["ema_5", "#f59e0b", 1.2]].forEach(([k, color, w]) => {
      ctx.strokeStyle = color; ctx.lineWidth = w; ctx.beginPath();
      let st = false;
      for (let i = start; i < n; i++) {
        const v = num(candles[i][k]); if (!(v > 0)) continue;
        if (!st) { ctx.moveTo(xOf(i), yOf(v)); st = true; } else ctx.lineTo(xOf(i), yOf(v));
      }
      ctx.stroke();
    });
    ctx.lineWidth = 1;
    // 패턴 작도
    if (layers.pattern) {
      const ov = pat.overlays;
      ov.trendlines.forEach(t => {
        ctx.strokeStyle = t.color; ctx.fillStyle = t.color; ctx.lineWidth = 1.4;
        ctx.setLineDash(t.dash ? [6, 4] : []);
        ctx.beginPath(); ctx.moveTo(xOf(Math.max(start, t.x1)), yOf(t.y1)); ctx.lineTo(xOf(t.x2), yOf(t.y2)); ctx.stroke(); ctx.setLineDash([]);
        if (t.label) ctx.fillText(t.label, xOf(t.x2) - 34, yOf(t.y2) - 3);
      });
      ov.arcs.forEach(a => {
        if (a.to < start) return;
        const x1 = xOf(Math.max(start, a.from)), x2 = xOf(a.to), y = yOf(a.hi) - 6;
        ctx.strokeStyle = a.color; ctx.fillStyle = a.color; ctx.lineWidth = 1.2;
        ctx.beginPath(); ctx.moveTo(x1, y + 4); ctx.quadraticCurveTo((x1 + x2) / 2, y - 12, x2, y + 4); ctx.stroke();
        ctx.fillText(a.label, (x1 + x2) / 2 - 10, y - 8);
      });
      ov.pivots.forEach(p => {
        if (p.idx < start) return;
        ctx.fillStyle = "#facc15";
        ctx.beginPath(); ctx.arc(xOf(p.idx), yOf(p.price), 3, 0, Math.PI * 2); ctx.fill();
        ctx.fillText(p.label, xOf(p.idx) - 8, yOf(p.price) + 14);
      });
      // 반전 캔들 시그널 뱃지 + 돌파 뱃지
      const badge = { HAMMER: "🔨", ENGULFING: "🔥", PIERCING: "⚡", DOJI_TURN: "✨" };
      for (let i = Math.max(start, 1); i < n; i++) {
        const sg = detectCandleSignal(candles, i);
        if (sg) { ctx.fillStyle = "#fde68a"; ctx.fillText(badge[sg.code], xOf(i) - 5, yOf(num(candles[i].high)) - 4); }
      }
      if (pat.vcp || pat.flag) { ctx.fillStyle = "#c4b5fd"; ctx.fillText("🚀", xOf(n - 1) - 5, yOf(num(candles[n - 1].high)) - 16); }
    }
    ctx.restore();
    // 가격선 + 마커
    if (layers.price) {
      (o.lines || []).forEach(l => {
        if (!(num(l.price) > 0)) return;
        const y = yOf(num(l.price));
        ctx.strokeStyle = l.color; ctx.fillStyle = l.color; ctx.lineWidth = 1.4;
        ctx.setLineDash(l.dash ? [6, 4] : []);
        ctx.beginPath(); ctx.moveTo(Lm, y); ctx.lineTo(cssW - Rm, y); ctx.stroke(); ctx.setLineDash([]);
        ctx.fillText((l.label || "") + " " + Math.round(num(l.price)).toLocaleString(), Lm + 4, y - 3);
      });
      (o.markers || []).forEach(mk => {
        let i = -1;
        for (let k = start; k < n; k++) if (candles[k].trade_date === mk.date) { i = k; break; }
        if (i < 0) return;
        const x = xOf(i), y = yOf(num(candles[i].low)) + 12;
        ctx.fillStyle = mk.color || "#facc15";
        ctx.beginPath(); ctx.moveTo(x, y - 9); ctx.lineTo(x - 5, y); ctx.lineTo(x + 5, y); ctx.closePath(); ctx.fill();
        if (mk.label) ctx.fillText("▲" + mk.label, x - 10, y + 11);
      });
    }
    ctx.lineWidth = 1;
    // 하단 서브 패널
    if (hasLower) {
      ctx.strokeStyle = "rgba(148,163,184,0.25)";
      ctx.strokeRect(Lm, lowTop, cssW - Lm - Rm, lowH);
      ctx.fillStyle = "#94a3b8";
      if (layers.lower === "inst") {
        const sMap = {};
        supplies.forEach(s => { sMap[s.trade_date] = s; });
        let maxAbs = 1, maxVol = 1;
        for (let i = start; i < n; i++) {
          const s = sMap[candles[i].trade_date];
          if (s) maxAbs = Math.max(maxAbs, Math.abs(num(s.real_inst_amt) / 100));
          maxVol = Math.max(maxVol, num(candles[i].volume));
        }
        const mid = lowTop + lowH / 2;
        ctx.fillText("순수기관(억) ±" + maxAbs.toFixed(0), Lm + 4, lowTop + 10);
        for (let i = start; i < n; i++) {
          const s = sMap[candles[i].trade_date];
          if (!s) continue;
          const v = num(s.real_inst_amt) / 100;
          const h = Math.abs(v) / maxAbs * (lowH / 2 - 2);
          ctx.fillStyle = v >= 0 ? "#10b981" : "#f43f5e";
          ctx.fillRect(xOf(i) - Math.max(1, step * 0.6) / 2, v >= 0 ? mid - h : mid, Math.max(1, step * 0.6), Math.max(1, h));
        }
        ctx.strokeStyle = "#facc15"; ctx.lineWidth = 1; ctx.beginPath();
        for (let i = start; i < n; i++) {
          const y = lowTop + lowH - num(candles[i].volume) / maxVol * (lowH - 4);
          if (i === start) ctx.moveTo(xOf(i), y); else ctx.lineTo(xOf(i), y);
        }
        ctx.stroke();
        ctx.fillStyle = "#facc15"; ctx.fillText("거래량", cssW - Rm + 4, lowTop + lowH - 2);
      } else {
        const yR = v => lowTop + (100 - v) / 100 * lowH;
        [30, 50, 70].forEach(lv => {
          ctx.strokeStyle = "rgba(148,163,184,0.35)"; ctx.setLineDash([3, 3]);
          ctx.beginPath(); ctx.moveTo(Lm, yR(lv)); ctx.lineTo(cssW - Rm, yR(lv)); ctx.stroke(); ctx.setLineDash([]);
          ctx.fillStyle = "#94a3b8"; ctx.fillText(String(lv), cssW - Rm + 4, yR(lv) + 3);
        });
        ctx.strokeStyle = "#c084fc"; ctx.lineWidth = 1.4; ctx.beginPath();
        for (let i = start; i < n; i++) { const y = yR(ind.rsi14[i]); if (i === start) ctx.moveTo(xOf(i), y); else ctx.lineTo(xOf(i), y); }
        ctx.stroke(); ctx.lineWidth = 1;
        ctx.fillStyle = "#c084fc"; ctx.fillText("RSI 14", Lm + 4, lowTop + 10);
      }
    }
    // 날짜 축
    ctx.fillStyle = "#94a3b8";
    const tickEvery = Math.max(1, Math.floor(vis / 6));
    for (let i = start; i < n; i += tickEvery) ctx.fillText(fmtDateShort(candles[i].trade_date), xOf(i) - 20, cssH - 3);
    // 크로스헤어
    if (o.hoverIdx !== undefined && o.hoverIdx !== null && o.hoverIdx >= start && o.hoverIdx < n) {
      const x = xOf(o.hoverIdx);
      ctx.strokeStyle = "rgba(226,232,240,0.55)"; ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(x, Tm); ctx.lineTo(x, Tm + plotH); ctx.stroke();
      const y = yOf(num(candles[o.hoverIdx].close));
      ctx.beginPath(); ctx.moveTo(Lm, y); ctx.lineTo(cssW - Rm, y); ctx.stroke(); ctx.setLineDash([]);
    }
    return {
      start, vis, step, cssW, cssH, pat, ind,
      idxAt: px => Math.max(start, Math.min(n - 1, start + Math.floor((px - Lm) / step)))
    };
  }

  function patternBadgesOf(pat) {
    if (!pat) return [];
    return ["vcp", "flag", "doubleBottom", "ihs"].filter(k => pat[k]).map(k => PATTERN_LABELS[k]);
  }

  function sanitizeFilePart(s) { return String(s || "").replace(/[\\/:*?"<>|\s]+/g, "").replace(/[🚀📐🌱🔥⏳👀⚠️⚡🕯️🎯]/gu, ""); }

  // state: { hname, shcode, candles, supplies, badges[], status }
  function chartImageFilename(state) {
    const candles = state.candles || [];
    const T = state.T || (candles.length ? candles[candles.length - 1].trade_date : "");
    let status = state.status;
    if (!status) status = (state.badges && state.badges[0]) || (patternBadgesOf(detectChartPatterns(candles, state.supplies || [], T))[0]) || "차트";
    return T + "_" + sanitizeFilePart(state.hname) + "_" + (sanitizeFilePart(status) || "차트") + ".png";
  }

  function buildChartImageCanvas(state, o) {
    const opt = o || {};
    const W = opt.width || 1100, H = opt.height || 620, dpr = opt.dpr || 2, headerH = 64;
    const candles = state.candles || [];
    const n = candles.length;
    const last = n ? candles[n - 1] : {};
    const prev = n > 1 ? num(candles[n - 2].close) : num(last.close);
    const chg = prev > 0 ? (num(last.close) / prev - 1) * 100 : 0;
    const T = state.T || last.trade_date || "";
    const pats = patternBadgesOf(detectChartPatterns(candles, state.supplies || [], T));
    const badges = (state.badges && state.badges.length ? state.badges : pats);
    const out = document.createElement("canvas");
    out.width = W * dpr; out.height = (H + headerH) * dpr;
    const ctx = out.getContext("2d");
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = "#090d16"; ctx.fillRect(0, 0, out.width, out.height);
    const inner = document.createElement("canvas");
    drawProChart(inner, { candles, supplies: state.supplies || [] }, {
      width: W, height: H, dpr, count: state.count || 120, layers: state.layers, lines: state.lines, markers: state.markers,
      highlightEma20: state.highlightEma20, background: "#090d16"
    });
    ctx.drawImage(inner, 0, headerH * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = "#111827"; ctx.fillRect(0, 0, W, headerH);
    ctx.fillStyle = "#f1f5f9"; ctx.font = "bold 18px sans-serif";
    ctx.fillText(String(state.hname || "") + " (" + String(state.shcode || "") + ") · 기준일 " + T + " · 현재가 " + fmtInt(last.close) + "원 (" + (chg > 0 ? "+" : "") + chg.toFixed(2) + "%)", 14, 26);
    ctx.fillStyle = "#34d399"; ctx.font = "13px sans-serif";
    ctx.fillText(badges.length ? badges.join("  ·  ") : "감지된 패턴 없음", 14, 50);
    return out;
  }

  function downloadChartPng(state, o) {
    const cv = buildChartImageCanvas(state, o);
    const url = cv.toDataURL("image/png");
    const a = document.createElement("a");
    a.href = url; a.download = chartImageFilename(state);
    if (document.body && document.body.appendChild) document.body.appendChild(a);
    if (a.click) a.click();
    if (a.remove) a.remove();
    return url;
  }

  async function copyChartToClipboard(state, o) {
    const cv = buildChartImageCanvas(state, o);
    if (typeof ClipboardItem === "undefined" || !navigator.clipboard || !cv.toBlob) return false;
    const blob = await new Promise(res => cv.toBlob(res, "image/png"));
    await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
    return true;
  }

  // 인터랙티브 패널 (기간 버튼 · 레이어 토글 · 브리핑 · 크게 보기 · 이미지 저장)
  function mountProChartPanel(container, popt) {
    const po = popt || {};
    const st = {
      shcode: "", hname: "", candles: [], supplies: [], T: "", lines: [], markers: [], badges: [], status: "",
      period: po.period || 120, layers: { pattern: true, bb: true, price: true, lower: "inst" }, fetchedLong: false,
      highlightEma20: false
    };
    container.innerHTML =
      '<div class="flex flex-wrap items-center gap-1 text-[11px] mb-1" data-role="bar"></div>' +
      '<div data-role="brief" class="text-[11px] font-mono text-[var(--muted-foreground)] h-4 mb-1 truncate"></div>' +
      '<canvas data-role="cv" class="w-full rounded-lg border border-[var(--border)] bg-[var(--background)]"></canvas>';
    const bar = container.querySelector('[data-role="bar"]');
    const brief = container.querySelector('[data-role="brief"]');
    const cv = container.querySelector('[data-role="cv"]');
    let geom = null;
    const btn = "px-1.5 py-0.5 rounded border ";
    function renderBar() {
      const periods = [[60, "60일"], [120, "120일"], [240, "240일(1년)"], [720, "720일(3년)"]];
      bar.innerHTML = periods.map(p => '<button type="button" data-period="' + p[0] + '" class="' + btn +
        (st.period === p[0] ? "border-emerald-500 bg-emerald-500 text-slate-950" : "border-[var(--border)]") + '">' + p[1] + "</button>").join("") +
        '<label class="ml-1"><input type="checkbox" data-layer="pattern" ' + (st.layers.pattern ? "checked" : "") + "/> 패턴작도</label>" +
        '<label><input type="checkbox" data-layer="bb" ' + (st.layers.bb ? "checked" : "") + "/> BB스퀴즈</label>" +
        '<label><input type="checkbox" data-layer="price" ' + (st.layers.price ? "checked" : "") + "/> 가격선</label>" +
        '<select data-role="lower" class="rounded border border-[var(--border)] bg-[var(--background)] px-1">' +
        [["inst", "기관·거래량"], ["rsi", "RSI 14"], ["none", "하단 숨김"]].map(x => '<option value="' + x[0] + '"' + (st.layers.lower === x[0] ? " selected" : "") + ">" + x[1] + "</option>").join("") + "</select>" +
        (po.big ? "" : '<button type="button" data-act="big" class="' + btn + 'border-[var(--border)]">🔍 크게 보기</button>') +
        '<button type="button" data-act="png" class="' + btn + 'border-emerald-500/40 text-emerald-400">📸 이미지 저장</button>' +
        (po.big ? '<button type="button" data-act="copy" class="' + btn + 'border-[var(--border)]">📋 클립보드 복사</button>' : "") +
        '<span data-role="msg" class="text-emerald-400"></span>';
    }
    function redraw(hoverIdx) {
      geom = drawProChart(cv, { candles: st.candles, supplies: st.supplies }, {
        height: po.height || 300, width: po.width, count: st.period, layers: st.layers, lines: st.lines, markers: st.markers,
        highlightEma20: st.highlightEma20, hoverIdx
      });
    }
    async function fetchLong() {
      if (st.fetchedLong || !st.shcode || !st.T) return;
      st.fetchedLong = true;
      const msg = bar.querySelector('[data-role="msg"]');
      if (msg) msg.textContent = "불러오는 중...";
      try {
        const [ch, su] = await Promise.all([
          sbGet("daily_chart?shcode=eq." + st.shcode + "&trade_date=lte." + st.T + "&select=" + CHART_COLS + "&order=trade_date.desc&limit=750"),
          sbGet("daily_investor_supply?shcode=eq." + st.shcode + "&trade_date=lte." + st.T + "&select=" + SUPPLY_COLS + "&order=trade_date.desc&limit=750")
        ]);
        if (ch.length) st.candles = ch.slice().reverse();
        if (su.length) st.supplies = su.slice().reverse();
        if (typeof po.onDataLoaded === "function") po.onDataLoaded(st.shcode, st.candles, st.supplies);
      } catch (e) { st.fetchedLong = false; }
      renderBar(); redraw();
    }
    bar.addEventListener("click", async e => {
      const t = e.target;
      const p = t.closest && t.closest("[data-period]");
      if (p) { st.period = Number(p.getAttribute("data-period")); renderBar(); if (st.period >= 240) await fetchLong(); renderBar(); redraw(); return; }
      const a = t.closest && t.closest("[data-act]");
      if (!a) return;
      const act = a.getAttribute("data-act");
      if (act === "big") openBig();
      if (act === "png") downloadChartPng(snapshot());
      if (act === "copy") {
        const ok = await copyChartToClipboard(snapshot());
        const msg = bar.querySelector('[data-role="msg"]');
        if (msg) msg.textContent = ok ? "복사됨" : "복사 미지원";
      }
    });
    bar.addEventListener("change", e => {
      const t = e.target;
      if (t.getAttribute("data-layer")) st.layers[t.getAttribute("data-layer")] = t.checked;
      if (t.getAttribute("data-role") === "lower") st.layers.lower = t.value;
      redraw();
    });
    cv.addEventListener("mousemove", e => {
      if (!geom) return;
      const r = cv.getBoundingClientRect();
      const idx = geom.idxAt((e.clientX - r.left) * (geom.cssW / (r.width || geom.cssW)));
      brief.textContent = buildBriefing(st.candles, st.supplies, geom.ind, idx);
      redraw(idx);
    });
    cv.addEventListener("mouseleave", () => { brief.textContent = ""; redraw(); });
    cv.addEventListener("dblclick", () => { if (!po.big) openBig(); });
    function snapshot() {
      return Object.assign({}, st, { count: st.period, layers: Object.assign({}, st.layers) });
    }
    function openBig() {
      const m = openModal('<div class="flex justify-between mb-2"><b class="text-sm">' + esc(st.hname) + " (" + esc(st.shcode) + ')</b>' +
        '<button type="button" data-act="x" class="px-2 py-1 rounded border border-[var(--border)]">닫기</button></div><div data-role="host"></div>', "max-w-6xl");
      m.el.querySelector('[data-act="x"]').onclick = m.close;
      const big = mountProChartPanel(m.el.querySelector('[data-role="host"]'), { big: true, height: 560, onDataLoaded: po.onDataLoaded, period: st.period });
      big.setData(Object.assign({}, snapshot(), { keepFetched: true }));
    }
    renderBar();
    return {
      state: st,
      setData(d) {
        const dKey = d.shcode + "|" + (d.T || "") + "|" + (d.status || "");
        const changed = dKey !== st.dataKey;
        st.dataKey = dKey;
        Object.assign(st, { shcode: d.shcode, hname: d.hname, candles: d.candles || [], supplies: d.supplies || [], T: d.T || "", lines: d.lines || [],
          markers: d.markers || [], badges: d.badges || [], status: d.status || "", highlightEma20: !!d.highlightEma20 });
        if (d.layers) st.layers = Object.assign({}, d.layers);
        if (d.period) st.period = d.period;
        if (changed && !d.keepFetched) st.fetchedLong = false;
        if (d.keepFetched) st.fetchedLong = !!d.fetchedLong;
        renderBar(); redraw();
        if (st.period >= 240 && !st.fetchedLong) fetchLong();
      },
      redraw, snapshot
    };
  }


  const api = {
    SUPABASE_URL, SUPABASE_KEY, MIGRATION_SQL, EXCLUDE_PRESETS, CHART_COLS, SUPPLY_COLS,
    esc, round2, num, fmtInt, todayKst, addDays,
    _setFetch: setFetch, parseBodySafe, sbRequest, sbGet, sbPost, sbUpsert, sbPatch, sbDelete, sbCount,
    avgIntradayRange20, isReverseAligned, isBottomSupportPattern, consec5pDaysOf, classifyRecommendation,
    planWatchlistMerge, calcTargets, calcRealizedReturn, calcPnl, summarizeClosed,
    evaluateWatchlistItem, evaluateHolding, chunkCodesForRange, loadSeriesForCodes, fetchLatestTradeDate,
    openModal, copyText, openMigrationSqlModal, showMissingTableBanner, isTableMissingError,
    renderNav, refreshNavCounts, onExcludedChange, loadExcludedSet, addExcluded, removeExcluded, openExcludedModal, lookupMasters,
    drawCandleChart,
    computeIndicators, findConfirmedPivots, detectCandleSignal, detectChartPatterns, drawProChart, mountProChartPanel,
    buildChartImageCanvas, chartImageFilename, downloadChartPng, copyChartToClipboard, buildBriefing, patternBadgesOf, PATTERN_LABELS
  };
  root.LSCommon = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
