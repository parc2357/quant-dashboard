"""종목·지표 유니버스 정의.

미국 티커는 네이버 규칙상 나스닥 상장은 `.O` 접미사, NYSE/AMEX는 접미사가 없다.
접미사를 잘못 적어도 fetch 단계에서 반대 형태로 자동 재시도하므로 치명적이지 않다.
"""

# ---------------------------------------------------------------------------
# Part 1 — 매크로
# ---------------------------------------------------------------------------

# 해외 지수: (표시명, 네이버 코드)
US_INDICES = [
    ("다우존스", ".DJI"),
    ("S&P 500", ".INX"),
    ("나스닥", ".IXIC"),
    ("필라델피아 반도체(SOX)", ".SOX"),
]

KR_INDICES = [
    ("코스피", "KOSPI"),
    ("코스닥", "KOSDAQ"),
]

# 원자재는 네이버 선물 경로가 막혀 있어 ETF로 대체한다.
# 이름에 'ETF'를 넣어 표시된 숫자가 배럴당 유가나 온스당 금값이 아님을 분명히 한다.
# 프록시에서 의미가 있는 것은 가격 수준이 아니라 등락률이다.
COMMODITY_PROXIES = [
    ("WTI 원유 ETF", "USO", "United States Oil Fund"),
    ("브렌트유 ETF", "BNO", "United States Brent Oil Fund"),
    ("금 ETF", "GLD", "SPDR Gold Shares"),
]

# 지역·테마 ETF. 요청서의 "DRAM(etf)"는 티커가 특정되지 않아 반도체 ETF로 대체했다.
THEME_ETFS = [
    ("한국 (EWY)", "EWY"),
    ("반도체 (SMH)", "SMH.O"),
    ("반도체 (SOXX)", "SOXX.O"),
]

SPDR_SECTORS = [
    ("기술", "XLK"),
    ("금융", "XLF"),
    ("에너지", "XLE"),
    ("헬스케어", "XLV"),
    ("산업재", "XLI"),
    ("경기소비재", "XLY"),
    ("필수소비재", "XLP"),
    ("유틸리티", "XLU"),
    ("소재", "XLB"),
    ("부동산", "XLRE"),
    ("커뮤니케이션", "XLC"),
]

# CDS 프리미엄은 무료 데이터가 없다(S&P/Markit 유료 독점).
# 시장 전체 신용위험은 채권 ETF 상대강도로, 개별 기업은 주가·변동성으로 대용한다.
CREDIT_PROXY_ETFS = [
    ("하이일드 회사채", "HYG"),
    ("우량 회사채", "LQD"),
    ("미국 국채 7-10년", "IEF"),
]

CDS_WATCH = [
    ("오라클", "ORCL"),
    ("메타", "META.O"),
    ("알파벳", "GOOGL.O"),
    ("마이크로소프트", "MSFT.O"),
    ("아마존", "AMZN.O"),
]

# ---------------------------------------------------------------------------
# Part 2 — 개별종목 유니버스
# ---------------------------------------------------------------------------

KR_UNIVERSE_SIZE = {"KOSPI": 100, "KOSDAQ": 50}

