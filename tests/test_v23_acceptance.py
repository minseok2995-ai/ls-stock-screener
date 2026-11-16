"""v2.3 (STRATEGY.md 6절) 수용 기준 AC-19 ~ AC-23 회귀 테스트."""
import datetime as dt
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import run_daily_screener as s  # noqa: E402

WORKFLOW = (ROOT / ".github" / "workflows" / "daily_batch.yml").read_text(encoding="utf-8")
SRC = (ROOT / "run_daily_screener.py").read_text(encoding="utf-8")


def _rows_page(dates):
    return {"t8410OutBlock1": [
        {"date": d, "open": 100, "high": 110, "low": 90, "close": 100, "jdiff_vol": 1000, "value": 1.0}
        for d in dates]}


class TestV23(unittest.TestCase):
    # ---- AC-19: probe ----
    def test_ac19_probe_mode_registered_no_db_write_and_log_format(self):
        self.assertIn('"probe_10y"', SRC)
        self.assertIn("[PROBE-10Y]", SRC)
        probe_src = SRC[SRC.index("def run_probe_10y"):SRC.index("def process_stock_10y")]
        self.assertNotIn("supabase_upsert", probe_src)

        client = mock.MagicMock()
        client.call_tr.return_value = {"t8410OutBlock1": [{"date": "20160104"}, {"date": "20160105"}]}
        rows = [{"trade_date": "2016-01-04", "itc_vol": 1, "pef_vol": 2, "pen_vol": 3, "frg_vol": 4, "fn_inv_vol": 5,
                 "ins_vol": 0, "etc_fin_vol": 0, "bank_vol": 0, "real_inst_vol": 6}]
        client.fetch_investor_supply.return_value = rows
        res = s.run_probe_10y(client)
        self.assertEqual(len(res), 3)
        self.assertEqual(res[0]["chart_first"], "2016-01-04")
        self.assertEqual(res[0]["verdict"], "OK")
        self.assertEqual(res[0]["formula_errors"], 0)

    def test_ac19_floor_search_when_2016_empty(self):
        client = mock.MagicMock()

        def fake(endpoint, tr, body, **kw):
            blk = body["t1717InBlock"]
            frm = blk["fromdt"]
            # 서버 수급 하한: 2019-05-02
            if frm >= "20190101" and blk["todt"] >= "20190502":
                d = max(frm, "20190502")
                return {"t1717OutBlock": [{"date": d}]}
            if frm >= "20190301" and frm <= "20190501" and blk["todt"] >= "20190502":
                return {"t1717OutBlock": [{"date": "20190502"}]}
            return {"t1717OutBlock": []}
        client.call_tr.side_effect = fake
        floor = s.find_supply_floor_for_stock(client, "005930")
        self.assertIsNotNone(floor)
        self.assertTrue(floor >= "2019-01-01")
        with mock.patch.object(s, "find_supply_floor_for_stock", return_value="2019-05-02"):
            self.assertEqual(s.detect_ls_server_history_floor(client), "2019-05-02")
        with mock.patch.object(s, "find_supply_floor_for_stock", return_value="2016-01-04"):
            self.assertEqual(s.detect_ls_server_history_floor(client), "2016-01-04")
        with mock.patch.object(s, "find_supply_floor_for_stock", return_value=None):
            self.assertEqual(s.detect_ls_server_history_floor(client), s.HISTORY_START_DATE)

    # ---- AC-20: 10y chart / EMA / anchor ----
    def test_ac20_fetch_daily_chart_pages_beyond_four(self):
        self.assertEqual(s.TARGET_10Y_CHART_COUNT, 3000)
        self.assertEqual(s.HISTORY_START_DATE, "2016-01-01")
        client = s.LSApiClient("k", "s")
        client.access_token = "x"
        base = dt.date(2026, 11, 12)
        state = {"n": 0}

        def fake(endpoint, tr, body, **kw):
            blk = body["t8410InBlock"]
            state["n"] += 1
            end = dt.datetime.strptime(blk["edate"], "%Y%m%d").date()
            ds = []
            d = end
            while len(ds) < 300:
                if d.weekday() < 5:
                    ds.append(d.strftime("%Y%m%d"))
                d -= dt.timedelta(days=1)
            return _rows_page(ds)
        with mock.patch.object(client, "call_tr", side_effect=fake):
            out = client.fetch_daily_chart("005930", "2016-01-01", base.isoformat(), count=3000)
        # 2016-01-01 이후 주중 영업일 약 2,800여 건이 10페이지 이내(기존 4페이지 한계 초과)로 수집되어야 함
        self.assertGreater(len(out), 2500)
        self.assertGreater(state["n"], 4)
        self.assertLessEqual(state["n"], 10)
        self.assertEqual(out[0]["trade_date"] >= "2016-01-01", True)

    def test_ac20_seeded_ema_equals_full_series(self):
        rows = [{"shcode": "X", "trade_date": (dt.date(2026, 1, 1) + dt.timedelta(days=i)).isoformat(),
                 "close": 1000 + (i * 37) % 211} for i in range(300)]
        full = s.compute_ema_series(rows)
        anchor = full[200]
        seeded = s.compute_ema_series(rows[201:], seed=anchor)
        for a, b in zip(full[201:], seeded):
            for span in s.EMA_SPANS:
                self.assertAlmostEqual(a[f"ema_{span}"], b[f"ema_{span}"], places=1)
            self.assertAlmostEqual(a["change_rate"], b["change_rate"], places=2)

    def test_ac20_anchor_ok_mismatch_missing(self):
        rows = [{"shcode": "X", "trade_date": f"2026-11-{d:02d}", "close": 1000 + d} for d in range(2, 13)]
        full = s.compute_ema_series(rows)
        anchor = dict(full[4])
        st, out = s.build_anchor_seeded_charts(rows, anchor)
        self.assertEqual(st, "ok")
        self.assertEqual(out[0]["trade_date"], full[5]["trade_date"])
        bad = dict(anchor, close=anchor["close"] * 2)
        self.assertEqual(s.build_anchor_seeded_charts(rows, bad)[0], "mismatch")
        self.assertEqual(s.build_anchor_seeded_charts(rows, dict(anchor, trade_date="2020-01-01"))[0], "missing")

    def test_ac20_daily_mismatch_triggers_10y_refetch(self):
        self.assertIn("[ANCHOR-MISMATCH]", SRC)
        self.assertIn("count=TARGET_10Y_CHART_COUNT", SRC)

    # ---- AC-21: backward delta + 2024-10 cutline ----
    def test_ac21_v231_defaults_and_needs_chart_fetch(self):
        self.assertEqual(s.CHART_HISTORY_START_DATE, "2021-11-01")
        self.assertEqual(s.SUPPLY_HISTORY_START_DATE, "2023-11-01")
        self.assertEqual(s.TWO_YEAR_CUT_OLD, "2024-10-20")
        self.assertEqual(s.RECENT_IPO_CUTLINE, "2024-11-15")
        n = s.needs_chart_fetch
        self.assertTrue(n(""))
        self.assertTrue(n("2024-10-24"))            # 2년 절단 종목
        self.assertTrue(n("2024-11-14"))
        self.assertFalse(n("2024-11-19"))           # 신규 상장 0초 스킵
        self.assertFalse(n("2021-11-10"))           # 이미 5년 적재
        self.assertFalse(n("2023-03-02"))           # 2023 상장
        # 무코드 10년 확장: 5년 절단선 종목도 확장 대상
        self.assertTrue(n("2021-11-01", "2016-01-01"))
        self.assertFalse(n("2016-01-04", "2016-01-01"))
        self.assertFalse(n("2021-11-01", "2021-11-01"))

    def test_ac21_history_completed_cases(self):
        tgt, rc = "2023-11-01", "2026-10-25"
        c = s.is_stock_history_completed
        self.assertTrue(c("2021-11-01", "2026-11-13", "2023-11-01", "2026-11-13", tgt, rc))
        self.assertFalse(c("2024-10-24", "2026-11-13", "2024-10-24", "2026-11-13", tgt, rc))  # 차트 확장 필요
        self.assertTrue(c("2025-03-05", "2026-11-13", "2025-03-05", "2026-11-13", tgt, rc))
        self.assertTrue(c("2024-04-15", "2026-11-13", "2024-04-15", "2026-11-13", tgt, rc))
        self.assertFalse(c("2021-11-01", "2026-11-13", "2024-10-24", "2026-11-13", tgt, rc))   # 수급 1년 미적재
        self.assertFalse(c("2021-11-01", "2026-11-13", "2023-11-01", "2026-11-13", tgt, rc, True))
        self.assertFalse(c("2021-11-01", "2026-11-13", "2023-11-01", "2026-01-01", tgt, rc))

    def test_ac21_halted_stock_not_unsettled(self):
        zero = {"trade_date": "2026-11-13", "real_inst_vol": 0, "frg_vol": 0, "ind_vol": 0, "fn_inv_vol": 0, "etc_corp_vol": 0}
        # 거래정지(volume==0): 정상
        self.assertFalse(s.resolve_supply_unsettled(zero, "2026-11-13", 0, "2026-11-13"))
        # 거래량 있는데 전 주체 0: 장중 미확정
        self.assertTrue(s.resolve_supply_unsettled(zero, "2026-11-13", 1000, "2026-11-13"))
        # 정상 거래정지 종목은 backward delta/완료 판정 정상
        st = {"supply_cnt": 480, "supply_oldest": "2024-10-24", "supply_latest": "2026-11-13", "is_latest_supply_unsettled": False}
        self.assertEqual(s.plan_supply_fetch(st, "2023-11-01", "2026-11-14", "2026-10-25")[0], "backward")

        def fake_get(url, headers=None, timeout=0):
            if "daily_chart" in url and "order=trade_date.desc" in url:
                self.assertIn("select=trade_date,volume", url)
                return [{"trade_date": "2026-11-13", "volume": 0}], {"content-range": "0-0/501"}
            if "daily_investor_supply" in url and "order=trade_date.desc" in url:
                return [zero], {"content-range": "0-0/501"}
            return [{"trade_date": "2024-10-24"}], {"content-range": "0-0/501"}
        with mock.patch.object(s, "http_get_with_headers", side_effect=fake_get):
            rs = s.supabase_get_stock_range_status("u", "k", "001570")
            self.assertFalse(rs["is_latest_supply_unsettled"])
            det = s.supabase_get_stock_data_status_detail("u", "k", "001570")
            self.assertFalse(det[4])

    def test_ac21_future_expansion_plan_2016(self):
        # chart_start=supply_start=2016-01-01 지정 시 무코드 재확장 계획
        st = {"supply_cnt": 740, "supply_oldest": "2023-11-01", "supply_latest": "2026-11-13", "is_latest_supply_unsettled": False}
        self.assertTrue(s.needs_chart_fetch("2021-11-01", "2016-01-01"))
        self.assertFalse(s.is_stock_history_completed("2021-11-01", "2026-11-13", "2023-11-01", "2026-11-13", "2016-01-01", "2026-10-25", False, "2016-01-01"))
        self.assertEqual(s.plan_supply_fetch(st, "2016-01-04", "2026-11-14", "2026-10-25"), ("backward", "2016-01-04", "2023-10-31"))

    def test_ac19_floor_first_window_is_20160131(self):
        client = mock.MagicMock()
        client.call_tr.return_value = {"t1717OutBlock": [{"date": "20160104"}]}
        self.assertEqual(s.find_supply_floor_for_stock(client, "005930"), "2016-01-04")
        body = client.call_tr.call_args[0][2]["t1717InBlock"]
        self.assertEqual((body["fromdt"], body["todt"]), ("20160101", "20160131"))

    def test_ac22_token_refresh_and_cli_args(self):
        self.assertIn('rsp_cd == "IGW00121"', SRC)
        self.assertIn('"--chart-start"', SRC)
        self.assertIn('"--supply-start"', SRC)
        self.assertIn("chart_start:", WORKFLOW)
        self.assertIn("supply_start:", WORKFLOW)
        self.assertIn("--chart-start", WORKFLOW)
        self.assertIn("-f chart_start=", WORKFLOW)

    def test_ac21_backward_delta_plan(self):
        today, rc = "2026-11-13", "2026-10-24"
        st = {"supply_cnt": 480, "supply_oldest": "2024-10-14", "supply_latest": "2026-11-12",
              "is_latest_supply_unsettled": False}
        kind, start, end = s.plan_supply_fetch(st, "2016-01-04", today, rc)
        self.assertEqual((kind, start, end), ("backward", "2016-01-04", "2024-10-13"))
        self.assertIsNone(s.plan_supply_fetch(dict(st, supply_oldest="2016-01-05"), "2016-01-04", today, rc))
        k2 = s.plan_supply_fetch(dict(st, supply_cnt=20), "2016-01-04", today, rc)
        self.assertEqual(k2, ("full", "2016-01-04", today))
        self.assertEqual(s.SUPPLY_MAX_PAGES_10Y, 135)
        self.assertEqual(s.compute_target_supply_start("2019-05-02", "2016-01-04"), "2019-05-02")
        self.assertEqual(s.compute_target_supply_start("2016-01-04", "2025-03-05"), "2025-03-05")

    def test_ac21_exception_does_not_mark_complete(self):
        st = {"error": True}
        with self.assertRaises(RuntimeError):
            s.process_stock_10y(mock.MagicMock(), "u", "k", "005930", st, "2016-01-04", "2026-11-13", "2026-10-24")

    def test_ac21_daily_completion_not_gated_by_2400(self):
        self.assertNotIn("chart_cnt >= 2400", SRC)
        self.assertTrue(s.is_stock_already_backfilled(480, "2026-11-12", 480, "2026-11-12", min_target_date="2026-10-24"))

    # ---- AC-22: yield / chain ----
    def test_ac22_yield_window_guard(self):
        kst = s.KST_TZ
        wd = dt.datetime(2026, 11, 12, 20, 30, tzinfo=kst)  # Thursday
        self.assertTrue(s.is_in_daily_yield_window(wd))
        self.assertTrue(s.is_in_daily_yield_window(wd.replace(hour=20, minute=10)))
        self.assertFalse(s.is_in_daily_yield_window(wd.replace(hour=21, minute=20)))
        self.assertFalse(s.is_in_daily_yield_window(wd.replace(hour=19, minute=59)))
        self.assertFalse(s.is_in_daily_yield_window(dt.datetime(2026, 11, 14, 20, 30, tzinfo=kst)))  # Saturday

    def test_ac22_workflow_modes_chain_permissions_crons(self):
        self.assertIn("backfill_10y", WORKFLOW)
        self.assertIn("probe_10y", WORKFLOW)
        self.assertIn("chain_round", WORKFLOW)
        self.assertRegex(WORKFLOW, r"permissions:\s*\n\s+actions:\s*write")
        self.assertIn("needs_resume == 'true'", WORKFLOW)
        self.assertIn("gh workflow run", WORKFLOW)
        crons = re.findall(r"-\s*cron:\s*'([^']+)'", WORKFLOW)
        self.assertEqual(crons, ["5 7 * * 1-5", "25 7 * * 1-5", "30 11 * * 1-5", "47 11 * * 1-5", "17 12 * * 1-5"])
        self.assertIn("누적 완주", SRC)
        self.assertIn("다음 회차 자동 이어받기 실행", SRC)

    def test_ac22_argparse_choices(self):
        m = re.search(r'choices=\[([^\]]+)\]', SRC[SRC.index("__main__"):])
        for mode in ("daily", "backfill", "backfill_10y", "probe_10y", "universe", "verify"):
            self.assertIn(f'"{mode}"', m.group(1))

    # ---- AC-23: no delete / verify ----
    def test_ac23_no_history_delete_and_verify_format(self):
        blk = SRC[SRC.index("def supabase_get_stock_range_status"):SRC.index("# 5. 메인 배치 파이프라인")]
        self.assertNotIn("DELETE", blk)
        self.assertNotIn("method=\"DELETE\"", blk)
        self.assertIn("시계열 적재 현황 (최초일 ~ 최신일, 총 영업일수)", SRC)
        self.assertIn("AC-1~AC-23", SRC)


if __name__ == "__main__":
    unittest.main()
