#!/usr/bin/env python3
"""데일리 투자 대시보드 생성기.

    python3 daily_dashboard.py              # 수집 후 dashboard.html 생성
    python3 daily_dashboard.py --dry-run    # 캐시만 사용 (네트워크 차단)
    python3 daily_dashboard.py --no-cache   # 캐시 무시하고 새로 받기
    python3 daily_dashboard.py --quick      # 유니버스를 줄여 빠르게 (점검용)

파이썬 표준 라이브러리만 사용한다. 설치할 것이 없다.
"""

import os
import sys
from datetime import datetime

import canslim
import fetch
import indicators as ind
import render
import universe as uni

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(BASE_DIR, "dashboard.html")
ARTIFACT_PATH = os.path.join(BASE_DIR, "dashboard_artifact.html")

QUICK = "--quick" in sys.argv
# 재무 데이터는 차트 점수 상위 종목에만 받는다. 호출 수를 3분의 1로 줄인다.
FUNDAMENTAL_DEPTH = 12 if QUICK else 40
TOP_N = 10

# 접미사가 틀려 자동 보정된 티커. 재무 조회에도 같은 코드를 써야 한다.
TICKER_FIXES = {}


def log(m):
    fetch.log(m)


# ---------------------------------------------------------------------------
# 시계열 도우미
# ---------------------------------------------------------------------------


def series_stats(rows, digits=2):
    """[{date, c}] 또는 일봉에서 현재값·전일대비·1주·1개월·스파크라인을 뽑는다."""
    if not rows:
        return {}
    vals = [r["c"] for r in rows if r.get("c") is not None]
    if not vals:
        return {}
    cur = vals[-1]
    out = {"value": cur, "digits": digits}
    if len(vals) > 1:
        prev = vals[-2]
        out["chg_abs"] = cur - prev
        out["chg_pct"] = (cur / prev - 1.0) * 100.0 if prev else None
    for key, back in (("w1", 5), ("m1", 21)):
        if len(vals) > back:
            old = vals[-(back + 1)]
            out[key + "_abs"] = cur - old  # 금리 표에서 bp로 표시
            if old:
                out[key] = (cur / old - 1.0) * 100.0
    out["_vals"] = vals[-60:]
    return out


def row(name, stats, badge=None, digits=None):
    r = dict(stats)
    r["name"] = name
    if badge:
        r["badge"] = badge
    if digits is not None:
        r["digits"] = digits
    r["spark"] = render.sparkline(stats.get("_vals"), label=name)
    return r


def ret_from(vals, back):
    if not vals or len(vals) <= back:
        return None
    old = vals[-(back + 1)]
    return (vals[-1] / old - 1.0) * 100.0 if old else None


# ---------------------------------------------------------------------------
# PART 1 — 매크로
# ---------------------------------------------------------------------------


