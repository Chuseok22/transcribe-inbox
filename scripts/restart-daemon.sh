#!/usr/bin/env bash
set -euo pipefail

LABEL="com.chuseok22.transcribe-inbox"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG="$HOME/Library/Logs/transcribe-inbox.log"
ERROR_LOG="$HOME/Library/Logs/transcribe-inbox.error.log"

# launchctl list 한 줄: "<PID 또는 -><TAB><마지막 종료코드><TAB><label>"
current_pid() {
  launchctl list | awk -v label="$LABEL" '$3 == label { print $1 }'
}

pid="$(current_pid || true)"

if [ -z "${pid:-}" ]; then
  echo "⚠️  데몬이 로드되어 있지 않습니다. 다음 명령으로 직접 로드하세요:"
  echo "    launchctl load ${PLIST}"
  exit 1
fi

if [ "$pid" = "-" ]; then
  echo "⚠️  데몬이 로드되어 있지만 실행 중이 아닙니다(반복 크래시로 launchd가 재시도를 포기했을 수 있음)."
  echo "    로그를 확인하세요:"
  echo "    ${LOG}"
  echo "    ${ERROR_LOG}"
  exit 1
fi

echo "현재 PID: ${pid} — 재시작을 시작합니다..."
if ! launchctl unload "$PLIST"; then
  echo "❌ launchctl unload 실패 — 로그를 확인하세요:"
  echo "    ${LOG}"
  echo "    ${ERROR_LOG}"
  exit 1
fi
if ! launchctl load "$PLIST"; then
  echo "❌ launchctl load 실패 — 로그를 확인하세요:"
  echo "    ${LOG}"
  echo "    ${ERROR_LOG}"
  exit 1
fi

new_pid=""
for _ in $(seq 1 20); do
  sleep 0.5
  candidate="$(current_pid || true)"
  if [ -n "${candidate:-}" ] && [ "$candidate" != "-" ] && [ "$candidate" != "$pid" ]; then
    new_pid="$candidate"
    break
  fi
done

if [ -n "$new_pid" ]; then
  echo "✅ 재시작 완료: PID ${pid} → ${new_pid}"
  exit 0
fi

echo "❌ 재시작 실패 — 로그를 확인하세요:"
echo "    ${LOG}"
echo "    ${ERROR_LOG}"
exit 1
