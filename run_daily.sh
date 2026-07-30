#!/bin/bash
# 매일 아침 대시보드를 갱신한다. launchd가 이 스크립트를 호출한다.
#
# 미국 시장은 한국시간 오전 5~6시에 마감하므로 07:00은 전일 미국 종가가
# 확정된 시점이다. 한국 시장은 개장 전이라 전일 종가가 들어간다.

set -uo pipefail
cd "$(dirname "$0")"

LOG_DIR="logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/$(date +%Y-%m-%d).log"

{
  echo "===== $(date '+%Y-%m-%d %H:%M:%S') 갱신 시작 ====="
  /usr/bin/python3 daily_dashboard.py
  echo "===== 종료 코드 $? ====="
} >>"$LOG" 2>&1

# 30일보다 오래된 로그와 캐시는 지운다.
find "$LOG_DIR" -name '*.log' -mtime +30 -delete 2>/dev/null
find cache -maxdepth 1 -type d -mtime +30 -exec rm -rf {} + 2>/dev/null

exit 0
