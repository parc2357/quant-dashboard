"""HTML + SVG 렌더링. 외부 리소스를 하나도 쓰지 않는 자기완결 파일을 만든다.

색상은 dataviz 스킬의 검증된 기본 팔레트를 그대로 쓴다.
등락 색은 발산형(diverging) 쌍 red↔blue를 쓰되, 한국 시장 관행에 맞춰
상승=빨강 / 하락=파랑으로 배정했다(네이버·HTS와 동일).
"""

import html
import math
from datetime import datetime

# 팔레트 (dataviz references/palette.md)
CSS = """
:root {
  color-scheme: light;
  --surface-1: #fcfcfb;
  --page: #f9f9f7;
  --ink-1: #0b0b0b;
  --ink-2: #52514e;
  --ink-muted: #898781;
  --grid: #e1e0d9;
  --baseline: #c3c2b7;
  --border: rgba(11,11,11,0.10);
  --up: #d03b3b;
  --down: #2a78d6;
  --flat: #898781;
  --series-1: #2a78d6;
  --series-2: #eb6834;
  --series-3: #1baf7a;
  --good: #0ca30c;
  --warn: #fab219;
  --neutral-mid: #f0efec;
  --chip: rgba(11,11,11,0.045);
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) {
    color-scheme: dark;
    --surface-1: #1a1a19;
    --page: #0d0d0d;
    --ink-1: #ffffff;
    --ink-2: #c3c2b7;
    --ink-muted: #898781;
    --grid: #2c2c2a;
    --baseline: #383835;
    --border: rgba(255,255,255,0.10);
    --up: #e66767;
    --down: #3987e5;
    --series-1: #3987e5;
    --series-2: #d95926;
    --series-3: #199e70;
    --neutral-mid: #383835;
    --chip: rgba(255,255,255,0.06);
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface-1: #1a1a19;
  --page: #0d0d0d;
  --ink-1: #ffffff;
  --ink-2: #c3c2b7;
  --ink-muted: #898781;
  --grid: #2c2c2a;
  --baseline: #383835;
  --border: rgba(255,255,255,0.10);
  --up: #e66767;
  --down: #3987e5;
  --series-1: #3987e5;
  --series-2: #d95926;
  --series-3: #199e70;
  --neutral-mid: #383835;
  --chip: rgba(255,255,255,0.06);
}

* { box-sizing: border-box; }
body {
  margin: 0; padding: 0 20px 64px;
  background: var(--page); color: var(--ink-1);
  font-family: system-ui, -apple-system, "Segoe UI", "Apple SD Gothic Neo", sans-serif;
  font-size: 14px; line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 1180px; margin: 0 auto; }

header.top { padding: 32px 0 20px; }
h1 { font-size: 24px; font-weight: 650; margin: 0 0 6px; letter-spacing: -0.01em; }
.stamp { color: var(--ink-2); font-size: 13px; }
.stamp b { color: var(--ink-1); font-weight: 600; }

h2 { font-size: 17px; font-weight: 640; margin: 40px 0 4px; letter-spacing: -0.01em; }
h2 .part { color: var(--ink-muted); font-weight: 500; font-size: 13px; margin-right: 8px; }
.sub { color: var(--ink-2); font-size: 13px; margin: 0 0 14px; }

.card {
  background: var(--surface-1); border: 1px solid var(--border);
  border-radius: 12px; padding: 4px 0; margin-bottom: 14px; overflow: hidden;
}
.card > h3 {
  font-size: 13px; font-weight: 620; color: var(--ink-2);
  margin: 0; padding: 13px 16px 9px; letter-spacing: 0.01em;
}
.card > h3 .note { font-weight: 450; color: var(--ink-muted); }

.scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
th, td { padding: 8px 12px; text-align: right; white-space: nowrap; }
th {
  font-size: 11px; font-weight: 560; color: var(--ink-muted);
  border-bottom: 1px solid var(--grid); text-transform: none; letter-spacing: 0.02em;
}
td { border-bottom: 1px solid var(--grid); font-size: 13.5px; }
tr:last-child td { border-bottom: none; }
th:first-child, td:first-child { text-align: left; padding-left: 16px; }
td:last-child, th:last-child { padding-right: 16px; }
td.name { font-weight: 520; color: var(--ink-1); }
td.val { font-weight: 620; }
.up { color: var(--up); }
.down { color: var(--down); }
.flat { color: var(--flat); }
.na { color: var(--ink-muted); }

.badge {
  display: inline-block; font-size: 10.5px; font-weight: 600;
  padding: 2px 6px; border-radius: 5px; background: var(--chip);
  color: var(--ink-2); margin-left: 6px; vertical-align: 1px;
  letter-spacing: 0.01em;
}

.heat { display: grid; grid-template-columns: repeat(auto-fit, minmax(96px, 1fr)); gap: 2px; padding: 4px 14px 16px; }
.heat .cell { border-radius: 8px; padding: 10px 10px 9px; }
.heat .cell .k { font-size: 11.5px; color: var(--ink-2); font-weight: 520; }
.heat .cell .v { font-size: 16px; font-weight: 650; margin-top: 3px; font-variant-numeric: tabular-nums; }
.heat .cell .m { font-size: 10.5px; color: var(--ink-muted); margin-top: 2px; font-variant-numeric: tabular-nums; }

.legend { display: flex; gap: 14px; flex-wrap: wrap; padding: 0 16px 12px; font-size: 11.5px; color: var(--ink-2); }
.legend i { display: inline-block; width: 16px; height: 2px; vertical-align: 3px; margin-right: 5px; border-radius: 1px; }

.grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(430px, 1fr)); gap: 14px; }
@media (max-width: 900px) { .grid2 { grid-template-columns: 1fr; } }

.stock {
  background: var(--surface-1); border: 1px solid var(--border);
  border-radius: 12px; padding: 14px 16px 12px; margin-bottom: 12px;
}
.stock .hd { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }
.stock .rank {
  font-size: 11px; font-weight: 700; color: var(--ink-muted);
  min-width: 20px; font-variant-numeric: tabular-nums;
}
.stock .nm { font-size: 16px; font-weight: 650; letter-spacing: -0.01em; }
.stock .tk { font-size: 11.5px; color: var(--ink-muted); font-variant-numeric: tabular-nums; }
.stock .px { margin-left: auto; font-size: 15px; font-weight: 650; font-variant-numeric: tabular-nums; }
.stock .px small { font-size: 12px; font-weight: 560; margin-left: 5px; }
.score {
  display: inline-block; font-size: 11px; font-weight: 650; padding: 2px 7px;
  border-radius: 5px; background: var(--chip); color: var(--ink-1);
  font-variant-numeric: tabular-nums;
}
.reasons { margin: 9px 0 0; padding: 0; list-style: none; }
.reasons li {
  font-size: 12.5px; color: var(--ink-2); padding: 2px 0 2px 14px;
  position: relative; line-height: 1.45;
}
.reasons li::before {
  content: ""; position: absolute; left: 3px; top: 8px;
  width: 4px; height: 4px; border-radius: 50%; background: var(--series-1);
}
.reasons li.cs::before { background: var(--series-3); }
.cslist { display: flex; gap: 3px; margin: 9px 0 0; flex-wrap: wrap; }
.cslist span {
  font-size: 10.5px; font-weight: 650; width: 20px; height: 20px;
  border-radius: 5px; display: inline-flex; align-items: center; justify-content: center;
  background: var(--chip); color: var(--ink-muted);
}
.cslist span.ok { background: var(--good); color: #fff; }
.cslist span.no { background: var(--chip); color: var(--ink-muted); }
.links { margin-top: 10px; display: flex; gap: 12px; font-size: 11.5px; }
.links a { color: var(--series-1); text-decoration: none; font-weight: 560; }
.links a:hover { text-decoration: underline; }
.metrics {
  display: flex; gap: 14px; flex-wrap: wrap; margin-top: 9px;
  font-size: 11.5px; color: var(--ink-muted); font-variant-numeric: tabular-nums;
}
.metrics b { color: var(--ink-2); font-weight: 600; }

figure { margin: 10px 0 0; }
svg { display: block; max-width: 100%; height: auto; }
svg text { font-family: system-ui, -apple-system, sans-serif; }

footer {
  margin-top: 44px; padding-top: 18px; border-top: 1px solid var(--grid);
  color: var(--ink-muted); font-size: 12px;
}
footer h4 { font-size: 12.5px; color: var(--ink-2); margin: 0 0 6px; font-weight: 620; }
footer ul { margin: 0 0 14px; padding-left: 17px; }
footer li { margin-bottom: 3px; }
.empty { padding: 18px 16px 22px; color: var(--ink-muted); font-size: 13px; }
"""


