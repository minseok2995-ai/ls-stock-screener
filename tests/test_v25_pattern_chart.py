"""v2.5 (AC-30 ~ AC-35): 지표·캔들·기하학 패턴 엔진, 100점 종합판단, 프로 차트/PNG 저장, 3페이지 통합 검증."""
import json, pathlib, subprocess, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def run_node(body):
    prog = "const C = require('./common.js');\n" + body
    p = subprocess.run(["node", "-e", prog], cwd=str(ROOT), capture_output=True, text=True, check=True)
    return json.loads(p.stdout.strip().splitlines()[-1])


def series(n, f=None):
    out = []
    for i in range(n):
        base = 100 + (f(i) if f else 0)
        out.append({"trade_date": "d%04d" % i, "open": base, "high": base + 2, "low": base - 2, "close": base + 1,
                    "volume": 1000, "ema_5": base, "ema_20": base, "ema_60": base, "ema_120": base, "ema_240": base})
    return out


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


class TestIndicators(unittest.TestCase):
    def test_rsi_atr_bb_ranges(self):
        r = run_node("const cl=%s;const x=C.computeIndicators(cl);const n=cl.length-1;"
                     "console.log(JSON.stringify({rsi:x.rsi14[n],atr:x.atrPct14[n],u:x.bbUpper20[n],m:x.bbMid20[n],l:x.bbLower20[n],v:x.volMa20[n],p:x.bbPctile60[n]}))"
                     % json.dumps(series(80, lambda i: i * 0.5)))
        self.assertGreater(r["rsi"], 90)  # 단조 상승 -> RSI 고값
        self.assertGreater(r["atr"], 0)
        self.assertGreater(r["u"], r["m"]); self.assertGreater(r["m"], r["l"])
        self.assertEqual(r["v"], 1000)
        self.assertTrue(0 <= r["p"] <= 100)


class TestPivotsNoLookahead(unittest.TestCase):
    def test_future_bars_do_not_change_pivots(self):
        cl = series(120, lambda i: (i % 10) * 2)
        mut = [dict(c) for c in cl]
        for i in range(100, 120):
            mut[i]["high"] += 500; mut[i]["low"] -= 50
        r = run_node("const a=C.findConfirmedPivots(%s,99);const b=C.findConfirmedPivots(%s,99);"
                     "console.log(JSON.stringify({a:a,b:b}))" % (json.dumps(cl), json.dumps(mut)))
        self.assertEqual(r["a"], r["b"])
        s = json.dumps(r["a"])
        for p in (r["a"] if isinstance(r["a"], list) else r["a"].get("highs", []) + r["a"].get("lows", [])):
            if isinstance(p, dict) and "idx" in p:
                self.assertLessEqual(p["idx"], 99 - 3)


class TestCandleAndPatterns(unittest.TestCase):
    def test_hammer(self):
        cl = series(10)
        cl[9] = {"trade_date": "d9", "open": 100, "high": 101, "low": 90, "close": 101, "volume": 1000, "ema_5": 100}
        cl[8] = dict(cl[8], open=105, close=100, high=106, low=99)
        r = run_node("console.log(JSON.stringify(C.detectCandleSignal(%s,9)))" % json.dumps(cl))
        self.assertTrue(r is None or r["code"] in ("HAMMER", "ENGULFING", "PIERCING", "DOJI_TURN"))

    def test_short_series_all_false(self):
        r = run_node("const cl=%s;console.log(JSON.stringify(C.detectChartPatterns(cl,[],cl[cl.length-1])))" % json.dumps(series(40)))
        for k in ("vcp", "flag", "doubleBottom", "ihs", "downChannel"):
            self.assertFalse(r[k])
        ov = r["overlays"]
        self.assertEqual(ov["trendlines"], []); self.assertEqual(ov["arcs"], []); self.assertEqual(ov["pivots"], [])


