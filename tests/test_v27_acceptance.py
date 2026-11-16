"""v2.7 (AC-44 ~ AC-48): 상단 슬림화, 실시간 시세 엔진/브리지, 거래량 전일비, 프로 차트 실시간 봉."""
import http.client, json, pathlib, re, sys, threading, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
from test_v25_pattern_chart import run_node, series, read

ROOT = pathlib.Path(__file__).resolve().parent.parent


def bar(d, close, vol, o=None, e=None):
    e = e if e is not None else close
    return {"trade_date": d, "open": o or close, "high": close + 5, "low": close - 5, "close": close, "volume": vol,
            "ema_5": e, "ema_20": e, "ema_60": e, "ema_120": e, "ema_240": e}


CL = [bar("2026-11-12", 100, 400), bar("2026-11-13", 105, 512323)]


class TestAC44Layout(unittest.TestCase):
    def test_index_single_header(self):
        i = read("index.html")
        self.assertIn("<h1 class=\"text-sm md:text-base font-bold tracking-tight whitespace-nowrap ml-1\">기관 수급 종목 스크리너</h1>", i)
        self.assertIn("순수 기관 = 금융투자를 제외한 투신 + 보험 + 은행 + 종금(기타금융) + 연기금 등 + 사모펀드", i)
        head = i[i.index("<header"):i.index("</header>")]
        for t in ('id="commonNav"', 'id="lastTradeDateBadge"', 'id="liveQuoteStatusBtn"'):
            self.assertIn(t, head)
        self.assertEqual(i.count("<header"), 1)
        self.assertIn("space-y-2", i); self.assertIn("p-2 md:px-4 md:py-2.5", i)
        self.assertIn("whitespace-nowrap", i[i.index('id="btnMergeWatchlist"') - 200:i.index('id="btnExportExcel"') + 300])
        self.assertIn('id="chartCandleCountLabel" class="hidden"', i)
        self.assertNotIn("grid grid-cols-5 gap-1.5 mt-3", i)
        for k in ("5", "20", "60", "120", "240"):
            self.assertIn('id="emaVal%s"' % k, i)
        self.assertIn("hideInlineBadges: true", i)
        self.assertIn("Math.max(480, Math.min(640, (window.innerHeight || 920) - 330))", i)

    def test_wl_hd_banner_removed(self):
        w, h = read("watchlist.html"), read("holdings.html")
        self.assertNotIn("⭐ 관심종목 작전판", w); self.assertNotIn("💼 보유종목 &amp; 청산 히스토리", h)
        for t, ids in ((w, ("wlDateBadge", "wlLiveStatusBtn", "commonNav")), (h, ("hdDateBadge", "hdLiveStatusBtn", "commonNav"))):
            head = t[t.index("<header"):t.index("</header>")]
            for i in ids:
                self.assertIn('id="%s"' % i, head)
            self.assertIn("hideInlineBadges: true", t)

    def test_nav_and_hide_option(self):
        c = read("common.js")
        self.assertNotIn('"flex flex-wrap items-center gap-2 mb-3"', c)
        self.assertIn("px-2.5 py-1 rounded-lg text-xs font-semibold", c)
        for t in ("🔍 수급 스크리너", "⭐ 관심종목", "💼 보유종목", "🚫 제외관리"):
            self.assertIn(t, c)
        self.assertIn("po.hideInlineBadges", c); self.assertIn('data-role="badges"', c); self.assertIn("st.shownBadges", c)


