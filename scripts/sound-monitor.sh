#!/bin/bash
# ==============================================================
# sound-monitor.sh — 声音提醒开关
# 通过 macOS launchd 用户代理实现（独立于 Codex 沙箱运行）。
# 语音使用系统 say 命令，Tingting 中文语音。
#
# 用法:
#   bash scripts/sound-monitor.sh start   启用声音提醒
#   bash scripts/sound-monitor.sh stop    关闭声音提醒
#   bash scripts/sound-monitor.sh status  查看状态
# ==============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FLAG_FILE="$SCRIPT_DIR/.sound-reminder-enabled"
PLIST_FILE="$SCRIPT_DIR/com.taixu.sound-monitor.plist"
LAUNCHD_LABEL="com.taixu.sound-monitor"
GUI_DOMAIN="gui/$(id -u)"

# ── 辅助函数 ──────────────────────────────────────────

launchd_loaded() {
    launchctl print "$GUI_DOMAIN/$LAUNCHD_LABEL" &>/dev/null
}

start() {
    # 检查是否已运行
    if launchd_loaded; then
        echo "🔔 声音提醒已在运行中"
        return 0
    fi

    # 创建开启标志
    touch "$FLAG_FILE"

    # 加载 launchd 代理
    if launchctl bootstrap "$GUI_DOMAIN" "$PLIST_FILE" 2>/dev/null; then
        echo "🔔 声音提醒已启用（任务完成后 Tingting 会语音提示）"
        echo "   即使 Codex 在后台也会发声。"
    else
        # 如果 bootstrap 返回"service already loaded"也算成功
        if launchd_loaded; then
            echo "🔔 声音提醒已启用"
        else
            echo "❌ 启动失败，launchctl 返回错误"
            rm -f "$FLAG_FILE"
            return 1
        fi
    fi
}

stop() {
    if launchd_loaded; then
        launchctl bootout "$GUI_DOMAIN/$LAUNCHD_LABEL" 2>/dev/null || true
    fi
    rm -f "$FLAG_FILE"
    echo "🔕 声音提醒已关闭"
}

status() {
    if launchd_loaded; then
        echo "🔔 声音提醒运行中（launchd 代理已加载）"
    elif [ -f "$FLAG_FILE" ]; then
        echo "⚠️  标志文件存在但代理未运行（状态异常）"
    else
        echo "🔕 声音提醒未启用"
    fi
}

# ── 入口 ──────────────────────────────────────────────

case "${1:-}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    status)
        status
        ;;
    *)
        echo "用法: $0 {start|stop|status}"
        exit 1
        ;;
esac
