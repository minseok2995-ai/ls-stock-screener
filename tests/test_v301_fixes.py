"""
v3.0.1 핫픽스 검증 테스트 스위트 (ISSUE-023 ~ ISSUE-028)
- ISSUE-023 (HIGH): Step 1-B stocks_master 추세 스냅샷 Upsert 시 시세·유동성 컬럼 보존 및 최신 마스터 재조회
- ISSUE-024 (MED): daily_supply_analysis 동일 거래일 prelim 잔존/탈락 행 자동 정리 및 빈 후보 삭제 금지 가드
- ISSUE-025 (MED): 750영업일 표준 추세 입력 윈도우 통일(백엔드·common.js·index.html), >1,000행 페이지네이션 무손실, 차트 재로드 시 탭/선택 불변
- ISSUE-026 (MED-LOW): v3.0 단계형 signal_type('A-1..C-2')의 '단기혼합' 과거 승률 트랙 오염 차단
- ISSUE-027 (LOW): 실제 urllib.error.HTTPError(400) 본문 기반 PGRST204 폴백 동작 및 일반 400 즉시 전파
- ISSUE-028 (LOW): 시총 0.1% 정확 경계(700억 / 0.7억 등) 부동소수 오차 보정 3중 일치
"""
from __future__ import annotations

import datetime as dt
import http.client
import http.server
import io
import json
import pathlib
import subprocess
import threading
import unittest
import urllib.error
from unittest import mock

