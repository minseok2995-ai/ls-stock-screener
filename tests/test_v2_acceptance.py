import datetime as dt
import re
import unittest
from pathlib import Path

import run_daily_screener as rds

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML_PATH = REPO_ROOT / "index.html"


class TestStrategyV2Acceptance(unittest.TestCase):
    """AC-7 ~ AC-12 regression tests for index.html and Strategy v2.0 formulas."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.html = INDEX_HTML_PATH.read_text(encoding="utf-8")
        script_match = re.search(r"<script>([\s\S]*?)</script>", cls.html)
        assert script_match is not None, "Inline <script> block missing in index.html"
        cls.script = script_match.group(1)

    def test_ac7_slim_header_and_no_dead_dom_references(self) -> None:
        title_m = re.search(r"<title>([^<]+)</title>", self.html)
        h1_m = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", self.html)
        self.assertIsNotNone(title_m)
        self.assertIsNotNone(h1_m)
        self.assertEqual(title_m.group(1).strip(), "기관 수급 종목 스크리너")
        self.assertEqual(h1_m.group(1).strip(), "기관 수급 종목 스크리너")

        expected_formula_notice = (
            "순수 기관 = 금융투자를 제외한 투신 + 보험 + 은행 + 종금(기타금융) + 연기금 등 + 사모펀드"
        )
        self.assertIn(expected_formula_notice, self.html)

        forbidden_legacy_tokens = [
            "verifyModal",
            "telegramModal",
            "supabaseModal",
            "btnTelegramPreview",
            "btnCloudConfig",
            "updateTelegramPreview",
            "renderVerificationReport",
            "toggleModal",
            "dbStatusBadge",
            "inputSupabaseUrl",
            "filterEma",
        ]
        for token in forbidden_legacy_tokens:
            self.assertNotIn(token, self.html, f"Legacy token should be removed: {token}")

        html_ids = set(re.findall(r'\bid="([^"]+)"', self.html))
        script_ids = set(re.findall(r'getElementById\("([^"]+)"\)', self.script))
        missing_ids = script_ids - html_ids
        self.assertEqual(missing_ids, set(), f"Script references missing DOM IDs: {missing_ids}")

    def test_ac8_control_bar_modes_and_suboptions(self) -> None:
        select_m = re.search(r'<select id="filterMode"[\s\S]*?</select>', self.html)
        self.assertIsNotNone(select_m)
        opts = [
            (m.group(1), m.group(2).strip())
            for m in re.finditer(r'<option\s+value="([^"]+)"[^>]*>([^<]+)</option>', select_m.group(0))
        ]
        self.assertEqual(
            opts,
            [
                ("inst_supply", "기관 수급 발생 종목"),
                ("trend_reversal", "하락 추세 전환 수급 발생"),
            ],
        )

        sub_wrap_m = re.search(r'<div[^>]*id="instSubOptionButtons"[^>]*>([\s\S]*?)</div>', self.html)
        self.assertIsNotNone(sub_wrap_m)
        btns = [
            (m.group(1), m.group(2).strip())
            for m in re.finditer(r'data-subopt="([^"]+)"[\s\S]*?>([\s\S]*?)</button>', sub_wrap_m.group(1))
        ]
        self.assertEqual(
            btns,
            [
                ("day_10", "당일 10% 이상"),
                ("day_15", "당일 15% 이상"),
                ("day_20", "당일 20% 이상"),
                ("consec_3d_5", "3일 연속 5% 이상"),
            ],
        )

    def test_ac10_and_ac11_table_columns_and_excel_spec(self) -> None:
        thead_m = re.search(r"<thead[\s\S]*?</thead>", self.html)
        self.assertIsNotNone(thead_m)
        ths = [m.group(1).strip() for m in re.finditer(r"<th[^>]*>([^<]+)</th>", thead_m.group(0))]
        self.assertEqual(
            ths,
            ["종목명", "현재가", "등락율", "수급비중", "수급금액", "외국인비중", "연속일수"],
        )

        self.assertIn("xlsx-0.20.3/package/dist/xlsx.full.min.js", self.html)
        expected_suffixes = [
            "_하락추세전환수급발생.xlsx",
            "_기관수급발생_당일10%이상.xlsx",
            "_기관수급발생_당일15%이상.xlsx",
            "_기관수급발생_당일20%이상.xlsx",
            "_기관수급발생_3일연속5%이상.xlsx",
        ]
        for suffix in expected_suffixes:
            self.assertIn(suffix, self.script)

        headers_m = re.search(r"const headers = \[([\s\S]*?)\];", self.script)
        self.assertIsNotNone(headers_m)
        excel_cols = re.findall(r'"([^"]+)"', headers_m.group(1))
        self.assertEqual(
            excel_cols,
            [
                "종목코드",
                "종목명",
                "현재가",
                "등락폭/율",
                "수급 비중",
                "수급 금액",
                "Ema5",
                "Ema20",
                "Ema60",
                "Ema120",
                "Ema240",
            ],
        )
        self.assertIn('padStart(6, "0")', self.script)

    def test_ac9_and_ac12_boundary_conditions_and_pk_queries(self) -> None:
        # Verify PK-indexed query patterns in index.html (3.5절)
        self.assertIn("shcode=in.(005930,000660,005380)", self.script)
        self.assertIn("const CHUNK_SIZE = 28;", self.script)
        self.assertIn("trade_date.lte.${TOP_TRADE_DATE}", self.script)
        self.assertIn("trade_date=lte.${TOP_TRADE_DATE}", self.script)

        # Verify exact -15.0% drawdown boundary and 5.0% / 10.0% boundaries in evaluate_strategy_v2_stock
        base_dt = dt.date(2026, 7, 1)
        charts = []
        supplies = []
        for i in range(70):
            d = (base_dt + dt.timedelta(days=i)).isoformat()
            if i == 10:
                o, h, l, c = 10000, 10000, 9900, 10000
            elif i < 66:
                o, h, l, c = 8600, 8700, 8400, 8550
            elif i in (66, 67, 68):  # T-3, T-2, T-1 stabilization at exactly -15.0% (8500 / 10000 - 1 = -15.0%)
                o, h, l, c = 8480, 8550, 8450, 8500
            else:  # i == 69 (T): bullish candle above EMA5
                o, h, l, c = 8500, 9000, 8490, 8900

            charts.append({
                "shcode": "000001",
                "trade_date": d,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "change_rate": 4.71 if i == 69 else 0.0,
                "volume": 100000,
                "ema_5": 8600.0,
                "ema_20": 8800.0,
                "ema_60": 9200.0,
                "ema_120": 9600.0,
                "ema_240": 9800.0,
            })
            ratio = 10.0 if i == 69 else 4.99
            supplies.append({
                "shcode": "000001",
                "trade_date": d,
                "real_inst_vol": int(ratio * 1000),
                "real_inst_amt": 500.0,
                "inst_vol_ratio": ratio,
                "frg_vol": 0,
                "frg_vol_ratio": 0.0,
            })

        ref_t = charts[-1]["trade_date"]
        ev_pass = rds.evaluate_strategy_v2_stock(charts, supplies, ref_t)
        self.assertIsNotNone(ev_pass)
        self.assertTrue(ev_pass["is_trend_reversal"])
        self.assertEqual(ev_pass["consec_5p_days"], 1)
        self.assertEqual(ev_pass["price_diff"], 400)

        # If one of prior 10 days had exactly 5.0% (>= 5.0%), Type A must fail
        supplies_fail = [dict(s) for s in supplies]
        supplies_fail[-5]["inst_vol_ratio"] = 5.0
        ev_fail = rds.evaluate_strategy_v2_stock(charts, supplies_fail, ref_t)
        self.assertIsNotNone(ev_fail)
        self.assertFalse(ev_fail["is_trend_reversal"])


if __name__ == "__main__":
    unittest.main()
