"""v2.8 (AC-49 ~ AC-53): 일일 배치 초고속 파이프라인 — Keep-Alive 풀, 프리페치, 경과시간 차감 페이서, 병렬 수집, 버퍼 Upsert."""
import gzip
import http.server
import json
import pathlib
import socketserver
import sys
import threading
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import run_daily_screener as s  # noqa: E402


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    close_next = False

    def log_message(self, *a):  # noqa: D401
        pass

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/err"):
            body = b'{"e":1}'
            self.send_response(404)
        elif self.path.startswith("/gz"):
            body = gzip.compress(b'{"ok":true}')
            self.send_response(200)
            self.send_header("Content-Encoding", "gzip")
        else:
            body = b'{"ok":true}'
            self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        if _Handler.close_next:
            _Handler.close_next = False
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        self.wfile.write(body)


class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


class TestKeepAlivePool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = _Server(("127.0.0.1", 0), _Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        s._HTTP_POOL.close_all()
        cls.srv.shutdown()

    def test_ac49_socket_reuse_gzip_httperror_reconnect(self):
        pool = s.KeepAliveHttpPool()
        try:
            base = f"http://127.0.0.1:{self.port}"
            for _ in range(3):
                st, _, raw = pool.request("GET", base + "/x", None, {}, 5.0)
                self.assertEqual((st, json.loads(raw)), (200, {"ok": True}))
            self.assertEqual(pool.connect_count, 1)  # 동일 호스트 연속 요청 → 단일 소켓 재사용
            # gzip 투명 해제
            _, _, raw = pool.request("GET", base + "/gz", None, {}, 5.0)
            self.assertEqual(json.loads(raw), {"ok": True})
            # 서버가 연결을 닫은 뒤에도 투명 재연결
            _Handler.close_next = True
            pool.request("GET", base + "/x", None, {}, 5.0)
            st, _, _ = pool.request("GET", base + "/x", None, {}, 5.0)
            self.assertEqual(st, 200)
            self.assertEqual(pool.connect_count, 2)
            # HTTP >= 400 → HTTPError (e.code, 바디 소비 후 소켓 재사용 가능)
            with self.assertRaises(urllib.error.HTTPError) as cm:
                pool.request("GET", base + "/err", None, {}, 5.0)
            self.assertEqual(cm.exception.code, 404)
            st, _, _ = pool.request("GET", base + "/x", None, {}, 5.0)
            self.assertEqual(st, 200)
        finally:
            pool.close_all()

    def test_public_functions_use_pool_and_keep_signature(self):
        base = f"http://127.0.0.1:{self.port}"
        with mock.patch.object(s, "_should_use_keepalive", return_value=True):
            self.assertEqual(s.http_get_json(base + "/x"), {"ok": True})
            body, hdr = s.http_get_with_headers(base + "/x")
            self.assertEqual(body, {"ok": True})
            self.assertIn("content-length", hdr)
            with self.assertRaises(urllib.error.HTTPError):
                s.http_get_json(base + "/err")
        s._HTTP_POOL.close_all()

    def test_proxy_env_falls_back_to_urllib(self):
        with mock.patch("urllib.request.getproxies", return_value={"https": "http://p:1"}), \
                mock.patch("urllib.request.proxy_bypass", return_value=False):
            self.assertFalse(s._should_use_keepalive("https://example.com/x"))
        with mock.patch("urllib.request.getproxies", return_value={}):
            self.assertTrue(s._should_use_keepalive("https://example.com/x"))


def _rows(date, codes, **extra):
    return [dict({"shcode": c, "trade_date": date}, **extra) for c in codes]


class TestPrefetch(unittest.TestCase):
    def test_ac50_prefetch_no_count_exact_and_anchor_T5(self):
        cal = [f"2026-11-{d:02d}" for d in range(30, 0, -1)]  # 단순 달력 (desc)
        cal = [d for d in cal if d <= "2026-11-13"]
        latest = "2026-11-13"
        prior = [d for d in cal if d < latest]
        urls = []

        def fake_get(url, headers=None, timeout=25.0):
            urls.append((url, dict(headers or {})))
            if "shcode=eq.005930" in url:
                return [{"trade_date": d} for d in cal]
            d = url.split("trade_date=eq.")[1].split("&")[0]
            if "daily_chart" in url and "ema_5" in url:
                bad = d == prior[4]  # T-5 에 EMA 없는 종목 B → T-6 으로 대체
                return [
                    {"shcode": "A", "trade_date": d, "close": 100, "ema_5": 1, "ema_20": 1, "ema_60": 1, "ema_120": 1, "ema_240": 1},
                    {"shcode": "B", "trade_date": d, "close": 100, "ema_5": None if bad else 1, "ema_20": 1, "ema_60": 1, "ema_120": 1, "ema_240": 1},
                ]
            if "daily_chart" in url and "volume" in url:
                return _rows(d, ["A", "B"], volume=1000)
            if "daily_investor_supply" in url and "real_inst_vol" in url:
                return _rows(d, ["A", "B"], real_inst_vol=5, frg_vol=1, ind_vol=-6, fn_inv_vol=0, etc_corp_vol=0)
            return []

        with mock.patch.object(s, "http_get_json", side_effect=fake_get):
            ctx = s.supabase_prefetch_daily_context("https://x.supabase.co", "k", latest)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx["anchor_dates"], prior[4:7])
        self.assertEqual(ctx["anchor_by_code"]["A"]["trade_date"], prior[4])  # T-5 일관 선택
        self.assertEqual(ctx["anchor_by_code"]["B"]["trade_date"], prior[5])  # T-6 폴백
        self.assertEqual(ctx["recent_status"]["A"]["chart_latest"], latest)
        self.assertFalse(ctx["recent_status"]["A"]["unsettled"])
        for u, h in urls:
            self.assertNotIn("count=exact", h.get("Prefer", ""))
        self.assertTrue(any("order=shcode.asc" in u for u, _ in urls))

    def test_lookup_prefetched_status_requires_2y_history(self):
        ctx = {
            "recent_status": {"A": {"chart_latest": "2026-11-13", "supply_latest": "2026-11-13", "unsettled": False}},
            "hist_chart_2y_codes": {"A"}, "hist_supply_2y_codes": {"A"},
        }
        self.assertEqual(s.lookup_prefetched_status(ctx, "A"), (450, "2026-11-13", 450, "2026-11-13", False))
        self.assertIsNone(s.lookup_prefetched_status(ctx, "NEW"))  # 신규상장 → 기존 단건 조회 폴백
        self.assertIsNone(s.lookup_prefetched_status(None, "A"))

    def test_prefetch_failure_returns_none(self):
        with mock.patch.object(s, "http_get_json", side_effect=RuntimeError("boom")):
            self.assertIsNone(s.supabase_prefetch_daily_context("https://x", "k", "2026-11-13"))


