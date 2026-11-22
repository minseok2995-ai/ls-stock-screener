"""v2.9 (AC-57 ~ AC-60): 일일 수급 전수 정량 분석 · Top 10 Gemini AI 요약 · 사후 복기 파이프라인 단위/회귀 검증."""
from __future__ import annotations

import datetime as dt
import io
import json
import pathlib
import subprocess
import sys
import unittest
import urllib.error
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import run_daily_screener as s  # noqa: E402


def _make_weekdays(end_date_str: str, count: int) -> list[str]:
    cur = dt.date.fromisoformat(end_date_str)
    out: list[str] = []
    while len(out) < count:
        if cur.weekday() < 5:
            out.append(cur.isoformat())
        cur -= dt.timedelta(days=1)
    return list(reversed(out))


def _make_series(
    shcode: str,
    dates: list[str],
    base_close: float = 20000.0,
    slope: float = 120.0,
    inst_ratio_last: float = 18.0,
    inst_amt_m_last: float = 650.0,
) -> tuple[list[dict], list[dict]]:
    charts: list[dict] = []
    supplies: list[dict] = []
    for i, d in enumerate(dates):
        c = int(round(base_close + i * slope))
        o = int(round(c * 0.985))
        h = int(round(c * 1.022))
        lo = int(round(c * 0.978))
        vol = 200000 if i < len(dates) - 1 else 360000
        charts.append({
            "shcode": shcode,
            "trade_date": d,
            "open": o,
            "high": h,
            "low": lo,
            "close": c,
            "volume": vol,
            "trading_value_m": round((c * vol) / 1_000_000.0, 2),
        })
        is_last = i == len(dates) - 1
        ratio = inst_ratio_last if is_last else (12.0 if i in (len(dates) - 15, len(dates) - 25) else 2.0)
        amt_m = inst_amt_m_last if is_last else (400.0 if ratio >= 10.0 else 40.0)
        supplies.append({
            "shcode": shcode,
            "trade_date": d,
            "real_inst_vol": int(round(vol * ratio / 100.0)),
            "real_inst_amt": amt_m,
            "inst_vol_ratio": ratio,
            "frg_vol": 15000 if is_last else 2000,
            "frg_amt": 380.0 if is_last else 50.0,
            "frg_vol_ratio": round((15000 / vol) * 100.0, 2) if is_last else 1.0,
            "ind_vol": -30000,
            "fn_inv_vol": 0,
            "etc_corp_vol": 0,
            "itc_vol": 20000 if is_last else 0,
            "itc_amt": 300.0 if is_last else 0.0,
            "pen_vol": 15000 if is_last else 0,
            "pen_amt": 220.0 if is_last else 0.0,
            "pef_vol": 9000 if is_last else 0,
            "pef_amt": 130.0 if is_last else 0.0,
            "ins_vol": 0,
            "ins_amt": 0.0,
            "etc_fin_vol": 0,
            "etc_fin_amt": 0.0,
            "bank_vol": 0,
            "bank_amt": 0.0,
        })
    return s.compute_ema_series(charts), supplies


