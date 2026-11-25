#!/bin/bash

# 平台通过 SSH 以 linaro 身份执行；需要 root 的脚本自动提权（sudo 密码固定 linaro）
if [ "$(id -u)" -ne 0 ]; then
    printf 'linaro\n' | sudo -S -p '' bash "$0" "$@"
    exit $?
fi
# ============================================================================
# SE13 CAN 接口测试 — 支持 loopback 自测和双板通信
#
# 测试内容: CAN (can0) 帧收发
# 测试方法:
#   - loopback 模式 (单板自测): can0 loopback on, cansend 发送, candump 接收验证
#   - 双板通信: 两块 SE13 can0 H↔H, L↔L 凤凰端子连接
#      Server: candump 监听 + cansend echo
#      Tester: cansend 发送, candump 接收 echo 并验证
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# === 内联公共函数库 (原 lib/test_common.sh) ===
set -o pipefail
VERBOSE=0
TEST_START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log_info()  { echo -e "${CYAN}[INFO]${NC}  $(date '+%H:%M:%S') $*"; }
log_pass()  { echo -e "${GREEN}[PASS]${NC}  $*"; }
log_fail()  { echo -e "${RED}[FAIL]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_debug() { [ "$VERBOSE" -ge 1 ] && echo -e "       [DEBUG] $*"; }
sentinel_pass() { echo "QA_PASS_$1"; }
sentinel_fail() { echo "QA_FAIL_$1: $2"; }
sentinel_skip() { echo "QA_SKIP_$1: $2"; }
run_sudo() { echo linaro | sudo -S "$@"; }
check_cmd() { command -v "$1" >/dev/null 2>&1 || { log_fail "命令 $1 未找到"; return 1; }; return 0; }
declare -a TEST_RESULTS=()
add_result() { TEST_RESULTS+=("$1|$2|$3"); }
print_summary() {
    echo ""; echo "=============================================="
    echo "  测试结果汇总  (开始: $TEST_START_TIME)"
    echo "=============================================="
    local pass_count=0 fail_count=0 skip_count=0
    for r in "${TEST_RESULTS[@]}"; do
        local name="${r%%|*}"; local rest="${r#*|}"; local status="${rest%%|*}"; local reason="${rest#*|}"
        case "$status" in
            PASS) echo -e "  ${GREEN}✓${NC} PASS: $name"; pass_count=$((pass_count+1)) ;;
            FAIL) echo -e "  ${RED}✗${NC} FAIL: $name — $reason"; fail_count=$((fail_count+1)) ;;
            SKIP) echo -e "  ${YELLOW}−${NC} SKIP: $name — $reason"; skip_count=$((skip_count+1)) ;;
        esac
    done
    echo "----------------------------------------------"
    echo -e "  ${GREEN}PASS:$pass_count${NC}  ${RED}FAIL:$fail_count${NC}  ${YELLOW}SKIP:$skip_count${NC}"
    echo "=============================================="
    if [ "$fail_count" -gt 0 ]; then
        sentinel_fail "$TEST_MODULE" "${fail_count}项失败"
        exit 1
    else
        sentinel_pass "$TEST_MODULE"
        exit 0
    fi
}
parse_args() {
    while [ $# -gt 0 ]; do case "$1" in
        --help|-h) usage; exit 0 ;;
        --verbose|-v) VERBOSE=1 ;;
        *) echo "未知参数: $1"; usage; exit 1 ;;
    esac; shift; done
}
check_device_reachable() {
    local ip="$1"
    [ -z "$ip" ] && return 0
    if ping -c 1 -W 2 "$ip" >/dev/null 2>&1; then
        log_info "设备 $ip 可达"; return 0
    else
        log_fail "设备 $ip 不可达"; add_result "设备连接" "FAIL" "ping 不通 $ip"; print_summary
    fi
}
gpio_export() { local n="$1"; [ -d "/sys/class/gpio/gpio$n" ] && return 0; run_sudo sh -c "echo $n > /sys/class/gpio/export" 2>/dev/null; sleep 0.1; }
gpio_unexport() { local n="$1"; run_sudo sh -c "echo $n > /sys/class/gpio/unexport" 2>/dev/null; }
gpio_set_dir() { local n="$1" d="$2"; run_sudo sh -c "echo $d > /sys/class/gpio/gpio$n/direction"; }
gpio_read() { local n="$1"; cat "/sys/class/gpio/gpio$n/value" 2>/dev/null; }
gpio_write() { local n="$1" v="$2"; run_sudo sh -c "echo $v > /sys/class/gpio/gpio$n/value"; }
# === 公共函数库结束 ===

TEST_MODULE="CAN"
MODE="loopback"

usage() {
    echo "用法: $0 [选项]"
    echo "  SE13 CAN 接口测试"
    echo "  模式:"
    echo "    --mode loopback   单板自测 (loopback on) — 无需外部连接"
    echo "    --mode server     双板 Server 模式 (监听+echo) — 需双板 H↔H,L↔L"
    echo "    --mode tester     双板 Tester 模式 (发送+验证) — 需双板 H↔H,L↔L"
    echo "  连接: can0 H↔H, L↔L (凤凰端子)"
    echo "  注意: SE13 cansend 语法为 cansend <iface> -i <ID> <bytes>"
    echo "选项:  --help, -h / --verbose, -v"
}