def esc(s):
    return html.escape(str(s), quote=True)


# ---------------------------------------------------------------------------
# 숫자 서식
# ---------------------------------------------------------------------------


def fmt_num(v, digits=2):
    if v is None:
        return "—"
    if abs(v) >= 1000:
        return f"{v:,.0f}" if digits <= 2 else f"{v:,.{digits}f}"
    return f"{v:,.{digits}f}"


def fmt_pct(v, digits=2):
    if v is None:
        return '<span class="na">—</span>'
    cls = "up" if v > 0 else ("down" if v < 0 else "flat")
    return f'<span class="{cls}">{v:+.{digits}f}%</span>'


def fmt_bp(v):
    """금리는 bp(0.01%) 단위 변화가 관행이다."""
    if v is None:
        return '<span class="na">—</span>'
    bp = v * 100.0
    cls = "up" if bp > 0 else ("down" if bp < 0 else "flat")
    return f'<span class="{cls}">{bp:+.0f}bp</span>'


# ---------------------------------------------------------------------------
# SVG
# ---------------------------------------------------------------------------


def sparkline(values, w=110, h=28, label=""):
    """단일 시계열 스파크라인. 시리즈가 하나라 범례는 두지 않는다(제목이 대신한다)."""
    vals = [v for v in (values or []) if v is not None]
    if len(vals) < 2:
        return '<span class="na">—</span>'
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    pad = 2.0
    n = len(vals)
    pts = []
    for i, v in enumerate(vals):
        x = pad + (w - 2 * pad) * i / (n - 1)
        y = h - pad - (h - 2 * pad) * (v - lo) / span
        pts.append(f"{x:.1f},{y:.1f}")
    # 등락 색(빨강/파랑)은 옆의 변화율 칸이 이미 쓰고 있다. 스파크라인까지
    # 색으로 방향을 말하면 기간이 달라 서로 어긋나 보이므로 중립 회색으로 물러선다.
    color = "var(--ink-muted)"
    tip = f"{label} {len(vals)}일: {fmt_num(vals[0])} → {fmt_num(vals[-1])}"
    return (
        f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
        f'aria-label="{esc(tip)}"><title>{esc(tip)}</title>'
        f'<polyline fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round" points="{" ".join(pts)}"/></svg>'
    )


