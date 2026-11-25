#!/bin/bash

# 平台通过 SSH 以 linaro 身份执行；需要 root 的脚本自动提权（sudo 密码固定 linaro）
if [ "$(id -u)" -ne 0 ]; then
    printf 'linaro\n' | sudo -S -p '' bash "$0" "$@"
    exit $?
fi
# ============================================================================
# SE13 WiFi 基础功能测试 — 自包含版，无外部依赖
# 用法: bash test_wifi.sh [-v]
#
# 测试内容:
#   1. PCIe WiFi 模块检测 (lspci)
#   2. 驱动加载 (自动匹配 8852be/ax210)
#   3. 接口验证 (ip link show)
#
# 支持的模块: Realtek 8852BE, Intel AX210
# ============================================================================

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log_info()  { echo -e "${CYAN}[INFO]${NC}  $(date '+%H:%M:%S') $*"; }
log_pass()  { echo -e "${GREEN}[PASS]${NC}  $*"; }
log_fail()  { echo -e "${RED}[FAIL]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }

declare -a RESULTS=()
add_result() { RESULTS+=("$1|$2|$3"); }
VERBOSE=0
# 平台通过 SSH 以 linaro 身份执行，需要 root 的命令统一走 run_sudo
run_sudo() { echo linaro | sudo -S "$@"; }

print_summary() {
    echo ""; echo "=============================================="
    echo "  测试结果汇总"
    echo "=============================================="
    local p=0 f=0 s=0
    for r in "${RESULTS[@]}"; do
        local n="${r%%|*}"; local rest="${r#*|}"; local st="${rest%%|*}"; local re="${rest#*|}"
        case "$st" in
            PASS) echo -e "  ${GREEN}✓${NC} $n"; p=$((p+1)) ;;
            FAIL) echo -e "  ${RED}✗${NC} $n — $re"; f=$((f+1)) ;;
            SKIP) echo -e "  ${YELLOW}−${NC} $n — $re"; s=$((s+1)) ;;
            WARN) echo -e "  ${YELLOW}⚠${NC} $n — $re" ;;
        esac
    done
    echo "----------------------------------------------"
    echo -e "  ${GREEN}PASS:$p${NC}  ${RED}FAIL:$f${NC}  ${YELLOW}SKIP:$s${NC}"
    echo "=============================================="
    [ "$f" -gt 0 ] && { echo "QA_FAIL_WIFI"; exit 1; }
    echo "QA_PASS_WIFI"; exit 0
}

while [ $# -gt 0 ]; do
    case "$1" in
        --help|-h) echo "用法: $0 [-v]"; echo "SE13 WiFi 基础功能测试"; exit 0 ;;
        --verbose|-v) VERBOSE=1 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
    shift
done

# ============================================================================
detect_wifi_module() {
    local pci_info
    pci_info=$(lspci 2>/dev/null | grep -iE "network|wifi|wireless")
    if [ -z "$pci_info" ]; then
        return 1
    fi
    if echo "$pci_info" | grep -qiE "realtek|8852|b852"; then
        echo "8852be"
    elif echo "$pci_info" | grep -qiE "intel|ax210|iwl|ax200|ax201"; then
        echo "ax210"
    else
        echo "unknown:$pci_info"
    fi
}

