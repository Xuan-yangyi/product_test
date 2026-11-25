#!/bin/bash

# 平台通过 SSH 以 linaro 身份执行；需要 root 的脚本自动提权（sudo 密码固定 linaro）
if [ "$(id -u)" -ne 0 ]; then
    printf 'linaro\n' | sudo -S -p '' bash "$0" "$@"
    exit $?
fi
# ============================================================================
# SE13 RS232 双板通信 多波特率测试 (v3: stty VTIME 替代 timeout, 无 fd 泄漏)
# Server: bash test_rs232.sh --mode server [--baudrate 115200]
# Tester: bash test_rs232.sh --mode tester [--baudrate 115200] [--batch]
# 连线: ttyS4 TX(Pin182)↔RX, RX(Pin178)↔TX 交叉
# ============================================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log_info() { echo -e "${CYAN}[INFO]${NC}  $(date '+%H:%M:%S') $*"; }
log_pass() { echo -e "${GREEN}[PASS]${NC}  $*"; }
log_fail() { echo -e "${RED}[FAIL]${NC}  $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }

MODE="tester"; BAUDRATE="115200"; BATCH_MODE=0
DEV="/dev/ttyS4"; TEST_STR="1234abcd"
BAUD_LIST=(9600 19200 38400 57600 115200 230400 460800 921600)

usage() {
    echo "用法: $0 --mode server|tester [--baudrate <rate>] [--batch]"
    echo "  RS232 ttyS4 双板通信, 波特率: ${BAUD_LIST[*]}"
}

# ---- Server: cat+kill (phoenix 模式) ----
run_server() {
    fuser -k "$DEV" 2>/dev/null
    log_info "=== RS232 Server ==="
    cvi_pinmux -w GPIO2/UART4_TX > /dev/null 2>&1
    cvi_pinmux -w GPIO3/UART4_RX > /dev/null 2>&1
    stty -F "$DEV" "$BAUDRATE" cs8 -cstopb -parenb -crtscts -echo
    log_info "就绪, 波特率=$BAUDRATE. Ctrl+C 停止"

    while true; do
        cat "$DEV" > /data/rs232_rx &
        local pid=$!
        sleep 1
        kill $pid 2>/dev/null; wait $pid 2>/dev/null
        if grep -q "$TEST_STR" /data/rs232_rx 2>/dev/null; then
            log_info "收到测试帧, echo 回传 232_rev_done"
            echo "1" > /data/rs232_rx
            echo "232_rev_done" > "$DEV"
        fi
    done
}

# ---- Tester: cat+kill ----
run_tester_single() {
    local rate="$1"; BAUDRATE="$rate"
    fuser -k "$DEV" 2>/dev/null
    log_info "--- RS232 Tester: $BAUDRATE ---"

    cvi_pinmux -w GPIO2/UART4_TX > /dev/null 2>&1
    cvi_pinmux -w GPIO3/UART4_RX > /dev/null 2>&1
    stty -F "$DEV" "$BAUDRATE" cs8 -cstopb -parenb -crtscts -echo

    > /data/rs232_rx
    cat "$DEV" > /data/rs232_rx &
    local pid=$!
    sleep 0.2
    echo "$TEST_STR" > "$DEV"
    log_info "已发送"
    sleep 3
    kill $pid 2>/dev/null; wait $pid 2>/dev/null
    sync

    if grep -q "232_rev_done" /data/rs232_rx 2>/dev/null; then
        log_pass "RS232 $BAUDRATE bps PASS"; return 0
    else
        log_fail "RS232 $BAUDRATE bps FAIL"; return 1
    fi
}

run_tester_batch() {
    log_info "=== RS232 批量波特率测试 (${#BAUD_LIST[@]} 个速率) ==="
    local pass=0 fail=0
    for rate in "${BAUD_LIST[@]}"; do
        if run_tester_single "$rate"; then pass=$((pass+1))
        else fail=$((fail+1)); fi
        echo ""; sleep 0.5
    done
    echo "=============================================="
    echo -e "  ${GREEN}PASS: $pass${NC}  ${RED}FAIL: $fail${NC} (共 ${#BAUD_LIST[@]})"
    echo "=============================================="
    [ "$fail" -gt 0 ] && exit 1 || exit 0
}

main() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --mode) MODE="$2"; shift 2 ;;
            --baudrate) BAUDRATE="$2"; shift 2 ;;
            --batch) BATCH_MODE=1; shift ;;
            --help|-h) usage; exit 0 ;;
            *) echo "未知: $1"; usage; exit 1 ;;
        esac
    done
    case "$MODE" in
        server) run_server ;;
        tester) [ "$BATCH_MODE" = "1" ] && run_tester_batch || run_tester_single "$BAUDRATE" ;;
        *) echo "无效 --mode"; usage; exit 1 ;;
    esac
}

main "$@"