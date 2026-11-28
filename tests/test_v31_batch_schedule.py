#!/usr/bin/env python3
"""
v3.1 (STRATEGY.md 17절, AC-67 ~ AC-71) 운영 안정화 검증 스위트:
- AC-67: 비정상 시간대(평일 00:00~15:44 · 19:00~20:04 KST · 주말) 자동 실행 즉시 무음 스킵,
         장전 빈 일봉(jdiff_vol=0, open=0) 및 15:30 KST 이전 당일 봉 제외, universe_count==0 텔레그램 발송 금지
- AC-68: 평일 daily 모드 기존 분기 유니버스(is_universe=True) 시총 700억 일시 하회 시 정상 적재,
         전수 분기 재산출(rebuild_due=True) 시 탈락 종목 DELETE 없이 is_universe=False 동기화 · KST 월 판별 · 프리페치 지원
- AC-69: t1463 신규 급등주 루프 전 시드 마스터 선등록(updated_at=1970-01-01...) 및 BatchUpsertBuffer HTTP 409 자가 복구,
         상장 65영업일 이하 신규 상장주(8일/8일, 40일/40일 등) 백필 완료 인정 + 초신규(<=5일) 1페이지 차트 조회
- AC-70: daily_batch.yml 2중 백업 크론('25 7 * * 1-5', '47 11 * * 1-5') 슬림화 및 극소량(0<=vol<=100) 기적재 종목 완료 인정
- AC-71: 프론트엔드 3페이지·common.js·DB 스키마·STRATEGY.md·TEST_REPORT.md 무변경 원칙 검증
"""
import datetime as dt
import io
import os
import pathlib
import re
import subprocess
import tempfile
import unittest
import urllib.error
from unittest import mock

import run_daily_screener as s

ROOT = pathlib.Path(__file__).resolve().parent.parent
KST = s.KST_TZ


def _make_chart_rows(shcode: str, dates: list[str], close: int = 10000, vol: int = 50000) -> list[dict]:
    return [
        {
            "shcode": shcode,
            "trade_date": d,
            "open": close - 100,
            "high": close + 150,
            "low": close - 150,
            "close": close,
            "change_rate": 1.0,
            "volume": vol,
            "trading_value_m": round((close * vol) / 1_000_000.0, 2),
        }
        for d in dates
    ]


def _make_supply_rows(shcode: str, dates: list[str], inst_ratio: float = 12.0) -> list[dict]:
    return [
        {
            "shcode": shcode,
            "trade_date": d,
            "real_inst_vol": 6000,
            "real_inst_amt": 600.0,
            "inst_vol_ratio": inst_ratio,
            "frg_vol": 1000,
            "frg_amt": 100.0,
            "frg_vol_ratio": 2.0,
            "ind_vol": -7000,
            "ind_amt": -700.0,
            "fn_inv_vol": 0,
            "fn_inv_amt": 0.0,
            "etc_corp_vol": 0,
            "etc_corp_amt": 0.0,
            "itc_vol": 6000,
            "itc_amt": 600.0,
            "pef_vol": 0,
            "pef_amt": 0.0,
            "pen_vol": 0,
            "pen_amt": 0.0,
            "ins_vol": 0,
            "ins_amt": 0.0,
            "etc_fin_vol": 0,
            "etc_fin_amt": 0.0,
            "bank_vol": 0,
            "bank_amt": 0.0,
        }
        for d in dates
    ]


