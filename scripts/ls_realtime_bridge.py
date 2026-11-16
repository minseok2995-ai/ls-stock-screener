#!/usr/bin/env python3
"""LS증권 Open API 로컬 실시간 시세 브릿지 (STRATEGY.md 11.2절 Tier 1).

- 표준 라이브러리만 사용, 127.0.0.1:8765 루프백 전용 바인딩.
- 인증 정보는 환경변수 LS_APP_KEY / LS_APP_SECRET 로만 읽는다 (코드·DB 저장 금지).
- 엔드포인트: GET /health, GET /quote?codes=003570,064960, GET /stream?code=003570&market=KOSPI (SSE)
- 모든 응답/OPTIONS 에 CORS 및 Private Network Access 헤더 포함.
"""
import json
import os
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST, PORT = "127.0.0.1", 8765
LS_BASE = "https://openapi.ls-sec.co.kr:8080"
CACHE_TTL = 1.5

_token = {"value": "", "exp": 0.0}
_cache = {}
_lock = threading.Lock()

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Private-Network": "true",
}


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def get_token():
    now = time.time()
    with _lock:
        if _token["value"] and now < _token["exp"]:
            return _token["value"]
        key, secret = os.environ.get("LS_APP_KEY", ""), os.environ.get("LS_APP_SECRET", "")
        if not key or not secret:
            raise RuntimeError("LS_APP_KEY / LS_APP_SECRET 환경변수가 설정되지 않았습니다")
        data = urllib.parse.urlencode({
            "grant_type": "client_credentials", "appkey": key, "appsecretkey": secret, "scope": "oob",
        }).encode()
        req = urllib.request.Request(LS_BASE + "/oauth2/token", data=data,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=8) as r:
            body = json.loads(r.read().decode("utf-8"))
        _token["value"] = body.get("access_token", "")
        _token["exp"] = now + max(60, int(body.get("expires_in", 3600)) - 120)
        return _token["value"]


def _kst_now():
    return time.gmtime(time.time() + 9 * 3600)


def _market_state(now=None):
    """[ISSUE-021] 평일 08:50~18:00 KST에만 OPEN, 그 외 CLOSE."""
    n = now or _kst_now()
    hm = n.tm_hour * 60 + n.tm_min
    return "OPEN" if n.tm_wday < 5 and 8 * 60 + 50 <= hm <= 18 * 60 else "CLOSE"


def _kst_trade_date(now_ts=None):
    """[ISSUE-021] 토/일 및 평일 09:00 KST 이전에는 직전 평일 날짜."""
    ts = (now_ts if now_ts is not None else time.time()) + 9 * 3600
    n = time.gmtime(ts)
    back = 0
    if n.tm_wday == 5:
        back = 1
    elif n.tm_wday == 6:
        back = 2
    elif n.tm_hour * 60 + n.tm_min < 9 * 60:
        back = 3 if n.tm_wday == 0 else 1
    return time.strftime("%Y-%m-%d", time.gmtime(ts - back * 86400))


def fetch_t1102(shcode):
    token = get_token()
    payload = json.dumps({"t1102InBlock": {"shcode": shcode}}).encode()
    req = urllib.request.Request(LS_BASE + "/stock/market-data", data=payload, headers={
        "Content-Type": "application/json; charset=UTF-8", "authorization": "Bearer " + token,
        "tr_cd": "t1102", "tr_cont": "N", "tr_cont_key": "",
    })
    with urllib.request.urlopen(req, timeout=8) as r:
        out = json.loads(r.read().decode("utf-8")).get("t1102OutBlock", {})
    sign = str(out.get("sign", "3"))
    diff = abs(_num(out.get("change")))
    s = -1 if sign in ("4", "5") else (0 if sign == "3" else 1)
    return {
        "shcode": shcode,
        "tradeDate": _kst_trade_date(),
        "price": _num(out.get("price")), "open": _num(out.get("open")),
        "high": _num(out.get("high")), "low": _num(out.get("low")),
        "volume": _num(out.get("volume")), "prevClose": _num(out.get("jnilclose")),
        "prevVolume": _num(out.get("jnilvolume")), "diff": s * diff,
        "changeRate": s * abs(_num(out.get("diff"))), "marketState": _market_state(), "source": "ls-bridge",
        "updatedAt": int(time.time() * 1000),
    }


def cached_quote(shcode):
    now = time.time()
    hit = _cache.get(shcode)
    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]
    q = fetch_t1102(shcode)
    _cache[shcode] = (now, q)
    return q


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("[bridge] " + fmt % args + "\n")

    def _send(self, code, obj, ctype="application/json; charset=utf-8"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(u.query)
        try:
            if u.path == "/health":
                return self._send(200, {"ok": True, "configured": bool(os.environ.get("LS_APP_KEY") and os.environ.get("LS_APP_SECRET"))})
            if u.path == "/quote":
                codes = [c for c in (qs.get("codes", [""])[0]).split(",") if c.strip()][:30]
                quotes = []
                for c in codes:
                    try:
                        quotes.append(cached_quote(c.strip()))
                    except Exception as e:  # 종목별 실패는 건너뛴다
                        sys.stderr.write("[bridge] quote 실패 %s: %s\n" % (c, e))
                return self._send(200, {"ok": True, "quotes": quotes})
            if u.path == "/stream":
                return self._stream((qs.get("code", [""])[0]).strip())
            return self._send(404, {"ok": False, "error": "not found"})
        except Exception as e:
            return self._send(500, {"ok": False, "error": str(e)})

    def _stream(self, code):
        if not code:
            return self._send(400, {"ok": False, "error": "code required"})
        self.send_response(200)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            while True:
                try:
                    data = json.dumps(cached_quote(code), ensure_ascii=False)
                except Exception as e:
                    data = json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
                self.wfile.write(("data: " + data + "\n\n").encode("utf-8"))
                self.wfile.flush()
                time.sleep(CACHE_TTL)
        except (BrokenPipeError, ConnectionResetError):
            return


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print("LS 실시간 브릿지 시작: http://%s:%d (Ctrl+C 종료)" % (HOST, PORT))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