import run_daily_screener as s

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _run_node_json(js_code: str) -> dict:
    proc = subprocess.run(
        ["node"],
        input=js_code,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _trading_dates(n: int, start: dt.date = dt.date(2022, 1, 3)) -> list[str]:
    out: list[str] = []
    cur = start
    while len(out) < n:
        if cur.weekday() < 5:
            out.append(cur.isoformat())
        cur += dt.timedelta(days=1)
    return out


class TestIssue023MasterSnapshotPreservation(unittest.TestCase):
    """ISSUE-023: Step 1-B 스냅샷이 배치가 갱신한 stocks_master 시세·유동성 컬럼을 덮어쓰지 않는지 검증"""

    def test_snapshot_columns_exclude_price_and_liquidity_fields(self):
        forbidden = {"shares", "market_cap_eok", "avg_vol_20d", "avg_val_20d_eok", "is_universe", "last_close"}
        self.assertEqual(forbidden.intersection(set(s.STOCKS_MASTER_TREND_UPSERT_COLS)), set())
        self.assertEqual(
            s.STOCKS_MASTER_TREND_UPSERT_COLS,
            (
                "shcode",
                "hname",
                "market",
                "trend_camp",
                "trend_stage_code",
                "trend_detail_code",
                "trend_full_label",
                "trend_updated_date",
            ),
        )

    def test_batch_updated_master_preserved_after_step1b_and_fresh_fetch_used(self):
        dates = _trading_dates(300)
        ref_date = dates[-1]
        bars = s.compute_ema_series([
            {
                "shcode": "005930",
                "trade_date": d,
                "open": 1000 + i,
                "high": 1010 + i,
                "low": 995 + i,
                "close": 1005 + i,
                "volume": 200000,
                "trading_value_m": 2500.0,
            }
            for i, d in enumerate(dates)
        ])
        bars[-1]["close"] = 1100

        # In-memory PostgREST merge-duplicates 시뮬레이터:
        # 전달된 payload 에 존재하는 키만 기존 행에 덮어씀
        db_masters = {
            "005930": {
                "shcode": "005930",
                "hname": "삼성전자",
                "market": "KOSPI",
                "shares": 600000,
                "market_cap_eok": 6600.0,   # 메인 배치가 방금 갱신한 최신 시총(1,100원 기준)
                "avg_vol_20d": 222000,      # 메인 배치가 방금 갱신한 최신 20일 거래량
                "avg_val_20d_eok": 244.2,   # 메인 배치가 방금 갱신한 최신 20일 거래대금
                "is_universe": True,
                "last_close": 1100,         # 메인 배치가 방금 갱신한 최신 종가
            }
        }
        stale_masters = [
            {
                "shcode": "005930",
                "hname": "삼성전자",
                "market": "KOSPI",
                "shares": 590000,
                "market_cap_eok": 5900.0,
                "avg_vol_20d": 180000,
                "avg_val_20d_eok": 180.0,
                "is_universe": True,
                "last_close": 1000,         # 배치 시작 시점의 낡은 값
            }
        ]

        captured_payloads: list[dict] = []

        def fake_merge_upsert(u, k, table, conflict, rows, *a, **kw):
            if table == "stocks_master":
                for row in rows:
                    captured_payloads.append(dict(row))
                    cur = db_masters.setdefault(row["shcode"], {})
                    for col_k, col_v in row.items():
                        cur[col_k] = col_v

        with mock.patch.object(s, "supabase_upsert", side_effect=fake_merge_upsert):
            updated_cnt = s.update_universe_trend_snapshots(
                sb_url="https://mock.supabase.co",
                sb_key="mock_key",
                target_date=ref_date,
                universe_masters=stale_masters,
                preloaded_chart_map={"005930": bars},
            )

        self.assertEqual(updated_cnt, 1)
        self.assertEqual(len(captured_payloads), 1)
        for col in ("shares", "market_cap_eok", "avg_vol_20d", "avg_val_20d_eok", "is_universe", "last_close"):
            self.assertNotIn(col, captured_payloads[0])

        # 배치가 갱신한 시세·유동성 컬럼이 100% 그대로 보존되었는지 검증
        after = db_masters["005930"]
        self.assertEqual(after["last_close"], 1100)
        self.assertEqual(after["market_cap_eok"], 6600.0)
        self.assertEqual(after["avg_vol_20d"], 222000)
        self.assertEqual(after["avg_val_20d_eok"], 244.2)
        self.assertEqual(after["shares"], 600000)
        self.assertEqual(after["trend_updated_date"], ref_date)
        self.assertTrue(after["trend_stage_code"])

        # existing_masters=None 전달 시 최신 DB 마스터(시총 6,600억)를 재조회하여 Step 1-A 스코어링에도 반영하는지 확인
        supplies = [
            {
                "shcode": "005930",
                "trade_date": d,
                "real_inst_vol": 30000,
                "real_inst_amt": 660.0,  # 6.6억 == 시총 6,600억의 0.1%
                "inst_vol_ratio": 15.0,
                "frg_vol": 1000,
                "frg_amt": 20.0,
                "frg_vol_ratio": 0.5,
                "ind_vol": -31000,
                "fn_inv_vol": 0,
                "etc_corp_vol": 0,
            }
            for d in dates[-5:]
        ]
        dsa_rows_saved: list[dict] = []

        def fake_get(url, headers=None, timeout=25.0):
            if "/excluded_stocks?" in url or "/daily_supply_analysis?" in url:
                return []
            if "shcode=eq.005930" in url and "limit=5" in url:
                return [{"trade_date": d} for d in reversed(dates[-5:])]
            if "/daily_chart?" in url:
                return list(bars)
            if "/daily_investor_supply?" in url:
                return list(supplies)
            return []

        def fake_upsert_all(u, k, table, conflict, rows, *a, **kw):
            if table == "daily_supply_analysis":
                dsa_rows_saved.extend(rows)

        with mock.patch.object(s, "supabase_fetch_existing_masters", return_value=[dict(db_masters["005930"])]) as m_fetch, \
             mock.patch.object(s, "http_get_json", side_effect=fake_get), \
             mock.patch.object(s, "http_request_json", return_value=[]), \
             mock.patch.object(s, "supabase_upsert", side_effect=fake_upsert_all):
            s.run_daily_supply_analysis_pipeline(
                sb_url="https://mock.supabase.co",
                sb_key="mock_key",
                ref_date=ref_date,
                existing_masters=None,
                effective_slot="prelim",
            )
        m_fetch.assert_called_once()
        self.assertEqual(dsa_rows_saved[0]["market_cap_eok"], 6600.0)
        self.assertEqual(dsa_rows_saved[0]["avg_val_20d_eok"], 244.2)


class TestIssue024StaleSameDayCleanup(unittest.TestCase):
    """ISSUE-024: prelim -> final 후보 축소 시 동일 거래일 탈락 행 삭제 및 빈 후보 시 삭제 금지 가드 검증"""

    def test_prelim_to_final_deletes_dropped_candidate_and_keeps_unique_ranks(self):
        dates = _trading_dates(60)
        ref_date = dates[-1]
        codes = ("000010", "000020", "000030")
        masters = [
            {"shcode": c, "hname": f"종목{c}", "market": "KOSPI", "market_cap_eok": 2000.0, "avg_val_20d_eok": 25.0, "is_universe": True}
            for c in codes
        ]
        charts_by_code = {
            c: s.compute_ema_series([
                {
                    "shcode": c,
                    "trade_date": d,
                    "open": 10000,
                    "high": 10400,
                    "low": 9900,
                    "close": 10200 + idx * 10,
                    "volume": 100000,
                    "trading_value_m": 1020.0,
                }
                for idx, d in enumerate(dates)
            ])
            for c in codes
        }

        def make_supplies(ratio_by_code: dict[str, float]) -> dict[str, list[dict]]:
            out = {}
            for c, r_today in ratio_by_code.items():
                out[c] = [
                    {
                        "shcode": c,
                        "trade_date": d,
                        "real_inst_vol": int(r_today * 1000) if d == ref_date else 1000,
                        "real_inst_amt": 500.0 if d == ref_date else 20.0,
                        "inst_vol_ratio": r_today if d == ref_date else 1.0,
                        "frg_vol": 500,
                        "frg_amt": 10.0,
                        "frg_vol_ratio": 0.5,
                        "ind_vol": -1500,
                        "fn_inv_vol": 0,
                        "etc_corp_vol": 0,
                    }
                    for d in dates[-5:]
                ]
            return out

        dsa_table: dict[tuple[str, str], dict] = {}
        delete_urls: list[str] = []
        current_supplies = make_supplies({"000010": 18.0, "000020": 14.0, "000030": 11.5})

        def fake_get(url, headers=None, timeout=25.0):
            if "/excluded_stocks?" in url or "/daily_supply_analysis?" in url:
                return []
            if "shcode=eq.005930" in url:
                return [{"trade_date": d} for d in reversed(dates[-5:])]
            if "trade_date=in.(" in url:
                dt_set = set(url.split("trade_date=in.(")[1].split(")")[0].split(","))
                ch_codes = url.split("shcode=in.(")[1].split(")")[0].split(",")
                src = charts_by_code if "/daily_chart?" in url else current_supplies
                return [r for c in ch_codes for r in src.get(c, []) if r["trade_date"] in dt_set]
            if "/daily_chart?" in url and "shcode=in.(" in url:
                ch_codes = url.split("shcode=in.(")[1].split(")")[0].split(",")
                return [r for c in ch_codes for r in charts_by_code.get(c, [])]
            if "/daily_investor_supply?" in url and "shcode=in.(" in url:
                ch_codes = url.split("shcode=in.(")[1].split(")")[0].split(",")
                return [r for c in ch_codes for r in current_supplies.get(c, [])]
            return []

        def fake_upsert(u, k, table, conflict, rows, *a, **kw):
            if table == "daily_supply_analysis":
                for r in rows:
                    dsa_table[(r["trade_date"], r["shcode"])] = dict(r)

        def fake_request(method, url, payload=None, headers=None, timeout=30.0):
            if method.upper() == "DELETE" and "/daily_supply_analysis?" in url and "shcode=not.in.(" in url:
                delete_urls.append(url)
                td = url.split("trade_date=eq.")[1].split("&")[0]
                keep = set(url.split("shcode=not.in.(")[1].split(")")[0].split(","))
                removed = []
                for key in list(dsa_table.keys()):
                    if key[0] == td and key[1] not in keep:
                        removed.append(dsa_table.pop(key))
                return removed
            return []

        # 1) prelim 슬롯: 3종목 적재 (000010, 000020, 000030)
        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "", "ANALYSIS_FORCE_RUN": "0"}, clear=False), \
             mock.patch.object(s, "http_get_json", side_effect=fake_get), \
             mock.patch.object(s, "http_request_json", side_effect=fake_request), \
             mock.patch.object(s, "supabase_upsert", side_effect=fake_upsert):
            s.run_daily_supply_analysis_pipeline(
                sb_url="https://mock.supabase.co",
                sb_key="mock_key",
                ref_date=ref_date,
                existing_masters=masters,
                effective_slot="prelim",
                update_master_trends=False,
            )

        self.assertEqual({k[1] for k in dsa_table if k[0] == ref_date}, {"000010", "000020", "000030"})

        # 2) final 슬롯: 확정 수급에서 000030이 3.0%로 하락하여 후보 탈락 -> 2종목만 남아야 함
        delete_urls.clear()
        current_supplies = make_supplies({"000010": 19.0, "000020": 13.5, "000030": 3.0})
        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "", "ANALYSIS_FORCE_RUN": "0"}, clear=False), \
             mock.patch.object(s, "http_get_json", side_effect=fake_get), \
             mock.patch.object(s, "http_request_json", side_effect=fake_request), \
             mock.patch.object(s, "supabase_upsert", side_effect=fake_upsert):
            res_final = s.run_daily_supply_analysis_pipeline(
                sb_url="https://mock.supabase.co",
                sb_key="mock_key",
                ref_date=ref_date,
                existing_masters=masters,
                effective_slot="final",
                update_master_trends=False,
            )

        self.assertEqual(len(delete_urls), 1)
        self.assertIn(f"trade_date=eq.{ref_date}", delete_urls[0])
        self.assertIn("shcode=not.in.(", delete_urls[0])
        self.assertEqual(res_final["stale_deleted"], 1)

        remaining_rows = sorted(
            [r for (td, _), r in dsa_table.items() if td == ref_date],
            key=lambda x: x["daily_rank"],
        )
        self.assertEqual([r["shcode"] for r in remaining_rows], ["000010", "000020"])
        self.assertEqual([r["daily_rank"] for r in remaining_rows], [1, 2])

        # 3) 후보가 0건(ranked_rows == [])인 비정상/휴장 상황에서는 동일 일자 DELETE 절대 미호출
        delete_urls.clear()
        current_supplies = make_supplies({"000010": 1.0, "000020": 1.0, "000030": 1.0})
        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "", "ANALYSIS_FORCE_RUN": "0"}, clear=False), \
             mock.patch.object(s, "http_get_json", side_effect=fake_get), \
             mock.patch.object(s, "http_request_json", side_effect=fake_request), \
             mock.patch.object(s, "supabase_upsert", side_effect=fake_upsert):
            s.run_daily_supply_analysis_pipeline(
                sb_url="https://mock.supabase.co",
                sb_key="mock_key",
                ref_date=ref_date,
                existing_masters=masters,
                effective_slot="prelim",
                update_master_trends=False,
            )
        self.assertEqual(len(delete_urls), 0)
        # 기존 적재 행도 보존됨
        self.assertEqual({k[1] for k in dsa_table if k[0] == ref_date}, {"000010", "000020"})


