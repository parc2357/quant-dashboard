"""CAN SLIM 7기준 채점 + 차트 점수 + 랭킹.

CAN SLIM은 윌리엄 오닐의 성장주 선별 모델이다. 원문 기준을 이 대시보드가
확보한 데이터로 판정 가능한 형태로 옮겼다. 판정에 필요한 데이터가 없으면
False가 아니라 None으로 두어 '충족 못함'과 '알 수 없음'을 구분한다.
"""

import fetch

QUARTER_GROWTH_THRESHOLD = 25.0  # C 기준: 분기 이익 YoY +25%
ANNUAL_GROWTH_THRESHOLD = 25.0   # A 기준: 연간 이익 YoY +25%


# ---------------------------------------------------------------------------
# 재무 데이터에서 성장률 뽑기
# ---------------------------------------------------------------------------


def _kr_growth(fin):
    """한국 분기 재무에서 EPS YoY와 4분기 합계 YoY를 계산한다.

    컬럼 키가 '202606' 형식이라 4를 빼면 바로 전년 동기가 된다.
    """
    if not fin:
        return None, None
    eps = fin.get("EPS") or {}
    keys = sorted(k for k in eps if len(k) == 6 and k.isdigit())
    if not keys:
        return None, None

    q_yoy = None
    latest = keys[-1]
    prev_year = str(int(latest) - 100)  # 202606 → 202506
    if prev_year in eps and eps[prev_year] != 0:
        base = abs(eps[prev_year])
        if base > 0:
            q_yoy = (eps[latest] - eps[prev_year]) / base * 100.0

    a_yoy = None
    if len(keys) >= 8:
        recent4 = sum(eps[k] for k in keys[-4:])
        prior4 = sum(eps[k] for k in keys[-8:-4])
        if prior4 != 0:
            a_yoy = (recent4 - prior4) / abs(prior4) * 100.0
    return q_yoy, a_yoy


def _us_growth(quarter, annual):
    """미국은 EPS 대신 당기순이익 YoY를 쓴다(네이버가 제공하는 항목)."""
    q_yoy = None
    if quarter:
        ni = quarter.get("당기순이익") or {}
        keys = sorted(ni.keys())
        if len(keys) >= 5:
            latest, year_ago = keys[-1], keys[-5]
            if ni.get(year_ago):
                base = abs(ni[year_ago])
                if base > 0:
                    q_yoy = (ni[latest] - ni[year_ago]) / base * 100.0

    a_yoy = None
    if annual:
        ni = annual.get("당기순이익") or {}
        keys = sorted(ni.keys())
        if len(keys) >= 2 and ni.get(keys[-2]):
            base = abs(ni[keys[-2]])
            if base > 0:
                a_yoy = (ni[keys[-1]] - ni[keys[-2]]) / base * 100.0
    return q_yoy, a_yoy


def load_fundamentals(ticker, market):
    """분기·연간 성장률. (분기 YoY %, 연간 YoY %, 라벨)

    한국은 EPS가 분기별로 제공되고, 미국은 EPS 대신 당기순이익만 나온다.
    """
    if market == "KR":
        q, a = _kr_growth(fetch.naver_kr_finance_quarter(ticker))
        return q, a, "EPS"

    quarter = _parse_rows(
        fetch.get_json(
            f"https://api.stock.naver.com/stock/{ticker}/finance/quarter",
            key=f"usq{ticker}",
        )
    )
    q, a = _us_growth(quarter, fetch.naver_us_finance(ticker))
    return q, a, "순이익"


def _parse_rows(d):
    """네이버 재무 응답의 rowList를 {지표명: {기간: 값}}으로."""
    if not d:
        return None
    out = {}
    for r in d.get("rowList") or []:
        t = r.get("title")
        title = (t.get("name") if isinstance(t, dict) else t) or ""
        title = title.strip()
        vals = {}
        for k, v in (r.get("columns") or {}).items():
            num = fetch.to_float(v.get("value") if isinstance(v, dict) else v)
            if num is not None:
                vals[k] = num
        if title:
            out[title] = vals
    return out or None


# ---------------------------------------------------------------------------
# 채점
# ---------------------------------------------------------------------------


