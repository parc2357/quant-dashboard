"""네트워크 접근의 단일 관문.

원칙:
- 브라우저 User-Agent 없이는 네이버가 차단하므로 항상 부착한다.
- 응답은 cache/YYYY-MM-DD/ 아래 저장한다. 재실행이 1분 안에 끝나고,
  데모 중 API가 흔들려도 직전 값으로 화면이 뜬다.
- 실패는 예외를 던지지 않고 None을 반환한다. 한 항목 때문에 대시보드 전체가
  죽는 일이 없어야 한다.
"""

import csv
import hashlib
import io
import json
import os
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache")

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Referer": "https://m.stock.naver.com/",
}

# --dry-run 이면 네트워크를 완전히 차단하고 캐시만 사용한다.
DRY_RUN = "--dry-run" in sys.argv
# 캐시를 무시하고 새로 받는다.
NO_CACHE = "--no-cache" in sys.argv

_ssl_ctx = ssl.create_default_context()
_print_lock = threading.Lock()
_stats = {"net": 0, "cache": 0, "fail": 0}


def log(msg):
    with _print_lock:
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()


def _cache_path(key):
    """캐시는 오늘 날짜 폴더에 둔다. 파일명이 안전하도록 해시를 덧붙인다."""
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)[:80]
    digest = hashlib.md5(key.encode()).hexdigest()[:8]
    day = date.today().isoformat()
    return os.path.join(CACHE_DIR, day, f"{safe}.{digest}.json")


def _cache_read(key):
    """오늘 캐시가 없으면 최근 7일을 거슬러 찾는다.

    데모 중 네트워크가 끊겨도 며칠 전 값으로라도 화면이 뜨게 하는 안전장치다.
    stale=True 로 표시해 호출부가 알 수 있게 한다.
    """
    for back in range(0, 8):
        day = (date.today() - timedelta(days=back)).isoformat()
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)[:80]
        digest = hashlib.md5(key.encode()).hexdigest()[:8]
        p = os.path.join(CACHE_DIR, day, f"{safe}.{digest}.json")
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f), back > 0
            except (ValueError, OSError):
                continue
    return None, False


def _cache_write(key, payload):
    p = _cache_path(key)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    os.replace(tmp, p)


def raw(url, key=None, retries=2, timeout=12):
    """URL을 문자열로 받아온다. 실패 시 None."""
    key = key or url
    if not NO_CACHE:
        cached, stale = _cache_read(key)
        if cached is not None:
            _stats["cache"] += 1
            return cached
    if DRY_RUN:
        _stats["fail"] += 1
        return None

    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx) as r:
                body = r.read().decode("utf-8", "replace")
            _stats["net"] += 1
            _cache_write(key, body)
            return body
        except Exception as e:  # HTTPError, URLError, socket.timeout 모두 포함
            last = e
            if attempt < retries:
                time.sleep(0.4 * (attempt + 1))
    _stats["fail"] += 1
    log(f"  [실패] {key}: {type(last).__name__} {str(last)[:60]}")
    return None


def get_json(url, key=None, retries=2):
    body = raw(url, key=key, retries=retries)
    if body is None:
        return None
    try:
        return json.loads(body)
    except ValueError:
        log(f"  [JSON 파싱 실패] {key or url}")
        return None


def parallel(jobs, workers=8):
    """jobs: {이름: 인자 없는 함수}. 결과 dict를 돌려준다. 개별 실패는 None."""
    out = {}

    def run(item):
        name, fn = item
        try:
            return name, fn()
        except Exception as e:
            log(f"  [예외] {name}: {type(e).__name__} {str(e)[:60]}")
            return name, None

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for name, val in ex.map(run, list(jobs.items())):
            out[name] = val
    return out


def stats_line():
    return (
        f"네트워크 {_stats['net']}건 · 캐시 {_stats['cache']}건 · 실패 {_stats['fail']}건"
    )


# ---------------------------------------------------------------------------
# 네이버 금융
# ---------------------------------------------------------------------------

API = "https://api.stock.naver.com"
MAPI = "https://m.stock.naver.com/api"


def naver_index(code):
    """해외 지수. code 예: .DJI .INX .IXIC .SOX .VIX"""
    return get_json(f"{API}/index/{urllib.parse.quote(code)}/basic", key=f"index{code}")


def naver_domestic_index(code):
    """국내 지수. code: KOSPI / KOSDAQ"""
    d = get_json(
        f"https://polling.finance.naver.com/api/realtime/domestic/index/{code}",
        key=f"dindex{code}",
    )
    if not d:
        return None
    datas = d.get("datas") or []
    return datas[0] if datas else None


def naver_stock(ticker):
    """미국 종목/ETF 현재가. ETF는 접미사 없는 티커, 나스닥 종목은 .O"""
    return get_json(f"{API}/stock/{urllib.parse.quote(ticker)}/basic", key=f"stk{ticker}")