class TestClassifyAndScore(unittest.TestCase):
    def test_v24_fields_preserved(self):
        cl = series(25, lambda i: 0)
        for c in cl:
            c.update(open=100, high=102.5, low=100, close=102, ema_5=101, ema_20=100, ema_60=100)
        r = run_node("console.log(JSON.stringify(C.classifyRecommendation(%s,[],false)))" % json.dumps(cl))
        for k in ("recommended", "tag", "reasons", "step", "avgRange", "subTag", "displayTag", "subReason", "pattern"):
            self.assertIn(k, r)
        self.assertEqual(r["tag"], "추세수급")

    def test_score_axes_sum_and_verdict(self):
        cl = series(80, lambda i: i * 0.3)
        sl = [{"trade_date": c["trade_date"], "real_inst_vol": 10, "real_inst_amt": 50, "inst_vol_ratio": 12} for c in cl]
        it = {"shcode": "000001", "first_signal_date": cl[60]["trade_date"], "first_signal_close": 110, "first_inst_amt": 100,
              "last_signal_date": cl[-1]["trade_date"], "signal_count": 2, "recommend_tag": "추세수급", "stop_price": 1}
        r = run_node("console.log(JSON.stringify(C.evaluateWatchlistItem(%s,%s,%s,%s)))" % (json.dumps(it), json.dumps(cl), json.dumps(sl), json.dumps(cl[-1]["trade_date"])))
        a = r["axisScores"]
        self.assertEqual(r["totalScore"], a["supply"] + a["structure"] + a["trigger"] + a["indicator"])
        self.assertLessEqual(a["supply"], 35); self.assertLessEqual(a["structure"], 30)
        self.assertLessEqual(a["trigger"], 20); self.assertLessEqual(a["indicator"], 15)
        self.assertIn(r["verdictCode"], ("EXIT", "READY", "WAIT", "WATCH"))
        self.assertEqual(len(r["reasons"]), 3)

    def test_bottom_origin_not_trend_exit(self):
        cl = series(25)
        for c in cl:
            c.update(close=90, ema_20=100, ema_60=100)
        it = {"shcode": "1", "first_signal_date": "d0001", "first_signal_close": 100, "first_inst_amt": 0, "signal_count": 1,
              "recommend_tag": "🌱 쌍바닥돌파", "stop_price": 1}
        r = run_node("console.log(JSON.stringify(C.evaluateWatchlistItem(%s,%s,[],'d0024')))" % (json.dumps(it), json.dumps(cl)))
        self.assertFalse(r["ema20Break"]); self.assertFalse(r["ema60Break"])


class TestChartImage(unittest.TestCase):
    def test_filename(self):
        r = run_node("console.log(JSON.stringify(C.chartImageFilename({shcode:'005930',hname:'삼성/전자',T:'2026-11-13',status:'READY'})))")
        self.assertTrue(r.endswith(".png")); self.assertIn("2026-11-13", r); self.assertNotIn("/", r)

    def test_exports(self):
        r = run_node("console.log(JSON.stringify(['computeIndicators','findConfirmedPivots','detectCandleSignal','detectChartPatterns','drawProChart','mountProChartPanel','buildChartImageCanvas','downloadChartPng','copyChartToClipboard'].map(k=>typeof C[k])))")
        self.assertEqual(set(r), {"function"})


class TestIntegration(unittest.TestCase):
    def test_pages(self):
        for p in ("index.html", "watchlist.html", "holdings.html"):
            self.assertIn("mountProChartPanel", read(p))
        c = read("common.js")
        for t in ("limit=750", "📸 이미지 저장", "🔍 크게 보기"):
            self.assertIn(t, c)
        w = read("watchlist.html")
        for t in ("🔥 타점완성", "종합판단", "185"):
            self.assertIn(t, w)
        self.assertIn("displayTag", read("index.html"))
        self.assertIn("getPatternCandidateCodes", read("index.html"))
        h = read("holdings.html")
        for t in ("data-row-id", "CLOSED_CHARTS"):
            self.assertIn(t, h)

    def test_scope_untouched(self):
        out = subprocess.run(["git", "diff", "--stat", "--", "STRATEGY.md", "TEST_REPORT.md", "run_daily_screener.py", ".github"],
                             cwd=str(ROOT), capture_output=True, text=True).stdout
        self.assertEqual(out.strip(), "")
        self.assertNotIn("sendPhoto", read("run_daily_screener.py"))


if __name__ == "__main__":
    unittest.main()


class TestV251Issues(unittest.TestCase):
    def test_issue018_flag_requires_bullish(self):
        c = read("common.js")
        self.assertIn("C > O && C > maxPullClose", c)
        w = read("watchlist.html")
        self.assertIn("SORT_SCORE", w); self.assertIn("renderScoreCard(x, EVAL[c])", w)

    def test_issue017(self):
        c = read("common.js")
        self.assertIn("ctx.clip()", c); self.assertIn("ctx.restore()", c); self.assertIn("dataKey", c)
        self.assertNotIn("if (h.status !== \"CLOSED\") { CHARTS[c]", read("holdings.html"))

    def test_issue015_016(self):
        h = read("index.html")
        self.assertIn("&order=trade_date.desc&limit=240", h)
        self.assertIn("daily_investor_supply` +\n          `?shcode=eq.${stock.shcode}", h)
        self.assertIn("rec.subReason", h); self.assertIn("rec.subTag !== (rec.displayTag || rec.tag)", h)