def candle_chart(bars, w=430, h=190, ma_periods=(20, 60), title=""):
    """일봉 캔들 + 이동평균 + 거래량 패널.

    가격과 거래량은 하나의 y축에 겹치지 않게 별도 패널로 쌓는다(이중축 금지).
    각 캔들에 <title>을 달아 마우스를 올리면 값이 보인다.
    """
    from indicators import sma

    bars = [b for b in (bars or []) if b]
    if len(bars) < 5:
        return ""

    price_h = int(h * 0.72)
    vol_h = h - price_h - 10
    pad_l, pad_r, pad_t, pad_b = 2, 46, 6, 2

    plot_w = w - pad_l - pad_r
    closes = [b["c"] for b in bars]
    mas = {n: sma(closes, n) for n in ma_periods}

    lo = min(b["l"] for b in bars)
    hi = max(b["h"] for b in bars)
    for series in mas.values():
        vals = [v for v in series if v is not None]
        if vals:
            lo, hi = min(lo, min(vals)), max(hi, max(vals))
    span = (hi - lo) or 1.0
    lo -= span * 0.04
    hi += span * 0.04
    span = hi - lo

    n = len(bars)
    step = plot_w / n
    body_w = max(1.4, min(6.0, step * 0.62))

    def px(i):
        return pad_l + step * (i + 0.5)

    def py(v):
        return pad_t + (price_h - pad_t - pad_b) * (1.0 - (v - lo) / span)

    out = [
        f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
        f'aria-label="{esc(title)} 일봉 캔들차트">'
    ]

    # 가로 눈금 4개 — 격자는 뒤로 물러나게 얇은 실선
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        v = lo + span * frac
        y = py(v)
        out.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w - pad_r}" y2="{y:.1f}" '
            f'stroke="var(--grid)" stroke-width="1"/>'
            f'<text x="{w - pad_r + 5}" y="{y + 3.5:.1f}" font-size="9" '
            f'fill="var(--ink-muted)">{esc(fmt_num(v, 0 if abs(v) >= 100 else 2))}</text>'
        )

    # 캔들
    for i, b in enumerate(bars):
        x = px(i)
        up = b["c"] >= b["o"]
        col = "var(--up)" if up else "var(--down)"
        y_h, y_l = py(b["h"]), py(b["l"])
        y_o, y_c = py(b["o"]), py(b["c"])
        top = min(y_o, y_c)
        height = max(0.9, abs(y_c - y_o))
        d = b["date"]
        tip = (
            f"{d[:4]}-{d[4:6]}-{d[6:]} 시 {fmt_num(b['o'])} 고 {fmt_num(b['h'])} "
            f"저 {fmt_num(b['l'])} 종 {fmt_num(b['c'])} 량 {b['v']:,.0f}"
        )
        out.append(
            f'<g><title>{esc(tip)}</title>'
            f'<line x1="{x:.1f}" y1="{y_h:.1f}" x2="{x:.1f}" y2="{y_l:.1f}" '
            f'stroke="{col}" stroke-width="1"/>'
            f'<rect x="{x - body_w / 2:.1f}" y="{top:.1f}" width="{body_w:.1f}" '
            f'height="{height:.1f}" fill="{col}" rx="0.8"/></g>'
        )

    # 이동평균선 — 2px, 시리즈 색상
    ma_colors = {ma_periods[0]: "var(--series-2)"}
    if len(ma_periods) > 1:
        ma_colors[ma_periods[1]] = "var(--series-3)"
    for period, series in mas.items():
        pts = [f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(series) if v is not None]
        if len(pts) < 2:
            continue
        out.append(
            f'<polyline fill="none" stroke="{ma_colors.get(period, "var(--series-1)")}" '
            f'stroke-width="2" stroke-linejoin="round" points="{" ".join(pts)}"/>'
        )

    # 거래량 패널 — 가격과 축을 공유하지 않는 별도 영역
    vmax = max(b["v"] for b in bars) or 1.0
    vy0 = price_h + 10 + vol_h
    for i, b in enumerate(bars):
        bh = (b["v"] / vmax) * vol_h
        up = b["c"] >= b["o"]
        col = "var(--up)" if up else "var(--down)"
        out.append(
            f'<rect x="{px(i) - body_w / 2:.1f}" y="{vy0 - bh:.1f}" '
            f'width="{body_w:.1f}" height="{max(0.6, bh):.1f}" fill="{col}" '
            f'opacity="0.42" rx="0.8"/>'
        )
    out.append(
        f'<line x1="{pad_l}" y1="{vy0:.1f}" x2="{w - pad_r}" y2="{vy0:.1f}" '
        f'stroke="var(--baseline)" stroke-width="1"/>'
        f'<text x="{w - pad_r + 5}" y="{vy0 - 1:.1f}" font-size="9" '
        f'fill="var(--ink-muted)">거래량</text>'
    )
    out.append("</svg>")

    legend = (
        f'<div class="legend">'
        f'<span><i style="background:var(--series-2)"></i>{ma_periods[0]}일 이동평균</span>'
        + (
            f'<span><i style="background:var(--series-3)"></i>{ma_periods[1]}일 이동평균</span>'
            if len(ma_periods) > 1 else ""
        )
        + f'<span><i style="background:var(--up)"></i>상승</span>'
          f'<span><i style="background:var(--down)"></i>하락</span></div>'
    )
    return f"<figure>{''.join(out)}{legend}</figure>"


