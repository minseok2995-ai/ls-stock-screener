import datetime as dt
import json
import pathlib
import random
import subprocess
import unittest
from unittest import mock

import run_daily_screener as s

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _run_node_json(js_code: str, stdin_payload: object = None):
    proc = subprocess.run(
        ["node", "-e", js_code],
        input=(json.dumps(stdin_payload) if stdin_payload is not None else None),
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    return json.loads(lines[-1])


def _bar(
    trade_date: str,
    close: float,
    e5: float,
    e20: float,
    e60: float,
    e120: float,
    e240: float = 0.0,
) -> dict:
    return {
        "trade_date": trade_date,
        "open": int(round(close * 0.99)),
        "high": int(round(close * 1.01)),
        "low": int(round(close * 0.98)),
        "close": int(round(close)),
        "volume": 100000,
        "trading_value_m": 1200.0,
        "ema_5": float(e5),
        "ema_20": float(e20),
        "ema_60": float(e60),
        "ema_120": float(e120),
        "ema_240": float(e240),
    }


def _build_all_63_states_series() -> list[dict]:
    """
    240봉 워밍업 이후 고점 사이클(A-1~A-7, C-1)과 저점 사이클(B-1~B-7, C-2)의
    63개 세부 추세 현황(01~63) 전부를 결정론적으로 순회하는 시계열 픽스처.
    """
    base = dt.date(2024, 1, 2)
    bars: list[dict] = []
    day_seq = 0

    def add(c: float, e5: float, e20: float, e60: float, e120: float, e240: float) -> None:
        nonlocal day_seq
        d = (base + dt.timedelta(days=day_seq)).isoformat()
        day_seq += 1
        bars.append(_bar(d, c, e5, e20, e60, e120, e240))

    # 0..239 (240봉 워밍업 -> i==239 시점부터 has_240=True, A-1 #01 시작)
    for _ in range(240):
        add(15500, 15000, 14000, 13000, 12000, 11000)

    # --- A-1 (01~09): 완전정배열 15000 > 14000 > 13000 > 12000 > 11000 ---
    add(15600, 15000, 14000, 13000, 12000, 11000)  # 01: 5일선위 상승지속 (prev_c >= e5)
    add(14500, 15000, 14000, 13000, 12000, 11000)  # 03: 5일선이탈(1일차) (e20 <= c < e5, day 1)
    add(15200, 15000, 14000, 13000, 12000, 11000)  # 02: 5일선 반등회복 (prev_c < e5 -> c >= e5)
    add(14400, 15000, 14000, 13000, 12000, 11000)  # 03: day 1
    add(14300, 15000, 14000, 13000, 12000, 11000)  # 04: 20일선 지지(2일+) (day 2)
    add(13500, 15000, 14000, 13000, 12000, 11000)  # 06: 20일선이탈 (e60 <= c < e20, day 1)
    add(13400, 15000, 14000, 13000, 12000, 11000)  # 07: 60일선 지지(2일+) (day 2)
    add(14200, 15000, 14000, 13000, 12000, 11000)  # 05: 20일선 반등회복 (prev_c < e20 -> e20 <= c < e5)
    add(12500, 15000, 14000, 13000, 12000, 11000)  # 08: 60일선이탈(120일지지)
    add(10500, 15000, 14000, 13000, 12000, 11000)  # 09: 120·240일선 직행이탈

    # --- A-2 (10~15): 고점 단기하락 (e5 < e20, e20 >= e60 >= e120, had_long_drop=False) ---
    add(14500, 13800, 14000, 13000, 12000, 11000)  # 10: 20일선 반등돌파 (c >= e20, sets prev_c_ge_60=True)
    add(13700, 13800, 14000, 13000, 12000, 11000)  # 11: 20일선이탈 유지 (day 1 in [e60, e20))
    add(13200, 13800, 14000, 13000, 12000, 11000)  # 12: 60일선 지지(2일+) (day 2 & lower half <= 13500)
    add(12500, 13800, 14000, 13000, 12000, 11000)  # 14: 60일선이탈(120일지지) (sets prev_c_ge_60=False)
    add(13300, 13800, 14000, 13000, 12000, 11000)  # 13: 60일선 반등 (prev_c < e60 -> c >= e60)
    add(11500, 13800, 14000, 13000, 12000, 11000)  # 15: 120일선이탈

    # --- A-3 (16~20): 고점 중기하락 (e5 < e20 < e60, e60 >= e120) ---
    add(13000, 12200, 12600, 13200, 12000, 11000)  # 16: 20일선 반등돌파
    add(12400, 12200, 12600, 13200, 12000, 11000)  # 17: 5일선 반등
    add(12100, 12200, 12600, 13200, 12000, 11000)  # 18: 120일선 지지
    add(11500, 12200, 12600, 13200, 12000, 11000)  # 19: 120일이탈(240일지지)
    add(10500, 12200, 12600, 13200, 12000, 11000)  # 20: 120·240일선 이탈

    # --- A-4 (21~23): 고점 중기하락내 단기반등 (e5 >= e20, e20 < e60, e60 >= e120) ---
    add(13500, 12800, 12600, 13200, 12000, 11000)  # 21: 60일선 돌파(복귀임박)
    add(12900, 12800, 12600, 13200, 12000, 11000)  # 22: 20일선위 안착
    add(12300, 12800, 12600, 13200, 12000, 11000)  # 23: 20일선 재이탈

    # --- C-1 (58~60): 고점 이평선밀집 (spread_3 <= 3%, gap_20_60 <= 1%, camp == BULL) ---
    add(13300, 13100, 13050, 13000, 12000, 11000)  # 58: 밀집상단 돌파시도
    add(13050, 13100, 13050, 13000, 12000, 11000)  # 59: 밀집내부 수렴
    add(12800, 13100, 13050, 13000, 12000, 11000)  # 60: 밀집하단 이탈

    # --- A-5 (24~27): 고점 장기하락 (e5 < e20 < e60 < e120, e120 >= e240 -> not full_bear, had_long_drop=True) ---
    add(11600, 11000, 11400, 11800, 12200, 11200)  # 24: 20일선 반등돌파
    add(11200, 11000, 11400, 11800, 12200, 11200)  # 25: 5일선 반등
    add(10950, 11000, 11400, 11800, 12200, 10800)  # 26: 240일선 지지 (c < e5 & c >= e240, e120 >= e240)
    add(10500, 11000, 11400, 11800, 12200, 10800)  # 27: 240일선 이탈 (c < e240)

    # --- A-6 (28~31): 고점 장기하락내 단중기반등 (e60 < e120, e5 >= e20 or e20 >= e60) ---
    add(11500, 11500, 11300, 11800, 12200, 11200)  # 28: 단기반등(5>=20)·60일아래
    add(12000, 11500, 11300, 11800, 12200, 11200)  # 29: 단기반등(5>=20)·60일돌파
    add(12000, 12000, 11900, 11700, 12200, 11200)  # 30: 중기반등(20>=60)·120일아래
    add(12500, 12000, 11900, 11700, 12200, 11200)  # 31: 중기반등(20>=60)·120일돌파

    # --- A-7 (32~33): 고점조정후 장기재상승 (had_long_drop=True & e60 >= e120, e120 <= e240 so not full_bull) ---
    add(12800, 12600, 12300, 12000, 11800, 12000)  # 32: 5일선위 순항
    add(12400, 12600, 12300, 12000, 11800, 12000)  # 33: 눌림지지

    # --- B-1 (34~38): 완전역배열 진입 (240 > 120 > 60 > 20 > 5 -> camp = BEAR, had_long_rise = False) ---
    add(8500, 9000, 9600, 10400, 11200, 12000)      # 34: 5일선아래 침체지속
    add(9200, 9000, 9600, 10400, 11200, 12000)      # 35: 5일선 첫돌파 (hold_5_below_20 == 1)
    add(9300, 9000, 9600, 10400, 11200, 12000)      # 36: 5일선 지지(2일+) (hold_5_below_20 == 2)
    add(9900, 9000, 9600, 10400, 11200, 12000)      # 37: 20일선 돌파
    add(10800, 9000, 9600, 10400, 11200, 12000)     # 38: 60일선이상 직행돌파

    # --- B-2 (39~42): 저점 단기상승 (e5 >= e20, e20 < e60 < e120, had_long_rise=False) ---
    add(10600, 9800, 9600, 10400, 11200, 12000)     # 39: 60일선 돌파
    add(10000, 9800, 9600, 10400, 11200, 12000)     # 40: 5일선위 순항
    add(9700, 9800, 9600, 10400, 11200, 12000)      # 41: 20일선 눌림지지
    add(9400, 9800, 9600, 10400, 11200, 12000)      # 42: 20일선 재이탈

    # --- B-3 (43~47): 저점 중기상승 (e5 >= e20 >= e60, e60 < e120) ---
    add(12500, 10800, 10500, 10200, 11200, 12000)   # 43: 120·240일선 돌파
    add(11500, 10800, 10500, 10200, 11200, 12000)   # 44: 120일선 돌파(240일아래)
    add(10900, 10800, 10500, 10200, 11200, 12000)   # 45: 60일선위 순항(120일아래)
    add(10400, 10800, 10500, 10200, 11200, 12000)   # 46: 20·60일선 눌림지지
    add(10000, 10800, 10500, 10200, 11200, 12000)   # 47: 60일선 이탈

    # --- B-4 (48~49): 저점 중기상승내 단기조정 (e5 < e20, e20 >= e60, e60 < e120) ---
    add(10300, 10400, 10600, 10200, 11200, 12000)   # 48: 60일선 지지눌림
    add(10000, 10400, 10600, 10200, 11200, 12000)   # 49: 60일선 이탈

    # --- C-2 (61~63): 저점 이평선밀집 (spread_3 <= 3%, gap_20_60 <= 1%, camp == BEAR) ---
    add(10500, 10250, 10200, 10150, 11200, 12000)   # 61: 밀집상단 돌파시도
    add(10200, 10250, 10200, 10150, 11200, 12000)   # 62: 밀집내부 수렴
    add(9900, 10250, 10200, 10150, 11200, 12000)    # 63: 밀집하단 이탈

    # --- B-5 (50~52): 저점 장기상승 (e5 >= e20 >= e60 >= e120, e120 <= e240 -> had_long_rise=True) ---
    add(12300, 11800, 11500, 11300, 11100, 12000)   # 50: 240일선 돌파(고점승격임박)
    add(11900, 11800, 11500, 11300, 11100, 12000)   # 51: 240일선 아래 순항
    add(11600, 11800, 11500, 11300, 11100, 12000)   # 52: 단기눌림지지

    # --- B-6 (53~54): 저점 장기상승내 단중기조정 (e60 >= e120, e5 < e20 or e20 < e60) ---
    add(11400, 11400, 11600, 11300, 11100, 12000)   # 53: 단기조정(20>=60유지)
    add(11100, 11100, 11200, 11400, 11100, 12000)   # 54: 중기조정(20<60)

    # --- B-7 (55~57): 저점 반등실패 재하락 (had_long_rise=True & e60 < e120 & e20 < e60, e120 >= e240로 full_bear 방지) ---
    add(10200, 10500, 10800, 11100, 11400, 11200)   # 55: 재하락 진행(5일선아래)
    add(10600, 10500, 10800, 11100, 11400, 11200)   # 56: 재하락중 5일선반등
    add(10950, 10900, 10800, 11100, 11400, 11200)   # 57: 재하락후 단기재반등(5>=20)

    return bars


class TestAC61TrendCycleEngineParity(unittest.TestCase):
    """AC-61: 양극 추세 사이클 16단계 · 63세부현황 결정론 및 Python·JS 100% 일치 검증"""

    def test_ac61_all_16_stages_and_63_details_covered_and_py_js_exact_match(self):
        self.assertEqual(len(s.TREND_STAGE_META), 16)
        self.assertEqual(len(s.TREND_DETAIL_META), 63)
        expected_detail_codes = {f"{i:02d}" for i in range(1, 64)}
        self.assertEqual(set(s.TREND_DETAIL_META.keys()), expected_detail_codes)

        bars = _build_all_63_states_series()
        py_res = s.classify_trend_cycle_series(bars)
        self.assertEqual(len(py_res), len(bars))

        seen_details = {r["trend_detail_code"] for r in py_res}
        seen_stages = {r["trend_stage_code"] for r in py_res}
        self.assertEqual(seen_details, expected_detail_codes, f"누락된 세부현황 코드: {expected_detail_codes - seen_details}")
        self.assertEqual(seen_stages, set(s.TREND_STAGE_META.keys()))

        # common.js C.TrendCycle.classifySeries 및 index.html 내장 폴백과 단 1봉 오차 없이 100% 일치하는지 검증
        js_code = r"""
const fs = require("fs");
const vm = require("vm");
const C = require("./common.js");
const bars = JSON.parse(fs.readFileSync(0, "utf8"));
const commonRes = C.TrendCycle.classifySeries(bars);

const html = fs.readFileSync("index.html", "utf8");
const script = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map(m => m[1]).filter(x => x.trim()).pop();
const makeEl = () => ({ value: "", textContent: "", innerHTML: "", style: {}, classList: { add(){}, remove(){} }, addEventListener(){}, querySelectorAll: () => [], getContext: () => null });
const sb = { console, Math, Date, Number, String, Boolean, Array, Object, Promise, Set, Map, RegExp, JSON, Error, encodeURIComponent, setTimeout, clearTimeout, window: { addEventListener(){} }, document: { getElementById: makeEl, querySelectorAll: () => [], createElement: makeEl }, fetch: async () => ({ ok: true, json: async () => [] }) };
sb.globalThis = sb;
vm.createContext(sb);
vm.runInContext(script, sb);
sb.__bars = bars;
const inlineRes = vm.runInContext("INLINE_TREND_CYCLE.classifySeries(__bars)", sb);

console.log(JSON.stringify({
  stageCnt: Object.keys(C.TrendCycle.STAGE_META).length,
  detailCnt: Object.keys(C.TrendCycle.DETAIL_META).length,
  commonRes,
  inlineRes
}));
"""
        out = _run_node_json(js_code, stdin_payload=bars)
        self.assertEqual(out["stageCnt"], 16)
        self.assertEqual(out["detailCnt"], 63)
        self.assertEqual(out["commonRes"], py_res)
        self.assertEqual(out["inlineRes"], py_res)

    def test_ac61_ipo_under_240_bars_and_random_walk_zero_unclassified(self):
        # 1) 신규 상장 240봉 미만 구간: ema_240 역전 상태여도 4개 이평선(5>20>60>120) 정배열이면 A-1 판정
        ipo_bars = [_bar(f"2026-06-{(i % 28) + 1:02d}", 21000, 20500, 19800, 19000, 18200, 25000) for i in range(50)]
        ipo_py = s.classify_trend_cycle_series(ipo_bars)
        self.assertTrue(all(r["trend_camp"] == "BULL" and r["trend_stage_code"] == "A-1" for r in ipo_py))

        # 2) 경동나비엔류 고점 사이클 장기 파동 + 급등락 600봉 랜덤 시계열 무결성 & JS 100% 일치
        rng = random.Random(20261122)
        raw_bars = []
        price = 50000.0
        base_dt = dt.date(2023, 1, 2)
        for i in range(600):
            drift = 0.004 if (i // 120) % 2 == 0 else -0.0045
            price = max(3000.0, price * (1.0 + drift + rng.uniform(-0.035, 0.035)))
            c = int(round(price))
            raw_bars.append({
                "shcode": "009450",
                "trade_date": (base_dt + dt.timedelta(days=i)).isoformat(),
                "open": int(round(c * rng.uniform(0.98, 1.02))),
                "high": int(round(c * 1.03)),
                "low": int(round(c * 0.97)),
                "close": c,
                "volume": 80000,
            })
        enriched = s.compute_ema_series(raw_bars)
        py_walk = s.classify_trend_cycle_series(enriched)
        js_walk = _run_node_json(
            'const fs=require("fs"),C=require("./common.js");'
            'console.log(JSON.stringify(C.TrendCycle.classifySeries(JSON.parse(fs.readFileSync(0,"utf8")))));',
            stdin_payload=enriched,
        )
        self.assertEqual(py_walk, js_walk)
        for r in py_walk:
            self.assertIn(r["trend_camp"], ("BULL", "BEAR"))
            self.assertIn(r["trend_stage_code"], s.TREND_STAGE_META)
            self.assertIn(r["trend_detail_code"], s.TREND_DETAIL_META)
            self.assertTrue(r["trend_full_label"].startswith(r["trend_stage_code"]))


class TestAC62QualificationRules(unittest.TestCase):
    """AC-62: 신규 자격 기준(일거래대금 >= 5억 & 기관순매수 >= 3억 또는 시총 0.1%) 정확성 검증"""

    def test_ac62_qualification_cases_py_and_js(self):
        # 1) 시총 1,000억 + 순매수 1.2억(0.12% >= 0.1%) + 일거래대금 6억 -> 통과
        ok1, rsn1 = s.qualify_supply_candidate_v30(trading_value_eok=6.0, real_inst_amt_eok=1.2, market_cap_eok=1000.0)
        self.assertTrue(ok1)
        self.assertEqual(rsn1, "")

        # 2) 일거래대금 4.5억 (< 5.0억) -> 탈락
        ok2, rsn2 = s.qualify_supply_candidate_v30(trading_value_eok=4.5, real_inst_amt_eok=5.0, market_cap_eok=1000.0)
        self.assertFalse(ok2)
        self.assertIn("일거래대금5억미만", rsn2)

        # 3) 시총 1,000억 + 순매수 0.5억 (< 3억 & < 시총 0.1%=1.0억) -> 탈락
        ok3, rsn3 = s.qualify_supply_candidate_v30(trading_value_eok=6.0, real_inst_amt_eok=0.5, market_cap_eok=1000.0)
        self.assertFalse(ok3)
        self.assertIn("기관순매수미달(3억·시총0.1%)", rsn3)

        # 4) 대형주(시총 50,000억) + 순매수 3.1억(>= 3.0억) + 일거래대금 10억 -> 통과
        ok4, _ = s.qualify_supply_candidate_v30(trading_value_eok=10.0, real_inst_amt_eok=3.1, market_cap_eok=50000.0)
        self.assertTrue(ok4)

        js_res = _run_node_json(
            """
const C = require("./common.js");
console.log(JSON.stringify([
  C.TrendCycle.qualifySupplyItem({ tradingValueEok: 6.0, realInstAmtEok: 1.2, marketCapEok: 1000.0 }).qualified,
  C.TrendCycle.qualifySupplyItem({ tradingValueEok: 4.5, realInstAmtEok: 5.0, marketCapEok: 1000.0 }).qualified,
  C.TrendCycle.qualifySupplyItem({ tradingValueEok: 6.0, realInstAmtEok: 0.5, marketCapEok: 1000.0 }).qualified,
  C.TrendCycle.qualifySupplyItem({ tradingValueEok: 10.0, realInstAmtEok: 3.1, marketCapEok: 50000.0 }).qualified
]));
"""
        )
        self.assertEqual(js_res, [True, False, False, True])


class TestAC63BatchSlotsSnapshotAndModel(unittest.TestCase):
    """AC-63: prelim/final 슬롯 동작 · stocks_master 추세 스냅샷 · gemini-3.5-flash-lite 기본값 검증"""

    def test_ac63_prelim_vs_final_and_master_snapshot_and_default_model(self):
        self.assertEqual(s.DEFAULT_GEMINI_MODEL, "gemini-3.5-flash-lite")

        with mock.patch.dict("os.environ", {"ANALYSIS_FORCE_RUN": "0"}):
            self.assertTrue(s.should_run_step1_v30_analysis("daily", "prelim"))
            self.assertTrue(s.should_run_step1_v30_analysis("daily", "final"))
            self.assertFalse(s.should_run_step1_v30_analysis("backfill", "final"))
            self.assertFalse(s.should_run_v29_analysis("daily", "prelim"))
            self.assertTrue(s.should_run_v29_analysis("daily", "final"))

        # 3종목: 000010(당일 15%), 000020(3일 연속 6% -> consec_5p_days>=3 포착), 000030(비수급 일반 유니버스 종목 -> 마스터 스냅샷만 갱신)
        base_dt = dt.date(2026, 9, 1)
        dates = [(base_dt + dt.timedelta(days=i)).isoformat() for i in range(40)]
        ref_date = dates[-1]

        def mk_data(code: str, ratios: list[float], amt_m: float, bull: bool):
            c_rows = []
            s_rows = []
            for idx, d in enumerate(dates):
                c = 20000 + (idx * 50 if bull else -idx * 50)
                c_rows.append({
                    "shcode": code,
                    "trade_date": d,
                    "open": c - 100,
                    "high": c + 200,
                    "low": c - 200,
                    "close": c,
                    "change_rate": 1.2,
                    "volume": 100000,
                    "trading_value_m": 2000.0,
                    "ema_5": c - 50 if bull else c + 50,
                    "ema_20": c - 200 if bull else c + 200,
                    "ema_60": c - 500 if bull else c + 500,
                    "ema_120": c - 900 if bull else c + 900,
                    "ema_240": c - 1300 if bull else c + 1300,
                })
                rt = ratios[idx - len(dates)] if idx >= len(dates) - len(ratios) else 1.0
                s_rows.append({
                    "shcode": code,
                    "trade_date": d,
                    "real_inst_vol": int(1000 * rt),
                    "real_inst_amt": amt_m,
                    "inst_vol_ratio": rt,
                    "frg_vol": 100,
                    "frg_amt": 50.0,
                    "frg_vol_ratio": 1.0,
                    "ind_vol": -1000,
                    "itc_amt": amt_m,
                    "itc_vol": int(1000 * rt),
                })
            return c_rows, s_rows

        c1, s1 = mk_data("000010", [2.0, 3.0, 15.0], 450.0, bull=True)
        c2, s2 = mk_data("000020", [6.0, 7.0, 6.5], 150.0, bull=False)  # 시총 1,000억 * 0.1% = 1.0억 <= 1.5억 통과!
        c3, s3 = mk_data("000030", [1.0, 1.0, 1.0], 10.0, bull=True)
        all_c = {"000010": c1, "000020": c2, "000030": c3}
        all_s = {"000010": s1, "000020": s2, "000030": s3}
        masters = [
            {"shcode": "000010", "hname": "고점수급주", "market": "KOSPI", "market_cap_eok": 5000.0, "avg_val_20d_eok": 30.0, "is_universe": True},
            {"shcode": "000020", "hname": "삼일연속소형주", "market": "KOSDAQ", "market_cap_eok": 1000.0, "avg_val_20d_eok": 12.0, "is_universe": True},
            {"shcode": "000030", "hname": "비수급유니버스주", "market": "KOSPI", "market_cap_eok": 2000.0, "avg_val_20d_eok": 20.0, "is_universe": True},
        ]

        def fake_get(url, headers=None, timeout=25.0):
            if "/excluded_stocks?" in url:
                return []
            if "shcode=eq.005930" in url:
                return [{"trade_date": d} for d in reversed(dates[-5:])]
            if "/daily_supply_analysis?" in url:
                return []
            if "trade_date=in.(" in url:
                dt_set = set(url.split("trade_date=in.(")[1].split(")")[0].split(","))
                codes = url.split("shcode=in.(")[1].split(")")[0].split(",")
                src = all_c if "/daily_chart?" in url else all_s
                return [r for c in codes for r in src.get(c, []) if r["trade_date"] in dt_set]
            if "/daily_chart?" in url and "shcode=in.(" in url:
                codes = url.split("shcode=in.(")[1].split(")")[0].split(",")
                return [r for c in codes for r in all_c.get(c, [])]
            if "/daily_investor_supply?" in url and "shcode=in.(" in url:
                codes = url.split("shcode=in.(")[1].split(")")[0].split(",")
                return [r for c in codes for r in all_s.get(c, [])]
            return []

        upserted: list[tuple[str, list[dict]]] = []
        called_gemini_urls: list[str] = []

        def fake_upsert(u, k, table, conflict, rows, *a, **kw):
            upserted.append((table, list(rows)))

        def fake_post(url, payload, headers=None, timeout=45.0):
            called_gemini_urls.append(url)
            return {
                "candidates": [{
                    "content": {"parts": [{"text": json.dumps({
                        "headline": "핵심 요약",
                        "supply_comment": "수급 양호",
                        "chart_comment": "추세 양호",
                        "risk_points": ["변동성 유의"],
                        "action_plan": "분할 접근",
                    }, ensure_ascii=False)}]}
                }]
            }

        # (1) prelim 슬롯: Step 1(daily_supply_analysis + stocks_master 추세 스냅샷) 수행, Gemini 미호출
        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "test_key", "ANALYSIS_FORCE_RUN": "0"}, clear=False), \
             mock.patch.object(s, "http_get_json", side_effect=fake_get), \
             mock.patch.object(s, "http_post_json", side_effect=fake_post), \
             mock.patch.object(s, "http_request_json", return_value=[]), \
             mock.patch.object(s, "supabase_upsert", side_effect=fake_upsert):
            os_env_backup = s.os.environ.pop("GEMINI_MODEL", None)
            try:
                res_prelim = s.run_daily_supply_analysis_pipeline(
                    sb_url="https://mock.supabase.co",
                    sb_key="mock_key",
                    ref_date=ref_date,
                    existing_masters=masters,
                    effective_slot="prelim",
                )
            finally:
                if os_env_backup is not None:
                    s.os.environ["GEMINI_MODEL"] = os_env_backup

        self.assertEqual(res_prelim["candidate_cnt"], 2)  # 000010(당일15%) + 000020(3일연속5%+)
        self.assertEqual(res_prelim["qualified_cnt"], 2)
        self.assertEqual(res_prelim["master_trend_updated"], 3)  # 비수급 포함 전 유니버스 3종목 스냅샷 갱신
        self.assertEqual(len(called_gemini_urls), 0)
        sm_rows = [rows for tbl, rows in upserted if tbl == "stocks_master"][0]
        self.assertEqual({r["shcode"] for r in sm_rows}, {"000010", "000020", "000030"})
        self.assertTrue(all(r["trend_updated_date"] == ref_date and r["trend_stage_code"] for r in sm_rows))

        # (2) final 슬롯 (GEMINI_MODEL 미지정): 기본 gemini-3.5-flash-lite 모델로 Step 2 호출 확인
        upserted.clear()
        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "test_key", "ANALYSIS_FORCE_RUN": "0"}, clear=False), \
             mock.patch.object(s, "http_get_json", side_effect=fake_get), \
             mock.patch.object(s, "http_post_json", side_effect=fake_post), \
             mock.patch.object(s, "http_request_json", return_value=[]), \
             mock.patch.object(s, "supabase_upsert", side_effect=fake_upsert):
            s.os.environ.pop("GEMINI_MODEL", None)
            res_final = s.run_daily_supply_analysis_pipeline(
                sb_url="https://mock.supabase.co",
                sb_key="mock_key",
                ref_date=ref_date,
                existing_masters=masters,
                effective_slot="final",
            )

        self.assertEqual(res_final["ai_stats"]["success_cnt"], 2)
        self.assertTrue(all("models/gemini-3.5-flash-lite:generateContent" in u for u in called_gemini_urls))