class TestIssue025Window750ParityAndChartStability(unittest.TestCase):
    """ISSUE-025: 750봉 표준 추세 입력 윈도우 3중 일치 · >1,000행 페이지네이션 무손실 · 차트 재로드 시 탭/선택 불변"""

    def _build_camp_sensitive_850_bars(self) -> list[dict]:
        dates = _trading_dates(850)
        bars: list[dict] = []
        for i, d in enumerate(dates):
            if i < 420:
                # 인덱스 100~419(=750봉 윈도우 내 인덱스 0~319, 즉 i_win >= 239 구간 포함)에서 완전정배열(fullBull) 확립 -> camp = BULL
                c, e5, e20, e60, e120, e240 = 22000, 21500, 20500, 19500, 18500, 17500
            else:
                # 인덱스 420~849(최근 430봉, 즉 308봉 윈도우 전체): e60 < e120 이나 e20 > e60 부분 반등 섞임(fullBear 아님!)
                # - 750봉 윈도우: 앞에서 확립된 BULL 유지 -> A-5 (#27)
                # - 308봉 윈도우: 첫 봉부터 e60 < e120 으로 시작 -> BEAR 오판(B-7 #55)!
                c, e5, e20, e60, e120, e240 = 15000, 15200, 15600, 16200, 17000, 16800
                c, e5 = 14800, 15100
            bars.append({
                "shcode": "009970",
                "trade_date": d,
                "open": c - 100,
                "high": c + 150,
                "low": c - 150,
                "close": c,
                "change_rate": 1.2,
                "volume": 120000,
                "trading_value_m": 1800.0,
                "ema_5": float(e5),
                "ema_20": float(e20),
                "ema_60": float(e60),
                "ema_120": float(e120),
                "ema_240": float(e240),
            })
        return bars

    def test_750_bar_window_parity_across_python_common_and_index_and_chart_reload_stability(self):
        bars_850 = self._build_camp_sensitive_850_bars()
        ref_date = bars_850[-1]["trade_date"]

        # 308봉 짧은 윈도우에서는 실제로 BEAR 진영으로 반전됨을 먼저 입증
        short_308 = s.classify_trend_cycle_series(bars_850[-308:])[-1]
        self.assertEqual(short_308["trend_camp"], "BEAR")

        # Python 백엔드 (DSA Step 1-A & Master Snapshot Step 1-B) 750봉 표준 윈도우 결과
        supplies = [{
            "shcode": "009970",
            "trade_date": ref_date,
            "real_inst_vol": 25000,
            "real_inst_amt": 450.0,
            "inst_vol_ratio": 20.8,
            "frg_vol": 1000,
            "frg_amt": 15.0,
            "frg_vol_ratio": 0.8,
        }]
        py_scored = s.score_daily_supply_candidate(
            bars_850,
            supplies,
            master_row={"shcode": "009970", "hname": "영풍정밀테스트", "market": "KOSDAQ", "market_cap_eok": 3000.0},
            ref_date=ref_date,
        )
        self.assertEqual(py_scored["trend_camp"], "BULL")
        self.assertEqual(py_scored["trend_stage_code"], "A-5")

        snap_rows: list[dict] = []
        with mock.patch.object(s, "supabase_upsert", side_effect=lambda u, k, t, c, r, *a, **kw: snap_rows.extend(r)):
            s.update_universe_trend_snapshots(
                "https://mock.supabase.co",
                "mock_key",
                ref_date,
                [{"shcode": "009970", "hname": "영풍정밀테스트", "market": "KOSDAQ", "is_universe": True}],
                preloaded_chart_map={"009970": bars_850},
            )
        self.assertEqual(snap_rows[0]["trend_camp"], py_scored["trend_camp"])
        self.assertEqual(snap_rows[0]["trend_stage_code"], py_scored["trend_stage_code"])
        self.assertEqual(snap_rows[0]["trend_detail_code"], py_scored["trend_detail_code"])

        # Node VM에서 common.js(ProChart 모달/호버) & index.html(리스트 + 차트 750봉 재로드 후 탭/선택 불변) 동시 검증
        payload_json = json.dumps({"bars850": bars_850, "supplies": supplies, "refDate": ref_date})
        js_clean = """
const fs = require("fs");
const vm = require("vm");
const C = require(require("path").resolve("common.js"));
const html = fs.readFileSync("index.html", "utf8");
const script = [...html.matchAll(/<script\\b[^>]*>([\\s\\S]*?)<\\/script>/gi)].map(m => m[1]).filter(x => x.trim()).pop();
const DATA = """ + payload_json + """;

const commonLatest = C.TrendCycle.classifyLatest(DATA.bars850, DATA.refDate);
const commonWin = C.TrendCycle.classifyWindowedSeries(DATA.bars850);
const commonWinLast = commonWin[commonWin.length - 1];

const mockCanvasCtx = () => new Proxy(function () {}, {
  get: (t, k) => k === "measureText" ? () => ({ width: 12 }) : (k === "canvas" ? {} : mockCanvasCtx()),
  apply: () => mockCanvasCtx(),
  set: () => true
});
const elements = {};
function makeNode(id) {
  const listeners = {};
  const children = {};
  return {
    id: id || "", textContent: "", _html: "", value: "", checked: false,
    clientWidth: 640, width: 640, height: 360, style: {}, dataset: {}, className: "",
    classList: { _s: new Set(["hidden"]), add(c){this._s.add(c);}, remove(c){this._s.delete(c);}, contains(c){return this._s.has(c);}, toggle(c){this._s.has(c)?this._s.delete(c):this._s.add(c);} },
    addEventListener(ev, fn) { listeners[ev] = fn; },
    trigger(ev, p) { if (listeners[ev]) return listeners[ev](p || {}); },
    getBoundingClientRect() { return { left: 0, top: 0, width: 640, height: 360 }; },
    getContext() { return mockCanvasCtx(); },
    querySelector(sel) { if (!children[sel]) children[sel] = makeNode(sel); return children[sel]; },
    querySelectorAll() { return []; },
    set innerHTML(v) { this._html = String(v); },
    get innerHTML() { return this._html; }
  };
}
const fetchedUrls = [];
const sandbox = {
  console, Math, Date, Number, String, Boolean, Array, Object, Promise, Set, Map, RegExp, JSON, Error,
  encodeURIComponent, setTimeout: (fn) => { fn(); return 1; }, clearTimeout, parseInt, parseFloat, isNaN, isFinite,
  window: { LSCommon: C, innerHeight: 940, addEventListener() {} },
  document: { getElementById: id => (elements[id] || (elements[id] = makeNode(id))), querySelectorAll: () => [], createElement: t => makeNode(t) },
  fetch: async (url) => {
    fetchedUrls.push(String(url));
    if (String(url).includes("daily_chart")) return { ok: true, status: 200, json: async () => DATA.bars850.slice(-750).slice().reverse() };
    return { ok: true, status: 200, json: async () => DATA.supplies };
  }
};
sandbox.globalThis = sandbox;
C._setFetch(sandbox.fetch);
vm.createContext(sandbox);
vm.runInContext(script, sandbox);
sandbox.__DATA = DATA;

(async () => {
  const uiRes = await vm.runInContext(`(async () => {
    IS_LIVE_SUPABASE = true;
    TOP_TRADE_DATE = __DATA.refDate;
    MASTERS_LIST = [
      { shcode: "009970", hname: "영풍정밀테스트", market: "KOSDAQ", market_cap_eok: 3000, avg_val_20d_eok: 20 }
    ];
    MASTER_BY_CODE["009970"] = MASTERS_LIST[0];
    FULL_CHART_LOADED["009970"] = true;
    RAW_CHARTS_BY_CODE["009970"] = __DATA.bars850.slice(-45);
    RAW_SUPPLIES_BY_CODE["009970"] = __DATA.supplies;

    await ensureSupplyCandidatesWarmup();
    applyScreening();
    setTrendStage("A-5");
    const beforeCamp = currentCamp;
    const beforeStage = currentStage;
    const beforeSelected = selectedShcode;
    const item = CURRENT_SCREENED_LIST.find(x => x.shcode === "009970");

    // 차트 720일 로드(syncRecommendationAfterLoad) 강제 트리거 시에도 탭/선택이 절대 바뀌지 않아야 함
    syncRecommendationAfterLoad(item);

    return {
      itemTrend: {
        camp: item.trend_camp,
        stage: item.trend_stage_code,
        detail: item.trend_detail_code
      },
      beforeCamp,
      afterCamp: currentCamp,
      beforeStage,
      afterStage: currentStage,
      beforeSelected,
      afterSelected: selectedShcode,
      screenedCodes: CURRENT_SCREENED_LIST.map(x => x.shcode)
    };
  })()`, sandbox);

  console.log(JSON.stringify({
    commonLatest,
    commonWinLen: commonWin.length,
    commonWinLast,
    fetchedUrls,
    uiRes
  }));
})();
"""
        r = _run_node_json(js_clean)
        self.assertEqual(r["commonWinLen"], 850)
        self.assertEqual(r["commonLatest"]["trend_camp"], py_scored["trend_camp"])
        self.assertEqual(r["commonLatest"]["trend_stage_code"], py_scored["trend_stage_code"])
        self.assertEqual(r["commonLatest"]["trend_detail_code"], py_scored["trend_detail_code"])
        self.assertEqual(r["commonWinLast"]["trend_detail_code"], py_scored["trend_detail_code"])

        self.assertEqual(r["uiRes"]["itemTrend"]["camp"], py_scored["trend_camp"])
        self.assertEqual(r["uiRes"]["itemTrend"]["stage"], py_scored["trend_stage_code"])
        self.assertEqual(r["uiRes"]["itemTrend"]["detail"], py_scored["trend_detail_code"])
        self.assertTrue(any("limit=750" in u for u in r["fetchedUrls"]))
        self.assertEqual(r["uiRes"]["beforeCamp"], r["uiRes"]["afterCamp"])
        self.assertEqual(r["uiRes"]["beforeStage"], r["uiRes"]["afterStage"])
        self.assertEqual(r["uiRes"]["beforeSelected"], "009970")
        self.assertEqual(r["uiRes"]["afterSelected"], "009970")
        self.assertEqual(r["uiRes"]["screenedCodes"], ["009970"])

    def test_multi_stock_chunk_over_1000_rows_paginates_without_truncation(self):
        dates = _trading_dates(750)
        ref_date = dates[-1]
        cutoff = _trading_dates(1)[0]
        codes = ["000010", "000020", "000030"]  # 3종목 × 750봉 = 2,250행 (> 1,000행 상한)
        all_rows = [
            {"shcode": c, "trade_date": d, "close": 10000 + i}
            for c in codes
            for i, d in enumerate(dates)
        ]
        all_rows.sort(key=lambda r: (r["shcode"], r["trade_date"]))

        calls: list[str] = []

        def fake_postgrest_capped_get(url, headers=None, timeout=25.0):
            calls.append(url)
            offset = int(url.split("offset=")[1].split("&")[0]) if "offset=" in url else 0
            # 실제 PostgREST 서버와 동일하게 응답당 최대 1,000행 강제 절단
            return all_rows[offset : offset + 1000]

        with mock.patch.object(s, "http_get_json", side_effect=fake_postgrest_capped_get):
            out = s._fetch_chart_window_for_codes(
                base="https://mock.supabase.co",
                headers={},
                codes=codes,
                cutoff_date=cutoff,
                target_date=ref_date,
                select_cols="shcode,trade_date,close",
                max_bars=750,
                chunk_size=3,
                max_workers=2,
            )

        self.assertEqual(len(calls), 3)  # offset=0(1000) + offset=1000(1000) + offset=2000(250)
        for c in codes:
            self.assertEqual(len(out[c]), 750)
            self.assertEqual(out[c][0]["trade_date"], dates[0])
            self.assertEqual(out[c][-1]["trade_date"], ref_date)


