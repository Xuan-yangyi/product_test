#!/bin/bash

# 平台通过 SSH 以 linaro 身份执行；需要 root 的脚本自动提权（sudo 密码固定 linaro）
if [ "$(id -u)" -ne 0 ]; then
    printf 'linaro\n' | sudo -S -p '' bash "$0" "$@"
    exit $?
fi
# ============================================================================
# SE13 GPIO + Relay 接口测试
#
# 测试内容:
#   - GPIO: DO1(Pin176)→DI1(Pin184), DO2(Pin180)→DI2(Pin186) 跳线回环
#   - Relay: GPIO92(sysfs 444) toggle 控制
# 测试方法简述:
#   - GPIO: sysfs export → set DO direction=out, DI=in → toggle DO → read DI 验证
#   - Relay: sysfs export GPIO92 → toggle → 建议万用表验证吸合/释放
# 预期结果: GPIO toggle 电平一致, Relay sysfs切换正常; QA_PASS_IO
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

TEST_MODULE="IO"

usage() {
    echo "用法: $0 [选项]"
    echo "  SE13 GPIO + Relay 接口测试"
    echo "  前置条件:"
    echo "    DO1(Pin176)↔DI1(Pin184) 跳线"
    echo "    DO2(Pin180)↔DI2(Pin186) 跳线"
    echo "选项:  --help, -h / --verbose, -v"
}

test_gpio_basic() {
    log_info "=== GPIO 基本功能 ==="
    local pairs=("485:480:DO1(GPIO5)→DI1(GPIO0) Pin176↔184" "481:484:DO2(GPIO1)→DI2(GPIO4) Pin180↔186")
    local all_pass=0

    for pair in "${pairs[@]}"; do
        IFS=':' read -r do_num di_num label <<< "$pair"
        gpio_export "$do_num" || { log_fail "$label export DO $do_num 失败"; all_pass=1; continue; }
        gpio_export "$di_num" || { log_fail "$label export DI $di_num 失败"; all_pass=1; continue; }
        sleep 0.1
        gpio_set_dir "$do_num" "out" || { log_fail "$label set DO dir 失败"; all_pass=1; continue; }
        gpio_set_dir "$di_num" "in"

        gpio_write "$do_num" 1; sleep 0.1; [ "$(gpio_read "$di_num")" = "1" ] || { log_fail "$label DO=1→DI≠1"; all_pass=1; }
        gpio_write "$do_num" 0; sleep 0.1; [ "$(gpio_read "$di_num")" = "0" ] || { log_fail "$label DO=0→DI≠0"; all_pass=1; }
        [ "$all_pass" -eq 0 ] && log_pass "$label ✓"
    done
    [ "$all_pass" -eq 0 ] && add_result "GPIO 基本功能" "PASS" "" || add_result "GPIO 基本功能" "FAIL" "电平不一致"
}

test_relay_basic() {
    log_info "=== Relay 基本功能 ==="
    local relay=444
    gpio_export "$relay" || { add_result "Relay 基本功能" "FAIL" "export $relay 失败"; return; }
    sleep 0.1; gpio_set_dir "$relay" "out"

    gpio_write "$relay" 1; sleep 0.1; local v1=$(gpio_read "$relay")
    gpio_write "$relay" 0; sleep 0.1; local v0=$(gpio_read "$relay")

    if [ "$v1" = "1" ] && [ "$v0" = "0" ]; then
        log_pass "Relay GPIO92 电平切换正常 (实际继电器吸合/释放建议万用表验证)"
        add_result "Relay 基本功能" "PASS" ""
    else
        log_fail "Relay GPIO92 电平异常: v1=$v1 v0=$v0"
        add_result "Relay 基本功能" "FAIL" "电平异常"
    fi
}

test_gpio_exception() {
    log_info "=== GPIO 异常测试 ==="
    log_info "DO/DI 反接、过压、短路等异常注入需外部设备配合"
    add_result "GPIO 异常" "SKIP" "需外部设备"
}

main() {
    parse_args "$@"
    log_info "SE13 GPIO + Relay 测试开始"
    log_info "预期跳线: DO1(Pin176)→DI1(Pin184), DO2(Pin180)→DI2(Pin186)"

    test_gpio_basic
    test_relay_basic
    test_gpio_exception

    print_summary
}

main "$@"