def canslim_score(a, q_yoy, a_yoy, growth_label, rs_pct, market_uptrend):
    """CAN SLIM 7기준. 각 항목은 (충족여부, 설명문)."""
    hi = a.get("high52") or {}
    surge = a.get("volume_surge_days")
    accum = a.get("accumulation")

    if isinstance(accum, tuple):  # 한국: (상승여부, 변화폭)
        accum_ok, accum_delta = accum
        accum_txt = (
            f"외국인 소진율 20일 {'상승' if accum_ok else '하락'} ({accum_delta:+.2f}%p)"
            if accum_ok is not None else "외국인 수급 데이터 없음"
        )
    else:
        accum_ok = accum
        accum_txt = (
            f"OBV(자금흐름) 20일 {'상승' if accum_ok else '하락'}"
            if accum_ok is not None else "자금흐름 데이터 없음"
        )

    items = [
        ("C", "최근 분기 이익 급증",
         None if q_yoy is None else q_yoy >= QUARTER_GROWTH_THRESHOLD,
         f"분기 {growth_label} YoY {q_yoy:+.1f}%" if q_yoy is not None else f"분기 {growth_label} 데이터 없음"),
        ("A", "연간 이익 성장",
         None if a_yoy is None else a_yoy >= ANNUAL_GROWTH_THRESHOLD,
         f"연간 {growth_label} YoY {a_yoy:+.1f}%" if a_yoy is not None else f"연간 {growth_label} 데이터 없음"),
        ("N", "신고가 근접",
         None if not hi else hi["pct_of_high"] >= 85.0,
         f"52주 고가의 {hi['pct_of_high']:.0f}% 수준" if hi else "52주 데이터 없음"),
        ("S", "수급(거래량 급증)",
         None if surge is None else surge >= 1,
         f"최근 20일 중 거래량 급증 {surge}일" if surge is not None else "거래량 데이터 부족"),
        ("L", "주도주(상대강도)",
         None if rs_pct is None else rs_pct <= 20.0,
         f"12개월 수익률 상위 {rs_pct:.0f}%" if rs_pct is not None else "상대강도 산출 불가"),
        ("I", "기관·외국인 매집", accum_ok, accum_txt),
        ("M", "시장 방향",
         market_uptrend,
         "시장 지수가 200일선 위" if market_uptrend else "시장 지수가 200일선 아래"),
    ]
    passed = sum(1 for _, _, ok, _ in items if ok)
    return {"items": items, "passed": passed, "total": len(items)}


CHART_WEIGHTS = {
    "weekly_order": 3.0,
    "weekly_cross": 2.5,
    "cup_handle": 3.0,
    "daily_order": 2.0,
    "daily_cross": 1.5,
    "big_candle": 1.5,
    "volume": 1.0,
    "breakout": 1.0,
    "minervini": 2.0,
}


def chart_score(a):
    """차트 조건 점수와 한국어 근거 문장 목록."""
    pts = 0.0
    reasons = []

    if a.get("weekly_perfect_order"):
        pts += CHART_WEIGHTS["weekly_order"]
        reasons.append("주봉 4·13·26·52주 정배열")

    wc = a.get("weekly_golden_cross")
    if wc:
        pts += CHART_WEIGHTS["weekly_cross"]
        reasons.append(f"주봉 4주-13주 골든크로스 ({wc}주 전)")

    cup = a.get("cup_handle")
    if cup:
        pts += CHART_WEIGHTS["cup_handle"]
        reasons.append(
            f"컵앤핸들 완성 (컵 깊이 {cup['depth']:.0f}%, 핸들 {cup['handle_depth']:.0f}%, "
            f"돌파선까지 {cup['pct_to_pivot']:+.1f}%)"
        )

    if a.get("daily_perfect_order"):
        pts += CHART_WEIGHTS["daily_order"]
        reasons.append("일봉 5·20·60·120일 정배열")

    dc = a.get("daily_golden_cross")
    if dc:
        pts += CHART_WEIGHTS["daily_cross"]
        reasons.append(f"일봉 20일-60일 골든크로스 ({dc}일 전)")

    bc = a.get("big_candle")
    if bc:
        kind, body_mult, vol_mult = bc
        pts += CHART_WEIGHTS["big_candle"] if kind == "양봉" else -CHART_WEIGHTS["big_candle"]
        reasons.append(
            f"장대{kind} 출현 (몸통 평균의 {body_mult:.1f}배, 거래량 {vol_mult:.1f}배)"
        )

    vr = a.get("volume_ratio")
    if vr and vr >= 2.0:
        pts += CHART_WEIGHTS["volume"]
        reasons.append(f"당일 거래량 50일 평균의 {vr:.1f}배")

    if a.get("breakout_20d"):
        pts += CHART_WEIGHTS["breakout"]
        reasons.append("20일 신고가 돌파")

    mv = a.get("minervini")
    if mv:
        if mv["passed"] >= 7:
            pts += CHART_WEIGHTS["minervini"]
        elif mv["passed"] >= 6:
            pts += CHART_WEIGHTS["minervini"] / 2
        if mv["passed"] >= 6:
            reasons.append(f"미네르비니 추세 템플릿 {mv['passed']}/{mv['total']} 충족")

    return pts, reasons


def total_score(cs, chart_pts):
    """CAN SLIM 충족 개수와 차트 점수를 합산한다.

    사용자가 지목한 최우선 기준이 CAN SLIM 3개 이상 + 차트 조건이므로
    CAN SLIM 한 개당 1.5점을 주어 두 축의 비중을 비슷하게 맞췄다.
    """
    return cs["passed"] * 1.5 + chart_pts
