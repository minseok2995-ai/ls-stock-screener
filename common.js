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
  const MIGRATION_SQL = "-- =====================================================================\n-- v2.4 마이그레이션: 영구제외 · 관심종목 · 보유종목(청산 히스토리) 테이블 3종\n-- Supabase 대시보드 > SQL Editor 에 전체를 붙여넣고 [Run] 한 번으로 실행하세요.\n-- (기존 stocks_master / daily_chart / daily_investor_supply 는 변경하지 않으며, 여러 번 실행해도 안전합니다)\n-- =====================================================================\n\n-- 5. 영구 제외 종목 사전 (은행·전력·통신 등 사용자 비선호/저변동 상단막힘 종목 영구 차단)\nCREATE TABLE IF NOT EXISTS excluded_stocks (\n    shcode VARCHAR(6) PRIMARY KEY,              -- 종목코드 (6자리)\n    hname VARCHAR(100) NOT NULL,                -- 종목명\n    market VARCHAR(10) DEFAULT '',              -- 시장구분 (KOSPI / KOSDAQ)\n    reason_tag VARCHAR(40) DEFAULT '비선호/저변동', -- 제외 사유 태그 (은행/금융, 공기업/유틸리티, 저변동/상단막힘, 기타)\n    memo TEXT DEFAULT '',                       -- 사용자 메모\n    created_at TIMESTAMPTZ DEFAULT NOW()\n);\n\n-- 6. 통합 관심종목군 (당일 수급 스마트 병합 + 재수급 횟수 누적 + 최종 진입대기 등급 관리)\nCREATE TABLE IF NOT EXISTS watchlist_items (\n    id BIGSERIAL PRIMARY KEY,\n    shcode VARCHAR(6) NOT NULL UNIQUE,          -- 활성 관심종목 종목코드 고유 제약\n    hname VARCHAR(100) NOT NULL,\n    market VARCHAR(10) DEFAULT '',\n    grade VARCHAR(20) NOT NULL DEFAULT 'B_WATCH', -- 'A_READY' (최우선 진입대기) | 'B_WATCH' (일반 관찰)\n    first_signal_date DATE NOT NULL,            -- 최초 포착 기준일 (박제)\n    first_signal_close INTEGER NOT NULL,        -- 최초 포착일 종가 (박제)\n    first_signal_low INTEGER NOT NULL,          -- 최초 포착일 저가 (기준봉 손절 기준선, 박제)\n    first_inst_ratio NUMERIC(8, 2) DEFAULT 0,   -- 최초 포착일 순수기관 비중 (%)\n    first_inst_amt NUMERIC(14, 2) DEFAULT 0,    -- 최초 포착일 순수기관 순매수 금액 (백만원)\n    last_signal_date DATE NOT NULL,             -- 가장 최근 수급 병합 기준일\n    last_inst_ratio NUMERIC(8, 2) DEFAULT 0,    -- 최근 병합일 순수기관 비중 (%)\n    last_inst_amt NUMERIC(14, 2) DEFAULT 0,     -- 최근 병합일 순수기관 순매수 금액 (백만원)\n    signal_count INTEGER NOT NULL DEFAULT 1,    -- 누적 수급 포착(병합) 횟수 (1회, 2회, 3회...)\n    recommend_tag VARCHAR(40) DEFAULT '',       -- 포착 유형 ('추세수급', '바닥전환 첫수급', '바닥지지 연속수급', '수동등록')\n    signal_mode VARCHAR(40) DEFAULT '',         -- 포착 당시 옵션 ('당일10%', '당일15%', '당일20%', '3일연속5%', '하락추세전환', '직접추가')\n    target_entry_price INTEGER,                 -- 사용자 희망 진입가 (선택)\n    stop_price INTEGER,                         -- 사용자 지정 손절가 (기본값: first_signal_low)\n    memo TEXT DEFAULT '',\n    created_at TIMESTAMPTZ DEFAULT NOW(),\n    updated_at TIMESTAMPTZ DEFAULT NOW()\n);\n\nCREATE INDEX IF NOT EXISTS idx_watchlist_grade_last_date\n    ON watchlist_items (grade ASC, last_signal_date DESC);\n\n-- 7. 보유종목 및 청산 매매 히스토리 (A안: 보유중 종목당 1행 고유 + 청산 완료 건별 영구 누적)\nCREATE TABLE IF NOT EXISTS portfolio_holdings (\n    id BIGSERIAL PRIMARY KEY,\n    shcode VARCHAR(6) NOT NULL,\n    hname VARCHAR(100) NOT NULL,\n    market VARCHAR(10) DEFAULT '',\n    status VARCHAR(16) NOT NULL DEFAULT 'HOLDING', -- 'HOLDING' (현재 보유중) | 'CLOSED' (전량 청산 완료)\n    buy_date DATE NOT NULL,                     -- 최초 진입(매수)일\n    avg_buy_price NUMERIC(14, 2) NOT NULL,      -- 진입 평균매수가 (원)\n    quantity BIGINT,                            -- 보유 수량 (주, 선택 입력 — NULL 허용)\n    target_1_price INTEGER NOT NULL,            -- 1차 목표가 (기본값: 진입가의 +5% 반올림, 수정 가능)\n    target_2_price INTEGER NOT NULL,            -- 2차 목표가 (기본값: 진입가의 +10% 반올림, 수정 가능)\n    tp1_done BOOLEAN NOT NULL DEFAULT FALSE,    -- 1차 목표 익절 실행 체크 표시 (수량 분할 입력 불필요)\n    tp2_done BOOLEAN NOT NULL DEFAULT FALSE,    -- 2차 목표 익절 실행 체크 표시\n    entry_source_tag VARCHAR(40) DEFAULT '',    -- 출신 전략 태그 보존 ('추세수급', '바닥전환 첫수급', '바닥지지 연속수급' 등)\n    memo TEXT DEFAULT '',                       -- 매매/복기 메모\n    sell_date DATE,                             -- 최종 전량 청산일 ('CLOSED' 전환 시 기록)\n    avg_sell_price NUMERIC(14, 2),              -- 최종 실제 평균 청산가 (사용자가 수작업 직접 입력!)\n    realized_return_pct NUMERIC(8, 2),          -- 최종 실현 수익률 (%) = ((avg_sell_price - avg_buy_price) / avg_buy_price) * 100\n    realized_pnl_krw BIGINT,                    -- 최종 실현 손익금 (원, quantity 입력 시 자동 계산)\n    close_reason VARCHAR(50) DEFAULT '',        -- 청산 사유 ('목표가 익절', '20일선 이탈 청산', '수급이탈 정리', '수동 청산' 등)\n    created_at TIMESTAMPTZ DEFAULT NOW(),\n    updated_at TIMESTAMPTZ DEFAULT NOW()\n);\n\n-- 현재 보유중('HOLDING') 상태에서는 동일 종목 중복 등록 차단, 청산('CLOSED') 후 재매매 시 신규 행 허용!\nCREATE UNIQUE INDEX IF NOT EXISTS idx_holdings_active_shcode\n    ON portfolio_holdings (shcode) WHERE status = 'HOLDING';\n\nCREATE INDEX IF NOT EXISTS idx_holdings_status_dates\n    ON portfolio_holdings (status, buy_date DESC, sell_date DESC);\n\nALTER TABLE excluded_stocks DISABLE ROW LEVEL SECURITY;\nALTER TABLE watchlist_items DISABLE ROW LEVEL SECURITY;\nALTER TABLE portfolio_holdings DISABLE ROW LEVEL SECURITY;\n\n-- PostgREST 스키마 캐시 즉시 갱신 (신규 테이블이 REST API 에 바로 노출되도록)\nNOTIFY pgrst, 'reload schema';\n";

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

  // 반환: { recommended, tag, reasons[], step, avgRange }
  function classifyRecommendation(cList, sList, isTrendReversal) {
    const T = cList[cList.length - 1];
    const close = num(T.close), open = num(T.open);
    const avgRange = avgIntradayRange20(cList);
    const reasons = [];
    // Step 1: 공통 비추천 (양봉은 윗꼬리·과열 여부와 무관하게 절대 제외하지 않음)
    if (avgRange < 2.5) reasons.push("[저변동]");
    if (close < open) reasons.push("[음봉마감]");
    if (close < num(T.ema_5)) reasons.push("[5일선이탈]");
    if (reasons.length) return { recommended: false, tag: "", reasons, step: 1, avgRange };
    // Step 2: 대바닥 예외 승격
    if (isTrendReversal) return { recommended: true, tag: "바닥전환 첫수급", reasons: [], step: 2, avgRange };
    if (isBottomSupportPattern(cList, sList || [])) return { recommended: true, tag: "바닥지지 연속수급", reasons: [], step: 2, avgRange };
    // Step 3: 일반 추세 필터
    if (close >= num(T.ema_5) && close >= num(T.ema_20) && close >= num(T.ema_60)) {
      return { recommended: true, tag: "추세수급", reasons: [], step: 3, avgRange };
    }
    if (isReverseAligned(T)) reasons.push("[역배열낙하]");
    else if (close < num(T.ema_20)) reasons.push("[20일선이탈]");
    else reasons.push("[60일선이탈]");
    return { recommended: false, tag: "", reasons, step: 3, avgRange };
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
  function evaluateWatchlistItem(item, cList, sList, T) {
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
    const ema20Break = ema20 > 0 && close < ema20;
    const ema60Break = ema60 > 0 && close < ema60;
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
    let maxHigh = 0;
    (cList || []).forEach(x => { if (x.trade_date >= h.buy_date && (!T || x.trade_date <= T)) maxHigh = Math.max(maxHigh, num(x.high)); });
    let postAmt = 0;
    (sList || []).forEach(s => { if (s.trade_date >= h.buy_date && (!T || s.trade_date <= T)) postAmt += num(s.real_inst_amt); });
    const ema20 = num(c.ema_20);
    return {
      close, ret: round2(ret), pnl,
      tp1Reached: num(h.target_1_price) > 0 && maxHigh >= num(h.target_1_price),
      tp2Reached: num(h.target_2_price) > 0 && maxHigh >= num(h.target_2_price),
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
    const days = Math.max(1, Math.round((new Date(toDate) - new Date(fromDate)) / 86400000) + 1);
    const chunks = chunkCodesForRange(codes, days);
    const out = {};
    codes.forEach(c => { out[c] = []; });
    const results = await Promise.all(chunks.map(ch => sbGet(
      table + "?shcode=in.(" + ch.join(",") + ")&and=(trade_date.gte." + fromDate + ",trade_date.lte." + toDate + ")" +
      "&select=" + cols + "&order=shcode.asc,trade_date.asc&limit=1000"
    )));
    results.forEach(rows => rows.forEach(r => { if (out[r.shcode]) out[r.shcode].push(r); }));
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
      '<div>⚠️ 관심종목·보유종목·제외관리 테이블이 아직 생성되지 않았습니다. 스크리닝은 정상 동작하며, 해당 기능은 SQL 실행 후 사용할 수 있습니다.</div>' +
      '<button type="button" id="btnShowMigrationSql" class="px-3 py-1 rounded bg-amber-500/20 border border-amber-500/40 font-semibold shrink-0">테이블 생성 SQL 원클릭 복사</button></div>';
    const btn = document.getElementById("btnShowMigrationSql");
    if (btn) btn.onclick = openMigrationSqlModal;
  }

  function isTableMissingError(err) { return !!(err && err.tableMissing); }

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

  // opts.onChange: 변경 후 콜백
  async function openExcludedModal(opts) {
    const o = opts || {};
    const m = openModal(
      '<div class="flex items-center justify-between mb-2"><h3 class="text-sm font-bold">🚫 영구 제외 사전 관리</h3>' +
      '<button type="button" data-act="close" class="px-2 py-1 rounded border border-[var(--border)]">닫기</button></div>' +
      '<div class="mb-2 flex gap-1.5"><input data-role="q" placeholder="종목명 또는 코드 검색" class="flex-1 rounded border border-[var(--border)] bg-[var(--background)] px-2 py-1.5" />' +
      '<button type="button" data-act="search" class="px-3 py-1.5 rounded border border-emerald-500/40 bg-emerald-500/15 text-emerald-400 font-semibold">검색</button></div>' +
      '<div data-role="results" class="mb-3 space-y-1"></div>' +
      '<div class="mb-3"><div class="font-semibold mb-1">업종 프리셋 일괄 등록</div><div data-role="presets" class="flex flex-wrap gap-1.5"></div></div>' +
      '<div class="font-semibold mb-1">등록된 제외 종목 <span data-role="cnt"></span></div><div data-role="list" class="space-y-1"></div>', "max-w-2xl");
    const q = s => m.el.querySelector(s);
    q('[data-act="close"]').onclick = m.close;

    async function notify() {
      refreshNavCounts();
      if (typeof o.onChange === "function") { try { await o.onChange(); } catch (e) { /* noop */ } }
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
      b.onclick = async () => {
        const key = b.getAttribute("data-preset");
        const preset = EXCLUDE_PRESETS[key];
        const found = await lookupMasters(preset.map(p => p[0]));
        const byCode = {};
        found.forEach(f => { byCode[f.shcode] = f; });
        const list = preset.map(p => byCode[p[0]] || { shcode: p[0], hname: p[1], market: "" });
        try { await addExcluded(list, key); } catch (e) { alert("등록 실패: " + e.message); return; }
        await renderList(); await notify();
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

  const api = {
    SUPABASE_URL, SUPABASE_KEY, MIGRATION_SQL, EXCLUDE_PRESETS, CHART_COLS, SUPPLY_COLS,
    esc, round2, num, fmtInt, todayKst, addDays,
    _setFetch: setFetch, parseBodySafe, sbRequest, sbGet, sbPost, sbUpsert, sbPatch, sbDelete, sbCount,
    avgIntradayRange20, isReverseAligned, isBottomSupportPattern, consec5pDaysOf, classifyRecommendation,
    planWatchlistMerge, calcTargets, calcRealizedReturn, calcPnl, summarizeClosed,
    evaluateWatchlistItem, evaluateHolding, chunkCodesForRange, loadSeriesForCodes, fetchLatestTradeDate,
    openModal, copyText, openMigrationSqlModal, showMissingTableBanner, isTableMissingError,
    renderNav, refreshNavCounts, loadExcludedSet, addExcluded, removeExcluded, openExcludedModal, lookupMasters,
    drawCandleChart
  };
  root.LSCommon = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