class TestAC67OffHoursAndPremarketGuard(unittest.TestCase):
    def test_ac67_is_allowed_auto_batch_window_boundaries(self) -> None:
        # 평일(월~금: 2026-11-23 월 ~ 2026-11-27 금) 전 구간 경계 검증
        for day in range(23, 28):
            # 차단 1: 평일 00:00 ~ 15:44 KST
            for h, m in ((0, 0), (2, 16), (5, 23), (5, 30), (6, 58), (9, 0), (15, 29), (15, 44)):
                ok, reason = s.is_allowed_auto_batch_window(dt.datetime(2026, 11, day, h, m, tzinfo=KST))
                self.assertFalse(ok, f"weekday {day} {h:02d}:{m:02d} must be blocked")
                self.assertIn("00:00~15:44", reason)

            # 허용 1 (prelim): 평일 15:45 ~ 18:59 KST (16:05, 16:25, 수능일 17:05 포함)
            for h, m in ((15, 45), (16, 5), (16, 25), (17, 5), (18, 59)):
                ok, _ = s.is_allowed_auto_batch_window(dt.datetime(2026, 11, day, h, m, tzinfo=KST))
                self.assertTrue(ok, f"weekday {day} {h:02d}:{m:02d} must be allowed")

            # 차단 2 (NXT 데드존): 평일 19:00 ~ 20:04 KST
            for h, m in ((19, 0), (19, 30), (19, 59), (20, 0), (20, 4)):
                ok, reason = s.is_allowed_auto_batch_window(dt.datetime(2026, 11, day, h, m, tzinfo=KST))
                self.assertFalse(ok, f"weekday {day} {h:02d}:{m:02d} deadzone must be blocked")
                self.assertIn("19:00~20:04", reason)

            # 허용 2 (final): 평일 20:05 ~ 23:59 KST (20:30, 20:47, 21:17 포함)
            for h, m in ((20, 5), (20, 30), (20, 47), (21, 17), (23, 59)):
                ok, _ = s.is_allowed_auto_batch_window(dt.datetime(2026, 11, day, h, m, tzinfo=KST))
                self.assertTrue(ok, f"weekday {day} {h:02d}:{m:02d} final must be allowed")

        # 차단 3: 토요일(28일)·일요일(29일) 전 시간대 차단
        for wknd_day in (28, 29):
            for h, m in ((0, 0), (3, 0), (16, 5), (17, 5), (20, 30), (20, 47), (23, 59)):
                ok, reason = s.is_allowed_auto_batch_window(dt.datetime(2026, 11, wknd_day, h, m, tzinfo=KST))
                self.assertFalse(ok, f"weekend {wknd_day} {h:02d}:{m:02d} must be blocked")
                self.assertIn("주말", reason)

        # UTC 타임존 입력 시 KST 자동 변환 확인 (07:05 UTC = 16:05 KST 허용 / 18:00 UTC = 익일 03:00 KST 차단)
        self.assertTrue(
            s.is_allowed_auto_batch_window(dt.datetime(2026, 11, 25, 7, 5, tzinfo=dt.timezone.utc))[0]
        )
        self.assertFalse(
            s.is_allowed_auto_batch_window(dt.datetime(2026, 11, 24, 18, 0, tzinfo=dt.timezone.utc))[0]
        )

    def test_ac67_offhours_auto_batch_skips_with_zero_auth_db_telegram(self) -> None:
        blocked_times = [
            dt.datetime(2026, 11, 25, 3, 15, tzinfo=KST),   # 평일 새벽 지연 크론
            dt.datetime(2026, 11, 25, 5, 23, tzinfo=KST),   # LS 서버 점검 시간대(키 없어도 무오류 스킵)
            dt.datetime(2026, 11, 25, 19, 40, tzinfo=KST),  # 야간장 데드존
            dt.datetime(2026, 11, 28, 16, 5, tzinfo=KST),   # 토요일 오후
        ]
        for fake_now in blocked_times:
            with tempfile.NamedTemporaryFile(mode="r+", encoding="utf-8") as gh_out:
                with (
                    mock.patch.dict(
                        os.environ,
                        {"LS_APP_KEY": "", "LS_APP_SECRET": "", "GITHUB_OUTPUT": gh_out.name},
                        clear=False,
                    ),
                    mock.patch.object(s, "get_kst_now", return_value=fake_now),
                    mock.patch.object(s.LSApiClient, "authenticate") as m_auth,
                    mock.patch.object(s, "supabase_fetch_existing_masters") as m_db,
                    mock.patch.object(s, "send_telegram_alert") as m_tg,
                ):
                    res = s.run_standalone_batch(mode="daily", skip_if_completed=True)
                gh_out.seek(0)
                out_txt = gh_out.read()
            self.assertTrue(res["skipped_completed"])
            self.assertTrue(res.get("skip_reason"))
            m_auth.assert_not_called()
            m_db.assert_not_called()
            m_tg.assert_not_called()
            self.assertIn("skipped_completed=true", out_txt)

    def test_ac67_manual_force_run_ignores_offhours_window(self) -> None:
        # skip_if_completed=False 수동 강제 실행은 새벽/주말에도 정상 실행되어야 함
        dawn_kst = dt.datetime(2026, 11, 25, 3, 20, tzinfo=KST)
        masters = [
            {"shcode": "005930", "hname": "삼성전자", "market": "KOSPI", "shares": 100000000, "market_cap_eok": 58000.0, "is_universe": True}
        ]
        with (
            mock.patch.dict(os.environ, {"LS_APP_KEY": "k", "LS_APP_SECRET": "sec"}, clear=False),
            mock.patch.object(s, "get_kst_now", return_value=dawn_kst),
            mock.patch.object(s, "is_quarterly_rebuild_due", return_value=(False, "수동 테스트")),
            mock.patch.object(s, "supabase_fetch_existing_masters", return_value=masters),
            mock.patch.object(s, "supabase_cleanup_unsettled_supply", return_value=0),
            mock.patch.object(s.LSApiClient, "authenticate", return_value="tok") as m_auth,
            mock.patch.object(s.LSApiClient, "fetch_latest_krx_trading_date", return_value="2026-11-24"),
            mock.patch.object(s, "check_daily_batch_completion", return_value={"is_completed": False, "completed_codes": set()}),
            mock.patch.object(
                s.LSApiClient,
                "fetch_common_stock_master",
                return_value={"005930": {"shcode": "005930", "hname": "삼성전자", "market": "KOSPI"}},
            ),
            mock.patch.object(s.LSApiClient, "fetch_top_trading_value_candidates", return_value={}),
            mock.patch.object(s, "supabase_get_stock_data_status_detail", return_value=(500, "2026-11-23", 500, "2026-11-23", False)),
            mock.patch.object(s, "supabase_get_anchor_row", return_value=None),
            mock.patch.object(s.LSApiClient, "fetch_daily_chart", return_value=_make_chart_rows("005930", ["2026-11-23", "2026-11-24"], 58000)),
            mock.patch.object(s.LSApiClient, "fetch_investor_supply", return_value=_make_supply_rows("005930", ["2026-11-24"])),
            mock.patch.object(s, "supabase_upsert"),
            mock.patch.object(s, "send_telegram_alert") as m_tg,
        ):
            res = s.run_standalone_batch(mode="daily", skip_if_completed=False)
        self.assertFalse(res["skipped_completed"])
        self.assertEqual(res["universe_count"], 1)
        m_auth.assert_called_once()
        m_tg.assert_called_once()

    def test_ac67_fetch_latest_krx_trading_date_excludes_empty_and_intraday(self) -> None:
        client = s.LSApiClient("k", "sec", sleep_sec=0.0)
        # 1) 05:35 KST 장전 빈 더미 봉(jdiff_vol=0, open=0) 제외 -> 직전 개장일 반환
        premarket_rows = [
            {"date": "20261125", "open": 0, "high": 0, "low": 0, "close": 58000, "jdiff_vol": 0},
            {"date": "20261124", "open": 57500, "high": 58200, "low": 57300, "close": 58000, "jdiff_vol": 12000000},
        ]
        with mock.patch.object(client, "call_tr", return_value={"t8410OutBlock1": premarket_rows}):
            d1 = client.fetch_latest_krx_trading_date(
                "2026-11-25", now_kst=dt.datetime(2026, 11, 25, 16, 5, tzinfo=KST)
            )
        self.assertEqual(d1, "2026-11-24")

        # 2) 14:10 KST (< 15:30 KST) 장중 진행 봉 제외 -> 직전 확정 개장일 반환
        intraday_rows = [
            {"date": "20261125", "open": 58100, "high": 58600, "low": 57900, "close": 58400, "jdiff_vol": 6500000},
            {"date": "20261124", "open": 57500, "high": 58200, "low": 57300, "close": 58000, "jdiff_vol": 12000000},
        ]
        with mock.patch.object(client, "call_tr", return_value={"t8410OutBlock1": intraday_rows}):
            d2 = client.fetch_latest_krx_trading_date(
                "2026-11-25", now_kst=dt.datetime(2026, 11, 25, 14, 10, tzinfo=KST)
            )
            d3 = client.fetch_latest_krx_trading_date(
                "2026-11-25", now_kst=dt.datetime(2026, 11, 25, 15, 30, tzinfo=KST)
            )
        self.assertEqual(d2, "2026-11-24")
        self.assertEqual(d3, "2026-11-25")

        # 3) 최소 Dict 테스트 픽스처({"date": "20261112"}) 하위 호환 유지
        with mock.patch.object(client, "call_tr", return_value={"t8410OutBlock1": [{"date": "20261112"}]}):
            self.assertEqual(
                client.fetch_latest_krx_trading_date("2026-11-12", now_kst=dt.datetime(2026, 11, 25, 16, 5, tzinfo=KST)),
                "2026-11-12",
            )

    def test_ac67_zero_universe_suppresses_telegram_and_dsa(self) -> None:
        masters = [
            {"shcode": "005930", "hname": "삼성전자", "market": "KOSPI", "shares": 100000000, "market_cap_eok": 58000.0, "is_universe": True}
        ]
        with (
            mock.patch.dict(os.environ, {"LS_APP_KEY": "k", "LS_APP_SECRET": "sec"}, clear=False),
            mock.patch.object(s, "get_kst_now", return_value=dt.datetime(2026, 11, 25, 16, 5, tzinfo=KST)),
            mock.patch.object(s, "is_quarterly_rebuild_due", return_value=(False, "평일 일일 업데이트")),
            mock.patch.object(s, "supabase_fetch_existing_masters", return_value=masters),
            mock.patch.object(s, "supabase_cleanup_unsettled_supply", return_value=0),
            mock.patch.object(s.LSApiClient, "authenticate", return_value="tok"),
            mock.patch.object(s.LSApiClient, "fetch_latest_krx_trading_date", return_value="2026-11-25"),
            mock.patch.object(s, "check_daily_batch_completion", return_value={"is_completed": False, "completed_codes": set()}),
            # LS 점검으로 t8436 마스터 0종목 반환 시뮬레이션
            mock.patch.object(s.LSApiClient, "fetch_common_stock_master", return_value={}),
            mock.patch.object(s.LSApiClient, "fetch_top_trading_value_candidates", return_value={}),
            mock.patch.object(s, "send_telegram_alert") as m_tg,
            mock.patch.object(s, "run_daily_supply_analysis_pipeline") as m_dsa,
        ):
            res = s.run_standalone_batch(mode="daily", skip_if_completed=False)
        self.assertEqual(res["universe_count"], 0)
        self.assertTrue(res.get("zero_universe_aborted"))
        m_tg.assert_not_called()
        m_dsa.assert_not_called()