# 미국 150종목: S&P100 핵심 + 나스닥100 + 최근 주도주.
# 리스트 API에 의존하지 않아 가장 빠르고 안전하다.
US_UNIVERSE = [
    # 메가캡 기술 (나스닥)
    "AAPL.O", "MSFT.O", "NVDA.O", "AMZN.O", "META.O", "GOOGL.O", "AVGO.O",
    "TSLA.O", "NFLX.O", "AMD.O", "ADBE.O", "COST.O", "PEP.O", "CSCO.O",
    "INTC.O", "QCOM.O", "TXN.O", "AMAT.O", "MU.O", "LRCX.O", "KLAC.O",
    "INTU.O", "ISRG.O", "BKNG.O", "ADP.O", "SBUX.O", "MDLZ.O", "GILD.O",
    "REGN.O", "VRTX.O", "PANW.O", "SNPS.O", "CDNS.O", "CRWD.O", "MRVL.O",
    "ADI.O", "ASML.O", "PDD.O", "MELI.O", "ABNB.O", "DASH.O", "ZS.O",
    "DDOG.O", "TEAM.O", "WDAY.O", "FTNT.O", "ON.O", "MCHP.O", "NXPI.O",
    "SMCI.O", "ARM.O", "PLTR.O", "COIN.O", "HOOD.O", "APP.O", "EA.O",
    "CTAS.O", "ODFL.O", "PAYX.O", "FAST.O", "BIIB.O", "ILMN.O", "SIRI.O",
    "MRNA.O", "LULU.O", "CPRT.O", "ROST.O", "IDXX.O", "ANSS.O", "TTWO.O",
    "ALGN.O", "ENPH.O", "RIVN.O", "LCID.O", "SOFI.O", "TSM",
    # NYSE 대형주
    "JPM", "V", "MA", "UNH", "XOM", "JNJ", "WMT", "PG", "HD", "CVX",
    "ABBV", "KO", "MRK", "BAC", "ORCL", "CRM", "ACN", "LLY", "PFE", "TMO",
    "ABT", "MCD", "DIS", "VZ", "T", "NKE", "PM", "RTX", "HON", "UPS",
    "CAT", "GS", "MS", "BLK", "AXP", "SPGI", "NOW", "UBER", "SHOP", "BA",
    "GE", "LMT", "MMM", "CVS", "ELV", "CI", "DE", "SCHW", "C", "WFC",
    "COP", "SLB", "EOG", "PSX", "MPC", "VLO", "OXY", "NEE", "DUK", "SO",
    "SHW", "LIN", "APD", "ECL", "FCX", "NEM", "NUE", "X", "CLF",
    "BABA", "NIO", "SE", "SNOW", "NET", "DELL", "HPE", "IBM", "GM", "F",
    "TGT", "LOW", "TJX", "SPOT", "RBLX", "CEG", "VST", "GEV", "TDG",
]

