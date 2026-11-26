#!/bin/bash

# 平台通过 SSH 以 linaro 身份执行；需要 root 的脚本自动提权（sudo 密码固定 linaro）
if [ "$(id -u)" -ne 0 ]; then
    printf 'linaro\n' | sudo -S -p '' bash "$0" "$@"
    exit $?
fi
# ============================================================================
# SE13 SSD 接口测试
# 测试内容: NVMe SSD 检测、挂载、基本读写、卸载（闭环，无故障注入）
# 特别注意: 如果 SSD 未安装，输出日志说明，标记 SKIP（不静默跳过）
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

TEST_MODULE="SSD"

usage() {
    echo "用法: $0 [选项]"
    echo "  SE13 SSD 接口测试 (NVMe)"
    echo "  如果 SSD 未安装，会输出 QA_SKIP_SSD 并记录详细原因"
    echo "选项:"
    echo "  --help, -h          显示帮助"
    echo "  --verbose, -v       详细输出"
}

# 检测 SSD — 裸盘自动分区初始化, 返回可挂载的设备路径
detect_ssd() {
    local ssd_dev=""

    # NVMe: 有分区用分区, 裸盘自动 fdisk+mkfs.ext4
    if run_sudo test -b "/dev/nvme0n1" 2>/dev/null; then
        if run_sudo test -b "/dev/nvme0n1p1" 2>/dev/null; then
            ssd_dev="/dev/nvme0n1p1"
        else
            log_info "NVMe 裸盘, 自动分区+格式化..."
            echo -e "n\np\n1\n\n\nw" | run_sudo fdisk /dev/nvme0n1 > /dev/null 2>&1
            sleep 1
            run_sudo mkfs.ext4 -F /dev/nvme0n1p1 > /dev/null 2>&1
            run_sudo partprobe /dev/nvme0n1 2>/dev/null || true
            ssd_dev="/dev/nvme0n1p1"
        fi
    fi

    # SATA SSD
    if [ -z "$ssd_dev" ]; then
        local sata=$(run_sudo ls -d /sys/block/sd*/removable 2>/dev/null)
        for f in $sata; do
            [ "$(run_sudo cat "$f" 2>/dev/null)" = "0" ] && { ssd_dev="/dev/$(echo "$f" | cut -d'/' -f4)"; break; }
        done
    fi

    echo "$ssd_dev"
}

test_ssd_presence() {
    log_info "=== 1.1 SSD 设备检测 ==="

    local ssd_dev=$(detect_ssd)
    SSD_DEV="$ssd_dev"

    if [ -n "$ssd_dev" ]; then
        run_sudo lsblk -o NAME,SIZE,TYPE,MOUNTPOINT 2>/dev/null | grep -E "nvme|sd" | while read l; do log_info "  $l"; done
        run_sudo lspci 2>/dev/null | grep -i "non-volatile\|nvme" | while read l; do log_info "  $l"; done
        log_pass "SSD 已检测到: $ssd_dev"
        add_result "SSD 检测" "PASS" "$ssd_dev"
        return 0
    else
        log_info "未检测到 NVMe 或 SATA SSD"
        run_sudo lspci 2>/dev/null | grep -i "non-volatile\|nvme" || log_info "  (无 SSD PCIe 设备)"
        run_sudo ls /dev/nvme* 2>/dev/null || log_info "  /dev/nvme* 不存在"
        sentinel_skip "SSD" "SSD 设备未检测到"
        add_result "SSD 检测" "SKIP" "设备未安装"
        return 1
    fi
}

test_ssd_mount_rw() {
    [ -z "$SSD_DEV" ] && { add_result "SSD 挂载读写" "SKIP" "无 SSD 设备"; return; }

    log_info "=== 1.2 SSD 挂载与基本读写 ($SSD_DEV) ==="

    local mnt="/mnt/ssd_se13_test_$$"
    run_sudo mkdir -p "$mnt" 2>/dev/null

    if grep -q "$mnt" /proc/mounts 2>/dev/null; then
        run_sudo umount "$mnt" 2>/dev/null
    fi

    if run_sudo mount "$SSD_DEV" "$mnt" 2>/dev/null; then
        log_info "SSD 挂载成功: $SSD_DEV -> $mnt"
    else
        log_fail "SSD 挂载失败"
        add_result "SSD 挂载读写" "FAIL" "挂载 $SSD_DEV 失败"
        run_sudo rmdir "$mnt" 2>/dev/null
        return
    fi

    local test_file="$mnt/se13_ssd_test_$$.bin"
    if run_sudo dd if=/dev/zero of="$test_file" bs=1M count=100 2>/dev/null; then
        log_info "SSD 写入 100MB 成功"
        run_sudo dd if="$test_file" of=/dev/null bs=1M 2>/dev/null && {
            log_pass "SSD 读写测试通过"
            add_result "SSD 挂载读写" "PASS" "100MB 读写成功"
        }
        run_sudo rm -f "$test_file"
    else
        log_fail "SSD 写入失败"
        add_result "SSD 挂载读写" "FAIL" "写入失败"
    fi

    # 卸载并确认
    run_sudo umount "$mnt" 2>/dev/null
    if grep -q "$mnt" /proc/mounts 2>/dev/null; then
        run_sudo umount -l "$mnt" 2>/dev/null
    fi
    if grep -q "$mnt" /proc/mounts 2>/dev/null; then
        log_fail "SSD 卸载失败: $mnt 仍挂载"
        add_result "SSD 卸载" "FAIL" "仍挂载 $mnt"
    else
        log_pass "SSD 卸载成功"
        add_result "SSD 卸载" "PASS" "已卸载"
    fi
    run_sudo rmdir "$mnt" 2>/dev/null
}

main() {
    parse_args "$@"
    log_info "SE13 SSD 接口测试开始"

    test_ssd_presence
    if [ -n "$SSD_DEV" ]; then
        test_ssd_mount_rw
    fi
    print_summary
}


# 哨兵输出由内联 print_summary 处理

main "$@"