class TestAC68QuarterlyUniverseRetentionAndDemotion(unittest.TestCase):
    def test_ac68_existing_universe_below_700_eok_retained_while_t1463_below_700_blocked(self) -> None:
        # 009470(기존 분기 유니버스, 1,000만주 × 6,500원 = 650억 < 700억) → 정상 적재되어야 함
        # 990001(t1463 신규 후보, 650억 < 700억) → 편입 차단되어야 함
        existing = [
            {
                "shcode": "009470",
                "hname": "기존소형하락주",
                "market": "KOSPI",
                "shares": 10_000_000,
                "market_cap_eok": 720.0,
                "is_universe": True,
            }
        ]
        upserted: dict[str, list[dict]] = {"daily_chart": [], "daily_investor_supply": [], "stocks_master": []}

        def fake_upsert(_u, _k, table, _cols, rows, *a, **kw):
            upserted.setdefault(table, []).extend(rows)

        with (
            mock.patch.dict(os.environ, {"LS_APP_KEY": "k", "LS_APP_SECRET": "sec"}, clear=False),
            mock.patch.object(s, "get_kst_now", return_value=dt.datetime(2026, 11, 25, 16, 10, tzinfo=KST)),
            mock.patch.object(s, "is_quarterly_rebuild_due", return_value=(False, "평일 일일 업데이트")),
            mock.patch.object(s, "supabase_fetch_existing_masters", return_value=existing),
            mock.patch.object(s, "supabase_cleanup_unsettled_supply", return_value=0),
            mock.patch.object(s.LSApiClient, "authenticate", return_value="tok"),
            mock.patch.object(s.LSApiClient, "fetch_latest_krx_trading_date", return_value="2026-11-25"),
            mock.patch.object(s, "check_daily_batch_completion", return_value={"is_completed": False, "completed_codes": set()}),
            mock.patch.object(
                s.LSApiClient,
                "fetch_common_stock_master",
                return_value={
                    "009470": {"shcode": "009470", "hname": "기존소형하락주", "market": "KOSPI"},
                    "990001": {"shcode": "990001", "hname": "신규미달후보", "market": "KOSDAQ"},
                },
            ),
            mock.patch.object(
                s.LSApiClient,
                "fetch_top_trading_value_candidates",
                return_value={"990001": {"shcode": "990001", "hname": "신규미달후보", "market": "KOSDAQ"}},
            ),
            mock.patch.object(s.LSApiClient, "fetch_single_stock_mcap", return_value=(650.0, 10_000_000, 6500)),
            mock.patch.object(s, "supabase_get_stock_data_status_detail", return_value=(500, "2026-11-24", 500, "2026-11-24", False)),
            mock.patch.object(s, "supabase_get_anchor_row", return_value=None),
            mock.patch.object(
                s.LSApiClient,
                "fetch_daily_chart",
                return_value=_make_chart_rows("009470", ["2026-11-24", "2026-11-25"], close=6500),
            ),
            mock.patch.object(
                s.LSApiClient,
                "fetch_investor_supply",
                return_value=_make_supply_rows("009470", ["2026-11-25"]),
            ),
            mock.patch.object(s, "supabase_upsert", side_effect=fake_upsert),
            mock.patch.object(s, "send_telegram_alert"),
        ):
            res = s.run_standalone_batch(mode="daily", skip_if_completed=False)

        self.assertEqual(res["universe_count"], 1)
        self.assertEqual({r["shcode"] for r in upserted["daily_chart"]}, {"009470"})
        self.assertEqual({r["shcode"] for r in upserted["daily_investor_supply"]}, {"009470"})
        master_009470 = [r for r in upserted["stocks_master"] if r["shcode"] == "009470"]
        self.assertEqual(len(master_009470), 1)
        self.assertTrue(master_009470[0]["is_universe"])
        self.assertAlmostEqual(master_009470[0]["market_cap_eok"], 650.0)
        self.assertNotIn("990001", {r["shcode"] for r in upserted["stocks_master"]})

    def test_ac68_quarterly_rebuild_demotes_dropped_stocks_without_delete_and_runs_prefetch(self) -> None:
        kept_codes = [f"{i:06d}" for i in range(1, 1205)]  # 1,204 >= MIN_COMPLETE_UNIVERSE_COUNT(1200)
        dropped_codes = ["900001", "900002"]
        existing = [
            {
                "shcode": c,
                "hname": f"종목{c}",
                "market": "KOSPI",
                "shares": 10_000_000,
                "market_cap_eok": 800.0,
                "avg_vol_20d": 50000,
                "avg_val_20d_eok": 5.0,
                "is_universe": True,
                "last_close": 8000,
                "updated_at": "2026-09-01T11:30:00+00:00",
            }
            for c in (kept_codes + dropped_codes)
        ]
        mcap_map = {
            c: {
                "shcode": c,
                "hname": f"종목{c}",
                "market": "KOSPI",
                "shares": 10_000_000,
                "market_cap_eok": 900.0,
                "price": 9000,
            }
            for c in kept_codes
        }
        common_master = {c: {"shcode": c, "hname": f"종목{c}", "market": "KOSPI"} for c in (kept_codes + dropped_codes)}

        master_batches: list[list[dict]] = []

        def fake_upsert(_u, _k, table, _cols, rows, *a, **kw):
            if table == "stocks_master":
                master_batches.append(list(rows))

        with (
            mock.patch.dict(os.environ, {"LS_APP_KEY": "k", "LS_APP_SECRET": "sec"}, clear=False),
            mock.patch.object(s, "get_kst_today", return_value=dt.date(2026, 12, 1)),
            mock.patch.object(s, "get_kst_now", return_value=dt.datetime(2026, 12, 1, 16, 5, tzinfo=KST)),
            mock.patch.object(s, "supabase_fetch_existing_masters", return_value=existing),
            mock.patch.object(s, "supabase_cleanup_unsettled_supply", return_value=0),
            mock.patch.object(s.LSApiClient, "authenticate", return_value="tok"),
            mock.patch.object(s.LSApiClient, "fetch_latest_krx_trading_date", return_value="2026-12-01"),
            mock.patch.object(s.LSApiClient, "fetch_common_stock_master", return_value=common_master),
            mock.patch.object(s.LSApiClient, "fetch_market_cap_above_threshold", return_value=mcap_map),
            mock.patch.object(s, "supabase_prefetch_daily_context", return_value=None) as m_prefetch,
            mock.patch.object(s, "supabase_get_anchor_row", return_value=None),
            mock.patch.object(s, "supabase_upsert", side_effect=fake_upsert),
            mock.patch.object(s, "build_daily_screening_lists_from_db", return_value=([], [])),
            mock.patch.object(s, "run_daily_supply_analysis_pipeline", return_value=None),
            mock.patch.object(s, "send_telegram_alert"),
            # 차트 빈 응답으로 1,204종목 루프 0.01초 내 통과
            mock.patch.object(s.LSApiClient, "fetch_daily_chart", return_value=[]),
            mock.patch.object(s.LSApiClient, "fetch_investor_supply", return_value=[]),
            mock.patch.object(s, "supabase_get_stock_data_status_detail", return_value=(500, "2026-11-30", 500, "2026-11-30", False)),
        ):
            # m_prefetch 가 패치되어 있으므로 mocked_db=False 로 프리페치 호출됨
            s.run_standalone_batch(mode="daily", skip_if_completed=False)

        self.assertGreaterEqual(len(master_batches), 1)
        initial_rows = master_batches[0]
        self.assertEqual(len(initial_rows), len(kept_codes) + len(dropped_codes))
        by_code = {r["shcode"]: r for r in initial_rows}
        # PostgREST 일괄 Upsert 시 모든 객체 키 집합이 완전히 동일해야 함(PGRST102 방지)
        expected_keys = set(initial_rows[0].keys())
        for row in initial_rows:
            self.assertEqual(set(row.keys()), expected_keys)
        for dc in dropped_codes:
            self.assertFalse(by_code[dc]["is_universe"])
            self.assertEqual(by_code[dc]["shares"], 10_000_000)
        self.assertTrue(by_code["000001"]["is_universe"])
        m_prefetch.assert_called_once()

    def test_ac68_is_quarterly_rebuild_due_kst_month_conversion(self) -> None:
        # PostgREST 가 반환한 UTC 2026-11-30T15:30:00+00:00 는 KST 2026-12-01 00:30:00+09:00 (이미 12월 갱신됨)
        rows_kst_dec = [
            {"shcode": f"{i:06d}", "is_universe": True, "updated_at": "2026-11-30T15:30:00+00:00"}
            for i in range(1, 1301)
        ]
        due_dec, _ = s.is_quarterly_rebuild_due(dt.date(2026, 12, 1), rows_kst_dec)
        self.assertFalse(due_dec)

        # UTC 2026-11-30T11:30:00+00:00 는 KST 2026-11-30 20:30:00+09:00 (아직 11월 → 12월 재산출 필요)
        rows_kst_nov = [
            {"shcode": f"{i:06d}", "is_universe": True, "updated_at": "2026-11-30T11:30:00+00:00"}
            for i in range(1, 1301)
        ]
        due_nov, reason_nov = s.is_quarterly_rebuild_due(dt.date(2026, 12, 1), rows_kst_nov)
        self.assertTrue(due_nov)
        self.assertIn("12월 분기 첫 거래일", reason_nov)

        # 비표준 문자열 startswith 폴백 호환
        rows_fallback = [
            {"shcode": f"{i:06d}", "is_universe": True, "updated_at": "2026-12-manual"}
            for i in range(1, 1301)
        ]
        self.assertFalse(s.is_quarterly_rebuild_due(dt.date(2026, 12, 2), rows_fallback)[0])