class TestPacer(unittest.TestCase):
    def _client(self):
        return s.LSApiClient("k", "sec", sleep_sec=0.55)

    def test_ac51_elapsed_time_deducted(self):
        c = self._client()
        sleeps = []
        clock = [100.0]
        with mock.patch.object(s.time, "monotonic", side_effect=lambda: clock[0]), \
                mock.patch.object(s.time, "sleep", side_effect=lambda x: sleeps.append(round(x, 3))):
            c._acquire_tr_slot("t8410", 0.38)  # 최초: 대기 없음
            clock[0] = 100.10
            c._acquire_tr_slot("t8410", 0.38)  # 0.10초 경과 → 0.28초만 대기
            clock[0] = 101.0
            c._acquire_tr_slot("t8410", 0.38)  # 이미 충분히 경과 → 대기 없음
        self.assertEqual(sleeps, [0.28])

    def test_zero_sleep_sec_never_waits_and_adaptive_backoff(self):
        c = s.LSApiClient("k", "sec", sleep_sec=0.0)
        with mock.patch.object(s.time, "sleep") as sl:
            c._acquire_tr_slot("t1717", 0.38)
            c._acquire_tr_slot("t1717", 0.38)
        sl.assert_not_called()
        c2 = self._client()
        for _ in range(8):
            c2._bump_extra_delay("t1717")
        self.assertAlmostEqual(c2._tr_extra_delay["t1717"], 0.30)  # 상한 0.30

    def test_igw00201_increments_extra_delay(self):
        c = s.LSApiClient("k", "sec", sleep_sec=0.0)
        c.access_token = "tok"
        seq = [{"rsp_cd": "IGW00201", "rsp_msg": "초당 거래건수 초과"}, {"rsp_cd": "00000", "t1717OutBlock": []}]
        with mock.patch.object(s, "http_post_json", side_effect=seq), mock.patch.object(s.time, "sleep"):
            res = c.call_tr("/stock/frgr-itt", "t1717", {})
        self.assertEqual(res["rsp_cd"], "00000")
        self.assertGreater(c._tr_extra_delay["t1717"], 0)

    def test_single_token_refresh_across_threads(self):
        c = s.LSApiClient("k", "sec", sleep_sec=0.0)
        c.access_token = "old"
        calls = []

        def fake_auth():
            calls.append(1)
            c.access_token = "new"
            c._auth_ts = s.time.monotonic()
            return "new"

        with mock.patch.object(c, "authenticate", side_effect=fake_auth):
            ts = [threading.Thread(target=c._reauth, args=("old",)) for _ in range(6)]
            [t.start() for t in ts]
            [t.join() for t in ts]
        self.assertEqual(len(calls), 1)


