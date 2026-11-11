#!/usr/bin/env python3
"""
=============================================================================
LS증권 Open API 기반 기관·외국인 수급 & EMA(5/20/60/120/240) 스크리닝 배치 시스템
=============================================================================
- 실행 시각: 평일 저녁 21:05 KST (야간시장 마감 이후 GitHub Actions 자동 실행)
- 핵심 기준:
  1) 유니버스: 코스피·코스닥 보통주 (ETF/ETN/ELW/스팩/우선주/리츠 제외)
               시가총액 700억 원 이상 & 최근 20일 평균 거래대금 20억 원 이상
  2) 시가총액/유니버스 산출 주기:
     - 최초 1회(DB 미구축 시) + 매년 3·6·9·12월 첫 거래일에 전체 유니버스 및 실제 시가총액(t1444/t1102) 정기 산출
     - 평일 일일 배치(daily) 시에는 기존 유니버스 종목만 수집하되(상장주식수×당일종가로 시총 부하 없이 자동 갱신),
       당일 거래대금 상위(t1463) 조회(2회 호출, 1.3초)를 통해 분기 중 급등 주도주(시총≥700억 & 20일평균≥20억) 자동 편입
  3) 순수 기관 정의: 투신(itc) + 사모펀드(pef) + 연기금(pen) + 보험(ins) + 기타금융(etc_fin) + 은행(bank)
                     (단기 차익·LP 물량이 섞인 금융투자(fn_inv)는 합산에서 제외하되 별도 컬럼 보관)
  4) 차트 지표: 수정주가(sujung=Y) 기준 일봉 + 5, 20, 60, 120, 240일 지수이동평균(EMA)
  5) 정렬 및 알림: 거래량 대비 순수기관 순매수 비중(%) 높은 순으로 Supabase 저장 및 텔레그램 발송
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Set, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ls_screener")

EMA_SPANS = (5, 20, 60, 120, 240)
PURE_INST_SUBJECTS = ("itc", "pef", "pen", "ins", "etc_fin", "bank")
QUARTERLY_MONTHS = (3, 6, 9, 12)

DEFAULT_SUPABASE_URL = "https://rwvvrtjsxzecmdykwrxg.supabase.co"
DEFAULT_SUPABASE_KEY = "sb_publishable_vH_-2K-y5HwQ9oqiT1gtIw_P9pKdJ26"
DEFAULT_TELEGRAM_CHAT_ID = "1018392459"


# ---------------------------------------------------------------------------
# 1. 표준 HTTP 유틸리티 (외부 패키지 미설치 환경에서도 100% 동작)
# ---------------------------------------------------------------------------
def http_request_json(
    method: str,
    url: str,
    payload: Any = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 25.0,
) -> Any:
    req_headers: Dict[str, str] = {}
    if headers:
        req_headers.update(headers)
    data_bytes: Optional[bytes] = None
    if payload is not None:
        if " Content-Type" not in req_headers and "Content-Type" not in req_headers and "content-type" not in req_headers:
            req_headers["Content-Type"] = "application/json; charset=utf-8"
        data_bytes = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data_bytes, headers=req_headers, method=method.upper())
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw.strip() else {}


def http_post_json(url: str, payload: Any, headers: Optional[Dict[str, str]] = None, timeout: float = 25.0) -> Any:
    return http_request_json("POST", url, payload=payload, headers=headers, timeout=timeout)


def http_get_json(url: str, headers: Optional[Dict[str, str]] = None, timeout: float = 20.0) -> Any:
    return http_request_json("GET", url, payload=None, headers=headers, timeout=timeout)


def http_post_form(url: str, form_data: Dict[str, str], timeout: float = 15.0) -> Any:
    data_bytes = urllib.parse.urlencode(form_data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw.strip() else {}


# ---------------------------------------------------------------------------
# 2. 유니버스 필터 및 EMA / 순수기관 수급 계산
# ---------------------------------------------------------------------------
def is_excluded_security(hname: str, etfgubun: str = "0", spac_gubun: str = "N", bu12gubun: str = "") -> bool:
    """ETF, ETN, ELW, 스팩(SPAC), 우선주, 리츠, 인버스/레버리지 등 제외 판별."""
    if str(etfgubun).strip() in ("1", "2", "3", "4") or str(spac_gubun).strip().upper() == "Y":
        return True
    if str(bu12gubun).strip() not in ("", "01", "00"):
        # bu12gubun이 일반 주권('01')이 아닌 외국주권/기타증권인 경우에도 종목명 추가 검증
        pass

    clean_name = (hname or "").strip()
    if not clean_name:
        return True

    excluded_keywords = (
        "스팩", "SPAC", "ETN", "ETF", "KODEX", "TIGER", "KBSTAR", "RISE", "ACE",
        "SOL", "HANARO", "KOSEF", "ARIRANG", "TIMEFOLIO", "PLUS", "WON", "FOCUS",
        "TREX", "SMART", "파워", "리츠", "맥쿼리", "인버스", "레버리지", "선물",
        "채권", "액티브", "합성", "우B", "우C", "1우", "2우", "3우", "전환",
    )
    upper_name = clean_name.upper()
    for kw in excluded_keywords:
        if kw in upper_name:
            return True

    # 우선주 판별 (예: 삼성전자우, 현대차2우B 등)
    # 단, '대우', '연우', '동우', '선우', '태우', '성우' 등 일반 사명 제외
    non_pref_exceptions = ("대우", "연우", "동우", "선우", "태우", "성우", "정우", "신우", "한우", "영우", "진우")
    if clean_name.endswith("우") and len(clean_name) >= 3:
        if not any(clean_name.endswith(exc) for exc in non_pref_exceptions):
            return True
    if clean_name.endswith(("우(전환)", "(우)")):
        return True

    return False


def compute_ema_series(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """오름차순 정렬된 일봉 리스트에 대해 전일대비 등락률(%) 및 EMA(5/20/60/120/240) 계산."""
    if not rows:
        return []
    sorted_rows = sorted(rows, key=lambda x: str(x["trade_date"]))
    alphas = {span: 2.0 / (span + 1.0) for span in EMA_SPANS}
    ema_state: Dict[int, float] = {}
    prev_close = 0.0
    result: List[Dict[str, Any]] = []

    for idx, r in enumerate(sorted_rows):
        item = dict(r)
        close_val = float(item.get("close", 0) or 0)
        if idx == 0 or prev_close <= 0:
            item["change_rate"] = float(item.get("change_rate", 0.0) or 0.0)
            for span in EMA_SPANS:
                ema_state[span] = close_val
                item[f"ema_{span}"] = round(close_val, 2)
        else:
            item["change_rate"] = round(((close_val - prev_close) / prev_close) * 100.0, 2)
            for span in EMA_SPANS:
                alpha = alphas[span]
                ema_state[span] = (close_val * alpha) + (ema_state[span] * (1.0 - alpha))
                item[f"ema_{span}"] = round(ema_state[span], 2)
        prev_close = close_val
        result.append(item)
    return result


def compute_pure_institutional_supply(row: Dict[str, Any], daily_volume: int) -> Dict[str, Any]:
    """
    순수 기관(투신+사모+연기금+보험+기타금융+은행, 금융투자 제외) 합산 수량·금액 및
    당일 거래량 대비 순매수 비중(%) 계산.
    """
    real_inst_vol = sum(int(row.get(f"{subj}_vol", 0) or 0) for subj in PURE_INST_SUBJECTS)
    real_inst_amt = round(sum(float(row.get(f"{subj}_amt", 0.0) or 0.0) for subj in PURE_INST_SUBJECTS), 2)
    frg_vol = int(row.get("frg_vol", 0) or 0)
    frg_amt = round(float(row.get("frg_amt", 0.0) or 0.0), 2)
    vol = int(daily_volume or 0)

    inst_vol_ratio = round((real_inst_vol / vol) * 100.0, 2) if vol > 0 else 0.0
    frg_vol_ratio = round((frg_vol / vol) * 100.0, 2) if vol > 0 else 0.0

    out = dict(row)
    out.update({
        "real_inst_vol": real_inst_vol,
        "real_inst_amt": real_inst_amt,
        "inst_vol_ratio": inst_vol_ratio,
        "frg_vol": frg_vol,
        "frg_amt": frg_amt,
        "frg_vol_ratio": frg_vol_ratio,
    })
    return out


def is_quarterly_rebuild_due(today: dt.date, existing_masters: List[Dict[str, Any]]) -> Tuple[bool, str]:
    """
    결정 1:
    1) DB에 유니버스 종목이 0건이면 '최초 1회 산출' 실행
    2) 3월, 6월, 9월, 12월의 첫 거래일(1~7일 중 해당 월에 아직 유니버스 전체 산출이 안 된 경우)에 '분기 정기 산출' 실행
    """
    universe_rows = [r for r in existing_masters if r.get("is_universe")]
    if not universe_rows:
        return True, "최초 1회 유니버스 구축 (DB 내 유니버스 0건)"

    if today.month in QUARTERLY_MONTHS and today.day <= 7:
        month_prefix = f"{today.year:04d}-{today.month:02d}"
        # 기존 마스터의 updated_at 중 이번 분기 월(YYYY-MM)에 갱신된 비율 확인
        updated_this_month = [
            r for r in universe_rows
            if str(r.get("updated_at", "")).startswith(month_prefix)
        ]
        if not updated_this_month:
            return True, f"{today.month}월 분기 첫 거래일 정기 시가총액·유니버스 재산출"

    return False, "기존 분기 유니버스 유지 (일일 증분 + 당일 거래대금 상위 급등주 자동 편입 모드)"


# ---------------------------------------------------------------------------
# 3. LS증권 Open API 클라이언트 (공식 TR 스펙 완벽 준수)
# ---------------------------------------------------------------------------
class LSApiClient:
    BASE_URL = "https://openapi.ls-sec.co.kr:8080"

    def __init__(self, app_key: str, app_secret: str, sleep_sec: float = 0.55) -> None:
        self.app_key = app_key
        self.app_secret = app_secret
        self.sleep_sec = sleep_sec
        self.access_token: Optional[str] = None

    def authenticate(self) -> str:
        payload = http_post_form(
            f"{self.BASE_URL}/oauth2/token",
            {
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "appsecretkey": self.app_secret,
                "scope": "oob",
            },
        )
        self.access_token = payload.get("access_token")
        if not self.access_token:
            raise RuntimeError(f"LS증권 토큰 발급 실패: {payload}")
        logger.info("LS증권 Open API 토큰 발급 성공")
        return self.access_token

    def call_tr(
        self,
        endpoint: str,
        tr_cd: str,
        body: Dict[str, Any],
        tr_cont: str = "N",
        tr_cont_key: str = "",
        sleep_override: Optional[float] = None,
    ) -> Dict[str, Any]:
        if not self.access_token:
            self.authenticate()
        headers = {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token}",
            "tr_cd": tr_cd,
            "tr_cont": tr_cont,
            "tr_cont_key": tr_cont_key,
            "mac_address": "000000000000",
        }
        wait_sec = self.sleep_sec if sleep_override is None else sleep_override
        if wait_sec > 0:
            time.sleep(wait_sec)

        for attempt in range(3):
            try:
                res = http_post_json(f"{self.BASE_URL}/{endpoint.lstrip('/')}", body, headers=headers)
                rsp_cd = str(res.get("rsp_cd", "00000"))
                if rsp_cd not in ("00000", "") and "초당" in str(res.get("rsp_msg", "")):
                    time.sleep(1.1 * (attempt + 1))
                    continue
                return res
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(1.2 * (attempt + 1))
                    continue
                raise
        return {}

    def fetch_common_stock_master(self) -> Dict[str, Dict[str, Any]]:
        """
        t8436(주식종목조회 API용)을 호출하여 ETF/ETN/스팩/우선주/리츠가 제외된
        코스피·코스닥 순수 보통주 마스터 맵을 반환합니다.
        """
        data = self.call_tr("/stock/etc", "t8436", {"t8436InBlock": {"gubun": "0"}}, sleep_override=0.35)
        master_map: Dict[str, Dict[str, Any]] = {}
        for item in data.get("t8436OutBlock", []) or []:
            shcode = str(item.get("shcode", "")).strip()
            hname = str(item.get("hname", "")).strip()
            etfgubun = str(item.get("etfgubun", item.get("etf_fg", "0"))).strip()
            spac_gubun = str(item.get("spac_gubun", "N")).strip()
            bu12gubun = str(item.get("bu12gubun", "")).strip()
            if len(shcode) == 6 and shcode.isdigit():
                if not is_excluded_security(hname, etfgubun=etfgubun, spac_gubun=spac_gubun, bu12gubun=bu12gubun):
                    master_map[shcode] = {
                        "shcode": shcode,
                        "hname": hname,
                        "market": "KOSPI" if str(item.get("gubun", "1")).strip() == "1" else "KOSDAQ",
                        "jnilclose": int(item.get("jnilclose", 0) or 0),
                    }
        logger.info("t8436 보통주 마스터 필터링 완료: %d종목 (ETF/ETN/스팩/우선주/리츠 제외)", len(master_map))
        return master_map

    def fetch_market_cap_above_threshold(
        self,
        common_master: Dict[str, Dict[str, Any]],
        min_mcap_eok: float = 700.0,
    ) -> Dict[str, Dict[str, Any]]:
        """
        t1444(시가총액상위) API를 코스피(001)·코스닥(301)별로 연속 조회하여
        실제 시가총액 >= min_mcap_eok(700억) 이상인 모든 보통주의 정확한 시가총액(억원)과 상장주식수를 산출합니다.
        """
        qualified: Dict[str, Dict[str, Any]] = {}
        for upcode, market_label in (("001", "KOSPI"), ("301", "KOSDAQ")):
            idx_val = 0
            tr_cont = "N"
            page_cnt = 0
            while page_cnt < 80:
                page_cnt += 1
                res = self.call_tr(
                    "/stock/high-item",
                    "t1444",
                    {"t1444InBlock": {"upcode": upcode, "idx": idx_val}},
                    tr_cont=tr_cont,
                    sleep_override=0.52,
                )
                rows = res.get("t1444OutBlock1", []) or []
                if not rows:
                    break

                reached_below_min = False
                for r in rows:
                    shcode = str(r.get("shcode", "")).strip()
                    mcap_eok = float(r.get("total", 0) or 0)
                    price = int(r.get("price", 0) or 0)
                    volume = int(r.get("volume", 0) or 0)
                    if mcap_eok < min_mcap_eok:
                        reached_below_min = True
                        continue
                    if shcode in common_master:
                        shares = int((mcap_eok * 100_000_000) / price) if price > 0 else 0
                        info = dict(common_master[shcode])
                        info.update({
                            "market": market_label,
                            "market_cap_eok": round(mcap_eok, 2),
                            "price": price,
                            "shares": shares,
                            "today_vol": volume,
                            "today_val_eok": round((price * volume) / 100_000_000, 2),
                        })
                        qualified[shcode] = info

                next_idx = int((res.get("t1444OutBlock") or {}).get("idx", 0) or 0)
                if reached_below_min or next_idx <= idx_val:
                    break
                idx_val = next_idx
                tr_cont = "Y"

        logger.info("t1444 실제 시가총액 ≥ %.0f억 보통주 추출 완료: %d종목", min_mcap_eok, len(qualified))
        return qualified

    def fetch_top_trading_value_candidates(
        self,
        common_master: Dict[str, Dict[str, Any]],
        pages_per_market: int = 2,
    ) -> Dict[str, Dict[str, Any]]:
        """
        t1463(거래대금상위) API를 호출하여 당일 거래대금이 활발한 상위 종목을 빠르게 조회합니다.
        (일일 배치 시 분기 중 급등 주도주 자동 편입 및 빠른 후보 추출에 활용)
        """
        top_map: Dict[str, Dict[str, Any]] = {}
        for gubun, mkt in (("1", "KOSPI"), ("2", "KOSDAQ")):
            idx_val = 0
            tr_cont = "N"
            for _ in range(pages_per_market):
                res = self.call_tr(
                    "/stock/high-item",
                    "t1463",
                    {
                        "t1463InBlock": {
                            "gubun": gubun,
                            "jnilgubun": "0",
                            "jc_num": 0,
                            "sprice": 0,
                            "eprice": 0,
                            "volume": 0,
                            "idx": idx_val,
                            "jc_num2": 0,
                        }
                    },
                    tr_cont=tr_cont,
                    sleep_override=0.6,
                )
                rows = res.get("t1463OutBlock1", []) or []
                if not rows:
                    break
                for r in rows:
                    shcode = str(r.get("shcode", "")).strip()
                    val_m = float(r.get("value", 0) or 0)  # 백만원 단위
                    price = int(r.get("price", 0) or 0)
                    if shcode in common_master and val_m >= 2000:  # 당일 거래대금 20억(2,000백만원) 이상
                        item = dict(common_master[shcode])
                        item["market"] = mkt
                        item["price"] = price
                        item["today_val_eok"] = round(val_m / 100.0, 2)
                        top_map[shcode] = item
                next_idx = int((res.get("t1463OutBlock") or {}).get("idx", 0) or 0)
                if next_idx <= idx_val:
                    break
                idx_val = next_idx
                tr_cont = "Y"
        return top_map

    def fetch_single_stock_mcap(self, shcode: str) -> Tuple[float, int, int]:
        """
        t1102(주식현재가조회)를 호출하여 개별 종목의 정확한 시가총액(억원), 상장주식수(주), 현재가(원)를 반환합니다.
        - t1102OutBlock.total: 시가총액(억원)
        - t1102OutBlock.listing: 상장주식수(천주) -> * 1000 = 주
        """
        res = self.call_tr("/stock/market-data", "t1102", {"t1102InBlock": {"shcode": shcode}}, sleep_override=0.25)
        out = res.get("t1102OutBlock") or {}
        mcap_eok = float(out.get("total", 0) or 0)
        listing_k = int(out.get("listing", 0) or 0)
        price = int(out.get("price", 0) or 0)
        shares = listing_k * 1000 if listing_k > 0 else (int((mcap_eok * 100_000_000) / price) if price > 0 else 0)
        return round(mcap_eok, 2), shares, price

    def fetch_daily_chart(self, shcode: str, start_date: str, end_date: str, count: int = 500) -> List[Dict[str, Any]]:
        """t8410(API전용주식차트) 일봉 수정주가(sujung=Y) 조회."""
        body = {
            "t8410InBlock": {
                "shcode": shcode,
                "gubun": "2",
                "qrycnt": count,
                "sdate": start_date.replace("-", ""),
                "edate": end_date.replace("-", ""),
                "cts_date": "",
                "comp_yn": "N",
                "sujung": "Y",
            }
        }
        data = self.call_tr("/stock/chart", "t8410", body, sleep_override=0.65)
        rows = data.get("t8410OutBlock1", []) or []
        parsed: List[Dict[str, Any]] = []
        for r in rows:
            d = str(r.get("date", "")).strip()
            if len(d) != 8:
                continue
            close_p = int(r.get("close", 0) or 0)
            vol = int(r.get("jdiff_vol", 0) or 0)
            val_m = float(r.get("value", 0) or 0)
            if val_m <= 0 and close_p > 0 and vol > 0:
                val_m = round((close_p * vol) / 1_000_000.0, 2)
            parsed.append({
                "shcode": shcode,
                "trade_date": f"{d[:4]}-{d[4:6]}-{d[6:8]}",
                "open": int(r.get("open", 0) or 0),
                "high": int(r.get("high", 0) or 0),
                "low": int(r.get("low", 0) or 0),
                "close": close_p,
                "volume": vol,
                "trading_value_m": round(val_m, 2),
            })
        parsed.sort(key=lambda x: x["trade_date"])
        return parsed

    def fetch_investor_supply(
        self,
        shcode: str,
        start_date: str,
        end_date: str,
        vol_by_date: Dict[str, int],
        close_by_date: Optional[Dict[str, int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        t1717(외인기관종목별동향, gubun="0" 일간순매수) 1회 호출로
        주체별 일간 순매수 수량(tjjXXXX_vol) 및 단가(tjjXXXX_dan)/금액(백만원)을 정확히 추출합니다.
        - 사모펀드: tjj0000, 금융투자: tjj0001, 보험: tjj0002, 투신: tjj0003,
          은행: tjj0004, 기타금융: tjj0005, 연기금: tjj0006, 기타법인: tjj0007,
          개인: tjj0008, 등록외국인: tjj0016, 외국인합계: tjj0017
        """
        sdate = start_date.replace("-", "")
        edate = end_date.replace("-", "")
        res = self.call_tr(
            "/stock/frgr-itt",
            "t1717",
            {"t1717InBlock": {"shcode": shcode, "gubun": "0", "fromdt": sdate, "todt": edate}},
            sleep_override=0.65,
        )
        rows = res.get("t1717OutBlock", []) or []
        close_map = close_by_date or {}

        def _extract_vol_and_amt(item: Dict[str, Any], code: str, fallback_close: int) -> Tuple[int, float]:
            # 공식 t1717OutBlock 필드명: tjjXXXX_vol (수량, 주), tjjXXXX_dan (단가, 원)
            vol_raw = item.get(f"{code}_vol", item.get(code, 0))
            vol_val = int(vol_raw or 0)
            dan_raw = item.get(f"{code}_dan", 0)
            dan_val = float(dan_raw or 0)
            unit_price = dan_val if dan_val > 0 else float(fallback_close or 0)
            amt_m = round((vol_val * unit_price) / 1_000_000.0, 2)
            return vol_val, amt_m

        out: List[Dict[str, Any]] = []
        for r in rows:
            d = str(r.get("date", "")).strip()
            if len(d) != 8:
                continue
            t_date = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
            row_close = int(r.get("close", 0) or close_map.get(t_date, 0) or 0)
            row_vol = int(vol_by_date.get(t_date, 0) or r.get("volume", 0) or 0)

            pef_vol, pef_amt = _extract_vol_and_amt(r, "tjj0000", row_close)
            fn_inv_vol, fn_inv_amt = _extract_vol_and_amt(r, "tjj0001", row_close)
            ins_vol, ins_amt = _extract_vol_and_amt(r, "tjj0002", row_close)
            itc_vol, itc_amt = _extract_vol_and_amt(r, "tjj0003", row_close)
            bank_vol, bank_amt = _extract_vol_and_amt(r, "tjj0004", row_close)
            etc_fin_vol, etc_fin_amt = _extract_vol_and_amt(r, "tjj0005", row_close)
            pen_vol, pen_amt = _extract_vol_and_amt(r, "tjj0006", row_close)
            etc_corp_vol, etc_corp_amt = _extract_vol_and_amt(r, "tjj0007", row_close)
            ind_vol, ind_amt = _extract_vol_and_amt(r, "tjj0008", row_close)

            # 외국인: tjj0017_vol 우선, 0이면 tjj0016_vol 참조
            frg_vol, frg_amt = _extract_vol_and_amt(r, "tjj0017", row_close)
            if frg_vol == 0 and int(r.get("tjj0016_vol", 0) or 0) != 0:
                frg_vol, frg_amt = _extract_vol_and_amt(r, "tjj0016", row_close)

            raw = {
                "shcode": shcode,
                "trade_date": t_date,
                "pef_vol": pef_vol,
                "pef_amt": pef_amt,
                "fn_inv_vol": fn_inv_vol,
                "fn_inv_amt": fn_inv_amt,
                "ins_vol": ins_vol,
                "ins_amt": ins_amt,
                "itc_vol": itc_vol,
                "itc_amt": itc_amt,
                "bank_vol": bank_vol,
                "bank_amt": bank_amt,
                "etc_fin_vol": etc_fin_vol,
                "etc_fin_amt": etc_fin_amt,
                "pen_vol": pen_vol,
                "pen_amt": pen_amt,
                "etc_corp_vol": etc_corp_vol,
                "etc_corp_amt": etc_corp_amt,
                "ind_vol": ind_vol,
                "ind_amt": ind_amt,
                "frg_vol": frg_vol,
                "frg_amt": frg_amt,
            }
            out.append(compute_pure_institutional_supply(raw, row_vol))

        out.sort(key=lambda x: x["trade_date"])
        return out