def naver_market_majors(category):
    """category: bond / exchange"""
    return get_json(f"{API}/marketindex/majors/{category}", key=f"majors{category}")


def naver_us_daily(ticker, days=420):
    """미국 일봉 OHLCV. [{date, o,h,l,c,v}] 최근순 아님(과거→현재)."""
    end = date.today()
    start = end - timedelta(days=days)
    url = (
        f"{API}/chart/foreign/item/{urllib.parse.quote(ticker)}/day"
        f"?startDateTime={start.strftime('%Y%m%d')}0000"
        f"&endDateTime={end.strftime('%Y%m%d')}0000"
    )
    d = get_json(url, key=f"usday{ticker}")
    if not d or not isinstance(d, list):
        return None
    bars = []
    for row in d:
        try:
            bars.append(
                {
                    "date": str(row["localDate"]),
                    "o": float(row["openPrice"]),
                    "h": float(row["highPrice"]),
                    "l": float(row["lowPrice"]),
                    "c": float(row["closePrice"]),
                    "v": float(row.get("accumulatedTradingVolume") or 0),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return bars or None


def naver_kr_daily(code, days=420):
    """한국 일봉 OHLCV + 외국인 소진율.

    siseJson 응답은 JSON이 아니라 파이썬 리터럴 형태(작은따옴표)라서
    직접 파싱해야 한다.
    """
    end = date.today()
    start = end - timedelta(days=days)
    url = (
        "https://api.finance.naver.com/siseJson.naver?symbol="
        f"{code}&requestType=1&startTime={start.strftime('%Y%m%d')}"
        f"&endTime={end.strftime('%Y%m%d')}&timeframe=day"
    )
    body = raw(url, key=f"krday{code}")
    if not body:
        return None
    bars = []
    for line in body.splitlines():
        line = line.strip().rstrip(",")
        if not line.startswith("[") or "날짜" in line:
            continue
        try:
            parts = json.loads(line.replace("'", '"'))
        except ValueError:
            continue
        if len(parts) < 6:
            continue
        try:
            bars.append(
                {
                    "date": str(parts[0]),
                    "o": float(parts[1]),
                    "h": float(parts[2]),
                    "l": float(parts[3]),
                    "c": float(parts[4]),
                    "v": float(parts[5]),
                    "frgn": float(parts[6]) if len(parts) > 6 and parts[6] is not None else None,
                }
            )
        except (TypeError, ValueError):
            continue
    return bars or None


def naver_us_index_daily(code, days=420):
    """해외 지수 일봉. 종목과 경로만 다르고 응답 형식은 같다."""
    end = date.today()
    start = end - timedelta(days=days)
    url = (
        f"{API}/chart/foreign/index/{urllib.parse.quote(code)}/day"
        f"?startDateTime={start.strftime('%Y%m%d')}0000"
        f"&endDateTime={end.strftime('%Y%m%d')}0000"
    )
    d = get_json(url, key=f"usidx{code}")
    if not d or not isinstance(d, list):
        return None
    bars = []
    for row in d:
        try:
            bars.append(
                {
                    "date": str(row["localDate"]),
                    "o": float(row["openPrice"]),
                    "h": float(row["highPrice"]),
                    "l": float(row["lowPrice"]),
                    "c": float(row["closePrice"]),
                    "v": float(row.get("accumulatedTradingVolume") or 0),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return bars or None


def resolve_us_ticker(ticker):
    """네이버가 쓰는 정확한 코드를 자동완성 API로 찾는다.

    같은 티커라도 상장 거래소에 따라 접미사가 `.O`(나스닥) / `.K`(NYSE·AMEX 일부) /
    없음으로 갈린다. 하드코딩한 접미사가 틀렸을 때만 호출하는 보정 경로다.
    """
    base = ticker.split(".")[0]
    d = get_json(
        f"https://ac.stock.naver.com/ac?q={urllib.parse.quote(base)}"
        "&target=stock%2Cetf",
        key=f"ac{base}",
    )
    for item in (d or {}).get("items") or []:
        if item.get("code", "").upper() == base.upper():
            return item.get("reutersCode") or base
    return None


def naver_marketindex_prices(category, code, size=60):
    """환율/금리 과거 시세. category: exchange / bond

    종가만 있는 단순 시계열이라 [{date, c}] 형태로 돌려준다(과거→현재).
    """
    d = get_json(
        f"{API}/marketindex/{category}/{urllib.parse.quote(code)}/prices"
        f"?page=1&pageSize={size}",
        key=f"mip{category}{code}",
    )
    if not d or not isinstance(d, list):
        return None
    rows = []
    for row in d:
        c = _to_float(row.get("closePrice"))
        day = str(row.get("localTradedAt") or "")[:10].replace("-", "")
        if c is not None and len(day) == 8:
            rows.append({"date": day, "c": c})
    rows.sort(key=lambda r: r["date"])
    return rows or None


def naver_kr_finance_quarter(code):
    """한국 분기 재무. {'EPS': {'202606': 10625.0, ...}, ...}"""
    d = get_json(f"{MAPI}/stock/{code}/finance/quarter", key=f"krfin{code}")
    if not d:
        return None
    info = d.get("financeInfo") or {}
    rows = info.get("rowList") or []
    out = {}
    for r in rows:
        title = (r.get("title") or "").strip()
        cols = r.get("columns") or {}
        vals = {}
        for k, v in cols.items():
            num = _to_float(v.get("value") if isinstance(v, dict) else v)
            if num is not None:
                vals[k] = num
        if title:
            out[title] = vals
    return out or None


def naver_us_finance(ticker):
    """미국 연간 재무. 지표명 → {기간: 값}"""
    d = get_json(f"{API}/stock/{ticker}/finance/annual", key=f"usfin{ticker}")
    if not d:
        return None
    out = {}
    for r in d.get("rowList") or []:
        title = (r.get("title") or {}).get("name") if isinstance(r.get("title"), dict) else r.get("title")
        title = (title or "").strip()
        cols = r.get("columns") or {}
        vals = {}
        for k, v in cols.items():
            num = _to_float(v.get("value") if isinstance(v, dict) else v)
            if num is not None:
                vals[k] = num
        if title:
            out[title] = vals
    return out or None


def naver_kr_universe(market, want=100):
    """시가총액 순 국내 보통주 목록. market: KOSPI / KOSDAQ

    시가총액 목록에는 ETF와 우선주가 섞여 있다. 둘 다 CAN SLIM 대상이 아니므로
    걸러낸다(ETF는 기업 실적이 없고, 우선주는 보통주와 중복이다). 걸러낸 만큼
    더 받아 원하는 개수를 채운다.
    """
    page_size = min(100, want + 20)
    out = []
    page = 1
    while len(out) < want and page <= 4:
        d = get_json(
            f"{MAPI}/stocks/marketValue/{market}?page={page}&pageSize={page_size}",
            key=f"uni{market}{page}x{page_size}",
        )
        stocks = (d or {}).get("stocks") or []
        if not stocks:
            break
        for s in stocks:
            code = s.get("itemCode")
            if not code or s.get("stockEndType") != "stock":
                continue
            if not code.endswith("0"):  # 우선주 제외 (예: 005935 삼성전자우)
                continue
            out.append({"code": code, "name": s.get("stockName") or code})
        page += 1
    return out[:want] or None


# ---------------------------------------------------------------------------
# 미국 재무부 — 30년 국채 (네이버는 10년만 제공)
# ---------------------------------------------------------------------------


def treasury_curve():
    """최근 영업일 국채 커브. {'10 Yr': 4.68, '30 Yr': 5.2, 'date': '07/29/2026'}"""
    year = date.today().year
    url = (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        f"daily-treasury-rates.csv/{year}/all"
        f"?type=daily_treasury_yield_curve&field_tdr_date_value={year}&_format=csv"
    )
    body = raw(url, key=f"treasury{year}", timeout=20)
    if not body:
        return None
    try:
        rows = list(csv.DictReader(io.StringIO(body)))
    except Exception:
        return None
    if not rows:
        return None
    # CSV는 최신순으로 내려온다. 첫 두 행이 있으면 전일 대비까지 만든다.
    def pick(row):
        out = {"date": row.get("Date")}
        for k, v in row.items():
            f = _to_float(v)
            if f is not None:
                out[k.strip()] = f
        return out

    latest = pick(rows[0])
    prev = pick(rows[1]) if len(rows) > 1 else {}
    hist = [pick(r) for r in rows[:70]]
    return {"latest": latest, "prev": prev, "history": list(reversed(hist))}


# ---------------------------------------------------------------------------
# 업비트 — 비트코인
# ---------------------------------------------------------------------------


def upbit_ticker(market="KRW-BTC"):
    d = get_json(
        f"https://api.upbit.com/v1/ticker?markets={market}", key=f"upbit{market}"
    )
    if not d or not isinstance(d, list) or not d:
        return None
    return d[0]


def upbit_daily(market="KRW-BTC", count=200):
    d = get_json(
        f"https://api.upbit.com/v1/candles/days?market={market}&count={count}",
        key=f"upbitday{market}",
    )
    if not d or not isinstance(d, list):
        return None
    bars = []
    for row in reversed(d):  # 최신순 → 과거순
        try:
            bars.append(
                {
                    "date": str(row["candle_date_time_kst"])[:10].replace("-", ""),
                    "o": float(row["opening_price"]),
                    "h": float(row["high_price"]),
                    "l": float(row["low_price"]),
                    "c": float(row["trade_price"]),
                    "v": float(row.get("candle_acc_trade_volume") or 0),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return bars or None


# ---------------------------------------------------------------------------


def _to_float(v):
    """'1,433.80' / '4.6830' / None / '-' 를 float 또는 None으로."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "").replace("%", "").replace("+", "")
    if s in ("", "-", "N/A", "null", "None"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


to_float = _to_float
