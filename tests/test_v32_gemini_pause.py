#!/usr/bin/env python3
"""
v3.2 (STRATEGY.md 18절, AC-72 ~ AC-73) 검증 스위트:
- AC-72: DEFAULT_AI_TOP_N=0 및 daily_batch.yml AI_TOP_N 기본 '0' 전환으로 final 슬롯에서도
         AI_TOP_N 미지정 시 Gemini API 호출 0회 · SKIPPED 유지 · Step 1(정량/추세/Top 10 is_top_pick) 및
         Step 3(사후 복기 및 과거 ai_summary 보존) 정상 동작 + AI_TOP_N 양수 지정 시 무코드 즉시 재개 검증
- AC-73: DB 스키마 · 프론트엔드 4종 · STRATEGY.md · TEST_REPORT.md 무변경 원칙 검증
"""
import datetime as dt
import json
import os
import pathlib
import subprocess
import unittest
from unittest import mock

import run_daily_screener as s

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _make_weekdays(end_date_str: str, n: int) -> list[str]:
    cur = dt.date.fromisoformat(end_date_str)
    out: list[str] = []
    while len(out) < n:
        if cur.weekday() < 5:
            out.append(cur.isoformat())
        cur -= dt.timedelta(days=1)
    out.reverse()
    return out


def _make_candidate_series(shcode: str, dates: list[str], inst_ratio: float, inst_amt_m: float):
    charts = []
    supplies = []
    for idx, d in enumerate(dates):
        close = 20000 + idx * 100
        vol = 100000
        charts.append({
            "shcode": shcode,
            "trade_date": d,
            "open": close - 150,
            "high": close + 250,
            "low": close - 200,
            "close": close,
            "change_rate": 1.2,
            "volume": vol,
            "trading_value_m": round((close * vol) / 1_000_000.0, 2),
        })
        is_last = idx == len(dates) - 1
        rt = inst_ratio if is_last else 1.5
        amt = inst_amt_m if is_last else 30.0
        supplies.append({
            "shcode": shcode,
            "trade_date": d,
            "real_inst_vol": int(vol * rt / 100.0),
            "real_inst_amt": amt,
            "inst_vol_ratio": rt,
            "frg_vol": 1000,
            "frg_amt": 20.0,
            "frg_vol_ratio": 1.0,
            "ind_vol": -int(vol * rt / 100.0) - 1000,
            "fn_inv_vol": 0,
            "etc_corp_vol": 0,
            "itc_vol": int(vol * rt / 100.0),
            "itc_amt": amt,
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
        })
    return s.compute_ema_series(charts), supplies