# ---------------------------------------------------------------------------
# 4. Supabase REST 연동 (조회 & Upsert) 및 텔레그램 알림
# ---------------------------------------------------------------------------
def supabase_headers(supabase_key: str) -> Dict[str, str]:
    return {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }


def supabase_fetch_existing_masters(supabase_url: str, supabase_key: str) -> List[Dict[str, Any]]:
    if not supabase_url or not supabase_key:
        return []
    url = f"{supabase_url.rstrip('/')}/rest/v1/stocks_master?select=*&order=market_cap_eok.desc"
    try:
        rows = http_get_json(url, headers=supabase_headers(supabase_key))
        return rows if isinstance(rows, list) else []
    except Exception as exc:
        logger.warning("기존 stocks_master 조회 실패: %s", exc)
        return []


def supabase_upsert(
    supabase_url: str,
    supabase_key: str,
    table: str,
    conflict_cols: str,
    rows: List[Dict[str, Any]],
) -> None:
    if not rows or not supabase_url or not supabase_key:
        return
    headers = supabase_headers(supabase_key)
    headers["Prefer"] = "resolution=merge-duplicates"
    url = f"{supabase_url.rstrip('/')}/rest/v1/{table}?on_conflict={conflict_cols}"
    for i in range(0, len(rows), 400):
        http_post_json(url, rows[i : i + 400], headers=headers)


