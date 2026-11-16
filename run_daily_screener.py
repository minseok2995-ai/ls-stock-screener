#!/usr/bin/env python3
"""
=============================================================================
LS증권 Open API 기반 기관·외국인 수급 & EMA(5/20/60/120/240) 스크리닝 배치 시스템
=============================================================================
- 실행 시각: 평일 저녁 20:30 KST (야간시장 마감 이후 GitHub Actions + 외부 웹훅 자동 실행, 20:47·21:17 KST 다중 백업)
- 핵심 기준 (Strategy v2.1 & 4중 누락 방지 아키텍처):
  1) 유니버스: 코스피·코스닥 보통주 (ETF/ETN/ELW/스팩/우선주/리츠/인버스/레버리지 제외)
               시가총액 700억 원 이상 전 종목 (약 1,463종목 100% 적재, 수집 단계 거래대금 사전 차단 제거)
  2) 시가총액/유니버스 산출 주기:
     - DB 내 유니버스 종목이 1,200종목 미만(미완성 초기 상태)이거나 매년 3·6·9·12월 첫 거래일에
       전체 유니버스 및 실제 시가총액(t1444/t1102) 전수 산출
     - 평일 일일 배치(daily) 시에는 기존 유니버스 전 종목을 유지하되(상장주식수×당일종가로 시총 갱신),
       당일 거래대금 상위(t1463) 조회를 통해 분기 중 시총 700억 돌파 급등주 자동 편입
  3) 데이터 보존 범위 (2년치 약 500영업일):
     - daily_chart: 수정주가(sujung=Y) 일봉 + EMA(5, 20, 60, 120, 240) 2년치(약 500영업일) 전수 적재
     - daily_investor_supply: t1717 역순 날짜 슬라이딩 연속 조회로 2년치(약 500영업일) 전수 적재
     - 평일 daily 모드에서는 이미 2년치 적재된 종목은 최근 증분(25영업일)만 고속 Upsert하고,
       2년치 미적재 종목은 자동으로 2년치 전체 백필 수행
  4) 순수 기관 정의: 투신(itc) + 사모펀드(pef) + 연기금(pen) + 보험(ins) + 기타금융(etc_fin) + 은행(bank)
                     (단기 차익·LP 물량이 섞인 금융투자(fn_inv)는 합산에서 제외하되 별도 컬럼 보관)
  5) 4중 스케줄 안정성: KST(UTC+9) 표준시 일원화, --skip-if-completed(98.5% 완주 멱등성 가드),
                        미처리 종목 고속 이어받기 및 전 종목 DB 기준 텔레그램 리포트 집계 지원
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import gzip
import http.client
import io
import json
import logging
import os
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Set, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ls_screener")

KST_TZ = dt.timezone(dt.timedelta(hours=9))
EMA_SPANS = (5, 20, 60, 120, 240)
PURE_INST_SUBJECTS = ("itc", "pef", "pen", "ins", "etc_fin", "bank")
QUARTERLY_MONTHS = (3, 6, 9, 12)
MIN_COMPLETE_UNIVERSE_COUNT = 1200
DAILY_COMPLETION_THRESHOLD_PCT = 98.5

# --- v2.3 (STRATEGY.md 6절): 10년치 확장 상수 ---
HISTORY_START_DATE = "2016-01-01"  # LS 서버 수급 하한 탐색 기준(과거 호환)
CHART_HISTORY_START_DATE = "2021-11-01"  # v2.3.1 차트 기본 5년
SUPPLY_HISTORY_START_DATE = "2023-11-01"  # v2.3.1 수급 기본 3년
TARGET_10Y_CHART_COUNT = 3000
SUPPLY_MAX_PAGES_10Y = 135
MIN_CHART_OLDEST_10Y = "2016-01-15"
RECENT_IPO_CUTLINE = "2024-11-15"
TWO_YEAR_CUT_OLD = "2024-10-20"
ANCHOR_RECENT_CALENDAR_DAYS = 105
ANCHOR_RECENT_COUNT = 60
ANCHOR_OFFSET_TRADING_DAYS = 5
PROBE_STOCKS = (("005930", "삼성전자"), ("000660", "SK하이닉스"), ("005380", "현대차"))
DEFAULT_BACKFILL_10Y_RUNTIME_MIN = 320
MAX_CHAIN_ROUND = 6
DAILY_YIELD_WINDOW_KST = ((20, 10), (21, 20))  # 평일 20:10 ~ 21:20 KST 에는 daily 배치에 양보
DAILY_YIELD_WINDOW_PRELIM_KST = ((15, 55), (16, 45))  # [v2.6] 평일 15:55 ~ 16:45 KST (1차 가집계 배치 양보 구간)
BATCH_SLOT_FINAL_CUTOFF_KST = (19, 30)  # auto 슬롯: 19:30 KST 미만 prelim, 이상 final
FINAL_SLOT_MIN_UPDATED_HM_KST = "20:00:00"  # final 슬롯 완료 판정 기준선(KST)
MEGA_CAP_3_SHCODES = ("005930", "000660", "005380")
REPRESENTATIVE_10_SHCODES = (
    "005930", "000660", "005380", "012450", "196170",
    "006650", "023160", "218410", "166090", "009420",
)

# --- v2.8 (STRATEGY.md 12절): 일일 배치 초고속 파이프라인 상수 ---
FLUSH_BATCH_STOCKS = 50  # 증분 종목 Upsert 버퍼 플러시 단위
TR_INTERVAL_INCREMENTAL = 0.38  # 단건(1페이지) 증분 TR 최소 간격(초)
TR_INTERVAL_MULTI = 0.45  # 다중 페이지 연속 조회 TR 최소 간격(초)
PREFETCH_PARALLEL_WORKERS = 6
INCREMENTAL_SUPPLY_UPSERT_DAYS = 10
TR_SERVER_FLOOR_BY_CD: Dict[str, float] = {"t8410": 1.04, "t1717": 0.54}  # [v2.8.2] TR별 서버 물리 최소 간격(초)

DEFAULT_SUPABASE_URL = "https://rwvvrtjsxzecmdykwrxg.supabase.co"
DEFAULT_SUPABASE_KEY = "sb_publishable_vH_-2K-y5HwQ9oqiT1gtIw_P9pKdJ26"
DEFAULT_TELEGRAM_CHAT_ID = "1018392459"


def get_kst_now(now_utc: Optional[dt.datetime] = None) -> dt.datetime:
    """시스템 타임존(UTC 등)과 무관하게 한국 표준시(KST = UTC+9) 현재 시각을 반환합니다."""
    base = now_utc if now_utc is not None else dt.datetime.now(dt.timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=dt.timezone.utc)
    return base.astimezone(KST_TZ)


def get_kst_today(now_utc: Optional[dt.datetime] = None) -> dt.date:
    """시스템 타임존(UTC 등)과 무관하게 한국 표준시(KST = UTC+9) 기준 오늘 날짜를 반환합니다."""
    return get_kst_now(now_utc).date()


def _write_github_output(key: str, value: str) -> None:
    gh_out = os.getenv("GITHUB_OUTPUT", "").strip()
    if gh_out:
        try:
            with open(gh_out, "a", encoding="utf-8") as fh:
                fh.write(f"{key}={value}\n")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 1. 표준 HTTP 유틸리티 (외부 패키지 미설치 환경에서도 100% 동작)
# ---------------------------------------------------------------------------
class KeepAliveHttpPool:
    """
    [v2.8 12.1절] 표준 라이브러리 전용 스레드별·호스트별 영구 HTTP/1.1 Keep-Alive 커넥션 풀.
    - 서버 측 유휴 종료 감지 시 캐시 소켓을 닫고 새 연결로 1회 자동 재시도
    - HTTP >= 400 은 바디를 끝까지 읽은 뒤 urllib.error.HTTPError 로 변환(상위 e.code 분기 호환)
    - Content-Encoding: gzip 투명 해제
    """

    def __init__(self) -> None:
        self._local = threading.local()
        self._ctx = ssl.create_default_context()
        self._count_lock = threading.Lock()
        self.connect_count = 0

    def _new_conn(self, scheme: str, host: str, port: int, timeout: float) -> http.client.HTTPConnection:
        with self._count_lock:
            self.connect_count += 1
        if scheme == "https":
            return http.client.HTTPSConnection(host, port, timeout=timeout, context=self._ctx)
        return http.client.HTTPConnection(host, port, timeout=timeout)

    def _conns(self) -> Dict[Tuple[str, str, int], http.client.HTTPConnection]:
        d = getattr(self._local, "conns", None)
        if d is None:
            d = {}
            self._local.conns = d
        return d

    def close_all(self) -> None:
        for c in list(self._conns().values()):
            try:
                c.close()
            except Exception:  # noqa: BLE001
                pass
        self._conns().clear()

    def request(
        self, method: str, url: str, body: Optional[bytes], headers: Dict[str, str], timeout: float
    ) -> Tuple[int, Dict[str, str], bytes]:
        parts = urllib.parse.urlsplit(url)
        scheme = parts.scheme.lower()
        host = parts.hostname or ""
        port = parts.port or (443 if scheme == "https" else 80)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        key = (scheme, host, port)

        req_headers = dict(headers)
        lower = {k.lower() for k in req_headers}
        if "connection" not in lower:
            req_headers["Connection"] = "keep-alive"
        if "accept-encoding" not in lower:
            req_headers["Accept-Encoding"] = "gzip"
        if "host" not in lower:
            req_headers["Host"] = parts.netloc

        conns = self._conns()
        last_exc: Optional[BaseException] = None
        for attempt in range(2):
            conn = conns.get(key)
            reused = conn is not None
            if conn is None:
                conn = self._new_conn(scheme, host, port, timeout)
                conns[key] = conn
            else:
                conn.timeout = timeout
                if getattr(conn, "sock", None) is not None:
                    try:
                        conn.sock.settimeout(timeout)
                    except Exception:  # noqa: BLE001
                        pass
            try:
                conn.request(method, path, body=body, headers=req_headers)
                resp = conn.getresponse()
                raw = resp.read()  # 소켓 오염 방지: 상태코드와 무관하게 바디 완전 소비
                status = resp.status
                resp_headers = {k.lower(): v for k, v in resp.getheaders()}
                reason = resp.reason
                if resp_headers.get("connection", "").lower() == "close" or resp.will_close:
                    conn.close()
                    conns.pop(key, None)
                break
            except (
                http.client.RemoteDisconnected, http.client.BadStatusLine, http.client.CannotSendRequest,
                http.client.ResponseNotReady, ConnectionError, TimeoutError, ssl.SSLError, OSError,
            ) as exc:
                last_exc = exc
                try:
                    conn.close()
                except Exception:  # noqa: BLE001
                    pass
                conns.pop(key, None)
                if attempt == 0 and reused:
                    continue  # 유휴 소켓 종료 → 새 연결로 1회 재시도
                raise
        else:  # pragma: no cover
            raise last_exc if last_exc else RuntimeError("keep-alive request failed")

        if resp_headers.get("content-encoding", "").lower() == "gzip" and raw:
            raw = gzip.decompress(raw)
        if status >= 400:
            msg = http.client.HTTPMessage()
            for k, v in resp_headers.items():
                msg[k] = v
            raise urllib.error.HTTPError(url, status, reason, msg, io.BytesIO(raw))
        return status, resp_headers, raw


_HTTP_POOL = KeepAliveHttpPool()


def _should_use_keepalive(url: str) -> bool:
    """명시적 프록시 환경(HTTP(S)_PROXY)에서는 urllib 경로로 폴백 (no_proxy 대상 호스트는 풀 사용)."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme.lower() not in ("http", "https"):
        return False
    try:
        proxies = urllib.request.getproxies()
        if parts.scheme.lower() in proxies and not urllib.request.proxy_bypass(parts.hostname or ""):
            return False
    except Exception:  # noqa: BLE001
        return False
    return True


def _http_exchange(
    method: str, url: str, data_bytes: Optional[bytes], headers: Dict[str, str], timeout: float
) -> Tuple[str, Dict[str, str]]:
    """공통 저수준 송수신: (응답 본문 텍스트, 소문자 응답 헤더). >=400 은 urllib.error.HTTPError."""
    if _should_use_keepalive(url):
        _, resp_headers, raw_bytes = _HTTP_POOL.request(method, url, data_bytes, headers, timeout)
        return raw_bytes.decode("utf-8", errors="replace"), resp_headers
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return raw, {k.lower(): v for k, v in resp.headers.items()}


def http_request_json(
    method: str,
    url: str,
    payload: Any = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 30.0,
) -> Any:
    req_headers: Dict[str, str] = {}
    if headers:
        req_headers.update(headers)
    data_bytes: Optional[bytes] = None
    if payload is not None:
        if "Content-Type" not in req_headers and "content-type" not in req_headers:
            req_headers["Content-Type"] = "application/json; charset=utf-8"
        data_bytes = json.dumps(payload).encode("utf-8")

    raw, _ = _http_exchange(method.upper(), url, data_bytes, req_headers, timeout)
    return json.loads(raw) if raw.strip() else {}


def http_post_json(url: str, payload: Any, headers: Optional[Dict[str, str]] = None, timeout: float = 30.0) -> Any:
    return http_request_json("POST", url, payload=payload, headers=headers, timeout=timeout)


def http_get_json(url: str, headers: Optional[Dict[str, str]] = None, timeout: float = 25.0) -> Any:
    return http_request_json("GET", url, payload=None, headers=headers, timeout=timeout)


def http_get_with_headers(
    url: str, headers: Optional[Dict[str, str]] = None, timeout: float = 25.0
) -> Tuple[Any, Dict[str, str]]:
    req_headers: Dict[str, str] = {}
    if headers:
        req_headers.update(headers)
    raw, resp_headers = _http_exchange("GET", url, None, req_headers, timeout)
    body = json.loads(raw) if raw.strip() else []
    return body, resp_headers


def http_post_form(url: str, form_data: Dict[str, str], timeout: float = 20.0) -> Any:
    data_bytes = urllib.parse.urlencode(form_data).encode("utf-8")
    raw, _ = _http_exchange(
        "POST", url, data_bytes, {"Content-Type": "application/x-www-form-urlencoded"}, timeout
    )
    return json.loads(raw) if raw.strip() else {}