class TestAC57QuantScoringAndPricing(unittest.TestCase):
    """AC-57: 정량 100점 스코어링 · 자격 필터 · 매수가/손절가/목표가(+7%/+15%) 정확성 검증"""

    def test_ac57_three_tracks_scoring_precision(self):
        dates = _make_weekdays("2026-11-17", 80)
        ref_date = dates[-1]
        charts, supplies = _make_series("005930", dates, base_close=45000, slope=180, inst_ratio_last=20.0, inst_amt_m_last=1200.0)
        master = {"shcode": "005930", "hname": "삼성전자", "market": "KOSPI", "market_cap_eok": 350000.0, "avg_val_20d_eok": 150.0}

        res_aligned = s.score_daily_supply_candidate(charts, supplies, master_row=master, ref_date=ref_date)
        self.assertIsNotNone(res_aligned)
        assert res_aligned is not None
        self.assertTrue(res_aligned["is_qualified"])
        self.assertEqual(res_aligned["disqualify_reason"], "")
        self.assertEqual(res_aligned["trend_stage_code"], "A-1")
        self.assertIn("A-1", res_aligned["signal_type"])
        self.assertGreaterEqual(res_aligned["score_trend"], 23.0)
        self.assertLessEqual(res_aligned["score_supply"], 35.0)
        self.assertLessEqual(res_aligned["score_trigger"], 20.0)
        self.assertGreaterEqual(res_aligned["score_risk_adj"], -15.0)
        self.assertLessEqual(res_aligned["score_risk_adj"], 15.0)
        self.assertGreaterEqual(res_aligned["total_score"], 70.0)
        self.assertLessEqual(res_aligned["total_score"], 100.0)
        self.assertEqual(res_aligned["top_inst_buyers"], {"투신": 3.0, "연기금": 2.2, "사모": 1.3})

        # 저점 단기상승/바닥전환 후보 (BEAR · B-1 / B-2 구간)
        bottom_cand = {
            "shcode": "042700",
            "hname": "한미반도체",
            "market": "KOSPI",
            "trade_date": ref_date,
            "market_cap_eok": 80000.0,
            "avg_val_20d_eok": 95.0,
            "trading_value_eok": 51.0,
            "open": 9600,
            "high": 10300,
            "low": 9550,
            "close": 10200,
            "change_rate": 5.5,
            "volume": 500000,
            "vol_ratio_20d": 2.1,
            "avg_range_20d": 3.8,
            "ema_5": 9950.0,
            "ema_20": 10050.0,
            "ema_60": 11200.0,
            "ema_120": 12000.0,
            "ema_240": 12500.0,
            "inst_vol_ratio": 16.0,
            "real_inst_amt_eok": 8.5,
            "frg_vol_ratio": 3.0,
            "frg_amt_eok": 2.0,
            "consec_5p_days": 1,
            "inst_cum_5d_amt_eok": 9.0,
            "inst_cum_20d_amt_eok": 5.0,
            "higher_low": True,
            "prev_20_high": 10400.0,
            "rsi_14": 58.0,
        }
        res_bottom = s.score_daily_supply_candidate(bottom_cand)
        assert res_bottom is not None
        self.assertEqual(res_bottom["trend_stage_code"], "B-1")
        self.assertEqual(res_bottom["trend_detail_code"], "37")  # 20일선 돌파 (prob7=40.6%)
        self.assertAlmostEqual(res_bottom["score_trend"], round((40.6 - 30.0) * 0.75, 2) + 9.0)
        self.assertTrue(res_bottom["is_qualified"])

        # B-2 저점 단기상승(5>=20) 후보
        short_cand = dict(bottom_cand, ema_5=10100.0, consec_5p_days=2, higher_low=False, prev_20_high=12000.0)
        res_short = s.score_daily_supply_candidate(short_cand)
        assert res_short is not None
        self.assertEqual(res_short["trend_stage_code"], "B-2")
        self.assertAlmostEqual(res_short["score_trend"], round((res_short["prob_7p_10d"] - 30.0) * 0.75, 2))

    def test_ac57_qualification_filters_and_reasons(self):
        base = {
            "shcode": "100001",
            "hname": "테스트주",
            "trade_date": "2026-11-17",
            "market_cap_eok": 5000.0,
            "avg_val_20d_eok": 30.0,
            "trading_value_eok": 20.8,
            "real_inst_amt_eok": 5.0,
            "open": 10000,
            "high": 10500,
            "low": 9900,
            "close": 10400,
            "change_rate": 4.0,
            "volume": 200000,
            "avg_range_20d": 3.2,
            "ema_5": 10200.0,
            "ema_20": 10000.0,
            "ema_60": 9800.0,
            "inst_vol_ratio": 15.0,
        }
        # [v3.0 16.2절 1항 개정] 일거래대금 < 5억 또는 기관순매수 미달(<3억 & <시총 0.1%)만 탈락, 음봉/저변동은 통과
        r_low_val = s.score_daily_supply_candidate(dict(base, shcode="100002", trading_value_eok=4.5))
        r_low_amt = s.score_daily_supply_candidate(dict(base, shcode="100003", real_inst_amt_eok=2.9))
        r_mcap_pass = s.score_daily_supply_candidate(dict(base, shcode="100004", market_cap_eok=1000.0, real_inst_amt_eok=1.2, trading_value_eok=6.0))
        r_bearish_ok = s.score_daily_supply_candidate(dict(base, shcode="100005", open=10500, close=10200, avg_range_20d=1.8))
        r_ok = s.score_daily_supply_candidate(base)

        for r, expected_reason in (
            (r_low_val, "일거래대금5억미만"),
            (r_low_amt, "기관순매수미달(3억·시총0.1%)"),
        ):
            assert r is not None
            self.assertFalse(r["is_qualified"])
            self.assertIn(expected_reason, r["disqualify_reason"])

        assert r_mcap_pass is not None and r_bearish_ok is not None
        self.assertTrue(r_mcap_pass["is_qualified"])
        self.assertTrue(r_bearish_ok["is_qualified"])

        assert r_ok is not None and r_low_val is not None
        ranked = s.rank_daily_supply_candidates([r_low_val, r_ok], ai_top_n=10, has_api_key=True)
        self.assertEqual(len(ranked), 2)  # 자격 미달 종목도 전수 포함
        self.assertEqual(ranked[0]["shcode"], "100001")
        self.assertEqual(ranked[0]["daily_rank"], 1)
        self.assertTrue(ranked[0]["is_top_pick"])
        self.assertEqual(ranked[1]["shcode"], "100002")
        self.assertEqual(ranked[1]["daily_rank"], 2)
        self.assertFalse(ranked[1]["is_top_pick"])  # 자격 미달은 is_top_pick 제외

    def test_ac57_overheated_vs_normal_entry_stop_targets_and_rr(self):
        # 1) 비과열 (disp_ema5 = +2.0%, rsi_14 = 60.0) -> 종가 ~ 5일선 밴드
        normal = s.score_daily_supply_candidate({
            "shcode": "200001",
            "hname": "비과열주",
            "trade_date": "2026-11-17",
            "avg_val_20d_eok": 50.0,
            "real_inst_amt_eok": 6.0,
            "open": 19800,
            "high": 20600,
            "low": 19500,
            "close": 20400,
            "ema_5": 20000.0,
            "ema_20": 19500.0,
            "ema_60": 19000.0,
            "rsi_14": 60.0,
            "avg_range_20d": 3.5,
            "inst_vol_ratio": 14.0,
        })
        assert normal is not None
        self.assertFalse(normal["is_overheated"])
        self.assertEqual(normal["entry_price_ref"], 20200)  # round((20400 + 20000) / 2)
        self.assertEqual(normal["entry_band_low"], 20000)
        self.assertEqual(normal["entry_band_high"], 20400)
        self.assertEqual(normal["stop_loss_price"], 19500)
        self.assertEqual(normal["target_price_1"], round(20200 * 1.07))
        self.assertEqual(normal["target_price_2"], round(20200 * 1.15))
        expected_rr = round((round(20200 * 1.07) - 20200) / (20200 - 19500), 2)
        self.assertEqual(normal["risk_reward_ratio"], expected_rr)

        # 2) 과열 A (disp_ema5 = +6.0% >= 5.0%) -> 5일선 눌림 대기 (round(ema_5))
        over_disp = s.score_daily_supply_candidate({
            "shcode": "200002",
            "hname": "이격과열주",
            "trade_date": "2026-11-17",
            "avg_val_20d_eok": 50.0,
            "real_inst_amt_eok": 6.0,
            "open": 20500,
            "high": 21500,
            "low": 19600,
            "close": 21200,
            "ema_5": 20000.0,
            "ema_20": 19200.0,
            "ema_60": 18500.0,
            "rsi_14": 65.0,
            "avg_range_20d": 4.0,
            "inst_vol_ratio": 18.0,
        })
        assert over_disp is not None
        self.assertTrue(over_disp["is_overheated"])
        self.assertEqual(over_disp["entry_price_ref"], 20000)
        self.assertEqual(over_disp["entry_band_low"], round(20000 * 0.99))
        self.assertEqual(over_disp["entry_band_high"], round(20000 * 1.015))
        self.assertEqual(over_disp["stop_loss_price"], 19600)
        self.assertEqual(over_disp["target_price_1"], 21400)
        self.assertEqual(over_disp["target_price_2"], 23000)

        # 3) 과열 B (disp_ema5 = +3.0% < 5%, 하지만 rsi_14 = 73.5 >= 72.0 & low >= entry_price_ref 극단 보정)
        over_rsi = s.score_daily_supply_candidate({
            "shcode": "200003",
            "hname": "RSI과열갭상승",
            "trade_date": "2026-11-17",
            "avg_val_20d_eok": 50.0,
            "real_inst_amt_eok": 6.0,
            "open": 20400,
            "high": 20800,
            "low": 20300,  # >= ema_5(20000) 이므로 0.95 보정 발동 검증
            "close": 20600,
            "ema_5": 20000.0,
            "ema_20": 19500.0,
            "ema_60": 19000.0,
            "rsi_14": 73.5,
            "avg_range_20d": 3.5,
            "inst_vol_ratio": 15.0,
        })
        assert over_rsi is not None
        self.assertTrue(over_rsi["is_overheated"])
        self.assertEqual(over_rsi["entry_price_ref"], 20000)
        self.assertEqual(over_rsi["stop_loss_price"], 19000)  # round(20000 * 0.95)