# 화면 표시용 한글 이름. 없으면 티커를 그대로 쓴다.
US_NAMES = {
    "AAPL": "애플", "MSFT": "마이크로소프트", "NVDA": "엔비디아", "AMZN": "아마존",
    "META": "메타", "GOOGL": "알파벳", "AVGO": "브로드컴", "TSLA": "테슬라",
    "NFLX": "넷플릭스", "AMD": "AMD", "ADBE": "어도비", "COST": "코스트코",
    "PEP": "펩시코", "CSCO": "시스코", "INTC": "인텔", "QCOM": "퀄컴",
    "TXN": "텍사스인스트루먼트", "AMAT": "어플라이드머티어리얼즈", "MU": "마이크론",
    "LRCX": "램리서치", "KLAC": "KLA", "INTU": "인튜이트", "ISRG": "인튜이티브서지컬",
    "BKNG": "부킹홀딩스", "SBUX": "스타벅스", "GILD": "길리어드", "REGN": "리제네론",
    "VRTX": "버텍스", "PANW": "팔로알토네트웍스", "SNPS": "시놉시스", "CDNS": "케이던스",
    "CRWD": "크라우드스트라이크", "MRVL": "마벨", "ADI": "아나로그디바이스",
    "ASML": "ASML", "PDD": "핀둬둬", "MELI": "메르카도리브레", "ABNB": "에어비앤비",
    "DASH": "도어대시", "ZS": "지스케일러", "DDOG": "데이터도그", "TEAM": "아틀라시안",
    "WDAY": "워크데이", "FTNT": "포티넷", "ON": "온세미", "MCHP": "마이크로칩",
    "NXPI": "NXP", "SMCI": "슈퍼마이크로", "ARM": "ARM", "PLTR": "팔란티어",
    "COIN": "코인베이스", "HOOD": "로빈후드", "APP": "앱러빈", "MRNA": "모더나",
    "LULU": "룰루레몬", "TSM": "TSMC", "JPM": "JP모간", "V": "비자",
    "MA": "마스터카드", "UNH": "유나이티드헬스", "XOM": "엑슨모빌", "JNJ": "존슨앤존슨",
    "WMT": "월마트", "PG": "P&G", "HD": "홈디포", "CVX": "셰브론", "ABBV": "애브비",
    "KO": "코카콜라", "MRK": "머크", "BAC": "뱅크오브아메리카", "ORCL": "오라클",
    "CRM": "세일즈포스", "ACN": "액센츄어", "LLY": "일라이릴리", "PFE": "화이자",
    "TMO": "써모피셔", "ABT": "애보트", "MCD": "맥도날드", "DIS": "디즈니",
    "VZ": "버라이즌", "T": "AT&T", "NKE": "나이키", "PM": "필립모리스",
    "RTX": "RTX", "HON": "허니웰", "UPS": "UPS", "CAT": "캐터필러",
    "GS": "골드만삭스", "MS": "모간스탠리", "BLK": "블랙록", "AXP": "아멕스",
    "SPGI": "S&P글로벌", "NOW": "서비스나우", "UBER": "우버", "SHOP": "쇼피파이",
    "BA": "보잉", "GE": "GE에어로스페이스", "LMT": "록히드마틴", "MMM": "3M",
    "CVS": "CVS", "ELV": "엘리번스", "CI": "시그나", "DE": "디어",
    "SCHW": "찰스슈왑", "C": "씨티그룹", "WFC": "웰스파고", "COP": "코노코필립스",
    "SLB": "슐럼버거", "EOG": "EOG리소스", "PSX": "필립스66", "MPC": "마라톤페트롤리엄",
    "VLO": "발레로", "OXY": "옥시덴탈", "NEE": "넥스트에라", "DUK": "듀크에너지",
    "SO": "서던컴퍼니", "SHW": "셔윈윌리엄스", "LIN": "린데", "APD": "에어프로덕츠",
    "ECL": "에코랩", "FCX": "프리포트", "NEM": "뉴몬트", "NUE": "뉴코어",
    "X": "US스틸", "CLF": "클리블랜드클리프스", "BABA": "알리바바", "NIO": "니오",
    "SE": "씨리미티드", "SNOW": "스노우플레이크", "NET": "클라우드플레어",
    "DELL": "델", "HPE": "HPE", "IBM": "IBM", "GM": "GM", "F": "포드",
    "TGT": "타깃", "LOW": "로우스", "TJX": "TJX", "SPOT": "스포티파이",
    "RBLX": "로블록스", "CEG": "콘스텔레이션에너지", "VST": "비스트라",
    "GEV": "GE버노바", "TDG": "트랜스다임", "EA": "EA", "SOFI": "소파이",
    "RIVN": "리비안", "LCID": "루시드", "SIRI": "시리우스XM", "ILMN": "일루미나",
    "BIIB": "바이오젠", "CTAS": "신타스", "ODFL": "올드도미니언", "PAYX": "페이첵스",
    "FAST": "패스널", "ADP": "ADP", "MDLZ": "몬델리즈", "ENPH": "엔페이즈",
    "CPRT": "코파트", "ROST": "로스스토어스", "IDXX": "아이덱스", "ANSS": "앤시스",
    "TTWO": "테이크투", "ALGN": "얼라인테크",
}


def base_ticker(t):
    """'NVDA.O' → 'NVDA'"""
    return t.split(".")[0]


def us_display_name(ticker):
    b = base_ticker(ticker)
    return US_NAMES.get(b, b)


def tradingview_url(ticker, market):
    """트레이딩뷰 차트 링크. 사용자가 유료 구독 중이라 심화 분석은 여기서 이어간다."""
    if market == "KR":
        return f"https://www.tradingview.com/chart/?symbol=KRX%3A{ticker}"
    b = base_ticker(ticker)
    exch = "NASDAQ" if ticker.endswith(".O") else "NYSE"
    return f"https://www.tradingview.com/chart/?symbol={exch}%3A{b}"


def naver_url(ticker, market):
    if market == "KR":
        return f"https://finance.naver.com/item/main.naver?code={ticker}"
    return f"https://m.stock.naver.com/worldstock/stock/{ticker}/total"