class TestAC64AndAC65IndexUIAndHover(unittest.TestCase):
    """AC-64 · AC-65: index.html 3단 추세 사이클 UI · 세부합산 리스트 · 차트 당일/호버 추세 배지 & AI 요약 검증"""

    def test_ac64_ac65_three_tier_ui_drilldown_hover_and_ai_card(self):
        js_test = r"""
const fs = require("fs");
const vm = require("vm");
const C = require("./common.js");
const html = fs.readFileSync("index.html", "utf8");
const script = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map(m => m[1]).filter(x => x.trim()).pop();

const mockCanvasCtx = () => new Proxy(function () {}, {
  get: (t, k) => k === "measureText" ? () => ({ width: 12 }) : (k === "canvas" ? {} : mockCanvasCtx()),
  apply: () => mockCanvasCtx(),
  set: () => true
});

const elements = {};
function makeNode(id) {
  const listeners = {};
  const children = {};
  const node = {
    id: id || "",
    textContent: "",
    _html: "",
    value: "",
    checked: false,
    clientWidth: 640,
    width: 640,
    height: 360,
    style: {},
    dataset: {},
    className: "",
    classList: {
      _set: new Set(["hidden"]),
      add(c) { this._set.add(c); },
      remove(c) { this._set.delete(c); },
      contains(c) { return this._set.has(c); },
      toggle(c) { if (this._set.has(c)) this._set.delete(c); else this._set.add(c); }
    },
    addEventListener(ev, fn) { listeners[ev] = fn; },
    trigger(ev, payload) { if (listeners[ev]) listeners[ev](payload || {}); },
    getBoundingClientRect() { return { left: 0, top: 0, width: 640, height: 360 }; },
    getContext() { return mockCanvasCtx(); },
    querySelector(sel) {
      if (!children[sel]) children[sel] = makeNode(sel);
      return children[sel];
    },
    querySelectorAll() { return []; },
    set innerHTML(v) { this._html = String(v); },
    get innerHTML() { return this._html; }
  };
  return node;
}
function getEl(id) {
  if (!elements[id]) elements[id] = makeNode(id);
  return elements[id];
}

const sandbox = {
  console, Math, Date, Number, String, Boolean, Array, Object, Promise, Set, Map, RegExp, JSON, Error,
  encodeURIComponent, setTimeout, clearTimeout, parseInt, parseFloat, isNaN, isFinite,
  window: { LSCommon: C, innerHeight: 940, addEventListener() {} },
  document: {
    getElementById: getEl,
    querySelectorAll: () => [],
    createElement: tag => makeNode(tag)
  },
  fetch: async () => ({ ok: true, status: 200, json: async () => [], text: async () => "[]" })
};
sandbox.globalThis = sandbox;
C._setFetch(sandbox.fetch);
vm.createContext(sandbox);
vm.runInContext(script, sandbox);

const out = vm.runInContext(`
(() => {
  IS_LIVE_SUPABASE = true;
  TOP_TRADE_DATE = "2026-11-20";
  MASTERS_LIST = [
    { shcode: "000001", hname: "장기고점주A", market: "KOSPI", market_cap_eok: 5000, avg_val_20d_eok: 40 },
    { shcode: "000002", hname: "장기고점눌림B", market: "KOSPI", market_cap_eok: 3000, avg_val_20d_eok: 25 },
    { shcode: "000003", hname: "고점중기하락C", market: "KOSDAQ", market_cap_eok: 1200, avg_val_20d_eok: 10 },
    { shcode: "000004", hname: "장기저점반등D", market: "KOSDAQ", market_cap_eok: 1000, avg_val_20d_eok: 8 },
    { shcode: "000005", hname: "자격미달탈락주", market: "KOSDAQ", market_cap_eok: 2000, avg_val_20d_eok: 5 }
  ];
  MASTERS_LIST.forEach(m => { MASTER_BY_CODE[m.shcode] = m; FULL_CHART_LOADED[m.shcode] = true; });

  // 000001: Day 1에서는 A-3(고점 중기하락), Day 2(기준일)에서는 A-1 #01(5일선위 상승지속)로 전환 -> 차트 호버 시 시점별 변화 검증!
  RAW_CHARTS_BY_CODE["000001"] = [
    { shcode: "000001", trade_date: "2026-11-19", open: 12900, high: 13200, low: 12800, close: 13100, change_rate: 1.5, volume: 100000, trading_value_m: 1310, ema_5: 12200, ema_20: 12600, ema_60: 13200, ema_120: 12000, ema_240: 11000 },
    { shcode: "000001", trade_date: "2026-11-20", open: 15200, high: 15800, low: 15100, close: 15600, change_rate: 4.2, volume: 150000, trading_value_m: 2340, ema_5: 15000, ema_20: 14000, ema_60: 13000, ema_120: 12000, ema_240: 11000 }
  ];
  RAW_SUPPLIES_BY_CODE["000001"] = [
    { shcode: "000001", trade_date: "2026-11-20", real_inst_vol: 30000, real_inst_amt: 500, inst_vol_ratio: 20.0, frg_vol_ratio: 2.0, itc_amt: 300, itc_vol: 18000 }
  ];
  DSA_BY_CODE["000001"] = {
    shcode: "000001",
    trade_date: "2026-11-20",
    ai_status: "SUCCESS",
    ai_model: "gemini-3.5-flash-lite",
    entry_price_ref: 15300,
    stop_loss_price: 15100,
    target_price_1: 16371,
    ai_summary: {
      headline: "투신 주도 완전정배열 돌파",
      supply_comment: "투신 순매수 집중 유입.",
      chart_comment: "장기고점 5일선 위 강세 지속.",
      risk_points: ["단기 이격 확대"],
      action_plan: "5일선 부근 분할 매수."
    }
  };

  // 000002: A-1 이지만 다른 세부현황(#04: 20일선 지지 2일+) -> A-1 선택 시 000001 + 000002 합산 표시 검증!
  RAW_CHARTS_BY_CODE["000002"] = [
    { shcode: "000002", trade_date: "2026-11-18", open: 15100, high: 15300, low: 15000, close: 15200, change_rate: 0.5, volume: 80000, trading_value_m: 1200, ema_5: 15000, ema_20: 14000, ema_60: 13000, ema_120: 12000, ema_240: 11000 },
    { shcode: "000002", trade_date: "2026-11-19", open: 14500, high: 14600, low: 14200, close: 14400, change_rate: -1.0, volume: 80000, trading_value_m: 1150, ema_5: 15000, ema_20: 14000, ema_60: 13000, ema_120: 12000, ema_240: 11000 },
    { shcode: "000002", trade_date: "2026-11-20", open: 14300, high: 14500, low: 14100, close: 14350, change_rate: -0.3, volume: 90000, trading_value_m: 1290, ema_5: 15000, ema_20: 14000, ema_60: 13000, ema_120: 12000, ema_240: 11000 }
  ];
  RAW_SUPPLIES_BY_CODE["000002"] = [
    { shcode: "000002", trade_date: "2026-11-20", real_inst_vol: 15000, real_inst_amt: 350, inst_vol_ratio: 16.7, frg_vol_ratio: 0.5 }
  ];

  // 000003: A-3 (고점 중기하락), 시총 1,200억 + 순매수 1.5억(>= 시총 0.1%=1.2억) + 거래대금 8억 -> 통과
  RAW_CHARTS_BY_CODE["000003"] = [
    { shcode: "000003", trade_date: "2026-11-20", open: 12500, high: 12600, low: 12000, close: 12100, change_rate: -2.1, volume: 70000, trading_value_m: 800, ema_5: 12200, ema_20: 12600, ema_60: 13200, ema_120: 12000, ema_240: 11000 }
  ];
  RAW_SUPPLIES_BY_CODE["000003"] = [
    { shcode: "000003", trade_date: "2026-11-20", real_inst_vol: 10000, real_inst_amt: 150, inst_vol_ratio: 14.3, frg_vol_ratio: -1.0 }
  ];

  // 000004: B-1 (장기저점 완전역배열), 시총 1,000억 + 순매수 1.2억 + 거래대금 6억 -> BEAR 진영 통과
  RAW_CHARTS_BY_CODE["000004"] = [
    { shcode: "000004", trade_date: "2026-11-20", open: 9050, high: 9400, low: 9000, close: 9300, change_rate: 3.1, volume: 65000, trading_value_m: 600, ema_5: 9000, ema_20: 9600, ema_60: 10400, ema_120: 11200, ema_240: 12000 }
  ];
  RAW_SUPPLIES_BY_CODE["000004"] = [
    { shcode: "000004", trade_date: "2026-11-20", real_inst_vol: 9000, real_inst_amt: 120, inst_vol_ratio: 13.8, frg_vol_ratio: 0.0 }
  ];

  // 000005: 거래대금 4.2억 (< 5억) -> 탈락!
  RAW_CHARTS_BY_CODE["000005"] = [
    { shcode: "000005", trade_date: "2026-11-20", open: 10000, high: 10500, low: 9900, close: 10400, change_rate: 4.0, volume: 40000, trading_value_m: 420, ema_5: 10200, ema_20: 10000, ema_60: 9800, ema_120: 9500, ema_240: 9000 }
  ];
  RAW_SUPPLIES_BY_CODE["000005"] = [
    { shcode: "000005", trade_date: "2026-11-20", real_inst_vol: 10000, real_inst_amt: 500, inst_vol_ratio: 25.0, frg_vol_ratio: 0.0 }
  ];

  applyScreening();
  const bullAllCodes = CURRENT_SCREENED_LIST.map(x => x.shcode);
  const bullStageHtml = document.getElementById("trendStageButtons").innerHTML;
  const bullCntTxt = document.getElementById("campBullCountBadge").textContent;
  const bearCntTxt = document.getElementById("campBearCountBadge").textContent;

  // A-1 단일 상위 추세 선택 -> 하위 세부현황(#01 + #04) 2종목 합산 표시 확인
  setTrendStage("A-1");
  const a1Codes = CURRENT_SCREENED_LIST.map(x => x.shcode);
  const a1TableHtml = document.getElementById("screenerTableBody").innerHTML;

  // 차트 상단 당일 추세 배지 & AI 카드 확인 (000001 선택 상태)
  const defaultMainBadge = document.getElementById("detailTrendMainBadge").textContent;
  const defaultProbBadge = document.getElementById("detailTrendProbBadge").textContent;
  const aiCardVisible = !document.getElementById("aiSummaryCard").classList.contains("hidden");
  const aiHeadline = document.getElementById("aiSummaryHeadline").textContent;

  // ProChart 과거 첫 번째 봉(2026-11-19, A-3 #16) 마우스 호버 시뮬레이션
  const proMount = document.getElementById("proChartMount");
  const proCv = proMount.querySelector('[data-role="cv"]');
  proCv.trigger("mousemove", { clientX: 20 });
  const hoverDateTag = document.getElementById("detailTrendDateTag").textContent;
  const hoverMainBadge = document.getElementById("detailTrendMainBadge").textContent;
  const hoverBrief = proMount.querySelector('[data-role="brief"]').textContent;

  // 마우스 이탈(mouseleave) 시 기준일(2026-11-20, A-1 #01) 추세 배지 복귀 확인
  proCv.trigger("mouseleave", {});
  const restoredDateTag = document.getElementById("detailTrendDateTag").textContent;
  const restoredMainBadge = document.getElementById("detailTrendMainBadge").textContent;

  // 하락 추세(BEAR) 탭 전환 확인
  setTrendCamp("BEAR");
  const bearAllCodes = CURRENT_SCREENED_LIST.map(x => x.shcode);
  const bearStageHtml = document.getElementById("trendStageButtons").innerHTML;

  return {
    bullCntTxt, bearCntTxt, bullAllCodes, bullStageHtml,
    a1Codes, a1TableHtml,
    defaultMainBadge, defaultProbBadge, aiCardVisible, aiHeadline,
    hoverDateTag, hoverMainBadge, hoverBrief,
    restoredDateTag, restoredMainBadge,
    bearAllCodes, bearStageHtml
  };
})()
`, sandbox);

console.log(JSON.stringify(out));
"""
        r = _run_node_json(js_test)
        self.assertEqual(r["bullCntTxt"], "3종목")
        self.assertEqual(r["bearCntTxt"], "1종목")
        self.assertEqual(r["bullAllCodes"], ["000001", "000002", "000003"])  # 000005 자격미달 제외!

        # 상승 추세 8개 상위 단계 버튼 + [상승 전체] 확인
        for lbl in ("[상승 전체]", "A-1 장기고점", "A-2 고점 단기하락", "A-3 고점 중기하락", "A-4 중기하락내 단기반등",
                    "A-5 고점 장기하락", "A-6 장기하락내 단중기반등", "A-7 고점조정후 장기재상승", "C-1 고점 이평선밀집"):
            self.assertIn(lbl, r["bullStageHtml"])

        # A-1 선택 시 하위 세부현황(#01 + #04) 합산 2종목 및 행 내 미니배지 표시
        self.assertEqual(r["a1Codes"], ["000001", "000002"])
        self.assertIn("5일선위 상승지속", r["a1TableHtml"])
        self.assertIn("20일선 지지(2일+)", r["a1TableHtml"])

        # 당일 추세 현황 배지 + 수익확률 + AI 요약 카드
        self.assertEqual(r["defaultMainBadge"], "[장기고점(완전정배열) | 5일선위 상승지속]")
        self.assertIn("52.9%", r["defaultProbBadge"])
        self.assertIn("40.1%", r["defaultProbBadge"])
        self.assertTrue(r["aiCardVisible"])
        self.assertEqual(r["aiHeadline"], "투신 주도 완전정배열 돌파")

        # 캔들 호버 시 과거 봉(2026-11-19, A-3 #16)의 추세 현황으로 즉시 전환 & 이탈 시 복귀
        self.assertEqual(r["hoverDateTag"], "📍 호버 2026-11-19")
        self.assertEqual(r["hoverMainBadge"], "[고점 중기하락(20<60) | 20일선 반등돌파]")
        self.assertIn("A-3 고점 중기하락(20<60) | 20일선 반등돌파", r["hoverBrief"])
        self.assertEqual(r["restoredDateTag"], "기준일 2026-11-20")
        self.assertEqual(r["restoredMainBadge"], "[장기고점(완전정배열) | 5일선위 상승지속]")

        # 하락 추세(BEAR) 탭 전환 시 8개 상위 단계 + [하락 전체] 및 종목 표시
        self.assertEqual(r["bearAllCodes"], ["000004"])
        for lbl in ("[하락 전체]", "B-1 장기저점", "B-2 저점 단기상승", "B-3 저점 중기상승", "B-4 중기상승내 단기조정",
                    "B-5 저점 장기상승", "B-6 장기상승내 단중기조정", "B-7 저점 반등실패 재하락", "C-2 저점 이평선밀집"):
            self.assertIn(lbl, r["bearStageHtml"])