class TestAC58GeminiPayloadEnvAndIsolation(unittest.TestCase):
    """AC-58: Gemini 압축 페이로드(40봉+요약) · 환경변수(GEMINI_MODEL, AI_TOP_N) · 무중단 폴백 검증"""

    def test_ac58_compressed_payload_40_bars_and_schema(self):
        dates = _make_weekdays("2026-11-17", 75)
        ref_date = dates[-1]
        charts, supplies = _make_series("000660", dates, base_close=150000, slope=500)
        # 미래 T+1 봉이 섞여 있어도 ref_date 상한으로 제외되는지 함께 확인
        charts_plus_future = charts + [dict(charts[-1], trade_date="2026-11-18", close=199999)]
        row = s.score_daily_supply_candidate(
            charts,
            supplies,
            master_row={"shcode": "000660", "hname": "SK하이닉스", "market": "KOSPI", "market_cap_eok": 1200000.0, "avg_val_20d_eok": 320.0},
            ref_date=ref_date,
        )
        assert row is not None
        payload = s.build_gemini_stock_payload(row, charts_plus_future, supplies, ref_date=ref_date)

        self.assertEqual(set(payload.keys()), {"meta", "quant_summary", "recent_bars"})
        self.assertEqual(len(payload["recent_bars"]), 40)
        self.assertEqual(payload["recent_bars"][-1][0], ref_date)
        self.assertEqual(len(payload["recent_bars"][0]), 13)
        for req_meta in ("shcode", "hname", "market", "trade_date", "market_cap_eok", "avg_val_20d_eok", "daily_rank", "signal_type", "ema_alignment"):
            self.assertIn(req_meta, payload["meta"])
        for req_q in ("total_score", "entry_price_ref", "stop_loss_price", "target_price_1", "target_price_2", "risk_reward_ratio", "is_overheated"):
            self.assertIn(req_q, payload["quant_summary"])

    def test_ac58_env_vars_model_top_n_and_429_retry(self):
        dates = _make_weekdays("2026-11-17", 50)
        ref_date = dates[-1]
        chart_map = {}
        supply_map = {}
        scored = []
        for idx, code in enumerate(("000001", "000002", "000003")):
            c_rows, s_rows = _make_series(code, dates, base_close=20000 + idx * 1000, inst_ratio_last=22.0 - idx * 2)
            chart_map[code] = c_rows
            supply_map[code] = s_rows
            r = s.score_daily_supply_candidate(
                c_rows,
                s_rows,
                master_row={"shcode": code, "hname": f"종목{code}", "market": "KOSPI", "market_cap_eok": 3000.0, "avg_val_20d_eok": 45.0},
                ref_date=ref_date,
            )
            assert r is not None
            scored.append(r)

        ranked = s.rank_daily_supply_candidates(scored, ai_top_n=2, has_api_key=True)
        called_urls: list[str] = []
        attempt_counter = {"cnt": 0}

        gemini_ok_body = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": json.dumps({
                            "headline": "투신·연기금 동반 정배열 신고가 돌파",
                            "supply_comment": "순수기관 3개 주체가 동시 순매수하며 수급 연속성이 강화되었습니다. 외국인도 동반 유입 중입니다.",
                            "chart_comment": "정배열 초기 구간에서 거래량이 실린 양봉으로 마감했습니다. 5일선 이격이 안정적입니다.",
                            "risk_points": ["단기 차익 매물 출회 가능성", "업종 순환매 변동성"],
                            "action_plan": "참고가 부근 분할 접근 후 기준봉 저가 이탈 시 손절합니다. +7%·+15% 분할 익절을 권장합니다.",
                        }, ensure_ascii=False)
                    }]
                }
            }]
        }

        def fake_post(url, payload, headers=None, timeout=30.0):
            called_urls.append(url)
            attempt_counter["cnt"] += 1
            if attempt_counter["cnt"] == 1:
                raise urllib.error.HTTPError(url, 429, "Rate Limit", {}, io.BytesIO(b""))
            return gemini_ok_body

        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "my_sec_key", "GEMINI_MODEL": "gemini-2.5-pro", "AI_TOP_N": "2"}), \
             mock.patch.object(s, "http_post_json", side_effect=fake_post), \
             mock.patch.object(s.time, "sleep"):
            updated, stats = s.populate_gemini_summaries(ranked, chart_map, supply_map, ref_date=ref_date)

        self.assertEqual(stats["target_cnt"], 2)  # AI_TOP_N=2 정확 반영 (3번째 종목은 생략)
        self.assertEqual(stats["success_cnt"], 2)
        self.assertEqual(stats["skipped_cnt"], 1)
        self.assertTrue(all("models/gemini-2.5-pro:generateContent?key=my_sec_key" in u for u in called_urls))
        self.assertGreaterEqual(len(called_urls), 3)  # 2종목 + 첫 호출 429 재시도 1회 = 3회 호출
        self.assertEqual(ranked[2]["ai_status"], "SKIPPED")
        for r in updated:
            self.assertEqual(r["ai_status"], "SUCCESS")
            self.assertEqual(r["ai_model"], "gemini-2.5-pro")
            self.assertEqual(set(r["ai_summary"].keys()), set(s.GEMINI_REQUIRED_KEYS))

    def test_ac58_slot_gating_and_nonstop_isolation_on_missing_key_or_error(self):
        # 1) 실행 시점 제어 검증: prelim 미실행 / final 자동실행 / ANALYSIS_FORCE_RUN=1 강제실행
        with mock.patch.dict("os.environ", {"ANALYSIS_FORCE_RUN": "0"}):
            self.assertFalse(s.should_run_v29_analysis("daily", "prelim"))
            self.assertTrue(s.should_run_v29_analysis("daily", "final"))
            self.assertFalse(s.should_run_v29_analysis("backfill", "final"))
        with mock.patch.dict("os.environ", {"ANALYSIS_FORCE_RUN": "1"}):
            self.assertTrue(s.should_run_v29_analysis("daily", "prelim"))

        # 2) 통합 파이프라인 무중단 격리 검증 (excluded_stocks 제외 + 3일 누적 포착 + API 키 미설정/오류 격리)
        dates = _make_weekdays("2026-11-17", 45)
        ref_date = dates[-1]
        c_day, s_day = _make_series("000010", dates, inst_ratio_last=16.0, inst_amt_m_last=500.0)
        # 000020: 당일 비중은 8.0%(<10%)지만 직전 2일이 14%, 13%여서 3일 누적 >= 10% 로 포착되는 종목
        c_3d, s_3d = _make_series("000020", dates, inst_ratio_last=8.0, inst_amt_m_last=450.0)
        for k, rt in ((-3, 14.0), (-2, 13.0), (-1, 8.0)):
            vol_k = c_3d[k]["volume"]
            s_3d[k]["inst_vol_ratio"] = rt
            s_3d[k]["real_inst_vol"] = int(round(vol_k * rt / 100.0))
        # 000099: excluded_stocks 등록 종목 -> 반드시 후보에서 제외되어야 함
        c_ex, s_ex = _make_series("000099", dates, inst_ratio_last=25.0, inst_amt_m_last=900.0)

        masters = [
            {"shcode": "000010", "hname": "당일포착주", "market": "KOSPI", "market_cap_eok": 5000.0, "avg_val_20d_eok": 55.0, "is_universe": True},
            {"shcode": "000020", "hname": "삼일누적주", "market": "KOSDAQ", "market_cap_eok": 3200.0, "avg_val_20d_eok": 40.0, "is_universe": True},
            {"shcode": "000099", "hname": "영구제외주", "market": "KOSPI", "market_cap_eok": 9000.0, "avg_val_20d_eok": 80.0, "is_universe": True},
        ]
        all_c = {"000010": c_day, "000020": c_3d, "000099": c_ex}
        all_s = {"000010": s_day, "000020": s_3d, "000099": s_ex}

        def fake_get(url, headers=None, timeout=25.0):
            if "/excluded_stocks?" in url:
                return [{"shcode": "000099"}]
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

        upserted_batches: list[tuple[str, list[dict]]] = []

        def fake_upsert(u, k, table, conflict, rows, *a, **kw):
            upserted_batches.append((table, list(rows)))

        # (A) GEMINI_API_KEY 미설정 시: SKIPPED 로 전수 저장 + Step 3 정상 수행
        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "", "AI_TOP_N": "10"}, clear=False), \
             mock.patch.object(s, "http_get_json", side_effect=fake_get), \
             mock.patch.object(s, "http_request_json", return_value=[]), \
             mock.patch.object(s, "supabase_upsert", side_effect=fake_upsert):
            res_no_key = s.run_daily_supply_analysis_pipeline(
                sb_url="https://mock.supabase.co",
                sb_key="mock_key",
                ref_date=ref_date,
                existing_masters=masters,
            )

        self.assertEqual(res_no_key["candidate_cnt"], 2)  # 000010 + 000020 포함, 000099(영구제외) 제외
        saved_codes = {r["shcode"] for r in upserted_batches[0][1]}
        self.assertEqual(saved_codes, {"000010", "000020"})
        self.assertTrue(all(r["ai_status"] == "SKIPPED" for r in upserted_batches[0][1]))

        # (B) GEMINI_API_KEY 설정 상태에서 Gemini 서버 장애(HTTP 500) 시: ERROR 기록 및 무중단 완주
        upserted_batches.clear()
        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "bad_key", "AI_TOP_N": "10"}, clear=False), \
             mock.patch.object(s, "http_get_json", side_effect=fake_get), \
             mock.patch.object(s, "http_request_json", return_value=[]), \
             mock.patch.object(s, "http_post_json", side_effect=RuntimeError("Gemini outage")), \
             mock.patch.object(s, "supabase_upsert", side_effect=fake_upsert):
            res_err = s.run_daily_supply_analysis_pipeline(
                sb_url="https://mock.supabase.co",
                sb_key="mock_key",
                ref_date=ref_date,
                existing_masters=masters,
            )

        self.assertEqual(res_err["candidate_cnt"], 2)
        self.assertEqual(res_err["ai_stats"]["error_cnt"], 2)
        dsa_batches = [rows for tbl, rows in upserted_batches if tbl == "daily_supply_analysis"]
        self.assertEqual(len(dsa_batches), 2)  # Step 1 전수 적재 + Step 2 ERROR 상태 갱신 모두 정상 완료
        self.assertTrue(all(r["ai_status"] == "ERROR" for r in dsa_batches[1]))