# ---------------------------------------------------------------------------
# 히트맵 (발산형: 상승 빨강 ↔ 하락 파랑, 중간은 회색)
# ---------------------------------------------------------------------------


def heat_color(pct, cap=3.0):
    """수익률을 발산형 색으로. 무지개 금지, 중간값은 중립 회색."""
    if pct is None:
        return "var(--neutral-mid)", "var(--ink-muted)"
    t = max(-1.0, min(1.0, pct / cap))
    alpha = 0.10 + 0.60 * abs(t)
    if abs(t) < 0.04:
        return "var(--neutral-mid)", "var(--ink-1)"
    base = "208,59,59" if t > 0 else "42,120,214"
    ink = "var(--ink-1)"
    return f"rgba({base},{alpha:.2f})", ink


# ---------------------------------------------------------------------------
# 표 조립
# ---------------------------------------------------------------------------


def macro_table(title, rows, note="", value_digits=2, change_style="pct"):
    """rows: [{name, badge, value, chg_abs, chg_pct, w1, m1, spark}]"""
    if not rows:
        return (
            f'<div class="card"><h3>{esc(title)}</h3>'
            f'<div class="empty">데이터를 가져오지 못했습니다.</div></div>'
        )
    head = (
        "<tr><th>항목</th><th>현재</th><th>전일대비</th>"
        "<th>1주</th><th>1개월</th><th>최근 60일</th></tr>"
    )
    body = []
    bp_mode = change_style == "bp"
    for r in rows:
        # 금리는 % 변화가 아니라 bp(0.01%p) 변화로 읽는 것이 관행이다.
        chg = fmt_bp(r.get("chg_abs")) if bp_mode else fmt_pct(r.get("chg_pct"))
        w1 = fmt_bp(r.get("w1_abs")) if bp_mode else fmt_pct(r.get("w1"), 1)
        m1 = fmt_bp(r.get("m1_abs")) if bp_mode else fmt_pct(r.get("m1"), 1)
        badge = f'<span class="badge">{esc(r["badge"])}</span>' if r.get("badge") else ""
        body.append(
            f'<tr><td class="name">{esc(r["name"])}{badge}</td>'
            f'<td class="val">{esc(fmt_num(r.get("value"), r.get("digits", value_digits)))}</td>'
            f"<td>{chg}</td><td>{w1}</td><td>{m1}</td>"
            f'<td>{r.get("spark") or chr(8212)}</td></tr>'
        )
    note_html = f' <span class="note">— {esc(note)}</span>' if note else ""
    return (
        f'<div class="card"><h3>{esc(title)}{note_html}</h3>'
        f'<div class="scroll"><table><thead>{head}</thead>'
        f"<tbody>{''.join(body)}</tbody></table></div></div>"
    )