class TestAC69Surger409EliminationAndNewIpoBackfill(unittest.TestCase):
    def test_ac69_t1463_new_surger_pre_seeded_avoiding_fk_409(self) -> None:
        # DB 외래키 제약을 모사: stocks_master 에 없는 shcode 로 daily_chart/supply Upsert 시 HTTP 409 발생!
        master_db: dict[str, dict] = {
            "005930": {
                "shcode": "005930",
                "hname": "삼성전자",
                "market": "KOSPI",
                "shares": 100_000_000,
                "market_cap_eok": 58000.0,
                "is_universe": True,
            }
        }
        master_upsert_history: list[dict] = []
        chart_upserted_codes: set[str] = set()

        def strict_fk_upsert(url, _k, table, _cols, rows, *a, **kw):
            if table == "stocks_master":
                for r in rows:
                    master_db[r["shcode"]] = dict(r)
                    master_upsert_history.append(dict(r))
                return
            for r in rows:
                if r["shcode"] not in master_db:
                    raise urllib.error.HTTPError(
                        url, 409, "Conflict", {}, io.BytesIO(b'{"code":"23503","message":"FK violation"}')
                    )
                if table == "daily_chart":
                    chart_upserted_codes.add(r["shcode"])

        with (
            mock.patch.dict(os.environ, {"LS_APP_KEY": "k", "LS_APP_SECRET": "sec"}, clear=False),
            mock.patch.object(s, "get_kst_now", return_value=dt.datetime(2026, 11, 25, 16, 10, tzinfo=KST)),
            mock.patch.object(s, "is_quarterly_rebuild_due", return_value=(False, "평일 일일 업데이트")),
            mock.patch.object(s, "supabase_fetch_existing_masters", return_value=list(master_db.values())),
            mock.patch.object(s, "supabase_cleanup_unsettled_supply", return_value=0),
            mock.patch.object(s.LSApiClient, "authenticate", return_value="tok"),
            mock.patch.object(s.LSApiClient, "fetch_latest_krx_trading_date", return_value="2026-11-25"),
            mock.patch.object(s, "check_daily_batch_completion", return_value={"is_completed": False, "completed_codes": {"005930"}}),
            mock.patch.object(
                s.LSApiClient,
                "fetch_common_stock_master",
                return_value={
                    "005930": {"shcode": "005930", "hname": "삼성전자", "market": "KOSPI"},
                    "471800": {"shcode": "471800", "hname": "에이엘로봇", "market": "KOSDAQ"},
                },
            ),
            mock.patch.object(
                s.LSApiClient,
                "fetch_top_trading_value_candidates",
                return_value={"471800": {"shcode": "471800", "hname": "에이엘로봇", "market": "KOSDAQ"}},
            ),
            mock.patch.object(s.LSApiClient, "fetch_single_stock_mcap", return_value=(850.0, 10_000_000, 8500)),
            mock.patch.object(s, "supabase_get_stock_data_status_detail", return_value=(500, "2026-11-25", 500, "2026-11-25", False)),
            mock.patch.object(s, "supabase_get_anchor_row", return_value=None),
            mock.patch.object(
                s.LSApiClient,
                "fetch_daily_chart",
                return_value=_make_chart_rows("471800", ["2026-11-24", "2026-11-25"], close=8500),
            ),
            mock.patch.object(
                s.LSApiClient,
                "fetch_investor_supply",
                return_value=_make_supply_rows("471800", ["2026-11-25"]),
            ),
            mock.patch.object(s, "supabase_upsert", side_effect=strict_fk_upsert),
            mock.patch.object(s, "build_daily_screening_lists_from_db", return_value=([], [])),
            mock.patch.object(s, "send_telegram_alert"),
        ):
            res = s.run_standalone_batch(mode="daily", skip_if_completed=False)

        self.assertEqual(res["backfilled_count"], 1)
        self.assertIn("471800", chart_upserted_codes)
        surger_records = [r for r in master_upsert_history if r["shcode"] == "471800"]
        self.assertEqual(len(surger_records), 2)
        # 1차: 루프 진입 전 시드 등록(updated_at == 1970-01-01...)
        self.assertEqual(surger_records[0]["updated_at"], "1970-01-01T00:00:00+09:00")
        self.assertTrue(surger_records[0]["is_universe"])
        # 2차: 차트·수급 적재 완료 후 실제 시각으로 갱신
        self.assertNotEqual(surger_records[1]["updated_at"], "1970-01-01T00:00:00+09:00")

    def test_ac69_batch_upsert_buffer_3post_order_and_409_self_recovery(self) -> None:
        # 1) 정상 묶음 플러시 3-POST 순서 계약(daily_chart → daily_investor_supply → stocks_master) 검증
        normal_calls: list[str] = []
        with mock.patch.object(s, "supabase_upsert", side_effect=lambda u, k, t, c, r, *a, **kw: normal_calls.append(t)):
            buf = s.BatchUpsertBuffer("https://example.supabase.co", "key", batch_size=50)
            buf.add({"shcode": "005930"}, [{"shcode": "005930", "trade_date": "2026-11-25"}], [{"shcode": "005930", "trade_date": "2026-11-25"}])
            self.assertEqual(buf.flush(), 1)
        self.assertEqual(normal_calls, ["daily_chart", "daily_investor_supply", "stocks_master"])

        # 2) 미등록 종목으로 인한 묶음·단건 HTTP 409 발생 시 시드 선등록 후 재시도 자가 복구 검증
        fk_masters = {"005930"}
        saved_charts: list[str] = []
        seed_seen: list[dict] = []

        def fk_sim_upsert(url, _k, table, _cols, rows, *a, **kw):
            if table == "stocks_master":
                for r in rows:
                    fk_masters.add(r["shcode"])
                    if r.get("updated_at") == "1970-01-01T00:00:00+09:00":
                        seed_seen.append(dict(r))
                return
            for r in rows:
                if r["shcode"] not in fk_masters:
                    raise urllib.error.HTTPError(url, 409, "Conflict", {}, io.BytesIO(b"23503"))
            if table == "daily_chart":
                saved_charts.extend(r["shcode"] for r in rows)

        with mock.patch.object(s, "supabase_upsert", side_effect=fk_sim_upsert):
            buf2 = s.BatchUpsertBuffer("https://example.supabase.co", "key", batch_size=50)
            for code in ("005930", "104620"):
                buf2.add(
                    {"shcode": code, "hname": f"N{code}", "market": "KOSDAQ", "is_universe": True},
                    [{"shcode": code, "trade_date": "2026-11-25"}],
                    [{"shcode": code, "trade_date": "2026-11-25"}],
                )
            ok_cnt = buf2.flush()

        self.assertEqual(ok_cnt, 2)
        self.assertEqual(saved_charts, ["005930", "104620"])
        self.assertEqual([r["shcode"] for r in seed_seen], ["104620"])

    def test_ac69_new_ipo_backfill_detection_and_ultra_new_single_page(self) -> None:
        # 상장 65영업일 이하 신규 상장주(1일, 8일, 12일, 40일, 65일) -> True
        for cnt in (1, 5, 8, 12, 40, 65):
            self.assertTrue(
                s.is_stock_already_backfilled(cnt, "2026-11-24", cnt, "2026-11-24", min_target_date="2026-11-05"),
                f"IPO {cnt}d/{cnt}d should be treated as already backfilled",
            )
        # 오차 5영업일 이내 허용
        self.assertTrue(s.is_stock_already_backfilled(40, "2026-11-24", 36, "2026-11-24", "2026-11-05"))

        # 구 v1.0 절단 데이터(60일/25일, 55일/35일) 및 불일치/미확정/미적재는 반드시 False 유지
        self.assertFalse(s.is_stock_already_backfilled(60, "2026-11-24", 25, "2026-11-24", "2026-11-05"))
        self.assertFalse(s.is_stock_already_backfilled(55, "2026-11-24", 35, "2026-11-24", "2026-11-05"))
        self.assertFalse(s.is_stock_already_backfilled(30, "2026-11-24", 15, "2026-11-24", "2026-11-05"))
        self.assertFalse(s.is_stock_already_backfilled(0, "", 0, "", "2026-11-05"))
        self.assertFalse(
            s.is_stock_already_backfilled(8, "2026-11-24", 8, "2026-11-24", "2026-11-05", is_latest_supply_unsettled=True)
        )

        # 초신규 상장주(chart_cnt=3 <= 5, anchor_row=None) daily 실행 시 3,000건 대신 105달력일(count=60) 1페이지 조회 확인
        ipo_master = [
            {"shcode": "480000", "hname": "초신규주", "market": "KOSDAQ", "shares": 10_000_000, "market_cap_eok": 1200.0, "is_universe": True}
        ]
        chart_call_args: list[tuple] = []

        def spy_fetch_chart(shcode, start_date, end_date, count=500):
            chart_call_args.append((shcode, start_date, end_date, count))
            return _make_chart_rows(shcode, ["2026-11-21", "2026-11-24", "2026-11-25"], close=12000)

        with (
            mock.patch.dict(os.environ, {"LS_APP_KEY": "k", "LS_APP_SECRET": "sec"}, clear=False),
            mock.patch.object(s, "get_kst_today", return_value=dt.date(2026, 11, 25)),
            mock.patch.object(s, "get_kst_now", return_value=dt.datetime(2026, 11, 25, 16, 10, tzinfo=KST)),
            mock.patch.object(s, "is_quarterly_rebuild_due", return_value=(False, "평일 일일 업데이트")),
            mock.patch.object(s, "supabase_fetch_existing_masters", return_value=ipo_master),
            mock.patch.object(s, "supabase_cleanup_unsettled_supply", return_value=0),
            mock.patch.object(s.LSApiClient, "authenticate", return_value="tok"),
            mock.patch.object(s.LSApiClient, "fetch_latest_krx_trading_date", return_value="2026-11-25"),
            mock.patch.object(s, "check_daily_batch_completion", return_value={"is_completed": False, "completed_codes": set()}),
            mock.patch.object(
                s.LSApiClient,
                "fetch_common_stock_master",
                return_value={"480000": {"shcode": "480000", "hname": "초신규주", "market": "KOSDAQ"}},
            ),
            mock.patch.object(s.LSApiClient, "fetch_top_trading_value_candidates", return_value={}),
            mock.patch.object(s, "supabase_get_stock_data_status_detail", return_value=(3, "2026-11-24", 3, "2026-11-24", False)),
            mock.patch.object(s, "supabase_get_anchor_row", return_value=None),
            mock.patch.object(s.LSApiClient, "fetch_daily_chart", side_effect=spy_fetch_chart),
            mock.patch.object(s.LSApiClient, "fetch_investor_supply", return_value=_make_supply_rows("480000", ["2026-11-25"])),
            mock.patch.object(s, "supabase_upsert"),
            mock.patch.object(s, "send_telegram_alert"),
        ):
            res = s.run_standalone_batch(mode="daily", skip_if_completed=False)

        self.assertEqual(res["backfilled_count"], 0)
        self.assertEqual(res["incremental_count"], 1)
        self.assertEqual(len(chart_call_args), 1)
        self.assertEqual(chart_call_args[0][3], s.ANCHOR_RECENT_COUNT)
        self.assertGreater(chart_call_args[0][1], s.CHART_HISTORY_START_DATE)