class TestAC59OutcomeBackfillAndRetention(unittest.TestCase):
    """AC-59: 사후 복기 수익률(ret_5d/10d/20d, max/min_ret_10d) 자동 백필 및 365일 보관 정리 검증"""

    def test_ac59_compute_and_backfill_outcomes_5d_10d_20d_and_intraday_extremes(self):
        dates = _make_weekdays("2026-11-17", 25)
        sig_date_20 = dates[0]   # 이후 24영업일 확보 -> ret_5d, ret_10d, ret_20d, max/min_ret_10d 모두 산출
        sig_date_6 = dates[18]   # 이후 6영업일 확보 -> ret_5d 만 산출, ret_10d / ret_20d 는 None 유지
        ref_date = dates[-1]

        chart_rows = []
        for idx, d in enumerate(dates):
            # idx==0 기준가 10,000원 -> idx==5 종가 10,700(+7%), idx==10 종가 11,200(+12%), idx==20 종가 12,500(+25%)
            close_map = {0: 10000, 5: 10700, 10: 11200, 20: 12500, 18: 20000, 23: 21000}
            c = close_map.get(idx, 10200)
            hi = 11800 if idx == 3 else (c + 100)  # T+1~T+10 최고가 = 11,800 (+18.0%)
            lo = 9400 if idx == 2 else (c - 100)   # T+1~T+10 최저가 = 9,400 (-6.0%)
            chart_rows.append({"shcode": "005930", "trade_date": d, "high": hi, "low": lo, "close": c})

        pending_dsa = [
            {"trade_date": sig_date_20, "shcode": "005930", "hname": "삼성전자", "daily_rank": 1, "close": 10000,
             "ret_5d": None, "ret_10d": None, "ret_20d": None, "max_ret_10d": None, "min_ret_10d": None},
            {"trade_date": sig_date_6, "shcode": "005930", "hname": "삼성전자", "daily_rank": 2, "close": 20000,
             "ret_5d": None, "ret_10d": None, "ret_20d": None, "max_ret_10d": None, "min_ret_10d": None},
        ]
        captured_updates: list[dict] = []

        def fake_get(url, headers=None, timeout=30.0):
            if "/daily_supply_analysis?" in url:
                return pending_dsa
            if "/daily_chart?" in url:
                return chart_rows
            return []

        def fake_upsert(u, k, table, conflict, rows, *a, **kw):
            self.assertEqual(table, "daily_supply_analysis")
            self.assertEqual(conflict, "trade_date,shcode")
            captured_updates.extend(rows)

        with mock.patch.object(s, "http_get_json", side_effect=fake_get), \
             mock.patch.object(s, "supabase_upsert", side_effect=fake_upsert):
            updated_cnt = s.backfill_daily_supply_outcomes("https://mock.supabase.co", "mock_key", ref_date)

        self.assertEqual(updated_cnt, 2)
        by_dt = {r["trade_date"]: r for r in captured_updates}

        r20 = by_dt[sig_date_20]
        self.assertAlmostEqual(r20["ret_5d"], 7.0)
        self.assertAlmostEqual(r20["ret_10d"], 12.0)
        self.assertAlmostEqual(r20["ret_20d"], 25.0)
        self.assertAlmostEqual(r20["max_ret_10d"], 18.0)
        self.assertAlmostEqual(r20["min_ret_10d"], -6.0)
        self.assertIsNotNone(r20["outcome_updated_at"])

        r6 = by_dt[sig_date_6]
        self.assertAlmostEqual(r6["ret_5d"], 5.0)  # (21000 - 20000) / 20000 * 100 = +5.0%
        self.assertIsNone(r6["ret_10d"])
        self.assertIsNone(r6["ret_20d"])

    def test_ac59_retention_365_days_cleanup(self):
        delete_calls: list[tuple[str, str]] = []

        def fake_req(method, url, payload=None, headers=None, timeout=25.0):
            delete_calls.append((method, url))
            return [{"trade_date": "2025-11-10", "shcode": "005930"}]

        with mock.patch.object(s, "http_request_json", side_effect=fake_req):
            purged = s.cleanup_old_daily_supply_analysis("https://mock.supabase.co", "mock_key", "2026-11-17")

        self.assertEqual(purged, 1)
        self.assertEqual(len(delete_calls), 1)
        self.assertEqual(delete_calls[0][0], "DELETE")
        self.assertIn("/daily_supply_analysis?trade_date=lt.2025-11-17", delete_calls[0][1])