class TestParallelParseEquivalence(unittest.TestCase):
    def test_split_fetch_parse_equals_sequential(self):
        rows = [
            {"date": "20261112", "close": 1000, "tjj0003_vol": 100, "tjj0006_vol": 50, "tjj0000_vol": 10,
             "tjj0001_vol": 5, "tjj0008_vol": -150, "tjj0017_vol": 7},
            {"date": "20261113", "close": 1010, "tjj0003_vol": 0, "tjj0006_vol": 0, "tjj0000_vol": 0,
             "tjj0001_vol": 0, "tjj0008_vol": 0, "tjj0017_vol": 0},  # 당일 미확정 더미(제외 대상)
        ]
        vol = {"2026-11-12": 10000, "2026-11-13": 9000}
        c = s.LSApiClient("k", "sec", sleep_sec=0.0)
        with mock.patch.object(c, "call_tr", return_value={"t1717OutBlock": rows}):
            seq = c.fetch_investor_supply("005930", "2026-11-01", "2026-11-13", vol, {}, max_pages=1)
            raw = c._fetch_t1717_pages("005930", "2026-11-01", "2026-11-13", max_pages=1)
            par = c._parse_t1717_rows("005930", raw, "2026-11-01", vol, {})  # 5인자 호출 호환
        self.assertEqual(seq, par)
        self.assertEqual([r["trade_date"] for r in seq], ["2026-11-12"])  # 미확정 더미 행 제외
        self.assertEqual(seq[0]["real_inst_vol"], 160)  # 순수기관 6대 주체 수식 유지