class TestAC45Engine(unittest.TestCase):
    def test_no_hardcoded_secrets(self):
        for f in ("common.js", "index.html", "watchlist.html", "holdings.html", "scripts/ls_realtime_bridge.py"):
            t = read(f)
            self.assertIsNone(re.search(r"(LS_APP_(KEY|SECRET)\s*=\s*['\"][^'\"]+['\"])", t))
        self.assertIn("os.environ.get(\"LS_APP_KEY\"", read("scripts/ls_realtime_bridge.py"))

    def test_bridge_stdlib_and_headers(self):
        src = read("scripts/ls_realtime_bridge.py")
        self.assertIn("Access-Control-Allow-Private-Network", src)
        mods = set(re.findall(r"^(?:import|from)\s+([a-zA-Z_\.]+)", src, re.M))
        std = {"json", "os", "sys", "threading", "time", "urllib.parse", "urllib.request", "http.server"}
        self.assertTrue(mods <= std, mods - std)
        import ls_realtime_bridge as B
        from http.server import ThreadingHTTPServer
        srv = ThreadingHTTPServer(("127.0.0.1", 0), B.Handler)
        port = srv.server_address[1]
        th = threading.Thread(target=srv.serve_forever, daemon=True); th.start()
        try:
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            c.request("GET", "/health"); r = c.getresponse(); body = json.loads(r.read())
            self.assertTrue(body["ok"])
            self.assertEqual(r.getheader("Access-Control-Allow-Private-Network"), "true")
            self.assertEqual(r.getheader("Access-Control-Allow-Origin"), "*")
            c.request("OPTIONS", "/quote"); r = c.getresponse(); r.read()
            self.assertEqual(r.status, 204)
            self.assertEqual(r.getheader("Access-Control-Allow-Private-Network"), "true")
        finally:
            srv.shutdown(); srv.server_close()

    def test_preopen_guard(self):
        r = run_node("const q={price:105,tradeDate:'2026-11-16',open:0,volume:0};"
                     "console.log(JSON.stringify({pre:C.isPreOpenEmptyQuote(q,'2026-11-13'),ok:C.isPreOpenEmptyQuote({price:110,tradeDate:'2026-11-16',open:100,volume:5},'2026-11-13'),"
                     "n:C.mergeLiveQuoteIntoCandles(%s,q).length}))" % json.dumps(CL))
        self.assertTrue(r["pre"]); self.assertFalse(r["ok"]); self.assertEqual(r["n"], 2)

    def test_naver_parse_and_jsonp_cleanup(self):
        prog = r"""
const resp={result:{time:Date.UTC(2026,10,16,1,0,0),areas:[{datas:[{cd:'003570',nv:30350,ov:28000,hv:31000,lv:27900,pcv:27750,cv:2600,cr:9.37,rf:'2',aq:220043,ms:'OPEN'},
 {cd:'064960',nv:900,ov:0,hv:0,lv:0,pcv:1000,cv:100,cr:10,rf:'5',aq:0,ms:'CLOSE'}]}]}};
const q=C.LiveQuoteManager.parseNaverRealtime(resp);
const scripts=[];
globalThis.document={createElement:()=>({parentNode:null,set src(v){this._s=v;scripts.push(this)}}),head:{appendChild(s){s.parentNode=this;const m=/_callback=([^&]+)/.exec(s._s)[1];setTimeout(()=>globalThis[m](resp),0)},removeChild(s){s.parentNode=null;s.removed=true}}};
C.LiveQuoteManager.fetchNaver(['003570']).then(r=>{
 const left=Object.keys(globalThis).filter(k=>k.startsWith('__lsq_'));
 console.log(JSON.stringify({a:q['003570'],b:q['064960'],got:Object.keys(r),removed:scripts[0].removed===true,left:left.length}));
 process.exit(0);});
"""
        r = run_node(prog)
        self.assertEqual(r["a"]["tradeDate"], "2026-11-16"); self.assertEqual(r["a"]["diff"], 2600); self.assertEqual(r["b"]["diff"], -100)
        self.assertEqual(r["b"]["changeRate"], -10)
        self.assertIn("003570", r["got"]); self.assertTrue(r["removed"]); self.assertEqual(r["left"], 0)

    def test_tier3_no_upper_bound_and_node_no_timers(self):
        c = read("common.js")
        seg = c[c.index("async function fetchSupabaseLatest"):c.index("// Tier 4")]
        self.assertNotIn("trade_date=lte", seg); self.assertIn("limit=2", seg)
        self.assertIn("polling.finance.naver.com/api/realtime", c); self.assertIn("2500", c)
        self.assertIn("4000", c)
        r = run_node("console.log(JSON.stringify(typeof C.LiveQuoteManager.start))")
        self.assertEqual(r, "function")