def sector_heatmap(cells, title, note=""):
    if not cells:
        return ""
    out = []
    for c in cells:
        bg, ink = heat_color(c.get("d1"))
        out.append(
            f'<div class="cell" style="background:{bg};color:{ink}" '
            f'title="{esc(c["name"])} · 1일 {fmt_num(c.get("d1"), 2)}% · '
            f'1주 {fmt_num(c.get("w1"), 1)}% · 1개월 {fmt_num(c.get("m1"), 1)}%">'
            f'<div class="k">{esc(c["name"])} <span style="color:var(--ink-muted)">'
            f'{esc(c["ticker"])}</span></div>'
            f'<div class="v">{("%+.2f%%" % c["d1"]) if c.get("d1") is not None else "—"}</div>'
            f'<div class="m">1주 {fmt_num(c.get("w1"), 1)}% · 1개월 {fmt_num(c.get("m1"), 1)}%</div>'
            f"</div>"
        )
    note_html = f' <span class="note">— {esc(note)}</span>' if note else ""
    legend = (
        '<div class="legend">'
        '<span><i style="background:var(--up)"></i>상승</span>'
        '<span><i style="background:var(--neutral-mid)"></i>보합</span>'
        '<span><i style="background:var(--down)"></i>하락</span>'
        '<span style="color:var(--ink-muted)">색 농도 = 1일 등락률 크기 (±3% 포화)</span>'
        "</div>"
    )
    return (
        f'<div class="card"><h3>{esc(title)}{note_html}</h3>'
        f'<div class="heat">{"".join(out)}</div>{legend}</div>'
    )


