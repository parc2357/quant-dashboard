# 데일리 투자 대시보드

한·미 매크로 지표와 CAN SLIM·차트 기준 개별종목 스크리닝을 매일 아침 하나의
HTML 파일로 만든다. **설치할 것이 없다** — 파이썬 표준 라이브러리만 쓴다.

## 쓰는 법

```bash
python3 daily_dashboard.py            # 수집 → dashboard.html
open dashboard.html                   # 브라우저로 열기

python3 daily_dashboard.py --dry-run  # 캐시만 사용 (네트워크 차단, 발표 리허설용)
python3 daily_dashboard.py --no-cache # 캐시 무시하고 새로 받기
python3 daily_dashboard.py --quick    # 유니버스 축소 (코드 점검용, 2초)
```

전체 수집 약 17초(515회 호출), 캐시 재사용 시 2초.

## 매일 07:00 자동 갱신

```bash
cp com.daehyun.quant.daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.daehyun.quant.daily.plist

# 확인 · 지금 바로 한 번 돌려보기 · 해제
launchctl list | grep quant
launchctl kickstart -k gui/$(id -u)/com.daehyun.quant.daily
launchctl unload ~/Library/LaunchAgents/com.daehyun.quant.daily.plist
```

미국 시장은 한국시간 오전 5~6시에 마감하므로 07:00은 전일 미국 종가가 확정된
시점이다. 실행 기록은 `logs/YYYY-MM-DD.log`에 남고 30일이 지나면 자동 삭제된다.

## 웹 배포

`dashboard_artifact.html`이 배포용 조각이다(`<html>`·`<head>` 태그 없이 본문만).
갱신 후 Claude Code에서 이 파일을 다시 배포하면 **같은 주소가 갱신**된다.

> 07:00 자동 갱신은 로컬 HTML만 새로 만든다. 웹 주소까지 갱신하려면 재배포가
> 한 번 필요하다. cron이 claude.ai에 올릴 수는 없다.

## 파일 구성

| 파일 | 역할 |
|---|---|
| `daily_dashboard.py` | 진입점. 수집 → 계산 → 렌더 |
| `fetch.py` | 모든 네트워크 접근의 단일 관문. 캐시·병렬·실패 격리 |
| `universe.py` | 종목·ETF·지수 유니버스 |
| `indicators.py` | MA·정배열·골든크로스·컵앤핸들·거래량·RSI·미네르비니 |
| `canslim.py` | CAN SLIM 7기준 채점, 차트 점수, 총점 |
| `render.py` | HTML 조립 + 손으로 만든 SVG 캔들·스파크라인·히트맵 |
| `cache/YYYY-MM-DD/` | 날짜별 응답 캐시. 오늘 것이 없으면 최근 7일까지 거슬러 찾는다 |

## 데이터 출처

| 항목 | 출처 |
|---|---|
| 지수·종목·ETF 시세·일봉·재무 | 네이버 금융 내부 API (인증키 불필요, 브라우저 User-Agent 필수) |
| 미국 국채 30년 | 미국 재무부 일별 수익률 커브 CSV |
| 비트코인 | 업비트 공개 API |

## 알려진 한계

- **CDS 프리미엄은 실제 스프레드가 아니다.** 기업별 CDS는 S&P·Markit 유료
  독점 데이터다. 채권 ETF 상대강도(HYG÷IEF, LQD÷IEF)와 개별 기업의 주가·
  변동성·52주 위치로 대용한다.
- **WTI·브렌트·금은 ETF 프록시**(USO·BNO·GLD). 표시된 숫자는 ETF 주가이므로
  배럴당 유가가 아니며, **등락률만 의미가 있다.**
- **한국 변동성은 VKOSPI가 아니다.** 코스피 20일 실현변동성(연율화)이다.
- **미국 종목의 이익 성장은 EPS가 아닌 당기순이익 기준**이다. 네이버가 해외
  종목에 EPS를 주지 않는다.
- **스크리닝은 유니버스 한정**(한국 시가총액 상위 150 + 미국 대표 150).
  전체 시장 스캔이 아니다. 국내 목록에서 ETF와 우선주는 제외한다.
- 이효석 아카데미·증권사 HTS·트레이딩뷰 유료 지표는 **미연동**. 로그인
  세션과 API 키 발급이 필요하다.
- `universe.py`의 `THEME_ETFS`에서 "DRAM ETF"는 티커가 특정되지 않아 반도체
  ETF(SMH·SOXX)로 대체했다. 원하는 티커가 있으면 한 줄만 고치면 된다.

투자 판단의 참고 자료이며 매매 권유가 아니다.
