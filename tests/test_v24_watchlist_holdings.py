"""v2.4 (STRATEGY.md 7절, AC-24 ~ AC-29) 관심종목 · 보유종목 · 영구제외 검증 테스트."""
import json
import pathlib
import re
import subprocess
import unittest
import urllib.error
from unittest import mock

import run_daily_screener as rds

ROOT = pathlib.Path(__file__).resolve().parent.parent


def run_node(js_body: str):
    """common.js 를 require 한 뒤 js_body 를 실행하고 마지막 줄 JSON 을 반환."""
    prog = "const C = require('./common.js');\n" + js_body
    proc = subprocess.run(["node", "-e", prog], cwd=str(ROOT), capture_output=True, text=True, check=True)
    return json.loads(proc.stdout.strip().splitlines()[-1])


def candle(i, o=100.0, h=102.5, l=100.0, c=102.0, e5=101.0, e20=100.0, e60=100.0, e120=90.0, e240=90.0):
    return {"trade_date": f"2026-01-{i + 1:02d}" if i < 28 else f"2026-02-{i - 27:02d}",
            "open": o, "high": h, "low": l, "close": c, "ema_5": e5, "ema_20": e20, "ema_60": e60,
            "ema_120": e120, "ema_240": e240}


def flat_series(n=25, **kw):
    return [candle(i, **kw) for i in range(n)]


def classify(cl, sl=None, rev=False):
    return run_node(f"console.log(JSON.stringify(C.classifyRecommendation({json.dumps(cl)}, {json.dumps(sl or [])}, {json.dumps(rev)})))")


class TestRecommendation(unittest.TestCase):
    def test_range_boundary_2_5_pass_2_49_fail(self):
        ok = classify(flat_series(h=102.5))
        self.assertTrue(ok["recommended"])
        self.assertEqual(ok["tag"], "추세수급")
        low = classify(flat_series(h=102.49))
        self.assertFalse(low["recommended"])
        self.assertIn("[저변동]", low["reasons"])

    def test_close_equals_open_passes_and_bearish_fails(self):
        eq = classify(flat_series(h=103, o=101, c=101, e5=101))
        self.assertTrue(eq["recommended"])
        bear = classify(flat_series(h=103, o=102, c=101, e5=100.5))
        self.assertIn("[음봉마감]", bear["reasons"])
        self.assertFalse(bear["recommended"])

    def test_bullish_long_upper_wick_overheated_not_excluded(self):
        res = classify(flat_series(o=100, h=130, l=99, c=110, e5=105, e20=100, e60=100))
        self.assertTrue(res["recommended"])

    def test_below_ema5_excluded(self):
        res = classify(flat_series(h=103, c=100.5, o=100, e5=101))
        self.assertIn("[5일선이탈]", res["reasons"])

    def test_step2_pattern_a_promotes_even_below_ema20(self):
        res = classify(flat_series(h=103, e20=120, e60=130, e120=140), rev=True)
        self.assertTrue(res["recommended"])
        self.assertEqual(res["tag"], "바닥전환 첫수급")

    def _pattern_b_series(self, recent_low_break=False):
        series = []
        for i in range(70):
            price = 200 - i * 1.4  # 200 -> ~102
            series.append(candle(i, o=price, h=price + 3, l=price - 3, c=price, e5=price - 1, e20=120, e60=140, e120=160))
        # 최근 5일: 저가가 직전 구간(T-19~T-5) 최저가 이상이거나(정상) 그 아래(돌파 실패)
        series[-1].update({"open": 100.0, "close": 101.0, "high": 104.0, "low": 99.0, "ema_5": 100.0})
        series[-2].update({"close": 100.5, "high": 104.0, "low": 99.0})
        if recent_low_break:
            series[-3]["low"] = 50.0
        else:
            for k in range(2, 20):
                series[-1 - k]["low"] = 90.0 if k >= 5 else series[-1 - k]["low"]
        return series

    def test_step2_pattern_b_bottom_support(self):
        cl = self._pattern_b_series()
        sl = [{"inst_vol_ratio": 6.0}, {"inst_vol_ratio": 7.0}]
        res = classify(cl, sl)
        self.assertTrue(res["recommended"], res)
        self.assertEqual(res["tag"], "바닥지지 연속수급")
        # consec_5p_days < 2 → 비추천 ([역배열낙하])
        res1 = classify(cl, [{"inst_vol_ratio": 1.0}, {"inst_vol_ratio": 7.0}])
        self.assertFalse(res1["recommended"])
        self.assertIn("[역배열낙하]", res1["reasons"])
        # 저점 재이탈 → 비추천
        res2 = classify(self._pattern_b_series(recent_low_break=True), sl)
        self.assertFalse(res2["recommended"])

    def test_step3_reasons(self):
        r20 = classify(flat_series(h=103, c=102, e5=101, e20=105, e60=95, e120=90))
        self.assertEqual(r20["reasons"], ["[20일선이탈]"])
        r60 = classify(flat_series(h=103, c=102, e5=101, e20=98, e60=105, e120=100))
        self.assertEqual(r60["reasons"], ["[60일선이탈]"])
        rrev = classify(flat_series(h=103, c=102, e5=101, e20=105, e60=110, e120=120))
        self.assertEqual(rrev["reasons"], ["[역배열낙하]"])