# ---------------------------------------------------------------------------
# 종목 카드
# ---------------------------------------------------------------------------


def stock_card(rank, s):
    a = s["analysis"]
    cs = s["canslim"]
    price = a["price"]
    prev = a.get("prev_close")
    chg = ((price / prev - 1.0) * 100.0) if prev else None
    digits = 0 if s["market"] == "KR" else 2

    cs_chips = []
    for code, name, ok, txt in cs["items"]:
        klass = "ok" if ok else "no"
        state = "충족" if ok else ("판정 불가" if ok is None else "미충족")
        cs_chips.append(
            f'<span class="{klass}" title="{esc(code)} · {esc(name)} — {esc(txt)} ({state})">'
            f"{esc(code)}</span>"
        )

    reasons = [f'<li>{esc(r)}</li>' for r in s["chart_reasons"]]
    for code, name, ok, txt in cs["items"]:
        if ok and code in ("C", "A", "N", "S", "L", "I"):
            reasons.append(f'<li class="cs">{esc(name)} — {esc(txt)}</li>')

    hi = a.get("high52") or {}
    metrics = []
    if a.get("rsi") is not None:
        metrics.append(f"RSI <b>{a['rsi']:.0f}</b>")
    if hi:
        metrics.append(f"52주 고가의 <b>{hi['pct_of_high']:.0f}%</b>")
    if a.get("ret_3m") is not None:
        metrics.append(f"3개월 <b>{a['ret_3m']:+.1f}%</b>")
    if a.get("ret_12m") is not None:
        metrics.append(f"12개월 <b>{a['ret_12m']:+.1f}%</b>")
    if a.get("atr_pct") is not None:
        metrics.append(f"ATR <b>{a['atr_pct']:.1f}%</b>")

    chart = candle_chart(a["bars"][-120:], title=s["name"])

    return (
        f'<article class="stock">'
        f'<div class="hd"><span class="rank">{rank}</span>'
        f'<span class="nm">{esc(s["name"])}</span>'
        f'<span class="tk">{esc(s["display_ticker"])}</span>'
        f'<span class="score" title="CAN SLIM 충족 개수×1.5 + 차트 점수">'
        f'총점 {s["total"]:.1f}</span>'
        f'<span class="px">{esc(fmt_num(price, digits))}'
        f'<small>{fmt_pct(chg)}</small></span></div>'
        f'<div class="cslist" title="CAN SLIM 7기준 — 색이 채워진 항목이 충족">'
        f'{"".join(cs_chips)}'
        f'<span style="background:transparent;color:var(--ink-muted);width:auto;'
        f'padding:0 4px;font-weight:500">{cs["passed"]}/7 충족</span></div>'
        f'<ul class="reasons">{"".join(reasons) or "<li>세부 근거 없음</li>"}</ul>'
        f'<div class="metrics">{" · ".join(metrics)}</div>'
        f"{chart}"
        f'<div class="links">'
        f'<a href="{esc(s["tv_url"])}" target="_blank" rel="noopener">트레이딩뷰에서 열기 →</a>'
        f'<a href="{esc(s["naver_url"])}" target="_blank" rel="noopener">네이버 금융 →</a>'
        f"</div></article>"
    )


# ---------------------------------------------------------------------------
# 페이지
# ---------------------------------------------------------------------------