def build_macro():
    log("[1/4] 매크로 수집…")

    jobs = {
        "treasury": fetch.treasury_curve,
        "bond_majors": lambda: fetch.naver_market_majors("bond"),
        "fx_majors": lambda: fetch.naver_market_majors("exchange"),
        "kr10_hist": lambda: fetch.naver_marketindex_prices("bond", "KR10YT=RR"),
        "us10_hist": lambda: fetch.naver_marketindex_prices("bond", "US10YT=RR"),
        "dxy_hist": lambda: fetch.naver_marketindex_prices("exchange", ".DXY"),
        "usdkrw_hist": lambda: fetch.naver_marketindex_prices("exchange", "FX_USDKRW"),
        "jpykrw_hist": lambda: fetch.naver_marketindex_prices("exchange", "FX_JPYKRW"),
        "vix": lambda: fetch.naver_us_index_daily(".VIX"),
        "kospi": lambda: fetch.naver_kr_daily("KOSPI"),
        "kosdaq": lambda: fetch.naver_kr_daily("KOSDAQ"),
        "btc": fetch.upbit_daily,
    }
    for label, code in uni.US_INDICES:
        jobs[f"idx{code}"] = (lambda c=code: fetch.naver_us_index_daily(c))
    etf_tickers = (
        [t for _, t, _ in uni.COMMODITY_PROXIES]
        + [t for _, t in uni.THEME_ETFS]
        + [t for _, t in uni.SPDR_SECTORS]
        + [t for _, t in uni.CREDIT_PROXY_ETFS]
        + [t for _, t in uni.CDS_WATCH]
    )
    for t in etf_tickers:
        jobs[f"etf{t}"] = (lambda tk=t: fetch.naver_us_daily(tk))

    d = fetch.parallel(jobs, workers=8)

    # 접미사를 잘못 적었을 가능성에 대비해 네이버가 쓰는 실제 코드를 찾아 재시도한다.
    for t in etf_tickers:
        if d.get(f"etf{t}") is None:
            alt = fetch.resolve_us_ticker(t)
            if alt and alt != t:
                log(f"  {t} 실패 → {alt} 재시도")
                d[f"etf{t}"] = fetch.naver_us_daily(alt)
                TICKER_FIXES[t] = alt

    def bars_stats(key, digits=2):
        return series_stats(d.get(key) or [], digits)

    sections = []

    # ---- 금리 --------------------------------------------------------------
    tc = d.get("treasury") or {}
    latest, prev = tc.get("latest") or {}, tc.get("prev") or {}
    hist = tc.get("history") or []
    rate_rows = []

    def curve_series(tenor):
        """재무부 커브 한 만기를 [{date, c}] 시계열로. series_stats를 그대로 쓰기 위해."""
        return [{"date": h.get("date") or str(i), "c": h[tenor]}
                for i, h in enumerate(hist) if h.get(tenor) is not None]

    us10 = series_stats(d.get("us10_hist") or [], 3)
    if us10:
        rate_rows.append(row("미국 국채 10년", us10, digits=3))
    else:
        st = series_stats(curve_series("10 Yr"), 3)
        if st:
            rate_rows.append(row("미국 국채 10년", st, badge="미 재무부", digits=3))

    st30 = series_stats(curve_series("30 Yr"), 3)
    if st30:
        rate_rows.append(row("미국 국채 30년", st30, badge="미 재무부", digits=3))

    kr10 = series_stats(d.get("kr10_hist") or [], 3)
    if kr10:
        rate_rows.append(row("한국 국채 10년", kr10, digits=3))

    # 파생 스프레드 — 커브 기울기와 한미 금리차는 매크로 판단의 핵심 신호다.
    spread = [{"date": h.get("date") or str(i), "c": h["30 Yr"] - h["10 Yr"]}
              for i, h in enumerate(hist)
              if h.get("30 Yr") is not None and h.get("10 Yr") is not None]
    st_sp = series_stats(spread, 3)
    if st_sp:
        rate_rows.append(row("미국 10-30년 스프레드", st_sp, badge="파생", digits=3))

    # 한미 금리차는 두 시계열을 날짜로 맞춰 뺀다.
    if d.get("kr10_hist") and d.get("us10_hist"):
        us_map = {r["date"]: r["c"] for r in d["us10_hist"]}
        diff = [{"date": r["date"], "c": r["c"] - us_map[r["date"]]}
                for r in d["kr10_hist"] if r["date"] in us_map]
        st_diff = series_stats(diff, 3)
        if st_diff:
            rate_rows.append(row("한국-미국 10년 금리차", st_diff, badge="파생", digits=3))

    sections.append(render.macro_table(
        "금리", rate_rows, note="단위 %, 변화는 bp", change_style="bp"))

    # ---- 환율 --------------------------------------------------------------
    fx_rows = []
    dxy = series_stats(d.get("dxy_hist") or [], 2)
    if dxy:
        fx_rows.append(row("달러 인덱스 (DXY)", dxy))
    usdkrw = series_stats(d.get("usdkrw_hist") or [], 2)
    if usdkrw:
        fx_rows.append(row("달러/원", usdkrw))
    jpykrw = series_stats(d.get("jpykrw_hist") or [], 2)
    if jpykrw:
        fx_rows.append(row("100엔/원", jpykrw))
    # 네이버는 100엔당 원화만 주므로 달러/엔은 나눠서 만든다.
    if usdkrw and jpykrw:
        u = d.get("usdkrw_hist") or []
        j = {r["date"]: r["c"] for r in (d.get("jpykrw_hist") or [])}
        pairs = [{"date": r["date"], "c": r["c"] / (j[r["date"]] / 100.0)}
                 for r in u if r["date"] in j and j[r["date"]]]
        st = series_stats(pairs, 2)
        if st:
            fx_rows.append(row("달러/엔", st, badge="달러원 ÷ (100엔원 ÷ 100)"))

    sections.append(render.macro_table("환율", fx_rows))

    # ---- 변동성 ------------------------------------------------------------
    vol_rows = []
    vix = bars_stats("vix", 2)
    if vix:
        vol_rows.append(row("VIX (미국)", vix))
    kospi_bars = d.get("kospi") or []
    if kospi_bars:
        rv_series = []
        for i in range(max(21, len(kospi_bars) - 60), len(kospi_bars)):
            v = ind.realized_vol(kospi_bars[: i + 1], 20)
            if v is not None:
                rv_series.append({"date": kospi_bars[i]["date"], "c": v})
        st = series_stats(rv_series, 2)
        if st:
            vol_rows.append(row("코스피 20일 실현변동성", st, badge="VKOSPI 대체"))
    sections.append(render.macro_table(
        "변동성", vol_rows, note="한국은 VKOSPI 무료 경로가 없어 실현변동성으로 대체"))

    # ---- 주식지수 ----------------------------------------------------------
    idx_rows = []
    for label, code in uni.US_INDICES:
        st = bars_stats(f"idx{code}", 2)
        if st:
            idx_rows.append(row(label, st, digits=2))
    for label, key in (("코스피", "kospi"), ("코스닥", "kosdaq")):
        st = bars_stats(key, 2)
        if st:
            idx_rows.append(row(label, st))
    sections.append(render.macro_table("주식지수", idx_rows))

    # ---- 원자재 · 암호화폐 -------------------------------------------------
    cm_rows = []
    for label, ticker, fullname in uni.COMMODITY_PROXIES:
        st = bars_stats(f"etf{ticker}", 2)
        if st:
            cm_rows.append(row(label, st, badge=f"ETF 프록시 {ticker}"))
    btc = bars_stats("btc", 0)
    if btc:
        cm_rows.append(row("비트코인 (원화)", btc, badge="업비트", digits=0))
        if usdkrw:
            usd = btc["value"] / usdkrw["value"]
            cm_rows.append(row("비트코인 (달러 환산)", {
                "value": usd, "digits": 0, "chg_pct": btc.get("chg_pct"),
                "w1": btc.get("w1"), "m1": btc.get("m1"),
                "_vals": [v / usdkrw["value"] for v in btc.get("_vals", [])],
            }, badge="파생"))
    sections.append(render.macro_table(
        "원자재 · 암호화폐", cm_rows,
        note="원자재는 네이버 선물 경로가 닫혀 ETF로 대체. "
             "표시된 숫자는 ETF 주가이므로 배럴당 유가·온스당 금값이 아니며, "
             "등락률만 의미가 있습니다"))

    # ---- 지역 · 테마 ETF ---------------------------------------------------
    etf_rows = []
    for label, ticker in uni.THEME_ETFS:
        st = bars_stats(f"etf{ticker}", 2)
        if st:
            etf_rows.append(row(label, st, badge=uni.base_ticker(ticker)))
    sections.append(render.macro_table(
        "지역 · 테마 ETF", etf_rows,
        note='요청서의 "DRAM ETF"는 티커가 특정되지 않아 반도체 ETF로 대체'))

    # ---- SPDR 섹터 히트맵 --------------------------------------------------
    cells = []
    for label, ticker in uni.SPDR_SECTORS:
        bars = d.get(f"etf{ticker}") or []
        vals = [b["c"] for b in bars]
        if len(vals) < 2:
            continue
        cells.append({
            "name": label, "ticker": ticker,
            "d1": ret_from(vals, 1), "w1": ret_from(vals, 5), "m1": ret_from(vals, 21),
        })
    cells.sort(key=lambda c: (c["d1"] is None, -(c["d1"] or 0)))
    sections.append(render.sector_heatmap(
        cells, "SPDR 섹터 ETF", note="1일 등락률 내림차순"))

    # ---- CDS 대용 지표 -----------------------------------------------------
    credit_rows = []
    for label, ticker in uni.CREDIT_PROXY_ETFS:
        st = bars_stats(f"etf{ticker}", 2)
        if st:
            credit_rows.append(row(label, st, badge=ticker))
    hyg = [b["c"] for b in (d.get("etfHYG") or [])]
    ief = [b["c"] for b in (d.get("etfIEF") or [])]
    lqd = [b["c"] for b in (d.get("etfLQD") or [])]
    for label, num, den in (("하이일드/국채 비율 (HYG÷IEF)", hyg, ief),
                            ("우량채/국채 비율 (LQD÷IEF)", lqd, ief)):
        if len(num) > 25 and len(den) > 25:
            n = min(len(num), len(den))
            ratio = [{"date": str(i), "c": num[-n + i] / den[-n + i]}
                     for i in range(n) if den[-n + i]]
            st = series_stats(ratio, 4)
            if st:
                credit_rows.append(row(label, st, badge="하락 = 신용위험 확대", digits=4))
    sections.append(render.macro_table(
        "CDS 대용 지표 — 시장 신용위험", credit_rows,
        note="실제 CDS 스프레드가 아님. 기업별 CDS는 무료 경로가 없습니다"))

    # ---- CDS 관심 기업 -----------------------------------------------------
    watch_rows = []
    for label, ticker in uni.CDS_WATCH:
        bars = d.get(f"etf{ticker}") or []
        st = bars_stats(f"etf{ticker}", 2)
        if not st:
            continue
        rv = ind.realized_vol(bars, 20)
        hi = ind.high52_position(bars)
        st["badge"] = (
            f"변동성 {rv:.0f}%" if rv is not None else ""
        ) + (f" · 52주 고가의 {hi['pct_of_high']:.0f}%" if hi else "")
        watch_rows.append(row(f"{label} ({uni.base_ticker(ticker)})", st))
    sections.append(render.macro_table(
        "CDS 관심 기업 — 주가 · 변동성 · 52주 위치", watch_rows,
        note="CDS 대신 확인 가능한 신용 관련 신호"))

    # 시장 방향(CAN SLIM의 M 기준)에 쓸 값을 함께 돌려준다.
    market_trend = {}
    for market, key in (("KR", "kospi"), ("US", f"idx.INX")):
        bars = d.get(key) or []
        c = [b["c"] for b in bars]
        ma200 = ind.last_sma(c, 200)
        market_trend[market] = bool(ma200 and c and c[-1] > ma200)
    return sections, market_trend