class TestAC66MigrationAndScope(unittest.TestCase):
    """AC-66: DB 마이그레이션 정합성 및 비수정 대상 파일(STRATEGY/TEST_REPORT/watchlist/holdings) 무결성 검증"""

    def test_ac66_migration_v30_and_schema_parity_and_untouched_files(self):
        schema_sql = (ROOT / "supabase_schema.sql").read_text(encoding="utf-8")
        mig_path = ROOT / "scripts" / "migration_v30_trend_cycle.sql"
        self.assertTrue(mig_path.exists())
        mig_sql = mig_path.read_text(encoding="utf-8")

        required_tokens = (
            "ALTER TABLE daily_supply_analysis",
            "ADD COLUMN IF NOT EXISTS trend_camp",
            "ADD COLUMN IF NOT EXISTS trend_stage_code",
            "ADD COLUMN IF NOT EXISTS trend_stage_name",
            "ADD COLUMN IF NOT EXISTS trend_detail_code",
            "ADD COLUMN IF NOT EXISTS trend_detail_name",
            "ADD COLUMN IF NOT EXISTS trend_full_label",
            "ADD COLUMN IF NOT EXISTS prob_7p_10d",
            "ADD COLUMN IF NOT EXISTS prob_10p_10d",
            "CREATE INDEX IF NOT EXISTS idx_dsa_date_camp_stage",
            "ALTER TABLE stocks_master",
            "ADD COLUMN IF NOT EXISTS trend_updated_date",
            "CREATE INDEX IF NOT EXISTS idx_sm_trend_stage",
        )
        for tok in required_tokens:
            self.assertIn(tok, schema_sql)
            self.assertIn(tok, mig_sql)

        diff = subprocess.check_output(
            [
                "git", "diff", "--stat", "--",
                "STRATEGY.md", "TEST_REPORT.md",
                "watchlist.html", "holdings.html", "scripts/ls_realtime_bridge.py",
            ],
            cwd=str(ROOT),
            text=True,
        ).strip()
        self.assertEqual(diff, "")


if __name__ == "__main__":
    unittest.main()