class TestAC60SchemaWorkflowAndScopeIntegrity(unittest.TestCase):
    """AC-60: 스키마 정합성 · 워크플로우 환경변수 · 전략 문서 및 관심/보유 페이지 무변경 검증"""

    def test_ac60_schema_and_migration_ddl_parity(self):
        schema_sql = (ROOT / "supabase_schema.sql").read_text(encoding="utf-8")
        mig_path = ROOT / "scripts" / "migration_v29_daily_supply_analysis.sql"
        self.assertTrue(mig_path.exists())
        mig_sql = mig_path.read_text(encoding="utf-8")

        required_fragments = (
            "CREATE TABLE IF NOT EXISTS daily_supply_analysis",
            "PRIMARY KEY (trade_date, shcode)",
            "CREATE INDEX IF NOT EXISTS idx_dsa_date_rank",
            "CREATE INDEX IF NOT EXISTS idx_dsa_shcode_date",
            "CREATE INDEX IF NOT EXISTS idx_dsa_top_pick",
            "WHERE is_top_pick = TRUE",
            "ALTER TABLE daily_supply_analysis DISABLE ROW LEVEL SECURITY;",
            "GRANT SELECT, INSERT, UPDATE, DELETE ON daily_supply_analysis TO anon, authenticated;",
            "ai_summary JSONB",
            "ret_5d NUMERIC(7, 2)",
            "max_ret_10d NUMERIC(7, 2)",
            "min_ret_10d NUMERIC(7, 2)",
        )
        for frag in required_fragments:
            self.assertIn(frag, schema_sql)
            self.assertIn(frag, mig_sql)

    def test_ac60_workflow_env_and_frontend_strategy_untouched(self):
        wf = (ROOT / ".github" / "workflows" / "daily_batch.yml").read_text(encoding="utf-8")
        self.assertIn("GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}", wf)
        self.assertIn("GEMINI_MODEL: ${{ vars.GEMINI_MODEL || 'gemini-3.5-flash-lite' }}", wf)
        self.assertIn("AI_TOP_N: ${{ vars.AI_TOP_N || '10' }}", wf)

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
