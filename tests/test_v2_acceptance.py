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
        # Verify PK-indexed query patterns in index.html (3.5절 & 4.5절)
        self.assertIn(
            "shcode=in.(005930,000660,005380,012450,196170,006650,023160,218410,166090,009420)",
            self.script,
        )
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

    def test_ac13_workflow_schedule_concurrency_failure_alert_and_gs(self) -> None:
        wf_path = REPO_ROOT / ".github" / "workflows" / "daily_batch.yml"
        gs_path = REPO_ROOT / "scripts" / "trigger_daily_batch.gs"
        self.assertTrue(wf_path.exists(), "daily_batch.yml missing")
        self.assertTrue(gs_path.exists(), "scripts/trigger_daily_batch.gs missing")

        wf_text = wf_path.read_text(encoding="utf-8")
        # 3 cron slots: 20:30 KST, 20:47 KST, 21:17 KST
        self.assertIn("cron: '30 11 * * 1-5'", wf_text)
        self.assertIn("cron: '47 11 * * 1-5'", wf_text)
        self.assertIn("cron: '17 12 * * 1-5'", wf_text)
        # Concurrency serialization without canceling active batch
        self.assertIn("concurrency:", wf_text)
        self.assertIn("group: daily-ls-stock-batch", wf_text)
        self.assertIn("cancel-in-progress: false", wf_text)
        # Auto --skip-if-completed on schedule and failure Telegram alert step
        self.assertIn("--skip-if-completed", wf_text)
        self.assertIn("if: failure()", wf_text)
        self.assertIn("api.telegram.org/bot", wf_text)
        self.assertIn("actions/runs/${{ github.run_id }}", wf_text)

        try:
            import yaml  # type: ignore
            parsed = yaml.safe_load(wf_text)
            on_block = parsed.get("on") or parsed.get(True)
            crons = [item["cron"] for item in on_block["schedule"]]
            self.assertEqual(crons, ["30 11 * * 1-5", "47 11 * * 1-5", "17 12 * * 1-5"])
            self.assertEqual(parsed["concurrency"]["cancel-in-progress"], False)
        except ImportError:
            pass

        gs_text = gs_path.read_text(encoding="utf-8")
        self.assertIn("/actions/workflows/daily_batch.yml/dispatches", gs_text)
        self.assertIn("skip_if_completed", gs_text)
        self.assertIn("atHour(20)", gs_text)
        self.assertIn("nearMinute(30)", gs_text)

    def test_ac14_kst_and_completion_threshold_logic(self) -> None:
        # KST(UTC+9) boundary verification
        self.assertEqual(
            rds.get_kst_today(dt.datetime(2026, 11, 12, 11, 30, tzinfo=dt.timezone.utc)),
            dt.date(2026, 11, 12),
        )
        self.assertEqual(
            rds.get_kst_today(dt.datetime(2026, 11, 12, 16, 0, tzinfo=dt.timezone.utc)),
            dt.date(2026, 11, 13),
        )

        # Verify check_daily_batch_completion requires >= 98.5% AND all 3 mega-caps settled
        import unittest.mock as mock

        codes = ["005930", "000660", "005380"] + [f"{i:06d}" for i in range(1000, 1197)]  # 200 stocks
        masters = [{"shcode": c, "is_universe": True} for c in codes]

        def fake_http_get_complete(url: str, headers=None, timeout: float = 30.0):
            m = re.search(r"shcode=in\.\(([^)]+)\)", url)
            chunk = m.group(1).split(",") if m else []
            if "daily_chart" in url:
                return [{"shcode": c, "trade_date": "2026-11-12", "volume": 0 if c.endswith("99") else 50000} for c in chunk]
            return [
                {
                    "shcode": c,
                    "trade_date": "2026-11-12",
                    "real_inst_vol": 0 if c.endswith("99") else 1000,
                    "frg_vol": 0,
                    "ind_vol": 0 if c.endswith("99") else -1000,
                    "fn_inv_vol": 0,
                    "etc_corp_vol": 0,
                }
                for c in chunk
            ]

        with mock.patch.object(rds, "http_get_json", side_effect=fake_http_get_complete):
            comp_ok = rds.check_daily_batch_completion("https://example.supabase.co", "key", masters, "2026-11-12")
            self.assertTrue(comp_ok["is_completed"])
            self.assertTrue(comp_ok["rep_3_settled"])
            self.assertEqual(comp_ok["completion_pct"], 100.0)

    def test_ac15_diversified_top_trade_date_and_sync_badge_js(self) -> None:
        import json
        import subprocess

        node_test_js = r"""
const fs = require("fs");
const vm = require("vm");
const html = fs.readFileSync("index.html", "utf8");
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

function makeEl() {
  return {
    textContent: "",
    innerHTML: "",
    value: "",
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    addEventListener() {},
    querySelectorAll() { return []; },
    getContext() { return null; }
  };
}

let mockRows = [];
const sandbox = {
  console,
  Math,
  Date,
  Number,
  String,
  Boolean,
  Array,
  Object,
  Promise,
  Set,
  Map,
  RegExp,
  JSON,
  encodeURIComponent,
  setTimeout,
  clearTimeout,
  window: { addEventListener() {} },
  document: {
    getElementById() { return makeEl(); },
    querySelectorAll() { return []; },
    createElement() { return makeEl(); }
  },
  fetch: async () => ({
    ok: true,
    status: 200,
    json: async () => sandbox.__mockRows,
    text: async () => JSON.stringify(sandbox.__mockRows)
  })
};
vm.createContext(sandbox);
vm.runInContext(script, sandbox);
vm.runInContext(`
(async () => {
  // Case 1: Mega-caps still at T-1 (2026-11-11), mid/small rep stock at T (2026-11-12)
  globalThis.__mockRows = [
    { shcode: "005930", trade_date: "2026-11-11" },
    { shcode: "000660", trade_date: "2026-11-11" },
    { shcode: "005380", trade_date: "2026-11-11" },
    { shcode: "023160", trade_date: "2026-11-12" }
  ];
  const detectedDate = await fetchLatestSettledTradeDate({});

  // Case 2: Badge text < 95% vs >= 95%
  const masters = Array.from({ length: 100 }, (_, i) => ({ shcode: String(i + 1).padStart(6, "0") }));
  const supplyPartial = {};
  for (let i = 0; i < 60; i++) {
    supplyPartial[masters[i].shcode] = [{ trade_date: "2026-11-12" }];
  }
  const settled60 = countSettledUniverseStocks(masters, {}, supplyPartial, "2026-11-12");
  const badgePartial = formatTradeDateBadgeText("2026-11-12", settled60, masters.length);

  const supplyDone = {};
  for (let i = 0; i < 96; i++) {
    supplyDone[masters[i].shcode] = [{ trade_date: "2026-11-12" }];
  }
  const settled96 = countSettledUniverseStocks(masters, {}, supplyDone, "2026-11-12");
  const badgeDone = formatTradeDateBadgeText("2026-11-12", settled96, masters.length);

  console.log(JSON.stringify({ detectedDate, settled60, badgePartial, settled96, badgeDone }));
})();
`, sandbox);
"""
        proc = subprocess.run(
            ["node", "-e", node_test_js],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        out = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(out["detectedDate"], "2026-11-12")
        self.assertEqual(out["settled60"], 60)
        self.assertEqual(
            out["badgePartial"],
            "기준일: 2026-11-12 (일일 배치 동기화 진행 중: 60/100종목)",
        )
        self.assertEqual(out["settled96"], 96)
        self.assertEqual(out["badgeDone"], "기준일: 2026-11-12")


if __name__ == "__main__":
    unittest.main()