class TestAC46Metrics(unittest.TestCase):
    def test_vol_ratio(self):
        r = run_node("console.log(JSON.stringify(C.computeQuoteMetrics(%s,{price:30350,tradeDate:'2026-11-16',open:1,volume:220043,prevVolume:512323,prevClose:27750})))" % json.dumps(CL))
        self.assertEqual(r["volRatioPct"], 42.95); self.assertEqual(r["diff"], 2600); self.assertEqual(r["changeRate"], 9.37)
        r = run_node("console.log(JSON.stringify(C.computeQuoteMetrics(%s,null)))" % json.dumps(CL))
        self.assertEqual(r["volume"], 512323); self.assertEqual(r["prevVolume"], 400)
        z = [bar("a", 100, 0), bar("b", 100, 5)]
        r = run_node("console.log(JSON.stringify(C.computeQuoteMetrics(%s,null)))" % json.dumps(z))
        self.assertIsNone(r["volRatioPct"])

    def test_headers_static(self):
        i, w, h = read("index.html"), read("watchlist.html"), read("holdings.html")
        for t in ("detailDiff", "detailVolume", "detailVolRatio", "detailLiveBadge", "text-lg md:text-xl font-extrabold"):
            self.assertIn(t, i)
        for t in ("wlDetailVolume", "wlDetailVolRatio", "wlDetailLiveBadge", "evalWithLive", "evaluateWatchlistItem"):
            self.assertIn(t, w)
        for t in ("hdDetailVolume", "hdDetailVolRatio", "evalHoldingLive", "청산 확정치"):
            self.assertIn(t, h)
        self.assertIn('h.status !== "CLOSED") startLive', h)


class TestAC47Merge(unittest.TestCase):
    def test_new_bar_and_immutable(self):
        r = run_node("const cl=%s;const snap=JSON.stringify(cl);const q={price:110,tradeDate:'2026-11-16',volume:7};"
                     "const m=C.mergeLiveQuoteIntoCandles(cl,q);console.log(JSON.stringify({len:m.length,same:JSON.stringify(cl)===snap,last:m[2]}))" % json.dumps(CL))
        self.assertEqual(r["len"], 3); self.assertTrue(r["same"])
        last = r["last"]
        self.assertEqual((last["open"], last["high"], last["low"], last["close"]), (110, 110, 110, 110))
        self.assertAlmostEqual(last["ema_5"], 110 * 2 / 6 + 105 * 4 / 6, places=6)
        self.assertAlmostEqual(last["ema_20"], 110 * 2 / 21 + 105 * 19 / 21, places=6)
        self.assertTrue(last["_live"])

    def test_same_day_update(self):
        r = run_node("const m=C.mergeLiveQuoteIntoCandles(%s,{price:120,high:125,low:90,open:104,tradeDate:'2026-11-13',volume:600000});console.log(JSON.stringify([m.length,m[1]]))" % json.dumps(CL))
        self.assertEqual(r[0], 2)
        b = r[1]
        self.assertEqual((b["close"], b["high"], b["low"], b["volume"]), (120, 125, 90, 600000))
        self.assertAlmostEqual(b["ema_5"], 120 * 2 / 6 + 100 * 4 / 6, places=6)

    def test_panel_update_live_and_pricetag(self):
        c = read("common.js")
        self.assertIn("updateLive(u)", c); self.assertIn("viewCandles()", c)
        self.assertIn("setLineDash([2, 3])", c); self.assertIn("cssW - Rm + 2", c)
        prog = r"""
const mk=()=>new Proxy(function(){}, {get:(t,k)=>k==='measureText'?()=>({width:10}):(k==='canvas'?{}:mk()), apply:()=>mk(), set:()=>true});
const els={};
const el=(k)=>els[k]||(els[k]={_h:'',classList:{add(){}},style:{},clientWidth:600,addEventListener(){},getContext:()=>mk(),getBoundingClientRect:()=>({left:0,width:600}),set innerHTML(v){this._h=v},get innerHTML(){return this._h},querySelector(){return null}});
const cont={innerHTML:'',clientWidth:600,querySelector:s=>el(s)};
const P=C.mountProChartPanel(cont,{height:300,period:120,hideInlineBadges:true});
const cl=%s;
P.setData({shcode:'1',hname:'x',candles:cl,supplies:[],T:'2026-11-13',lines:[],markers:[],badges:[],status:''});
P.state.period=60; P.state.layers.pattern=false;
P.updateLive({liveQuote:{price:111,tradeDate:'2026-11-16',volume:9}});
console.log(JSON.stringify({period:P.state.period,pattern:P.state.layers.pattern,q:P.state.liveQuote.price,base:P.state.candles.length}));
""" % json.dumps(CL)
        r = run_node(prog)
        self.assertEqual(r, {"period": 60, "pattern": False, "q": 111, "base": 2})


class TestAC48Regression(unittest.TestCase):
    def test_scripts_valid_and_ids(self):
        for p in ("index.html", "watchlist.html", "holdings.html"):
            t = read(p)
            ids = set(re.findall(r'id="([^"]+)"', t))
            for m in re.findall(r'getElementById\("([^"]+)"\)', t):
                self.assertIn(m, ids, (p, m))