CAVEATS = [
    "<b>CDS 프리미엄은 실제 스프레드가 아닙니다.</b> 기업별 CDS는 S&P·Markit 유료 독점 "
    "데이터로 무료 경로가 없어, 채권 ETF 상대강도(시장 신용위험)와 개별 기업의 "
    "주가·변동성·52주 위치로 대용했습니다.",
    "<b>WTI·브렌트·금은 ETF 프록시입니다.</b> 네이버 선물 시세 경로가 닫혀 있어 "
    "USO·BNO·GLD 가격으로 대체했습니다. 현물/선물가와는 롤오버 비용만큼 차이가 납니다.",
    "<b>한국 변동성은 VKOSPI가 아닙니다.</b> 무료 경로가 없어 코스피 일간 수익률의 "
    "20일 실현변동성(연율화)으로 대체했습니다.",
    "<b>미국 종목의 이익 성장은 EPS가 아닌 당기순이익 기준입니다.</b> 네이버가 해외 "
    "종목에 EPS를 제공하지 않아, 순이익 YoY로 CAN SLIM의 C·A 기준을 판정했습니다.",
    "<b>이효석 아카데미·증권사 HTS·트레이딩뷰 유료 지표는 미연동입니다.</b> "
    "로그인 세션과 API 키 발급이 필요해 후속 작업으로 남겨두었습니다.",
    "<b>종목 스크리닝은 유니버스 한정입니다.</b> 전체 시장 스캔이 아니라 한국 "
    "시가총액 상위 150종목 + 미국 대표 150종목 안에서만 골라냅니다.",
    "이 대시보드는 <b>투자 판단의 참고 자료</b>이며 매매 권유가 아닙니다. "
    "모든 수치는 원 출처에서 반드시 재확인하세요.",
]


def body_html(sections, kr_stocks, us_stocks, generated_at, stats, screen_note):
    """<body> 안에 들어갈 내용만. Artifact는 껍데기를 직접 씌우므로 이 조각을 쓴다."""
    stock_html = []
    for label, lst in (("한국", kr_stocks), ("미국", us_stocks)):
        cards = "".join(stock_card(i + 1, s) for i, s in enumerate(lst))
        if not cards:
            cards = (
                '<div class="card"><div class="empty">조건을 충족하는 종목이 '
                "없거나 데이터를 가져오지 못했습니다.</div></div>"
            )
        stock_html.append(f"<div><h3 style='font-size:14px;font-weight:640;"
                          f"margin:6px 0 10px'>{label} 상위 {len(lst)}종목</h3>{cards}</div>")

    caveat_items = "".join(f"<li>{c}</li>" for c in CAVEATS)

    return f"""<div class="wrap">
<header class="top">
  <h1>데일리 투자 대시보드</h1>
  <div class="stamp">
    기준 시각 <b>{esc(generated_at.strftime('%Y년 %m월 %d일 %H:%M'))}</b> ·
    출처 네이버 금융 · 미국 재무부 · 업비트 · {esc(stats)}
  </div>
</header>

<h2><span class="part">PART 1</span>매크로 &amp; 시황</h2>
<p class="sub">한·미 시장에 영향을 주는 주요 변수. 금리는 bp(0.01%p), 나머지는 % 변화입니다.</p>
{''.join(sections)}

<h2><span class="part">PART 2</span>주목할 개별종목</h2>
<p class="sub">{esc(screen_note)}</p>
<div class="grid2">{''.join(stock_html)}</div>

<footer>
  <h4>데이터 한계 — 반드시 확인하세요</h4>
  <ul>{caveat_items}</ul>
</footer>
</div>
"""


def page(sections, kr_stocks, us_stocks, generated_at, stats, screen_note):
    """더블클릭으로 바로 열리는 완전한 HTML 파일."""
    body = body_html(sections, kr_stocks, us_stocks, generated_at, stats, screen_note)
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>데일리 투자 대시보드 · {esc(generated_at.strftime('%Y-%m-%d'))}</title>
<style>{CSS}</style>
</head>
<body>
{body}</body>
</html>
"""


def artifact_page(sections, kr_stocks, us_stocks, generated_at, stats, screen_note):
    """Artifact 배포용. doctype/html/head/body 태그는 배포 시점에 씌워지므로 빼고,
    제목과 스타일만 직접 넣는다."""
    body = body_html(sections, kr_stocks, us_stocks, generated_at, stats, screen_note)
    # 제목에는 날짜를 넣지 않는다. 매일 재배포할 때 같은 페이지로 갱신되어야 하고,
    # 제목이 바뀌면 다른 페이지처럼 보인다. 기준 시각은 본문 머리에 있다.
    return (
        f"<title>데일리 투자 대시보드</title>\n"
        f"<style>{CSS}</style>\n{body}"
    )