class TestAC70AC71CronSlimmingMicroVolumeAndScope(unittest.TestCase):
    def test_ac70_workflow_two_backup_crons(self) -> None:
        wf_text = (ROOT / ".github" / "workflows" / "daily_batch.yml").read_text(encoding="utf-8")
        crons = re.findall(r"-\s*cron:\s*'([^']+)'", wf_text)
        self.assertEqual(crons, ["25 7 * * 1-5", "47 11 * * 1-5"])

    def test_ac70_micro_volume_stock_completion_recognition(self) -> None:
        # 005930, 000660, 005380 (대형주 3종) + 001260(조흥: volume=47 <= 100, 순매수 합 0, 수급 행 존재)
        # + 009999(일반주: volume=101 > 100, 순매수 합 0 -> 장중 미확정으로 간주되어 제외)
        # + 008888(수급 행 미존재: volume=30 <= 100 이지만 daily_investor_supply 행 없음 -> 제외)
        codes = ["005930", "000660", "005380", "001260", "009999", "008888"]
        masters = [{"shcode": c, "is_universe": True} for c in codes]

        def make_http_get(rep3_settled: bool):
            def _fake_get(url: str, headers=None, timeout: float = 30.0):
                if "daily_chart" in url:
                    vols = {
                        "005930": 10_000_000,
                        "000660": 5_000_000,
                        "005380": 2_000_000,
                        "001260": 47,
                        "009999": 101,
                        "008888": 30,
                    }
                    return [{"shcode": c, "trade_date": "2026-11-25", "volume": vols[c]} for c in codes]
                out = []
                for c in codes:
                    if c == "008888":
                        continue  # 수급 레코드 아직 없음
                    is_mega = c in ("005930", "000660", "005380")
                    inst_v = (5000 if rep3_settled else 0) if is_mega else 0
                    ind_v = (-5000 if rep3_settled else 0) if is_mega else 0
                    out.append({
                        "shcode": c,
                        "trade_date": "2026-11-25",
                        "real_inst_vol": inst_v,
                        "frg_vol": 0,
                        "ind_vol": ind_v,
                        "fn_inv_vol": 0,
                        "etc_corp_vol": 0,
                    })
                return out

            return _fake_get

        # 1) 대표 대형주 3종 확정 시: 001260(vol=47, 수급행 존재)만 추가 완료 인정, 009999(vol=101)·008888(수급행 없음)은 미완료 유지
        with mock.patch.object(s, "http_get_json", side_effect=make_http_get(rep3_settled=True)):
            comp_settled = s.check_daily_batch_completion("https://example.supabase.co", "key", masters, "2026-11-25")
        self.assertTrue(comp_settled["rep_3_settled"])
        self.assertIn("001260", comp_settled["completed_codes"])
        self.assertNotIn("009999", comp_settled["completed_codes"])
        self.assertNotIn("008888", comp_settled["completed_codes"])

        # 2) 대표 대형주 3종 미확정(장중) 시: 001260 도 완료 집합에 절대 포함되지 않음
        with mock.patch.object(s, "http_get_json", side_effect=make_http_get(rep3_settled=False)):
            comp_intraday = s.check_daily_batch_completion("https://example.supabase.co", "key", masters, "2026-11-25")
        self.assertFalse(comp_intraday["rep_3_settled"])
        self.assertNotIn("001260", comp_intraday["completed_codes"])

    def test_ac71_frontend_and_schema_untouched(self) -> None:
        diff = subprocess.check_output(
            [
                "git",
                "diff",
                "--stat",
                "--",
                "index.html",
                "watchlist.html",
                "holdings.html",
                "common.js",
                "supabase_schema.sql",
                "scripts",
                "STRATEGY.md",
                "TEST_REPORT.md",
            ],
            cwd=str(ROOT),
            text=True,
        ).strip()
        self.assertEqual(diff, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