if __name__ == "__main__":
    unittest.main()


class TestIssue021022(unittest.TestCase):
    def _bars(self):
        import json as _j
        def bar(d, o, h, l, c, v):
            return {"trade_date": d, "open": o, "high": h, "low": l, "close": c, "volume": v, "change_rate": 0,
                    "ema_5": c, "ema_20": c, "ema_60": c, "ema_120": c, "ema_240": c}
        return _j.dumps([bar("2026-11-12", 100, 105, 99, 100, 1000), bar("2026-11-13", 101, 110, 100, 108, 2000)])

    def test_weekend_snapshot_not_duplicated(self):
        from test_v25_pattern_chart import run_node
        r = run_node("const cl=%s;const q={price:108,open:101,high:110,low:100,volume:2000,prevClose:100,tradeDate:'2026-11-15',marketState:'CLOSE'};"
                     "const m=C.computeQuoteMetrics(cl,q);const mg=C.mergeLiveQuoteIntoCandles(cl,q);"
                     "console.log(JSON.stringify({n:mg.length,r:m.volRatioPct,d:m.tradeDate,cr:m.changeRate}))" % self._bars())
        self.assertEqual(r["n"], 2); self.assertEqual(r["r"], 200.0); self.assertEqual(r["d"], "2026-11-13"); self.assertEqual(r["cr"], 8.0)

    def test_holiday_weekday_same_snapshot_and_open_live(self):
        from test_v25_pattern_chart import run_node
        r = run_node("const cl=%s;const q={price:108,open:101,high:110,low:100,volume:2000,prevClose:108,tradeDate:'2026-11-16',marketState:'CLOSE'};"
                     "const live={price:112,open:109,high:113,low:108,volume:500,prevClose:108,tradeDate:'2026-11-16',marketState:'OPEN'};"
                     "console.log(JSON.stringify({a:C.mergeLiveQuoteIntoCandles(cl,q).length,b:C.mergeLiveQuoteIntoCandles(cl,live).length}))" % self._bars())
        self.assertEqual(r, {"a": 2, "b": 3})

    def test_naver_weekend_and_preopen_dates(self):
        from test_v25_pattern_chart import run_node
        # 2026-11-14 토 10:00 KST, 2026-11-16 월 08:00 KST, 2026-11-17 화 08:00 KST, 월 10:00
        r = run_node("const mk=(iso,ms)=>({result:{time:Date.parse(iso),areas:[{datas:[{cd:'005930',nv:1,cv:0,cr:0,rf:'3',ov:1,hv:1,lv:1,aq:1,ms}]}]}});"
                     "const f=(iso,ms)=>C.LiveQuoteManager.parseNaverRealtime(mk(iso,ms))['005930'].tradeDate;"
                     "console.log(JSON.stringify([f('2026-11-14T10:00:00+09:00','CLOSE'),f('2026-11-16T08:00:00+09:00','CLOSE'),f('2026-11-17T08:00:00+09:00','CLOSE'),f('2026-11-16T10:00:00+09:00','OPEN')]))")
        self.assertEqual(r, ["2026-11-13", "2026-11-13", "2026-11-16", "2026-11-16"])

    def test_issue022_static_and_bridge(self):
        c = read("common.js")
        self.assertIn("d.liveQuote !== undefined", c)
        self.assertIn("candles: viewCandles()", c)
        self.assertIn("h.configured !== false", c)
        self.assertIn("C.LiveQuoteManager.stop(); LIVE = { code: \"\", quote: null };", read("holdings.html"))
        import importlib.util, time as _t
        spec = importlib.util.spec_from_file_location("brg", str(__import__("pathlib").Path(__file__).resolve().parent.parent / "scripts/ls_realtime_bridge.py"))
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        kst = lambda s: __import__("calendar").timegm(_t.strptime(s, "%Y-%m-%d %H:%M")) - 9 * 3600
        self.assertEqual(m._kst_trade_date(kst("2026-11-14 10:00")), "2026-11-13")
        self.assertEqual(m._kst_trade_date(kst("2026-11-15 10:00")), "2026-11-13")
        self.assertEqual(m._kst_trade_date(kst("2026-11-16 08:00")), "2026-11-13")
        self.assertEqual(m._kst_trade_date(kst("2026-11-17 08:00")), "2026-11-16")
        self.assertEqual(m._kst_trade_date(kst("2026-11-17 10:00")), "2026-11-17")