# ---------------------------------------------------------------------------
# PART 2 — 개별종목
# ---------------------------------------------------------------------------


def build_stocks(market_trend):
    log("[2/4] 종목 유니버스 구성…")
    kr = []
    for mkt, size in uni.KR_UNIVERSE_SIZE.items():
        got = fetch.naver_kr_universe(mkt, 20 if QUICK else size) or []
        kr.extend(got)
    us = uni.US_UNIVERSE[:20] if QUICK else uni.US_UNIVERSE
    log(f"  한국 {len(kr)}종목 · 미국 {len(us)}종목")

    log("[3/4] 일봉 수집 및 지표 계산…")
    jobs = {}
    for s in kr:
        jobs[("KR", s["code"], s["name"])] = (
            lambda c=s["code"]: fetch.naver_kr_daily(c, days=520))
    for t in us:
        jobs[("US", t, uni.us_display_name(t))] = (
            lambda tk=t: fetch.naver_us_daily(tk, days=520))

    # dict 키가 튜플이면 fetch.parallel의 items()가 그대로 통과한다.
    bars_map = fetch.parallel(jobs, workers=8)

    # 미국 종목 중 접미사가 틀려 실패한 것은 실제 코드를 찾아 한 번 재시도한다.
    retry = [k for k, v in bars_map.items() if v is None and k[0] == "US"]
    if retry:
        log(f"  미국 {len(retry)}종목 티커 보정 중…")
        for key in retry:
            alt = fetch.resolve_us_ticker(key[1])
            if alt and alt != key[1]:
                bars_map[key] = fetch.naver_us_daily(alt, days=520)
                if bars_map[key]:
                    TICKER_FIXES[key[1]] = alt

    candidates = []
    for (market, ticker, name), bars in bars_map.items():
        if not bars:
            continue
        a = ind.analyze(bars, market)
        if not a:
            continue
        candidates.append({
            "market": market, "ticker": ticker, "name": name, "analysis": a,
        })
    log(f"  지표 계산 완료 {len(candidates)}종목")

    # 상대강도(L 기준)는 유니버스 내 순위라서 전체를 모은 뒤에 계산한다.
    for market in ("KR", "US"):
        group = [c for c in candidates if c["market"] == market]
        ranked = sorted(
            [c for c in group if c["analysis"].get("ret_12m") is not None],
            key=lambda c: -c["analysis"]["ret_12m"],
        )
        n = len(ranked)
        for i, c in enumerate(ranked):
            c["rs_pct"] = (i + 1) / n * 100.0 if n else None
        for c in group:
            c.setdefault("rs_pct", None)

    # 차트 점수를 먼저 매기고, 재무는 상위 종목만 받는다(호출 절약).
    for c in candidates:
        c["chart_pts"], c["chart_reasons"] = canslim.chart_score(c["analysis"])

    log("[4/4] 상위 종목 재무 확인…")
    finals = []
    for market in ("KR", "US"):
        group = sorted(
            [c for c in candidates if c["market"] == market],
            key=lambda c: -c["chart_pts"],
        )[:FUNDAMENTAL_DEPTH]

        fund_jobs = {
            c["ticker"]: (lambda t=TICKER_FIXES.get(c["ticker"], c["ticker"]), m=market:
                          canslim.load_fundamentals(t, m))
            for c in group
        }
        funds = fetch.parallel(fund_jobs, workers=6)

        for c in group:
            q, an, label = funds.get(c["ticker"]) or (None, None, "EPS")
            cs = canslim.canslim_score(
                c["analysis"], q, an, label, c.get("rs_pct"),
                market_trend.get(market, False),
            )
            c["canslim"] = cs
            c["total"] = canslim.total_score(cs, c["chart_pts"])
            c["display_ticker"] = (
                c["ticker"] if market == "KR" else uni.base_ticker(c["ticker"])
            )
            c["tv_url"] = uni.tradingview_url(c["ticker"], market)
            c["naver_url"] = uni.naver_url(c["ticker"], market)
            finals.append(c)

    def pick(market):
        group = [c for c in finals if c["market"] == market]
        # 사용자가 지목한 최우선 기준: CAN SLIM 3개 이상 충족.
        qualified = [c for c in group if c["canslim"]["passed"] >= 3]
        pool = qualified or group
        return sorted(pool, key=lambda c: -c["total"])[:TOP_N]

    kr_top, us_top = pick("KR"), pick("US")
    note = (
        f"한국 {len([c for c in candidates if c['market'] == 'KR'])}종목 · "
        f"미국 {len([c for c in candidates if c['market'] == 'US'])}종목을 스캔해 "
        f"차트 점수 상위 {FUNDAMENTAL_DEPTH}종목의 재무를 확인한 뒤, "
        f"CAN SLIM 3개 이상 충족 종목을 총점 순으로 골랐습니다. "
        f"총점 = CAN SLIM 충족 개수 × 1.5 + 차트 점수(정배열 3 · 주봉 골든크로스 2.5 · "
        f"컵앤핸들 3 · 일봉 정배열 2 · 일봉 골든크로스 1.5 · 장대양봉 1.5 · "
        f"거래량 급증 1 · 신고가 돌파 1 · 미네르비니 2)."
    )
    return kr_top, us_top, note