class TestV32GeminiDefaultPause(unittest.TestCase):
    def test_ac72_constants_resolve_and_workflow_default_zero(self) -> None:
        self.assertEqual(s.DEFAULT_AI_TOP_N, 0)
        self.assertEqual(s.DEFAULT_TOP_PICK_LIMIT, 10)
        self.assertEqual(s.DEFAULT_GEMINI_MODEL, "gemini-3.5-flash-lite")

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AI_TOP_N", None)
            self.assertEqual(s.resolve_ai_top_n(), 0)
            self.assertEqual(s.resolve_ai_top_n(""), 0)
            self.assertEqual(s.resolve_ai_top_n("   "), 0)
            self.assertEqual(s.resolve_ai_top_n("not_an_int"), 0)
            self.assertEqual(s.resolve_ai_top_n("-7"), 0)
            self.assertEqual(s.resolve_ai_top_n("10"), 10)
            self.assertEqual(s.resolve_ai_top_n(15), 15)
            self.assertEqual(s.resolve_ai_top_n("500"), 200)

        wf = (ROOT / ".github" / "workflows" / "daily_batch.yml").read_text(encoding="utf-8")
        self.assertIn("AI_TOP_N: ${{ vars.AI_TOP_N || '0' }}", wf)
        self.assertIn("GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}", wf)
        self.assertIn("GEMINI_MODEL: ${{ vars.GEMINI_MODEL || 'gemini-3.5-flash-lite' }}", wf)

    def test_ac72_top_10_is_top_pick_preserved_when_ai_top_n_zero(self) -> None:
        scored_rows = []
        for i in range(1, 16):  # 15 qualified candidates
            scored_rows.append({
                "shcode": f"{i:06d}",
                "is_qualified": True,
                "total_score": 95.0 - i,
                "inst_vol_ratio": 25.0 - i * 0.5,
                "real_inst_amt_eok": 10.0,
                "ai_model": "",
                "ai_status": "PENDING",
                "ai_summary": None,
                "ai_generated_at": None,
            })
        for j in range(16, 19):  # 3 unqualified candidates
            scored_rows.append({
                "shcode": f"{j:06d}",
                "is_qualified": False,
                "total_score": 99.0,
                "inst_vol_ratio": 30.0,
                "real_inst_amt_eok": 0.5,
                "ai_model": "",
                "ai_status": "PENDING",
                "ai_summary": None,
                "ai_generated_at": None,
            })

        ranked = s.rank_daily_supply_candidates(scored_rows, ai_top_n=0, has_api_key=True)
        self.assertEqual([r["daily_rank"] for r in ranked], list(range(1, 19)))
        top_picks = [r["shcode"] for r in ranked if r["is_top_pick"]]
        self.assertEqual(len(top_picks), 10)
        self.assertEqual(top_picks, [f"{i:06d}" for i in range(1, 11)])
        self.assertTrue(all(not r["is_top_pick"] for r in ranked[10:]))
        self.assertTrue(
            all(
                r["ai_status"] == "SKIPPED"
                and r["ai_model"] == ""
                and r["ai_summary"] is None
                and r["ai_generated_at"] is None
                for r in ranked
            )
        )

    def test_ac72_final_slot_default_zero_gemini_calls_step1_step3_and_reenable(self) -> None:
        dates = _make_weekdays("2026-11-27", 45)
        ref_date = dates[-1]
        past_sig_date = dates[-7]  # 이후 6영업일 경과 -> Step 3 에서 ret_5d 백필 대상

        codes = [f"{1000 + i:06d}" for i in range(12)]
        masters = [
            {
                "shcode": c,
                "hname": f"종목{c}",
                "market": "KOSPI",
                "market_cap_eok": 3000.0,
                "avg_val_20d_eok": 30.0,
                "is_universe": True,
            }
            for c in codes
        ]
        chart_by_code = {}
        supply_by_code = {}
        for idx, c in enumerate(codes):
            ch, sp = _make_candidate_series(c, dates, inst_ratio=14.0 + idx, inst_amt_m=450.0 + idx * 20)
            chart_by_code[c] = ch
            supply_by_code[c] = sp

        past_ai_row = {
            "trade_date": past_sig_date,
            "shcode": codes[0],
            "hname": f"종목{codes[0]}",
            "close": chart_by_code[codes[0]][-7]["close"],
            "ai_model": "gemini-3.5-flash-lite",
            "ai_status": "SUCCESS",
            "ai_summary": {"headline": "과거 AI 코멘트 보존 확인"},
            "ai_generated_at": "2026-11-19T20:40:00+09:00",
            "ret_5d": None,
            "ret_10d": None,
            "ret_20d": None,
            "max_ret_10d": None,
            "min_ret_10d": None,
        }

        def fake_get(url: str, headers=None, timeout: float = 30.0):
            if "/excluded_stocks?" in url:
                return []
            if "shcode=eq.005930" in url or "shcode=eq.000660" in url:
                return [{"trade_date": d} for d in reversed(dates[-5:])]
            if "/daily_supply_analysis?" in url:
                if "or=(ret_5d.is.null" in url:
                    return [dict(past_ai_row)]
                return []
            if "trade_date=in.(" in url:
                dt_set = set(url.split("trade_date=in.(")[1].split(")")[0].split(","))
                req_codes = url.split("shcode=in.(")[1].split(")")[0].split(",")
                src = chart_by_code if "/daily_chart?" in url else supply_by_code
                return [r for c in req_codes for r in src.get(c, []) if r["trade_date"] in dt_set]
            if "/daily_chart?" in url and "shcode=in.(" in url:
                req_codes = url.split("shcode=in.(")[1].split(")")[0].split(",")
                if "order=shcode.asc,trade_date.desc" in url:
                    return [r for c in req_codes for r in reversed(chart_by_code.get(c, []))]
                return [r for c in req_codes for r in chart_by_code.get(c, [])]
            if "/daily_investor_supply?" in url and "shcode=in.(" in url:
                req_codes = url.split("shcode=in.(")[1].split(")")[0].split(",")
                return [r for c in req_codes for r in supply_by_code.get(c, [])]
            return []

        gemini_calls: list[str] = []
        upserts: list[tuple[str, list[dict]]] = []

        def fake_post(url: str, payload, headers=None, timeout: float = 30.0):
            gemini_calls.append(url)
            return {
                "candidates": [{
                    "content": {"parts": [{"text": json.dumps({
                        "headline": "재개 요약",
                        "supply_comment": "수급 유입",
                        "chart_comment": "정배열 지지",
                        "risk_points": ["단기 이격"],
                        "action_plan": "분할 매수",
                    }, ensure_ascii=False)}]}
                }]
            }

        def fake_upsert(_u, _k, table: str, _cols: str, rows: list[dict], *a, **kw):
            upserts.append((table, [dict(r) for r in rows]))

        # (A) 기본 상태(AI_TOP_N 미지정 -> 0): GEMINI_API_KEY 가 있어도 final 슬롯에서 Gemini 호출 0회!
        with (
            mock.patch.dict(os.environ, {"GEMINI_API_KEY": "real_secret_key", "ANALYSIS_FORCE_RUN": "0"}, clear=False),
            mock.patch.object(s, "http_get_json", side_effect=fake_get),
            mock.patch.object(s, "http_post_json", side_effect=fake_post),
            mock.patch.object(s, "http_request_json", return_value=[]),
            mock.patch.object(s, "supabase_upsert", side_effect=fake_upsert),
            self.assertLogs("ls_screener", level="INFO") as cm,
        ):
            prev_top = os.environ.pop("AI_TOP_N", None)
            try:
                res_paused = s.run_daily_supply_analysis_pipeline(
                    sb_url="https://mock.supabase.co",
                    sb_key="mock_key",
                    ref_date=ref_date,
                    existing_masters=masters,
                    effective_slot="final",
                )
            finally:
                if prev_top is not None:
                    os.environ["AI_TOP_N"] = prev_top

        self.assertEqual(len(gemini_calls), 0)
        self.assertTrue(any("Gemini AI 코멘트 추출 비활성(AI_TOP_N=0) — 호출 생략" in m for m in cm.output))
        self.assertEqual(res_paused["candidate_cnt"], 12)
        self.assertEqual(res_paused["qualified_cnt"], 12)
        self.assertEqual(res_paused["master_trend_updated"], 12)
        self.assertEqual(res_paused["backfilled_outcomes"], 1)
        self.assertEqual(res_paused["ai_stats"], {"target_cnt": 0, "success_cnt": 0, "error_cnt": 0, "skipped_cnt": 12})
        self.assertEqual(sum(1 for r in res_paused["rows"] if r["is_top_pick"]), 10)
        self.assertTrue(all(r["ai_status"] == "SKIPPED" and r["ai_summary"] is None for r in res_paused["rows"]))

        # Step 1 당일 Upsert(1회) + Step 3 과거 복기 Upsert(1회)만 수행되며 과거 행의 ai_summary 는 무손상 보존
        dsa_upserts = [rows for tbl, rows in upserts if tbl == "daily_supply_analysis"]
        self.assertEqual(len(dsa_upserts), 2)
        backfilled_row = dsa_upserts[1][0]
        self.assertEqual(backfilled_row["trade_date"], past_sig_date)
        self.assertIsNotNone(backfilled_row["ret_5d"])
        self.assertEqual(backfilled_row["ai_status"], "SUCCESS")
        self.assertEqual(backfilled_row["ai_summary"], {"headline": "과거 AI 코멘트 보존 확인"})

        # (B) AI_TOP_N="3" 명시 지정 시 코드 수정 없이 즉시 Gemini 요약 재개 동작 확인
        upserts.clear()
        gemini_calls.clear()
        with (
            mock.patch.dict(
                os.environ,
                {"GEMINI_API_KEY": "real_secret_key", "ANALYSIS_FORCE_RUN": "0", "AI_TOP_N": "3"},
                clear=False,
            ),
            mock.patch.object(s, "http_get_json", side_effect=fake_get),
            mock.patch.object(s, "http_post_json", side_effect=fake_post),
            mock.patch.object(s, "http_request_json", return_value=[]),
            mock.patch.object(s, "supabase_upsert", side_effect=fake_upsert),
        ):
            res_resumed = s.run_daily_supply_analysis_pipeline(
                sb_url="https://mock.supabase.co",
                sb_key="mock_key",
                ref_date=ref_date,
                existing_masters=masters,
                effective_slot="final",
            )

        self.assertEqual(len(gemini_calls), 3)
        self.assertEqual(res_resumed["ai_stats"]["target_cnt"], 3)
        self.assertEqual(res_resumed["ai_stats"]["success_cnt"], 3)
        self.assertTrue(all("models/gemini-3.5-flash-lite:generateContent" in u for u in gemini_calls))

    def test_ac72_ac73_preserved_functions_schema_and_untouched_scope(self) -> None:
        # AI 헬퍼 함수 원형 보존 확인
        self.assertTrue(callable(s.build_gemini_stock_payload))
        self.assertTrue(callable(s.call_gemini_stock_summary))
        self.assertTrue(callable(s.populate_gemini_summaries))

        # DB 스키마 4개 AI 컬럼 보존 확인
        schema_sql = (ROOT / "supabase_schema.sql").read_text(encoding="utf-8")
        for col in ("ai_model", "ai_status", "ai_summary", "ai_generated_at"):
            self.assertIn(col, schema_sql)
            self.assertIn(col, s.DSA_UPSERT_COLUMNS)

        # 프론트엔드 4종 · 스키마 · STRATEGY.md · TEST_REPORT.md 무변경 확인
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
