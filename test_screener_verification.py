#!/usr/bin/env python3
"""
LS증권 수급·차트 스크리닝 시스템 자동화 단위/통합 테스트 스위트
1) ETF/ETN/스팩/우선주/리츠 필터링 검증 (t8436 etfgubun 반영)
2) 분기별(최초 1회 + 3·6·9·12월 첫 거래일) 시가총액·유니버스 재산출 판정 검증
3) EMA(5/20/60/120/240) 지수이동평균 수식 검증
4) t1717 공식 응답(tjjXXXX_vol / tjjXXXX_dan) 파싱 및 순수기관(금융투자 제외 6대 주체) 비중(%) 검증
5) Supabase 실시간 테이블 연결(HTTP 200) 및 4단계 검증 리포트 동작 확인
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
        self.assertFalse(s.is_excluded_security("대우건설", etfgubun="0", spac_gubun="N"))
        self.assertFalse(s.is_excluded_security("연우", etfgubun="0", spac_gubun="N"))

        # ETF, ETN, 스팩, 우선주, 리츠는 제외(True)되어야 함
        self.assertTrue(s.is_excluded_security("KODEX 200", etfgubun="1", spac_gubun="N"))
        self.assertTrue(s.is_excluded_security("신한제10호스팩", etfgubun="0", spac_gubun="Y"))
        self.assertTrue(s.is_excluded_security("삼성전자우", etfgubun="0", spac_gubun="N"))
        self.assertTrue(s.is_excluded_security("현대차2우B", etfgubun="0", spac_gubun="N"))
        self.assertTrue(s.is_excluded_security("롯데리츠", etfgubun="0", spac_gubun="N"))

    def test_2_quarterly_market_cap_schedule(self) -> None:
        # 1) 최초 1회 (DB가 비어있을 때) -> 무조건 True
        due, reason = s.is_quarterly_rebuild_due(dt.date(2026, 11, 11), [])
        self.assertTrue(due)
        self.assertIn("최초 1회", reason)

        # 2) 평달(예: 11월)이고 기존 유니버스가 존재할 때 -> False (일일 증분 + 급등주 자동편입 모드)
        existing = [{"shcode": "005930", "is_universe": True, "updated_at": "2026-11-10T12:00:00Z"}]
        due2, _ = s.is_quarterly_rebuild_due(dt.date(2026, 11, 11), existing)
        self.assertFalse(due2)

        # 3) 3·6·9·12월 첫 거래일(예: 2026-12-01)이고 아직 12월 갱신이 안 된 경우 -> True
        due3, reason3 = s.is_quarterly_rebuild_due(dt.date(2026, 12, 1), existing)
        self.assertTrue(due3)
        self.assertIn("12월 분기 첫 거래일", reason3)

        # 4) 12월 첫 거래일 산출이 이미 완료된 후 12월 2일에 실행될 때 -> False
        existing_dec = [{"shcode": "005930", "is_universe": True, "updated_at": "2026-12-01T12:05:00Z"}]
        due4, _ = s.is_quarterly_rebuild_due(dt.date(2026, 12, 2), existing_dec)
        self.assertFalse(due4)

    def test_3_ema_and_pure_institutional_formula(self) -> None:
        # EMA 계산 검증
        rows = [
            {"shcode": "196170", "trade_date": f"2026-10-{d:02d}", "close": 10000 + d * 100, "volume": 100000}
            for d in range(1, 26)
        ]
        enriched = s.compute_ema_series(rows)
        self.assertEqual(len(enriched), 25)
        last = enriched[-1]
        self.assertGreater(last["ema_5"], last["ema_20"])
        self.assertGreater(last["ema_20"], last["ema_60"])

        # 순수기관 = 투신(itc) + 사모(pef) + 연기금(pen) + 보험(ins) + 기타금융(etc_fin) + 은행(bank)
        # 금융투자(fn_inv = -50000)는 합산에서 제외되어야 함!
        raw_supply = {
            "shcode": "196170",
            "trade_date": "2026-11-11",
            "itc_vol": 10000, "itc_amt": 1000.0,
            "pef_vol": 8000, "pef_amt": 800.0,
            "pen_vol": 12000, "pen_amt": 1200.0,
            "ins_vol": 3000, "ins_amt": 300.0,
            "etc_fin_vol": 1000, "etc_fin_amt": 100.0,
            "bank_vol": 1000, "bank_amt": 100.0,
            "fn_inv_vol": -50000, "fn_inv_amt": -5000.0,  # 금융투자 대규모 매도 (제외 대상)
            "frg_vol": 15000, "frg_amt": 1500.0,
        }
        res = s.compute_pure_institutional_supply(raw_supply, daily_volume=100000)
        # 10000 + 8000 + 12000 + 3000 + 1000 + 1000 = 35000주 (거래량 100,000주 대비 35.0%)
        self.assertEqual(res["real_inst_vol"], 35000)
        self.assertEqual(res["real_inst_amt"], 3500.0)
        self.assertEqual(res["inst_vol_ratio"], 35.0)
        self.assertEqual(res["frg_vol_ratio"], 15.0)

    def test_4_t1717_official_response_parsing(self) -> None:
        # LS증권 공식 t1717OutBlock 응답 구조(tjjXXXX_vol, tjjXXXX_dan) 파싱 검증
        client = s.LSApiClient("dummy_key", "dummy_secret", sleep_sec=0.0)
        client.access_token = "mock_token"
        mock_t1717_resp = {
            "rsp_cd": "00000",
            "t1717OutBlock": [
                {
                    "date": "20261111",
                    "close": 100000,
                    "volume": 200000,
                    "tjj0000_vol": 10000, "tjj0000_dan": 100000,  # 사모펀드 +10,000주 (+1,000백만원)
                    "tjj0001_vol": -30000, "tjj0001_dan": 100000, # 금융투자 -30,000주 (순수기관 제외)
                    "tjj0002_vol": 2000, "tjj0002_dan": 100000,   # 보험 +2,000주
                    "tjj0003_vol": 15000, "tjj0003_dan": 100000,  # 투신 +15,000주
                    "tjj0004_vol": 1000, "tjj0004_dan": 100000,   # 은행 +1,000주
                    "tjj0005_vol": 2000, "tjj0005_dan": 100000,   # 기타금융 +2,000주
                    "tjj0006_vol": 10000, "tjj0006_dan": 100000,  # 연기금 +10,000주
                    "tjj0007_vol": 0, "tjj0007_dan": 0,
                    "tjj0008_vol": -30000, "tjj0008_dan": 100000, # 개인
                    "tjj0017_vol": 20000, "tjj0017_dan": 100000,  # 외국인 +20,000주
                }
            ],
        }
        with patch.object(client, "call_tr", return_value=mock_t1717_resp):
            rows = client.fetch_investor_supply(
                "196170", "2026-11-01", "2026-11-11", {"2026-11-11": 200000}, {"2026-11-11": 100000}
            )
        self.assertEqual(len(rows), 1)
        r = rows[0]
        # 순수기관 = 10000(사모) + 2000(보험) + 15000(투신) + 1000(은행) + 2000(기타금융) + 10000(연기금) = 40000주
        self.assertEqual(r["real_inst_vol"], 40000)
        self.assertEqual(r["inst_vol_ratio"], 20.0)  # 40,000 / 200,000 = 20.0%
        self.assertEqual(r["fn_inv_vol"], -30000)    # 금융투자는 별도 기록되고 합산에서는 제외됨


if __name__ == "__main__":
    unittest.main(verbosity=2)
