"""차트 지표 계산. 입력은 모두 과거→현재 순서의 일봉 리스트.

일봉 dict: {"date": "20260730", "o","h","l","c","v", (한국은) "frgn"}
"""

import statistics


def closes(bars):
    return [b["c"] for b in bars]


def sma(values, n):
    """이동평균 시계열. 데이터가 모자란 앞부분은 None."""
    if n <= 0:
        return []
    out = [None] * len(values)
    total = 0.0
    for i, v in enumerate(values):
        total += v
        if i >= n:
            total -= values[i - n]
        if i >= n - 1:
            out[i] = total / n
    return out


def last_sma(values, n):
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def to_weekly(bars):
    """일봉을 주봉으로 합성. ISO 주 단위로 묶는다."""
    import datetime as _dt

    buckets = {}
    order = []
    for b in bars:
        try:
            d = _dt.datetime.strptime(b["date"], "%Y%m%d").date()
        except ValueError:
            continue
        y, w, _ = d.isocalendar()
        key = (y, w)
        if key not in buckets:
            buckets[key] = {"date": b["date"], "o": b["o"], "h": b["h"], "l": b["l"],
                            "c": b["c"], "v": b["v"]}
            order.append(key)
        else:
            wk = buckets[key]
            wk["h"] = max(wk["h"], b["h"])
            wk["l"] = min(wk["l"], b["l"])
            wk["c"] = b["c"]
            wk["v"] += b["v"]
            wk["date"] = b["date"]
    return [buckets[k] for k in order]


# ---------------------------------------------------------------------------
# 정배열 / 골든크로스
# ---------------------------------------------------------------------------


def perfect_order(values, periods):
    """정배열: 짧은 이동평균이 긴 이동평균보다 순서대로 위에 있는지."""
    mas = []
    for n in periods:
        m = last_sma(values, n)
        if m is None:
            return None
        mas.append(m)
    return all(mas[i] > mas[i + 1] for i in range(len(mas) - 1)), mas


def golden_cross(values, short, long_, lookback):
    """최근 lookback 구간 안에서 단기선이 장기선을 상향 돌파했는지.

    돌파 시점까지 몇 봉 전인지 함께 돌려준다. None이면 판정 불가.
    """
    s = sma(values, short)
    l = sma(values, long_)
    n = len(values)
    if n < long_ + 2:
        return None
    for back in range(1, min(lookback, n - long_ - 1) + 1):
        i = n - back
        j = i - 1
        if s[i] is None or l[i] is None or s[j] is None or l[j] is None:
            continue
        if s[j] <= l[j] and s[i] > l[i]:
            return back
    return None


# ---------------------------------------------------------------------------
# 거래량 / 캔들
# ---------------------------------------------------------------------------


def volume_ratio(bars, n=50):
    """당일 거래량 / 직전 n일 평균 거래량."""
    if len(bars) < n + 1:
        return None
    prev = [b["v"] for b in bars[-(n + 1):-1]]
    avg = sum(prev) / len(prev)
    if avg <= 0:
        return None
    return bars[-1]["v"] / avg


def volume_surge_recent(bars, window=20, avg_n=50, threshold=1.5):
    """최근 window일 중 거래량이 평균의 threshold배를 넘은 날 수."""
    if len(bars) < avg_n + window:
        return None
    count = 0
    for i in range(len(bars) - window, len(bars)):
        prev = [b["v"] for b in bars[i - avg_n:i]]
        avg = sum(prev) / len(prev) if prev else 0
        if avg > 0 and bars[i]["v"] / avg >= threshold:
            count += 1
    return count


def big_candle(bars, avg_n=20, body_mult=2.5, vol_mult=2.0):
    """장대양봉/음봉 판정.

    몸통이 최근 평균 몸통의 body_mult배 이상이고 거래량도 vol_mult배 이상일 때.
    ('양봉', 배수) / ('음봉', 배수) / None
    """
    if len(bars) < avg_n + 1:
        return None
    bodies = [abs(b["c"] - b["o"]) for b in bars[-(avg_n + 1):-1]]
    avg_body = sum(bodies) / len(bodies) if bodies else 0
    cur = bars[-1]
    body = abs(cur["c"] - cur["o"])
    if avg_body <= 0 or body < avg_body * body_mult:
        return None
    vr = volume_ratio(bars)
    if vr is None or vr < vol_mult:
        return None
    return ("양봉" if cur["c"] >= cur["o"] else "음봉", body / avg_body, vr)


# ---------------------------------------------------------------------------
# 위치 / 강도
# ---------------------------------------------------------------------------