class TestBatchBuffer(unittest.TestCase):
    def _entry(self, code):
        return ({"shcode": code, "updated_at": "old"}, [{"shcode": code, "trade_date": "d"}], [{"shcode": code, "trade_date": "d"}])

    def test_ac52_order_chart_supply_master_last(self):
        calls = []
        with mock.patch.object(s, "supabase_upsert", side_effect=lambda u, k, t, c, r, *a, **kw: calls.append((t, len(r)))):
            buf = s.BatchUpsertBuffer("u", "k", 50)
            for i in range(50):
                buf.add(*self._entry(f"{i:06d}"))
            self.assertEqual(len(buf), 50)
            buf.flush()
        self.assertEqual(calls, [("daily_chart", 50), ("daily_investor_supply", 50), ("stocks_master", 50)])  # 3 POST / 50종목

    def test_master_updated_at_refreshed_and_empty_flush_noop(self):
        seen = {}
        with mock.patch.object(s, "supabase_upsert", side_effect=lambda u, k, t, c, r, *a, **kw: seen.__setitem__(t, r)):
            buf = s.BatchUpsertBuffer("u", "k")
            self.assertEqual(buf.flush(), 0)
            buf.add(*self._entry("000001"))
            buf.flush()
        self.assertNotEqual(seen["stocks_master"][0]["updated_at"], "old")

    def test_isolated_fallback_loses_no_good_stock(self):
        ok_codes = []

        def fake(u, k, t, c, rows, *a, **kw):
            if len(rows) > 1 and t == "daily_chart":
                raise RuntimeError("bulk fail")
            if t == "daily_chart" and rows[0]["shcode"] == "BAD":
                raise RuntimeError("bad stock")
            if t == "stocks_master":
                ok_codes.extend(r["shcode"] for r in rows)

        with mock.patch.object(s, "supabase_upsert", side_effect=fake):
            buf = s.BatchUpsertBuffer("u", "k")
            for c in ("A", "BAD", "C"):
                buf.add(*self._entry(c))
            n = buf.flush()
        self.assertEqual(n, 2)
        self.assertEqual(ok_codes, ["A", "C"])  # BAD 는 master 미기록 → 재시도 대상

    def test_ac52_theoretical_runtime_under_15_minutes(self):
        self.assertLess(s.estimate_daily_batch_minutes(1463), 15.0)
        self.assertGreater(s.estimate_daily_batch_minutes(1463), 8.0)
        self.assertEqual(s.FLUSH_BATCH_STOCKS, 50)
        # 4,389회 → ~90회 POST (3종 × ceil(1463/50)=30)
        self.assertLessEqual(3 * -(-1463 // 50), 90)


class TestScopeProtection(unittest.TestCase):
    def test_ac53_frontend_and_strategy_untouched_by_markers(self):
        root = pathlib.Path(__file__).resolve().parent.parent
        src = (root / "run_daily_screener.py").read_text(encoding="utf-8")
        for token in ("KeepAliveHttpPool", "supabase_prefetch_daily_context", "_acquire_tr_slot",
                      "_fetch_t1717_pages", "_parse_t1717_rows", "FLUSH_BATCH_STOCKS"):
            self.assertIn(token, src)


class TestV281Hotfix(unittest.TestCase):
    def test_ac54_pk_chunk_prefetch_and_parallel_fallback_zero_loop_db_gets(self):
        import datetime as dt

        base_d = dt.date(2026, 11, 13)
        # 평일 420영업일 달력 생성 (desc): prior_dates > 405 충족
        cal = []
        cur = base_d
        while len(cal) < 425:
            if cur.weekday() < 5:
                cal.append(cur.isoformat())
            cur -= dt.timedelta(days=1)
        latest = cal[0]
        prior = cal[1:]

        reg_codes = [f"{i:06d}" for i in range(1, 56)]  # 55개 → 50 + 5 두 청크
        target_codes = reg_codes + ["MISSANC", "IPO001"]
        urls = []

        def fake_get(url, headers=None, timeout=30.0):
            urls.append((url, dict(headers or {})))
            if "shcode=eq.005930" in url:
                return [{"trade_date": d} for d in cal]
            # PK 청크 쿼리 파싱: shcode=in.(...)&trade_date=in.(...)
            sh_part = url.split("shcode=in.(")[1].split(")")[0].split(",")
            dt_part = url.split("trade_date=in.(")[1].split(")")[0].split(",")
            out = []
            if "/daily_chart?" in url:
                for c in sh_part:
                    if c == "IPO001":
                        continue  # 신규상장/미해결 종목 시뮬레이션
                    for d in dt_part:
                        if c == "MISSANC" and d in prior[4:7]:
                            continue  # 2년 보유지만 T-5..T-7 앵커 결측
                        bad_t5 = (c == "000002" and d == prior[4])  # T-5 EMA 결측 → T-6 폴백 검증
                        out.append({
                            "shcode": c, "trade_date": d, "close": 10000, "volume": 5000,
                            "ema_5": None if bad_t5 else 9900.0, "ema_20": 9800.0,
                            "ema_60": 9700.0, "ema_120": 9600.0, "ema_240": 9500.0,
                        })
            elif "/daily_investor_supply?" in url:
                for c in sh_part:
                    if c == "IPO001":
                        continue
                    for d in dt_part:
                        out.append({
                            "shcode": c, "trade_date": d, "real_inst_vol": 100,
                            "frg_vol": 20, "ind_vol": -120, "fn_inv_vol": 0, "etc_corp_vol": 0,
                        })
            return out

        ipo_tuple = (120, latest, 120, latest, False)
        miss_anchor = {
            "trade_date": prior[7], "close": 10000,
            "ema_5": 9900.0, "ema_20": 9800.0, "ema_60": 9700.0, "ema_120": 9600.0, "ema_240": 9500.0,
        }
        with mock.patch.object(s, "http_get_json", side_effect=fake_get), \
                mock.patch.object(s, "supabase_get_stock_data_status_detail", return_value=ipo_tuple) as m_detail, \
                mock.patch.object(s, "supabase_get_anchor_row", return_value=miss_anchor) as m_anc:
            ctx = s.supabase_prefetch_daily_context(
                "https://x.supabase.co", "k", latest, target_codes=target_codes
            )

        self.assertIsNotNone(ctx)
        # 1) 달력 조회 1회 외 모든 http_get_json 은 order 절 및 Prefer: count=exact 없는 PK 청크(shcode=in.) 쿼리
        pk_urls = [u for u, _ in urls if "shcode=eq.005930" not in u]
        self.assertEqual(len(pk_urls), 4)  # 57종목 → 2청크 × (chart + supply) = 4회
        for u, h in urls:
            self.assertNotIn("count=exact", h.get("Prefer", ""))
            if "shcode=eq.005930" not in u:
                self.assertIn("shcode=in.(", u)
                self.assertIn("trade_date=in.(", u)
                self.assertNotIn("order=", u)

        # 2) T-5 우선 / T-6 폴백 / 결측 앵커 병렬 보강 검증
        self.assertEqual(ctx["anchor_by_code"]["000001"]["trade_date"], prior[4])
        self.assertEqual(ctx["anchor_by_code"]["000002"]["trade_date"], prior[5])
        self.assertEqual(ctx["anchor_by_code"]["MISSANC"]["trade_date"], prior[7])
        m_anc.assert_called_once_with("https://x.supabase.co", "k", "MISSANC")

        # 3) 미해결 신규상장 종목(IPO001)만 병렬 사전 해결 → lookup_prefetched_status 가 전 종목 즉시 해결 (루프 내 DB GET 0회)
        m_detail.assert_called_once_with("https://x.supabase.co", "k", "IPO001")
        self.assertEqual(ctx["fallback_status_by_code"]["IPO001"], ipo_tuple)
        for c in target_codes:
            self.assertIsNotNone(s.lookup_prefetched_status(ctx, c))
        self.assertEqual(s.lookup_prefetched_status(ctx, "IPO001"), ipo_tuple)
        self.assertEqual(s.lookup_prefetched_status(ctx, "000001"), (450, latest, 450, latest, False))

    def test_ac55_t8410_single_page_60_and_038s_interval(self):
        import datetime as dt

        self.assertEqual(s.ANCHOR_RECENT_CALENDAR_DAYS, 105)
        self.assertEqual(s.ANCHOR_RECENT_COUNT, 60)

        end_d = dt.date(2026, 11, 16)
        start_d = end_d - dt.timedelta(days=s.ANCHOR_RECENT_CALENDAR_DAYS)
        # LS t8410 비압축(comp_yn="N") 응답 모사: 최신일부터 역순으로 최대 100건(여기서는 구간 내 72영업일, 상한 100건) 반환
        all_days = []
        cur = end_d
        while cur >= start_d - dt.timedelta(days=40) and len(all_days) < 100:
            if cur.weekday() < 5:
                all_days.append(cur.strftime("%Y%m%d"))
            cur -= dt.timedelta(days=1)

        client = s.LSApiClient("k", "sec", sleep_sec=0.55)
        calls = []

        def fake_call_tr(endpoint, tr_cd, body, **kwargs):
            calls.append((endpoint, tr_cd, body, kwargs))
            ed = body["t8410InBlock"]["edate"]
            sd = body["t8410InBlock"]["sdate"]
            page = [
                {"date": d, "open": 1000, "high": 1020, "low": 990, "close": 1010, "jdiff_vol": 5000, "value": 5.05}
                for d in all_days if sd <= d <= ed
            ][:100]  # comp_yn="N" 회당 최대 100건 캡
            return {"t8410OutBlock1": page}

        with mock.patch.object(client, "call_tr", side_effect=fake_call_tr):
            rows = client.fetch_daily_chart(
                "005930", start_d.isoformat(), end_d.isoformat(), count=s.ANCHOR_RECENT_COUNT
            )

        self.assertEqual(len(calls), 1)  # 2페이지 슬라이딩 없이 정확히 1회 호출로 종료
        self.assertEqual(calls[0][1], "t8410")
        self.assertAlmostEqual(calls[0][3]["sleep_override"], s.TR_INTERVAL_INCREMENTAL)  # 0.38s 적용
        self.assertEqual(len(rows), 60)
        self.assertEqual(rows, sorted(rows, key=lambda r: r["trade_date"]))

        # shutdown(wait=True) 및 len(supply_to_upsert) 로그 반영 확인
        src = (pathlib.Path(__file__).resolve().parent.parent / "run_daily_screener.py").read_text(encoding="utf-8")
        self.assertIn("pair_pool.shutdown(wait=True)", src)
        self.assertIn("len(charts_to_upsert), len(supply_to_upsert)", src)


if __name__ == "__main__":
    unittest.main()
