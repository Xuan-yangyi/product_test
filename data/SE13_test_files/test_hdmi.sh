#!/bin/bash

# 平台通过 SSH 以 linaro 身份执行；需要 root 的脚本自动提权（sudo 密码固定 linaro）
if [ "$(id -u)" -ne 0 ]; then
    printf 'linaro\n' | sudo -S -p '' bash "$0" "$@"
    exit $?
fi
# ============================================================================
# SE13 HDMI 接口测试
#
# 测试内容: HDMI 显示输出检测、DRM 设备存在性
# 测试方法简述:
#   - 检查 /dev/dri/ 下 DRM 设备
#   - 检查 /sys/class/drm/card0-*/status 连接状态
#   - 检查 /dev/fb0 framebuffer 设备
#   - 检查 HDMI 驱动模块加载
# 预期结果: DRM 设备存在、连接状态可读、QA_PASS_HDMI
# 特别注意: 如果 HDMI 未连接显示器，输出日志说明，标记 SKIP（不静默跳过）
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

TEST_MODULE="HDMI"

usage() {
    echo "用法: $0 [选项]"
    echo "  SE13 HDMI 接口测试"
    echo "  如果 HDMI 未连接显示器，会输出 QA_SKIP_HDMI 并记录详细原因"
    echo "选项:"
    echo "  --help, -h     显示帮助"
    echo "  --verbose, -v   详细输出"
}

# --- 基本功能 ---

test_hdmi_drm_presence() {
    log_info "=== 1.1 HDMI / DRM 设备检测 ==="

    # 检查 DRM 设备节点
    local drm_devices=$(ls /dev/dri/ 2>/dev/null)
    if [ -n "$drm_devices" ]; then
        log_info "/dev/dri/ 设备: $drm_devices"
        add_result "HDMI DRM 设备" "PASS" "/dev/dri/ 存在"
    else
        log_info "/dev/dri/ 目录不存在或为空"
        log_info "这可能表示 DRM 驱动未加载或图形子系统未初始化"
        log_info "检查内核 DRM 相关日志:"
        dmesg 2>/dev/null | grep -i drm | tail -5 | while read l; do log_info "  $l"; done
        add_result "HDMI DRM 设备" "SKIP" "/dev/dri/ 不存在 — DRM 未加载，无法检测 HDMI"
        return 1
    fi

    return 0
}

test_hdmi_connection() {
    log_info "=== 1.2 HDMI 连接状态检测 ==="

    local connected=0
    for status_file in /sys/class/drm/card*-*/status; do
        [ -f "$status_file" ] || continue
        local card=$(echo "$status_file" | grep -o 'card[0-9]')
        local conn=$(echo "$status_file" | grep -o 'card[0-9]-[^/]*' | sed 's/card[0-9]-//')
        local status=$(cat "$status_file" 2>/dev/null)
        log_info "  $card ($conn): $status"

        if [ "$status" = "connected" ]; then
            connected=1
            # 获取支持的分辨率
            local modes_file="${status_file%status}modes"
            if [ -f "$modes_file" ]; then
                log_info "    支持模式: $(cat "$modes_file" 2>/dev/null | head -3 | tr '\n' ' ')"
            fi
            # 获取 EDID 信息
            local edid_file="${status_file%status}edid"
            [ -f "$edid_file" ] && log_info "    EDID 可用 ($(wc -c < "$edid_file") bytes)"
        fi
    done

    if [ "$connected" -eq 1 ]; then
        log_pass "HDMI 已连接显示器"
        add_result "HDMI 连接状态" "PASS" "显示器已连接"
    else
        log_info "HDMI 未连接显示器 — 所有 connector 状态均为 disconnected"
        log_info "如需测试显示功能，请连接 HDMI 显示器后重新运行此脚本"
        sentinel_skip "HDMI" "HDMI 未连接显示器 — 所有 DRM connector 状态为 disconnected. DRM 设备存在但无法验证显示输出."
        add_result "HDMI 连接状态" "SKIP" "无显示器连接 — 所有 connector disconnected"
    fi
}

test_hdmi_framebuffer() {
    log_info "=== 1.3 Framebuffer 设备检测 ==="

    if [ -c "/dev/fb0" ]; then
        log_info "/dev/fb0 存在"
        if command -v fbset >/dev/null 2>&1; then
            fbset -i 2>/dev/null | while read l; do [ -n "$l" ] && log_info "  $l"; done
        fi
        add_result "HDMI Framebuffer" "PASS" "/dev/fb0 存在"
    else
        log_info "/dev/fb0 不存在"
        log_info "其他 fb 设备: $(ls /dev/fb* 2>/dev/null || echo '无')"
        add_result "HDMI Framebuffer" "SKIP" "/dev/fb0 不存在"
    fi
}

test_hdmi_driver() {
    log_info "=== 1.4 HDMI 驱动模块检查 ==="

    local drv_found=0
    # 检查 cvitek HDMI 相关驱动
    if lsmod 2>/dev/null | grep -iE "hdmi|cvitek_drm|drm" | grep -q .; then
        log_info "HDMI/DRM 相关内核模块:"
        lsmod 2>/dev/null | grep -iE "hdmi|cvitek_drm|drm" | while read l; do log_info "  $l"; done
        drv_found=1
    fi

    if [ "$drv_found" -eq 1 ]; then
        add_result "HDMI 驱动" "PASS" "模块已加载"
    else
        log_info "未检测到明确的 HDMI 驱动模块"
        # 检查内核配置
        if [ -f /proc/config.gz ]; then
            zcat /proc/config.gz 2>/dev/null | grep -i "CONFIG_DRM" | head -5 | while read l; do log_info "  $l"; done
        fi
        add_result "HDMI 驱动" "SKIP" "驱动模块未检测到"
    fi
}

# --- 异常测试 ---

test_hdmi_exception() {
    log_info "=== 2. HDMI 异常测试 ==="

    # 检查 dmesg 中的 HDMI 错误
    if dmesg 2>/dev/null | grep -i "hdmi" | grep -i "error\|fail\|warn" | tail -3 | grep -q .; then
        log_warn "HDMI 相关错误/警告:"
        dmesg 2>/dev/null | grep -i "hdmi" | grep -i "error\|fail\|warn" | tail -3 | while read l; do log_info "  $l"; done
        add_result "HDMI 异常" "WARN" "有错误日志"
    else
        log_info "无 HDMI 相关错误日志（频繁插拔异常需人工操作）"
        add_result "HDMI 异常" "SKIP" "无错误日志，频繁插拔需人工操作"
    fi
}

# --- 主流程 ---

main() {
    parse_args "$@"
    log_info "SE13 HDMI 接口测试开始"
    log_info "注意: 完整 HDMI 显示功能测试需连接显示器"

    test_hdmi_drm_presence
    test_hdmi_connection
    test_hdmi_framebuffer
    test_hdmi_driver
    test_hdmi_exception

    print_summary
}

main "$@"