def high52_position(bars, days=252):
    """52주 고가 대비 현재 위치(%)와 52주 저가 대비 상승률(%)."""
    window = bars[-days:] if len(bars) >= days else bars
    if not window:
        return None
    hi = max(b["h"] for b in window)
    lo = min(b["l"] for b in window)
    cur = bars[-1]["c"]
    if hi <= 0 or lo <= 0:
        return None
    return {
        "high": hi,
        "low": lo,
        "pct_of_high": cur / hi * 100.0,
        "pct_above_low": (cur / lo - 1.0) * 100.0,
    }


def rsi(bars, n=14):
    c = closes(bars)
    if len(c) < n + 1:
        return None
    gains, losses = [], []
    for i in range(len(c) - n, len(c)):
        diff = c[i] - c[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    ag = sum(gains) / n
    al = sum(losses) / n
    if al == 0:
        return 100.0
    rs = ag / al
    return 100.0 - (100.0 / (1.0 + rs))


def atr_pct(bars, n=14):
    """ATR을 현재가 대비 %로. 변동성 크기 감각용."""
    if len(bars) < n + 1:
        return None
    trs = []
    for i in range(len(bars) - n, len(bars)):
        prev_c = bars[i - 1]["c"]
        tr = max(bars[i]["h"] - bars[i]["l"], abs(bars[i]["h"] - prev_c),
                 abs(bars[i]["l"] - prev_c))
        trs.append(tr)
    cur = bars[-1]["c"]
    if cur <= 0:
        return None
    return sum(trs) / n / cur * 100.0


def ret_pct(bars, days):
    """days 거래일 전 대비 수익률(%)."""
    if len(bars) < days + 1:
        return None
    old = bars[-(days + 1)]["c"]
    if old <= 0:
        return None
    return (bars[-1]["c"] / old - 1.0) * 100.0


def realized_vol(bars, n=20):
    """연율화 실현변동성(%). VKOSPI 대체용."""
    c = closes(bars)
    if len(c) < n + 1:
        return None
    rets = []
    for i in range(len(c) - n, len(c)):
        if c[i - 1] > 0:
            rets.append(c[i] / c[i - 1] - 1.0)
    if len(rets) < 2:
        return None
    return statistics.stdev(rets) * (252 ** 0.5) * 100.0


def obv_trend(bars, n=20):
    """OBV(누적 거래량 흐름)가 최근 n일 동안 오르고 있는지.

    기관 매집을 간접적으로 보는 지표. 미국 종목에서 외국인 소진율 대체로 쓴다.
    """
    if len(bars) < n + 2:
        return None
    obv = 0.0
    series = []
    for i in range(1, len(bars)):
        if bars[i]["c"] > bars[i - 1]["c"]:
            obv += bars[i]["v"]
        elif bars[i]["c"] < bars[i - 1]["c"]:
            obv -= bars[i]["v"]
        series.append(obv)
    if len(series) < n + 1:
        return None
    return series[-1] > series[-(n + 1)]


def foreign_trend(bars, n=20):
    """한국 종목의 외국인 소진율이 최근 n일 동안 올랐는지."""
    vals = [b.get("frgn") for b in bars if b.get("frgn") is not None]
    if len(vals) < n + 1:
        return None
    return vals[-1] > vals[-(n + 1)], vals[-1] - vals[-(n + 1)]


def breakout_20d(bars):
    """당일 종가가 직전 20일 최고가를 넘었는지(신고가 돌파)."""
    if len(bars) < 22:
        return None
    prior_high = max(b["h"] for b in bars[-21:-1])
    return bars[-1]["c"] > prior_high


# ---------------------------------------------------------------------------
# 컵앤핸들 근사 탐지
# ---------------------------------------------------------------------------


def cup_with_handle(bars, days=252):
    """컵앤핸들 근사 탐지.

    엄격한 패턴 인식이 아니라 오닐이 말한 형태의 핵심 조건을 순서대로 확인한다:
      1) 52주 안에 좌측 고점이 있다
      2) 거기서 15~35% 조정을 받았다 (컵 바닥)
      3) 다시 올라 좌측 고점의 90% 이상을 회복했다 (컵 우측)
      4) 회복 후 3~15% 소폭 눌림이 있다 (핸들)
      5) 현재가가 핸들 고점의 95% 이상이다 (돌파 임박)

    조건 충족 시 세부 수치를 담은 dict, 아니면 None.
    """
    w = bars[-days:] if len(bars) >= days else bars
    if len(w) < 60:
        return None

    highs = [b["h"] for b in w]
    lows = [b["l"] for b in w]

    # 1) 좌측 고점: 최근 15% 구간은 제외해야 '이후 전개'를 볼 수 있다.
    search_end = int(len(w) * 0.85)
    if search_end < 20:
        return None
    left_i = max(range(search_end), key=lambda i: highs[i])
    left_high = highs[left_i]
    if left_high <= 0:
        return None

    # 2) 컵 바닥
    after = range(left_i + 1, len(w))
    if len(list(after)) < 20:
        return None
    bottom_i = min(after, key=lambda i: lows[i])
    bottom = lows[bottom_i]
    depth = (1.0 - bottom / left_high) * 100.0
    if not (15.0 <= depth <= 40.0):
        return None

    # 3) 컵 우측: 바닥 이후 좌측 고점의 90% 이상 회복
    right = range(bottom_i + 1, len(w))
    if len(list(right)) < 8:
        return None
    right_i = max(right, key=lambda i: highs[i])
    right_high = highs[right_i]
    if right_high < left_high * 0.90:
        return None

    # 4) 핸들: 우측 고점 이후 소폭 눌림
    handle = list(range(right_i + 1, len(w)))
    if len(handle) < 3:
        return None
    handle_low = min(lows[i] for i in handle)
    handle_depth = (1.0 - handle_low / right_high) * 100.0
    if not (2.0 <= handle_depth <= 18.0):
        return None

    # 5) 현재가가 돌파 임박 위치인지
    cur = w[-1]["c"]
    if cur < right_high * 0.93:
        return None

    return {
        "depth": depth,
        "handle_depth": handle_depth,
        "pivot": right_high,
        "pct_to_pivot": (right_high / cur - 1.0) * 100.0,
        "handle_bars": len(handle),
    }


# ---------------------------------------------------------------------------
# 미네르비니 트렌드 템플릿 (8조건)
# ---------------------------------------------------------------------------


def minervini_template(bars):
    """마크 미네르비니의 추세 템플릿. 충족 개수와 항목별 결과를 돌려준다."""
    c = closes(bars)
    if len(c) < 200:
        return None
    ma50 = last_sma(c, 50)
    ma150 = last_sma(c, 150)
    ma200 = last_sma(c, 200)
    ma200_prev = last_sma(c[:-21], 200) if len(c) > 221 else None
    pos = high52_position(bars)
    if None in (ma50, ma150, ma200) or pos is None:
        return None
    cur = c[-1]
    checks = {
        "주가가 150일·200일선 위": cur > ma150 and cur > ma200,
        "150일선이 200일선 위": ma150 > ma200,
        "200일선이 1개월 전보다 상승": ma200_prev is not None and ma200 > ma200_prev,
        "50일선이 150일·200일선 위": ma50 > ma150 and ma50 > ma200,
        "주가가 50일선 위": cur > ma50,
        "52주 저가 대비 30% 이상 상승": pos["pct_above_low"] >= 30.0,
        "52주 고가의 75% 이상": pos["pct_of_high"] >= 75.0,
        "상대강도 양호(12개월 수익률 > 0)": (ret_pct(bars, 252) or -1) > 0,
    }
    return {"passed": sum(1 for v in checks.values() if v), "total": len(checks),
            "checks": checks}


# ---------------------------------------------------------------------------
# 종합
# ---------------------------------------------------------------------------


def analyze(bars, market):
    """일봉에서 뽑을 수 있는 모든 지표를 한 번에 계산한다."""
    if not bars or len(bars) < 60:
        return None
    c = closes(bars)
    weekly = to_weekly(bars)
    wc = closes(weekly)

    daily_order = perfect_order(c, [5, 20, 60, 120])
    weekly_order = perfect_order(wc, [4, 13, 26, 52])

    res = {
        "last": bars[-1],
        "price": c[-1],
        "prev_close": c[-2] if len(c) > 1 else None,
        "bars": bars,
        "weekly": weekly,
        "ma": {n: last_sma(c, n) for n in (5, 20, 60, 120, 200)},
        "wma": {n: last_sma(wc, n) for n in (4, 13, 26, 52)},
        "daily_perfect_order": daily_order[0] if daily_order else None,
        "weekly_perfect_order": weekly_order[0] if weekly_order else None,
        "daily_golden_cross": golden_cross(c, 20, 60, lookback=20),
        "weekly_golden_cross": golden_cross(wc, 4, 13, lookback=10),
        "volume_ratio": volume_ratio(bars),
        "volume_surge_days": volume_surge_recent(bars),
        "big_candle": big_candle(bars),
        "high52": high52_position(bars),
        "rsi": rsi(bars),
        "atr_pct": atr_pct(bars),
        "ret_1m": ret_pct(bars, 21),
        "ret_3m": ret_pct(bars, 63),
        "ret_6m": ret_pct(bars, 126),
        "ret_12m": ret_pct(bars, 252),
        "cup_handle": cup_with_handle(bars),
        "minervini": minervini_template(bars),
        "breakout_20d": breakout_20d(bars),
    }
    if market == "KR":
        res["accumulation"] = foreign_trend(bars)
    else:
        res["accumulation"] = obv_trend(bars)
    return res
