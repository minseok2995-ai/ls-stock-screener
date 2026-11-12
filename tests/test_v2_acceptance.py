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
                "등락폭",
                "등락률",
                "수급 비중",
                "수급 금액",
                "연속 일수",
                "이동평균 추세 현황",
            ],
        )
        self.assertNotIn("등락폭/율", self.script)
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

    def test_ac16_ac17_ac18_v22_filters_and_excel_9cols_js(self) -> None:
        import json
        import subprocess

        # Static check: CHART_SELECT_COLS must include trading_value_m (5.1절 1항)
        chart_cols_m = re.search(r'const CHART_SELECT_COLS\s*=\s*"([^"]+)";', self.script)
        self.assertIsNotNone(chart_cols_m)
        assert chart_cols_m is not None
        self.assertIn("trading_value_m", chart_cols_m.group(1).split(","))

        node_test_js = r"""
const fs = require("fs");
const vm = require("vm");
const html = fs.readFileSync("index.html", "utf8");
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

const elements = {};
function getEl(id) {
  if (!elements[id]) {
    elements[id] = {
      id,
      textContent: "",
      innerHTML: "",
      value: id === "screeningModeSelect" ? "inst_supply" : "",
      classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
      addEventListener() {},
      querySelectorAll() { return []; },
      getContext() { return null; }
    };
  }
  return elements[id];
}

let capturedAoa = null;
let capturedSheet = null;
let capturedFilename = null;

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
  alert() {},
  XLSX: {
    utils: {
      aoa_to_sheet(aoa) {
        capturedAoa = aoa;
        const ws = {};
        return ws;
      },
      book_new() { return {}; },
      book_append_sheet(wb, ws) { capturedSheet = ws; }
    },
    writeFile(wb, filename) {
      capturedFilename = filename;
    }
  },
  window: { addEventListener() {} },
  document: {
    getElementById: getEl,
    querySelectorAll() { return []; },
    createElement() { return getEl("__tmp"); }
  },
  fetch: async () => ({ ok: true, status: 200, json: async () => [], text: async () => "[]" })
};

vm.createContext(sandbox);
vm.runInContext(script, sandbox);

vm.runInContext(`
(() => {
  IS_LIVE_SUPABASE = true;
  TOP_TRADE_DATE = "2026-11-12";
  // Build 70 trading dates ending at 2026-11-12
  const dates = [];
  const endDt = new Date("2026-11-12T00:00:00Z");
  for (let i = 69; i >= 0; i--) {
    const d = new Date(endDt.getTime() - i * 86400000).toISOString().slice(0, 10);
    dates.push(d);
  }
  const dT2 = dates[67], dT1 = dates[68], dT = dates[69];

  MASTERS_LIST = [
    { shcode: "005930", hname: "삼성전자", market: "KOSPI" },
    { shcode: "007330", hname: "소액수급제외주", market: "KOSPI" },
    { shcode: "006650", hname: "대한유화", market: "KOSPI" },
    { shcode: "900099", hname: "저유동성추세전환주", market: "KOSDAQ" }
  ];
  MASTERS_LIST.forEach(m => {
    MASTER_BY_CODE[m.shcode] = m;
    FULL_CHART_LOADED[m.shcode] = true;
  });

  // 1) 005930: 당일 25.4%, 수급금액 42.5억(4250), 거래량 120,000, 거래대금 51.9억(5190) -> day_10/15/20 모두 통과
  RAW_CHARTS_BY_CODE["005930"] = [
    { shcode: "005930", trade_date: dT2, open: 41000, high: 41800, low: 40800, close: 41500, change_rate: 1.2, volume: 100000, trading_value_m: 4150, ema_5: 41000, ema_20: 40500, ema_60: 43000, ema_120: 45000, ema_240: 48000 },
    { shcode: "005930", trade_date: dT1, open: 41500, high: 42000, low: 41200, close: 41700, change_rate: 0.48, volume: 110000, trading_value_m: 4587, ema_5: 41100, ema_20: 40600, ema_60: 43200, ema_120: 45000, ema_240: 48500 },
    { shcode: "005930", trade_date: dT,  open: 41800, high: 43500, low: 41700, close: 43250, change_rate: 4.11, volume: 120000, trading_value_m: 5190, ema_5: 41200, ema_20: 40800, ema_60: 43500, ema_120: 45000, ema_240: 48900 }
  ];
  RAW_SUPPLIES_BY_CODE["005930"] = [
    { shcode: "005930", trade_date: dT2, real_inst_vol: 6000, real_inst_amt: 500, inst_vol_ratio: 6.0, frg_vol_ratio: 1.0 },
    { shcode: "005930", trade_date: dT1, real_inst_vol: 7700, real_inst_amt: 600, inst_vol_ratio: 7.0, frg_vol_ratio: 1.5 },
    { shcode: "005930", trade_date: dT,  real_inst_vol: 30480, real_inst_amt: 4250, inst_vol_ratio: 25.4, frg_vol_ratio: 3.2 }
  ];

  // 2) 007330: 당일 비중 35.0%이지만 수급금액 0.3억(30.0 < 100.0) -> day_10/15/20 모두 제외
  RAW_CHARTS_BY_CODE["007330"] = [
    { shcode: "007330", trade_date: dT, open: 15800, high: 16200, low: 15700, close: 16000, change_rate: 1.27, volume: 50000, trading_value_m: 800, ema_5: 15900, ema_20: 15800, ema_60: 15700, ema_120: 15600, ema_240: 15500 }
  ];
  RAW_SUPPLIES_BY_CODE["007330"] = [
    { shcode: "007330", trade_date: dT, real_inst_vol: 17500, real_inst_amt: 30.0, inst_vol_ratio: 35.0, frg_vol_ratio: 0.0 }
  ];

  // 3) 006650: 당일(T) 거래량 24,000(<30,000)·수급금액 70(<100)·거래대금 480(<500, trading_value_m=0 폴백도 함께 검증!)이지만 3일 평균은 모두 기준 이상 -> day_10 제외, consec_3d_5 포함!
  RAW_CHARTS_BY_CODE["006650"] = [
    { shcode: "006650", trade_date: dT2, open: 19800, high: 20200, low: 19700, close: 20000, change_rate: 1.0, volume: 45000, trading_value_m: 0, ema_5: 19900, ema_20: 19800, ema_60: 19500, ema_120: 19000, ema_240: 18500 },
    { shcode: "006650", trade_date: dT1, open: 20000, high: 20300, low: 19900, close: 20000, change_rate: 0.0, volume: 36000, trading_value_m: 0, ema_5: 19950, ema_20: 19850, ema_60: 19550, ema_120: 19050, ema_240: 18550 },
    { shcode: "006650", trade_date: dT,  open: 20100, high: 20200, low: 19900, close: 20000, change_rate: 0.0, volume: 24000, trading_value_m: 0, ema_5: 20000, ema_20: 19900, ema_60: 19600, ema_120: 19100, ema_240: 18600 }
  ];
  RAW_SUPPLIES_BY_CODE["006650"] = [
    { shcode: "006650", trade_date: dT2, real_inst_vol: 3600, real_inst_amt: 180.0, inst_vol_ratio: 8.0, frg_vol_ratio: 0.5 },
    { shcode: "006650", trade_date: dT1, real_inst_vol: 3420, real_inst_amt: 140.0, inst_vol_ratio: 9.5, frg_vol_ratio: 0.4 },
    { shcode: "006650", trade_date: dT,  real_inst_vol: 3000, real_inst_amt: 70.0,  inst_vol_ratio: 12.5, frg_vol_ratio: -0.2 }
  ];

  // 4) 900099: 하락 추세 전환(2.3절) 충족 + 저유동성(거래량 12,000, 수급금액 45.0) -> inst_supply 제외, trend_reversal 포함!
  RAW_CHARTS_BY_CODE["900099"] = dates.map((d, i) => {
    let o = 8000, h = 8100, l = 7400, c = 7800;
    if (i === 10) { o = 10000; h = 10200; l = 9900; c = 10000; }
    else if (i >= 66 && i <= 68) { o = 7520; h = 7600; l = 7500; c = 7550; }
    else if (i === 69) { o = 7550; h = 8000; l = 7540; c = 7900; }
    return { shcode: "900099", trade_date: d, open: o, high: h, low: l, close: c, change_rate: i === 69 ? 4.64 : 0.0, volume: 12000, trading_value_m: 94.8, ema_5: 7650, ema_20: 7800, ema_60: 8400, ema_120: 9000, ema_240: 9500 };
  });
  RAW_SUPPLIES_BY_CODE["900099"] = dates.map((d, i) => ({
    shcode: "900099", trade_date: d, real_inst_vol: i === 69 ? 1680 : 120, real_inst_amt: 45.0, inst_vol_ratio: i === 69 ? 14.0 : 1.0, frg_vol_ratio: 0.0
  }));

  currentMode = "inst_supply";
  currentInstOpt = "day_10";
  applyScreening();
  const day10Codes = CURRENT_SCREENED_LIST.map(x => x.shcode);

  currentInstOpt = "day_20";
  applyScreening();
  const day20Codes = CURRENT_SCREENED_LIST.map(x => x.shcode);

  currentInstOpt = "consec_3d_5";
  applyScreening();
  const consec3Codes = CURRENT_SCREENED_LIST.map(x => x.shcode);

  currentMode = "trend_reversal";
  applyScreening();
  const revCodes = CURRENT_SCREENED_LIST.map(x => x.shcode);

  // Test Excel export 9 columns, types, signs, -0 prevention, and tie-breaking EMA trend string
  currentMode = "inst_supply";
  currentInstOpt = "day_10";
  CURRENT_SCREENED_LIST = [
    {
      shcode: "5930",
      hname: "하나머티리얼즈",
      close: 43250,
      priceDiff: 1550,
      change_rate: 4.11,
      instRatioT: 53.6,
      instAmtM_T: 4250.0,
      consec5pDays: 3,
      ema_5: 41200,
      ema_20: 40800,
      ema_60: 43500,
      ema_120: 45000,
      ema_240: 48900
    },
    {
      shcode: "166090",
      hname: "음수테스트주",
      close: 51200,
      priceDiff: -1150,
      change_rate: -4.11,
      instRatioT: 12.3,
      instAmtM_T: -320.0,
      consec5pDays: 1,
      ema_5: 50000,
      ema_20: 50000,
      ema_60: 52000,
      ema_120: 52000,
      ema_240: 49000
    },
    {
      shcode: "000660",
      hname: "영값경계주",
      close: 180000,
      priceDiff: -0.2,
      change_rate: -0.002,
      instRatioT: -0.01,
      instAmtM_T: -0.02,
      consec5pDays: 0,
      ema_5: 185000,
      ema_20: 184000,
      ema_60: 183000,
      ema_120: 182000,
      ema_240: 181000
    }
  ];
  exportScreenedToExcel();

  globalThis.__out = {
    day10Codes,
    day20Codes,
    consec3Codes,
    revCodes
  };
})();
`, sandbox);

const negZeroFlags = capturedAoa.slice(1).flatMap(row =>
  row.map(cell => Object.is(cell.v, -0))
);
console.log(JSON.stringify({
  ...sandbox.__out,
  capturedFilename,
  capturedAoa,
  colsWidth: capturedSheet["!cols"],
  hasAnyNegZero: negZeroFlags.some(Boolean)
}));
"""
        proc = subprocess.run(
            ["node", "-e", node_test_js],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        out = json.loads(proc.stdout.strip().splitlines()[-1])

        # AC-16 assertions
        self.assertEqual(out["day10Codes"], ["005930"])
        self.assertEqual(out["day20Codes"], ["005930"])
        self.assertEqual(out["consec3Codes"], ["005930", "006650"])
        self.assertEqual(out["revCodes"], ["900099"])

        # AC-17 & AC-18 assertions
        self.assertEqual(out["capturedFilename"], "2026-11-12_기관수급발생_당일10%이상.xlsx")
        self.assertFalse(out["hasAnyNegZero"])
        aoa = out["capturedAoa"]
        self.assertEqual(
            aoa[0],
            [
                "종목코드",
                "종목명",
                "현재가",
                "등락폭",
                "등락률",
                "수급 비중",
                "수급 금액",
                "연속 일수",
                "이동평균 추세 현황",
            ],
        )

        # Row 1: positive values — NO '+' sign, NO '억'/'일' suffix, proper types
        r1 = aoa[1]
        self.assertEqual(r1[0], {"t": "s", "v": "005930"})
        self.assertEqual(r1[1], {"t": "s", "v": "하나머티리얼즈"})
        self.assertEqual(r1[2], {"t": "n", "v": 43250})
        self.assertEqual(r1[3], {"t": "n", "v": 1550})
        self.assertEqual(r1[4], {"t": "s", "v": "4.11%"})
        self.assertEqual(r1[5], {"t": "s", "v": "53.6%"})
        self.assertEqual(r1[6]["t"], "n")
        self.assertEqual(r1[6]["v"], 42.5)
        self.assertEqual(r1[7], {"t": "n", "v": 3})
        self.assertEqual(r1[8], {"t": "s", "v": "Ema240 > Ema120 > Ema60 > Ema5 > Ema20"})

        # Row 2: negative values + EMA tie-break (span ascending: Ema60 > Ema120 > Ema5 > Ema20 > Ema240)
        r2 = aoa[2]
        self.assertEqual(r2[3], {"t": "n", "v": -1150})
        self.assertEqual(r2[4], {"t": "s", "v": "-4.11%"})
        self.assertEqual(r2[6]["t"], "n")
        self.assertEqual(r2[6]["v"], -3.2)
        self.assertEqual(r2[7], {"t": "n", "v": 1})
        self.assertEqual(r2[8], {"t": "s", "v": "Ema60 > Ema120 > Ema5 > Ema20 > Ema240"})

        # Row 3: near-zero boundary — no "-0.00%" or "-0.0%"
        r3 = aoa[3]
        self.assertEqual(r3[3], {"t": "n", "v": 0})
        self.assertEqual(r3[4], {"t": "s", "v": "0.00%"})
        self.assertEqual(r3[5], {"t": "s", "v": "0.0%"})
        self.assertEqual(r3[6]["v"], 0)
        self.assertEqual(r3[7], {"t": "n", "v": 0})
        self.assertEqual(r3[8], {"t": "s", "v": "Ema5 > Ema20 > Ema60 > Ema120 > Ema240"})

        # Column widths: 9 columns, 9th column wch >= 40
        self.assertEqual(len(out["colsWidth"]), 9)
        self.assertGreaterEqual(out["colsWidth"][8]["wch"], 40)

    def test_ac16_exact_boundary_cutoffs_js_py_parity(self):
        """AC-16 경계값(99.99 vs 100.0 / 29,999 vs 30,000 / 499.99 vs 500.0) JS↔Python 100% 일치 검증"""
        import json
        import subprocess
        import run_daily_screener as rds

        cases = [
            # (code, amt_list, vol_list, tv_list, exp_day10, exp_consec3)
            ("100001", [100.0, 100.0, 100.0], [30000, 30000, 30000], [500.0, 500.0, 500.0], True, True),
            ("100002", [200.0, 200.0, 99.99], [30000, 30000, 30000], [500.0, 500.0, 500.0], False, True),
            ("100003", [100.0, 100.0, 99.97], [30000, 30000, 30000], [500.0, 500.0, 500.0], False, False),
            ("100004", [150.0, 150.0, 150.0], [30001, 30000, 29999], [500.0, 500.0, 500.0], False, True),
            ("100005", [150.0, 150.0, 150.0], [30000, 30000, 29997], [500.0, 500.0, 500.0], False, False),
            ("100006", [150.0, 150.0, 150.0], [35000, 35000, 35000], [500.01, 500.0, 499.99], False, True),
            ("100007", [150.0, 150.0, 150.0], [35000, 35000, 35000], [500.0, 500.0, 499.97], False, False),
        ]
        dts = ["2026-11-10", "2026-11-11", "2026-11-12"]

        py_results = {}
        js_payload = []
        for code, amts, vols, tvs, exp_d10, exp_c3 in cases:
            c_rows = [
                {
                    "shcode": code,
                    "trade_date": dts[i],
                    "open": 10000,
                    "high": 10200,
                    "low": 9900,
                    "close": 10000,
                    "change_rate": 0.0,
                    "volume": vols[i],
                    "trading_value_m": tvs[i],
                    "ema_5": 10000,
                    "ema_20": 9900,
                    "ema_60": 9800,
                    "ema_120": 9700,
                    "ema_240": 9600,
                }
                for i in range(3)
            ]
            s_rows = [
                {
                    "shcode": code,
                    "trade_date": dts[i],
                    "real_inst_vol": 4000,
                    "real_inst_amt": amts[i],
                    "inst_vol_ratio": 12.0,
                    "frg_vol": 0,
                    "frg_vol_ratio": 0.0,
                    "ind_vol": -4000,
                }
                for i in range(3)
            ]
            ev = rds.evaluate_strategy_v2_stock(c_rows, s_rows, "2026-11-12")
            self.assertIsNotNone(ev)
            self.assertEqual(ev["is_day_10"], exp_d10, msg=f"Python day_10 mismatch on {code}")
            self.assertEqual(ev["is_consec_3d_5p"], exp_c3, msg=f"Python consec_3d_5 mismatch on {code}")
            py_results[code] = (ev["is_day_10"], ev["is_consec_3d_5p"])
            js_payload.append({"code": code, "charts": c_rows, "supplies": s_rows})

        js_runner = rf"""
const fs = require("fs");
const vm = require("vm");
const html = fs.readFileSync("index.html", "utf8");
const script = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)]
  .map(m => m[1])
  .filter(s => s.trim().length > 0)
  .pop();
const makeEl = () => ({{ value: "", textContent: "", innerHTML: "", style: {{}}, dataset: {{}}, classList: {{ add(){{}}, remove(){{}}, toggle(){{}}, contains(){{ return false; }} }}, addEventListener(){{}}, getAttribute(){{ return ""; }}, getContext(){{ return null; }} }});
const sandbox = {{
  console, Math, Date, Number, String, Boolean, Array, Object, Promise, Set, Map, RegExp, JSON, Error,
  encodeURIComponent, setTimeout, clearTimeout, parseInt, parseFloat, isNaN, isFinite,
  window: {{ addEventListener(){{}} }},
  document: {{ getElementById: makeEl, querySelectorAll: () => [], createElement: makeEl }},
  fetch: async () => ({{ ok: true, status: 200, json: async () => [], text: async () => "[]" }})
}};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(script, sandbox);
sandbox.__cases = {json.dumps(js_payload)};
const res = vm.runInContext(`
  IS_LIVE_SUPABASE = true;
  TOP_TRADE_DATE = "2026-11-12";
  MASTERS_LIST = __cases.map(item => ({{ shcode: item.code, hname: item.code, market: "KOSPI" }}));
  for (const item of __cases) {{
    MASTER_BY_CODE[item.code] = {{ shcode: item.code, hname: item.code, market: "KOSPI" }};
    FULL_CHART_LOADED[item.code] = true;
    RAW_CHARTS_BY_CODE[item.code] = item.charts;
    RAW_SUPPLIES_BY_CODE[item.code] = item.supplies;
  }}
  currentMode = "inst_supply";
  currentInstOpt = "day_10";
  applyScreening();
  const d10Set = new Set(CURRENT_SCREENED_LIST.map(x => x.shcode));
  currentInstOpt = "consec_3d_5";
  applyScreening();
  const c3Set = new Set(CURRENT_SCREENED_LIST.map(x => x.shcode));
  const out = {{}};
  for (const item of __cases) {{
    out[item.code] = [d10Set.has(item.code), c3Set.has(item.code)];
  }}
  JSON.stringify(out);
`, sandbox);
console.log(res);
"""
        proc = subprocess.run(
            ["node", "-e", js_runner],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        js_results = json.loads(proc.stdout.strip().splitlines()[-1])
        for code, expected_pair in py_results.items():
            self.assertEqual(tuple(js_results[code]), expected_pair, msg=f"JS/Py boundary mismatch on {code}")


if __name__ == "__main__":
    unittest.main()



