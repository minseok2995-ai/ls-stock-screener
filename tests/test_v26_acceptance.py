"""v2.6 (AC-39 ~ AC-43): 1일 2회 배치, 패턴 상시 표기, 역배열 추세돌파/하락채널, 3페이지 초슬림 리스트."""
import datetime as dt, json, pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import run_daily_screener as R
from test_v25_pattern_chart import run_node, series, read

KST = dt.timezone(dt.timedelta(hours=9))


class TestBatchSlots(unittest.TestCase):
    def test_resolve_slot(self):
        self.assertEqual(R.resolve_batch_slot("auto", dt.datetime(2026, 11, 16, 18, 0, tzinfo=KST)), "prelim")
        self.assertEqual(R.resolve_batch_slot("auto", dt.datetime(2026, 11, 16, 19, 30, tzinfo=KST)), "final")
        self.assertEqual(R.resolve_batch_slot("final", dt.datetime(2026, 11, 16, 10, 0, tzinfo=KST)), "final")
        self.assertEqual(R.resolve_batch_slot("prelim", dt.datetime(2026, 11, 16, 21, 0, tzinfo=KST)), "prelim")

    def test_updated_at_tz_aware(self):
        m = "2026-11-16T20:00:00+09:00"
        self.assertFalse(R.is_updated_at_or_after("2026-11-16T07:05:00Z", m))  # 16:05 KST
        self.assertTrue(R.is_updated_at_or_after("2026-11-16T11:30:00+00:00", m))  # 20:30 KST
        self.assertFalse(R.is_updated_at_or_after(None, m))

    def test_yield_window(self):
        f = lambda h, mi, d=16: R.is_in_daily_yield_window(dt.datetime(2026, 11, d, h, mi, tzinfo=KST))
        self.assertFalse(f(15, 54)); self.assertTrue(f(15, 55)); self.assertTrue(f(16, 44)); self.assertFalse(f(16, 45))
        self.assertTrue(f(20, 30)); self.assertFalse(f(15, 55, 14))

    def test_workflow_and_gs(self):
        y = read(".github/workflows/daily_batch.yml")
        for c in ("5 7", "25 7", "30 11", "47 11", "17 12"):
            self.assertIn("'%s * * 1-5'" % c, y)
        self.assertIn("batch_slot", y); self.assertIn("--batch-slot", y)
        g = read("scripts/trigger_daily_batch.gs")
        self.assertIn("setupDaily1605And2030Triggers", g)
        s = read("run_daily_screener.py")
        self.assertIn("[1차 정규장 가집계]", s); self.assertIn("[2차 최종 확정]", s); self.assertIn("--batch-slot", s)


class TestPatternBadges(unittest.TestCase):
    def test_always_badge(self):
        for n in (0, 5, 70, 130):
            r = run_node("console.log(JSON.stringify(C.describeStockPattern(%s,[],'d9999')))" % json.dumps(series(n, lambda i: i * 0.3)))
            self.assertGreaterEqual(len(r["badges"]), 1)

    def test_exports(self):
        r = run_node("console.log(JSON.stringify([typeof C.describeStockPattern, typeof C.detectTurnaroundBreakout]))")
        self.assertEqual(r, ["function", "function"])

    def test_manual_tag_not_ema60_exit(self):
        cl = series(130, lambda i: 0)
        r = run_node("const it={shcode:'1',hname:'x',recommend_tag:'수동등록',first_signal_date:'d0100',first_signal_close:101,first_signal_low:50,stop_price:50,signal_count:1,grade:'B'};"
                     "const e=C.evaluateWatchlistItem(it,%s,[],'d0129');console.log(JSON.stringify({s:e.stopBreak,e60:e.ema60Break||false}))" % json.dumps(cl))
        self.assertFalse(r["e60"])


class TestSlimPages(unittest.TestCase):
    def test_pages(self):
        i, w, h = read("index.html"), read("watchlist.html"), read("holdings.html")
        for t in (i, w, h):
            self.assertIn("lg:items-stretch", t); self.assertIn("overflow-x-hidden", t)
            self.assertIn("lg:absolute lg:inset-0", t); self.assertIn("scrollbar-width: thin", t)
            self.assertIn("describeStockPattern", t)
        self.assertIn("detailBadgesBar", i)
        self.assertIn("lg:grid-cols-[490px_minmax(0,1fr)] xl:grid-cols-[520px_minmax(0,1fr)]", i)
        self.assertIn("lg:grid-cols-[395px_minmax(0,1fr)] xl:grid-cols-[410px_minmax(0,1fr)]", w)
        self.assertIn("lg:grid-cols-[380px_minmax(0,1fr)] xl:grid-cols-[400px_minmax(0,1fr)]", h)
        self.assertIn("-185", h)
        self.assertNotIn("buildRowBadges(item)}</td>", i)


if __name__ == "__main__":
    unittest.main()


class TestIssue019020(unittest.TestCase):
    def test_issue019_slim_tables(self):
        i, w = read("index.html"), read("watchlist.html")
        self.assertIn("text-[10.5px] tracking-tight", i)
        self.assertIn('id="screenerTableBody" class="divide-y divide-[var(--border)] text-[11px]"', i)
        self.assertIn("w-[6em] max-w-[6em]", i)
        self.assertIn("px-1 py-0.5 text-[10px]", i)
        head = i[i.index("<thead"):i.index("</thead>")]
        for old in ("px-3", "px-2.5", "px-2\""):
            self.assertNotIn(old, head)
        row = i[i.index("screener-row cursor-pointer"):i.index("renderStockDetail(selectedShcode);")]
        self.assertNotIn("px-2.5", row)
        self.assertIn("w-[7em] max-w-[7em]", w)
        self.assertIn('id="wlBody" class="divide-y divide-[var(--border)] text-[11px]"', w)
        self.assertNotIn("px-1.5 py-1.5", w)
        for t in ("💼 보유편입", "🗑️ 제외", "🚫 영구제외", "renderScoreCard(x, EVAL[c])"):
            self.assertIn(t, w)

    def test_issue020_panel_badges_and_filename(self):
        c = read("common.js")
        self.assertIn('data-role="badges"', c)
        self.assertIn("renderBadges", c)
        self.assertIn("[...new Set(state.badges", c)
        r = run_node("console.log(JSON.stringify(['🔄 a','🟦b','📈c','↗️d','📉e','🔨f','✨g','ℹ️h','🚀i'].map(x=>C.sanitizeFilePart?C.sanitizeFilePart(x):x)))")
        self.assertEqual(r, list("abcdefghi") if False else ["a", "b", "c", "d", "e", "f", "g", "h", "i"])

    def test_issue020_dedup_static(self):
        i, w = read("index.html"), read("watchlist.html")
        self.assertIn("[하락채널저항]", i); self.assertIn("syncRecommendationAfterLoad", i)
        self.assertIn("[...new Set(", i)
        self.assertIn("patternBadgesFor", w); self.assertIn("renderDetailHeader(x, EVAL[c])", w)