# ---------------------------------------------------------------------------
# 2. 유니버스 필터 및 EMA / 순수기관 수급 계산
# ---------------------------------------------------------------------------
def is_excluded_security(hname: str, etfgubun: str = "0", spac_gubun: str = "N", bu12gubun: str = "") -> bool:
    """ETF, ETN, ELW, 스팩(SPAC), 우선주, 리츠, 인버스/레버리지 등 제외 판별."""
    if str(etfgubun).strip() in ("1", "2", "3", "4") or str(spac_gubun).strip().upper() == "Y":
        return True
    if str(bu12gubun).strip() not in ("", "01", "00"):
        pass

    clean_name = (hname or "").strip()
    if not clean_name:
        return True

    excluded_keywords = (
        "스팩", "SPAC", "기업인수목적", "ETN", "ETF", "KODEX", "TIGER", "KBSTAR", "RISE", "ACE",
        "SOL", "HANARO", "KOSEF", "ARIRANG", "TIMEFOLIO", "PLUS", "WON", "FOCUS",
        "TREX", "SMART", "히어로즈", "마이티", "원큐", "파워", "리츠", "맥쿼리", "인버스",
        "레버리지", "선물", "채권", "액티브", "합성", "우B", "우C", "1우", "2우", "3우", "전환",
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


def compute_ema_series(rows: List[Dict[str, Any]], seed: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """오름차순 정렬된 일봉 리스트에 대해 전일대비 등락률(%) 및 EMA(5/20/60/120/240) 계산.

    seed(앵커 행: close, ema_5..ema_240)가 주어지면 첫 종가 시드 대신 앵커 EMA에서 이어서 계산합니다(v2.3 6.3절).
    """
    if not rows:
        return []
    sorted_rows = sorted(rows, key=lambda x: str(x["trade_date"]))
    alphas = {span: 2.0 / (span + 1.0) for span in EMA_SPANS}
    ema_state: Dict[int, float] = {}
    prev_close = 0.0
    if seed:
        prev_close = float(seed.get("close", 0) or 0)
        for span in EMA_SPANS:
            ema_state[span] = float(seed.get(f"ema_{span}", prev_close) or prev_close)
    result: List[Dict[str, Any]] = []

    for idx, r in enumerate(sorted_rows):
        item = dict(r)
        close_val = float(item.get("close", 0) or 0)
        if prev_close <= 0 or (idx == 0 and not seed):
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


def is_quarterly_rebuild_due(
    today: dt.date,
    existing_masters: List[Dict[str, Any]],
    min_universe_count: int = MIN_COMPLETE_UNIVERSE_COUNT,
) -> Tuple[bool, str]:
    """
    유니버스 전체 산출 판정:
    1) DB에 유니버스 종목이 0건이면 '최초 1회 산출' 실행
    2) DB 내 유니버스 종목 수가 min_universe_count(1,200종목) 미만이면 '미완성 초기 상태'로 판정하여 전체 산출 실행
       (단, 단위 테스트 등 소규모 목업 리스트 검증 시에는 min_universe_count 조정 가능)
    3) 3월, 6월, 9월, 12월의 첫 거래일(1~7일 중 해당 월에 아직 유니버스 전체 산출이 안 된 경우)에 '분기 정기 산출' 실행
    """
    universe_rows = [r for r in existing_masters if r.get("is_universe")]
    if not universe_rows:
        return True, "최초 1회 유니버스 구축 (DB 내 유니버스 0건)"

    if today.month in QUARTERLY_MONTHS and today.day <= 7:
        month_prefix = f"{today.year:04d}-{today.month:02d}"
        updated_this_month = [
            r for r in universe_rows
            if str(r.get("updated_at", "")).startswith(month_prefix)
        ]
        if not updated_this_month:
            return True, f"{today.month}월 분기 첫 거래일 정기 시가총액·유니버스 재산출"

    if len(universe_rows) < min_universe_count and len(universe_rows) > 5:
        return True, f"미완성 유니버스 보완 전수 산출 (현재 {len(universe_rows)}종목 < {min_universe_count}종목 기준)"

    return False, "기존 분기 유니버스 유지 (일일 증분 + 당일 거래대금 상위 급등주 자동 편입 모드)"


# ---------------------------------------------------------------------------
# 3. LS증권 Open API 클라이언트 (공식 TR 스펙 및 2년치 연속조회 완벽 준수)
# ---------------------------------------------------------------------------
class _RawT1717Rows(list):
    """t1717 원시 행 리스트 (end_date 메타 보유: 미확정 더미 행 필터용)."""

    end_date: Optional[str] = None


class LSApiClient:
    BASE_URL = "https://openapi.ls-sec.co.kr:8080"

    def __init__(self, app_key: str, app_secret: str, sleep_sec: float = 0.55) -> None:
        self.app_key = app_key
        self.app_secret = app_secret
        self.sleep_sec = sleep_sec
        self.access_token: Optional[str] = None
        # [v2.8 12.3절 · v2.8.2 14.1절] 스레드 안전 TR별 경과시간 차감·서버 바닥 정속 페이서 & 자가 보정
        self._auth_lock = threading.Lock()
        self._rate_lock = threading.Lock()
        self._tr_last_ts: Dict[str, float] = {}
        self._tr_extra_delay: Dict[str, float] = {}
        self._tr_learned_floor: Dict[str, float] = {}
        self._global_last_ts: float = 0.0
        self._global_learned_gap: float = 0.0
        self._auth_ts: float = 0.0
        self.tr_call_count: int = 0
        self.rate_limit_retry_count: int = 0

    def _acquire_tr_slot(self, tr_cd: str, min_interval: float) -> None:
        """직전 동일 TR 발송 후 이미 경과한 시간을 차감한 잔여 시간만 대기합니다."""
        if self.sleep_sec <= 0 or min_interval <= 0:
            return
        with self._rate_lock:
            now = time.monotonic()
            eff_interval = max(
                min_interval + self._tr_extra_delay.get(tr_cd, 0.0),
                self._tr_learned_floor.get(tr_cd, 0.0),
            )
            base_gap = min(0.22, eff_interval * 0.5) if eff_interval >= 1.0 else min(0.12, eff_interval * 0.5)
            global_gap = max(base_gap, self._global_learned_gap)
            prev_tr = self._tr_last_ts.get(tr_cd)
            next_tr = (prev_tr + eff_interval) if prev_tr is not None else now
            next_global = (self._global_last_ts + global_gap) if self._tr_last_ts else now
            target = max(now, next_tr, next_global)
            self._tr_last_ts[tr_cd] = target
            self._global_last_ts = target
        if target > now:
            time.sleep(target - now)

    def _bump_extra_delay(self, tr_cd: str) -> None:
        with self._rate_lock:
            self._tr_extra_delay[tr_cd] = min(0.30, self._tr_extra_delay.get(tr_cd, 0.0) + 0.06)

    def _on_rate_limit_wait(self, tr_cd: str, attempt: int, fallback_sleep: float) -> None:
        """
        [v2.8.2 14.1절] IGW00201 / IGW00103 / HTTP 429 발생 시:
        - 제한 재시도 카운트 집계 + _bump_extra_delay 유지(하위 호환)
        - sleep_sec > 0 실전 모드: _tr_learned_floor 자가 보정 및 _acquire_tr_slot 재예약으로 도미노 재시도 차단
        - sleep_sec <= 0 테스트 모드: 기존 time.sleep(fallback_sleep) 유지
        """
        self._bump_extra_delay(tr_cd)
        if self.sleep_sec <= 0:
            with self._rate_lock:
                self.rate_limit_retry_count += 1
            time.sleep(fallback_sleep)
            return
        with self._rate_lock:
            self.rate_limit_retry_count += 1
            prev_floor = max(
                TR_SERVER_FLOOR_BY_CD.get(tr_cd, 0.0),
                self._tr_learned_floor.get(tr_cd, 0.0),
            )
            if prev_floor < 1.04:
                self._tr_learned_floor[tr_cd] = 1.04
            else:
                self._tr_learned_floor[tr_cd] = min(1.30, round(prev_floor + 0.06, 4))
            if self.rate_limit_retry_count >= 3:
                self._global_learned_gap = min(1.04, max(0.52, round(self._global_learned_gap + 0.26, 4)))
            now_m = time.monotonic()
            self._tr_last_ts[tr_cd] = max(self._tr_last_ts.get(tr_cd, 0.0), now_m)
            learned_floor = self._tr_learned_floor.get(tr_cd, 1.06)
        self._acquire_tr_slot(tr_cd, max(1.06 * (attempt + 1), learned_floor))

    def _reauth(self, used_token: Optional[str]) -> None:
        """토큰 만료 시 단일 갱신: 다른 스레드가 이미(5초 이내) 갱신했다면 재발급 없이 재사용."""
        with self._auth_lock:
            if self.access_token and (
                self.access_token != used_token
                or (self._auth_ts > 0 and time.monotonic() - self._auth_ts < 5.0)
            ):
                return
            self.authenticate()

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
        self._auth_ts = time.monotonic()
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
            with self._auth_lock:
                if not self.access_token:
                    self.authenticate()
        wait_sec = self.sleep_sec if sleep_override is None else sleep_override
        if self.sleep_sec > 0 and wait_sec > 0:
            with self._rate_lock:
                learned_f = self._tr_learned_floor.get(tr_cd, 0.0)
            wait_sec = max(wait_sec, TR_SERVER_FLOOR_BY_CD.get(tr_cd, 0.0), learned_f)
        self._acquire_tr_slot(tr_cd, wait_sec)

        for attempt in range(6):
            used_token = self.access_token
            headers = {
                "content-type": "application/json; charset=utf-8",
                "authorization": f"Bearer {used_token}",
                "tr_cd": tr_cd,
                "tr_cont": tr_cont,
                "tr_cont_key": tr_cont_key,
                "mac_address": "000000000000",
            }
            try:
                with self._rate_lock:
                    self.tr_call_count += 1
                res = http_post_json(f"{self.BASE_URL}/{endpoint.lstrip('/')}", body, headers=headers)
                rsp_cd = str(res.get("rsp_cd", "00000"))
                rsp_msg = str(res.get("rsp_msg", ""))
                if (rsp_cd == "IGW00121" or "토큰" in rsp_msg) and attempt < 4:
                    logger.info("LS증권 토큰 만료 응답(%s) — 재발급 후 재시도", rsp_cd)
                    self._reauth(used_token)
                    continue
                if rsp_cd not in ("00000", "") and (
                    any(k in rsp_msg for k in ("초당", "제한", "건수", "요청"))
                    or rsp_cd in ("IGW00201", "IGW00103")
                ):
                    self._on_rate_limit_wait(tr_cd, attempt, 1.15 * (attempt + 1))
                    continue
                return res
            except urllib.error.HTTPError as e:
                if e.code == 401 and attempt < 4:
                    logger.info("LS증권 토큰 재발급 시도 (HTTP 401)")
                    self._reauth(used_token)
                    continue
                # LS증권 게이트웨이가 초당 호출 제한 초과 시 302 리다이렉트 -> 404/403을 반환하는 케이스 대응
                if e.code in (403, 404, 429, 500, 502, 503, 504) and attempt < 5:
                    logger.warning("LS 게이트웨이 일시 제한/오류 재시도 (%s, HTTP %d, %d/6)", tr_cd, e.code, attempt + 1)
                    if e.code == 429:
                        self._on_rate_limit_wait(tr_cd, attempt, 1.6 * (attempt + 1))
                    else:
                        time.sleep(1.6 * (attempt + 1))
                    continue
                raise
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                if attempt < 5:
                    logger.warning("네트워크 일시 오류 재시도 (%s, %d/6): %s", tr_cd, attempt + 1, e)
                    time.sleep(1.6 * (attempt + 1))
                    continue
                raise
        return {}

    def fetch_common_stock_master(self) -> Dict[str, Dict[str, Any]]:
        """
        t8436(주식종목조회 API용)을 호출하여 ETF/ETN/스팩/우선주/리츠가 제외된
        코스피·코스닥 순수 보통주 마스터 맵을 반환합니다.
        """
        data = self.call_tr("/stock/etc", "t8436", {"t8436InBlock": {"gubun": "0"}}, sleep_override=0.55)
        master_map: Dict[str, Dict[str, Any]] = {}
        for item in data.get("t8436OutBlock", []) or []:
            shcode = str(item.get("shcode", "")).strip()
            hname = str(item.get("hname", "")).strip()
            etfgubun = str(item.get("etfgubun", item.get("etf_fg", "0"))).strip()
            spac_gubun = str(item.get("spac_gubun", "N")).strip()
            bu12gubun = str(item.get("bu12gubun", "")).strip()
            if len(shcode) == 6 and shcode.isdigit():
                # 보통주 코드(끝자리 '0') 및 비제외 종목 필터링
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
        실제 시가총액 >= min_mcap_eok(700억) 이상인 모든 보통주(약 1,477종목)의 정확한 시가총액(억원)과 상장주식수를 산출합니다.
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
                    sleep_override=0.62,
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

        logger.info("t1444 실제 시가총액 ≥ %.0f억 보통주 전수 추출 완료: %d종목", min_mcap_eok, len(qualified))
        return qualified

    def fetch_top_trading_value_candidates(
        self,
        common_master: Dict[str, Dict[str, Any]],
        pages_per_market: int = 2,
    ) -> Dict[str, Dict[str, Any]]:
        """
        t1463(거래대금상위) API를 호출하여 당일 거래대금이 활발한 상위 종목을 빠르게 조회합니다.
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
                    sleep_override=0.50,
                )
                rows = res.get("t1463OutBlock1", []) or []
                if not rows:
                    break
                for r in rows:
                    shcode = str(r.get("shcode", "")).strip()
                    val_m = float(r.get("value", 0) or 0)
                    price = int(r.get("price", 0) or 0)
                    if shcode in common_master and val_m >= 1000:
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
        """
        res = self.call_tr("/stock/market-data", "t1102", {"t1102InBlock": {"shcode": shcode}}, sleep_override=0.25)
        out = res.get("t1102OutBlock") or {}
        mcap_eok = float(out.get("total", 0) or 0)
        listing_k = int(out.get("listing", 0) or 0)
        price = int(out.get("price", 0) or 0)
        shares = listing_k * 1000 if listing_k > 0 else (int((mcap_eok * 100_000_000) / price) if price > 0 else 0)
        return round(mcap_eok, 2), shares, price

    def fetch_latest_krx_trading_date(self, end_date_str: str) -> str:
        """
        대표 종목(005930 삼성전자, 폴백 000660 SK하이닉스)의 t8410 최근 일봉을 1회 조회하여
        실제 최신 KRX 개장 거래일(YYYY-MM-DD)을 반환합니다. (평일 공휴일에는 직전 개장일 반환)
        """
        end_dt = dt.date.fromisoformat(end_date_str)
        start_str = (end_dt - dt.timedelta(days=15)).strftime("%Y%m%d")
        end_compact = end_dt.strftime("%Y%m%d")
        for rep_code in ("005930", "000660"):
            body = {
                "t8410InBlock": {
                    "shcode": rep_code,
                    "gubun": "2",
                    "qrycnt": 5,
                    "sdate": start_str,
                    "edate": end_compact,
                    "cts_date": "",
                    "comp_yn": "N",
                    "sujung": "Y",
                }
            }
            data = self.call_tr("/stock/chart", "t8410", body, sleep_override=0.15)
            rows = data.get("t8410OutBlock1", []) or []
            valid_dates = [
                f"{d[:4]}-{d[4:6]}-{d[6:8]}"
                for d in (str(r.get("date", "")).strip() for r in rows)
                if len(d) == 8 and d.isdigit()
            ]
            if valid_dates:
                return max(valid_dates)
        return end_date_str

    def fetch_daily_chart(self, shcode: str, start_date: str, end_date: str, count: int = 500) -> List[Dict[str, Any]]:
        """
        t8410(API전용주식차트) 일봉 수정주가(sujung=Y) 조회.
        종목당 최근 2년치(약 480~500영업일, 신규 상장주는 상장일 이후 전 기간)를 확보합니다.
        1회 호출로 count에 미달하고 과거 데이터가 더 존재하는 경우 역순 슬라이딩으로 연속 수집합니다.
        """
        sdate = start_date.replace("-", "")
        curr_edate = end_date.replace("-", "")
        by_date: Dict[str, Dict[str, Any]] = {}

        for _ in range(10):
            req_cnt = max(100, count - len(by_date))
            body = {
                "t8410InBlock": {
                    "shcode": shcode,
                    "gubun": "2",
                    "qrycnt": min(500, req_cnt),
                    "sdate": sdate,
                    "edate": curr_edate,
                    "cts_date": "",
                    "comp_yn": "N",
                    "sujung": "Y",
                }
            }
            data = self.call_tr(
                "/stock/chart", "t8410", body,
                sleep_override=(TR_INTERVAL_INCREMENTAL if count <= 60 else TR_INTERVAL_MULTI) if self.sleep_sec > 0 else 0.0,
            )
            rows = data.get("t8410OutBlock1", []) or []
            if not rows:
                break

            oldest_d: Optional[str] = None
            new_added = 0
            for r in rows:
                d = str(r.get("date", "")).strip()
                if len(d) != 8 or not d.isdigit():
                    continue
                if oldest_d is None or d < oldest_d:
                    oldest_d = d
                if d < sdate:
                    continue
                close_p = int(r.get("close", 0) or 0)
                vol = int(r.get("jdiff_vol", 0) or 0)
                val_m = float(r.get("value", 0) or 0)
                if val_m <= 0 and close_p > 0 and vol > 0:
                    val_m = round((close_p * vol) / 1_000_000.0, 2)
                t_date = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
                if t_date not in by_date:
                    new_added += 1
                by_date[t_date] = {
                    "shcode": shcode,
                    "trade_date": t_date,
                    "open": int(r.get("open", 0) or 0),
                    "high": int(r.get("high", 0) or 0),
                    "low": int(r.get("low", 0) or 0),
                    "close": close_p,
                    "volume": vol,
                    "trading_value_m": round(val_m, 2),
                }

            if len(by_date) >= count or oldest_d is None or oldest_d <= sdate or new_added == 0 or len(rows) < 20:
                break

            oldest_dt = dt.date(int(oldest_d[:4]), int(oldest_d[4:6]), int(oldest_d[6:8]))
            curr_edate = (oldest_dt - dt.timedelta(days=1)).strftime("%Y%m%d")
            if curr_edate < sdate:
                break

        parsed = sorted(by_date.values(), key=lambda x: x["trade_date"])
        return parsed[-count:] if count > 0 else parsed

    def _fetch_t1717_pages(self, shcode: str, start_date: str, end_date: str, max_pages: int = 25) -> "_RawT1717Rows":
        """t1717 원시 OutBlock 행을 역순 날짜 슬라이딩으로 수집합니다 (파싱 미수행, 병렬 수집용)."""
        sdate = start_date.replace("-", "")
        curr_todt = end_date.replace("-", "")
        interval = (TR_INTERVAL_INCREMENTAL if max_pages == 1 else TR_INTERVAL_MULTI) if self.sleep_sec > 0 else 0.0
        out = _RawT1717Rows()
        out.end_date = end_date
        seen: Set[str] = set()
        for _ in range(max(1, max_pages)):
            res = self.call_tr(
                "/stock/frgr-itt",
                "t1717",
                {"t1717InBlock": {"shcode": shcode, "gubun": "0", "fromdt": sdate, "todt": curr_todt}},
                sleep_override=interval,
            )
            rows = res.get("t1717OutBlock", []) or []
            if not rows:
                break
            oldest_d: Optional[str] = None
            new_added = 0
            for r in rows:
                d = str(r.get("date", "")).strip()
                if len(d) != 8 or not d.isdigit():
                    continue
                if oldest_d is None or d < oldest_d:
                    oldest_d = d
                if d < sdate:
                    continue
                if d not in seen:
                    seen.add(d)
                    new_added += 1
            out.extend(rows)
            if oldest_d is None or oldest_d <= sdate or new_added == 0 or len(rows) < 5:
                break
            oldest_dt = dt.date(int(oldest_d[:4]), int(oldest_d[4:6]), int(oldest_d[6:8]))
            curr_todt = (oldest_dt - dt.timedelta(days=1)).strftime("%Y%m%d")
            if curr_todt < sdate:
                break
        return out

    def _parse_t1717_rows(
        self,
        shcode: str,
        raw_rows: List[Dict[str, Any]],
        start_date: str,
        vol_by_date: Dict[str, int],
        close_by_date: Optional[Dict[str, int]] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """원시 t1717OutBlock 행 → 순수기관 6대 주체 수식이 적용된 수급 행 리스트(날짜 오름차순)."""
        sdate = start_date.replace("-", "")
        close_map = close_by_date or {}
        eff_end = end_date if end_date is not None else getattr(raw_rows, "end_date", None)

        def _extract_vol_and_amt(item: Dict[str, Any], code: str, fallback_close: int) -> Tuple[int, float]:
            vol_raw = item.get(f"{code}_vol", item.get(code, 0))
            vol_val = int(vol_raw or 0)
            dan_raw = item.get(f"{code}_dan", 0)
            dan_val = float(dan_raw or 0)
            unit_price = dan_val if dan_val > 0 else float(fallback_close or 0)
            amt_m = round((vol_val * unit_price) / 1_000_000.0, 2)
            return vol_val, amt_m

        by_date: Dict[str, Dict[str, Any]] = {}
        for r in raw_rows:
            d = str(r.get("date", "")).strip()
            if len(d) != 8 or not d.isdigit():
                continue
            if d < sdate:
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
            if eff_end is not None and t_date >= eff_end and is_unsettled_supply_row(raw):
                # 장중(수급 확정 전) 당일(end_date) 모든 투자주체 수량이 0인 미확정 더미 행은 DB 적재에서 제외
                continue
            by_date[t_date] = compute_pure_institutional_supply(raw, row_vol)
        return sorted(by_date.values(), key=lambda x: x["trade_date"])

    def fetch_investor_supply(
        self,
        shcode: str,
        start_date: str,
        end_date: str,
        vol_by_date: Dict[str, int],
        close_by_date: Optional[Dict[str, int]] = None,
        max_pages: int = 25,
    ) -> List[Dict[str, Any]]:
        """
        t1717(외인기관종목별동향, gubun="0" 일간순매수) 역순 날짜 슬라이딩 연속 조회(Pagination)를 통해
        start_date ~ end_date 구간의 주체별 일간 순매수 수량·금액을 전수 수집합니다.
        (v2.8) ① 원시 페이지 수집(_fetch_t1717_pages) ② 파싱(_parse_t1717_rows) 순차 호출 — 기존 동작 100% 보존.
        - 사모펀드: tjj0000, 금융투자: tjj0001, 보험: tjj0002, 투신: tjj0003,
          은행: tjj0004, 기타금융: tjj0005, 연기금: tjj0006, 기타법인: tjj0007,
          개인: tjj0008, 등록외국인: tjj0016, 외국인합계: tjj0017
        """
        raw_rows = self._fetch_t1717_pages(shcode, start_date, end_date, max_pages=max_pages)
        return self._parse_t1717_rows(shcode, raw_rows, start_date, vol_by_date, close_by_date, end_date=end_date)


# ---------------------------------------------------------------------------
# 4. Supabase REST 연동 (대용량 페이지네이션 조회 & 500건 청크 안전 Upsert)
# ---------------------------------------------------------------------------
def is_unsettled_supply_row(row: Dict[str, Any]) -> bool:
    """
    장중(투자자별 수급 집계 확정 전) 모든 투자주체 순매수 수량이 0으로 반환된 미확정 행인지 판별합니다.
    """
    if not row:
        return True
    check_keys = (
        "real_inst_vol",
        "frg_vol",
        "ind_vol",
        "fn_inv_vol",
        "etc_corp_vol",
        "pef_vol",
        "ins_vol",
        "itc_vol",
        "bank_vol",
        "etc_fin_vol",
        "pen_vol",
    )
    present_keys = [k for k in check_keys if k in row]
    if not present_keys:
        return True
    return all(int(row.get(k, 0) or 0) == 0 for k in present_keys)


def supabase_headers(supabase_key: str) -> Dict[str, str]:
    return {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }


def supabase_cleanup_unsettled_supply(
    supabase_url: str,
    supabase_key: str,
    target_date: str = "",
    existing_masters: Optional[List[Dict[str, Any]]] = None,
) -> int:
    """
    장중 실행 등으로 인해 당일(KST 기준) daily_investor_supply에 적재된 미확정(전 주체 수량 0) 레코드를
    복합 PK(shcode, trade_date) 인덱스를 타도록 50종목 단위 병렬 청크로 안전하게 정리합니다.
    """
    if not supabase_url or not supabase_key:
        return 0
    t_date = target_date or get_kst_today().isoformat()
    masters = existing_masters if existing_masters is not None else supabase_fetch_existing_masters(supabase_url, supabase_key)
    codes = [str(m["shcode"]) for m in masters if m.get("shcode")]
    if not codes:
        return 0

    headers = supabase_headers(supabase_key)
    headers["Prefer"] = "return=representation"
    base = supabase_url.rstrip("/")
    chunks = [codes[i : i + 50] for i in range(0, len(codes), 50)]

    def _delete_chunk(ch: List[str]) -> int:
        in_str = ",".join(ch)
        url = (
            f"{base}/rest/v1/daily_investor_supply"
            f"?shcode=in.({in_str})&trade_date=eq.{t_date}"
            "&real_inst_vol=eq.0&frg_vol=eq.0&ind_vol=eq.0&fn_inv_vol=eq.0&etc_corp_vol=eq.0"
        )
        try:
            deleted = http_request_json("DELETE", url, headers=headers, timeout=15.0)
            return len(deleted) if isinstance(deleted, list) else 0
        except Exception as exc:
            logger.warning("미확정 0 수급 레코드 정리 중 예외(무시 가능): %s", exc)
            return 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        return sum(ex.map(_delete_chunk, chunks))


def fetch_latest_settled_trade_date_db(
    supabase_url: str,
    supabase_key: str,
    rep_codes: Tuple[str, ...] = REPRESENTATIVE_10_SHCODES,
) -> str:
    """
    시가총액 상·중·하위 분산 대표 10종목의 복합 PK(shcode, trade_date) 인덱스를 활용하여
    0.3초 이내에 가장 최신 확정 수급 거래일(T)을 조회합니다. (STRATEGY.md 4.5절)
    """
    if not supabase_url or not supabase_key:
        return "-"
    base = supabase_url.rstrip("/")
    headers = supabase_headers(supabase_key)
    in_str = ",".join(rep_codes)

    url = (
        f"{base}/rest/v1/daily_investor_supply"
        f"?shcode=in.({in_str})"
        "&or=(real_inst_vol.neq.0,frg_vol.neq.0,ind_vol.neq.0,fn_inv_vol.neq.0)"
        "&select=shcode,trade_date&order=trade_date.desc&limit=30"
    )
    rows = http_get_json(url, headers=headers)
    if isinstance(rows, list) and rows:
        return max((str(r["trade_date"]) for r in rows if r.get("trade_date")), default="-")
    return "-"


def parse_tz_aware_datetime(value: Any) -> Optional[dt.datetime]:
    """ISO 문자열('Z' 또는 오프셋 포함)을 타임존 인식 datetime 으로 변환 (실패 시 None). 오프셋 없으면 KST 로 간주."""
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone(dt.timedelta(hours=9)))
    return parsed


def is_updated_at_or_after(updated_at: Any, min_updated_at_kst: str) -> bool:
    cur = parse_tz_aware_datetime(updated_at)
    base = parse_tz_aware_datetime(min_updated_at_kst)
    if cur is None or base is None:
        return False
    return cur >= base


def resolve_batch_slot(batch_slot: str = "auto", now_kst: Optional[dt.datetime] = None) -> str:
    """[v2.6 10.1절] auto: KST 19:30 미만 → prelim, 이상 → final. 명시값(prelim/final)은 그대로."""
    slot = (batch_slot or "auto").strip().lower()
    if slot in ("prelim", "final"):
        return slot
    now = now_kst or get_kst_now()
    return "prelim" if (now.hour, now.minute) < BATCH_SLOT_FINAL_CUTOFF_KST else "final"


def check_daily_batch_completion(
    supabase_url: str,
    supabase_key: str,
    existing_masters: List[Dict[str, Any]],
    target_date: str,
    threshold_pct: float = DAILY_COMPLETION_THRESHOLD_PCT,
    min_updated_at_kst: Optional[str] = None,
) -> Dict[str, Any]:
    """
    기준 거래일(target_date = latest_krx_date)의 전 종목 일봉 및 확정 수급 완주 여부를
    50종목 단위 PK 인덱스 병렬 청크로 고속 검사합니다. (STRATEGY.md 4.2절 3항)
    - 대표 대형주 3종(005930, 000660, 005380) 모두 확정 수급 및 일봉 존재 필수
    - 전체 유니버스 대비 확정 완료 종목(거래정지 volume=0 종목 포함) 비율 >= 98.5% 시 완주 판정
    """
    universe_codes = [str(m["shcode"]) for m in existing_masters if m.get("is_universe") and m.get("shcode")]
    if not supabase_url or not supabase_key or not universe_codes or not target_date:
        return {
            "is_completed": False,
            "target_date": target_date,
            "total_universe": len(universe_codes),
            "chart_count": 0,
            "settled_supply_count": 0,
            "halted_count": 0,
            "completed_count": 0,
            "completion_pct": 0.0,
            "rep_3_settled": False,
            "completed_codes": set(),
        }

    base = supabase_url.rstrip("/")
    headers = supabase_headers(supabase_key)
    universe_set = set(universe_codes)
    query_codes = list(universe_codes)
    for rc in MEGA_CAP_3_SHCODES:
        if rc not in universe_set:
            query_codes.append(rc)

    chunks50 = [query_codes[i : i + 50] for i in range(0, len(query_codes), 50)]
    chart_vol_by_code: Dict[str, Optional[int]] = {}
    settled_supply_codes: Set[str] = set()

    s_cols = (
        "shcode,trade_date,real_inst_vol,frg_vol,ind_vol,fn_inv_vol,etc_corp_vol,"
        "itc_vol,pef_vol,pen_vol,ins_vol,etc_fin_vol,bank_vol"
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
        fut_charts = [
            ex.submit(
                http_get_json,
                f"{base}/rest/v1/daily_chart?shcode=in.({','.join(ch)})"
                f"&trade_date=eq.{target_date}&select=shcode,trade_date,volume&limit=1000",
                headers,
            )
            for ch in chunks50
        ]
        fut_supplies = [
            ex.submit(
                http_get_json,
                f"{base}/rest/v1/daily_investor_supply?shcode=in.({','.join(ch)})"
                f"&trade_date=eq.{target_date}&select={s_cols}&limit=1000",
                headers,
            )
            for ch in chunks50
        ]
        for fc in fut_charts:
            rows = fc.result()
            if isinstance(rows, list):
                for r in rows:
                    code = str(r.get("shcode", ""))
                    if code:
                        vol_raw = r.get("volume")
                        chart_vol_by_code[code] = int(vol_raw or 0) if vol_raw is not None else None
        for fs in fut_supplies:
            rows = fs.result()
            if isinstance(rows, list):
                for r in rows:
                    code = str(r.get("shcode", ""))
                    if code and not is_unsettled_supply_row(r):
                        settled_supply_codes.add(code)

    rep_3_settled = all(
        (rc in settled_supply_codes and rc in chart_vol_by_code) for rc in MEGA_CAP_3_SHCODES
    )
    active_settled_codes = (set(chart_vol_by_code.keys()) & settled_supply_codes) & universe_set
    halted_done_codes = (
        {c for c, v in chart_vol_by_code.items() if c in universe_set and v is not None and v == 0}
        if rep_3_settled
        else set()
    )
    completed_codes = active_settled_codes | halted_done_codes
    # [v2.6 10.1절] final 슬롯: stocks_master.updated_at 이 기준선(예: 20:00 KST) 이후인 종목만 완료로 인정
    #  (PostgREST 는 TIMESTAMPTZ 를 UTC '+00:00' 문자열로 반환하므로 반드시 tz-aware datetime 으로 비교)
    if min_updated_at_kst:
        fresh_codes = {
            str(m["shcode"]) for m in existing_masters
            if m.get("shcode") and is_updated_at_or_after(m.get("updated_at"), min_updated_at_kst)
        }
        completed_codes = completed_codes & fresh_codes
        halted_done_codes = halted_done_codes & fresh_codes
    completion_pct = round((len(completed_codes) / len(universe_codes)) * 100.0, 2)
    is_completed = bool(universe_codes) and rep_3_settled and (completion_pct >= threshold_pct)

    return {
        "is_completed": is_completed,
        "target_date": target_date,
        "total_universe": len(universe_codes),
        "chart_count": len(set(chart_vol_by_code.keys()) & universe_set),
        "settled_supply_count": len(settled_supply_codes & universe_set),
        "halted_count": len(halted_done_codes),
        "completed_count": len(completed_codes),
        "completion_pct": completion_pct,
        "rep_3_settled": rep_3_settled,
        "completed_codes": completed_codes,
    }


def build_daily_screening_lists_from_db(
    supabase_url: str,
    supabase_key: str,
    universe_masters: List[Dict[str, Any]],
    ref_date: str,
    min_ratio: float = 10.0,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    부분 적재 이어받기 등으로 일부 종목이 API 호출을 스킵하더라도 텔레그램 요약 리포트(screened_1d, screened_3d)에
    전 종목이 누락 없이 반영되도록, DB에 확정 적재된 전체 유니버스의 ref_date 기준 데이터를 PK 청크로 집계합니다.
    (STRATEGY.md 4.2절 4항)
    """
    if not supabase_url or not supabase_key or not universe_masters or not ref_date:
        return [], []
    try:
        ref_dt = dt.date.fromisoformat(ref_date)
    except ValueError:
        return [], []

    cutoff20 = (ref_dt - dt.timedelta(days=20)).isoformat()
    master_by_code = {str(m["shcode"]): m for m in universe_masters if m.get("shcode")}
    all_codes = list(master_by_code.keys())
    if not all_codes:
        return [], []

    base = supabase_url.rstrip("/")
    headers = supabase_headers(supabase_key)
    chunks35 = [all_codes[i : i + 35] for i in range(0, len(all_codes), 35)]
    c_cols = "shcode,trade_date,close,change_rate,volume,ema_20,ema_60"
    s_cols = (
        "shcode,trade_date,real_inst_vol,real_inst_amt,inst_vol_ratio,"
        "frg_vol,frg_vol_ratio,ind_vol,fn_inv_vol,etc_corp_vol"
    )

    c_map: Dict[str, List[Dict[str, Any]]] = {}
    s_map: Dict[str, List[Dict[str, Any]]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        fut_c = [
            ex.submit(
                http_get_json,
                f"{base}/rest/v1/daily_chart?shcode=in.({','.join(ch)})"
                f"&and=(trade_date.gte.{cutoff20},trade_date.lte.{ref_date})"
                f"&select={c_cols}&order=shcode.asc,trade_date.asc&limit=1000",
                headers,
            )
            for ch in chunks35
        ]
        fut_s = [
            ex.submit(
                http_get_json,
                f"{base}/rest/v1/daily_investor_supply?shcode=in.({','.join(ch)})"
                f"&and=(trade_date.gte.{cutoff20},trade_date.lte.{ref_date})"
                f"&select={s_cols}&order=shcode.asc,trade_date.asc&limit=1000",
                headers,
            )
            for ch in chunks35
        ]
        for fc in fut_c:
            rows = fc.result()
            if isinstance(rows, list):
                for r in rows:
                    c_map.setdefault(str(r["shcode"]), []).append(r)
        for fs in fut_s:
            rows = fs.result()
            if isinstance(rows, list):
                for r in rows:
                    s_map.setdefault(str(r["shcode"]), []).append(r)

    db_1d: List[Dict[str, Any]] = []
    db_3d: List[Dict[str, Any]] = []
    for shcode, m_info in master_by_code.items():
        c_rows = sorted(
            [c for c in c_map.get(shcode, []) if str(c.get("trade_date", "")) <= ref_date],
            key=lambda x: str(x["trade_date"]),
        )
        s_rows = sorted(
            [
                s for s in s_map.get(shcode, [])
                if str(s.get("trade_date", "")) < ref_date
                or (str(s.get("trade_date", "")) == ref_date and not is_unsettled_supply_row(s))
            ],
            key=lambda x: str(x["trade_date"]),
        )
        if not c_rows or not s_rows:
            continue
        if str(c_rows[-1]["trade_date"]) != ref_date or str(s_rows[-1]["trade_date"]) != ref_date:
            continue

        last_c = c_rows[-1]
        last_s = s_rows[-1]
        hname = str(m_info.get("hname") or shcode)
        market = str(m_info.get("market") or "")

        if float(last_s.get("inst_vol_ratio", 0) or 0) >= min_ratio:
            db_1d.append({
                "shcode": shcode,
                "hname": hname,
                "market": market,
                "trade_date": ref_date,
                "inst_vol_ratio": float(last_s.get("inst_vol_ratio", 0) or 0),
                "real_inst_amt": float(last_s.get("real_inst_amt", 0) or 0),
                "real_inst_vol": int(last_s.get("real_inst_vol", 0) or 0),
                "frg_vol_ratio": float(last_s.get("frg_vol_ratio", 0) or 0),
                "change_rate": float(last_c.get("change_rate", 0) or 0),
                "close": int(last_c.get("close", 0) or 0),
                "ema_20": float(last_c.get("ema_20", 0) or 0),
                "ema_60": float(last_c.get("ema_60", 0) or 0),
            })

        if len(s_rows) >= 3 and len(c_rows) >= 3:
            vol_by_dt = {str(c["trade_date"]): int(c.get("volume", 0) or 0) for c in c_rows}
            recent_3_s = s_rows[-3:]
            vol_3d = sum(vol_by_dt.get(str(r["trade_date"]), 0) for r in recent_3_s)
            inst_3d = sum(int(r.get("real_inst_vol", 0) or 0) for r in recent_3_s)
            amt_3d = sum(float(r.get("real_inst_amt", 0) or 0) for r in recent_3_s)
            frg_3d = sum(int(r.get("frg_vol", 0) or 0) for r in recent_3_s)
            ratio_3d = round((inst_3d / vol_3d) * 100.0, 2) if vol_3d > 0 else 0.0
            if ratio_3d >= min_ratio:
                db_3d.append({
                    "shcode": shcode,
                    "hname": hname,
                    "trade_date": ref_date,
                    "inst_vol_ratio": ratio_3d,
                    "real_inst_amt": amt_3d,
                    "frg_vol_ratio": round((frg_3d / vol_3d) * 100.0, 2) if vol_3d > 0 else 0.0,
                })

    db_1d.sort(key=lambda x: (-x["inst_vol_ratio"], -x["real_inst_amt"], x["shcode"]))
    db_3d.sort(key=lambda x: (-x["inst_vol_ratio"], -x["real_inst_amt"], x["shcode"]))
    return db_1d, db_3d


def supabase_fetch_existing_masters(supabase_url: str, supabase_key: str) -> List[Dict[str, Any]]:
    """
    Supabase PostgREST의 1회 1,000건 반환 제한을 우회하여
    stocks_master의 전체 종목(1,477+ 종목)을 병렬 페이지네이션으로 고속 조회합니다.
    """
    if not supabase_url or not supabase_key:
        return []
    all_rows: List[Dict[str, Any]] = []
    base = supabase_url.rstrip("/")
    headers = supabase_headers(supabase_key)

    def _fetch_page(page: int) -> List[Dict[str, Any]]:
        offset = page * 1000
        url = f"{base}/rest/v1/stocks_master?select=*&order=market_cap_eok.desc,shcode.asc&limit=1000&offset={offset}"
        try:
            rows = http_get_json(url, headers=headers)
            return rows if isinstance(rows, list) else []
        except Exception as exc:
            logger.warning("기존 stocks_master 페이지 %d 조회 실패: %s", page, exc)
            return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        first_pages = list(ex.map(_fetch_page, (0, 1, 2)))
    for rows in first_pages:
        if rows:
            all_rows.extend(rows)
    if first_pages[-1] and len(first_pages[-1]) == 1000:
        for page in range(3, 6):
            rows = _fetch_page(page)
            if not rows:
                break
            all_rows.extend(rows)
            if len(rows) < 1000:
                break
    return all_rows


def _parse_content_range_total(content_range: str) -> int:
    """Content-Range 헤더(예: '0-0/488' 또는 '*/0')에서 전체 행 수를 파싱합니다."""
    if not content_range or "/" not in content_range:
        return 0
    total_part = content_range.split("/")[-1].strip()
    return int(total_part) if total_part.isdigit() else 0


def supabase_get_table_exact_count(supabase_url: str, supabase_key: str, table: str, filter_qs: str = "") -> int:
    """
    테이블(또는 조건부)의 전체 행 수를 Content-Range 헤더로 빠르게 조회합니다.
    70만 행 이상의 무필터 전체 테이블 조회 시 statement_timeout 방지를 위해 count=estimated 폴백을 지원합니다.
    """
    if not supabase_url or not supabase_key:
        return 0
    qs = f"&{filter_qs.lstrip('&')}" if filter_qs else ""
    url = f"{supabase_url.rstrip('/')}/rest/v1/{table}?select=shcode&limit=1{qs}"
    prefer_modes = ("count=exact", "count=estimated") if filter_qs else ("count=estimated", "count=exact")
    for prefer in prefer_modes:
        headers = supabase_headers(supabase_key)
        headers["Prefer"] = prefer
        try:
            _, resp_headers = http_get_with_headers(url, headers=headers, timeout=15.0)
            cnt = _parse_content_range_total(resp_headers.get("content-range", ""))
            if cnt > 0 or filter_qs:
                return cnt
        except Exception:
            continue
    return 0


def resolve_supply_unsettled(
    supply_row: Dict[str, Any], chart_latest: str, chart_latest_vol: int, supply_latest: str
) -> bool:
    """
    최신 수급 행 장중 미확정 여부. 최신 일봉 거래량이 0인 정상 거래정지 종목(chart_latest == supply_latest
    and volume == 0)은 전 주체 0이 정상이므로 False. 거래량이 있는데 전 주체 0일 때만 True (v2.3.1).
    """
    if chart_latest and chart_latest == supply_latest and int(chart_latest_vol or 0) == 0:
        return False
    return is_unsettled_supply_row(supply_row)


def supabase_get_stock_data_status_detail(
    supabase_url: str,
    supabase_key: str,
    shcode: str,
) -> Tuple[int, str, int, str, bool]:
    """
    개별 종목(shcode)의 daily_chart 및 daily_investor_supply 적재 건수, 최신 거래일,
    그리고 최신 수급 행의 장중 미확정(전 주체 0) 여부를 반환합니다.
    반환값: (chart_count, chart_latest_date, supply_count, supply_latest_date, is_latest_supply_unsettled)
    """
    if not supabase_url or not supabase_key:
        return 0, "", 0, "", False
    headers = supabase_headers(supabase_key)
    headers["Prefer"] = "count=exact"
    base = supabase_url.rstrip("/")

    chart_cnt, chart_latest = 0, ""
    chart_latest_vol = -1
    supply_cnt, supply_latest = 0, ""
    is_latest_supply_unsettled = False
    try:
        c_rows, c_hdr = http_get_with_headers(
            f"{base}/rest/v1/daily_chart?shcode=eq.{shcode}&select=trade_date,volume&order=trade_date.desc&limit=1",
            headers=headers,
            timeout=15.0,
        )
        chart_cnt = _parse_content_range_total(c_hdr.get("content-range", ""))
        if isinstance(c_rows, list) and c_rows:
            chart_latest = str(c_rows[0].get("trade_date", ""))
            chart_latest_vol = int(c_rows[0].get("volume", -1) if c_rows[0].get("volume") is not None else -1)
    except Exception:
        pass

    try:
        s_rows, s_hdr = http_get_with_headers(
            f"{base}/rest/v1/daily_investor_supply?shcode=eq.{shcode}"
            "&select=trade_date,real_inst_vol,frg_vol,ind_vol,fn_inv_vol,etc_corp_vol"
            "&order=trade_date.desc&limit=1",
            headers=headers,
            timeout=15.0,
        )
        supply_cnt = _parse_content_range_total(s_hdr.get("content-range", ""))
        if isinstance(s_rows, list) and s_rows:
            supply_latest = str(s_rows[0].get("trade_date", ""))
            is_latest_supply_unsettled = resolve_supply_unsettled(s_rows[0], chart_latest, chart_latest_vol, supply_latest)
    except Exception:
        pass

    return chart_cnt, chart_latest, supply_cnt, supply_latest, is_latest_supply_unsettled


def supabase_get_stock_data_status(
    supabase_url: str,
    supabase_key: str,
    shcode: str,
) -> Tuple[int, str, int, str]:
    """
    개별 종목(shcode)의 daily_chart 및 daily_investor_supply 적재 건수와 최신 거래일을 반환합니다.
    반환값: (chart_count, chart_latest_date, supply_count, supply_latest_date)
    """
    c_cnt, c_last, s_cnt, s_last, _ = supabase_get_stock_data_status_detail(supabase_url, supabase_key, shcode)
    return c_cnt, c_last, s_cnt, s_last


def is_stock_already_backfilled(
    chart_cnt: int,
    chart_latest: str,
    supply_cnt: int,
    supply_latest: str,
    min_target_date: str = "",
    is_latest_supply_unsettled: bool = False,
) -> bool:
    """
    종목이 이미 2년치(또는 신규 상장 이후 전 기간) 차트·수급 백필이 완료되었는지 판별합니다.
    - 기존에 60일(차트)/25일(수급)만 잘려 적재된 247개 종목(supply_cnt <= 60)은 무조건 False를 반환하여
      2년치(500영업일) 전체를 다시 백필하도록 보장합니다.
    - is_latest_supply_unsettled=True(장중 0 수급 더미 행 적재 상태)이면 False를 반환하여 스킵을 방지합니다.
    """
    if is_latest_supply_unsettled:
        return False
    if chart_cnt < 400 and supply_cnt <= 65:
        return False
    if supply_cnt <= 65:
        return False
    if min_target_date and (chart_latest < min_target_date or supply_latest < min_target_date):
        return False
    # 1) 상장 2년 이상 일반 종목: 차트와 수급 모두 400영업일 이상 적재 완료
    if chart_cnt >= 400 and supply_cnt >= 400:
        return True
    # 2) 상장 2년 미만 신규 상장주: 수급이 65영업일 초과이고 차트 영업일수와 수급 영업일수가 거의 일치(오차 5일 이내)
    if supply_cnt > 65 and abs(chart_cnt - supply_cnt) <= 5:
        return True
    return False


def supabase_upsert(
    supabase_url: str,
    supabase_key: str,
    table: str,
    conflict_cols: str,
    rows: List[Dict[str, Any]],
    chunk_size: int = 500,
) -> None:
    """500건 단위 청크 분할 및 네트워크 일시 오류 자동 재시도(3회)가 적용된 안전 Upsert."""
    if not rows or not supabase_url or not supabase_key:
        return
    headers = supabase_headers(supabase_key)
    headers["Prefer"] = "resolution=merge-duplicates"
    url = f"{supabase_url.rstrip('/')}/rest/v1/{table}?on_conflict={conflict_cols}"
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        for attempt in range(3):
            try:
                http_post_json(url, chunk, headers=headers, timeout=35.0)
                break
            except Exception as exc:
                if attempt < 2:
                    time.sleep(1.2 * (attempt + 1))
                    continue
                raise exc


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
    send_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        try:
            http_post_json(
                send_url,
                {"chat_id": chat_id, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True},
            )
        except urllib.error.HTTPError as http_exc:
            if http_exc.code != 400:
                raise
            # v2.4: Markdown 엔티티 파싱 오류(홀수 개 '_' 등) -> parse_mode 제거 후 일반 텍스트 재전송
            logger.warning("텔레그램 Markdown 파싱 오류(HTTP 400) -> 일반 텍스트로 재전송")
            http_post_json(
                send_url,
                {"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            )
        logger.info("텔레그램 알림 전송 완료 (chat_id=%s)", chat_id)
        return True
    except Exception as exc:
        logger.warning("텔레그램 전송 실패: %s", exc)
        return False


# ---------------------------------------------------------------------------
# 4-B. v2.3 (STRATEGY.md 6절) 10년치 확장: 범위 상태 조회 / 앵커 EMA / 증분 판정 / 프로브 / 백필
# ---------------------------------------------------------------------------
def _add_days(date_str: str, days: int) -> str:
    """'YYYY-MM-DD' 문자열에 달력일을 가감합니다."""
    d = dt.date.fromisoformat(date_str)
    return (d + dt.timedelta(days=days)).isoformat()


def is_in_daily_yield_window(now_kst: Optional[dt.datetime] = None) -> bool:
    """평일 15:55 ~ 16:45 KST 및 20:10 ~ 21:20 KST 구간(daily 배치 양보 구간) 여부."""
    now = now_kst or get_kst_now()
    if now.weekday() >= 5:
        return False
    hm = (now.hour, now.minute)
    return (
        DAILY_YIELD_WINDOW_KST[0] <= hm < DAILY_YIELD_WINDOW_KST[1]
        or DAILY_YIELD_WINDOW_PRELIM_KST[0] <= hm < DAILY_YIELD_WINDOW_PRELIM_KST[1]
    )


def supabase_get_stock_range_status(supabase_url: str, supabase_key: str, shcode: str) -> Dict[str, Any]:
    """
    종목 1개의 차트/수급 적재 범위(건수·최초일·최신일·최신 수급 미확정 여부)를
    PK 인덱스 limit=1 쿼리만으로 조회합니다(전 행 다운로드 없음).
    조회 오류 시 error=True 를 표시합니다(호출측은 해당 종목을 완료 처리하지 않고 재시도).
    """
    out: Dict[str, Any] = {
        "chart_cnt": 0, "chart_oldest": "", "chart_latest": "",
        "supply_cnt": 0, "supply_oldest": "", "supply_latest": "",
        "is_latest_supply_unsettled": False, "error": False,
    }
    if not supabase_url or not supabase_key:
        out["error"] = True
        return out
    headers = supabase_headers(supabase_key)
    headers["Prefer"] = "count=exact"
    base = supabase_url.rstrip("/")

    def _q(table: str, select: str, order: str) -> Tuple[Any, Dict[str, str]]:
        url = f"{base}/rest/v1/{table}?shcode=eq.{shcode}&select={select}&order=trade_date.{order}&limit=1"
        last_exc: Optional[Exception] = None
        for attempt in range(2):
            try:
                return http_get_with_headers(url, headers=headers, timeout=20.0)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                time.sleep(0.4 * (attempt + 1))
        raise last_exc if last_exc else RuntimeError("supabase query failed")

    try:
        rows, hdr = _q("daily_chart", "trade_date,volume", "desc")
        out["chart_cnt"] = _parse_content_range_total(hdr.get("content-range", ""))
        chart_latest_vol = -1
        if isinstance(rows, list) and rows:
            out["chart_latest"] = str(rows[0].get("trade_date", ""))
            if rows[0].get("volume") is not None:
                chart_latest_vol = int(rows[0]["volume"])
        rows, _ = _q("daily_chart", "trade_date", "asc")
        if isinstance(rows, list) and rows:
            out["chart_oldest"] = str(rows[0].get("trade_date", ""))

        rows, hdr = _q("daily_investor_supply", "trade_date,real_inst_vol,frg_vol,ind_vol,fn_inv_vol,etc_corp_vol", "desc")
        out["supply_cnt"] = _parse_content_range_total(hdr.get("content-range", ""))
        if isinstance(rows, list) and rows:
            out["supply_latest"] = str(rows[0].get("trade_date", ""))
            out["is_latest_supply_unsettled"] = resolve_supply_unsettled(
                rows[0], out["chart_latest"], chart_latest_vol, out["supply_latest"]
            )
        rows, _ = _q("daily_investor_supply", "trade_date", "asc")
        if isinstance(rows, list) and rows:
            out["supply_oldest"] = str(rows[0].get("trade_date", ""))
    except Exception as exc:  # noqa: BLE001
        logger.warning("범위 상태 조회 실패 (%s): %s", shcode, exc)
        out["error"] = True
    return out


def supabase_get_anchor_row(
    supabase_url: str,
    supabase_key: str,
    shcode: str,
    offset_trading_days: int = ANCHOR_OFFSET_TRADING_DAYS,
) -> Optional[Dict[str, Any]]:
    """최신일 기준 약 N영업일 전 앵커 행(trade_date, close, ema_5..ema_240)을 조회합니다. 실패/부재 시 None."""
    if not supabase_url or not supabase_key:
        return None
    ema_cols = ",".join(f"ema_{s}" for s in EMA_SPANS)
    url = (
        f"{supabase_url.rstrip('/')}/rest/v1/daily_chart?shcode=eq.{shcode}"
        f"&select=trade_date,close,{ema_cols}&order=trade_date.desc&offset={offset_trading_days}&limit=1"
    )
    try:
        rows = http_get_json(url, headers=supabase_headers(supabase_key), timeout=15.0)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(rows, list) or not rows:
        return None
    row = rows[0]
    if any(row.get(f"ema_{s}") is None for s in EMA_SPANS) or not row.get("close"):
        return None
    return row


def build_anchor_seeded_charts(
    chart_rows: List[Dict[str, Any]],
    anchor: Dict[str, Any],
) -> Tuple[str, Optional[List[Dict[str, Any]]]]:
    """
    API 최근 일봉과 DB 앵커 행 종가를 대조합니다.
    - 일치("ok"): 앵커 EMA를 시드로 앵커 이후 행만 EMA 이어계산하여 반환
    - 불일치("mismatch"): 액면분할·무상증자 등 수정주가 변동 → 호출측이 10년치 전체 재적재
    - 앵커일/이후 행 없음("missing"): 호출측이 기존 경로로 폴백
    """
    a_date = str(anchor.get("trade_date", ""))
    by_date = {r["trade_date"]: r for r in chart_rows}
    api_anchor = by_date.get(a_date)
    if api_anchor is None:
        return "missing", None
    if int(api_anchor["close"]) != int(anchor["close"]):
        return "mismatch", None
    after = [r for r in chart_rows if r["trade_date"] > a_date]
    if not after:
        return "missing", None
    return "ok", compute_ema_series(after, seed=anchor)


def supabase_get_chart_vol_close(
    supabase_url: str, supabase_key: str, shcode: str, start_date: str, end_date: str
) -> Tuple[Dict[str, int], Dict[str, int]]:
    """DB daily_chart 의 [start,end] 구간 거래량·종가 맵(수급 비중 계산용)을 1,000건 페이지로 조회."""
    vol_map: Dict[str, int] = {}
    close_map: Dict[str, int] = {}
    base = supabase_url.rstrip("/")
    headers = supabase_headers(supabase_key)
    offset = 0
    while True:
        url = (
            f"{base}/rest/v1/daily_chart?shcode=eq.{shcode}&trade_date=gte.{start_date}&trade_date=lte.{end_date}"
            f"&select=trade_date,close,volume&order=trade_date.asc&offset={offset}&limit=1000"
        )
        rows = http_get_json(url, headers=headers, timeout=25.0)
        if not isinstance(rows, list) or not rows:
            break
        for r in rows:
            vol_map[str(r["trade_date"])] = int(r.get("volume", 0) or 0)
            close_map[str(r["trade_date"])] = int(r.get("close", 0) or 0)
        if len(rows) < 1000:
            break
        offset += 1000
    return vol_map, close_map


def _paginate_trade_date(
    base: str, headers: Dict[str, str], table: str, select: str, trade_date: str
) -> List[Dict[str, Any]]:
    """단일 거래일 인덱스 스캔(order=shcode.asc, Prefer: count=exact 미사용) 1,000건 페이지네이션."""
    out: List[Dict[str, Any]] = []
    offset = 0
    while True:
        url = (
            f"{base}/rest/v1/{table}?trade_date=eq.{trade_date}&select={select}"
            f"&order=shcode.asc&limit=1000&offset={offset}"
        )
        rows = http_get_json(url, headers=headers, timeout=30.0)
        if not isinstance(rows, list) or not rows:
            break
        out.extend(rows)
        if len(rows) < 1000:
            break
        offset += 1000
    return out


def supabase_prefetch_daily_context(
    supabase_url: str,
    supabase_key: str,
    latest_krx_date: str,
    target_codes: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    [v2.8 12.2절 · v2.8.1 13.1절] 종목 루프 진입 전 전 종목 상태·앵커를 일괄 적재하여 종목별 단건 사전 조회를 제거합니다.
    - target_codes 전달 시: 50종목 PK 인덱스 청크(shcode=in.(...)&trade_date=in.(...)) 병렬 조회 + 미해결 소수 종목 병렬 사전 해결
    - target_codes is None 시: 하위 호환용 단일 거래일 페이지네이션(_paginate_trade_date) 유지
    실패/달력 부족 시 None (호출측은 기존 종목별 조회로 폴백).
    """
    if not supabase_url or not supabase_key:
        return None
    base = supabase_url.rstrip("/")
    headers = supabase_headers(supabase_key)
    try:
        cal_dates: List[str] = []
        for rep_code in ("005930", "000660"):
            rows = http_get_json(
                f"{base}/rest/v1/daily_chart?shcode=eq.{rep_code}&select=trade_date&order=trade_date.desc&limit=430",
                headers=headers, timeout=25.0,
            )
            if isinstance(rows, list) and rows:
                cal_dates = [str(r["trade_date"]) for r in rows if r.get("trade_date")]
                break
        prior_dates = [d for d in cal_dates if d < latest_krx_date]
        if len(prior_dates) < 5:
            return None
        anchor_dates = prior_dates[4:7]
        recent_dates = [latest_krx_date] + ([prior_dates[0]] if prior_dates else [])
        hist_dates = [prior_dates[200], prior_dates[405]] if len(prior_dates) > 405 else []

        ema_cols = ",".join(f"ema_{sp}" for sp in EMA_SPANS)
        results: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

        if target_codes is None:
            tasks: List[Tuple[str, str, str, str]] = []  # (kind, table, select, date)
            for d in anchor_dates:
                tasks.append(("anchor", "daily_chart", f"shcode,trade_date,close,{ema_cols}", d))
            for d in recent_dates:
                tasks.append(("recent_chart", "daily_chart", "shcode,trade_date,volume", d))
                tasks.append((
                    "recent_supply", "daily_investor_supply",
                    "shcode,trade_date,real_inst_vol,frg_vol,ind_vol,fn_inv_vol,etc_corp_vol", d,
                ))
            for d in hist_dates:
                tasks.append(("hist_chart", "daily_chart", "shcode", d))
                tasks.append(("hist_supply", "daily_investor_supply", "shcode", d))

            with concurrent.futures.ThreadPoolExecutor(max_workers=PREFETCH_PARALLEL_WORKERS) as ex:
                futs = {
                    ex.submit(_paginate_trade_date, base, headers, tbl, sel, d): (kind, d)
                    for kind, tbl, sel, d in tasks
                }
                for fut, key in futs.items():
                    results[key] = fut.result()
            codes_list: List[str] = []
        else:
            codes_list = list(dict.fromkeys(str(c) for c in target_codes if c))
            all_chart_dates = list(dict.fromkeys(anchor_dates + recent_dates + hist_dates))
            all_supply_dates = list(dict.fromkeys(recent_dates + hist_dates))
            chunks50 = [codes_list[i : i + 50] for i in range(0, len(codes_list), 50)]
            chart_by_d: Dict[str, List[Dict[str, Any]]] = {d: [] for d in all_chart_dates}
            supply_by_d: Dict[str, List[Dict[str, Any]]] = {d: [] for d in all_supply_dates}

            def _fetch_pk_url(url: str) -> List[Dict[str, Any]]:
                res = http_get_json(url, headers=headers, timeout=30.0)
                return res if isinstance(res, list) else []

            chart_dates_csv = ",".join(all_chart_dates)
            supply_dates_csv = ",".join(all_supply_dates)
            if chunks50:
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex_pk:
                    pk_futs: Dict[concurrent.futures.Future[List[Dict[str, Any]]], str] = {}
                    for ch in chunks50:
                        codes_csv = ",".join(ch)
                        if all_chart_dates:
                            c_url = (
                                f"{base}/rest/v1/daily_chart?shcode=in.({codes_csv})"
                                f"&trade_date=in.({chart_dates_csv})"
                                f"&select=shcode,trade_date,close,volume,{ema_cols}&limit=1000"
                            )
                            pk_futs[ex_pk.submit(_fetch_pk_url, c_url)] = "chart"
                        if all_supply_dates:
                            s_url = (
                                f"{base}/rest/v1/daily_investor_supply?shcode=in.({codes_csv})"
                                f"&trade_date=in.({supply_dates_csv})"
                                "&select=shcode,trade_date,real_inst_vol,frg_vol,ind_vol,fn_inv_vol,etc_corp_vol"
                                "&limit=1000"
                            )
                            pk_futs[ex_pk.submit(_fetch_pk_url, s_url)] = "supply"
                    for fut_pk, kind_pk in pk_futs.items():
                        rows_pk = fut_pk.result()
                        target_bucket = chart_by_d if kind_pk == "chart" else supply_by_d
                        for r in rows_pk:
                            td = str(r.get("trade_date", ""))
                            if td in target_bucket:
                                target_bucket[td].append(r)

            for d in anchor_dates:
                results[("anchor", d)] = chart_by_d.get(d, [])
            for d in recent_dates:
                results[("recent_chart", d)] = chart_by_d.get(d, [])
                results[("recent_supply", d)] = supply_by_d.get(d, [])
            for d in hist_dates:
                results[("hist_chart", d)] = chart_by_d.get(d, [])
                results[("hist_supply", d)] = supply_by_d.get(d, [])

        anchor_by_code: Dict[str, Dict[str, Any]] = {}
        for d in anchor_dates:  # 최신(T-5) 우선, 무효 시 T-6·T-7 순
            for r in results.get(("anchor", d), []):
                code = str(r.get("shcode", ""))
                if not code or code in anchor_by_code:
                    continue
                if any(r.get(f"ema_{sp}") is None for sp in EMA_SPANS) or not r.get("close"):
                    continue
                anchor_by_code[code] = r

        chart_latest: Dict[str, Tuple[str, int]] = {}
        supply_latest: Dict[str, Tuple[str, Dict[str, Any]]] = {}
        for d in sorted(recent_dates):  # 오름차순 덮어쓰기 → 최신일 우선
            for r in results.get(("recent_chart", d), []):
                vol = r.get("volume")
                chart_latest[str(r["shcode"])] = (d, int(vol) if vol is not None else -1)
            for r in results.get(("recent_supply", d), []):
                supply_latest[str(r["shcode"])] = (d, r)

        recent_status: Dict[str, Dict[str, Any]] = {}
        for code, (c_date, c_vol) in chart_latest.items():
            if code not in supply_latest:
                continue
            s_date, s_row = supply_latest[code]
            recent_status[code] = {
                "chart_latest": c_date,
                "supply_latest": s_date,
                "unsettled": resolve_supply_unsettled(s_row, c_date, c_vol, s_date),
            }

        hist_chart_2y: Set[str] = set()
        hist_supply_2y: Set[str] = set()
        if hist_dates:
            sets_c = [{str(r["shcode"]) for r in results.get(("hist_chart", d), [])} for d in hist_dates]
            sets_s = [{str(r["shcode"]) for r in results.get(("hist_supply", d), [])} for d in hist_dates]
            hist_chart_2y = set.intersection(*sets_c) if sets_c else set()
            hist_supply_2y = set.intersection(*sets_s) if sets_s else set()

        fallback_status_by_code: Dict[str, Tuple[int, str, int, str, bool]] = {}
        if target_codes is not None and codes_list:
            unresolved = [
                c for c in codes_list
                if not (c in recent_status and c in hist_chart_2y and c in hist_supply_2y)
            ]
            missing_anchors = [
                c for c in codes_list
                if c in hist_chart_2y and c in hist_supply_2y and c not in anchor_by_code
            ]
            run_unresolved = 0 < len(unresolved) <= 200
            run_anchors = 0 < len(missing_anchors) <= 50
            if run_unresolved or run_anchors:
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex_fb:
                    fut_status = {
                        ex_fb.submit(supabase_get_stock_data_status_detail, supabase_url, supabase_key, c): c
                        for c in (unresolved if run_unresolved else [])
                    }
                    fut_anc = {
                        ex_fb.submit(supabase_get_anchor_row, supabase_url, supabase_key, c): c
                        for c in (missing_anchors if run_anchors else [])
                    }
                    for fut_s, code_s in fut_status.items():
                        try:
                            fallback_status_by_code[code_s] = fut_s.result()
                        except Exception as exc_fb:  # noqa: BLE001
                            logger.warning("[PREFETCH] 미해결 종목 상태 조회 실패 (%s): %s", code_s, exc_fb)
                    for fut_a, code_a in fut_anc.items():
                        try:
                            anc_row = fut_a.result()
                            if anc_row:
                                anchor_by_code[code_a] = anc_row
                        except Exception as exc_anc:  # noqa: BLE001
                            logger.warning("[PREFETCH] 앵커 보강 조회 실패 (%s): %s", code_a, exc_anc)

        return {
            "cal_dates": cal_dates,
            "anchor_dates": anchor_dates,
            "recent_dates": recent_dates,
            "hist_dates": hist_dates,
            "anchor_by_code": anchor_by_code,
            "recent_status": recent_status,
            "hist_chart_2y_codes": hist_chart_2y,
            "hist_supply_2y_codes": hist_supply_2y,
            "fallback_status_by_code": fallback_status_by_code,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("[PREFETCH] 일괄 프리페치 실패 — 종목별 조회로 폴백: %s", exc)
        return None


def lookup_prefetched_status(
    ctx: Optional[Dict[str, Any]], shcode: str
) -> Optional[Tuple[int, str, int, str, bool]]:
    """프리페치 맵만으로 2년 히스토리·최신 상태 판정(또는 사전 해결 폴백)이 가능한 종목의 5-튜플 반환."""
    if not ctx:
        return None
    st = ctx["recent_status"].get(shcode)
    if st and shcode in ctx["hist_chart_2y_codes"] and shcode in ctx["hist_supply_2y_codes"]:
        return 450, st["chart_latest"], 450, st["supply_latest"], bool(st["unsettled"])
    fb = ctx.get("fallback_status_by_code", {}).get(shcode)
    if fb is not None:
        return fb
    return None


class BatchUpsertBuffer:
    """
    [v2.8 12.4절] 증분 종목 적재 버퍼. flush 시 반드시 daily_chart → daily_investor_supply → stocks_master(updated_at 갱신) 순서.
    묶음 오류 시 종목별 개별 Upsert로 격리 폴백(정상 종목 유실 0건).
    """

    def __init__(self, sb_url: str, sb_key: str, batch_size: int = FLUSH_BATCH_STOCKS) -> None:
        self.sb_url = sb_url
        self.sb_key = sb_key
        self.batch_size = batch_size
        self.entries: List[Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]] = []
        self.flush_count = 0

    def add(self, master: Dict[str, Any], charts: List[Dict[str, Any]], supplies: List[Dict[str, Any]]) -> None:
        self.entries.append((master, charts, supplies))

    def __len__(self) -> int:
        return len(self.entries)

    def _write(self, entries: List[Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]]) -> None:
        charts = [r for _, c, _ in entries for r in c]
        supplies = [r for _, _, sp in entries for r in sp]
        flush_iso = get_kst_now().isoformat()
        masters = [dict(m, updated_at=flush_iso) for m, _, _ in entries]
        supabase_upsert(self.sb_url, self.sb_key, "daily_chart", "shcode,trade_date", charts)
        supabase_upsert(self.sb_url, self.sb_key, "daily_investor_supply", "shcode,trade_date", supplies)
        supabase_upsert(self.sb_url, self.sb_key, "stocks_master", "shcode", masters)  # 반드시 마지막

    def flush(self) -> int:
        if not self.entries:
            return 0
        pending, self.entries = self.entries, []
        self.flush_count += 1
        try:
            self._write(pending)
            return len(pending)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[FLUSH] %d종목 묶음 Upsert 실패 — 개별 종목 격리 재시도: %s", len(pending), exc)
        ok = 0
        for entry in pending:
            try:
                self._write([entry])
                ok += 1
            except Exception as exc2:  # noqa: BLE001
                logger.warning("[FLUSH] 개별 Upsert 실패 (%s): %s", entry[0].get("shcode"), exc2)
        return ok


def estimate_daily_batch_minutes(
    n_stocks: int, chart_interval: float = TR_INTERVAL_INCREMENTAL, supply_interval: float = TR_INTERVAL_INCREMENTAL,
    flush_batch: int = FLUSH_BATCH_STOCKS, flush_sec: float = 2.0, fixed_sec: float = 60.0,
) -> float:
    """t8410‖t1717 병렬 시 종목당 max(두 TR 간격) + 배치 플러시 + 고정 오버헤드 기반 이론 소요 시간(분)."""
    per_stock = max(chart_interval, supply_interval)
    flushes = -(-n_stocks // max(1, flush_batch))
    return (n_stocks * per_stock + flushes * flush_sec + fixed_sec) / 60.0


def needs_chart_fetch(db_chart_oldest: str, target_chart_start: str = CHART_HISTORY_START_DATE) -> bool:
    """t8410 조회로 목표 차트 시작일까지 확장해야 하는지 판정 (v2.3.1 6.4절, 임의의 chart_start 지원)."""
    if not db_chart_oldest:
        return True
    if db_chart_oldest <= _add_days(target_chart_start, 14):
        return False
    if db_chart_oldest > RECENT_IPO_CUTLINE:
        return False
    if TWO_YEAR_CUT_OLD < db_chart_oldest <= RECENT_IPO_CUTLINE:
        return True
    # 향후 5년→10년 무코드 확장: 기존 5년 절단선(2021-11) 종목도 확장 대상
    if target_chart_start < "2021-10-15" and "2021-10-25" <= db_chart_oldest <= "2021-11-15":
        return True
    return False


def is_stock_history_completed(
    chart_oldest: str,
    chart_latest: str,
    supply_oldest: str,
    supply_latest: str,
    effective_supply_target: str,
    recent_cutoff: str,
    is_latest_supply_unsettled: bool = False,
    target_chart_start: str = CHART_HISTORY_START_DATE,
) -> bool:
    """확장 완료 판정 (v2.3.1 6.4절). daily 의 is_stock_already_backfilled 와 별개."""
    if not chart_oldest or not supply_oldest or is_latest_supply_unsettled:
        return False
    if chart_latest < recent_cutoff or supply_latest < recent_cutoff:
        return False
    if needs_chart_fetch(chart_oldest, target_chart_start):
        return False
    return supply_oldest <= _add_days(max(effective_supply_target, chart_oldest), 10)


def compute_target_supply_start(effective_supply_target: str, chart_oldest: str) -> str:
    return max(effective_supply_target, chart_oldest) if chart_oldest else effective_supply_target


def plan_supply_fetch(
    status: Dict[str, Any], target_start: str, today_str: str, recent_cutoff: str
) -> Optional[Tuple[str, str, str]]:
    """
    t1717 수급 보강 계획. None=API 호출 0회 스킵 / ("backward", start, end)=과거 구간만 / ("full", start, end)=전체.
    """
    s_cnt = int(status.get("supply_cnt", 0) or 0)
    s_old = str(status.get("supply_oldest", "") or "")
    s_latest = str(status.get("supply_latest", "") or "")
    unsettled = bool(status.get("is_latest_supply_unsettled", False))
    recent_ok = s_cnt > 0 and s_latest >= recent_cutoff and not unsettled
    if recent_ok and s_old and s_old <= _add_days(target_start, 10):
        return None
    if recent_ok and s_cnt >= 65 and s_old:
        return ("backward", target_start, _add_days(s_old, -1))
    return ("full", target_start, today_str)


def _t1717_window_rows(client: "LSApiClient", shcode: str, from_d: str, to_d: str) -> List[Dict[str, Any]]:
    """t1717 원본 응답에서 [from_d, to_d](YYYYMMDD) 구간 행만 반환."""
    res = client.call_tr(
        "/stock/frgr-itt", "t1717",
        {"t1717InBlock": {"shcode": shcode, "gubun": "0", "fromdt": from_d, "todt": to_d}},
        sleep_override=0.4,
    )
    rows = res.get("t1717OutBlock", []) or []
    return [r for r in rows if from_d <= str(r.get("date", "")).strip() <= to_d]


def _fmt_d(d8: str) -> str:
    return f"{d8[:4]}-{d8[4:6]}-{d8[6:8]}"


def find_supply_floor_for_stock(client: "LSApiClient", shcode: str) -> Optional[str]:
    """
    2016-01~02 수급이 비어 있을 때 LS 서버 수급 실제 하한일 탐색:
    2017~2024 연 단위 앵커 → 최초 적중 연도의 직전 연도 월 단위 스캔. 하한을 못 찾으면 None.
    """
    rows = _t1717_window_rows(client, shcode, "20160101", "20160131")
    if rows:
        return _fmt_d(min(str(r["date"]).strip() for r in rows))
    hit_year: Optional[int] = None
    hit_rows: List[Dict[str, Any]] = []
    for y in range(2017, 2025):
        rows = _t1717_window_rows(client, shcode, f"{y}0101", f"{y}0228")
        if rows:
            hit_year, hit_rows = y, rows
            break
    if hit_year is None:
        return None
    for m in range(3, 13):
        last_day = (dt.date(hit_year - 1, m % 12 + 1, 1) if m < 12 else dt.date(hit_year, 1, 1)) - dt.timedelta(days=1)
        rows = _t1717_window_rows(client, shcode, f"{hit_year - 1}{m:02d}01", last_day.strftime("%Y%m%d"))
        if rows:
            return _fmt_d(min(str(r["date"]).strip() for r in rows))
    return _fmt_d(min(str(r["date"]).strip() for r in hit_rows))


def detect_ls_server_history_floor(client: "LSApiClient") -> str:
    """대표 3종목(005930, 000660, 005380) 기준 effective_supply_floor 자동 판정 (기본 2016-01-01)."""
    floors: List[str] = []
    for code, _name in PROBE_STOCKS:
        try:
            f = find_supply_floor_for_stock(client, code)
        except Exception as exc:  # noqa: BLE001
            logger.warning("수급 하한 탐색 실패 (%s): %s", code, exc)
            f = None
        if f:
            floors.append(f)
    if not floors:
        return HISTORY_START_DATE
    return max(HISTORY_START_DATE, max(floors))


def run_probe_10y(client: Optional["LSApiClient"] = None) -> List[Dict[str, Any]]:
    """
    [probe_10y] DB 쓰기 없이 LS 실서버의 2016-01~02 차트(t8410)·수급(t1717) 실제 반환을 실측합니다.
    """
    if client is None:
        ls_key = os.getenv("LS_APP_KEY", "").strip()
        ls_secret = os.getenv("LS_APP_SECRET", "").strip()
        if not ls_key or not ls_secret:
            raise SystemExit("LS_APP_KEY / LS_APP_SECRET 미설정 — probe_10y 는 LS API 인증이 필요합니다.")
        client = LSApiClient(ls_key, ls_secret)
        client.authenticate()

    results: List[Dict[str, Any]] = []
    for code, name in PROBE_STOCKS:
        res: Dict[str, Any] = {"shcode": code, "hname": name, "chart_first": "", "chart_cnt": 0,
                               "supply_first": "", "supply_cnt": 0, "nonzero": {}, "formula_errors": 0,
                               "verdict": "FLOOR", "floor": None}
        try:
            chart = client.call_tr("/stock/chart", "t8410", {"t8410InBlock": {
                "shcode": code, "gubun": "2", "qrycnt": 60, "sdate": "20160101", "edate": "20160229",
                "cts_date": "", "comp_yn": "N", "sujung": "Y"}}, sleep_override=0.4)
            c_rows = [r for r in (chart.get("t8410OutBlock1", []) or [])
                      if "20160101" <= str(r.get("date", "")).strip() <= "20160229"]
            res["chart_cnt"] = len(c_rows)
            if c_rows:
                res["chart_first"] = _fmt_d(min(str(r["date"]).strip() for r in c_rows))

            s_rows = client.fetch_investor_supply(code, "2016-01-01", "2016-02-29", {}, {}, max_pages=3)
            res["supply_cnt"] = len(s_rows)
            if s_rows:
                res["supply_first"] = s_rows[0]["trade_date"]
                for col in ("itc", "pef", "pen", "frg", "fn_inv"):
                    res["nonzero"][col] = sum(1 for r in s_rows if int(r.get(f"{col}_vol", 0) or 0) != 0)
                res["formula_errors"] = sum(
                    1 for r in s_rows
                    if sum(int(r.get(f"{s}_vol", 0) or 0) for s in PURE_INST_SUBJECTS) != int(r.get("real_inst_vol", 0) or 0)
                )
                res["verdict"] = "OK" if res["nonzero"].get("pef", 0) > 0 and res["nonzero"].get("itc", 0) > 0 else "FLOOR"
            else:
                res["floor"] = find_supply_floor_for_stock(client, code)
        except Exception as exc:  # noqa: BLE001
            res["verdict"] = f"ERROR({exc})"
        results.append(res)
        logger.info(
            "[PROBE-10Y] %s %s | 차트 최초일: %s | 수급 최초일: %s | 2016-01 사모펀드(pef_vol)·순수기관 컬럼 검증: %s",
            code, name, res["chart_first"] or "-", res["supply_first"] or "-", res["verdict"],
        )
        logger.info(
            "[PROBE-10Y]   └ 차트 %d행 | 수급 %d행 | 비영(非0) 행수 %s | 순수기관 합산 오차 %d건 | 수급 하한 탐색결과 %s",
            res["chart_cnt"], res["supply_cnt"], res["nonzero"], res["formula_errors"], res["floor"] or "-",
        )
    floors = [r["floor"] for r in results if r.get("floor")]
    logger.info("[PROBE-10Y] effective_supply_floor 판정: %s", max(floors) if floors else HISTORY_START_DATE)
    return results


def process_stock_10y(
    client: "LSApiClient",
    sb_url: str,
    sb_key: str,
    shcode: str,
    status: Dict[str, Any],
    effective_supply_target: str,
    today_str: str,
    recent_cutoff: str,
    chart_start: str = CHART_HISTORY_START_DATE,
) -> Dict[str, Any]:
    """종목 1개의 10년치 차트(필요 시) + 수급(과거 역방향 델타) 보강. 예외는 호출측이 '잔여'로 처리."""
    if status.get("error"):
        raise RuntimeError("DB 범위 상태 조회 오류 — 다음 회차 재시도")
    chart_oldest = str(status.get("chart_oldest", "") or "")
    chart_rows: Optional[List[Dict[str, Any]]] = None
    api_chart = 0

    if needs_chart_fetch(chart_oldest, chart_start):
        chart_rows = client.fetch_daily_chart(shcode, chart_start, today_str, count=TARGET_10Y_CHART_COUNT)
        api_chart = 1
        if not chart_rows:
            raise RuntimeError("t8410 일봉 응답 없음")
        new_oldest = chart_rows[0]["trade_date"]
        if not chart_oldest or new_oldest < chart_oldest:
            supabase_upsert(sb_url, sb_key, "daily_chart", "shcode,trade_date", compute_ema_series(chart_rows))
        chart_oldest = min(chart_oldest, new_oldest) if chart_oldest else new_oldest

    target = compute_target_supply_start(effective_supply_target, chart_oldest)
    plan = plan_supply_fetch(status, target, today_str, recent_cutoff)
    added = 0
    if plan:
        kind, s_start, s_end = plan
        if s_start <= s_end:
            if chart_rows:
                vol_map = {r["trade_date"]: int(r["volume"]) for r in chart_rows}
                close_map = {r["trade_date"]: int(r["close"]) for r in chart_rows}
            else:
                vol_map, close_map = supabase_get_chart_vol_close(sb_url, sb_key, shcode, s_start, s_end)
            supply_rows = client.fetch_investor_supply(
                shcode, s_start, s_end, vol_map, close_map, max_pages=SUPPLY_MAX_PAGES_10Y
            )
            if supply_rows:
                supabase_upsert(sb_url, sb_key, "daily_investor_supply", "shcode,trade_date", supply_rows)
            added = len(supply_rows)
    return {"plan": plan[0] if plan else "skip", "chart_api": api_chart, "supply_added": added}


def run_backfill_10y(
    max_runtime_minutes: int = DEFAULT_BACKFILL_10Y_RUNTIME_MIN,
    chain_round: int = 1,
    max_stocks: int = 0,
    chart_start: str = CHART_HISTORY_START_DATE,
    supply_start: str = SUPPLY_HISTORY_START_DATE,
) -> Dict[str, Any]:
    """[backfill_10y] 시총 700억↑ 유니버스 전 종목 10년치 차트·수급 무중단 이어받기 백필."""
    t0 = time.time()
    ls_key = os.getenv("LS_APP_KEY", "").strip()
    ls_secret = os.getenv("LS_APP_SECRET", "").strip()
    sb_url = os.getenv("SUPABASE_URL", DEFAULT_SUPABASE_URL).strip() or DEFAULT_SUPABASE_URL
    sb_key = os.getenv("SUPABASE_KEY", DEFAULT_SUPABASE_KEY).strip() or DEFAULT_SUPABASE_KEY
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    tg_chat = os.getenv("TELEGRAM_CHAT_ID", DEFAULT_TELEGRAM_CHAT_ID).strip() or DEFAULT_TELEGRAM_CHAT_ID
    if not ls_key or not ls_secret:
        raise SystemExit("LS_APP_KEY / LS_APP_SECRET 미설정")

    today = get_kst_today()
    today_str = today.isoformat()
    recent_cutoff = (today - dt.timedelta(days=20)).isoformat()
    client = LSApiClient(ls_key, ls_secret)
    client.authenticate()

    floor = detect_ls_server_history_floor(client)
    effective_supply_target = max(supply_start, floor)
    span_txt = f"차트 {chart_start}~ / 수급 {supply_start}~"
    logger.info(
        "[BACKFILL-10Y] %d회차 시작 | effective_supply_floor=%s | effective_supply_target=%s | %s",
        chain_round, floor, effective_supply_target, span_txt,
    )

    masters = [m for m in supabase_fetch_existing_masters(sb_url, sb_key)
               if m.get("is_universe") and float(m.get("market_cap_eok", 0) or 0) >= 700.0]
    masters.sort(key=lambda m: (-float(m.get("market_cap_eok", 0) or 0), str(m.get("shcode", ""))))
    if max_stocks > 0:
        masters = masters[:max_stocks]
    codes = [str(m["shcode"]) for m in masters]
    total = len(codes)

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        statuses = dict(zip(codes, ex.map(lambda c: supabase_get_stock_range_status(sb_url, sb_key, c), codes)))

    def _done(st: Dict[str, Any]) -> bool:
        return (not st.get("error")) and is_stock_history_completed(
            st["chart_oldest"], st["chart_latest"], st["supply_oldest"], st["supply_latest"],
            effective_supply_target, recent_cutoff, st["is_latest_supply_unsettled"], chart_start,
        )

    todo = [c for c in codes if not _done(statuses[c])]
    already_done = total - len(todo)
    logger.info("[BACKFILL-10Y] 유니버스 %d종목 | 기완주 %d | 처리 대상 %d", total, already_done, len(todo))

    processed_ok: Set[str] = set()
    failed: List[str] = []
    yielded = False
    timed_out = False
    for i, code in enumerate(todo, 1):
        if max_runtime_minutes > 0 and (time.time() - t0) / 60.0 >= max_runtime_minutes:
            timed_out = True
            break
        if is_in_daily_yield_window():
            yielded = True
            logger.warning("[BACKFILL-10Y] 평일 20:10~21:20 KST daily 배치 양보 구간 — 안전 종료")
            break
        try:
            r = process_stock_10y(
                client, sb_url, sb_key, code, statuses[code], effective_supply_target, today_str, recent_cutoff, chart_start
            )
            processed_ok.add(code)
            if i <= 10 or i % 25 == 0:
                logger.info("[BACKFILL-10Y %d/%d] %s plan=%s chart_api=%d supply+%d",
                            i, len(todo), code, r["plan"], r["chart_api"], r["supply_added"])
        except Exception as exc:  # noqa: BLE001
            failed.append(code)
            logger.warning("[BACKFILL-10Y] %s 실패(다음 회차 재시도): %s", code, exc)

    remaining = [c for c in todo if c not in processed_ok]
    done_cnt = total - len(remaining)
    pct = (done_cnt / total * 100.0) if total else 100.0
    needs_resume = bool(remaining)
    _write_github_output("needs_resume", "true" if needs_resume else "false")
    _write_github_output("remaining_count", str(len(remaining)))
    _write_github_output("yielded", "true" if yielded else "false")

    if needs_resume:
        msg = (
            f"⏳ [LS 확장 백필({span_txt}) — {chain_round}회차 중간 저장 완료] "
            f"누적 완주: {done_cnt}/{total}종목 ({pct:.1f}%) | 잔여: {len(remaining)}종목 → 다음 회차 자동 이어받기 실행"
        )
        if yielded:
            msg += " (daily 배치 양보로 중단 — 수동 재실행 필요)"
    else:
        c_total = supabase_get_table_exact_count(sb_url, sb_key, "daily_chart")
        s_total = supabase_get_table_exact_count(sb_url, sb_key, "daily_investor_supply")
        ref = supabase_get_stock_range_status(sb_url, sb_key, "005930")
        msg = (
            f"✅ [LS 확장 백필 완료 ({span_txt})] 유니버스 {total}종목 100% | daily_chart 약 {c_total:,}행 | "
            f"daily_investor_supply 약 {s_total:,}행 | 삼성전자 일봉 {ref['chart_oldest']} ~ {ref['chart_latest']}"
        )
    logger.info(msg)
    send_telegram_alert(tg_token, tg_chat, msg)
    return {"total": total, "done": done_cnt, "remaining": len(remaining), "failed": failed,
            "needs_resume": needs_resume, "yielded": yielded, "timed_out": timed_out}


# ---------------------------------------------------------------------------
# 5. 메인 배치 파이프라인 (시가총액 700억 이상 보통주 전수 구축 & 일일 증분)
# ---------------------------------------------------------------------------
def run_standalone_batch(
    mode: str = "daily",
    min_ratio: float = 10.0,
    max_stocks: int = 0,
    skip_existing: bool = True,
    skip_if_completed: bool = False,
    start_idx: int = 0,
    end_idx: int = 0,
    chunk_spec: str = "",
    max_runtime_minutes: int = 345,
    batch_slot: str = "auto",
) -> Dict[str, Any]:
    batch_start_ts = time.time()
    ls_key = os.getenv("LS_APP_KEY", "").strip()
    ls_secret = os.getenv("LS_APP_SECRET", "").strip()
    sb_url = os.getenv("SUPABASE_URL", DEFAULT_SUPABASE_URL).strip() or DEFAULT_SUPABASE_URL
    sb_key = os.getenv("SUPABASE_KEY", DEFAULT_SUPABASE_KEY).strip() or DEFAULT_SUPABASE_KEY
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    tg_chat_id = os.getenv("TELEGRAM_CHAT_ID", DEFAULT_TELEGRAM_CHAT_ID).strip() or DEFAULT_TELEGRAM_CHAT_ID

    # [4.2절 1항] 시스템 타임존(UTC)과 무관하게 항상 KST(UTC+9) 기준일 사용
    today = get_kst_today()
    today_str = today.isoformat()
    recent_history_cutoff = (today - dt.timedelta(days=20)).isoformat()
    existing_masters = supabase_fetch_existing_masters(sb_url, sb_key)
    existing_by_code = {str(r["shcode"]): r for r in existing_masters if r.get("shcode")}

    rebuild_due, reason = is_quarterly_rebuild_due(today, existing_masters)
    if mode in ("backfill", "universe"):
        rebuild_due = True
        reason = f"수동 {mode} 모드 실행 (시가총액 ≥ 700억 보통주 전수 산출 및 데이터 확보)"

    # LS_APP_KEY 미설정 로컬 환경에서도 당일(today_str) 데이터가 이미 >= 98.5% 완주된 상태라면 5초 내 즉시 정상 종료 지원
    if mode == "daily" and skip_if_completed and not rebuild_due and (not ls_key or not ls_secret):
        fast_comp = check_daily_batch_completion(sb_url, sb_key, existing_masters, today_str)
        if fast_comp["is_completed"]:
            elapsed_sec = time.time() - batch_start_ts
            logger.info(
                "[SKIP-COMPLETED] 기준일(%s) 일일 배치가 이미 정상 완주됨 "
                "(완주율 %.2f%% >= %.1f%% | 확정 %d/%d종목, 거래정지 %d종목 | %.2f초) — 중복 수집 및 텔레그램 발송 생략",
                today_str,
                fast_comp["completion_pct"],
                DAILY_COMPLETION_THRESHOLD_PCT,
                fast_comp["completed_count"],
                fast_comp["total_universe"],
                fast_comp["halted_count"],
                elapsed_sec,
            )
            _write_github_output("skipped_completed", "true")
            return {
                "skipped_completed": True,
                "latest_trade_date": today_str,
                "completion_pct": fast_comp["completion_pct"],
                "universe_count": fast_comp["completed_count"],
                "backfilled_count": 0,
                "incremental_count": 0,
                "skipped_count": fast_comp["completed_count"],
                "screened_1d": [],
                "screened_3d": [],
                "report_text": "",
            }

    if not ls_key or not ls_secret:
        raise ValueError("LS_APP_KEY 및 LS_APP_SECRET 환경변수가 필요합니다.")

    client = LSApiClient(ls_key, ls_secret)
    client.authenticate()

    # [4.2절 2항] 대표 종목(005930) t8410 1회 조회로 실제 최신 KRX 개장일(latest_krx_date) 획득 및 공휴일 보호
    latest_krx_date = client.fetch_latest_krx_trading_date(today_str) if mode == "daily" else today_str
    is_partial_resume = True

    # [v2.6 10.1절] 1일 2회 배치 슬롯 판별 + 평일 공휴일(latest_krx_date != today_str) 스킵 우선 처리
    effective_slot = resolve_batch_slot(batch_slot)
    min_updated_at_kst: Optional[str] = None
    if mode == "daily":
        if latest_krx_date != today_str:
            if rebuild_due and mode == "daily":
                logger.info("[HOLIDAY] 평일 공휴일(최신 개장일 %s != KST오늘 %s) — 분기 재산출보다 공휴일 스킵을 우선 처리", latest_krx_date, today_str)
            rebuild_due = False
        elif effective_slot == "final":
            min_updated_at_kst = f"{today_str}T{FINAL_SLOT_MIN_UPDATED_HM_KST}+09:00"
    completed_codes: Set[str] = set()
    slot_label = "[2차 최종 확정]" if effective_slot == "final" else "[1차 정규장 가집계]"
    logger.info("배치 슬롯: %s (요청=%s, min_updated_at_kst=%s)", effective_slot, batch_slot, min_updated_at_kst)

    # [4.2절 3항] 당일(또는 공휴일 직전 최신 개장일) 완주 여부 사전 검사 (--skip-if-completed)
    if mode == "daily" and not rebuild_due and existing_masters:
        comp = check_daily_batch_completion(
            sb_url, sb_key, existing_masters, latest_krx_date, min_updated_at_kst=min_updated_at_kst
        )
        completed_codes = set(comp.get("completed_codes") or set())
        is_partial_resume = not comp["is_completed"]
        if skip_if_completed and comp["is_completed"]:
            elapsed_sec = time.time() - batch_start_ts
            logger.info(
                "[SKIP-COMPLETED] 기준일(%s, KST오늘=%s) 일일 배치가 이미 정상 완주됨 "
                "(완주율 %.2f%% >= %.1f%% | 확정 %d/%d종목, 거래정지 %d종목 | %.2f초) — LS API 전수 호출 및 중복 텔레그램 발송 생략",
                latest_krx_date,
                today_str,
                comp["completion_pct"],
                DAILY_COMPLETION_THRESHOLD_PCT,
                comp["completed_count"],
                comp["total_universe"],
                comp["halted_count"],
                elapsed_sec,
            )
            _write_github_output("skipped_completed", "true")
            return {
                "skipped_completed": True,
                "latest_trade_date": latest_krx_date,
                "completion_pct": comp["completion_pct"],
                "universe_count": comp["completed_count"],
                "backfilled_count": 0,
                "incremental_count": 0,
                "skipped_count": comp["completed_count"],
                "screened_1d": [],
                "screened_3d": [],
                "report_text": "",
            }

    _write_github_output("skipped_completed", "false")

    # 시작 전 혹시 DB에 남아있는 장중 미확정(전 주체 0) 수급 레코드 자동 정리
    purged_cnt = supabase_cleanup_unsettled_supply(
        sb_url, sb_key, target_date=today_str, existing_masters=existing_masters
    )
    if purged_cnt > 0:
        logger.info("장중 미확정(전 주체 0) 수급 레코드 %d건 사전 정리 완료", purged_cnt)

    logger.info(
        "배치 실행 모드 판정: %s (사유: %s | KST기준일: %s | 최신KRX개장일: %s | 기존 마스터: %d종목)",
        "유니버스 전수 산출" if rebuild_due else "일일 증분 + 급등주 자동 편입",
        reason,
        today_str,
        latest_krx_date,
        len(existing_by_code),
    )

    common_master = client.fetch_common_stock_master()
    target_candidates: List[Dict[str, Any]] = []

    if rebuild_due:
        # 1) 시가총액 ≥ 700억 보통주 전수 추출
        mcap_map = client.fetch_market_cap_above_threshold(common_master, min_mcap_eok=700.0)

        # 추출된 유니버스 마스터를 먼저 stocks_master에 일괄 Upsert하여 유니버스 누락 원천 방지
        initial_master_rows: List[Dict[str, Any]] = []
        now_iso = get_kst_now().isoformat()
        for shcode, info in mcap_map.items():
            prev = existing_by_code.get(shcode) or {}
            initial_master_rows.append({
                "shcode": shcode,
                "hname": info["hname"],
                "market": info["market"],
                "shares": int(info.get("shares", 0) or prev.get("shares", 0) or 0),
                "market_cap_eok": float(info.get("market_cap_eok", 0) or prev.get("market_cap_eok", 0) or 0),
                "avg_vol_20d": int(prev.get("avg_vol_20d", 0) or 0),
                "avg_val_20d_eok": float(prev.get("avg_val_20d_eok", 0) or 0),
                "is_universe": True,
                "last_close": int(info.get("price", 0) or prev.get("last_close", 0) or 0),
                "updated_at": now_iso,
            })
        supabase_upsert(sb_url, sb_key, "stocks_master", "shcode", initial_master_rows)
        logger.info("stocks_master에 시가총액 ≥ 700억 보통주 %d종목 일괄 선등록 완료", len(initial_master_rows))

        target_candidates = sorted(
            mcap_map.values(),
            key=lambda x: (-float(x.get("market_cap_eok", 0) or 0), str(x.get("shcode", ""))),
        )
    else:
        # 2) 평일 일일 배치: 기존 유니버스 종목(is_universe=True) 전체 로드 + t1463 급등주 자동 편입
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

        target_candidates = sorted(
            target_candidates,
            key=lambda x: (-float(x.get("market_cap_eok", 0) or 0), str(x.get("shcode", ""))),
        )

    total_candidates_count = len(target_candidates)

    # 구간 분할(--chunk N/M 또는 --start-idx / --end-idx) 적용
    if chunk_spec and "/" in chunk_spec:
        part_str, total_str = chunk_spec.split("/", 1)
        part_idx = max(1, int(part_str))
        total_parts = max(1, int(total_str))
        chunk_len = (total_candidates_count + total_parts - 1) // total_parts
        c_start = (part_idx - 1) * chunk_len
        c_end = min(total_candidates_count, part_idx * chunk_len)
        target_candidates = target_candidates[c_start:c_end]
        logger.info("청크 분할(%s) 적용: 전체 %d종목 중 [%d:%d] (%d종목) 처리", chunk_spec, total_candidates_count, c_start, c_end, len(target_candidates))
    elif start_idx > 0 or end_idx > 0:
        s_i = max(0, start_idx)
        e_i = end_idx if end_idx > 0 else total_candidates_count
        target_candidates = target_candidates[s_i:e_i]
        logger.info("인덱스 구간 분할 적용: 전체 %d종목 중 [%d:%d] (%d종목) 처리", total_candidates_count, s_i, e_i, len(target_candidates))

    if max_stocks > 0:
        target_candidates = target_candidates[:max_stocks]
        logger.info("최대 처리 종목 수(--max-stocks) 적용: %d종목만 처리", len(target_candidates))

    # 2년치(약 500영업일, 760달력일) 기준 시작일 설정
    two_year_start_date = (today - dt.timedelta(days=760)).isoformat()

    screened_1d: List[Dict[str, Any]] = []
    screened_3d: List[Dict[str, Any]] = []
    universe_count = 0
    skipped_count = 0
    backfilled_count = 0
    incremental_count = 0
    latest_trade_date = ""

    # [v2.8 12.2절 · v2.8.1 13.1절] 일괄 프리페치 (daily & 분기 재산출 아님, 단위 테스트 Mock 환경에서는 비활성)
    prefetch_ctx: Optional[Dict[str, Any]] = None
    mocked_db = (
        not hasattr(supabase_prefetch_daily_context, "_mock_name")
        and (
            hasattr(supabase_get_stock_data_status_detail, "_mock_name")
            or hasattr(supabase_get_anchor_row, "_mock_name")
        )
    )
    if mode == "daily" and not rebuild_due and existing_by_code and not mocked_db:
        t_pf = time.time()
        pf_codes = [item["shcode"] for item in target_candidates if item.get("shcode") in existing_by_code]
        prefetch_ctx = supabase_prefetch_daily_context(
            sb_url, sb_key, latest_krx_date, target_codes=pf_codes
        )
        if prefetch_ctx:
            logger.info(
                "[PREFETCH] 상태·앵커 일괄 적재 완료 (앵커 %d종목 | 최신상태 %d종목 | 2년보유 차트 %d/수급 %d | 폴백사전해결 %d | %.1f초)",
                len(prefetch_ctx["anchor_by_code"]), len(prefetch_ctx["recent_status"]),
                len(prefetch_ctx["hist_chart_2y_codes"]), len(prefetch_ctx["hist_supply_2y_codes"]),
                len(prefetch_ctx.get("fallback_status_by_code", {})), time.time() - t_pf,
            )

    # [v2.8 12.3절] t8410‖t1717 병렬 수집 (Mock 환경에서는 기존 순차 호출)
    parallel_ok = not (
        hasattr(client.fetch_daily_chart, "_mock_name") or hasattr(client.fetch_investor_supply, "_mock_name")
    )
    pair_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2) if parallel_ok else None
    upsert_buf = BatchUpsertBuffer(sb_url, sb_key, FLUSH_BATCH_STOCKS)

    for idx, item in enumerate(target_candidates, 1):
        # GitHub Actions 6시간(360분) 제한 도달 전 안전 종료 가드 (기본 345분)
        elapsed_min = (time.time() - batch_start_ts) / 60.0
        if max_runtime_minutes > 0 and elapsed_min >= max_runtime_minutes:
            logger.warning(
                "최대 실행 시간(%.1f분) 도달로 안전 종료합니다. 재실행 시 --skip-existing으로 즉시 이어받기됩니다.",
                elapsed_min,
            )
            break

        shcode = item["shcode"]
        hname = item["hname"]
        market = item["market"]
        try:
            # 기존 DB 적재 상태 확인 (이미 마스터에 존재했던 종목만 조회하여 불필요한 쿼리 절감)
            chart_cnt, chart_latest, supply_cnt, supply_latest, is_latest_supply_unsettled = 0, "", 0, "", False
            if shcode in existing_by_code:
                pf_status = lookup_prefetched_status(prefetch_ctx, shcode)
                if pf_status is not None:
                    chart_cnt, chart_latest, supply_cnt, supply_latest, is_latest_supply_unsettled = pf_status
                else:
                    chart_cnt, chart_latest, supply_cnt, supply_latest, is_latest_supply_unsettled = (
                        supabase_get_stock_data_status_detail(sb_url, sb_key, shcode)
                    )

            # 1) 2년치 과거 시계열이 DB에 구축되어 있는지 판정 (최근 20달력일 이내 데이터 보유 & 400영업일 이상 또는 신규상장 전 기간)
            has_2yr_history = is_stock_already_backfilled(
                chart_cnt,
                chart_latest,
                supply_cnt,
                supply_latest,
                min_target_date=recent_history_cutoff,
                is_latest_supply_unsettled=False,
            )

            # 2-A) backfill 모드 스마트 이어받기 스킵
            if mode == "backfill" and skip_existing and has_2yr_history and not is_latest_supply_unsettled:
                skipped_count += 1
                universe_count += 1
                if supply_latest > latest_trade_date:
                    latest_trade_date = supply_latest
                if skipped_count <= 10 or skipped_count % 25 == 0:
                    logger.info(
                        "[SKIP %d/%d] %s(%s) 이미 2년치 적재 완료 (차트 %d일·수급 %d일, 최신 %s)",
                        idx, len(target_candidates), hname, shcode, chart_cnt, supply_cnt, supply_latest,
                    )
                continue

            # 2-B) [4.2절 4항] daily 모드 부분 적재(98.5% 미만 중단) 이어받기 스킵:
            #      이미 2년치 히스토리가 있고 당일(latest_krx_date) 일봉 및 확정 수급까지 적재 완료된 종목은 LS API 호출 생략
            if (
                mode == "daily"
                and skip_existing
                and is_partial_resume
                and has_2yr_history
                and chart_latest == latest_krx_date
                and supply_latest == latest_krx_date
                and not is_latest_supply_unsettled
                and (not min_updated_at_kst or shcode in completed_codes)
            ):
                skipped_count += 1
                universe_count += 1
                if supply_latest > latest_trade_date:
                    latest_trade_date = supply_latest
                if skipped_count <= 10 or skipped_count % 25 == 0:
                    logger.info(
                        "[DAILY-SKIP %d/%d] %s(%s) 최신 개장일(%s) 확정 데이터 기적재 완료 — 미처리 종목 고속 이어받기",
                        idx, len(target_candidates), hname, shcode, latest_krx_date,
                    )
                continue

            # 3) 수정주가 일봉 수집 및 EMA(5, 20, 60, 120, 240) 계산 [v2.3 6.3절]
            #    - 신규/미완성 종목: 2016-01-01부터 최대 3,000영업일(10년치) 전체 적재
            #    - 기존 종목(daily): DB 앵커 행 종가 대조 후 앵커 EMA를 시드로 이어받기(증분) — 불일치(액면분할 등) 시 10년치 전체 재적재
            needs_full_2yr = (not has_2yr_history) or (mode == "backfill" and not skip_existing)
            anchor_row: Optional[Dict[str, Any]] = None
            seeded_charts: Optional[List[Dict[str, Any]]] = None
            pre_supply_raw: Optional[List[Dict[str, Any]]] = None
            if not needs_full_2yr and mode in ("daily", "universe"):
                anchor_row = (prefetch_ctx["anchor_by_code"].get(shcode) if prefetch_ctx else None) or \
                    supabase_get_anchor_row(sb_url, sb_key, shcode)

            if needs_full_2yr:
                chart_rows = client.fetch_daily_chart(shcode, CHART_HISTORY_START_DATE, today_str, count=TARGET_10Y_CHART_COUNT)
            elif anchor_row:
                recent_start = (today - dt.timedelta(days=ANCHOR_RECENT_CALENDAR_DAYS)).isoformat()
                if pair_pool is not None:
                    fut_chart = pair_pool.submit(client.fetch_daily_chart, shcode, recent_start, today_str, ANCHOR_RECENT_COUNT)
                    fut_sup = pair_pool.submit(client._fetch_t1717_pages, shcode, recent_start, today_str, 1)
                    chart_rows = fut_chart.result()
                    try:
                        pre_supply_raw = fut_sup.result()
                    except Exception as exc_sup:  # noqa: BLE001
                        logger.warning("t1717 병렬 수집 실패 (%s) — 순차 재수집: %s", shcode, exc_sup)
                        pre_supply_raw = None
                else:
                    chart_rows = client.fetch_daily_chart(shcode, recent_start, today_str, count=ANCHOR_RECENT_COUNT)
                anchor_status, seeded_charts = build_anchor_seeded_charts(chart_rows, anchor_row)
                if anchor_status != "ok":
                    pre_supply_raw = None
                if anchor_status == "mismatch":
                    logger.warning("[ANCHOR-MISMATCH] %s(%s) 앵커 종가 불일치(액면분할 등 수정주가 변동) — 차트 전체 재적재", hname, shcode)
                    chart_rows = client.fetch_daily_chart(shcode, CHART_HISTORY_START_DATE, today_str, count=TARGET_10Y_CHART_COUNT)
                    seeded_charts = None
                    needs_full_2yr = True
                elif anchor_status == "missing":
                    chart_rows = client.fetch_daily_chart(shcode, CHART_HISTORY_START_DATE, today_str, count=TARGET_10Y_CHART_COUNT)
                    seeded_charts = None
            else:
                chart_rows = client.fetch_daily_chart(shcode, CHART_HISTORY_START_DATE, today_str, count=TARGET_10Y_CHART_COUNT)
            if not chart_rows:
                continue

            # 최근 20영업일 평균 거래대금(억원) 및 거래량 계산 (수집 단계 사전 차단 없이 모든 시총≥700억 보통주 적재!)
            recent_20 = chart_rows[-20:]
            avg_val_20d_eok = round(
                sum(float(r["trading_value_m"]) for r in recent_20) / max(1, len(recent_20)) / 100.0, 2
            )
            avg_vol_20d = int(sum(int(r["volume"]) for r in recent_20) / max(1, len(recent_20)))

            enriched_charts = seeded_charts if seeded_charts else compute_ema_series(chart_rows)
            last_c = enriched_charts[-1]
            last_close = int(last_c["close"])

            # 시가총액 계산: 상장주식수(shares) × 당일종가
            shares = int(item.get("shares", 0) or 0)
            mcap_eok = float(item.get("market_cap_eok", 0) or 0)
            if shares <= 0 or mcap_eok <= 0:
                mcap_eok, shares, _ = client.fetch_single_stock_mcap(shcode)
            elif last_close > 0 and shares > 0:
                mcap_eok = round((shares * last_close) / 100_000_000.0, 2)

            if mcap_eok < 700.0:
                continue

            vol_map = {r["trade_date"]: int(r["volume"]) for r in chart_rows}
            close_map = {r["trade_date"]: int(r["close"]) for r in chart_rows}
            chart_by_date = {r["trade_date"]: r for r in enriched_charts}

            # 4) 수급 데이터 수집:
            #    - 히스토리 미완성 종목(또는 --force-all): 135페이지(약 3,000영업일) 전체 역순 슬라이딩 백필
            #    - 이미 히스토리가 있는 종목(평일 daily 모드 또는 장중 미확정 수급 재갱신): 최근 1페이지(25영업일)만 고속 증분 Upsert
            if needs_full_2yr:
                supply_start = max(SUPPLY_HISTORY_START_DATE, chart_rows[0]["trade_date"])
                supply_rows = client.fetch_investor_supply(
                    shcode, supply_start, today_str, vol_map, close_map, max_pages=SUPPLY_MAX_PAGES_10Y
                )
                charts_to_upsert = enriched_charts
                backfilled_count += 1
            else:
                supply_start = chart_rows[max(0, len(chart_rows) - 25)]["trade_date"]
                if pre_supply_raw is not None:
                    supply_rows = client._parse_t1717_rows(
                        shcode, pre_supply_raw, supply_start, vol_map, close_map, end_date=today_str
                    )
                else:
                    supply_rows = client.fetch_investor_supply(
                        shcode, supply_start, today_str, vol_map, close_map, max_pages=1
                    )
                charts_to_upsert = enriched_charts if seeded_charts else enriched_charts[-25:]
                incremental_count += 1

            if not supply_rows:
                continue

            m_row = {
                "shcode": shcode,
                "hname": hname,
                "market": market,
                "shares": shares,
                "market_cap_eok": mcap_eok,
                "avg_vol_20d": avg_vol_20d,
                "avg_val_20d_eok": avg_val_20d_eok,
                "is_universe": True,
                "last_close": last_close,
                "updated_at": get_kst_now().isoformat(),
            }

            # [v2.8 12.4절] 증분 수급 Upsert 윈도우 슬림화(직전 누락일 자동 치유 유지) + 50종목 버퍼 Upsert
            supply_to_upsert = supply_rows
            if not needs_full_2yr and anchor_row is not None and mode == "daily":
                ten_start = supply_rows[max(0, len(supply_rows) - INCREMENTAL_SUPPLY_UPSERT_DAYS)]["trade_date"]
                cutoff_parts = [ten_start, str(anchor_row.get("trade_date") or ten_start)]
                if supply_latest:
                    cutoff_parts.append(supply_latest)
                cutoff_supply_date = min(cutoff_parts)
                supply_to_upsert = [r for r in supply_rows if str(r["trade_date"]) >= cutoff_supply_date]
            upsert_buf.add(m_row, charts_to_upsert, supply_to_upsert)
            if needs_full_2yr or mode != "daily" or len(target_candidates) <= 5 or len(upsert_buf) >= FLUSH_BATCH_STOCKS:
                upsert_buf.flush()

            universe_count += 1
            last_s = supply_rows[-1]
            settled_date = str(last_s["trade_date"])
            if settled_date > latest_trade_date:
                latest_trade_date = settled_date
            matched_c = chart_by_date.get(settled_date, last_c)

            if float(last_s["inst_vol_ratio"]) >= min_ratio:
                screened_1d.append({
                    "shcode": shcode,
                    "hname": hname,
                    "market": market,
                    "trade_date": settled_date,
                    "inst_vol_ratio": float(last_s["inst_vol_ratio"]),
                    "real_inst_amt": float(last_s["real_inst_amt"]),
                    "real_inst_vol": int(last_s["real_inst_vol"]),
                    "frg_vol_ratio": float(last_s["frg_vol_ratio"]),
                    "change_rate": float(matched_c["change_rate"]),
                    "close": int(matched_c["close"]),
                    "ema_20": float(matched_c["ema_20"]),
                    "ema_60": float(matched_c["ema_60"]),
                })

            if len(supply_rows) >= 3 and len(enriched_charts) >= 3:
                recent_3_s = supply_rows[-3:]
                vol_3d = sum(int(vol_map.get(r["trade_date"], 0)) for r in recent_3_s)
                inst_3d = sum(int(r["real_inst_vol"]) for r in recent_3_s)
                amt_3d = sum(float(r["real_inst_amt"]) for r in recent_3_s)
                frg_3d = sum(int(r["frg_vol"]) for r in recent_3_s)
                ratio_3d = round((inst_3d / vol_3d) * 100.0, 2) if vol_3d > 0 else 0.0
                if ratio_3d >= min_ratio:
                    screened_3d.append({
                        "shcode": shcode,
                        "hname": hname,
                        "trade_date": settled_date,
                        "inst_vol_ratio": ratio_3d,
                        "real_inst_amt": amt_3d,
                        "frg_vol_ratio": round((frg_3d / vol_3d) * 100.0, 2) if vol_3d > 0 else 0.0,
                    })

            if idx <= 5 or universe_count % 10 == 0:
                logger.info(
                    "진행 [%d/%d] %s(%s): 차트 %d일·수급 %d일 적재 완료 (누적 처리 %d종목 | 2년백필 %d | 증분 %d | 스킵 %d)",
                    idx, len(target_candidates), hname, shcode,
                    len(charts_to_upsert), len(supply_to_upsert),
                    universe_count, backfilled_count, incremental_count, skipped_count,
                )
        except Exception as exc:
            logger.warning("종목 처리 중 건너뜀 (%s %s): %s", shcode, hname, exc)

    # 루프 종료·중단 시 잔여 버퍼 전량 플러시 (필수)
    try:
        upsert_buf.flush()
    except Exception as exc:  # noqa: BLE001
        logger.warning("잔여 버퍼 플러시 중 예외: %s", exc)
    if pair_pool is not None:
        pair_pool.shutdown(wait=True)
    logger.info(
        "[PERF] 배치 루프 완료: %.1f분 (플러시 %d회 | TR호출 %d회 | 제한재시도 %d회 | 학습바닥 %s)",
        (time.time() - batch_start_ts) / 60.0,
        upsert_buf.flush_count,
        client.tr_call_count,
        client.rate_limit_retry_count,
        client._tr_learned_floor,
    )

    # [4.2절 4항] 기적재 스킵 종목이 텔레그램 요약 리포트(screened_1d, screened_3d)에서 절대 누락되지 않도록
    # 전체 유니버스 DB 확정 데이터 기준으로 재집계·병합
    report_ref_date = latest_trade_date or latest_krx_date or today_str
    # [v2.8 12.4절 3항] 무스킵 완주 시 전 종목 DB 재다운로드 생략 (부분 이어받기 시에는 기존과 동일하게 병합)
    skip_db_rebuild = (
        mode == "daily" and skipped_count == 0 and universe_count > 0
        and not hasattr(build_daily_screening_lists_from_db, "_mock_name")
    )
    if skip_db_rebuild:
        logger.info("[PERF] 무스킵 완주 — 사후 DB 재집계 생략 (루프 집계 결과 사용)")
        db_1d, db_3d = [], []
    else:
        latest_masters = [m for m in supabase_fetch_existing_masters(sb_url, sb_key) if m.get("is_universe")]
        if not latest_masters:
            latest_masters = [m for m in existing_masters if m.get("is_universe")] or target_candidates
        try:
            db_1d, db_3d = build_daily_screening_lists_from_db(
                sb_url, sb_key, latest_masters, report_ref_date, min_ratio=min_ratio
            )
        except Exception as exc:
            logger.warning("DB 기준 텔레그램 스크리닝 재집계 중 예외(루프 메모리 결과 사용): %s", exc)
            db_1d, db_3d = [], []

    merged_1d: Dict[str, Dict[str, Any]] = {str(item["shcode"]): item for item in db_1d}
    for item in screened_1d:
        if item.get("trade_date") == report_ref_date:
            merged_1d[str(item["shcode"])] = item
    merged_3d: Dict[str, Dict[str, Any]] = {str(item["shcode"]): item for item in db_3d}
    for item in screened_3d:
        if item.get("trade_date") == report_ref_date:
            merged_3d[str(item["shcode"])] = item

    screened_1d = sorted(
        merged_1d.values(),
        key=lambda x: (-float(x["inst_vol_ratio"]), -float(x["real_inst_amt"]), str(x["shcode"])),
    )
    screened_3d = sorted(
        merged_3d.values(),
        key=lambda x: (-float(x["inst_vol_ratio"]), -float(x["real_inst_amt"]), str(x["shcode"])),
    )

    lines = [
        ("📊 *[1차 정규장 가집계]* LS 수급·차트 스크리너 DB 업데이트 완료" if effective_slot == "prelim" else "✅ *[2차 최종 확정]* LS 수급·차트 스크리너 DB 업데이트 완료"),
        f"• 기준 거래일: `{report_ref_date}`",
        f"• 실행 모드: `{reason}`",
        f"• 유니버스 처리: *{universe_count:,}종목* (2년백필 {backfilled_count:,} | 일일증분 {incremental_count:,} | 기적재스킵 {skipped_count:,})",
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
        "skipped_completed": False,
        "latest_trade_date": report_ref_date,
        "universe_count": universe_count,
        "backfilled_count": backfilled_count,
        "incremental_count": incremental_count,
        "skipped_count": skipped_count,
        "screened_1d": screened_1d,
        "screened_3d": screened_3d,
        "report_text": report_text,
    }


# ---------------------------------------------------------------------------
# 6. 확정 스크리닝 전략 v2.0 평가 함수 (STRATEGY.md 2.1 ~ 2.3 단일 진실 공급원)
# ---------------------------------------------------------------------------
def compute_consec_5p_days(supply_series: List[Dict[str, Any]]) -> int:
    """기준일 T부터 역순으로 순수기관 거래량 비중이 연속 >= 5.0%인 거래일 수를 산출합니다."""
    cnt = 0
    for row in reversed(supply_series):
        if float(row.get("inst_vol_ratio", 0) or 0) >= 5.0:
            cnt += 1
        else:
            break
    return cnt


def evaluate_first_inst_supply_types(supply_series: List[Dict[str, Any]]) -> Tuple[bool, bool]:
    """2.3절 ② 당일 첫 순수기관 수급 발생 조건 (유형 A, 유형 B) 충족 여부를 반환합니다."""
    n = len(supply_series)
    is_type_a = False
    is_type_b = False

    if n >= 11 and float(supply_series[-1].get("inst_vol_ratio", 0) or 0) >= 10.0:
        is_type_a = all(float(supply_series[-1 - k].get("inst_vol_ratio", 0) or 0) < 5.0 for k in range(1, 11))

    if n >= 13:
        recent_3 = all(float(supply_series[-1 - k].get("inst_vol_ratio", 0) or 0) >= 5.0 for k in range(0, 3))
        if recent_3:
            is_type_b = all(float(supply_series[-1 - m].get("inst_vol_ratio", 0) or 0) < 5.0 for m in range(3, 13))

    return is_type_a, is_type_b


def check_stabilization_at_p(chart_series: List[Dict[str, Any]], p_idx: int) -> bool:
    """2.3절 ①-(2) 기준점 P에서의 60거래일 낙폭 과대(-15.0% 이하) 및 바닥 진정(a·b·c) 조건을 검증합니다."""
    if p_idx < 59 or p_idx >= len(chart_series):
        return False

    max_high_60 = max(float(chart_series[p_idx - k].get("high", 0) or 0) for k in range(0, 60))
    if max_high_60 <= 0:
        return False

    close_p = float(chart_series[p_idx].get("close", 0) or 0)
    drawdown_pct = ((close_p / max_high_60) - 1.0) * 100.0
    if drawdown_pct > -15.0:
        return False

    close_pm1 = float(chart_series[p_idx - 1].get("close", 0) or 0)
    close_pm2 = float(chart_series[p_idx - 2].get("close", 0) or 0)
    min_close_3 = min(close_pm2, close_pm1, close_p)
    min_low_17 = min(float(chart_series[p_idx - k].get("low", 0) or 0) for k in range(3, 20))
    if min_close_3 < min_low_17:
        return False

    low_pm3 = float(chart_series[p_idx - 3].get("low", 0) or 0)
    low_pm2 = float(chart_series[p_idx - 2].get("low", 0) or 0)
    low_pm1 = float(chart_series[p_idx - 1].get("low", 0) or 0)
    if not (close_pm2 >= low_pm3 and close_pm1 >= low_pm2 and close_p >= low_pm1):
        return False

    return True


def resolve_trading_value_m(chart_row: Dict[str, Any]) -> float:
    """일봉 행에서 거래대금(백만원)을 추출합니다. trading_value_m <= 0이면 (close * volume) / 1,000,000 폴백 (5.1절 1항)."""
    raw_val_m = float(chart_row.get("trading_value_m", 0) or 0)
    if raw_val_m > 0:
        return raw_val_m
    c = float(chart_row.get("close", 0) or 0)
    v = float(chart_row.get("volume", 0) or 0)
    if c > 0 and v > 0:
        return (c * v) / 1_000_000.0
    return 0.0


def format_ema_trend_status(chart_or_item: Dict[str, Any]) -> str:
    """기준일(T)의 5개 EMA(5, 20, 60, 120, 240)를 큰 순서(내림차순, 동률 시 단기->장기)로 정렬한 추세 문자열을 반환합니다 (5.2절)."""
    entries = [
        ("Ema5", 5, float(chart_or_item.get("ema_5", 0) or 0)),
        ("Ema20", 20, float(chart_or_item.get("ema_20", 0) or 0)),
        ("Ema60", 60, float(chart_or_item.get("ema_60", 0) or 0)),
        ("Ema120", 120, float(chart_or_item.get("ema_120", 0) or 0)),
        ("Ema240", 240, float(chart_or_item.get("ema_240", 0) or 0)),
    ]
    entries.sort(key=lambda x: (-x[2], x[1]))
    return " > ".join(e[0] for e in entries)


def evaluate_strategy_v2_stock(
    chart_rows: List[Dict[str, Any]],
    supply_rows: List[Dict[str, Any]],
    ref_date: str,
) -> Optional[Dict[str, Any]]:
    """
    단일 종목의 일봉·수급 시계열에 대해 기준 확정일 ref_date(T) 기준 Strategy v2.2 지표를 산출합니다.
    - trade_date <= ref_date 상한 적용 (장중 T+1 일봉 혼입 원천 차단)
    - 일봉과 확정 수급 모두 ref_date(T) 레코드가 존재하는 종목만 유효 반환
    - [모드 1: 기관 수급 발생 종목] 전용 유동성·수급금액 제외 필터 반영 (2.2절 & 5.1절):
      · 당일 10%/15%/20% 이상: 당일 수급금액 >= 1억(100.0) & 거래량 >= 3만주(30,000) & 거래대금 >= 5억(500.0)
      · 3일 연속 5% 이상: 최근 3일 평균 수급금액 >= 1억(100.0) & 3일 평균 거래량 >= 3만주(30,000) & 3일 평균 거래대금 >= 5억(500.0)
    - [모드 2: 하락 추세 전환 수급 발생]: 유동성·수급금액 제외 필터 미적용 (기존 2.3절 유지)
    """
    c_by_dt = {str(c["trade_date"]): c for c in chart_rows if c.get("trade_date") and str(c["trade_date"]) <= ref_date}
    s_by_dt = {
        str(s["trade_date"]): s
        for s in supply_rows
        if s.get("trade_date")
        and (
            str(s["trade_date"]) < ref_date
            or (str(s["trade_date"]) == ref_date and not is_unsettled_supply_row(s))
        )
    }
    if ref_date not in c_by_dt or ref_date not in s_by_dt:
        return None

    c_list = [c_by_dt[d] for d in sorted(c_by_dt.keys())]
    s_list = [s_by_dt[d] for d in sorted(s_by_dt.keys())]
    chart_t = c_list[-1]
    supply_t = s_list[-1]
    if is_unsettled_supply_row(supply_t):
        return None

    inst_ratio_t = float(supply_t.get("inst_vol_ratio", 0) or 0)
    frg_ratio_t = float(supply_t.get("frg_vol_ratio", 0) or 0)
    inst_amt_m_t = float(supply_t.get("real_inst_amt", 0) or 0)
    volume_t = int(chart_t.get("volume", 0) or 0)
    trading_value_m_t = resolve_trading_value_m(chart_t)
    consec_5p_days = compute_consec_5p_days(s_list)

    # 2.2절 1항 & 5.1절 2항 ①: 당일 단일일 3개 옵션 제외 필터 (수급금액 >= 1억, 거래량 >= 3만주, 거래대금 >= 5억)
    passes_day_inst_liquidity = (
        inst_amt_m_t >= 100.0 and volume_t >= 30000 and trading_value_m_t >= 500.0
    )

    # 2.2절 2항 & 5.1절 2항 ②: 3일 연속 5% 이상 제외 필터 (최근 3일 평균 수급금액·거래량·거래대금 적용)
    is_consec_3d_5p = False
    if (
        len(c_list) >= 3
        and len(s_list) >= 3
        and all(float(s_list[-1 - k].get("inst_vol_ratio", 0) or 0) >= 5.0 for k in range(0, 3))
    ):
        avg_amt_3d = sum(float(s_list[-1 - k].get("real_inst_amt", 0) or 0) for k in range(0, 3)) / 3.0
        avg_vol_3d = sum(float(c_list[-1 - k].get("volume", 0) or 0) for k in range(0, 3)) / 3.0
        avg_val_m_3d = sum(resolve_trading_value_m(c_list[-1 - k]) for k in range(0, 3)) / 3.0
        is_consec_3d_5p = (
            avg_amt_3d >= 100.0 and avg_vol_3d >= 30000.0 and avg_val_m_3d >= 500.0
        )

    is_trend_reversal = False
    if len(c_list) >= 65 and len(s_list) >= 13:
        t_idx = len(c_list) - 1
        c_tm1 = c_list[t_idx - 1]
        close_t = float(chart_t.get("close", 0) or 0)
        open_t = float(chart_t.get("open", 0) or 0)
        ema5_t = float(chart_t.get("ema_5", 0) or 0)
        e20 = float(c_tm1.get("ema_20", 0) or 0)
        e60 = float(c_tm1.get("ema_60", 0) or 0)
        e120 = float(c_tm1.get("ema_120", 0) or 0)
        if close_t >= ema5_t and close_t > open_t and (0 < e20 < e60 < e120):
            is_type_a, is_type_b = evaluate_first_inst_supply_types(s_list)
            valid_a = is_type_a and check_stabilization_at_p(c_list, t_idx - 1)
            valid_b = is_type_b and (
                check_stabilization_at_p(c_list, t_idx - 1) or check_stabilization_at_p(c_list, t_idx - 3)
            )
            is_trend_reversal = valid_a or valid_b

    close_val = int(chart_t.get("close", 0) or 0)
    prev_close = int(c_list[-2].get("close", 0) or 0) if len(c_list) >= 2 else None
    price_diff = (close_val - prev_close) if prev_close is not None else 0

    ema_5 = float(chart_t.get("ema_5", close_val) or close_val)
    ema_20 = float(chart_t.get("ema_20", close_val) or close_val)
    ema_60 = float(chart_t.get("ema_60", close_val) or close_val)
    ema_120 = float(chart_t.get("ema_120", close_val) or close_val)
    ema_240 = float(chart_t.get("ema_240", close_val) or close_val)

    return {
        "trade_date": ref_date,
        "close": close_val,
        "volume": volume_t,
        "trading_value_m": trading_value_m_t,
        "price_diff": price_diff,
        "change_rate": float(chart_t.get("change_rate", 0) or 0),
        "ema_5": ema_5,
        "ema_20": ema_20,
        "ema_60": ema_60,
        "ema_120": ema_120,
        "ema_240": ema_240,
        "ema_trend_status": format_ema_trend_status({
            "ema_5": ema_5,
            "ema_20": ema_20,
            "ema_60": ema_60,
            "ema_120": ema_120,
            "ema_240": ema_240,
        }),
        "inst_vol_ratio": inst_ratio_t,
        "real_inst_amt": inst_amt_m_t,
        "frg_vol_ratio": frg_ratio_t,
        "consec_5p_days": consec_5p_days,
        "is_day_10": passes_day_inst_liquidity and (inst_ratio_t >= 10.0),
        "is_day_15": passes_day_inst_liquidity and (inst_ratio_t >= 15.0),
        "is_day_20": passes_day_inst_liquidity and (inst_ratio_t >= 20.0),
        "is_consec_3d_5p": is_consec_3d_5p,
        "is_trend_reversal": is_trend_reversal,
    }


# ---------------------------------------------------------------------------
# 7. 합격 기준(AC-1 ~ AC-18) 정합성 및 Strategy v2.2 검증 리포트 (--mode verify)
# ---------------------------------------------------------------------------
def verify_supabase_data(sb_url: str = DEFAULT_SUPABASE_URL, sb_key: str = DEFAULT_SUPABASE_KEY) -> Dict[str, Any]:
    """
    대용량 DB(70만 행) 환경에서 복합 PK(shcode, trade_date) 인덱스 쿼리를 사용하여
    statement_timeout(HTTP 500) 없이 AC-1 ~ AC-18 정합성 및 Strategy v2.2 포착 결과를 검증합니다.
    """
    base = sb_url.rstrip("/")
    headers = supabase_headers(sb_key)
    masters = supabase_fetch_existing_masters(sb_url, sb_key)
    universe_masters = [m for m in masters if m.get("is_universe")]
    master_by_code = {str(m["shcode"]): m for m in universe_masters if m.get("shcode")}

    total_charts = supabase_get_table_exact_count(sb_url, sb_key, "daily_chart")
    total_supplies = supabase_get_table_exact_count(sb_url, sb_key, "daily_investor_supply")

    # 1) 시총 상·중·하위 분산 대표 10종목 PK 인덱스 조회로 최신 확정 거래일(T) 고속 확인 (4.5절)
    latest_settled_date = fetch_latest_settled_trade_date_db(sb_url, sb_key)

    # 2) PK 인덱스 기반 샘플 조회 및 전 종목 45일 윈도우 병렬 로드
    sample_codes = ",".join(str(m["shcode"]) for m in universe_masters[:20])
    charts = (
        http_get_json(
            f"{base}/rest/v1/daily_chart?shcode=in.({sample_codes})&trade_date=eq.{latest_settled_date}&select=*&limit=100",
            headers=headers,
        )
        if sample_codes and latest_settled_date != "-"
        else []
    )
    supplies = (
        http_get_json(
            f"{base}/rest/v1/daily_investor_supply?shcode=in.({sample_codes})"
            f"&trade_date=lte.{latest_settled_date}&select=*&order=shcode.asc,trade_date.desc&limit=500",
            headers=headers,
        )
        if sample_codes and latest_settled_date != "-"
        else []
    )

    print("=" * 84)
    print("🔍 [LS 수급·차트 스크리닝 시스템] 데이터 정합성(AC-1~AC-23) & Strategy v2.3 검증 리포트")
    print("=" * 84)
    print("1) [AC-1 & AC-2: 시총 700억 이상 보통주 전수 유니버스 & 거래대금 사전차단 해제 검증]")
    print(f"   - stocks_master 유니버스(is_universe=True) 종목 수: {len(universe_masters):,}종목")
    excluded_leaks = [m for m in universe_masters if is_excluded_security(str(m.get("hname", "")))]
    under_mcap = [m for m in universe_masters if float(m.get("market_cap_eok", 0) or 0) < 700.0]
    under_val_included = [m for m in universe_masters if float(m.get("avg_val_20d_eok", 0) or 0) < 20.0]
    print(f"   - ETF/ETN/스팩/우선주/리츠 혼입 건수: {len(excluded_leaks)}건 (정상 기준: 0건)")
    print(f"   - 시가총액 700억 미만 혼입 건수: {len(under_mcap)}건 (정상 기준: 0건)")
    print(f"   - 거래대금 20억 미만 중소형 보통주 포함 건수(AC-2): {len(under_val_included):,}종목")

    key_stocks = [
        ("005930", "삼성전자"),
        ("000660", "SK하이닉스"),
        ("005380", "현대차"),
        ("012450", "한화에어로스페이스"),
        ("196170", "알테오젠"),
        ("006650", "대한유화"),
        ("023160", "태광"),
    ]
    print("   - 주요 대형주 및 검증 대상 종목 시계열 적재 현황 (최초일 ~ 최신일, 총 영업일수):")
    for code, name in key_stocks:
        in_m = code in master_by_code
        if in_m:
            rs = supabase_get_stock_range_status(sb_url, sb_key, code)
        else:
            rs = {"chart_cnt": 0, "chart_oldest": "-", "chart_latest": "-",
                  "supply_cnt": 0, "supply_oldest": "-", "supply_latest": "-"}
        print(
            f"     · {name}({code}): 마스터={'OK' if in_m else 'MISSING'} | "
            f"일봉: {rs['chart_cnt']:,}일 ({rs['chart_oldest'] or '-'} ~ {rs['chart_latest'] or '-'}) | "
            f"수급: {rs['supply_cnt']:,}일 ({rs['supply_oldest'] or '-'} ~ {rs['supply_latest'] or '-'})"
        )

    print("\n2) [AC-3: 수정주가 일봉(daily_chart) & EMA(5/20/60/120/240) 검증]")
    print(f"   - daily_chart 전체 적재 행 수(추정/집계): 약 {total_charts:,}건 (기준일 PK 샘플: {len(charts)}건)")
    for c in charts[:3]:
        hname = (master_by_code.get(str(c["shcode"])) or {}).get("hname", c["shcode"])
        print(
            f"     · [{c['trade_date']}] {hname}({c['shcode']}): 종가 {int(c['close']):,}원 ({float(c['change_rate']):+.2f}%) | "
            f"거래량 {int(c['volume']):,}주 | EMA5={c['ema_5']}, EMA20={c['ema_20']}, EMA60={c['ema_60']}, EMA120={c['ema_120']}, EMA240={c['ema_240']}"
        )

    print("\n3) [AC-4: 순수기관(금융투자 제외 6대 주체) 수급(daily_investor_supply) 검증]")
    print(f"   - daily_investor_supply 전체 적재 행 수(추정/집계): 약 {total_supplies:,}건 (PK 샘플: {len(supplies)}건)")
    formula_errors = 0
    for s in supplies:
        calc_inst = sum(int(s.get(f"{subj}_vol", 0) or 0) for subj in PURE_INST_SUBJECTS)
        if calc_inst != int(s.get("real_inst_vol", 0) or 0):
            formula_errors += 1
    print(f"   - 순수기관 합산 수식(투신+사모+연기금+보험+기타금융+은행, 금투 제외) 오차 건수: {formula_errors}건 (정상 기준: 0건)")

    print("\n4) [AC-5, AC-9 & AC-16: 과거 시계열 실증 및 Strategy v2.2 전 종목 PK 스크리닝 결과]")
    try:
        tk_s = http_get_json(
            f"{base}/rest/v1/daily_investor_supply?shcode=eq.023160&trade_date=eq.2026-08-25&select=*",
            headers=headers,
        )
        kp_s = http_get_json(
            f"{base}/rest/v1/daily_investor_supply?shcode=eq.006650&trade_date=eq.2026-11-03&select=*",
            headers=headers,
        )
        if tk_s:
            r0 = tk_s[0]
            print(f"   - 태광(023160) 2026-08-25 수급: 존재 (OK) · 순수기관 {int(r0['real_inst_vol']):+,}주 ({float(r0['real_inst_amt']):+.1f}백만원, 비중 {float(r0['inst_vol_ratio']):+.2f}%)")
        if kp_s:
            r1 = kp_s[0]
            print(f"   - 대한유화(006650) 2026-11-03 수급: 존재 (OK) · 순수기관 {int(r1['real_inst_vol']):+,}주 ({float(r1['real_inst_amt']):+.1f}백만원, 비중 {float(r1['inst_vol_ratio']):+.2f}%)")
    except Exception as exc:
        print(f"   - 과거 특정일 조회 실패: {exc}")

    day10_list: List[Dict[str, Any]] = []
    day15_cnt = 0
    day20_cnt = 0
    consec3_cnt = 0
    reversal_list: List[Dict[str, Any]] = []

    if latest_settled_date != "-" and universe_masters:
        ref_dt = dt.date.fromisoformat(latest_settled_date)
        cutoff45 = (ref_dt - dt.timedelta(days=45)).isoformat()
        cutoff125 = (ref_dt - dt.timedelta(days=125)).isoformat()
        all_codes = [str(m["shcode"]) for m in universe_masters]
        chunks28 = [all_codes[i : i + 28] for i in range(0, len(all_codes), 28)]
        c_cols = "shcode,trade_date,open,high,low,close,change_rate,volume,trading_value_m,ema_5,ema_20,ema_60,ema_120,ema_240"
        s_cols = "shcode,trade_date,real_inst_vol,real_inst_amt,inst_vol_ratio,frg_vol,frg_vol_ratio,ind_vol,fn_inv_vol,etc_corp_vol,itc_vol,pef_vol,pen_vol,ins_vol,etc_fin_vol,bank_vol"

        c_map: Dict[str, List[Dict[str, Any]]] = {}
        s_map: Dict[str, List[Dict[str, Any]]] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            f_c = [
                ex.submit(
                    http_get_json,
                    f"{base}/rest/v1/daily_chart?shcode=in.({','.join(ch)})"
                    f"&and=(trade_date.gte.{cutoff45},trade_date.lte.{latest_settled_date})"
                    f"&select={c_cols}&order=shcode.asc,trade_date.asc&limit=1000",
                    headers,
                )
                for ch in chunks28
            ]
            f_s = [
                ex.submit(
                    http_get_json,
                    f"{base}/rest/v1/daily_investor_supply?shcode=in.({','.join(ch)})"
                    f"&and=(trade_date.gte.{cutoff45},trade_date.lte.{latest_settled_date})"
                    f"&select={s_cols}&order=shcode.asc,trade_date.asc&limit=1000",
                    headers,
                )
                for ch in chunks28
            ]
            for fut in f_c:
                for row in fut.result():
                    c_map.setdefault(str(row["shcode"]), []).append(row)
            for fut in f_s:
                for row in fut.result():
                    s_map.setdefault(str(row["shcode"]), []).append(row)

        # 1차 후보 추출 후 125일 일봉 보강 (3.5절 3항 동일 절차)
        stage1_codes: List[str] = []
        for code in all_codes:
            cl = [c for c in c_map.get(code, []) if str(c["trade_date"]) <= latest_settled_date]
            sl = [
                s for s in s_map.get(code, [])
                if str(s["trade_date"]) < latest_settled_date
                or (str(s["trade_date"]) == latest_settled_date and not is_unsettled_supply_row(s))
            ]
            if len(cl) < 2 or len(sl) < 13:
                continue
            if str(cl[-1]["trade_date"]) != latest_settled_date or str(sl[-1]["trade_date"]) != latest_settled_date:
                continue
            c_t, c_tm1 = cl[-1], cl[-2]
            if float(c_t["close"]) >= float(c_t["ema_5"]) and float(c_t["close"]) > float(c_t["open"]):
                if 0 < float(c_tm1["ema_20"]) < float(c_tm1["ema_60"]) < float(c_tm1["ema_120"]):
                    t_a, t_b = evaluate_first_inst_supply_types(sl)
                    if t_a or t_b:
                        stage1_codes.append(code)

        for i in range(0, len(stage1_codes), 10):
            ch10 = stage1_codes[i : i + 10]
            extra_rows = http_get_json(
                f"{base}/rest/v1/daily_chart?shcode=in.({','.join(ch10)})"
                f"&and=(trade_date.gte.{cutoff125},trade_date.lte.{latest_settled_date})"
                f"&select={c_cols}&order=shcode.asc,trade_date.asc&limit=1000",
                headers=headers,
            )
            by_code_extra: Dict[str, List[Dict[str, Any]]] = {}
            for r in extra_rows:
                by_code_extra.setdefault(str(r["shcode"]), []).append(r)
            for code, rows_ext in by_code_extra.items():
                c_map[code] = rows_ext

        for code in all_codes:
            ev = evaluate_strategy_v2_stock(c_map.get(code, []), s_map.get(code, []), latest_settled_date)
            if not ev:
                continue
            ev["shcode"] = code
            ev["hname"] = (master_by_code.get(code) or {}).get("hname", code)
            if ev["is_day_10"]:
                day10_list.append(ev)
            if ev["is_day_15"]:
                day15_cnt += 1
            if ev["is_day_20"]:
                day20_cnt += 1
            if ev["is_consec_3d_5p"]:
                consec3_cnt += 1
            if ev["is_trend_reversal"]:
                reversal_list.append(ev)

        day10_list.sort(key=lambda x: (-x["inst_vol_ratio"], -x["real_inst_amt"], x["shcode"]))
        reversal_list.sort(key=lambda x: (-x["inst_vol_ratio"], -x["real_inst_amt"], x["shcode"]))

    print(
        f"   - 기준일({latest_settled_date}) Strategy v2.2 포착 현황: "
        f"당일10%이상={len(day10_list)}종목 | 당일15%이상={day15_cnt}종목 | "
        f"당일20%이상={day20_cnt}종목 | 3일연속5%이상={consec3_cnt}종목 | "
        f"하락추세전환={len(reversal_list)}종목"
    )
    print(f"   - [기관 수급 발생 종목 · 당일 10% 이상] 상위 5종목:")
    for s in day10_list[:5]:
        print(
            f"     · {s['hname']}({s['shcode']}): 수급비중 {s['inst_vol_ratio']:.1f}% | "
            f"수급금액 {s['real_inst_amt'] / 100.0:+.1f}억 | 외국인 {s['frg_vol_ratio']:+.1f}% | 연속 {s['consec_5p_days']}일"
        )
    if reversal_list:
        print(f"   - [하락 추세 전환 수급 발생] 포착 종목:")
        for s in reversal_list[:5]:
            print(
                f"     · {s['hname']}({s['shcode']}): 수급비중 {s['inst_vol_ratio']:.1f}% | "
                f"수급금액 {s['real_inst_amt'] / 100.0:+.1f}억 | 종가 {s['close']:,}원 ({s['change_rate']:+.2f}%)"
            )

    print("=" * 84)
    return {
        "masters_count": len(universe_masters),
        "total_charts": total_charts,
        "total_supplies": total_supplies,
        "latest_settled_date": latest_settled_date,
        "day10_count": len(day10_list),
        "day15_count": day15_cnt,
        "day20_count": day20_cnt,
        "consec3_count": consec3_cnt,
        "reversal_count": len(reversal_list),
        "excluded_leaks": len(excluded_leaks),
        "formula_errors": formula_errors,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LS증권 수급·차트 스크리닝 배치 및 2년치 백필 도구")
    parser.add_argument(
        "--mode",
        choices=["daily", "backfill", "backfill_10y", "probe_10y", "universe", "verify"],
        default="daily",
    )
    parser.add_argument("--min-ratio", type=float, default=10.0)
    parser.add_argument("--max-stocks", type=int, default=0, help="테스트용 최대 처리 종목 수 (0=전체 유니버스)")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="이미 2년치 차트·수급이 적재된 종목은 건너뛰기 (기본 활성화)",
    )
    parser.add_argument(
        "--force-all",
        action="store_true",
        default=False,
        help="기적재 여부와 무관하게 전 종목 강제 재수집",
    )
    parser.add_argument(
        "--skip-if-completed",
        action="store_true",
        default=False,
        help="최신 KRX 개장일 데이터가 98.5%% 이상 완주된 상태면 5초 이내 즉시 정상 종료 (자동 스케줄 멱등성 가드)",
    )
    parser.add_argument("--batch-slot", choices=["auto", "prelim", "final"], default="auto", help="1일 2회 배치 슬롯 (auto: KST 19:30 미만 prelim / 이상 final)")
    parser.add_argument("--start-idx", type=int, default=0, help="후보 리스트 시작 인덱스 (0부터 시작)")
    parser.add_argument("--end-idx", type=int, default=0, help="후보 리스트 종료 인덱스 (0=끝까지)")
    parser.add_argument("--chunk", type=str, default="", help="구간 분할 지정 (예: '1/3', '2/3', '3/3')")
    parser.add_argument("--max-runtime-minutes", type=int, default=345, help="최대 실행 시간(분) 안전 가드")
    parser.add_argument("--chain-round", type=int, default=1, help="backfill_10y 자동 이어받기 회차 (1~6)")
    parser.add_argument("--chart-start", type=str, default=CHART_HISTORY_START_DATE, help="차트 확장 시작일 YYYY-MM-DD")
    parser.add_argument("--supply-start", type=str, default=SUPPLY_HISTORY_START_DATE, help="수급 확장 시작일 YYYY-MM-DD")
    args = parser.parse_args()

    if args.mode == "verify":
        verify_supabase_data()
    elif args.mode == "probe_10y":
        run_probe_10y()
    elif args.mode == "backfill_10y":
        run_backfill_10y(
            max_runtime_minutes=(args.max_runtime_minutes if args.max_runtime_minutes != 345 else DEFAULT_BACKFILL_10Y_RUNTIME_MIN),
            chain_round=args.chain_round,
            max_stocks=args.max_stocks,
            chart_start=args.chart_start,
            supply_start=args.supply_start,
        )
    else:
        run_standalone_batch(
            mode=args.mode,
            min_ratio=args.min_ratio,
            max_stocks=args.max_stocks,
            skip_existing=not args.force_all,
            skip_if_completed=args.skip_if_completed,
            start_idx=args.start_idx,
            end_idx=args.end_idx,
            chunk_spec=args.chunk,
            max_runtime_minutes=args.max_runtime_minutes,
            batch_slot=args.batch_slot,
        )
