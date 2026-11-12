#!/usr/bin/env python3
"""
LS증권 수급·차트 스크리닝 시스템 자동화 단위/통합 테스트 스위트
1) ETF/ETN/스팩/우선주/리츠 필터링 검증 (t8436 etfgubun 반영)
2) 분기별(최초 1회 + 1,200종목 미만 미완성 유니버스 감지 + 3·6·9·12월 첫 거래일) 시가총액·유니버스 재산출 판정 검증
3) EMA(5/20/60/120/240) 지수이동평균 수식 검증
4) t1717 공식 응답 파싱, 순수기관(금융투자 제외 6대 주체) 비중(%) 및 2년치 역순 날짜 슬라이딩 연속조회(Pagination) 검증
5) 대량 백필 스마트 이어받기(is_stock_already_backfilled) 및 레퍼런스 종목(대한유화 006650, 태광 023160) 최우선 정렬 검증
"""
import datetime as dt
import unittest
from unittest.mock import patch

import run_daily_screener as s


class TestScreenerVerification(unittest.TestCase):
    def test_1_excluded_security_filter(self) -> None:
        # 일반 보통주는 통과(False)해야 함
        self.assertFalse(s.is_excluded_security("삼성전자", etfgubun="0", spac_gubun="N"))
        self.assertFalse(s.is_excluded_security("알테오젠", etfgubun="0", spac_gubun="N"))
        self.assertFalse(s.is_excluded_security("대한유화", etfgubun="0", spac_gubun="N"))
        self.assertFalse(s.is_excluded_security("태광", etfgubun="0", spac_gubun="N"))
        self.assertFalse(s.is_excluded_security("대우건설", etfgubun="0", spac_gubun="N"))
        self.assertFalse(s.is_excluded_security("연우", etfgubun="0", spac_gubun="N"))

        # ETF, ETN, 스팩, 우선주, 리츠는 제외(True)되어야 함
        self.assertTrue(s.is_excluded_security("KODEX 200", etfgubun="1", spac_gubun="N"))
        self.assertTrue(s.is_excluded_security("신한제10호스팩", etfgubun="0", spac_gubun="Y"))
        self.assertTrue(s.is_excluded_security("삼성전자우", etfgubun="0", spac_gubun="N"))
        self.assertTrue(s.is_excluded_security("현대차2우B", etfgubun="0", spac_gubun="N"))
        self.assertTrue(s.is_excluded_security("롯데리츠", etfgubun="0", spac_gubun="N"))

    def test_2_quarterly_and_incomplete_universe_schedule(self) -> None:
        # 1) 최초 1회 (DB가 비어있을 때) -> 무조건 True
        due, reason = s.is_quarterly_rebuild_due(dt.date(2026, 11, 11), [])
        self.assertTrue(due)
        self.assertIn("최초 1회", reason)

        # 2) 미완성 유니버스 상태(예: 247종목 < 1,200종목) -> True (자동 전수 재산출)
        incomplete_247 = [
            {"shcode": f"{i:06d}", "is_universe": True, "updated_at": "2026-11-11T12:00:00Z"}
            for i in range(1, 248)
        ]
        due_inc, reason_inc = s.is_quarterly_rebuild_due(dt.date(2026, 11, 11), incomplete_247)
        self.assertTrue(due_inc)
        self.assertIn("미완성 유니버스 보완", reason_inc)

        # 3) 정상 완비 상태(예: 1,477종목 >= 1,200종목)이고 평달(11월)일 때 -> False
        complete_1477 = [
            {"shcode": f"{i:06d}", "is_universe": True, "updated_at": "2026-11-11T12:00:00Z"}
            for i in range(1, 1478)
        ]
        due2, _ = s.is_quarterly_rebuild_due(dt.date(2026, 11, 11), complete_1477)
        self.assertFalse(due2)

        # 4) 3·6·9·12월 첫 거래일(예: 2026-12-01)이고 아직 12월 갱신이 안 된 경우 -> True
        due3, reason3 = s.is_quarterly_rebuild_due(dt.date(2026, 12, 1), complete_1477)
        self.assertTrue(due3)
        self.assertIn("12월 분기 첫 거래일", reason3)

    def test_3_ema_and_pure_institutional_formula(self) -> None:
        rows = [
            {"shcode": "196170", "trade_date": f"2026-10-{d:02d}", "close": 10000 + d * 100, "volume": 100000}
            for d in range(1, 26)
        ]
        enriched = s.compute_ema_series(rows)
        self.assertEqual(len(enriched), 25)
        last = enriched[-1]
        self.assertGreater(last["ema_5"], last["ema_20"])
        self.assertGreater(last["ema_20"], last["ema_60"])

        raw_supply = {
            "shcode": "196170",
            "trade_date": "2026-11-11",
            "itc_vol": 10000, "itc_amt": 1000.0,
            "pef_vol": 8000, "pef_amt": 800.0,
            "pen_vol": 12000, "pen_amt": 1200.0,
            "ins_vol": 3000, "ins_amt": 300.0,
            "etc_fin_vol": 1000, "etc_fin_amt": 100.0,
            "bank_vol": 1000, "bank_amt": 100.0,
            "fn_inv_vol": -50000, "fn_inv_amt": -5000.0,
            "frg_vol": 15000, "frg_amt": 1500.0,
        }
        res = s.compute_pure_institutional_supply(raw_supply, daily_volume=100000)
        self.assertEqual(res["real_inst_vol"], 35000)
        self.assertEqual(res["real_inst_amt"], 3500.0)
        self.assertEqual(res["inst_vol_ratio"], 35.0)
        self.assertEqual(res["frg_vol_ratio"], 15.0)

    def test_4_t1717_official_response_and_sliding_pagination(self) -> None:
        client = s.LSApiClient("dummy_key", "dummy_secret", sleep_sec=0.0)
        client.access_token = "mock_token"

        # 2페이지 연속 슬라이딩 응답 모킹 (1페이지: 2026-10-07~2026-11-11, 2페이지: 2026-08-25~2026-10-06)
        page1_rows = [
            {
                "date": f"202610{d:02d}",
                "close": 100000,
                "volume": 200000,
                "tjj0000_vol": 10000, "tjj0000_dan": 100000,
                "tjj0001_vol": -30000, "tjj0001_dan": 100000,
                "tjj0002_vol": 2000, "tjj0002_dan": 100000,
                "tjj0003_vol": 15000, "tjj0003_dan": 100000,
                "tjj0004_vol": 1000, "tjj0004_dan": 100000,
                "tjj0005_vol": 2000, "tjj0005_dan": 100000,
                "tjj0006_vol": 10000, "tjj0006_dan": 100000,
                "tjj0008_vol": -30000, "tjj0008_dan": 100000,
                "tjj0017_vol": 20000, "tjj0017_dan": 100000,
            }
            for d in range(7, 15)
        ]
        page2_rows = [
            {
                "date": "20260825",
                "close": 15000,
                "volume": 100000,
                "tjj0003_vol": 25000, "tjj0003_dan": 15000,
            }
        ]
        call_effects = [
            {"rsp_cd": "00000", "t1717OutBlock": page1_rows},
            {"rsp_cd": "00000", "t1717OutBlock": page2_rows},
        ]
        with patch.object(client, "call_tr", side_effect=call_effects) as mocked_call:
            rows = client.fetch_investor_supply(
                "023160", "2026-08-01", "2026-10-14", {"2026-08-25": 100000}, {"2026-08-25": 15000}, max_pages=5
            )
            self.assertEqual(mocked_call.call_count, 2)
            # 2번째 호출의 todt가 1페이지 최저일(20261007)의 전날인 20261006으로 슬라이딩되었는지 검증
            second_call_body = mocked_call.call_args_list[1][0][2]
            self.assertEqual(second_call_body["t1717InBlock"]["todt"], "20261006")

        self.assertEqual(len(rows), 9)
        self.assertEqual(rows[0]["trade_date"], "2026-08-25")
        self.assertEqual(rows[0]["real_inst_vol"], 25000)
        self.assertEqual(rows[0]["inst_vol_ratio"], 25.0)

        # [ISSUE-008 검증] 장중(수급 확정 전) 전 주체 수량이 0인 당일 행은 적재에서 자동 제외되어야 함
        intraday_zero_row = {
            "date": "20261112",
            "close": 208000,
            "volume": 5000000,
            "tjj0000_vol": 0,
            "tjj0001_vol": 0,
            "tjj0002_vol": 0,
            "tjj0003_vol": 0,
            "tjj0004_vol": 0,
            "tjj0005_vol": 0,
            "tjj0006_vol": 0,
            "tjj0007_vol": 0,
            "tjj0008_vol": 0,
            "tjj0017_vol": 0,
        }
        with patch.object(
            client,
            "call_tr",
            return_value={"rsp_cd": "00000", "t1717OutBlock": [intraday_zero_row] + page1_rows[:2]},
        ):
            filtered_rows = client.fetch_investor_supply("005930", "2026-10-01", "2026-11-12", {}, {}, max_pages=1)
        self.assertTrue(all(r["trade_date"] != "2026-11-12" for r in filtered_rows))
        self.assertEqual(len(filtered_rows), 2)

    def test_5_smart_resume_backfill_detection(self) -> None:
        # 기존 60일(차트)/25일(수급) 절단 상태는 반드시 False(백필 대상)여야 함
        self.assertFalse(s.is_stock_already_backfilled(60, "2026-11-11", 25, "2026-11-11", "2026-10-23"))
        # [ISSUE-007 검증] 새 거래일(2026-11-12)에 전일(2026-11-11)까지 500일 적재된 종목은
        # recent_history_cutoff(2026-10-23) 기준으로 True(2년치 보유 인정 -> daily 모드에서 1페이지 증분)여야 함
        self.assertTrue(s.is_stock_already_backfilled(500, "2026-11-11", 500, "2026-11-11", "2026-10-23"))
        # [ISSUE-008 검증] 최신 수급 행이 장중 미확정(전 주체 0) 상태이면 스킵하지 않도록 False를 반환해야 함
        self.assertFalse(
            s.is_stock_already_backfilled(
                500, "2026-11-12", 500, "2026-11-12", "2026-10-23", is_latest_supply_unsettled=True
            )
        )
        # 신규 상장주(예: 상장 후 120영업일 경과하여 차트 120일 / 수급 120일 일치)도 True(스킵 대상)여야 함
        self.assertTrue(s.is_stock_already_backfilled(120, "2026-11-11", 120, "2026-11-11", "2026-10-23"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