class TestMergeAndTrading(unittest.TestCase):
    SEL = {"shcode": "005930", "hname": "삼성전자", "market": "KOSPI", "close": 70000, "low": 68500,
           "instRatioT": 12.345, "instAmtM_T": 5000.5, "recommended": True, "tag": "추세수급", "signalMode": "당일10%"}

    def plan(self, selected, existing, T):
        return run_node(f"console.log(JSON.stringify(C.planWatchlistMerge({json.dumps(selected)}, {json.dumps(existing)}, {json.dumps(T)})))")

    def test_new_insert_fields(self):
        p = self.plan([self.SEL], {}, "2026-11-13")
        self.assertEqual(len(p["inserts"]), 1)
        r = p["inserts"][0]
        self.assertEqual((r["first_signal_date"], r["first_signal_close"], r["first_signal_low"]), ("2026-11-13", 70000, 68500))
        self.assertEqual((r["signal_count"], r["stop_price"], r["grade"]), (1, 68500, "B_WATCH"))
        self.assertEqual((r["recommend_tag"], r["signal_mode"]), ("추세수급", "당일10%"))

    def test_existing_increment_and_idempotent(self):
        ex = {"005930": {"shcode": "005930", "signal_count": 1, "last_signal_date": "2026-11-12", "grade": "A_READY"}}
        p = self.plan([self.SEL], ex, "2026-11-13")
        self.assertEqual(len(p["updates"]), 1)
        patch = p["updates"][0]["patch"]
        self.assertEqual((patch["signal_count"], patch["last_signal_date"]), (2, "2026-11-13"))
        for protected in ("first_signal_date", "first_signal_close", "grade", "stop_price", "memo", "target_entry_price"):
            self.assertNotIn(protected, patch)
        # 같은 기준일 재병합 → 증가 없음
        ex2 = {"005930": {"shcode": "005930", "signal_count": 2, "last_signal_date": "2026-11-13"}}
        p2 = self.plan([self.SEL], ex2, "2026-11-13")
        self.assertEqual((len(p2["updates"]), len(p2["inserts"]), p2["untouched"]), (0, 0, ["005930"]))

    def test_white_day_never_deletes_or_increments(self):
        white = dict(self.SEL, recommended=False, tag="")
        ex = {"005930": {"shcode": "005930", "signal_count": 1, "last_signal_date": "2026-11-12"}}
        p = self.plan([white], ex, "2026-11-13")
        self.assertEqual((p["updates"], p["inserts"], p["untouched"]), ([], [], ["005930"]))
        self.assertNotIn("deletes", p)

    def test_targets_and_realized(self):
        out = run_node("console.log(JSON.stringify({a:C.calcTargets(10000), b:C.calcTargets(33333), r:C.calcRealizedReturn(10000, 10750), p:C.calcPnl(10000,10750,100), n:C.calcPnl(10000,10750,null)}))")
        self.assertEqual(out["a"], {"target1": 10500, "target2": 11000})
        self.assertEqual(out["b"], {"target1": 35000, "target2": 36666})
        self.assertEqual((out["r"], out["p"], out["n"]), (7.5, 75000, None))

    def test_closed_history_summary_win_rate(self):
        rows = [
            {"status": "CLOSED", "realized_return_pct": 10.0, "realized_pnl_krw": 100000},
            {"status": "CLOSED", "realized_return_pct": -4.0, "realized_pnl_krw": -40000},
            {"status": "CLOSED", "realized_return_pct": 0.0, "realized_pnl_krw": 0},
            {"status": "CLOSED", "realized_return_pct": 3.0, "realized_pnl_krw": None},
            {"status": "HOLDING", "realized_return_pct": None},
        ]
        s = run_node(f"console.log(JSON.stringify(C.summarizeClosed({json.dumps(rows)})))")
        self.assertEqual((s["count"], s["wins"], s["winRate"], s["avgReturn"], s["totalPnl"]), (4, 2, 50.0, 2.25, 60000))

    def test_watchlist_alerts(self):
        item = {"first_signal_date": "2026-01-10", "first_signal_close": 100, "first_inst_amt": 1000, "stop_price": 95,
                "last_signal_date": "2026-01-25", "signal_count": 2}
        cl = flat_series(25, c=102, e5=101, e20=100, e60=90)
        sl = [{"trade_date": "2026-01-15", "real_inst_amt": -800}]
        ev = run_node(f"console.log(JSON.stringify(C.evaluateWatchlistItem({json.dumps(item)}, {json.dumps(cl)}, {json.dumps(sl)}, '2026-01-25')))")
        self.assertTrue(ev["supplyExit"])           # -800 <= -0.7*1000
        self.assertFalse(ev["stopBreak"])
        self.assertTrue(ev["reSignal"])
        self.assertTrue(ev["isExit"])
        sl2 = [{"trade_date": "2026-01-15", "real_inst_amt": -699}]
        ev2 = run_node(f"console.log(JSON.stringify(C.evaluateWatchlistItem({json.dumps(item)}, {json.dumps(cl)}, {json.dumps(sl2)}, '2026-01-25')))")
        self.assertFalse(ev2["supplyExit"])
        self.assertTrue(ev2["pullback"])             # close 102 vs ema20 100 → +2.0%
        item3 = dict(item, stop_price=103)
        ev3 = run_node(f"console.log(JSON.stringify(C.evaluateWatchlistItem({json.dumps(item3)}, {json.dumps(cl)}, [], '2026-01-25')))")
        self.assertTrue(ev3["stopBreak"])
        self.assertFalse(ev3["pullback"])

    def test_issue012_ema_break_only_for_trend_origin(self):
        base = {"first_signal_date": "2026-01-10", "first_signal_close": 100, "first_inst_amt": 1000, "stop_price": 50,
                "last_signal_date": "2026-01-20", "signal_count": 1}
        cl = flat_series(25, c=102, e5=101, e20=105, e60=110)

        def ev(tag, **kw):
            item = dict(base, recommend_tag=tag, **kw)
            return run_node(f"console.log(JSON.stringify(C.evaluateWatchlistItem({json.dumps(item)}, {json.dumps(cl)}, [], '2026-01-25')))")
        t = ev("추세수급")
        self.assertTrue(t["ema20Break"] and t["ema60Break"] and t["isExit"])
        for tag in ("바닥전환 첫수급", "바닥지지 연속수급"):
            r = ev(tag)
            self.assertFalse(r["ema20Break"] or r["ema60Break"] or r["isExit"], tag)
            self.assertTrue(ev(tag, stop_price=103)["isExit"])  # 기준저가 이탈은 정상 경보

    def test_issue011_rls_42501_detected(self):
        out = run_node("""
C._setFetch(async () => ({ok:false, status:401, headers:{get:()=>''}, text: async ()=>JSON.stringify({code:'42501', message:'new row violates row-level security policy'})}));
C.sbPost('watchlist_items', [{}]).then(()=>console.log('null')).catch(e=>console.log(JSON.stringify({r:e.rlsBlocked,m:e.tableMissing,i:C.isTableMissingError(e)})));
""")
        self.assertEqual(out, {"r": True, "m": False, "i": True})

    def test_issue011_sql_has_grants(self):
        sql = (ROOT / "scripts/migration_v24_watchlist_holdings.sql").read_text(encoding="utf-8")
        self.assertIn("GRANT ALL ON TABLE excluded_stocks, watchlist_items, portfolio_holdings TO anon, authenticated, service_role;", sql)
        self.assertIn("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;", sql)

    def test_issue014_long_range_segmented(self):
        out = run_node("""
const urls = [];
C._setFetch(async (u) => { urls.push(u); return {ok:true,status:200,headers:{get:()=>''},text: async()=>'[]'}; });
C.loadSeriesForCodes('daily_chart', ['005930'], '2021-11-01', '2026-11-13').then(() => console.log(JSON.stringify(urls.length)));
""")
        self.assertGreaterEqual(out, 2)

    def test_holding_ema20_exit_and_targets(self):
        h = {"buy_date": "2026-01-05", "avg_buy_price": 100, "quantity": 10, "target_1_price": 105, "target_2_price": 110}
        cl = flat_series(25, c=98, e20=99.6)
        cl[10]["high"] = 106
        ev = run_node(f"console.log(JSON.stringify(C.evaluateHolding({json.dumps(h)}, {json.dumps(cl)}, [], '2026-01-25')))")
        self.assertTrue(ev["ema20Break"])
        self.assertEqual(ev["ema20ExitPrice"], 100)
        # [ISSUE-014] 현재가(종가) 기준 — 장중 고가 106 이 있어도 종가 98 이면 미도달
        self.assertFalse(ev["tp1Reached"])
        cl2 = flat_series(25, c=111, e20=99.6)
        ev2 = run_node(f"console.log(JSON.stringify(C.evaluateHolding({json.dumps(h)}, {json.dumps(cl2)}, [], '2026-01-25')))")
        self.assertTrue(ev2["tp1Reached"])
        self.assertTrue(ev2["tp2Reached"])
        self.assertEqual((ev["ret"], ev["pnl"]), (-2.0, -20))


