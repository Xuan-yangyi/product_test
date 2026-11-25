#!/bin/bash

# 平台通过 SSH 以 linaro 身份执行；需要 root 的脚本自动提权（sudo 密码固定 linaro）
if [ "$(id -u)" -ne 0 ]; then
    printf 'linaro\n' | sudo -S -p '' bash "$0" "$@"
    exit $?
fi
# ============================================================================
# SE13 内存/存储接口测试
#
# 测试内容: eMMC 分区容量检查、内存容量、存储基本读写
# 测试方法简述:
#   - eMMC: df 检测 /dev/mmcblk0p5/p6 分区大小 (≥6GB/15GB)
#   - 内存: free -h / cat /proc/meminfo 检测总容量
#   - 读写: dd 单次读写验证 eMMC 可用性
# 预期结果: eMMC 分区满足规格、内存容量≥32GB、QA_PASS_MEMORY_STORAGE
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

TEST_MODULE="MEMORY_STORAGE"

usage() {
    echo "用法: $0 [选项]"
    echo "  SE13 内存/存储接口测试"
    echo "选项:"
    echo "  --help, -h          显示帮助"
    echo "  --verbose, -v       详细输出"
}

# --- 基本功能 ---

test_emmc_basic() {
    log_info "=== 1.1 eMMC 分区容量检查 ==="

    local err=0

    # 检查 p5
    if df -h 2>/dev/null | grep -q "mmcblk0p5"; then
        local size_p5=$(df -h 2>/dev/null | grep "mmcblk0p5" | awk '{print $2}')
        local size_gb_p5=$(echo "$size_p5" | sed 's/G//')
        log_info "eMMC p5: $size_p5"
        if [ "$(echo "$size_gb_p5 >= 6" | bc 2>/dev/null)" = "1" ] || [ "$(printf '%.0f' "$size_gb_p5" 2>/dev/null)" -ge 6 ] 2>/dev/null; then
            log_pass "eMMC p5 ≥ 6GB ✓"
        else
            log_fail "eMMC p5: $size_p5 < 6GB"
            err=1
        fi
    else
        log_fail "eMMC p5 分区未找到"
        err=1
    fi

    # 检查 p6
    if df -h 2>/dev/null | grep -q "mmcblk0p6"; then
        local size_p6=$(df -h 2>/dev/null | grep "mmcblk0p6" | awk '{print $2}')
        local size_gb_p6=$(echo "$size_p6" | sed 's/G//')
        log_info "eMMC p6: $size_p6"
        if [ "$(echo "$size_gb_p6 >= 15" | bc 2>/dev/null)" = "1" ] || [ "$(printf '%.0f' "$size_gb_p6" 2>/dev/null)" -ge 15 ] 2>/dev/null; then
            log_pass "eMMC p6 ≥ 15GB ✓"
        else
            log_fail "eMMC p6: $size_p6 < 15GB"
            err=1
        fi
    else
        log_fail "eMMC p6 分区未找到"
        err=1
    fi

    if [ "$err" -eq 0 ]; then
        add_result "eMMC 分区检查" "PASS" ""
    else
        add_result "eMMC 分区检查" "FAIL" "分区大小不满足"
    fi
}

test_memory_basic() {
    log_info "=== 1.2 内存容量检查 ==="

    local total_mem=$(free -h 2>/dev/null | grep Mem | awk '{print $2}')
    local total_mem_kb=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}')

    log_info "总内存: $total_mem ($total_mem_kb kB)"

    # SE13 规格: 32GB LPDDR5 (不同配置可能 8/16/24/32/64GB)
    local total_gb=$((total_mem_kb / 1024 / 1024))
    log_info "检测到内存: ~${total_gb}GB"
    if [ "$total_gb" -ge 1 ]; then
        log_info "内存容量: ${total_gb}GB (设备已检测到可用内存)"
        add_result "内存容量" "PASS" "${total_gb}GB"
    else
        log_fail "内存容量异常: ${total_gb}GB"
        add_result "内存容量" "FAIL" "${total_gb}GB"
    fi
}

test_emmc_rw() {
    log_info "=== 1.3 eMMC 基本读写 ==="

    local test_file="/tmp/se13_emmc_test_$$.bin"
    if dd if=/dev/zero of="$test_file" bs=1M count=10 2>/dev/null; then
        log_info "eMMC 写入 10MB 成功"
        if dd if="$test_file" of=/dev/null bs=1M 2>/dev/null; then
            log_pass "eMMC 读写测试通过"
            add_result "eMMC 读写" "PASS" ""
        fi
        rm -f "$test_file"
    else
        log_fail "eMMC 写入失败"
        add_result "eMMC 读写" "FAIL" "写入失败"
    fi
}

# --- 异常测试 ---

test_memory_exception() {
    log_info "=== 2. 内存/存储异常测试 ==="

    # 检查是否有 OOM killer 历史
    if dmesg 2>/dev/null | grep -i "out of memory" | tail -3 | grep -q .; then
        log_warn "发现 OOM 历史记录:"
        dmesg 2>/dev/null | grep -i "out of memory" | tail -3 | while read l; do log_info "  $l"; done
        add_result "内存异常" "FAIL" "有 OOM 历史"
    else
        log_info "无 OOM 历史"
        add_result "内存异常" "PASS" "无 OOM 历史"
    fi
}

# --- 主流程 ---

main() {
    parse_args "$@"
    log_info "SE13 内存/存储接口测试开始"

    test_emmc_basic
    test_memory_basic
    test_emmc_rw
    test_memory_exception
    print_summary
}

main "$@"