def send_telegram_alert(bot_token: str, chat_id: str, text: str) -> bool:
    if not bot_token:
        logger.info("TELEGRAM_BOT_TOKEN 미설정으로 텔레그램 발송 생략")
        return False
    if not chat_id:
        try:
            data = http_get_json(f"https://api.telegram.org/bot{bot_token}/getUpdates")
            for item in reversed(data.get("result", [])):
                msg = item.get("message") or {}
                if msg.get("chat", {}).get("id"):
                    chat_id = str(msg["chat"]["id"])
                    break
        except Exception as exc:
            logger.warning("텔레그램 getUpdates 실패: %s", exc)
    if not chat_id:
        logger.warning("텔레그램 Chat ID 미확인")
        return False
    try:
        http_post_json(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            {"chat_id": chat_id, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True},
        )
        logger.info("텔레그램 알림 전송 완료 (chat_id=%s)", chat_id)
        return True
    except Exception as exc:
        logger.warning("텔레그램 전송 실패: %s", exc)
        return False


# ---------------------------------------------------------------------------
# 5. 메인 배치 파이프라인 (분기별 정기 산출 + 일일 증분 & 급등주 자동 편입)
# ---------------------------------------------------------------------------
def run_standalone_batch(
    mode: str = "daily",
    min_ratio: float = 10.0,
    max_stocks: int = 0,
) -> Dict[str, Any]:
    ls_key = os.getenv("LS_APP_KEY", "").strip()
    ls_secret = os.getenv("LS_APP_SECRET", "").strip()
    sb_url = os.getenv("SUPABASE_URL", DEFAULT_SUPABASE_URL).strip() or DEFAULT_SUPABASE_URL
    sb_key = os.getenv("SUPABASE_KEY", DEFAULT_SUPABASE_KEY).strip() or DEFAULT_SUPABASE_KEY
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    tg_chat_id = os.getenv("TELEGRAM_CHAT_ID", DEFAULT_TELEGRAM_CHAT_ID).strip() or DEFAULT_TELEGRAM_CHAT_ID

    if not ls_key or not ls_secret:
        raise ValueError("LS_APP_KEY 및 LS_APP_SECRET 환경변수가 필요합니다.")

    client = LSApiClient(ls_key, ls_secret)
    client.authenticate()

    today = dt.date.today()
    today_str = today.isoformat()
    existing_masters = supabase_fetch_existing_masters(sb_url, sb_key)
    existing_by_code = {str(r["shcode"]): r for r in existing_masters if r.get("shcode")}

    rebuild_due, reason = is_quarterly_rebuild_due(today, existing_masters)
    if mode in ("backfill", "universe"):
        rebuild_due = True
        reason = f"수동 {mode} 모드 실행 (전체 시가총액·유니버스 산출)"

    logger.info("배치 실행 모드 판정: %s (사유: %s)", "분기/초기 유니버스 전체 산출" if rebuild_due else "일일 기존 유니버스 + 급등주 편입", reason)

    common_master = client.fetch_common_stock_master()
    target_candidates: List[Dict[str, Any]] = []

    if rebuild_due:
        # 1) 분기 정기 산출(또는 최초 1회): t1444로 시가총액 ≥ 700억 보통주 전수 추출 후 당일 거래대금/시총 순 정렬
        mcap_map = client.fetch_market_cap_above_threshold(common_master, min_mcap_eok=700.0)
        # 당일 거래대금 상위(t1463) 종목 우선순위 부여
        top_val_map = client.fetch_top_trading_value_candidates(common_master, pages_per_market=4)
        for shcode, t_info in top_val_map.items():
            if shcode not in mcap_map:
                mcap_eok, shares, price = client.fetch_single_stock_mcap(shcode)
                if mcap_eok >= 700.0:
                    t_info.update({"market_cap_eok": mcap_eok, "shares": shares, "price": price})
                    mcap_map[shcode] = t_info

        # 거래대금이 활발한 종목부터 정렬
        target_candidates = sorted(
            mcap_map.values(),
            key=lambda x: (float(x.get("today_val_eok", 0) or 0), float(x.get("market_cap_eok", 0) or 0)),
            reverse=True,
        )
    else:
        # 2) 평일 일일 배치: 기존 유니버스 종목(is_universe=True) 로드 + t1463 당일 거래대금 상위 급등주 자동 편입
        seen_codes: Set[str] = set()
        for shcode, m_row in existing_by_code.items():
            if m_row.get("is_universe") and shcode in common_master:
                target_candidates.append({
                    "shcode": shcode,
                    "hname": m_row.get("hname") or common_master[shcode]["hname"],
                    "market": m_row.get("market") or common_master[shcode]["market"],
                    "shares": int(m_row.get("shares", 0) or 0),
                    "market_cap_eok": float(m_row.get("market_cap_eok", 0) or 0),
                })
                seen_codes.add(shcode)

        # 분기 중 급등 주도주 누락 방지: 당일 거래대금 상위(t1463) 체크
        top_val_map = client.fetch_top_trading_value_candidates(common_master, pages_per_market=2)
        new_surgers = 0
        for shcode, t_info in top_val_map.items():
            if shcode not in seen_codes:
                mcap_eok, shares, price = client.fetch_single_stock_mcap(shcode)
                if mcap_eok >= 700.0:
                    target_candidates.append({
                        "shcode": shcode,
                        "hname": t_info["hname"],
                        "market": t_info["market"],
                        "shares": shares,
                        "market_cap_eok": mcap_eok,
                    })
                    seen_codes.add(shcode)
                    new_surgers += 1
        if new_surgers > 0:
            logger.info("당일 거래대금 상위(t1463) 기반 분기 중 신규 급등 후보 %d종목 추가 편입", new_surgers)

    if max_stocks > 0:
        target_candidates = target_candidates[:max_stocks]
        logger.info("검증/테스트 제한 적용: 상위 %d종목만 처리", len(target_candidates))

    chart_count = 500 if mode == "backfill" else 120
    start_date = (
        (today - dt.timedelta(days=730)).isoformat()
        if mode == "backfill"
        else (today - dt.timedelta(days=180)).isoformat()
    )

    screened_1d: List[Dict[str, Any]] = []
    screened_3d: List[Dict[str, Any]] = []
    universe_count = 0
    latest_trade_date = today_str

    for idx, item in enumerate(target_candidates, 1):
        shcode = item["shcode"]
        hname = item["hname"]
        market = item["market"]
        try:
            chart_rows = client.fetch_daily_chart(shcode, start_date, today_str, count=chart_count)
            if len(chart_rows) < 20:
                continue

            # 최근 20영업일 평균 거래대금(억원) 계산 (trading_value_m은 백만원 단위 -> / 100 = 억원)
            recent_20 = chart_rows[-20:]
            avg_val_20d_eok = round(sum(float(r["trading_value_m"]) for r in recent_20) / 20.0 / 100.0, 2)
            if avg_val_20d_eok < 20.0:
                continue

            enriched_charts = compute_ema_series(chart_rows)
            last_c = enriched_charts[-1]
            last_close = int(last_c["close"])
            latest_trade_date = max(latest_trade_date, str(last_c["trade_date"]))

            # 시가총액 계산: 상장주식수(shares)가 있으면 (상장주식수 × 당일종가)로 API 부하 없이 정밀 갱신
            shares = int(item.get("shares", 0) or 0)
            mcap_eok = float(item.get("market_cap_eok", 0) or 0)
            if shares <= 0 or mcap_eok <= 0:
                mcap_eok, shares, _ = client.fetch_single_stock_mcap(shcode)
            elif last_close > 0 and shares > 0:
                mcap_eok = round((shares * last_close) / 100_000_000.0, 2)

            if mcap_eok < 700.0:
                continue

            vol_map = {r["trade_date"]: int(r["volume"]) for r in enriched_charts}
            close_map = {r["trade_date"]: int(r["close"]) for r in enriched_charts}
            supply_start = (
                start_date
                if mode == "backfill"
                else enriched_charts[max(0, len(enriched_charts) - 25)]["trade_date"]
            )
            supply_rows = client.fetch_investor_supply(shcode, supply_start, today_str, vol_map, close_map)
            if not supply_rows:
                continue

            m_row = {
                "shcode": shcode,
                "hname": hname,
                "market": market,
                "shares": shares,
                "market_cap_eok": mcap_eok,
                "avg_vol_20d": int(sum(int(r["volume"]) for r in recent_20) / 20),
                "avg_val_20d_eok": avg_val_20d_eok,
                "is_universe": True,
                "last_close": last_close,
                "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            }

            supabase_upsert(sb_url, sb_key, "stocks_master", "shcode", [m_row])
            supabase_upsert(sb_url, sb_key, "daily_chart", "shcode,trade_date", enriched_charts[-60:] if mode != "backfill" else enriched_charts)
            supabase_upsert(sb_url, sb_key, "daily_investor_supply", "shcode,trade_date", supply_rows)

            universe_count += 1
            last_s = supply_rows[-1]
            if float(last_s["inst_vol_ratio"]) >= min_ratio:
                screened_1d.append({
                    "shcode": shcode,
                    "hname": hname,
                    "market": market,
                    "inst_vol_ratio": float(last_s["inst_vol_ratio"]),
                    "real_inst_amt": float(last_s["real_inst_amt"]),
                    "real_inst_vol": int(last_s["real_inst_vol"]),
                    "frg_vol_ratio": float(last_s["frg_vol_ratio"]),
                    "change_rate": float(last_c["change_rate"]),
                    "close": last_close,
                    "ema_20": float(last_c["ema_20"]),
                    "ema_60": float(last_c["ema_60"]),
                })

            if len(supply_rows) >= 3 and len(enriched_charts) >= 3:
                vol_3d = sum(int(r["volume"]) for r in enriched_charts[-3:])
                inst_3d = sum(int(r["real_inst_vol"]) for r in supply_rows[-3:])
                amt_3d = sum(float(r["real_inst_amt"]) for r in supply_rows[-3:])
                frg_3d = sum(int(r["frg_vol"]) for r in supply_rows[-3:])
                ratio_3d = round((inst_3d / vol_3d) * 100.0, 2) if vol_3d > 0 else 0.0
                if ratio_3d >= min_ratio:
                    screened_3d.append({
                        "shcode": shcode,
                        "hname": hname,
                        "inst_vol_ratio": ratio_3d,
                        "real_inst_amt": amt_3d,
                        "frg_vol_ratio": round((frg_3d / vol_3d) * 100.0, 2) if vol_3d > 0 else 0.0,
                    })

            if universe_count % 10 == 0:
                logger.info("진행 상황: %d/%d 후보 확인 | 유니버스 적재 %d종목", idx, len(target_candidates), universe_count)
        except Exception as exc:
            logger.warning("종목 처리 중 건너뜀 (%s %s): %s", shcode, hname, exc)

    screened_1d.sort(key=lambda x: x["inst_vol_ratio"], reverse=True)
    screened_3d.sort(key=lambda x: x["inst_vol_ratio"], reverse=True)

    lines = [
        "📊 *[LS 수급·차트 스크리너] 일일 DB 업데이트 완료*",
        f"• 기준 거래일: `{latest_trade_date}`",
        f"• 시총 산출 모드: `{reason}`",
        f"• 분석 유니버스: *{universe_count:,}종목* (시총≥700억 & 20일 평균거래대금≥20억 보통주)",
        "",
        f"🔥 *[당일(1일) 거래량 대비 순수기관 비중 ≥ {min_ratio:.0f}% 상위]*",
        "_(순수기관 = 투신+사모+연기금+보험+기타금융+은행, 금융투자 제외)_",
    ]
    if not screened_1d:
        lines.append("• 해당 기준 충족 종목 없음")
    for i, s in enumerate(screened_1d[:15], 1):
        amt_eok = s["real_inst_amt"] / 100.0
        lines.append(
            f"*{i}. {s['hname']}* (`{s['shcode']}`) *기관비중 {s['inst_vol_ratio']:.1f}%* "
            f"({amt_eok:+.1f}억 | 등락 {s['change_rate']:+.1f}%)"
        )

    lines.extend(["", f"🚀 *[최근 3일 누적 거래량 대비 순수기관 비중 ≥ {min_ratio:.0f}% 상위]*"])
    if not screened_3d:
        lines.append("• 해당 기준 충족 종목 없음")
    for i, s in enumerate(screened_3d[:10], 1):
        amt_eok = s["real_inst_amt"] / 100.0
        lines.append(
            f"*{i}. {s['hname']}* (`{s['shcode']}`) *3일비중 {s['inst_vol_ratio']:.1f}%* "
            f"(누적 {amt_eok:+.1f}억 | 외인 {s['frg_vol_ratio']:+.1f}%)"
        )

    report_text = "\n".join(lines)
    logger.info("요약 리포트:\n%s", report_text)
    send_telegram_alert(tg_token, tg_chat_id, report_text)

    return {
        "latest_trade_date": latest_trade_date,
        "universe_count": universe_count,
        "screened_1d": screened_1d,
        "screened_3d": screened_3d,
        "report_text": report_text,
    }


# ---------------------------------------------------------------------------
# 6. 4단계 데이터 정합성 검증 리포트 (--mode verify)
# ---------------------------------------------------------------------------
def verify_supabase_data(sb_url: str = DEFAULT_SUPABASE_URL, sb_key: str = DEFAULT_SUPABASE_KEY) -> Dict[str, Any]:
    """Supabase DB에 저장된 데이터의 4단계 정합성을 검증하고 상세 리포트를 출력합니다."""
    headers = supabase_headers(sb_key)
    masters = http_get_json(f"{sb_url.rstrip('/')}/rest/v1/stocks_master?select=*&order=market_cap_eok.desc", headers=headers)
    charts = http_get_json(f"{sb_url.rstrip('/')}/rest/v1/daily_chart?select=*&order=trade_date.desc&limit=1000", headers=headers)
    supplies = http_get_json(f"{sb_url.rstrip('/')}/rest/v1/daily_investor_supply?select=*&order=trade_date.desc&limit=1000", headers=headers)

    print("=" * 78)
    print("🔍 [LS 수급·차트 스크리닝 시스템] 4단계 데이터 정합성 검증 리포트")
    print("=" * 78)
    print(f"1) [1단계: 유니버스 & 시가총액 검증]")
    print(f"   - stocks_master 총 종목 수: {len(masters)}종목")
    excluded_leaks = [m for m in masters if is_excluded_security(str(m.get("hname", "")))]
    under_mcap = [m for m in masters if float(m.get("market_cap_eok", 0) or 0) < 700.0]
    under_val = [m for m in masters if float(m.get("avg_val_20d_eok", 0) or 0) < 20.0]
    print(f"   - ETF/ETN/스팩/우선주/리츠 혼입 건수: {len(excluded_leaks)}건 (정상 기준: 0건)")
    print(f"   - 시가총액 700억 미만 혼입 건수: {len(under_mcap)}건 (정상 기준: 0건)")
    print(f"   - 20일 평균 거래대금 20억 미만 혼입 건수: {len(under_val)}건 (정상 기준: 0건)")
    for m in masters[:5]:
        print(
            f"     · {m['hname']}({m['shcode']}, {m['market']}): "
            f"시총 {float(m['market_cap_eok']):,.0f}억 | 20일평균거래대금 {float(m['avg_val_20d_eok']):,.1f}억 | "
            f"상장주식수 {int(m.get('shares', 0)):,}주 | 최근종가 {int(m.get('last_close', 0)):,}원"
        )

    print(f"\n2) [2단계: 수정주가 일봉 & EMA(5/20/60/120/240) 검증]")
    print(f"   - 최근 조회된 daily_chart 레코드 수: {len(charts)}건")
    for c in charts[:5]:
        print(
            f"     · [{c['trade_date']}] 종목 {c['shcode']}: 종가 {int(c['close']):,}원 ({float(c['change_rate']):+.2f}%) | "
            f"거래량 {int(c['volume']):,}주 | EMA5={c['ema_5']}, EMA20={c['ema_20']}, EMA60={c['ema_60']}, EMA120={c['ema_120']}, EMA240={c['ema_240']}"
        )

    print(f"\n3) [3단계: 순수기관(금융투자 제외 6대 주체) 수급 & 거래량 대비 비중(%) 검증]")
    print(f"   - 최근 조회된 daily_investor_supply 레코드 수: {len(supplies)}건")
    formula_errors = 0
    for s in supplies:
        calc_inst = sum(int(s.get(f"{subj}_vol", 0) or 0) for subj in PURE_INST_SUBJECTS)
        if calc_inst != int(s.get("real_inst_vol", 0) or 0):
            formula_errors += 1
    print(f"   - 순수기관 합산 수식(투신+사모+연기금+보험+기타금융+은행, 금투 제외) 오차 건수: {formula_errors}건 (정상 기준: 0건)")
    for s in supplies[:5]:
        print(
            f"     · [{s['trade_date']}] 종목 {s['shcode']}: 순수기관 {int(s['real_inst_vol']):+,}주 "
            f"({float(s['real_inst_amt']):+.1f}백만원, 비중 {float(s['inst_vol_ratio']):+.2f}%) | "
            f"외인 {int(s['frg_vol']):+,}주 ({float(s['frg_vol_ratio']):+.2f}%) | 금투(제외분) {int(s['fn_inv_vol']):+,}주"
        )

    print("=" * 78)
    return {
        "masters_count": len(masters),
        "charts_count": len(charts),
        "supplies_count": len(supplies),
        "excluded_leaks": len(excluded_leaks),
        "formula_errors": formula_errors,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LS증권 수급·차트 스크리닝 배치 및 검증 도구")
    parser.add_argument("--mode", choices=["daily", "backfill", "universe", "verify"], default="daily")
    parser.add_argument("--min-ratio", type=float, default=10.0)
    parser.add_argument("--max-stocks", type=int, default=0, help="테스트용 최대 처리 종목 수 (0=제한없음)")
    args = parser.parse_args()

    if args.mode == "verify":
        verify_supabase_data()
    else:
        run_standalone_batch(mode=args.mode, min_ratio=args.min_ratio, max_stocks=args.max_stocks)