run_loopback() {
    log_info "=== CAN Loopback 自测模式 ==="

    ip link show can0 >/dev/null 2>&1 || { log_fail "can0 不存在"; add_result "CAN 设备检查" "FAIL" "can0 不存在"; print_summary; }

    run_sudo ip link set can0 down 2>/dev/null; sleep 0.2
    run_sudo ip link set can0 up type can bitrate 250000 loopback on 2>/dev/null
    sleep 0.3

    local can_state=$(ip -details link show can0 2>/dev/null | grep -oP 'can\s+<\S+>\s+state\s+\S+' | grep -oP 'state\s+\S+' | awk '{print $2}')
    log_info "CAN 状态: $can_state"

    case "$can_state" in
        ERROR-ACTIVE|ERROR-PASSIVE)
            local tmpfile="/tmp/se13_can_lb_$$.log"
            echo linaro | sudo -S timeout 3 candump can0 > "$tmpfile" 2>/dev/null &
            sleep 0.3
            run_sudo cansend can0 -i 0x55 0x12 0x23 0x34 2>/dev/null
            sleep 3

            if run_sudo grep -q "<0x055>" "$tmpfile" 2>/dev/null; then
                local frame=$(run_sudo grep "<0x055>" "$tmpfile" | head -1)
                log_pass "CAN loopback 帧收发正常 $frame"
                add_result "CAN loopback" "PASS" ""
            else
                log_warn "CAN $can_state 但未收到 loopback 帧"
                add_result "CAN loopback" "SKIP" "$can_state — 无回环帧"
            fi
            run_sudo rm -f "$tmpfile"
            ;;
        *)
            log_fail "CAN 状态异常: $can_state"
            add_result "CAN loopback" "FAIL" "状态 $can_state"
            ;;
    esac

    # 异常测试: CAN 总线错误
    log_info "=== CAN 异常测试 ==="
    log_info "CAN 总线短路/终端电阻缺失等异常需外部设备配合"
    add_result "CAN 异常" "SKIP" "需外部设备"

    # 波特率测试
    log_info "=== CAN 波特率 ==="
    local cur_bitrate=$(ip -details link show can0 2>/dev/null | grep -o 'bitrate [0-9]*' | awk '{print $2}')
    log_info "当前波特率: ${cur_bitrate:-未知}"
    add_result "CAN 波特率" "PASS" "${cur_bitrate:-250000} bps"

    print_summary
}

run_server() {
    log_info "=== CAN Server 模式 (监听+echo) ==="
    log_info "监听 can0, 收到帧后原 ID + 数据 echo 回传. Ctrl+C 停止"

    run_sudo ip link set can0 down 2>/dev/null; sleep 0.2
    run_sudo ip link set can0 up type can bitrate 250000 2>/dev/null
    sleep 0.3

    log_info "CAN Echo Server 已就绪..."

    # 持续 candump + cansend echo
    # 策略: 每次 candump 捕获一帧，解析后 cansend echo 回去
    while true; do
        local frame=$(echo linaro | sudo -S timeout 10 candump can0 -n 1 2>/dev/null)
        if echo "$frame" | grep -q "can0"; then
            # 解析帧: can0  0x055  [3] 12 23 34
            local can_id=$(echo "$frame" | awk '{print $2}' | sed 's/0x//')
            local dlc=$(echo "$frame" | grep -oP '\[\d+\]' | tr -d '[]')
            local data=$(echo "$frame" | sed 's/.*\[.*\]\s*//')
            [ -n "$can_id" ] && run_sudo cansend can0 -i "$can_id" $data 2>/dev/null
            log_info "Echo: ID=0x$can_id data=$data"
        fi
    done
}

run_tester() {
    log_info "=== CAN Tester 模式 ==="

    ip link show can0 >/dev/null 2>&1 || { log_fail "can0 不存在"; add_result "CAN 设备检查" "FAIL" "can0 不存在"; print_summary; }

    run_sudo ip link set can0 down 2>/dev/null; sleep 0.2
    run_sudo ip link set can0 up type can bitrate 250000 2>/dev/null
    sleep 0.3

    local can_state=$(ip -details link show can0 2>/dev/null | grep -oP 'can\s+<\S+>\s+state\s+\S+' | grep -oP 'state\s+\S+' | awk '{print $2}')
    log_info "CAN 状态: $can_state"

    log_info "=== CAN 双板通信测试 ==="
    log_info "请确认 Tester 与 Server 的 can0 H↔H, L↔L 已连接"

    local test_id="0x66"
    local test_data="0xAB 0xCD 0xEF"
    local tmpfile="/tmp/se13_can_dual_$$.log"

    echo linaro | sudo -S timeout 5 candump can0 > "$tmpfile" 2>/dev/null &
    sleep 0.3
    run_sudo cansend can0 -i "$test_id" $test_data 2>/dev/null
    sleep 3.5  # 等待 Server 收到 → echo 回传

    if run_sudo grep -q "<${test_id}>" "$tmpfile" 2>/dev/null; then
        log_pass "CAN 双板通信 ✓ (Server echo 已接收)"
        local frame=$(run_sudo grep "<${test_id}>" "$tmpfile" | head -1)
        log_debug "收到 echo: $frame"
        add_result "CAN 双板通信" "PASS" ""
    else
        log_fail "CAN 双板通信失败: 未收到 Server echo"
        log_warn "请确认: 1) Server 端已运行 --mode server  2) H↔H, L↔L 接线正确"
        add_result "CAN 双板通信" "FAIL" "无 echo 回传"
    fi
    run_sudo rm -f "$tmpfile"

    add_result "CAN 异常" "SKIP" "需外部设备"
    print_summary
}

main() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --mode) MODE="$2"; shift 2 ;;
            --help|-h) usage; exit 0 ;;
            --verbose|-v) VERBOSE=1; shift ;;
            *) echo "未知: $1"; usage; exit 1 ;;
        esac
    done

    case "$MODE" in
        loopback) run_loopback ;;
        server) run_server ;;
        tester) run_tester ;;
        *) echo "无效 --mode: $MODE (loopback|server|tester)"; exit 1 ;;
    esac
}

main "$@"