class TestIssue026TrackStatsNoV30Pollution(unittest.TestCase):
    """ISSUE-026: prior_dsa_rows 의 v3.0 추세 단계 signal_type 이 '단기혼합' 트랙 표본을 오염시키지 않는지 검증"""

    def test_v30_stage_signal_types_do_not_increment_short_mixed_track(self):
        prior_rows = [
            {"trade_date": "2026-10-01", "shcode": "000010", "signal_type": "A-3 고점 중기하락(20<60)", "ret_5d": 6.5, "ret_10d": 9.0},
            {"trade_date": "2026-10-02", "shcode": "000020", "signal_type": "A-3 120·240일선 이탈", "ret_5d": -2.0, "ret_10d": 1.0},
            {"trade_date": "2026-10-03", "shcode": "000030", "signal_type": "B-3 저점 중기상승(20>=60)", "ret_5d": 4.0, "ret_10d": 8.0},
            {"trade_date": "2026-10-04", "shcode": "000040", "signal_type": "C-1 고점 이평선밀집", "ret_5d": 1.5, "ret_10d": 2.5},
            # 레거시 v2.9 행 2건은 정상 집계 유지
            {"trade_date": "2026-09-15", "shcode": "000050", "signal_type": "정배열", "ret_5d": 5.0, "ret_10d": 11.0},
            {"trade_date": "2026-09-16", "shcode": "000060", "signal_type": "눌림지지", "ret_5d": 3.0, "ret_10d": 4.0},
        ]
        stats = s.build_historical_track_stats(
            chart_map={},
            supply_map={},
            ref_date="2026-11-20",
            prior_dsa_rows=prior_rows,
        )
        self.assertEqual(stats["정배열"]["hist_sample_cnt"], 1)
        self.assertEqual(stats["바닥첫수급"]["hist_sample_cnt"], 0)
        # v3.0 행 4건은 단기혼합에 섞이지 않고 레거시 '눌림지지' 1건만 집계됨
        self.assertEqual(stats["단기혼합"]["hist_sample_cnt"], 1)


