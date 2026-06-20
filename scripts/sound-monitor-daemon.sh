#!/bin/bash
# ==============================================================
# sound-monitor-daemon.sh — 声音提醒守护进程
# 由 launchd 管理，独立于 Codex 沙箱运行。
# 监控 ~/.codex/shell_snapshots/ 目录，检测任务完成并播放语音。
# ==============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FLAG_FILE="$SCRIPT_DIR/.sound-reminder-enabled"
LOG_FILE="$SCRIPT_DIR/.sound-monitor-daemon.log"
SNAPSHOT_DIR="${HOME}/.codex/shell_snapshots"

# ── 配置 ──────────────────────────────────────────────
GAP_SECONDS=6
COOLDOWN_SECONDS=30
POLL_INTERVAL=2
VOICE="Tingting"
MESSAGE="任务已经完成，请指示"

# ── 主循环 ────────────────────────────────────────────

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 守护进程已启动" >> "$LOG_FILE"

last_activity=0
last_notification=0
has_activity=false

# 初始化：取当前最新快照时间戳
if [ -d "$SNAPSHOT_DIR" ]; then
    init_file=$(ls -t "$SNAPSHOT_DIR"/*.sh 2>/dev/null | head -1)
    if [ -n "$init_file" ]; then
        last_activity=$(($(stat -f "%m" "$init_file" 2>/dev/null || echo 0) - 1))
    fi
fi

while true; do
    # 检查是否已被用户关闭
    if [ ! -f "$FLAG_FILE" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 声音提醒已关闭，守护进程退出" >> "$LOG_FILE"
        exit 0
    fi

    sleep "$POLL_INTERVAL"

    if [ ! -d "$SNAPSHOT_DIR" ]; then
        continue
    fi

    latest_mtime=0
    newest_file=$(ls -t "$SNAPSHOT_DIR"/*.sh 2>/dev/null | head -1)
    if [ -n "$newest_file" ]; then
        latest_mtime=$(stat -f "%m" "$newest_file" 2>/dev/null || echo 0)
    fi

    if [ "$latest_mtime" -gt "$last_activity" ]; then
        last_activity="$latest_mtime"
        has_activity=true
    fi

    now=$(date +%s)
    gap=$(( now - last_activity ))
    cooldown=$(( now - last_notification ))

    if [ "$has_activity" = true ] \
        && [ "$gap" -ge "$GAP_SECONDS" ] \
        && [ "$cooldown" -ge "$COOLDOWN_SECONDS" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 播放提醒" >> "$LOG_FILE"
        say -v "$VOICE" "$MESSAGE"
        last_notification="$now"
        has_activity=false
        last_activity="$now"
    fi
done