find_driver() {
    local module="$1"
    case "$module" in
        8852be)
            # 搜索多个可能路径
            for p in /mnt/system/ko/3rd/8852be.ko /lib/modules/*/extra/8852be.ko /tmp/8852be.ko; do
                [ -f "$p" ] && { echo "$p"; return 0; }
            done
            # find 兜底
            local f
            f=$(find /mnt /lib/modules /opt /tmp -name "8852be.ko" -type f 2>/dev/null | head -1)
            [ -n "$f" ] && { echo "$f"; return 0; }
            return 1
            ;;
        ax210)
            local iwl="" iwlmvm=""
            for p in /mnt/system/ko/iwlwifi.ko /mnt/system/ko/3rd/iwlwifi.ko; do
                [ -f "$p" ] && { iwl="$p"; break; }
            done
            for p in /mnt/system/ko/iwlmvm.ko /mnt/system/ko/3rd/iwlmvm.ko; do
                [ -f "$p" ] && { iwlmvm="$p"; break; }
            done
            [ -n "$iwl" ] && [ -n "$iwlmvm" ] && { echo "$iwl $iwlmvm"; return 0; }
            return 1
            ;;
    esac
    return 1
}

load_driver() {
    local module="$1"
    local ko_path="$2"
    case "$module" in
        8852be)
            if lsmod | grep -q 8852be; then
                log_info "驱动已加载: 8852be"
                return 0
            fi
            log_info "insmod $ko_path"
            run_sudo insmod "$ko_path" rtw_country_code=US 2>/dev/null && return 0
            run_sudo insmod "$ko_path" 2>/dev/null && return 0
            return 1
            ;;
        ax210)
            local iwl=$(echo "$ko_path" | awk '{print $1}')
            local mvm=$(echo "$ko_path" | awk '{print $2}')
            lsmod | grep -q iwlwifi || { log_info "insmod $iwl"; run_sudo insmod "$iwl" 2>/dev/null || return 1; }
            lsmod | grep -q iwlmvm || { log_info "insmod $mvm"; run_sudo insmod "$mvm" 2>/dev/null || return 1; }
            return 0
            ;;
    esac
    return 1
}

# ============================================================================
log_info "SE13 WiFi 基础功能测试开始"
log_info "测试时间: $(date '+%Y-%m-%d %H:%M:%S')"

# --- 1. PCIe WiFi 检测 ---
log_info "=== 1. PCIe WiFi 模块检测 ==="
WIFI_MODULE=$(detect_wifi_module)
if [ -z "$WIFI_MODULE" ]; then
    log_warn "lspci 未检测到 WiFi/Network 设备"
    lspci 2>/dev/null | grep -iE "net|eth|controller" | while read l; do log_info "  $l"; done
    add_result "WiFi模块检测" "SKIP" "lspci 无 WiFi 设备"
    print_summary
fi
case "$WIFI_MODULE" in
    8852be) log_info "检测到: Realtek 8852BE"; add_result "WiFi模块检测" "PASS" "Realtek 8852BE" ;;
    ax210)   log_info "检测到: Intel AX210"; add_result "WiFi模块检测" "PASS" "Intel AX210" ;;
    unknown:*) log_info "检测到未知模块"; add_result "WiFi模块检测" "WARN" "未知模块" ;;
esac

# --- 2. 驱动加载 ---
log_info "=== 2. 驱动加载 ==="
DRV_PATH=$(find_driver "$WIFI_MODULE")
if [ -z "$DRV_PATH" ]; then
    log_fail "未找到驱动文件"
    log_info "搜索路径: /mnt/system/ko/3rd/, /lib/modules/, /tmp/"
    ls /mnt/system/ko/3rd/ 2>/dev/null | while read l; do [ -n "$l" ] && log_info "  /mnt/system/ko/3rd/$l"; done
    add_result "驱动加载" "FAIL" "驱动文件不存在"
    print_summary
fi
if load_driver "$WIFI_MODULE" "$DRV_PATH"; then
    log_pass "驱动加载完成"
    add_result "驱动加载" "PASS" "$WIFI_MODULE"
else
    log_fail "驱动加载失败"
    dmesg 2>/dev/null | grep -iE "8852|iwl|error|fail" | tail -3 | while read l; do log_info "  $l"; done
    add_result "驱动加载" "FAIL" "insmod 失败"
    print_summary
fi
sleep 2

# --- 3. 接口验证 ---
log_info "=== 3. WiFi 接口验证 ==="
WIFI_IFACE=$(ip link show 2>/dev/null | grep -oE 'wlp[0-9]+s[0-9]+|wlan[0-9]+' | head -1)
if [ -z "$WIFI_IFACE" ]; then
    log_fail "未找到 WiFi 接口 (wlp*/wlan*)"
    ip link show 2>/dev/null | while read l; do [ -n "$l" ] && log_info "  $l"; done
    add_result "接口验证" "FAIL" "无 WiFi 接口"
    print_summary
fi
WIFI_MAC=$(ip link show "$WIFI_IFACE" 2>/dev/null | grep -oE '([0-9a-f]{2}:){5}[0-9a-f]{2}' | head -1)
log_info "接口: $WIFI_IFACE  MAC: ${WIFI_MAC:-未知}"
add_result "接口验证" "PASS" "$WIFI_IFACE ($WIFI_MAC)"

print_summary