class TestIssue027HttpErrorPgrst204Fallback(unittest.TestCase):
    """ISSUE-027: 실제 urllib.error.HTTPError(400) 본문 기반 PGRST204 폴백 및 비-PGRST204 400 즉시 전파"""

    def test_real_urllib_httperror_400_pgrst204_triggers_base_columns_fallback(self):
        sample_row = {col: None for col in s.DSA_UPSERT_COLUMNS}
        sample_row.update({"trade_date": "2026-11-20", "shcode": "005930", "hname": "삼성전자", "trend_camp": "BULL"})

        post_payloads: list[list[dict]] = []

        def fake_post_pgrst204_once(url, payload, headers=None, timeout=35.0):
            post_payloads.append(payload)
            if len(post_payloads) == 1:
                hdrs = http.client.HTTPMessage()
                body = b'{"code":"PGRST204","details":null,"hint":null,"message":"Could not find the \'trend_camp\' column of \'daily_supply_analysis\' in the schema cache"}'
                raise urllib.error.HTTPError(url, 400, "Bad Request", hdrs, io.BytesIO(body))
            return []

        with mock.patch.object(s, "http_post_json", side_effect=fake_post_pgrst204_once):
            s._upsert_dsa_rows_safe("https://mock.supabase.co", "mock_key", [sample_row])

        # 1차(v3.0 전체 컬럼) 실패 즉시 재시도 없이 2차(기본 컬럼 폴백) 1회 호출 = 총 2회
        self.assertEqual(len(post_payloads), 2)
        self.assertIn("trend_camp", post_payloads[0][0])
        self.assertNotIn("trend_camp", post_payloads[1][0])
        self.assertEqual(set(post_payloads[1][0].keys()), set(s.DSA_BASE_UPSERT_COLUMNS))

    def test_local_http_server_400_pgrst204_and_non_pgrst204_400_raises(self):
        received: list[tuple[int, dict]] = []
        mode = {"kind": "pgrst204"}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                ln = int(self.headers.get("Content-Length", "0"))
                rows = json.loads(self.rfile.read(ln).decode("utf-8"))
                received.append((len(received), rows[0]))
                if mode["kind"] == "pgrst204" and "trend_camp" in rows[0]:
                    payload = b'{"code":"PGRST204","message":"Could not find the \'trend_camp\' column"}'
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                elif mode["kind"] == "other400":
                    payload = b'{"code":"23502","message":"null value in column hname violates not-null constraint"}'
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                else:
                    payload = b"[]"
                    self.send_response(201)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)

            def log_message(self, fmt, *args):  # noqa: ANN001
                return

        srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        port = srv.server_port
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            base_url = f"http://127.0.0.1:{port}"
            row = {col: None for col in s.DSA_UPSERT_COLUMNS}
            row.update({"trade_date": "2026-11-20", "shcode": "005930", "hname": "삼성전자", "trend_camp": "BULL"})

            with mock.patch.dict("os.environ", {"NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1"}, clear=False):
                s._upsert_dsa_rows_safe(base_url, "local_key", [row])
                self.assertEqual(len(received), 2)
                self.assertIn("trend_camp", received[0][1])
                self.assertNotIn("trend_camp", received[1][1])

                # 일반 400(23502 NOT NULL 위반 등)은 폴백하지 않고 HTTPError 즉시 전파
                received.clear()
                mode["kind"] = "other400"
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    s._upsert_dsa_rows_safe(base_url, "local_key", [row])
                self.assertEqual(ctx.exception.code, 400)
                self.assertEqual(len(received), 1)
        finally:
            srv.shutdown()
            srv.server_close()