class TestInfra(unittest.TestCase):
    def test_safe_http_parsing_and_prefer_headers(self):
        out = run_node("""
const calls = [];
C._setFetch(async (url, init) => { calls.push({url, init}); return {ok:true, status:204, headers:{get:()=>''}, text: async ()=>''}; });
(async () => {
  const a = await C.sbPatch('watchlist_items?id=eq.1', {memo:'x'});
  const b = await C.sbPost('watchlist_items', [{shcode:'000000'}]);
  const c = await C.sbDelete('watchlist_items?id=eq.1');
  const d = await C.sbUpsert('excluded_stocks', [{shcode:'000000'}], 'shcode');
  C._setFetch(async () => ({ok:true, status:200, headers:{get:()=>''}, text: async ()=>'   '}));
  const e = await C.sbGet('x');
  console.log(JSON.stringify({a,b,c,d,e,prefer:calls.map(x=>x.init.headers.Prefer)}));
})();
""")
        self.assertEqual((out["a"], out["b"], out["c"], out["d"], out["e"]), ([], [], [], [], []))
        self.assertEqual(out["prefer"], ["return=representation", "return=representation", "return=representation",
                                         "resolution=merge-duplicates,return=representation"])

    def test_table_missing_detection(self):
        out = run_node("""
C._setFetch(async () => ({ok:false, status:404, headers:{get:()=>''}, text: async ()=>JSON.stringify({code:'PGRST205', message:'no table'})}));
C.sbGet('watchlist_items').then(()=>console.log('null')).catch(e=>console.log(JSON.stringify({m:e.tableMissing,s:e.status})));
""")
        self.assertEqual(out, {"m": True, "s": 404})

    def test_chunk_stays_under_1000_rows(self):
        out = run_node("""
const codes = Array.from({length:55}, (_, i) => String(i).padStart(6,'0'));
const res = {};
for (const d of [30, 120, 400, 900]) { const ch = C.chunkCodesForRange(codes, d); res[d] = [ch.length, Math.max(...ch.map(x=>x.length)), ch.flat().length]; }
console.log(JSON.stringify(res));
""")
        for days, (n, size, total) in out.items():
            self.assertEqual(total, 55)
            self.assertLessEqual(size * (int(days) * 5 / 7 + 2), 1000, msg=days)

    def test_telegram_400_markdown_fallback(self):
        calls = []

        def fake_post(url, payload, headers=None, timeout=30.0):
            calls.append(dict(payload))
            if "parse_mode" in payload:
                raise urllib.error.HTTPError(url, 400, "Bad Request", {}, None)
            return {"ok": True}

        with mock.patch.object(rds, "http_post_json", side_effect=fake_post):
            self.assertTrue(rds.send_telegram_alert("TOKEN", "123", "snake_case_ _odd"))
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["parse_mode"], "Markdown")
        self.assertNotIn("parse_mode", calls[1])
        self.assertEqual(calls[1]["text"], "snake_case_ _odd")

    def test_telegram_non_400_error_not_retried(self):
        calls = []

        def fake_post(url, payload, headers=None, timeout=30.0):
            calls.append(payload)
            raise urllib.error.HTTPError(url, 500, "err", {}, None)

        with mock.patch.object(rds, "http_post_json", side_effect=fake_post):
            self.assertFalse(rds.send_telegram_alert("TOKEN", "123", "hi"))
        self.assertEqual(len(calls), 1)


