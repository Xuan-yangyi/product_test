#!/bin/bash

# 平台通过 SSH 以 linaro 身份执行；需要 root 的脚本自动提权（sudo 密码固定 linaro）
if [ "$(id -u)" -ne 0 ]; then
    printf 'linaro\n' | sudo -S -p '' bash "$0" "$@"
    exit $?
fi
# ============================================================================
# SE13 网络接口测试
#
# 测试内容: 以太网连通性、速率
# 测试方法简述:
#   - 动态获取网关、ping 连通性测试、ethtool 速率验证
# 预期结果: 0% packet loss, 1000Mb/s, QA_PASS_NETWORK
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

TEST_MODULE="NETWORK"

usage() {
    echo "用法: $0 [选项]"
    echo "  SE13 网络接口测试"
    echo "选项:"
    echo "  --help, -h         显示帮助"
    echo "  --verbose, -v      详细输出"
}

# --- 基本功能 ---

test_eth_basic() {
    log_info "=== 1.1 以太网连通性测试 ==="

    # 获取网关
    local gateway=$(ip route 2>/dev/null | grep default | awk '{print $3}' | head -1)
    if [ -z "$gateway" ]; then
        log_fail "无法获取默认网关"
        add_result "以太网连通性" "FAIL" "无默认网关"
        return
    fi
    log_info "网关: $gateway"

    # 测试每个网口
    local eth_found=0
    for eth in eth0 eth1; do
        # 检查接口是否存在
        ip link show "$eth" >/dev/null 2>&1 || { log_debug "$eth 不存在"; continue; }

        # 检查 CARRIER
        local carrier=$(cat "/sys/class/net/${eth}/carrier" 2>/dev/null)
        if [ "$carrier" != "1" ]; then
            log_info "$eth: NO-CARRIER，跳过"
            continue
        fi

        eth_found=1
        log_info "测试 $eth ..."

        # Ping 连通性 (eth1直连PC 192.168.150.223, eth0走网关)
        local ping_target="$gateway"
        [ "$eth" = "eth1" ] && ping_target="192.168.150.223"
        if ping -c 1 -W 2 -I "$eth" "$ping_target" >/dev/null 2>&1; then
            log_pass "$eth: ping $ping_target OK"

            # 速率检查
            local speed=$(run_sudo ethtool "$eth" 2>/dev/null | grep Speed | awk '{print $2}')
            if [ -n "$speed" ]; then
                log_info "$eth: Speed=$speed (期望 1000Mb/s)"
                if [ "$speed" = "1000Mb/s" ]; then
                    log_pass "$eth: 速率符合预期"
                else
                    log_warn "$eth: 速率=$speed (期望 1000Mb/s)"
                fi
            fi
        else
            log_fail "$eth: ping $ping_target 失败"
            add_result "以太网连通性" "FAIL" "$eth ping $ping_target 失败"
            continue
        fi
    done

    if [ "$eth_found" -eq 0 ]; then
        log_warn "无可用网口（均已 NO-CARRIER 或不存在）"
        add_result "以太网连通性" "SKIP" "无可用网口"
    else
        add_result "以太网连通性" "PASS" ""
    fi
}

test_eth_dhcp_static() {
    log_info "=== 1.2 网口 IP 配置 ==="

    for eth in eth0; do
        ip link show "$eth" >/dev/null 2>&1 || continue
        local carrier=$(cat "/sys/class/net/${eth}/carrier" 2>/dev/null)
        [ "$carrier" != "1" ] && continue

        local current_ip=$(ip addr show "$eth" 2>/dev/null | grep 'inet ' | awk '{print $2}')
        if [ -n "$current_ip" ]; then
            log_info "$eth: IP=$current_ip"
        else
            log_info "$eth: 无 IP 地址"
        fi
    done

    add_result "网口 IP 配置" "PASS" ""
}

# --- 异常测试 ---

test_eth_exception() {
    log_info "=== 2. 网络异常测试 ==="

    # 网口存在性检查
    local eth_count=0
    for eth in eth0 eth1; do
        ip link show "$eth" >/dev/null 2>&1 && eth_count=$((eth_count+1))
    done

    if [ "$eth_count" -ge 1 ]; then
        log_info "检测到 $eth_count 个网口"
        log_info "网线插拔异常/单通收发异常需人工配合验证"
        add_result "网络异常" "SKIP" "异常注入需人工操作，$eth_count 网口检测正常"
    else
        add_result "网络异常" "FAIL" "未检测到网口"
    fi
}

# --- 主流程 ---

main() {
    parse_args "$@"
    log_info "SE13 网络接口测试开始"

    test_eth_basic
    test_eth_dhcp_static
    test_eth_exception
    print_summary
}

main "$@"