class TestIssue028MarketCap01PctFloatBoundary(unittest.TestCase):
    """ISSUE-028: 시총 0.1% 정확 경계(700억/0.7억, 2900억/2.9억) 부동소수 오차 보정 3중 일치 검증"""

    def test_exact_01_pct_boundary_passes_across_python_common_and_index(self):
        cases = [
            # (market_cap_eok, real_inst_amt_eok, trading_value_eok, expected_qualified)
            (700.0, 0.7, 6.0, True),     # 700 * 0.001 == 0.7000000000000001 -> 통과해야 함!
            (700.0, 0.6999, 6.0, False),  # 0.1% 미달 -> 탈락해야 함!
            (1400.0, 1.4, 6.0, True),    # 1400 * 0.001 == 1.4000000000000001 -> 통과
            (2900.0, 2.9, 6.0, True),    # 2900 * 0.001 == 2.9000000000000004 -> 통과
            (2900.0, 2.8999, 6.0, False),
        ]
        js_code = """
const fs = require("fs");
const vm = require("vm");
const C = require(require("path").resolve("common.js"));
const html = fs.readFileSync("index.html", "utf8");
const i0 = html.indexOf("const INLINE_TREND_CYCLE = (function () {");
const i1 = html.indexOf("function escapeHtml(str)", i0);
const inlineSrc = html.slice(i0, i1);
const box = { C: null, Number, Math, String, Object, Array };
vm.createContext(box);
const cases = """ + json.dumps(cases) + """;
const inlineOut = vm.runInContext(
  inlineSrc + "; (" + JSON.stringify(cases) + ").map(([mcap, amt, tv]) => INLINE_TREND_CYCLE.qualifySupplyItem({ marketCapEok: mcap, realInstAmtEok: amt, tradingValueEok: tv }).qualified);",
  box
);
const out = cases.map(([mcap, amt, tv], idx) => ({
  c: C.TrendCycle.qualifySupplyItem({ marketCapEok: mcap, realInstAmtEok: amt, tradingValueEok: tv }).qualified,
  i: inlineOut[idx]
}));
console.log(JSON.stringify(out));
"""
        js_res = _run_node_json(js_code)
        for idx, (mcap, amt, tv, expected) in enumerate(cases):
            py_ok, _ = s.qualify_supply_candidate_v30(trading_value_eok=tv, real_inst_amt_eok=amt, market_cap_eok=mcap)
            self.assertEqual(py_ok, expected, f"Python mismatch on case {cases[idx]}")
            self.assertEqual(js_res[idx]["c"], expected, f"common.js mismatch on case {cases[idx]}")
            self.assertEqual(js_res[idx]["i"], expected, f"index.html mismatch on case {cases[idx]}")


if __name__ == "__main__":
    unittest.main()