class TestSqlAndHtml(unittest.TestCase):
    def read(self, rel):
        return (ROOT / rel).read_text(encoding="utf-8")

    def test_sql_definitions(self):
        sql = self.read("scripts/migration_v24_watchlist_holdings.sql")
        for t in ("excluded_stocks", "watchlist_items", "portfolio_holdings"):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {t}", sql)
            self.assertIn(f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY", sql)
        self.assertRegex(sql, r"CREATE UNIQUE INDEX IF NOT EXISTS idx_holdings_active_shcode\s+ON portfolio_holdings \(shcode\) WHERE status = 'HOLDING'")
        self.assertRegex(sql, r"shcode VARCHAR\(6\) NOT NULL UNIQUE")

    def test_schema_file_contains_same_ddl(self):
        schema = self.read("supabase_schema.sql")
        for t in ("excluded_stocks", "watchlist_items", "portfolio_holdings"):
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {t}", schema)
        self.assertIn("idx_holdings_active_shcode", schema)
        # 기존 3개 테이블 정의는 유지
        for t in ("stocks_master", "daily_chart", "daily_investor_supply"):
            self.assertIn(t, schema)

    def test_common_js_embeds_identical_sql(self):
        sql = self.read("scripts/migration_v24_watchlist_holdings.sql")
        out = run_node("console.log(JSON.stringify(C.MIGRATION_SQL))")
        self.assertEqual(out, sql)

    def test_three_pages_share_nav_and_common_js(self):
        for page in ("index.html", "watchlist.html", "holdings.html"):
            html = self.read(page)
            self.assertIn('<script src="common.js"></script>', html, msg=page)
            self.assertIn('id="commonNav"', html, msg=page)
        common = self.read("common.js")
        for label in ("🔍 수급 스크리너", "⭐ 관심종목", "💼 보유종목", "🚫 제외관리"):
            self.assertIn(label, common)
        for href in ("index.html", "watchlist.html", "holdings.html"):
            self.assertIn(f'"{href}"', common)

    def test_index_v24_features(self):
        html = self.read("index.html")
        for token in ("excludeStock" if False else "openExcludeReasonModal", "mergeSelectedToWatchlist", "classifyRecommendation",
                      "[⭐ 선택 종목 관심종목 병합]" if False else "선택 종목 관심종목 병합", "🟢 추천 후보", "⚪ 비추천 보류",
                      "기존관심", "보유중", "computeConsec5pDays(sList) >= 2",
                      "excludedHiddenNotice", "영구제외", "onExcludedChange", "updateMergeControls"):
            self.assertIn(token, html)
        # 가드: common.js 미로딩 환경에서도 스크리닝 동작
        self.assertIn('window.LSCommon) ? window.LSCommon : null', html)

    def test_pages_have_required_ui(self):
        wl = self.read("watchlist.html")
        for token in ("🗑️ 선택 종목 일괄 제외", "일괄 A급 승격", "+ 종목 직접 검색 추가", "⚠️ 이탈·정리 대상", "💼 보유편입", "🚫 영구제외"):
            self.assertIn(token, wl)
        self.assertIn("data-pchk", self.read("common.js"))
        self.assertIn("선택 프리셋 종목 일괄 등록", self.read("common.js"))
        hd = self.read("holdings.html")
        self.assertIn("data-row-id", hd)
        self.assertIn("CLOSED_CHARTS", hd)
        self.assertIn("(D+", hd)
        for token in ("청산 종목 함께 보기", "📜 청산 히스토리", "✅ 청산 처리", "🚨 20일선 이탈", "1차완료 ✓", "+ 보유종목 직접 등록"):
            self.assertIn(token, hd)


if __name__ == "__main__":
    unittest.main()