# ---------------------------------------------------------------------------


def main():
    started = datetime.now()
    mode = []
    if fetch.DRY_RUN:
        mode.append("캐시 전용")
    if fetch.NO_CACHE:
        mode.append("캐시 무시")
    if QUICK:
        mode.append("축소 유니버스")
    log(f"대시보드 생성 시작 {started:%Y-%m-%d %H:%M:%S}"
        + (f" ({', '.join(mode)})" if mode else ""))

    sections, market_trend = build_macro()
    log(f"  시장 방향(200일선 위): 한국 {market_trend.get('KR')} · "
        f"미국 {market_trend.get('US')}")

    try:
        kr_top, us_top, note = build_stocks(market_trend)
    except Exception as e:
        # 종목 파트가 실패해도 매크로 파트는 반드시 나가야 한다.
        log(f"[경고] 종목 파트 실패: {type(e).__name__} {e}")
        kr_top, us_top = [], []
        note = f"종목 스크리닝 중 오류가 발생했습니다: {type(e).__name__}"

    now = datetime.now()
    args = (sections, kr_top, us_top, now, fetch.stats_line(), note)

    html_out = render.page(*args)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_out)

    # 웹 배포(Artifact)용 조각도 함께 써 둔다. 갱신 후 재배포가 한 번에 끝난다.
    with open(ARTIFACT_PATH, "w", encoding="utf-8") as f:
        f.write(render.artifact_page(*args))

    elapsed = (now - started).total_seconds()
    log(f"완료 — {OUT_PATH} ({len(html_out) / 1024:.0f}KB, {elapsed:.0f}초)")
    log(f"       {ARTIFACT_PATH} (웹 배포용)")
    log(f"  {fetch.stats_line()}")
    log(f"  한국 {len(kr_top)}종목 · 미국 {len(us_top)}종목 선정")


if __name__ == "__main__":
    main()
